from __future__ import annotations

import unittest
from pathlib import Path

from eightfold.extractors.ats_json import extract_ats_json


class TestAtsExtractor(unittest.TestCase):
    def test_extract_ats_json_real_sample(self) -> None:
        sample_path = Path(__file__).resolve().parents[1] / "sample_inputs" / "ats_export.json"

        records = extract_ats_json(str(sample_path))

        self.assertEqual(len(records), 3)

        ananya = next(record for record in records if record.full_name == "Ananya Sharma")
        self.assertEqual(ananya.phones, ["+91 98765 43210"])
        self.assertEqual(ananya.skills, ["Python", "Django", "PostgreSQL", "AWS"])
        self.assertEqual(ananya.source_name, "ats_json")
        self.assertIsNotNone(ananya.provenance)


if __name__ == "__main__":
    unittest.main()
