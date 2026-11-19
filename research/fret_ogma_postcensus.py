#!/usr/bin/env python3
"""Derive strictly isolated, source-qualified FRET→Ogma diagnostic inputs.

The six outputs are controls, not revisions to the original requirements.
Every derivation is checked against exact upstream source content before writing.
"""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


PINNED_EXPORT_SHA256 = "2754f9a2debefbe87e8dc9d9e0a4c5226473781bd21433ed80f3accf802f1443"
WIND_FORMULA = "(H((-30.0 <= wind_speed)) and H((wind_speed <= 30.0)))"
KIAS_FORMULA = "H((kias >= 0.0))"
ASSIGNMENTS = {
    "semi_thrust_borne": "1",
    "semi_wing_borne": "2",
    "thrust_borne": "0",
    "wing_borne": "3",
}


def _source_case(document, name):
    requirements = document["vehicleSpec"]["Requirements"]
    matches = [requirement for requirement in requirements if requirement.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one original requirement {name}: found {len(matches)}")
    result = deepcopy(document)
    result["vehicleSpec"]["Requirements"] = deepcopy(matches)
    return result


def _case_bytes(document):
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def build_controls(source, destination, *, expected_sha256=PINNED_EXPORT_SHA256):
    """Build six independently classified controls with a verifiable receipt.

    All validations happen before any directory or case file is written.
    """
    source = Path(source)
    destination = Path(destination)
    payload = source.read_bytes()
    digest = sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise ValueError(f"source sha256 mismatch: expected {expected_sha256}, got {digest}")

    document = json.loads(payload)
    vehicle = document["vehicleSpec"]
    original_internals = vehicle["Internal_variables"]
    if len(original_internals) != len(ASSIGNMENTS):
        raise ValueError("source internal variable count drift")
    names = [record.get("name") for record in original_internals]
    if set(names) != set(ASSIGNMENTS) or len(set(names)) != len(ASSIGNMENTS):
        raise ValueError("source internal variable identity drift")
    for record in original_internals:
        if (record.get("assignmentCopilot") != ""
                or record.get("assignmentLustre") != ASSIGNMENTS[record["name"]]
                or record.get("type") != "int"):
            raise ValueError(f"source internal assignment/type drift: {record['name']}")

    kias_original = _source_case(document, "LPC_KIAS_0")
    wind_original = _source_case(document, "LPC_WIND_SPEED_30_assumption")
    if kias_original["vehicleSpec"]["Requirements"][0].get("CoCoSpecCode") != KIAS_FORMULA:
        raise ValueError("KIAS source formula drift")
    if wind_original["vehicleSpec"]["Requirements"][0].get("CoCoSpecCode") != WIND_FORMULA:
        raise ValueError("WIND source formula drift")

    kias_assigned = deepcopy(kias_original)
    for record in kias_assigned["vehicleSpec"]["Internal_variables"]:
        record["assignmentCopilot"] = ASSIGNMENTS[record["name"]]

    generated = [
        ("047-original.json", kias_original,
         "unaltered source slice; expected Copilot syntactic failure"),
        ("047-assigned-control.json", kias_assigned,
         "derived numeric Copilot assignments; not a source requirement"),
        ("040-original.json", wind_original,
         "unaltered source slice; expected standalone translator rejection"),
    ]
    for filename, formula, label in (
        ("040-nonnegative-diagnostic.json",
         "(H((0.0 <= wind_speed)) and H((wind_speed <= 30.0)))",
         "semantics-changing diagnostic, not a proposed repair"),
        ("040-subtractive-equivalent.json",
         "(H(((0.0 - 30.0) <= wind_speed)) and H((wind_speed <= 30.0)))",
         "arithmetic-equivalent diagnostic for signed literal parsing"),
        ("040-regrouped-equivalent.json",
         "H(((-30.0 <= wind_speed) and (wind_speed <= 30.0)))",
         "history-equivalent regrouping, retains signed literal"),
    ):
        candidate = deepcopy(wind_original)
        candidate["vehicleSpec"]["Requirements"][0]["CoCoSpecCode"] = formula
        generated.append((filename, candidate, label))

    receipt = {
        "sourceSha256": digest,
        "sourceRequirementCount": len(vehicle["Requirements"]),
        "classification": "DERIVED diagnostic; original source untouched",
        "cases": [
            {
                "file": filename,
                "sha256": sha256(_case_bytes(case)).hexdigest(),
                "label": label,
            }
            for filename, case, label in generated
        ],
    }
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("refusing to overwrite an occupied control directory")
    destination.mkdir(parents=True, exist_ok=True)
    for filename, case, _ in generated:
        (destination / filename).write_bytes(_case_bytes(case))
    (destination / "derived-receipt.json").write_bytes(_case_bytes(receipt))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-sha256", default=PINNED_EXPORT_SHA256)
    options = parser.parse_args()
    receipt = build_controls(
        options.input, options.out, expected_sha256=options.expected_sha256
    )
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
