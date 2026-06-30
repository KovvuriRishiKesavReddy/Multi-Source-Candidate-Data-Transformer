"""
Date normalization -> "YYYY-MM".

Sample inputs are already mostly in this shape, so this is mainly a
validate-and-passthrough step, plus tolerance for a few common variants
(full dates, "Month YYYY" text). Unparseable or empty input becomes None —
we don't guess a date.
"""

from __future__ import annotations

import logging
import re

from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

_YYYY_MM_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def normalize_date(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None

    raw = str(raw).strip()

    if _YYYY_MM_RE.match(raw):
        return raw

    try:
        parsed = dateutil_parser.parse(raw, default=None, fuzzy=False)
    except (ValueError, OverflowError, TypeError) as e:
        logger.debug("Could not parse date '%s': %s", raw, e)
        return None

    return f"{parsed.year:04d}-{parsed.month:02d}"