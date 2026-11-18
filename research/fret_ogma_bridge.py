"""FRET Lift+Cruise → FRET-template-shaped JSON → native NASA Ogma pilot.

The JSON shape follows FRET's checked-in CoPilotTemplates and Ogma's fcs_lustre
format; this does *not* invoke the full FRET/Electron exporter. Native Ogma and
Copilot must be separately executed before claiming monitor correspondence.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from fret_lpc_replay import PINNED_FRET, REQUIREMENT, _contract_from_case


PINNED_OGMA = "1f8355712aba76b4047ccb4b1f4cead1b6cdb42a"
ORIGINAL_FORMULA = "H((rearprop xor hover_control_mode))"
# Explicit diagnostic control: Boolean XOR expanded into the operators exposed
# by the pinned NASA Ogma Lustre grammar. This is not a FRET export or an
# owner-authorized change of requirement intent.
OGMA_LUSTRE_CONTROL = (
    "H(((rearprop or hover_control_mode) and not "
    "(rearprop and hover_control_mode)))"
)


def create_ogma_input(case: dict, variant: str = "original") -> dict:
    if variant not in ("original", "ogma-lustre-control"):
        raise ValueError(f"Unrecognized diagnostic variant: {variant}")
    contract = _contract_from_case(case)
    requirement = next(r for r in case["requirements"] if r["reqid"] == "LPC_REARPROP")
    semantics = requirement["semantics"]
    if semantics.get("CoCoSpecCode") != ORIGINAL_FORMULA:
        raise ValueError("Pinned source Copilot temporal formula changed")
    formula = ORIGINAL_FORMULA if variant == "original" else OGMA_LUSTRE_CONTROL
    return {
        "vehicleSpec": {
            "Internal_variables": [],
            "Other_variables": contract["outputVariables"],
            "Functions": [],
            "Requirements": [{
                "name": "LPC_REARPROP",
                "fretish": REQUIREMENT,
                "CoCoSpecCode": formula,
                "ptLTL": semantics["ptExpanded"],
            }],
        }
    }


def _checked_sha(path: Path, sha: str) -> None:
    actual = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    if actual != sha:
        raise ValueError(f"Wrong pinned source {path}: {actual} != {sha}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fret", required=True, type=Path)
    parser.add_argument("--ogma", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--variant", choices=("original", "ogma-lustre-control"), default="original")
    args = parser.parse_args()
    fret, ogma, out = args.fret.resolve(), args.ogma.resolve(), args.out.resolve()
    _checked_sha(fret, PINNED_FRET)
    _checked_sha(ogma, PINNED_OGMA)
    case_path = fret / "caseStudies/LiftPlusCruise/LPC_full_reqts_and_vars.json"
    case = json.loads(case_path.read_text())
    out.mkdir(parents=True, exist_ok=True)
    target = out / (
        "LPC_REARPROP.fret-copilot.json" if args.variant == "original"
        else "LPC_REARPROP.ogma-lustre-control.json"
    )
    target.write_text(json.dumps(create_ogma_input(case, variant=args.variant), indent=2) + "\n")
    manifest = {
        "source": "NASA-SW-VnV/fret LiftPlusCruise LPC_REARPROP",
        "fret_sha": PINNED_FRET,
        "ogma_sha": PINNED_OGMA,
        "fret_case_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
        "input_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "diagnostic_variant": args.variant,
        "source_CoCoSpecCode": ORIGINAL_FORMULA,
        "input_template": "FRET CoPilotTemplates/Complete.ejs and Ogma fcs_lustre compatible shape",
        "scope": "source-pinned template-shaped contract; no FRET Electron exporter execution",
    }
    (out / "source-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
