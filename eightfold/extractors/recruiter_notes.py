"""
Extractor for recruiter notes (.txt) — the unstructured source.

This is free text, so extraction is regex + light heuristics rather than a
fixed field mapping. The bar here is deliberately conservative: if a value
isn't clearly present in the block, we leave it as None rather than guessing
from surrounding prose. A wrong-but-confident guess is worse than an honest
empty field (this is stated explicitly in the brief, and it's the main risk
with free-text extraction, so we lean hard the other way).

Block format expected (see sample_inputs/recruiter_notes.txt):
    === Candidate: <name> ===
    <free text, fields appear inconsistently across blocks>
"""

from __future__ import annotations

import logging
import re

from ..schema.canonical import PartialExperience, PartialRecord

logger = logging.getLogger(__name__)

SOURCE_NAME = "recruiter_notes"

_BLOCK_HEADER_RE = re.compile(r"===\s*Candidate:\s*(.+?)\s*===")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s]{7,14}\d)")

# "Currently <Title> at <Company>"  OR  "at <Company> as <Title>" /
# "Currently at <Company> as <Title>" — the sample data uses both orders.
_TITLE_AT_COMPANY_RE = re.compile(
    r"(?:Currently\s+)?(?P<title>[A-Za-z][A-Za-z .]*?)\s+at\s+(?P<company>[A-Za-z][A-Za-z .]*?)(?:[.,]|\s+as\s|\n|$)",
    re.IGNORECASE,
)
_AT_COMPANY_AS_TITLE_RE = re.compile(
    r"at\s+(?P<company>[A-Za-z][A-Za-z .]*?)\s+as\s+(?:an?\s+)?(?P<title>[A-Za-z][A-Za-z0-9 .]*?)(?:[.,]|\n|$)",
    re.IGNORECASE,
)
_SKILLS_LINE_RE = re.compile(r"^\s*Skills:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _split_blocks(text: str) -> list[tuple[str, str]]:
    """Returns list of (name_from_header, block_body)."""
    matches = list(_BLOCK_HEADER_RE.finditer(text))
    blocks = []
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks.append((name, text[start:end].strip()))
    return blocks


def _find_email(block: str) -> str | None:
    m = _EMAIL_RE.search(block)
    return m.group(0) if m else None


def _find_phone(block: str) -> str | None:
    for line in block.splitlines():
        if "phone" in line.lower():
            m = _PHONE_RE.search(line)
            if m:
                return m.group(0).strip()
    # fall back to scanning the whole block in case "Phone:" label is absent
    m = _PHONE_RE.search(block)
    return m.group(0).strip() if m else None


def _find_company_title(block: str) -> tuple[str | None, str | None]:
    m = _AT_COMPANY_AS_TITLE_RE.search(block)
    if m:
        return m.group("company").strip(), m.group("title").strip()
    m = _TITLE_AT_COMPANY_RE.search(block)
    if m:
        return m.group("company").strip(), m.group("title").strip()
    return None, None


def _find_skills(block: str) -> list[str]:
    m = _SKILLS_LINE_RE.search(block)
    if not m:
        return []
    return [s.strip() for s in m.group(1).split(",") if s.strip()]


def _extract_one(name: str, block: str) -> PartialRecord:
    record = PartialRecord(source_name=SOURCE_NAME)

    if name:
        record.full_name = name
        record.add_provenance("full_name", "block header (=== Candidate: ... ===)")

    email = _find_email(block)
    if email:
        record.emails = [email]
        record.add_provenance("emails", "regex: email pattern")

    phone = _find_phone(block)
    if phone:
        record.phones = [phone]
        record.add_provenance("phones", "regex: phone pattern")

    company, title = _find_company_title(block)
    if company or title:
        record.experience.append(PartialExperience(company=company, title=title))
        record.add_provenance("experience", "regex: '<title> at <company>' / 'at <company> as <title>' pattern")

    skills = _find_skills(block)
    if skills:
        record.skills = skills
        record.add_provenance("skills", "regex: 'Skills:' labeled line, split on comma")

    # Anything left over is unstructured prose. Rather than force it into a
    # structured field (risking us inventing structure that isn't really
    # there), we keep it as a summary note attached to the most recent
    # experience entry if we have one, since that's the most natural home
    # for "context about this role/person" — and skip it otherwise. This is
    # a deliberate, documented choice rather than an oversight.
    notes_match = re.search(r"^\s*Notes?:\s*(.+)$", block, re.IGNORECASE | re.MULTILINE)
    if notes_match and record.experience:
        record.experience[-1].summary = notes_match.group(1).strip()
        record.add_provenance("experience", "regex: 'Notes:' labeled line attached as summary")

    return record


def extract_recruiter_notes(filepath: str) -> list[PartialRecord]:
    """
    Load and extract candidate records from a free-text recruiter notes file.

    Never raises on a missing file or an unparseable block — logs a warning
    and degrades gracefully.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        logger.warning("Recruiter notes source not found at %s — skipping this source.", filepath)
        return []
    except OSError as e:
        logger.warning("Recruiter notes source at %s could not be read (%s) — skipping this source.", filepath, e)
        return []

    blocks = _split_blocks(text)
    if not blocks:
        logger.warning(
            "Recruiter notes source at %s had no '=== Candidate: ... ===' blocks — skipping this source.",
            filepath,
        )
        return []

    records: list[PartialRecord] = []
    for name, block in blocks:
        try:
            records.append(_extract_one(name, block))
        except Exception as e:  # noqa: BLE001 - one bad block must not kill the run
            logger.warning("Failed to extract block for '%s' (%s) — skipping block.", name, e)
            continue

    return records