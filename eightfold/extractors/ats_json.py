"""
Extractor for the ATS JSON export (structured source).

The ATS export uses its own field names that don't map 1:1 onto our canonical
schema (e.g. "candidate_name" not "full_name", "contact_number" not "phones",
"skillset" is a single comma-separated string rather than a list). This module
does the remapping + light type coercion. It does NOT normalize phone/date/
skill formats — that's a separate stage (normalize/) so this extractor stays
a pure "what does the source literally say" step.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..schema.canonical import PartialExperience, PartialEducation, PartialRecord

logger = logging.getLogger(__name__)

SOURCE_NAME = "ats_json"


def _is_valid_email_shape(value: str | None) -> bool:
    """Loose shape check only — full normalization/validation happens later.
    Just enough to decide whether a record has *any* usable identity signal."""
    if not value:
        return False
    return "@" in value and "." in value.split("@")[-1]


def _extract_one(entry: dict[str, Any]) -> PartialRecord | None:
    name = (entry.get("candidate_name") or "").strip()
    email_raw = (entry.get("email_address") or "").strip()
    has_usable_name = bool(name)
    has_usable_email = _is_valid_email_shape(email_raw)

    if not has_usable_name and not has_usable_email:
        # No way to identify this person at all from this record. This is our
        # minimum bar for "usable" — skip it rather than fabricate an identity.
        return None

    record = PartialRecord(source_name=SOURCE_NAME)

    if has_usable_name:
        record.full_name = name
        record.add_provenance("full_name", "direct field mapping (candidate_name)")

    if has_usable_email:
        record.emails = [email_raw]
        record.add_provenance("emails", "direct field mapping (email_address)")

    phone_raw = entry.get("contact_number")
    if phone_raw:
        record.phones = [str(phone_raw).strip()]
        record.add_provenance("phones", "direct field mapping (contact_number)")

    employer = entry.get("employer")
    title = entry.get("job_title")
    if employer or title:
        # We also surface current role as the first experience entry so the
        # merge stage can treat "current company/title" uniformly with the
        # rest of the experience list, rather than as a special case.
        record.experience.append(
            PartialExperience(company=employer or None, title=title or None)
        )
        record.add_provenance("experience", "direct field mapping (employer/job_title)")

    skillset_raw = entry.get("skillset")
    if skillset_raw:
        skills = [s.strip() for s in skillset_raw.split(",") if s.strip()]
        if skills:
            record.skills = skills
            record.add_provenance("skills", "split on comma (skillset)")

    work_history = entry.get("work_history") or []
    if isinstance(work_history, list):
        for job in work_history:
            if not isinstance(job, dict):
                continue
            record.experience.append(
                PartialExperience(
                    company=job.get("org"),
                    title=job.get("role"),
                    start=job.get("from"),
                    end=job.get("to"),
                )
            )
        if work_history:
            record.add_provenance(
                "experience", "nested field mapping (work_history: org/role/from/to)"
            )

    academics = entry.get("academics") or []
    if isinstance(academics, list):
        for school in academics:
            if not isinstance(school, dict):
                continue
            record.education.append(
                PartialEducation(
                    institution=school.get("school"),
                    degree=school.get("qualification"),
                    field=school.get("major"),
                    end_year=school.get("grad_year"),
                )
            )
        if academics:
            record.add_provenance(
                "education",
                "nested field mapping (academics: school/qualification/major/grad_year)",
            )

    return record


def extract_ats_json(filepath: str) -> list[PartialRecord]:
    """
    Load and extract candidate records from an ATS JSON export.

    Never raises on a missing/malformed file or a malformed individual entry —
    logs a warning and degrades gracefully (missing file -> empty list,
    malformed entry -> that entry skipped, rest of the file still processed).
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.warning("ATS JSON source not found at %s — skipping this source.", filepath)
        return []
    except json.JSONDecodeError as e:
        logger.warning("ATS JSON source at %s is not valid JSON (%s) — skipping this source.", filepath, e)
        return []

    candidates = data.get("candidates") if isinstance(data, dict) else None
    if not isinstance(candidates, list):
        logger.warning("ATS JSON source at %s has no usable 'candidates' list — skipping this source.", filepath)
        return []

    records: list[PartialRecord] = []
    for i, entry in enumerate(candidates):
        if not isinstance(entry, dict):
            logger.warning("ATS JSON candidates[%d] is not an object — skipping entry.", i)
            continue
        try:
            record = _extract_one(entry)
        except Exception as e:  # noqa: BLE001 - a single bad record must not kill the run
            logger.warning("ATS JSON candidates[%d] failed to extract (%s) — skipping entry.", i, e)
            continue
        if record is None:
            logger.warning(
                "ATS JSON candidates[%d] has no usable name or email — skipping entry as unidentifiable.",
                i,
            )
            continue
        records.append(record)

    return records