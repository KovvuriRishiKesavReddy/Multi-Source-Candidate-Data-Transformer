# Multi-Source Candidate Data Transformer

Takes candidate data from an ATS JSON export (structured) and recruiter notes
(.txt, unstructured), merges records that belong to the same person across both
sources, resolves whatever they disagree on, and produces one canonical profile
per candidate — with provenance and confidence for every field. The output shape
itself is driven by a runtime config, so the same engine can serve different
consumers without any code changes.

Full design reasoning (pipeline, schema, merge policy, confidence formula, edge
cases) is in `Kovvuri Rishi Kesav Reddy_rishikesav2005@gmail.com_Eightfold.pdf`.
This README covers how to actually run it.

## Setup

```bash
pip install -r requirements.txt
```

Dependencies: `pydantic` (canonical schema + validation), `phonenumbers`
(E.164 normalization), `rapidfuzz` (fuzzy name matching fallback),
`python-dateutil` (date parsing), `pytest` (tests).

## Running it

Default config (full schema, confidence + provenance included):

```bash
python -m cli.main \
  --ats sample_inputs/ats_export.json \
  --notes sample_inputs/recruiter_notes.txt \
  --config sample_inputs/config_default.json \
  --output output.json
```

Minimal/custom config (different field names, no confidence/provenance,
missing fields omitted instead of nulled):

```bash
python -m cli.main \
  --ats sample_inputs/ats_export.json \
  --notes sample_inputs/recruiter_notes.txt \
  --config sample_inputs/config_minimal.json \
  --output output_minimal.json
```

Run both configs in one pass (useful for the demo video — second config's
output goes to `<output>.alt.json`):

```bash
python -m cli.main \
  --ats sample_inputs/ats_export.json \
  --notes sample_inputs/recruiter_notes.txt \
  --config sample_inputs/config_default.json \
  --config2 sample_inputs/config_minimal.json \
  --output output.json
```

Either `--ats` or `--notes` can be omitted entirely — the pipeline runs on
whatever sources are actually provided. If no `--output` is given, results
print to stdout instead of a file.

## Running tests

```bash
pytest tests/ -v
```

21 tests across extraction, normalization, merge/conflict-resolution, and
projection — including the specific conflict, missing-source, and
unmatched-config-path edge cases described in the design doc.

## Design decisions (summary — see PDF for full reasoning)

**Merge priority** (highest wins on disagreement): `ats_json` over
`recruiter_notes` for name/email/phone/company/title/experience/education.
**Skills** are unioned across sources rather than priority-resolved, since
dropping a skill only one source mentioned throws away real signal.

**Matching** across sources: normalized email exact match, then normalized
phone exact match, then a fuzzy name+company match as a last resort (weaker
signal, penalized in confidence).

**Confidence** is a simple additive score (base score per source + agreement
bonus − conflict penalty − fuzzy-match penalty, capped 0–1) — deliberately
not learned, so every number is traceable to a one-line reason.

**Config projection**: the projector only ever reads the canonical profile, never
the raw sources. `on_missing` (`null` / `omit` / `error`) applies to scalar fields
that are genuinely empty (`None` or `""`) — an empty list counts as a real result,
not missing data, so it isn't touched by `on_missing`. A config path that doesn't
exist on the schema at all is always a hard error no matter what `on_missing` says,
since that's a config bug, not missing data.

## Known limitations / descoped

- Only 2 source types implemented (ATS JSON + recruiter notes), per the
  brief's "at least one structured, one unstructured" minimum. GitHub/
  LinkedIn/resume extractors aren't built.
- No ML-based entity resolution or NLP extraction from free text — the notes
  extractor is regex + heuristics, conservative by design (leaves a field
  `None` rather than guessing if it's not clearly present).
- CLI only, no UI — intentional per the brief, which marks that surface as
  lower priority than the engine itself.
- Country/skill normalization use small hand-written lookup tables, not
  exhaustive — anything outside the table passes through unnormalized with
  a lower confidence score rather than being dropped or guessed.

## Example output

Run against the real sample inputs with `config_default.json` — all 4 candidates,
full schema, confidence + provenance included. Ananya Sharma is the clearest
example of merge logic at work: appears in both sources with a phone conflict
(ATS wins, confidence reduced, both values traceable in provenance) and a
partial skills overlap (notes contributes Kafka/System Design that ATS didn't
have):

```bash
python -m cli.main \
  --ats sample_inputs/ats_export.json \
  --notes sample_inputs/recruiter_notes.txt \
  --config sample_inputs/config_default.json \
  --output output_default.json
```

```json
[
  {
    "full_name": "Ananya Sharma",
    "primary_email": "ananya.sharma@gmail.com",
    "phone": "+919876543210",
    "skills": ["python", "django", "postgresql", "aws", "kafka", "system design"],
    "confidence": 0.845,
    "provenance": [
      { "field": "full_name", "source": "ats_json", "method": "selected as highest-priority source" },
      { "field": "full_name", "source": "recruiter_notes", "method": "alternate value seen but lower priority, not used" },
      { "field": "emails", "source": "ats_json", "method": "selected as primary (highest-priority source)" },
      { "field": "emails", "source": "recruiter_notes", "method": "selected as primary (highest-priority source)" },
      { "field": "phones", "source": "ats_json", "method": "selected as primary (highest-priority source) (conflict: sources disagree)" },
      { "field": "phones", "source": "recruiter_notes", "method": "alternate value, lower priority (conflict: sources disagree)" },
      { "field": "experience[0].company", "source": "ats_json", "method": "selected as highest-priority source" },
      { "field": "experience[0].company", "source": "recruiter_notes", "method": "alternate value seen but lower priority, not used" },
      { "field": "experience[0].title", "source": "ats_json", "method": "selected as highest-priority source" },
      { "field": "experience[0].title", "source": "recruiter_notes", "method": "alternate value seen but lower priority, not used" },
      { "field": "skills[python]", "source": "ats_json,recruiter_notes", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[django]", "source": "ats_json,recruiter_notes", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[postgresql]", "source": "ats_json", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[aws]", "source": "ats_json,recruiter_notes", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[kafka]", "source": "recruiter_notes", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[system design]", "source": "recruiter_notes", "method": "union across sources, deduped by canonical skill name" }
    ]
  },
  {
    "full_name": "Rohit Verma",
    "primary_email": "rohit.verma@outlook.com",
    "phone": "+919123456780",
    "skills": ["product strategy", "sql", "jira", "roadmapping", "figma", "stakeholder management"],
    "confidence": 0.809,
    "provenance": [
      { "field": "full_name", "source": "ats_json", "method": "selected as highest-priority source" },
      { "field": "full_name", "source": "recruiter_notes", "method": "alternate value seen but lower priority, not used" },
      { "field": "emails", "source": "ats_json", "method": "selected as primary (highest-priority source)" },
      { "field": "emails", "source": "recruiter_notes", "method": "selected as primary (highest-priority source)" },
      { "field": "phones", "source": "ats_json", "method": "selected as primary (highest-priority source)" },
      { "field": "experience[0].company", "source": "ats_json", "method": "selected as highest-priority source" },
      { "field": "experience[0].company", "source": "recruiter_notes", "method": "alternate value seen but lower priority, not used" },
      { "field": "experience[0].title", "source": "ats_json", "method": "selected as highest-priority source" },
      { "field": "experience[0].title", "source": "recruiter_notes", "method": "alternate value seen but lower priority, not used (conflict)" },
      { "field": "skills[product strategy]", "source": "ats_json,recruiter_notes", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[sql]", "source": "ats_json,recruiter_notes", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[jira]", "source": "ats_json", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[roadmapping]", "source": "ats_json", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[figma]", "source": "recruiter_notes", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[stakeholder management]", "source": "recruiter_notes", "method": "union across sources, deduped by canonical skill name" }
    ]
  },
  {
    "full_name": "Priya Iyer",
    "primary_email": "priya.iyer.work@gmail.com",
    "phone": "+919988766554",
    "skills": ["python", "machine learning", "pandas", "scikit-learn"],
    "confidence": 0.739,
    "provenance": [
      { "field": "full_name", "source": "ats_json", "method": "selected as highest-priority source" },
      { "field": "full_name", "source": "recruiter_notes", "method": "alternate value seen but lower priority, not used" },
      { "field": "emails", "source": "ats_json", "method": "selected as primary (highest-priority source)" },
      { "field": "phones", "source": "ats_json", "method": "selected as primary (highest-priority source)" },
      { "field": "experience[0].company", "source": "ats_json", "method": "selected as highest-priority source" },
      { "field": "experience[0].title", "source": "ats_json", "method": "selected as highest-priority source" },
      { "field": "skills[python]", "source": "ats_json", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[machine learning]", "source": "ats_json", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[pandas]", "source": "ats_json", "method": "union across sources, deduped by canonical skill name" },
      { "field": "skills[scikit-learn]", "source": "ats_json", "method": "union across sources, deduped by canonical skill name" }
    ]
  },
  {
    "full_name": "Karthik Reddy",
    "primary_email": "karthik.reddy.dev@gmail.com",
    "phone": "+919000011122",
    "skills": [],
    "confidence": 0.5,
    "provenance": [
      { "field": "full_name", "source": "recruiter_notes", "method": "selected as highest-priority source" },
      { "field": "emails", "source": "recruiter_notes", "method": "selected as primary (highest-priority source)" },
      { "field": "phones", "source": "recruiter_notes", "method": "selected as primary (highest-priority source)" },
      { "field": "experience[0].company", "source": "recruiter_notes", "method": "selected as highest-priority source" },
      { "field": "experience[0].title", "source": "recruiter_notes", "method": "selected as highest-priority source" }
    ]
  }
]
```

Note Karthik Reddy's `skills` is `[]` here, not `null`. His notes block never has a "Skills:" line (just loose mentions of Go/gRPC/Kubernetes that I'm not parsing as structured skills), so skills resolves to an empty list. I treat that as a real result — we looked and found nothing — not as missing data, so it doesn't get touched by `on_missing` the way a genuinely empty field (a `None`) would.

Run against `config_minimal.json` — same 4 profiles, different field names, no
confidence/provenance. `on_missing: "omit"` still drops genuinely missing scalar
fields (Priya's `location_country` is gone below since she has no location data),
but Karthik's `top_skills` stays as an empty list instead of getting dropped:

```bash
python -m cli.main \
  --ats sample_inputs/ats_export.json \
  --notes sample_inputs/recruiter_notes.txt \
  --config sample_inputs/config_minimal.json \
  --output output_minimal.json
```

```json
[
  {
    "name": "Ananya Sharma",
    "company": "Razorpay",
    "top_skills": ["python", "django", "postgresql", "aws", "kafka", "system design"]
  },
  {
    "name": "Rohit Verma",
    "company": "Freshworks",
    "top_skills": ["product strategy", "sql", "jira", "roadmapping", "figma", "stakeholder management"]
  },
  {
    "name": "Priya Iyer",
    "company": "Swiggy",
    "top_skills": ["python", "machine learning", "pandas", "scikit-learn"]
  },
  {
    "name": "Karthik Reddy",
    "company": "Postman",
    "top_skills": []
  }
]
```

## Project structure

```
schema/canonical.py      canonical PartialRecord + CandidateProfile models (pydantic)
schema/paths.py          path resolver (e.g. "skills[].name", "experience[0].company")
schema/projector.py      config-driven projection layer
schema/validator.py      validates projected output against the config

extractors/ats_json.py        structured source extractor
extractors/recruiter_notes.py unstructured source extractor (regex + heuristics)

normalize/phone.py    -> E.164
normalize/date.py     -> YYYY-MM
normalize/country.py  -> ISO-3166 alpha-2
normalize/skills.py   -> canonical skill names + synonym table

merge/matcher.py        groups records across sources into same-candidate clusters
merge/resolver.py       per-field conflict resolution + skills union
merge/confidence.py     additive confidence scoring
merge/build_profile.py  orchestrates the above into one CandidateProfile

cli/main.py    CLI entry point
tests/         pytest suite (21 tests)
sample_inputs/ sample ATS JSON, recruiter notes, and two example configs
```