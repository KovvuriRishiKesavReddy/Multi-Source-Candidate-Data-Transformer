"""
Groups PartialRecords from different sources that represent the same candidate.

Match priority, in order (first one that succeeds wins, we don't keep
checking the weaker signals once a strong one has matched):

    1. Normalized email exact match (case-insensitive)
    2. Normalized phone exact match (E.164)
    3. Fuzzy match on (full_name, current company) as a last resort

The first two are treated as near-certain identity signals. The fuzzy
fallback is a meaningfully weaker guess — two different people can share a
similar name, so any group formed this way is tagged accordingly and the
confidence scorer applies a penalty for it later.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from ..normalize.phone import normalize_phone
from ..schema.canonical import PartialRecord

FUZZY_NAME_THRESHOLD = 85  # 0-100 rapidfuzz score; below this, treat as no match


@dataclass
class MatchGroup:
    records: list[PartialRecord] = field(default_factory=list)
    match_method: str = "single_source"  # "email" | "phone" | "fuzzy_name" | "single_source"


def _norm_email(email: str) -> str:
    return email.strip().lower()


def _current_company(record: PartialRecord) -> str | None:
    if record.experience:
        return record.experience[0].company
    return None


def _fuzzy_match(a: PartialRecord, b: PartialRecord) -> bool:
    if not a.full_name or not b.full_name:
        return False
    name_score = fuzz.ratio(a.full_name.lower(), b.full_name.lower())
    if name_score < FUZZY_NAME_THRESHOLD:
        return False
    # Require company agreement too if both have one — name similarity alone
    # is too weak a signal on its own (lots of people share similar names).
    company_a, company_b = _current_company(a), _current_company(b)
    if company_a and company_b:
        return company_a.strip().lower() == company_b.strip().lower()
    # If we don't have company info for at least one side, fall back to name
    # similarity alone, but only at a stricter threshold to compensate.
    return name_score >= 95


def group_records(records: list[PartialRecord]) -> list[MatchGroup]:
    groups: list[MatchGroup] = []

    for record in records:
        matched_group: MatchGroup | None = None
        matched_method: str | None = None

        record_emails = {_norm_email(e) for e in record.emails if e}
        record_phones = {normalize_phone(p) for p in record.phones if p}
        record_phones.discard(None)

        for group in groups:
            group_emails = {
                _norm_email(e) for r in group.records for e in r.emails if e
            }
            if record_emails & group_emails:
                matched_group, matched_method = group, "email"
                break

        if matched_group is None:
            for group in groups:
                group_phones = {
                    normalize_phone(p) for r in group.records for p in r.phones if p
                }
                group_phones.discard(None)
                if record_phones & group_phones:
                    matched_group, matched_method = group, "phone"
                    break

        if matched_group is None:
            for group in groups:
                if any(_fuzzy_match(record, existing) for existing in group.records):
                    matched_group, matched_method = group, "fuzzy_name"
                    break

        if matched_group is not None:
            matched_group.records.append(record)
            # The group's recorded match_method should reflect the WEAKEST
            # signal that was needed to assemble it — e.g. if two records
            # matched by email but a third only joined via fuzzy name, the
            # group as a whole is only as trustworthy as that weakest link.
            # method_strength: higher = stronger signal. We track the
            # *minimum* strength seen so far, defaulting a fresh group's
            # initial strength to "infinite" (no signal needed yet, since
            # there was nothing to match against).
            method_strength = {"email": 3, "phone": 2, "fuzzy_name": 1, "single_source": 99}
            if method_strength[matched_method] < method_strength[matched_group.match_method]:
                matched_group.match_method = matched_method
        else:
            groups.append(MatchGroup(records=[record], match_method="single_source"))

    return groups