import json

from eightfold.extractors.ats_json import extract_ats_json
from eightfold.extractors.recruiter_notes import extract_recruiter_notes
from eightfold.merge.matcher import group_records
from eightfold.merge.build_profile import build_canonical_profile
from eightfold.schema.projector import project, ProjectionError
from eightfold.schema.validator import validate_against_config

records = (
    extract_ats_json("sample_inputs/ats_export.json")
    + extract_recruiter_notes("sample_inputs/recruiter_notes.txt")
)

groups = group_records(records)
profiles = {p.full_name: p for p in (build_canonical_profile(g) for g in groups)}
ananya = profiles["Ananya Sharma"]

with open("sample_inputs/config_default.json", encoding="utf-8") as f:
    cfg_default = json.load(f)

with open("sample_inputs/config_minimal.json", encoding="utf-8") as f:
    cfg_minimal = json.load(f)

print("=== DEFAULT CONFIG ===")
out = project(ananya, cfg_default)
print(json.dumps(out, indent=2))

errs = validate_against_config(out, cfg_default)
print("validation errors:", errs)

print()

print("=== MINIMAL CONFIG ===")
out2 = project(ananya, cfg_minimal)
print(json.dumps(out2, indent=2))

errs2 = validate_against_config(out2, cfg_minimal)
print("validation errors:", errs2)