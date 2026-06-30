"""
Orchestrates matcher.py + resolver.py + confidence.py into one finished
CandidateProfile per matched group of PartialRecords. This is the one place
that touches every part of the merge stage, so it's intentionally thin —
each sub-step's logic lives in its own module and is independently tested.
"""

from __future__ import annotations

from ..merge.confidence import score_field_confidence, score_overall_confidence
from ..merge.matcher import MatchGroup
from ..merge.resolver import resolve_scalar_field, resolve_skills
from ..normalize.country import normalize_country
from ..normalize.date import normalize_date
from ..normalize.phone import normalize_phone
from ..normalize.skills import is_canonical_skill, normalize_skill
from ..schema.canonical import (
    CandidateProfile,
    Education,
    Experience,
    Links,
    Location,
    ProvenanceEntry,
    Skill,
    generate_candidate_id,
)


def _values_for(records, getter):
    """Returns [(record, value), ...] for every record where getter(record) is truthy."""
    out = []
    for r in records:
        v = getter(r)
        if v:
            out.append((r, v))
    return out


def build_canonical_profile(group: MatchGroup) -> CandidateProfile:
    records = group.records
    all_provenance: list[ProvenanceEntry] = []
    field_confidences: list[float] = []

    def resolve_and_score(category: str, field_name: str, getter):
        pairs = _values_for(records, getter)
        resolution = resolve_scalar_field(pairs, category, field_name)
        all_provenance.extend(resolution.provenance)
        if resolution.sources_used:
            conf = score_field_confidence(
                resolution.sources_used, resolution.agreed, resolution.conflicted, group.match_method
            )
            field_confidences.append(conf)
        return resolution.value

    # --- identity fields ---
    full_name = resolve_and_score("identity", "full_name", lambda r: r.full_name)

    # Email/phone are lists in the canonical schema because a person can
    # legitimately have more than one. But when two sources both report a
    # value clearly intended as THE primary contact and they disagree, that
    # is a conflict, not two equally-valid facts — we can't tell those cases
    # apart automatically, so the defensible rule is: order the list with
    # the highest-priority source's value first (that's "the" value
    # consumers should treat as primary), keep other distinct values after
    # it rather than discarding them, and explicitly record the disagreement
    # in provenance + reflect it in confidence either way.
    def resolve_list_field(category: str, field_name: str, getter, value_normalizer=None):
        pairs = []
        for r in records:
            for v in getter(r):
                if v:
                    pairs.append((r, v))
        if not pairs:
            return [], []

        pairs.sort(key=lambda pair: _priority_rank_for(pair[0].source_name, category))
        ordered_values = list(dict.fromkeys(v for _, v in pairs))

        # Conflict detection should compare values in their normalized form
        # where one is available (e.g. "+91 98765 43210" and "9876512345"
        # are different numbers once normalized, but "+91 98765 43210" and
        # "+91-98765-43210" would be the SAME number and shouldn't count as
        # a conflict just because the raw text differs).
        def comparable(v):
            return value_normalizer(v) if value_normalizer else str(v).strip().lower()

        distinct_normalized = {comparable(v) for _, v in pairs}
        distinct_normalized.discard(None)
        conflicted = len(distinct_normalized) > 1
        agreed = len(distinct_normalized) == 1 and len(pairs) > 1
        sources_used = list(dict.fromkeys(r.source_name for r, _ in pairs))

        prov = []
        for r, v in pairs:
            is_primary = v == ordered_values[0]
            method = "selected as primary (highest-priority source)" if is_primary else "alternate value, lower priority"
            if conflicted:
                method += " (conflict: sources disagree)"
            prov.append(ProvenanceEntry(field=field_name, source=r.source_name, method=method))

        conf = score_field_confidence(sources_used, agreed, conflicted, group.match_method)
        field_confidences.append(conf)
        return ordered_values, prov

    def _priority_rank_for(source: str, category: str) -> int:
        order = SOURCE_PRIORITY_LOCAL.get(category, [])
        return order.index(source) if source in order else len(order)

    SOURCE_PRIORITY_LOCAL = {"identity": ["ats_json", "recruiter_notes"]}

    emails_raw_ordered, emails_prov = resolve_list_field(
        "identity", "emails", lambda r: r.emails, value_normalizer=lambda v: v.strip().lower()
    )
    phones_raw_ordered, phones_prov = resolve_list_field(
        "identity", "phones", lambda r: r.phones, value_normalizer=normalize_phone
    )
    all_provenance.extend(emails_prov)
    all_provenance.extend(phones_prov)

    emails = list(dict.fromkeys(e.strip().lower() for e in emails_raw_ordered if e))
    phones_normalized = list(
        dict.fromkeys(filter(None, (normalize_phone(p) for p in phones_raw_ordered)))
    )

    # --- role / current experience (category "role" priority applies to
    # the first experience entry each source contributed; full experience
    # lists below are concatenated since each entry is its own job, not a
    # field to pick-a-winner on) ---
    company = resolve_and_score(
        "role", "experience[0].company",
        lambda r: r.experience[0].company if r.experience else None,
    )
    title = resolve_and_score(
        "role", "experience[0].title",
        lambda r: r.experience[0].title if r.experience else None,
    )

    experience_entries: list[Experience] = []
    seen_exp = set()
    for r in records:
        for exp in r.experience:
            key = (exp.company, exp.title, exp.start, exp.end)
            if key in seen_exp:
                continue
            seen_exp.add(key)
            experience_entries.append(
                Experience(
                    company=exp.company,
                    title=exp.title,
                    start=normalize_date(exp.start),
                    end=normalize_date(exp.end),
                    summary=exp.summary,
                )
            )
    # Ensure the resolved winner's company/title is reflected as entry[0] if
    # it differs (e.g. resolver picked ATS's title over notes' for the
    # current role specifically), so the canonical record's "headline" role
    # matches what resolve_and_score decided rather than whichever source
    # happened to be concatenated first.
    if experience_entries and (company or title):
        experience_entries[0].company = company or experience_entries[0].company
        experience_entries[0].title = title or experience_entries[0].title

    education_entries: list[Education] = []
    seen_edu = set()
    for r in records:
        for edu in r.education:
            key = (edu.institution, edu.degree, edu.field, edu.end_year)
            if key in seen_edu:
                continue
            seen_edu.add(key)
            education_entries.append(
                Education(
                    institution=edu.institution,
                    degree=edu.degree,
                    field=edu.field,
                    end_year=edu.end_year,
                )
            )

    location = Location(
        city=resolve_and_score("identity", "location.city", lambda r: r.city),
        region=resolve_and_score("identity", "location.region", lambda r: r.region),
        country=normalize_country(
            resolve_and_score("identity", "location.country", lambda r: r.country)
        ),
    )
    links = Links(
        linkedin=resolve_and_score("identity", "links.linkedin", lambda r: r.linkedin),
        github=resolve_and_score("identity", "links.github", lambda r: r.github),
        portfolio=resolve_and_score("identity", "links.portfolio", lambda r: r.portfolio),
    )
    headline = resolve_and_score("identity", "headline", lambda r: r.headline)
    years_experience = resolve_and_score("identity", "years_experience", lambda r: r.years_experience)

    skills_data, skills_provenance = resolve_skills(records, normalize_skill, is_canonical_skill)
    all_provenance.extend(skills_provenance)
    skills: list[Skill] = []
    for s in skills_data:
        conf = score_field_confidence(
            s["sources"],
            agreed=len(s["sources"]) > 1,
            conflicted=False,  # skills are unioned, not contested, so no conflict concept here
            match_method=group.match_method,
        )
        # Skills not found in the canonical synonym table carry an extra
        # haircut on confidence — we can't vouch for the spelling being
        # canonical, separate from how many sources mentioned it.
        if not s["any_canonical"]:
            conf = max(0.0, conf - 0.1)
        skills.append(Skill(name=s["name"], confidence=round(conf, 3), sources=s["sources"]))
        field_confidences.append(conf)

    overall_confidence = score_overall_confidence(field_confidences)

    return CandidateProfile(
        candidate_id=generate_candidate_id(emails, phones_normalized),
        full_name=full_name or "Unknown",
        emails=emails,
        phones=phones_normalized,
        location=location,
        links=links,
        headline=headline,
        years_experience=years_experience,
        skills=skills,
        experience=experience_entries,
        education=education_entries,
        provenance=all_provenance,
        overall_confidence=overall_confidence,
    )