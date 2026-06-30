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

karthik = next(p for p in profiles if p.full_name == "Karthik Reddy")
print("=== KARTHIK (single source) ===")
print("emails:", karthik.emails, "| phones:", karthik.phones)
print("experience:", [(e.company, e.title) for e in karthik.experience])
print("overall_confidence:", karthik.overall_confidence)
print()

priya = next(p for p in profiles if p.full_name == "Priya Iyer")
print("=== PRIYA (notes missing contact info) ===")
print("emails:", priya.emails, "| phones:", priya.phones)
print("skills:", [s.name for s in priya.skills])
print("overall_confidence:", priya.overall_confidence)