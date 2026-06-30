"""
Canonical data model for the Eightfold multi-source candidate transformer.

Two models live here, deliberately kept separate:

- PartialRecord: what a single extractor produces from a single source. Every
  field is optional. Extractors must never invent a value here — if a source
  doesn't contain something, the field stays None/empty, full stop. Each
  PartialRecord knows which source it came from (`source_name`) so the merge
  stage can apply source-priority rules later.

- CandidateProfile: the merged, canonical record for one candidate, after the
  merge stage has resolved every field across however many PartialRecords
  matched to the same person. This is the "one trustworthy profile" the
  assignment brief asks for. It always has the full fixed shape (lists are
  empty rather than missing, optional fields are None rather than absent),
  and it carries provenance + confidence for every field so the projection
  layer can show its work.

The projection layer (schema/projector.py) reads ONLY from CandidateProfile,
never from raw sources or PartialRecords. That separation is intentional and
is the core of how the runtime config requirement is satisfied without
forking the underlying engine.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Provenance — shared by both models
# ---------------------------------------------------------------------------

class ProvenanceEntry(BaseModel):
    field: str
    source: str
    method: str


# ---------------------------------------------------------------------------
# PartialRecord — one source's view of one candidate
# ---------------------------------------------------------------------------

class PartialExperience(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    summary: Optional[str] = None


class PartialEducation(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[int] = None


class PartialRecord(BaseModel):
    source_name: str  # e.g. "ats_json", "recruiter_notes"

    full_name: Optional[str] = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)

    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None

    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other_links: list[str] = Field(default_factory=list)

    headline: Optional[str] = None
    years_experience: Optional[float] = None

    skills: list[str] = Field(default_factory=list)  # raw, not yet canonicalized
    experience: list[PartialExperience] = Field(default_factory=list)
    education: list[PartialEducation] = Field(default_factory=list)

    provenance: list[ProvenanceEntry] = Field(default_factory=list)

    def add_provenance(self, field: str, method: str) -> None:
        self.provenance.append(
            ProvenanceEntry(field=field, source=self.source_name, method=method)
        )


# ---------------------------------------------------------------------------
# CandidateProfile — the merged canonical record
# ---------------------------------------------------------------------------

class Location(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None  # ISO-3166 alpha-2


class Links(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    name: str
    confidence: float
    sources: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    summary: Optional[str] = None


class Education(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[int] = None


class CandidateProfile(BaseModel):
    candidate_id: str
    full_name: str
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    links: Links = Field(default_factory=Links)
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list[Skill] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    provenance: list[ProvenanceEntry] = Field(default_factory=list)
    overall_confidence: float = 0.0


# ---------------------------------------------------------------------------
# candidate_id generation
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def generate_candidate_id(emails: list[str], phones: list[str]) -> str:
    """
    Stable, deterministic id derived from the strongest identifying field
    available: normalized email first, else normalized phone, else a random
    uuid as a last resort (meaning: we couldn't identify this person reliably
    at all, which itself is useful signal we keep elsewhere via confidence).
    """
    if emails:
        key = emails[0].strip().lower()
        return "cand_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    if phones:
        key = phones[0].strip()
        return "cand_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return "cand_" + uuid.uuid4().hex[:16]