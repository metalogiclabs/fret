"""Pinned FRET Lift+Cruise requirement → C2PO → native R2U2 replay.

This is a *renderer-and-monitor* pilot, not a full FRET UI export or a
FRET/Ogma/Copilot equivalence result.  The source authority is the checked-in
FRET case-study requirement LPC_REARPROP, with its MLTL/past-time fields.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


PINNED_FRET = "cf0f913cc15c41705e803593297e89cd6056b839"
PINNED_R2U2 = "2875a1dfc0b8cb27c4c4f14bece6b95c3afff91a"
REQUIREMENT = "The vehicle shall always satisfy rearprop xor hover_control_mode"
CHANNELS = ("rearprop", "hover_control_mode")

CASES = {
    "clear": ((1, 0), (0, 1), (1, 0)),
    "both_on": ((1, 0), (1, 1), (0, 1)),
    "both_off": ((1, 0), (0, 0), (0, 1)),
}
EXPECTED = {
    "clear": (True, True, True),
    "both_on": (True, False, True),
    "both_off": (True, False, True),
}


def expected_rows(name: str) -> tuple[bool, ...]:
    return EXPECTED[name]


def _contract_from_case(case: dict) -> dict:
    reqs = [r for r in case["requirements"] if r.get("reqid") == "LPC_REARPROP"]
    if len(reqs) != 1 or reqs[0].get("fulltext") != REQUIREMENT:
        raise ValueError("Pinned FRET source requirement changed or disappeared")
    semantics = reqs[0]["semantics"]
    if (semantics.get("component_name") != "vehicle"
            or semantics.get("R2U2Code") != "(rearprop xor hover_control_mode)"
            or semantics.get("ptExpanded") != "(H (rearprop xor hover_control_mode))"):
        raise ValueError("FRET source/target semantics fingerprint changed")
    variables = []
    for name in CHANNELS:
        matches = [v for v in case["variables"] if v.get("variable_name") == name
                   and v.get("component_name") == "vehicle"]
        if len(matches) != 1 or matches[0].get("dataType") != "boolean" or matches[0].get("idType") != "Output" or not matches[0].get("r2u2Completed"):
            raise ValueError(f"Incomplete or ambiguous FRET variable: {name}")
        variables.append({"name": name, "type": "bool"})
    return {"outputVariables": variables, "inputVariables": [],
            "internalVariables": [], "r2u2Assignments": [],
            "properties": [{"reqid": "LPC_REARPROP", "R2U2": semantics["R2U2Code"]}]}


_RENDERER_RUNNER = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const file = fs.readFileSync(process.argv[1], 'utf8');
// Remove only ESM export syntax to execute the *unchanged* original function
// bodies in Node's stock VM, avoiding an Electron/Babel installation.
const stripped = file.replace(/^export\s*\{[^}]*\}\s*/m, '');
if (stripped === file) throw new Error('Unrecognized FRET exporter module');
const renderers = vm.runInNewContext(stripped + '\n;({renderC2POSpec,renderC2POMap,renderC2POCSVHeader})');
const contract = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify({
  c2po: renderers.renderC2POSpec(contract),
  map: renderers.renderC2POMap(contract),
  csv: renderers.renderC2POCSVHeader(contract)
}));
"""


def render_from_pinned_fret(exporter_path: Path, case: dict) -> dict[str, str]:
    contract = _contract_from_case(case)
    result = subprocess.run(["node", "-e", _RENDERER_RUNNER, str(exporter_path)],
                            input=json.dumps(contract), capture_output=True,
                            text=True, timeout=30, check=True)
    rendered = json.loads(result.stdout)
    if set(rendered) != {"c2po", "map", "csv"}:
        raise ValueError("Unexpected renderer output")
    return rendered


def native_verdicts(stdout: str, count: int) -> tuple[bool, ...]:
    records = re.findall(r"^0:(\d+),([TF])$", stdout, flags=re.MULTILINE)
    if len(records) != count:
        raise ValueError(f"Expected {count} indexed formula-0 verdicts; got {records!r}")
    stamps = [int(i) for i, _ in records]
    if stamps != list(range(count)):
        raise ValueError(f"Native verdict timestamps missing, duplicate, or reordered: {stamps}")
    return tuple(v == "T" for _, v in records)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(args: list[str], output: Path, cwd: Path) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True,
                            timeout=240, check=False)
    output.with_suffix(".stdout").write_text(result.stdout)
    output.with_suffix(".stderr").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {args}\n{result.stderr[-3000:]}")
    return result.stdout


def _assert_checkout(repo: Path, expected_sha: str) -> None:
    actual = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if actual != expected_sha:
        raise ValueError(f"Expected {expected_sha}, got {actual} in {repo}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fret", required=True, type=Path)
    parser.add_argument("--r2u2", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    fret, r2u2, out = args.fret.resolve(), args.r2u2.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    _assert_checkout(fret, PINNED_FRET)
    _assert_checkout(r2u2, PINNED_R2U2)
    case_path = fret / "caseStudies/LiftPlusCruise/LPC_full_reqts_and_vars.json"
    renderer = fret / "fret-electron/support/r2u2Export.js"
    generated = render_from_pinned_fret(renderer, json.loads(case_path.read_text()))
    for name, ext in (("c2po", "c2po"), ("map", "map"), ("csv", "csv")):
        (out / f"LPC_REARPROP.{ext}").write_text(generated[name])
    if (generated["map"].splitlines() != ["rearprop:0", "hover_control_mode:1"]
            or generated["csv"].strip() != "# rearprop, hover_control_mode"):
        raise ValueError("FRET exporter did not preserve the expected signal mapping")
    if "LPC_REARPROP: (rearprop xor hover_control_mode);" not in generated["c2po"]:
        raise ValueError("FRET exporter changed requirement identity or body")

    trace_paths = {}
    for name, rows in CASES.items():
        path = out / f"{name}.csv"
        path.write_text(generated["csv"] + "".join(f"{a},{b}\n" for a, b in rows))
        trace_paths[name] = path

    spec_path = out / "LPC_REARPROP.c2po"
    binary = out / "LPC_REARPROP.bin"
    _run(["python3", str(r2u2 / "compiler/c2po.py"), "--spec", str(spec_path),
          "--trace", str(trace_paths["clear"]), "--output", str(binary)],
         out / "compile", cwd=r2u2)
    manifest = {
        "stage": "RESEARCH / exact finite-trace pilot",
        "source": "NASA-SW-VnV/fret caseStudies/LiftPlusCruise LPC_REARPROP",
        "fret_sha": PINNED_FRET, "r2u2_sha": PINNED_R2U2,
        "source_requirement": REQUIREMENT,
        "r2u2_property_body": "(rearprop xor hover_control_mode)",
        "past_time_property": "H (rearprop xor hover_control_mode)",
        "interpretation": "Each native verdict is a pointwise result; conjunction of the prefix is compared to source's historical-always semantics",
        "case_study_sha256": _sha256(case_path),
        "renderer_sha256": _sha256(renderer),
        "generated_c2po_sha256": _sha256(spec_path),
        "binary_sha256": _sha256(binary),
        "cases": {},
        "limitations": ["Two Boolean signals only", "Not FRET GUI/Electron end-to-end", "Not Copilot native verification", "Not mission deployment"],
    }
    for name, path in trace_paths.items():
        stdout = _run([str(r2u2 / "monitors/c/build/r2u2"), str(binary), str(path)],
                      out / f"run_{name}", cwd=r2u2)
        native = native_verdicts(stdout, len(CASES[name]))
        expected = expected_rows(name)
        if native != expected:
            raise AssertionError(f"Native R2U2 {name}: {native} != independent source truth {expected}")
        prefix = tuple(all(native[:i + 1]) for i in range(len(native)))
        expected_prefix = tuple(all(expected[:i + 1]) for i in range(len(expected)))
        if prefix != expected_prefix:
            raise AssertionError("Historical-always prefix discrepancy")
        manifest["cases"][name] = {
            "trace_sha256": _sha256(path), "expected_pointwise": expected,
            "native_pointwise": native, "source_H_prefix": expected_prefix,
            "native_aggregated_prefix": prefix,
            "native_stdout": stdout.strip(),
        }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
