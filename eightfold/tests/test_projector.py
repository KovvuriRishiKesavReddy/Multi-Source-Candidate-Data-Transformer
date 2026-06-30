import json

from eightfold.extractors.ats_json import extract_ats_json
from eightfold.extractors.recruiter_notes import extract_recruiter_notes
from eightfold.merge.matcher import group_records
from eightfold.merge.build_profile import build_canonical_profile
from eightfold.schema.projector import project, ProjectionError
from eightfold.schema.validator import validate_against_config

def _build_profiles():
    records = extract_ats_json("sample_inputs/ats_export.json") + extract_recruiter_notes(
        "sample_inputs/recruiter_notes.txt"
    )
    groups = group_records(records)
    return {p.full_name: p for p in (build_canonical_profile(g) for g in groups)}


def _load_config(name):
    with open(f"sample_inputs/{name}") as f:
        return json.load(f)


def test_default_config_pulls_primary_email_from_emails_index_zero():
    profiles = _build_profiles()
    ananya = profiles["Ananya Sharma"]
    config = _load_config("config_default.json")

    out = project(ananya, config)

    assert out["primary_email"] == ananya.emails[0]
    assert validate_against_config(out, config) == []


def test_minimal_config_omits_missing_field_rather_than_nulling():
    profiles = _build_profiles()
    priya = profiles["Priya Iyer"]  # has no location data -> location.country is None
    config = _load_config("config_minimal.json")

    out = project(priya, config)

    assert "location_country" not in out  # omitted, not nulled
    assert validate_against_config(out, config) == []


def test_empty_skills_list_stays_empty_list_not_treated_as_missing():
    # Karthik Reddy has no "Skills:" line in his notes block, so skills
    # resolves to an empty list. An empty list is a real, honest result
    # (we looked, found nothing) and should NOT be treated the same as a
    # missing scalar field — it must not be omitted (under on_missing=omit)
    # or nulled (under on_missing=null), it should just stay [].
    profiles = _build_profiles()
    karthik = profiles["Karthik Reddy"]

    default_config = _load_config("config_default.json")  # on_missing: null
    out_default = project(karthik, default_config)
    assert out_default["skills"] == []

    minimal_config = _load_config("config_minimal.json")  # on_missing: omit
    out_minimal = project(karthik, minimal_config)
    assert "top_skills" in out_minimal
    assert out_minimal["top_skills"] == []


def test_nonexistent_canonical_path_raises_clear_error_not_silent_null():
    profiles = _build_profiles()
    karthik = profiles["Karthik Reddy"]
    bad_config = {
        "fields": [{"path": "foo", "from": "totally_made_up_field", "type": "string"}],
        "on_missing": "null",
    }

    try:
        project(karthik, bad_config)
        assert False, "expected ProjectionError to be raised"
    except ProjectionError:
        pass


def test_required_field_missing_always_errors_regardless_of_on_missing():
    profiles = _build_profiles()
    karthik = profiles["Karthik Reddy"]  # no education entries
    config = {
        "fields": [
            {"path": "school", "from": "education[0].institution", "type": "string", "required": True}
        ],
        "on_missing": "null",  # even though policy is "null", required overrides it
    }

    try:
        project(karthik, config)
        assert False, "expected ProjectionError for missing required field"
    except ProjectionError:
        pass