"""
Country normalization -> ISO-3166 alpha-2.

Small lookup table for common name variants. Deliberately not exhaustive —
returns None for anything not recognized rather than guessing, since a wrong
country code is worse than a missing one.
"""

from __future__ import annotations

_COUNTRY_LOOKUP: dict[str, str] = {
    "india": "IN",
    "in": "IN",
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "us": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "u.k.": "GB",
    "great britain": "GB",
    "canada": "CA",
    "germany": "DE",
    "france": "FR",
    "australia": "AU",
    "singapore": "SG",
    "united arab emirates": "AE",
    "uae": "AE",
    "netherlands": "NL",
    "ireland": "IE",
}


def normalize_country(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None

    key = raw.strip().lower()
    return _COUNTRY_LOOKUP.get(key)