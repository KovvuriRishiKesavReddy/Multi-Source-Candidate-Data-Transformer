"""
Confidence scoring — deliberately simple and additive, not learned, so every
number is traceable to a one-line reason. Each adjustment below is named so
the reasoning is visible directly in the code, not buried in a formula.
"""

from __future__ import annotations

BASE_SCORE_BY_SOURCE: dict[str, float] = {
    "ats_json": 0.9,   # structured, presumably reviewed before export
    "recruiter_notes": 0.5,  # free text, unreviewed, more error-prone to extract
}
DEFAULT_BASE_SCORE = 0.5

AGREEMENT_BONUS = 0.10       # multiple sources had the same value
CONFLICT_PENALTY = 0.20      # multiple sources disagreed on the value
FUZZY_MATCH_PENALTY = 0.15   # the candidate group itself was formed via fuzzy name match


def score_field_confidence(
    sources_used: list[str],
    agreed: bool,
    conflicted: bool,
    match_method: str,
) -> float:
    if not sources_used:
        return 0.0

    base = max(BASE_SCORE_BY_SOURCE.get(s, DEFAULT_BASE_SCORE) for s in sources_used)

    score = base
    if agreed:
        score += AGREEMENT_BONUS
    if conflicted:
        score -= CONFLICT_PENALTY
    if match_method == "fuzzy_name":
        score -= FUZZY_MATCH_PENALTY

    return max(0.0, min(1.0, score))


def score_overall_confidence(field_confidences: list[float]) -> float:
    if not field_confidences:
        return 0.0
    return round(sum(field_confidences) / len(field_confidences), 3)