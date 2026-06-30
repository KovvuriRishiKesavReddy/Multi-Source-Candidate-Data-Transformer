"""
Resolves a single canonical field's value across multiple PartialRecords that
have been matched to the same candidate.

Source priority is defined per field CATEGORY, not as one global rule, since
"most trustworthy source" genuinely differs by field. The priority lists are
the explicit, defensible part of this design — every choice here should be
explainable in one sentence if asked.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schema.canonical import PartialRecord, ProvenanceEntry

# Highest priority first. A source not in the list is treated as lowest
# priority, in original-encounter order, after everything listed here.
SOURCE_PRIORITY: dict[str, list[str]] = {
    "identity": ["ats_json", "recruiter_notes"],     # name, email, phone
    "role": ["ats_json", "recruiter_notes"],          # current company/title
    "experience": ["ats_json", "recruiter_notes"],
    "education": ["ats_json", "recruiter_notes"],
}


@dataclass
class FieldResolution:
    value: object
    sources_used: list[str]
    agreed: bool
    conflicted: bool
    provenance: list[ProvenanceEntry]


def _priority_rank(source: str, category: str) -> int:
    order = SOURCE_PRIORITY.get(category, [])
    return order.index(source) if source in order else len(order)


def resolve_scalar_field(
    records_with_values: list[tuple[PartialRecord, object]],
    category: str,
    field_name: str,
) -> FieldResolution:
    """
    records_with_values: list of (record, value) pairs where value is the
    raw value that record contributed for this field (already filtered to
    non-None by the caller).
    """
    if not records_with_values:
        return FieldResolution(value=None, sources_used=[], agreed=False, conflicted=False, provenance=[])

    records_with_values.sort(key=lambda pair: _priority_rank(pair[0].source_name, category))

    winner_record, winner_value = records_with_values[0]
    sources_used = [r.source_name for r, _ in records_with_values]

    distinct_values = {str(v).strip().lower() for _, v in records_with_values}
    agreed = len(distinct_values) == 1 and len(records_with_values) > 1
    conflicted = len(distinct_values) > 1

    provenance = [
        ProvenanceEntry(
            field=field_name,
            source=r.source_name,
            method=(
                "selected as highest-priority source"
                if r is winner_record
                else "alternate value seen but lower priority, not used" + (
                    " (conflict)" if conflicted else ""
                )
            ),
        )
        for r, _ in records_with_values
    ]

    return FieldResolution(
        value=winner_value,
        sources_used=sources_used,
        agreed=agreed,
        conflicted=conflicted,
        provenance=provenance,
    )


def resolve_skills(
    records: list[PartialRecord],
    normalize_skill_fn,
    is_canonical_skill_fn,
) -> tuple[list[dict], list[ProvenanceEntry]]:
    """
    Skills are unioned across sources rather than priority-resolved — a skill
    mentioned by any credible source is worth keeping, and dropping ones only
    one source mentioned would throw away real signal for no good reason.

    Returns (skills_data, provenance) where skills_data is a list of dicts
    with name/sources/raw_is_canonical, ready for the caller to attach
    per-skill confidence (confidence scoring lives in confidence.py and needs
    match_method, which this function intentionally doesn't know about, to
    keep this function focused on the union/dedup logic only).
    """
    by_canonical_name: dict[str, dict] = {}
    provenance: list[ProvenanceEntry] = []

    for record in records:
        for raw_skill in record.skills:
            canonical = normalize_skill_fn(raw_skill)
            if not canonical:
                continue
            entry = by_canonical_name.setdefault(
                canonical,
                {"name": canonical, "sources": [], "any_canonical": False},
            )
            if record.source_name not in entry["sources"]:
                entry["sources"].append(record.source_name)
            if is_canonical_skill_fn(raw_skill):
                entry["any_canonical"] = True

    for canonical, entry in by_canonical_name.items():
        provenance.append(
            ProvenanceEntry(
                field=f"skills[{canonical}]",
                source=",".join(entry["sources"]),
                method="union across sources, deduped by canonical skill name",
            )
        )

    return list(by_canonical_name.values()), provenance