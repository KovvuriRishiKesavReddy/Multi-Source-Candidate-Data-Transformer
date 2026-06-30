from eightfold.normalize.phone import normalize_phone
from eightfold.normalize.date import normalize_date
from eightfold.normalize.country import normalize_country
from eightfold.normalize.skills import normalize_skill, is_canonical_skill


def test_phone_valid_indian_numbers():
    assert normalize_phone("+91 98765 43210") == "+919876543210"
    assert normalize_phone("9876512345") == "+919876512345"
    assert normalize_phone("+91-99887-66554") == "+919988766554"


def test_phone_invalid_returns_none():
    assert normalize_phone("garbage") is None
    assert normalize_phone(None) is None
    assert normalize_phone("123") is None


def test_date_passthrough_and_none():
    assert normalize_date("2023-03") == "2023-03"
    assert normalize_date(None) is None
    assert normalize_date("") is None


def test_country_lookup_and_unknown():
    assert normalize_country("India") == "IN"
    assert normalize_country("USA") == "US"
    assert normalize_country("Atlantis") is None


def test_skill_synonyms():
    assert normalize_skill("JS") == "javascript"
    assert normalize_skill("reactjs") == "react"
    assert normalize_skill("Python") == "python"


def test_skill_passthrough_for_unknown():
    assert normalize_skill("Kafka") == "kafka"
    assert is_canonical_skill("Kafka") is False
    assert is_canonical_skill("Python") is True