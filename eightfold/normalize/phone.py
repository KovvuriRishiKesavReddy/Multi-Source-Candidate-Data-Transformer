"""
Phone normalization -> E.164.

Never guesses a country code if one truly can't be determined. If parsing
fails or the number is invalid even with the default region fallback, we
return None rather than emit something that looks valid but might not be.
"""

from __future__ import annotations

import logging

import phonenumbers

logger = logging.getLogger(__name__)


def normalize_phone(raw: str | None, default_region: str = "IN") -> str | None:
    if not raw or not raw.strip():
        return None

    raw = raw.strip()

    try:
        parsed = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException as e:
        logger.debug("Could not parse phone '%s': %s", raw, e)
        return None

    if not phonenumbers.is_valid_number(parsed):
        logger.debug("Phone '%s' parsed but is not a valid number.", raw)
        return None

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)