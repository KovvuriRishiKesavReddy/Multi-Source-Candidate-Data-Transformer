from eightfold.extractors.ats_json import extract_ats_json


def test_extracts_three_valid_candidates_skips_garbage():
    records = extract_ats_json("sample_inputs/ats_export.json")
    assert len(records) == 3
    names = {r.full_name for r in records}
    assert names == {"Ananya Sharma", "Rohit Verma", "Priya Iyer"}


def test_ananya_raw_phone_and_skills_before_normalization():
    records = extract_ats_json("sample_inputs/ats_export.json")
    ananya = next(r for r in records if r.full_name == "Ananya Sharma")
    assert ananya.phones == ["+91 98765 43210"]
    assert "Python" in ananya.skills
    assert "AWS" in ananya.skills


def test_missing_file_returns_empty_list_not_crash():
    records = extract_ats_json("sample_inputs/does_not_exist.json")
    assert records == []