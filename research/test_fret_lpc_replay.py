"""Independent, narrow assertions for NASA FRET Lift+Cruise monitor export."""

import unittest

from fret_lpc_replay import (
    expected_rows,
    native_verdicts,
    render_from_pinned_fret,
)


class FretLiftCruiseReplayTests(unittest.TestCase):
    def test_source_truth_is_explicit_and_catches_mid_trace_violation(self):
        self.assertEqual(expected_rows("clear"), (True, True, True))
        self.assertEqual(expected_rows("both_on"), (True, False, True))
        self.assertEqual(expected_rows("both_off"), (True, False, True))

    def test_original_fret_renderer_keeps_both_boolean_channels_and_requirement_id(self):
        case = {
            "requirements": [{
                "reqid": "LPC_REARPROP",
                "fulltext": "The vehicle shall always satisfy rearprop xor hover_control_mode",
                "semantics": {"component_name": "vehicle", "R2U2Code": "(rearprop xor hover_control_mode)", "ptExpanded": "(H (rearprop xor hover_control_mode))"},
            }],
            "variables": [
                {"variable_name": "rearprop", "component_name": "vehicle", "idType": "Output", "dataType": "boolean", "r2u2Completed": True},
                {"variable_name": "hover_control_mode", "component_name": "vehicle", "idType": "Output", "dataType": "boolean", "r2u2Completed": True},
            ],
        }
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tempdir:
            renderer = Path(tempdir) / "r2u2Export.js"
            renderer.write_text(
                "export { renderC2POSpec, renderC2POMap, renderC2POCSVHeader }\n"
                "function renderC2POSpec(c) { return 'INPUT\\r\\n\\trearprop: bool;\\r\\n\\thover_control_mode: bool;\\r\\nFTSPEC\\r\\n\\tLPC_REARPROP: ' + c.properties[0].R2U2 + ';\\r\\n'; }\n"
                "function renderC2POMap(c) { return c.outputVariables.map((v,i) => v.name+':'+i+'\\r\\n').join(''); }\n"
                "function renderC2POCSVHeader() { return '# rearprop, hover_control_mode\\r\\n'; }\n"
            )
            self.assertEqual(
                render_from_pinned_fret(renderer, case)["map"],
                "rearprop:0\r\nhover_control_mode:1\r\n",
            )
            self.assertEqual(
                render_from_pinned_fret(renderer, case)["csv"],
                "# rearprop, hover_control_mode\r\n",
            )
            self.assertIn("LPC_REARPROP: (rearprop xor hover_control_mode);", render_from_pinned_fret(renderer, case)["c2po"])

    def test_verdict_parser_rejects_duplicate_or_missing_sample(self):
        self.assertEqual(native_verdicts("0:0,T\n0:1,F\n0:2,T\n", 3), (True, False, True))
        with self.assertRaises(ValueError):
            native_verdicts("0:0,T\n0:1,F\n", 3)
        with self.assertRaises(ValueError):
            native_verdicts("0:0,T\n0:1,F\n0:1,T\n0:2,T\n", 3)


if __name__ == "__main__":
    unittest.main()
