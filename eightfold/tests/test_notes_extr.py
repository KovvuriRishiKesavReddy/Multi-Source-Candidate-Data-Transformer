from eightfold.extractors.recruiter_notes import extract_recruiter_notes


def test_extracts_four_candidate_blocks():
    records = extract_recruiter_notes("sample_inputs/recruiter_notes.txt")
    assert len(records) == 4


def test_karthik_only_in_notes_extracted_fully():
    records = extract_recruiter_notes("sample_inputs/recruiter_notes.txt")
    karthik = next(r for r in records if r.full_name == "Karthik Reddy")
    assert karthik.emails == ["karthik.reddy.dev@gmail.com"]
    assert karthik.phones == ["+91 90000 11122"]
    assert karthik.experience[0].company == "Postman"


def test_priya_missing_contact_info_stays_none_not_guessed():
    records = extract_recruiter_notes("sample_inputs/recruiter_notes.txt")
    priya = next(r for r in records if r.full_name == "Priya Iyer")
    assert priya.emails == []
    assert priya.phones == []


def test_missing_file_returns_empty_list_not_crash():
    records = extract_recruiter_notes("sample_inputs/does_not_exist.txt")
    assert records == []