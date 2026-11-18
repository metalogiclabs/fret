"""Finite, source-preserving property slicing and native-result census tests."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fret_ogma_full_census import classify, split


class FullCensusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.source = self.work / "full.json"
        self.example = {
            "vehicleSpec": {
                "Internal_variables": [{"name": "k", "type": "int", "assignmentLustre": "2"}],
                "Other_variables": [{"name": "a", "type": "bool"}, {"name": "b", "type": "bool"}],
                "Functions": [],
                "Requirements": [
                    {"name": "R_A", "CoCoSpecCode": "H(a)", "fretish": "always a"},
                    {"name": "R_B", "CoCoSpecCode": "H((a xor b))", "fretish": "always xor"},
                ],
            }
        }
        self.source.write_text(json.dumps(self.example), encoding="utf-8")

    def test_split_preserves_every_non_requirement_field_and_source_order(self):
        receipt = split(self.source, self.work / "slices")
        self.assertEqual(receipt["requirements"], 2)
        self.assertEqual(receipt["otherVariables"], 2)
        self.assertEqual([item["name"] for item in receipt["items"]], ["R_A", "R_B"])
        for i, item in enumerate(receipt["items"]):
            sliced = json.loads((self.work / "slices" / item["file"]).read_text())
            self.assertEqual(sliced["vehicleSpec"]["Requirements"],
                             [self.example["vehicleSpec"]["Requirements"][i]])
            for key, value in self.example["vehicleSpec"].items():
                if key != "Requirements":
                    self.assertEqual(sliced["vehicleSpec"][key], value)
        self.assertEqual(split(self.source, self.work / "slices"), receipt)

    def test_duplicate_names_get_distinct_numbered_paths(self):
        self.example["vehicleSpec"]["Requirements"][1]["name"] = "R_A"
        self.source.write_text(json.dumps(self.example), encoding="utf-8")
        receipt = split(self.source, self.work / "slices")
        self.assertNotEqual(receipt["items"][0]["file"], receipt["items"][1]["file"])

    def test_reject_untrusted_names_and_empty_requirements(self):
        self.example["vehicleSpec"]["Requirements"][0]["name"] = "../escape"
        self.source.write_text(json.dumps(self.example), encoding="utf-8")
        with self.assertRaises(ValueError):
            split(self.source, self.work / "slices")
        self.example["vehicleSpec"]["Requirements"] = []
        self.source.write_text(json.dumps(self.example), encoding="utf-8")
        with self.assertRaises(ValueError):
            split(self.source, self.work / "slices")

    def test_classification_accounts_for_every_native_result(self):
        receipt = split(self.source, self.work / "slices")
        status = self.work / "status.tsv"
        status.write_text(
            "index\tfile\texit_code\tgenerated_haskell\n"
            f"0\t{receipt['items'][0]['file']}\t0\t1\n"
            f"1\t{receipt['items'][1]['file']}\t1\t0\n",
            encoding="utf-8",
        )
        report = classify(receipt, status)
        self.assertEqual(report["translated"], 1)
        self.assertEqual(report["notTranslated"], 1)
        self.assertEqual([item["status"] for item in report["items"]],
                         ["translated", "not_translated"])

    def test_classification_fails_closed_for_missing_or_conflicting_results(self):
        receipt = split(self.source, self.work / "slices")
        status = self.work / "status.tsv"
        status.write_text("index\tfile\texit_code\tgenerated_haskell\n"
                          f"0\t{receipt['items'][0]['file']}\t0\t0\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            classify(receipt, status)
        status.write_text("index\tfile\texit_code\tgenerated_haskell\n"
                          f"0\t{receipt['items'][0]['file']}\t1\t1\n"
                          f"1\t{receipt['items'][1]['file']}\t0\t1\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            classify(receipt, status)


if __name__ == "__main__":
    unittest.main()
