import json

from eightfold.extractors.ats_json import extract_ats_json
from eightfold.extractors.recruiter_notes import extract_recruiter_notes
from eightfold.merge.matcher import group_records
from eightfold.merge.build_profile import build_canonical_profile

records = (
    extract_ats_json("sample_inputs/ats_export.json")
    + extract_recruiter_notes("sample_inputs/recruiter_notes.txt")
)

groups = group_records(records)
profiles = [build_canonical_profile(g) for g in groups]

ananya = next(p for p in profiles if p.full_name == "Ananya Sharma")

print("=== ANANYA ===")
print("phones:", ananya.phones)
print("skills:", [(s.name, s.confidence, s.sources) for s in ananya.skills])
print("overall_confidence:", ananya.overall_confidence)

print()
print("provenance for phones:")
for p in ananya.provenance:
    if "phone" in p.field.lower():
        print(" ", p)