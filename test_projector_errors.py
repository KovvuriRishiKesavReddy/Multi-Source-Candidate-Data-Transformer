from eightfold.extractors.ats_json import extract_ats_json
from eightfold.extractors.recruiter_notes import extract_recruiter_notes
from eightfold.merge.matcher import group_records
from eightfold.merge.build_profile import build_canonical_profile
from eightfold.schema.projector import project, ProjectionError

records = (
    extract_ats_json("sample_inputs/ats_export.json")
    + extract_recruiter_notes("sample_inputs/recruiter_notes.txt")
)

groups = group_records(records)
profiles = {p.full_name: p for p in (build_canonical_profile(g) for g in groups)}

karthik = profiles["Karthik Reddy"]  # has no education data

# Test 1: invalid path
bad_config = {
    "fields": [
        {
            "path": "foo",
            "from": "not_a_real_field",
            "type": "string",
        }
    ],
    "on_missing": "null",
}

try:
    project(karthik, bad_config)
    print("FAIL: should have raised")
except ProjectionError as e:
    print("Test 1 PASS - bad path correctly raised:", e)

# Test 2: required field missing
req_config = {
    "fields": [
        {
            "path": "school",
            "from": "education[0].institution",
            "type": "string",
            "required": True,
        }
    ],
    "on_missing": "null",
}

try:
    project(karthik, req_config)
    print("FAIL: should have raised on missing required field")
except ProjectionError as e:
    print("Test 2 PASS - missing required field correctly raised:", e)

# Test 3: on_missing = error
err_config = {
    "fields": [
        {
            "path": "school",
            "from": "education[0].institution",
            "type": "string",
        }
    ],
    "on_missing": "error",
}

try:
    project(karthik, err_config)
    print("FAIL: should have raised due to on_missing=error")
except ProjectionError as e:
    print("Test 3 PASS - on_missing=error correctly raised:", e)