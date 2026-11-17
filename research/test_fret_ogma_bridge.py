"""Source-independent assertions for the next FRET→Ogma/Copilot pilot."""

import unittest

from fret_ogma_bridge import create_ogma_input


class FretOgmaBridgeTests(unittest.TestCase):
    def test_template_shaped_input_preserves_h_and_both_typed_boolean_signals(self):
        case = {
            "requirements": [{
                "reqid": "LPC_REARPROP",
                "fulltext": "The vehicle shall always satisfy rearprop xor hover_control_mode",
                "semantics": {
                    "component_name": "vehicle",
                    "R2U2Code": "(rearprop xor hover_control_mode)",
                    "ptExpanded": "(H (rearprop xor hover_control_mode))",
                    "CoCoSpecCode": "H((rearprop xor hover_control_mode))",
                },
            }],
            "variables": [
                {"variable_name": "rearprop", "component_name": "vehicle", "idType": "Output", "dataType": "boolean", "r2u2Completed": True},
                {"variable_name": "hover_control_mode", "component_name": "vehicle", "idType": "Output", "dataType": "boolean", "r2u2Completed": True},
            ],
        }
        result = create_ogma_input(case)
        self.assertEqual(list(result), ["vehicleSpec"])
        item = result["vehicleSpec"]
        self.assertEqual(item["Internal_variables"], [])
        self.assertEqual(item["Functions"], [])
        self.assertEqual(item["Other_variables"], [
            {"name": "rearprop", "type": "bool"},
            {"name": "hover_control_mode", "type": "bool"},
        ])
        self.assertEqual(item["Requirements"], [{
            "name": "LPC_REARPROP",
            "fretish": "The vehicle shall always satisfy rearprop xor hover_control_mode",
            "CoCoSpecCode": "H((rearprop xor hover_control_mode))",
            "ptLTL": "(H (rearprop xor hover_control_mode))",
        }])

    def test_source_change_must_fail_closed(self):
        with self.assertRaises((ValueError, KeyError)):
            create_ogma_input({"requirements": [], "variables": []})


if __name__ == "__main__":
    unittest.main()
