"""
Skill name normalization -> canonical form.

Lowercase + trim, then look up against a synonym table. Anything not in the
table passes through lowercased/trimmed but unmodified — it's still usable,
just not guaranteed to be "the" canonical spelling, which is exactly why
is_canonical_skill() exists: it lets the confidence scorer reflect that
uncertainty rather than silently treating every skill the same.
"""

from __future__ import annotations

_SKILL_SYNONYMS: dict[str, str] = {
    "js": "javascript",
    "javascript": "javascript",
    "reactjs": "react",
    "react.js": "react",
    "react": "react",
    "node.js": "nodejs",
    "nodejs": "nodejs",
    "node": "nodejs",
    "ml": "machine learning",
    "machine learning": "machine learning",
    "py": "python",
    "python": "python",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "golang": "go",
    "go": "go",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "aws": "aws",
    "amazon web services": "aws",
    "sql": "sql",
}


def normalize_skill(raw: str) -> str:
    if not raw:
        return ""
    key = raw.strip().lower()
    return _SKILL_SYNONYMS.get(key, key)


def is_canonical_skill(raw: str) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in _SKILL_SYNONYMS