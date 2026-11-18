"""Lossless per-property slices of a pinned FRET-exported Ogma JSON document.

This tool never changes a property formula. Translation outcomes require an
external native Ogma execution; absent or malformed native results fail closed.
"""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re


EXPECTED_FULL_SHA256 = "2754f9a2debefbe87e8dc9d9e0a4c5226473781bd21433ed80f3accf802f1443"
SAFE_NAME = re.compile(r"[A-Za-z0-9_.-]+\Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def locate_ogma_binary(ogma_project: Path) -> Path:
    """Find exactly one executable built by the pinned cabal ogma-cli target.

    Cabal list-bin may mix status diagnostics into stdout. Inspect actual
    build output rather than treating console text as an executable path.
    """
    glob = "dist-newstyle/build/*/*/ogma-cli-*/x/ogma/build/ogma/ogma"
    candidates = sorted(
        path.resolve() for path in ogma_project.glob(glob)
        if path.is_file() and os.access(path, os.X_OK)
    )
    if len(candidates) != 1:
        raise ValueError(f"Expected exactly one Ogma CLI executable, got {len(candidates)}")
    return candidates[0]


def split(source: Path, destination: Path) -> dict:
    """Preserve every field except replacing all Requirements with a singleton."""
    original = source.read_bytes()
    document = json.loads(original)
    if not isinstance(document, dict) or list(document) != ["vehicleSpec"]:
        raise ValueError("Expected the exported vehicleSpec document")
    spec = document["vehicleSpec"]
    if not isinstance(spec, dict):
        raise ValueError("Expected a vehicleSpec mapping")
    requirements = spec.get("Requirements")
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("Expected nonempty Requirements array")
    others = spec.get("Other_variables")
    if not isinstance(others, list):
        raise ValueError("Expected Other_variables array")

    items = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            raise ValueError(f"Requirement {index} is not a mapping")
        name = requirement.get("name")
        formula = requirement.get("CoCoSpecCode")
        if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
            raise ValueError(f"Requirement {index} has an unsafe name")
        if not isinstance(formula, str):
            raise ValueError(f"Requirement {index} lacks the formula")
        filename = f"{index:03d}-{name}.json"
        # Rebuild the smallest changed document; the original field order and
        # contents are preserved after JSON parsing. Formula bytes are unchanged.
        isolated_spec = {key: ([requirement] if key == "Requirements" else value)
                         for key, value in spec.items()}
        isolated_document = {"vehicleSpec": isolated_spec}
        encoded = (json.dumps(isolated_document, ensure_ascii=False, indent=2) + "\n").encode()
        items.append((filename, encoded, name, formula))

    destination.mkdir(parents=True, exist_ok=True)
    for filename, encoded, _, _ in items:
        (destination / filename).write_bytes(encoded)

    receipt = {
        "boundary": "FRET source-method-exported JSON; one exact property per native Ogma run",
        "fullSourceSha256": sha256(original),
        "requirements": len(items),
        "otherVariables": len(others),
        "items": [
            {"index": index, "file": name, "name": pname,
             "formula": formula, "sliceSha256": sha256(data)}
            for index, (name, data, pname, formula) in enumerate(items)
        ],
    }
    (destination / "slice-manifest.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


def classify(manifest: dict, statuses: Path) -> dict:
    """Count only native exit-zero plus emitted Haskell as translated."""
    expected = manifest["items"]
    with statuses.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    if len(rows) != len(expected):
        raise ValueError(f"Missing native outcomes: got {len(rows)}, expected {len(expected)}")
    results = []
    for item, row in zip(expected, rows):
        if (set(row) != {"index", "file", "exit_code", "generated_haskell"}
                or row["index"] != str(item["index"])
                or row["file"] != item["file"]
                or row["generated_haskell"] not in ("0", "1")):
            raise ValueError(f"Unexpected or mismatched native outcome: {row}")
        try:
            code = int(row["exit_code"])
        except (ValueError, TypeError) as error:
            raise ValueError(f"Invalid native exit status: {row}") from error
        if code < 0 or (code != 0 and row["generated_haskell"] == "1"):
            raise ValueError(f"Inconsistent native outcome: {row}")
        translated = code == 0 and row["generated_haskell"] == "1"
        results.append({**item, "nativeExit": code, "emittedHaskell": row["generated_haskell"] == "1",
                        "status": "translated" if translated else "not_translated"})
    accepted = sum(item["status"] == "translated" for item in results)
    return {
        "boundary": "native Ogma parse/translation and emitted Copilot.hs, not GHC/C99 execution",
        "sourceSha256": manifest["fullSourceSha256"],
        "requirements": len(results),
        "translated": accepted,
        "notTranslated": len(results) - accepted,
        "items": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="operation", required=True)
    slicer = subs.add_parser("split")
    slicer.add_argument("--input", type=Path, required=True)
    slicer.add_argument("--out", type=Path, required=True)
    slicer.add_argument("--expect-sha256", default=EXPECTED_FULL_SHA256)
    reporter = subs.add_parser("report")
    reporter.add_argument("--manifest", type=Path, required=True)
    reporter.add_argument("--statuses", type=Path, required=True)
    reporter.add_argument("--out", type=Path, required=True)
    finder = subs.add_parser("locate")
    finder.add_argument("--ogma-dir", type=Path, required=True)
    finder.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.operation == "split":
        actual_hash = sha256(args.input.read_bytes())
        if actual_hash != args.expect_sha256:
            parser.error(f"Full export source hash mismatch: got {actual_hash}, expected {args.expect_sha256}")
        receipt = split(args.input, args.out)
        print(f"Isolated {receipt['requirements']} exact requirements, {receipt['otherVariables']} variables; "
              f"source={receipt['fullSourceSha256']}")
    elif args.operation == "report":
        receipt = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = classify(receipt, args.statuses)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Native Ogma translation: {report['translated']}/{report['requirements']} translated; "
              f"{report['notTranslated']} not translated")
    else:
        binary = locate_ogma_binary(args.ogma_dir)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(str(binary) + "\n", encoding="utf-8")
        print(f"Resolved unique built Ogma CLI: {binary}")


if __name__ == "__main__":
    main()
