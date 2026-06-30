# Prompt Set — Eightfold Candidate Data Transformer

Use these in order. Each one builds on the last. Paste them as-is, or adapt wording —
the important part is the embedded context (schema, rules, file paths), since that's
what keeps the output consistent with your design doc.

Sample inputs already created at:
- sample_inputs/ats_export.json
- sample_inputs/recruiter_notes.txt
- sample_inputs/config_default.json
- sample_inputs/config_minimal.json

---

## PROMPT 1 — Project scaffold + canonical schema

```
I'm building a Python data pipeline for a take-home assignment. Set up the project
structure and the canonical data model first, no business logic yet.

Project layout:
  eightfold/
    extractors/      (one file per source type)
    normalize/        (pure normalization functions)
    merge/            (matching + conflict resolution + confidence)
    schema/           (canonical model + projector + validator)
    cli/              (entry point)
    tests/
    sample_inputs/    (already has: ats_export.json, recruiter_notes.txt,
                        config_default.json, config_minimal.json)

Use pydantic (v2) for the canonical schema. Define these models in schema/canonical.py:

CandidateProfile:
  candidate_id: str
  full_name: str
  emails: list[str]
  phones: list[str]              # E.164 format once normalized
  location: { city: str|None, region: str|None, country: str|None }  # country = ISO-3166 alpha-2
  links: { linkedin: str|None, github: str|None, portfolio: str|None, other: list[str] }
  headline: str|None
  years_experience: float|None
  skills: list[{ name: str, confidence: float, sources: list[str] }]
  experience: list[{ company: str, title: str, start: str|None, end: str|None, summary: str|None }]
  education: list[{ institution: str, degree: str|None, field: str|None, end_year: int|None }]
  provenance: list[{ field: str, source: str, method: str }]
  overall_confidence: float

Also define a lighter-weight intermediate model, PartialRecord, with the same fields
all optional, used by extractors before merging — extractors should never need to
guess values, so every field they don't find should just stay None/empty rather than
being defaulted to something fake. Each PartialRecord should also carry a `source_name`
field (e.g. "ats_json" or "recruiter_notes") so later stages know where it came from.

Generate candidate_id as a stable hash/uuid derived from normalized email if present,
else normalized phone, else a random uuid (we'll refine this in matching later).

Write a short docstring at the top of canonical.py explaining the separation between
PartialRecord (per-source, partial) and CandidateProfile (merged, canonical, complete).
```

---

## PROMPT 2 — ATS JSON extractor (structured source)

```
Now build extractors/ats_json.py.

Input: sample_inputs/ats_export.json — see actual file for exact shape, but the
top-level structure is { "export_date": ..., "candidates": [ {...}, ... ] }.
Field names in this source do NOT match our canonical schema (e.g. "candidate_name"
not "full_name", "contact_number" not "phones", "skillset" is a comma-separated
string not a list, "work_history"/"academics" use different nested key names than
our experience/education).

Write extract_ats_json(filepath: str) -> list[PartialRecord] that:
- Loads the JSON, handling the case where the file is missing or malformed (log a
  warning, return an empty list — must not crash the whole pipeline).
- For each candidate entry, maps fields onto PartialRecord. Split "skillset" on
  commas into individual skill name strings (don't normalize/canonicalize yet,
  that's a separate stage).
- Skips any candidate entry where full_name is empty/missing AND email is invalid/
  missing (this is our minimum bar for "this record is unusable garbage") — log
  each skip with a reason, but keep processing the rest of the file.
- For every field successfully populated, record a provenance entry with
  source="ats_json" and a one-line method description (e.g. "direct field mapping",
  "split on comma").
- Leaves any field it has no data for as None — never invent a value.

Add a basic test in tests/test_ats_extractor.py that runs this against the real
sample_inputs/ats_export.json and asserts: 3 valid candidates are extracted (the
4th malformed one is skipped), and Ananya Sharma's raw phone numbers and skills
list come through correctly before normalization.
```

---

## PROMPT 3 — Recruiter notes extractor (unstructured source)

```
Now build extractors/recruiter_notes.py.

Input: sample_inputs/recruiter_notes.txt — free text, candidates separated by lines
like "=== Candidate: <name> ===". Within each block, fields appear inconsistently:
sometimes "Email: x", sometimes just a bare email address on its own line, sometimes
"Phone:", sometimes "Skills:" as a labeled line. Some blocks are missing fields
entirely (e.g. one candidate has no email/phone at all, just a vague mention).

Write extract_recruiter_notes(filepath: str) -> list[PartialRecord] that:
- Splits the file into per-candidate blocks using the "=== Candidate: ... ===" marker.
- Within each block, uses regex to pull: an email address (standard email regex,
  anywhere in the block), a phone number (regex tolerant of spaces/dashes/+91 prefix),
  current company + title if a line matches a pattern like "at <Company> as <Title>"
  or "Currently <Title> at <Company>" (handle both orders, they appear in the sample),
  and a skills list from a line starting with "Skills:" (comma-separated).
- If a field genuinely can't be found in the block, leaves it as None — do not
  attempt to infer or guess it from surrounding prose.
- Treats the rest of the block as a free-text note, stored somewhere reasonable
  (e.g. as the `summary` on a single open-ended experience entry, or skip if that
  feels forced — your call, just document the decision in a comment).
- Records provenance with source="recruiter_notes" and the method used (e.g.
  "regex: email pattern", "regex: company/title pattern").

Add tests/test_notes_extractor.py asserting: 4 candidate blocks are found, Karthik
Reddy (who only appears in this source) is extracted with email/phone/company
correctly, and Priya Iyer's block correctly produces None for email and phone since
the text says they weren't confirmed yet.
```

---

## PROMPT 4 — Normalizers

```
Build the normalize/ package as pure, independently testable functions. No classes
needed, just functions, each handling failure by returning None rather than raising
or guessing.

normalize/phone.py:
  normalize_phone(raw: str, default_region: str = "IN") -> str | None
  Use the `phonenumbers` library. Parse with default_region as fallback for numbers
  without a country code. Return E.164 format if valid, None if unparseable/invalid.
  Must handle inputs like "+91 98765 43210", "9876512345", "+91-99887-66554",
  "+91 90000 11122", and garbage strings without crashing.

normalize/date.py:
  normalize_date(raw: str) -> str | None
  Convert various date-ish strings to "YYYY-MM". Sample inputs are already mostly
  "YYYY-MM" so this should mainly validate/passthrough, but should also handle
  None/empty input by returning None, and not crash on garbage.

normalize/country.py:
  normalize_country(raw: str) -> str | None
  Small lookup dict mapping common country name variants to ISO-3166 alpha-2
  (e.g. "India" -> "IN", "United States" -> "US", "USA" -> "US", "U.S." -> "US").
  Return None if not found in the table rather than guessing.

normalize/skills.py:
  normalize_skill(raw: str) -> str
  Lowercase, strip whitespace, then look up against a synonym dict, e.g.:
    "js": "javascript", "reactjs": "react", "node.js": "nodejs", "ml": "machine learning",
    "py": "python", "k8s": "kubernetes", "golang": "go"
  If not in the dict, return the lowercased/trimmed value as-is (still usable, just
  not guaranteed canonical — confidence scoring elsewhere will reflect this).
  Also write is_canonical_skill(raw: str) -> bool so the confidence scorer can check
  whether a skill came from the known table or passed through unchanged.

Write tests/test_normalize.py covering: valid and invalid phone numbers from the
sample data, a None/empty date, an unrecognized country string, and at least 3
skill synonym lookups plus one passthrough case.
```

---

## PROMPT 5 — Matching + conflict resolution + confidence

```
Build merge/matcher.py, merge/resolver.py, merge/confidence.py. This is the core
logic of the whole assignment, so be explicit and well-commented — every decision
needs to be explainable in one sentence, since I have to defend this in a demo video.

merge/matcher.py:
  group_records(records: list[PartialRecord]) -> list[list[PartialRecord]]
  Groups PartialRecords that represent the same candidate. Match priority, in order:
    1. Normalized email exact match (case-insensitive)
    2. Else normalized phone exact match (E.164)
    3. Else fuzzy match on (full_name, current company from experience[0]) using
       rapidfuzz, with a clearly named threshold constant (e.g. FUZZY_NAME_THRESHOLD = 85)
  Records that don't match any existing group become their own group of size 1.
  Tag each group with which match method produced it, since fuzzy matches should
  carry lower confidence downstream.

merge/resolver.py:
  resolve_field(records: list[PartialRecord], field_path: str, source_priority: list[str]) -> (value, provenance_entries)
  For non-skill fields: pick the value from the highest-priority source (per
  source_priority list, e.g. ["ats_json", "recruiter_notes"]) that has a non-null
  value for this field. If multiple sources at different priority both have values
  and they DISAGREE, still pick the higher-priority one but mark the conflict
  (store both raw values in provenance, not just the winner).
  For skills specifically: union all sources' skill lists instead of picking one
  winner — write a separate resolve_skills() that merges by normalized skill name,
  and if a skill appears in multiple sources, mark it as agreed upon.

  Use this priority table (define as a constant dict at the top of the file, field
  category -> priority list):
    name/email/phone:        ["ats_json", "recruiter_notes"]
    current_company/title:   ["ats_json", "recruiter_notes"]
    experience/education:    ["ats_json", "recruiter_notes"]
    skills:                  union, not priority-based

merge/confidence.py:
  score_field_confidence(sources_used: list[str], agreed: bool, match_method: str) -> float
  Simple additive formula, capped [0, 1]:
    base = 0.9 if "ats_json" in sources_used else 0.5
    if agreed (multiple sources had the same value): base += 0.1
    if there was a conflict (multiple sources disagreed): base -= 0.2
    if the candidate group was formed via fuzzy match rather than exact email/phone: base -= 0.15
    clamp to [0.0, 1.0]
  Also write score_overall_confidence(profile) that averages the per-field
  confidences into the profile's overall_confidence.

merge/build_profile.py:
  build_canonical_profile(group: list[PartialRecord], match_method: str) -> CandidateProfile
  Orchestrates the above: resolves every canonical field using resolver.py, builds
  the skills list with per-skill confidence and sources, fills provenance, computes
  overall_confidence, generates candidate_id.

Write tests/test_merge.py using the real sample data covering: Ananya Sharma's
phone conflict resolves to the ATS value with reduced confidence and both raw
values present in provenance, Ananya's skills list is a union including Kafka and
System Design from the notes source, Karthik Reddy (single-source) still produces
a complete, valid profile, and Priya Iyer's missing email/phone in the notes source
doesn't overwrite or corrupt the ATS source's values for those fields.
```

---

## PROMPT 6 — Config-driven projection + validation

```
Build schema/projector.py and schema/validator.py — this is the "required twist"
from the brief, so it needs to be solid.

The config format (see sample_inputs/config_default.json and config_minimal.json
for real examples) has:
  "fields": [ { "path": str, "from": str (optional), "type": str,
                "required": bool (optional), "normalize": str (optional) }, ... ]
  "include_confidence": bool
  "include_provenance": bool (optional, default true)
  "on_missing": "null" | "omit" | "error"

schema/projector.py:
  project(profile: CandidateProfile, config: dict) -> dict
  For each field in config["fields"]:
    - Resolve the value from `profile` using the "from" path if given, else use
      "path" directly as the lookup path against the canonical profile. Support
      simple paths: dotted access ("location.country"), array indexing
      ("emails[0]", "experience[0].company"), and array-of-field projection
      ("skills[].name" -> list of all skill names).
    - If "normalize" is specified in the field config, re-apply that normalizer
      (E164, canonical, etc.) even if the canonical value is already normalized —
      this lets the config request a DIFFERENT normalization than what's stored
      internally; document this design choice in a comment.
    - Apply on_missing policy if the resolved value is None/empty:
        "null"  -> include the key with value None
        "omit"  -> drop the key from the output entirely
        "error" -> raise a clear ProjectionError naming the field and config,
                   abort the whole projection for this candidate (don't return
                   a partial object)
    - If "required": true and the value is missing, this is always an error
      regardless of on_missing setting — required fields can't be silently
      null/omitted.
  After building the field values, attach "confidence" per field only if
  include_confidence is true, and a top-level "provenance" array only if
  include_provenance is not explicitly false.
  Return the final dict.

schema/validator.py:
  validate_against_config(output: dict, config: dict) -> list[str]  # list of errors, empty if valid
  Build a lightweight expected-shape check from config["fields"] (right keys present,
  right basic type per declared "type": "string"/"string[]"/"number"/etc.) and
  validate the projector's output against it BEFORE returning to the caller.
  This should catch our own bugs, not just bad input — i.e. if the projector has
  a mistake, this should catch the output not matching what the config asked for.

Write tests/test_projector.py covering: config_default.json produces a valid
result for Ananya Sharma with primary_email correctly pulled from emails[0],
config_minimal.json correctly omits missing fields rather than nulling them
(test this against a candidate who lacks a "company" e.g. Priya Iyer if no
experience entry resolved), and a deliberately broken config requesting a
nonexistent canonical path causes a clear validation error rather than a
silent empty result.
```

---

## PROMPT 7 — CLI + end-to-end wiring + README

```
Build cli/main.py to wire everything together end-to-end, plus a README.

CLI behavior:
  python -m cli.main \
    --ats sample_inputs/ats_export.json \
    --notes sample_inputs/recruiter_notes.txt \
    --config sample_inputs/config_default.json \
    --output output.json

Should:
  1. Run both extractors (skip any source gracefully if its file path isn't
     provided or doesn't exist — log a warning, continue with whatever sources
     ARE available, per the "any source may be missing" requirement).
  2. Group/match records, resolve conflicts, build canonical profiles for every
     distinct candidate found across all provided sources.
  3. Project each canonical profile through the given config.
  4. Validate each projected result; if validation fails for a candidate, log
     the error clearly and skip just that candidate's output rather than
     crashing the whole run.
  5. Write the final list of projected candidate JSON objects to --output
     (pretty-printed, 2-space indent). If --output isn't given, print to stdout.
  6. Print a short run summary to stderr: how many candidates were found, how
     many sources contributed, how many were skipped/malformed and why.

Also add --config2 as an optional second flag that, if given, ALSO runs the
exact same canonical profiles through a second config and writes to
<output>.alt.json — this is purely so I can demonstrate two different output
shapes from one run for the demo video without re-running the whole pipeline.

Then write README.md with:
  - One-paragraph description of what this is
  - Exact setup steps (pip install -r requirements.txt, list the actual
    dependencies: pydantic, phonenumbers, rapidfuzz, python-dateutil)
  - Exact run command using the real sample_inputs files, both for the default
    config and the minimal config
  - How to run tests (pytest tests/)
  - A short "Design decisions" section that summarizes the merge priority table,
    confidence formula, and on_missing policy in a few lines (point to the design
    PDF for full reasoning, don't duplicate it)
  - A "Known limitations / descoped" section listing what's NOT handled (no
    GitHub/LinkedIn/resume sources, no ML-based entity resolution, simple
    regex-based notes extraction)

Run the whole pipeline against the real sample files with both configs and paste
the actual output JSON into the README under an "Example output" section so
the grader can see results without running anything.
```

---

## Notes for using these efficiently under time pressure

- Run prompts 2 and 3 in parallel if you have two sessions/windows open — the
  extractors don't depend on each other.
- Prompt 5 is the one to spend the most actual thinking time on, not just
  copy-pasting the answer — this is what graders will probe hardest in your
  demo video ("why did you pick ATS over notes for X").
- After prompt 5, do a sanity pass yourself: open the merge output for Ananya
  Sharma and check the phone conflict and skill union actually look right
  before moving on — catching a wrong merge rule early is much cheaper than
  after the projector and tests are built on top of it.
- Prompt 7's last step (paste real output into README) doubles as your final
  end-to-end smoke test — if it crashes or looks wrong, you'll catch it before
  recording the demo video, not during.
