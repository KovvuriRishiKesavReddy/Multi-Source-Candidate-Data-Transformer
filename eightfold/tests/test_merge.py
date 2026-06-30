from eightfold.extractors.ats_json import extract_ats_json
from eightfold.extractors.recruiter_notes import extract_recruiter_notes
from eightfold.merge.matcher import group_records
from eightfold.merge.build_profile import build_canonical_profile


def _build_all_profiles():
    records = extract_ats_json("sample_inputs/ats_export.json") + extract_recruiter_notes(
        "sample_inputs/recruiter_notes.txt"
    )
    groups = group_records(records)
    return {p.full_name: p for p in (build_canonical_profile(g) for g in groups)}


def test_ananya_phone_conflict_ats_wins_with_reduced_confidence():
    profiles = _build_all_profiles()
    ananya = profiles["Ananya Sharma"]

    # ATS's number should be primary (listed first)
    assert ananya.phones[0] == "+919876543210"
    # Both raw values should be visible in provenance, not silently dropped
    phone_prov_sources = {p.source for p in ananya.provenance if p.field == "phones"}
    assert phone_prov_sources == {"ats_json", "recruiter_notes"}
    conflict_flagged = any(
        "conflict" in p.method for p in ananya.provenance if p.field == "phones"
    )
    assert conflict_flagged


def test_ananya_skills_union_includes_notes_only_skills():
    profiles = _build_all_profiles()
    ananya = profiles["Ananya Sharma"]
    skill_names = {s.name for s in ananya.skills}
    # Kafka and System Design only appear in recruiter notes, not ATS
    assert "kafka" in skill_names
    assert "system design" in skill_names
    # Python appears in both sources
    assert "python" in skill_names


def test_karthik_single_source_still_produces_complete_profile():
    profiles = _build_all_profiles()
    karthik = profiles["Karthik Reddy"]
    assert karthik.emails == ["karthik.reddy.dev@gmail.com"]
    assert karthik.phones == ["+919000011122"]
    assert karthik.experience[0].company == "Postman"
    assert 0.0 < karthik.overall_confidence <= 1.0


def test_priya_missing_notes_contact_info_does_not_corrupt_ats_values():
    profiles = _build_all_profiles()
    priya = profiles["Priya Iyer"]
    # ATS source had the real email/phone; notes had none for this candidate.
    # The merged profile must still have ATS's values, untouched.
    assert priya.emails == ["priya.iyer.work@gmail.com"]
    assert priya.phones == ["+919988766554"]