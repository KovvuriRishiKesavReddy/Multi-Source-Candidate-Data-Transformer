from eightfold.schema.canonical import PartialRecord, CandidateProfile, generate_candidate_id

pr = PartialRecord(
    source_name="ats_json",
    full_name="Test Person",
    emails=["a@b.com"]
)

pr.add_provenance("full_name", "direct field mapping")

print(pr)
print()

print(generate_candidate_id(["a@b.com"], []))
print(generate_candidate_id([], ["+919876543210"]))
print(generate_candidate_id([], []))