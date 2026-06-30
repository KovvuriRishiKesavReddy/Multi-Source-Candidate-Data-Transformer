from __future__ import annotations

from ..normalize.country import normalize_country
from ..normalize.phone import normalize_phone
from ..normalize.skills import normalize_skill
from ..schema.canonical import CandidateProfile
from ..schema.paths import resolve_path, PathResolutionError

_NORMALIZERS = {
    "E164": normalize_phone,
    "canonical": normalize_skill,
    "ISO-3166": normalize_country,
}


class ProjectionError(Exception):
    pass


def _is_missing(value) -> bool:
    """
    None and empty strings count as "missing" — genuinely absent data.
    An empty LIST does not count as missing: it means we attempted
    extraction/resolution for a list-typed field and found zero items,
    which is a real, honest result (e.g. "this candidate has no skills
    listed anywhere") rather than "we have no idea". Treating the two
    the same would make on_missing's "omit"/"error" behavior fire on a
    perfectly valid empty result, which is the wrong call for list fields
    specifically.
    """
    if value is None:
        return True
    if isinstance(value, str) and len(value) == 0:
        return True
    return False


def _apply_normalize(value, normalize_name: str | None):
    if normalize_name is None or value is None:
        return value
    fn = _NORMALIZERS.get(normalize_name)
    if fn is None:
        # An unknown normalizer name in the config is a config mistake, not
        # a missing-data case — surface it loudly rather than silently
        # skipping the requested normalization.
        raise ProjectionError(f"Unknown normalize type '{normalize_name}' in config")
    if isinstance(value, list):
        return [fn(v) for v in value]
    return fn(value)


def project(profile: CandidateProfile, config: dict) -> dict:
    fields = config.get("fields", [])
    on_missing = config.get("on_missing", "null")
    include_confidence = config.get("include_confidence", False)
    include_provenance = config.get("include_provenance", True)

    if on_missing not in ("null", "omit", "error"):
        raise ProjectionError(f"Invalid on_missing policy: '{on_missing}'")

    output: dict = {}

    for field_cfg in fields:
        out_path = field_cfg["path"]
        from_path = field_cfg.get("from", out_path)
        required = field_cfg.get("required", False)
        normalize_name = field_cfg.get("normalize")

        try:
            value = resolve_path(profile, from_path)
        except PathResolutionError as e:
            # A path that doesn't exist on the canonical schema at all is
            # always a hard error, regardless of on_missing — on_missing
            # governs legitimately-empty DATA, not a typo'd/nonexistent path.
            raise ProjectionError(
                f"Field '{out_path}' (from '{from_path}') does not resolve against the canonical schema: {e}"
            ) from e

        value = _apply_normalize(value, normalize_name)

        if _is_missing(value):
            if required:
                raise ProjectionError(
                    f"Required field '{out_path}' (from '{from_path}') is missing for candidate {profile.candidate_id}"
                )
            if on_missing == "error":
                raise ProjectionError(
                    f"Field '{out_path}' (from '{from_path}') is missing and on_missing policy is 'error'"
                )
            if on_missing == "omit":
                continue
            output[out_path] = None
            continue

        output[out_path] = value

    if include_confidence:
        output["confidence"] = profile.overall_confidence

    if include_provenance:
        output["provenance"] = [p.model_dump() for p in profile.provenance]

    return output