import logging

logging.basicConfig(level=logging.WARNING)

from eightfold.extractors.recruiter_notes import extract_recruiter_notes

records = extract_recruiter_notes("sample_inputs/recruiter_notes.txt")

print(f"Extracted {len(records)} records (expect 4)")

for r in records:
    exp = r.experience[0] if r.experience else None
    print("--", r.full_name, "| email:", r.emails, "| phone:", r.phones, "| skills:", r.skills)
    print("   company/title:", (exp.company, exp.title) if exp else None,
          "| summary:", exp.summary if exp else None)