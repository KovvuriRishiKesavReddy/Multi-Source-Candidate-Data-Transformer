import logging

logging.basicConfig(level=logging.WARNING)

from eightfold.extractors.ats_json import extract_ats_json
from eightfold.extractors.recruiter_notes import extract_recruiter_notes
from eightfold.merge.matcher import group_records
from eightfold.merge.build_profile import build_canonical_profile

records = (
    extract_ats_json("sample_inputs/ats_export.json")
    + extract_recruiter_notes("sample_inputs/recruiter_notes.txt")
)

groups = group_records(records)

print(f"{len(groups)} groups formed (expect 4: Ananya, Rohit, Priya, Karthik)")

for g in groups:
    print(
        "---",
        [r.source_name for r in g.records],
        "method:",
        g.match_method,
        "| names:",
        [r.full_name for r in g.records],
    )