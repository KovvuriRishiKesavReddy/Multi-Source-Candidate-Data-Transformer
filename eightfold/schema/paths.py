"""
Resolves simple path expressions against a CandidateProfile (or any nested
pydantic model / dict / list combination). Supports exactly the path shapes
the config format from the brief actually uses:

    "full_name"             -> direct attribute
    "location.country"      -> nested attribute
    "emails[0]"              -> list index
    "experience[0].company"  -> list index then nested attribute
    "skills[].name"          -> "for every item in this list, give me .name"
                                (returns a list of names, not a single value)

This is intentionally NOT a general JSONPath implementation — the brief's
example config only ever needs these shapes, and a narrower, fully-understood
implementation is easier to defend in the demo video than a clever general
one with edge cases I haven't thought through.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

_TOKEN_RE = re.compile(r"([^.\[\]]+)(\[(\d*)\])?")


class PathResolutionError(Exception):
    pass


def _get_attr_or_key(obj, name: str):
    if isinstance(obj, BaseModel):
        if not hasattr(obj, name):
            raise PathResolutionError(f"'{name}' is not a field on {type(obj).__name__}")
        return getattr(obj, name)
    if isinstance(obj, dict):
        if name not in obj:
            raise PathResolutionError(f"'{name}' is not a key on this object")
        return obj[name]
    raise PathResolutionError(f"Cannot access '{name}' on a {type(obj).__name__}")


def resolve_path(profile, path: str):
    """
    Returns the resolved value, or None if any step along the way is
    legitimately empty (e.g. emails[0] when emails is []). Raises
    PathResolutionError only when the path itself references a field/segment
    that doesn't exist on the canonical schema at all — that's a config
    mistake, not a missing-data situation, and the two must be distinguished
    so on_missing handling and "unknown path" validation errors stay separate.
    """
    segments = path.split(".")
    current = profile

    for seg in segments:
        m = _TOKEN_RE.fullmatch(seg)
        if not m:
            raise PathResolutionError(f"Malformed path segment: '{seg}' in '{path}'")

        field_name, has_index, index_str = m.group(1), m.group(2), m.group(3)

        if current is None:
            # An earlier segment was legitimately empty (e.g. experience[0]
            # didn't exist because experience == []). Everything downstream
            # of that is just "missing", not a config error.
            return None

        current = _get_attr_or_key(current, field_name)

        if has_index is not None:
            if not isinstance(current, list):
                raise PathResolutionError(f"'{field_name}' is not a list, but path used '[...]' on it")

            if index_str == "":
                # "[].subfield" form: map the rest of the path over every
                # item in the list and return a list of results.
                remaining = ".".join(segments[segments.index(seg) + 1:])
                if not remaining:
                    return list(current)
                return [resolve_path(item, remaining) for item in current]

            idx = int(index_str)
            current = current[idx] if 0 <= idx < len(current) else None

    return current