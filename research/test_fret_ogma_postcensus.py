"""Source-preserving, explicitly derived Ogma diagnostic controls."""

from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fret_ogma_postcensus import build_controls


class DerivedControlsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "method-full-project.json"
        self.original = {
            "vehicleSpec": {
                "Internal_variables": [
                    {
                        "name": name,
                        "type": "int",
                        "assignmentLustre": value,
                        "assignmentCopilot": "",
                    }
                    for name, value in [
                        ("semi_thrust_borne", "1"),
                        ("semi_wing_borne", "2"),
                        ("thrust_borne", "0"),
                        ("wing_borne", "3"),
                    ]
                ],
                "Other_variables": [
                    {"name": "kias", "type": "real"},
                    {"name": "wind_speed", "type": "real"},
                ],
                "Functions": [],
                "Requirements": [
                    {"name": "LPC_KIAS_0", "CoCoSpecCode": "H((kias >= 0.0))"},
                    {
                        "name": "LPC_WIND_SPEED_30_assumption",
                        "CoCoSpecCode":
                            "(H((-30.0 <= wind_speed)) and H((wind_speed <= 30.0)))",
                    },
                ],
            }
        }
        self.source.write_text(json.dumps(self.original) + "\n", encoding="utf-8")
        self.digest = sha256(self.source.read_bytes()).hexdigest()

    def read_case(self, directory, filename):
        return json.loads((directory / filename).read_text(encoding="utf-8"))["vehicleSpec"]

    def test_assigned_control_changes_only_four_blank_copilot_expressions(self):
        out = self.root / "out"
        saved = self.source.read_bytes()
        build_controls(self.source, out, expected_sha256=self.digest)
        self.assertEqual(self.source.read_bytes(), saved)
        self.assertTrue((out / "047-original.json").is_file())
        original = self.read_case(out, "047-original.json")
        assigned = self.read_case(out, "047-assigned-control.json")
        self.assertEqual(original["Requirements"], assigned["Requirements"])
        self.assertEqual(assigned["Requirements"][0]["CoCoSpecCode"], "H((kias >= 0.0))")
        self.assertEqual(original["Other_variables"], assigned["Other_variables"])
        expected = [("semi_thrust_borne", "1"), ("semi_wing_borne", "2"),
                    ("thrust_borne", "0"), ("wing_borne", "3")]
        for (name, value), a, b in zip(expected, original["Internal_variables"],
                                       assigned["Internal_variables"]):
            self.assertEqual(a["name"], name)
            self.assertEqual(a["assignmentCopilot"], "")
            self.assertEqual(b["assignmentCopilot"], value)
            self.assertEqual(b["assignmentLustre"], value)
            for key in a:
                if key != "assignmentCopilot":
                    self.assertEqual(a[key], b[key])

    def test_signed_literal_controls_keep_the_other_fields_and_expose_causes(self):
        out = self.root / "out"
        receipt = build_controls(self.source, out, expected_sha256=self.digest)
        self.assertTrue((out / "040-original.json").is_file())
        original = self.read_case(out, "040-original.json")
        formula = original["Requirements"][0]["CoCoSpecCode"]
        self.assertEqual(
            formula,
            "(H((-30.0 <= wind_speed)) and H((wind_speed <= 30.0)))",
        )
        want = {
            "040-nonnegative-diagnostic.json":
                "(H((0.0 <= wind_speed)) and H((wind_speed <= 30.0)))",
            "040-subtractive-equivalent.json":
                "(H(((0.0 - 30.0) <= wind_speed)) and H((wind_speed <= 30.0)))",
            "040-regrouped-equivalent.json":
                "H(((-30.0 <= wind_speed) and (wind_speed <= 30.0)))",
        }
        for filename, expression in want.items():
            candidate = self.read_case(out, filename)
            self.assertEqual(candidate["Requirements"][0]["CoCoSpecCode"], expression)
            for field in original:
                if field != "Requirements":
                    self.assertEqual(original[field], candidate[field])
            recorded = next(x for x in receipt["cases"] if x["file"] == filename)
            self.assertEqual(recorded["sha256"], sha256((out / filename).read_bytes()).hexdigest())
        self.assertEqual(len(receipt["cases"]), 6)
        self.assertEqual(receipt["sourceSha256"], self.digest)
        self.assertNotEqual(receipt["cases"][0]["sha256"], receipt["cases"][1]["sha256"])

    def test_history_rewrite_controls_are_equivalent_but_diagnostic_is_not(self):
        values = (-31.0, -30.0, -29.0, -1.0, 0.0, 29.0, 30.0, 31.0)
        for trace in product(values, repeat=3):
            source = all(v >= -30.0 for v in trace) and all(v <= 30.0 for v in trace)
            regroup = all((v >= -30.0 and v <= 30.0) for v in trace)
            subtraction = all((v >= 0.0 - 30.0) for v in trace) and all(
                v <= 30.0 for v in trace
            )
            self.assertEqual(source, regroup)
            self.assertEqual(source, subtraction)
        self.assertNotEqual(
            all(v >= -30.0 and v <= 30.0 for v in (-1.0, -1.0, -1.0)),
            all(v >= 0.0 and v <= 30.0 for v in (-1.0, -1.0, -1.0)),
        )

    def test_fail_closed_on_hash_contract_or_source_mutation(self):
        out = self.root / "out"
        with self.assertRaises(ValueError):
            build_controls(self.source, out, expected_sha256="0" * 64)
        self.assertFalse(out.exists())
        wrong = deepcopy(self.original)
        wrong["vehicleSpec"]["Internal_variables"][0]["assignmentCopilot"] = "999"
        self.source.write_text(json.dumps(wrong), encoding="utf-8")
        with self.assertRaises(ValueError):
            build_controls(self.source, out, expected_sha256=sha256(self.source.read_bytes()).hexdigest())
        self.assertFalse(out.exists())

    def test_reject_formula_drift_without_writing_any_derived_case(self):
        out = self.root / "out"
        self.original["vehicleSpec"]["Requirements"][1]["CoCoSpecCode"] = (
            "(H((wind_speed >= -30.0)) and H((wind_speed <= 30.0)))"
        )
        self.source.write_text(json.dumps(self.original), encoding="utf-8")
        with self.assertRaises(ValueError):
            build_controls(self.source, out, expected_sha256=sha256(self.source.read_bytes()).hexdigest())
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
