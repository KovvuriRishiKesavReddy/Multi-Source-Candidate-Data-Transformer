import logging

logging.basicConfig(level=logging.WARNING)

from eightfold.extractors.ats_json import extract_ats_json

records = extract_ats_json("sample_inputs/ats_export.json")

print(f"Extracted {len(records)} records (expect 3, 4th is garbage)")

for r in records:
    print("-", r.full_name, r.emails, r.phones, r.skills)