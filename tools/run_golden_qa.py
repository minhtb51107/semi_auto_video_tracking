#!/usr/bin/env python3
"""Run lightweight Analyzer behavior checks from tests/golden_data/manifest.json."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from motlib import Det
from review_tracks import load_config
from review_tracks_v2 import DEFAULT_V2, analyze_v2, validate_config

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tests" / "golden_data" / "manifest.json"


def run_manifest(path=DEFAULT_MANIFEST):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if data.get("schema_version") != 1 or not isinstance(data.get("cases"), list):
        raise ValueError("Invalid golden manifest")
    covered = {category for case in data["cases"] for category in case.get("category", [])}
    missing = sorted(set(data.get("required_categories", [])) - covered)
    if missing:
        raise ValueError(f"Missing golden categories: {missing}")
    v1 = load_config()
    v2 = validate_config(json.loads(DEFAULT_V2.read_text(encoding="utf-8-sig")))
    results = []
    for case in data["cases"]:
        kind = case.get("source_kind")
        if kind == "OBSERVED_REFERENCE_ONLY":
            reference = ROOT / case["reference"]
            if not reference.is_file():
                raise ValueError(f"Missing observed reference: {case['reference']}")
            results.append({"id": case["id"], "status": "REFERENCE_PRESENT", "automated_ground_truth": False})
            continue
        if kind != "SYNTHETIC_RULE_FIXTURE":
            raise ValueError(f"Unknown source_kind in {case.get('id')}")
        detections = [Det(int(x[0]), int(x[1]), *map(float, x[2:7]), int(x[7]))
                      for x in case.get("detections", [])]
        total = max((x.frame for x in detections), default=1)
        output = analyze_v2(detections, v1, v2, total)
        reasons = {x["reason"] for x in output["flags"]}
        missing_reasons = sorted(set(case.get("expect_reasons", [])) - reasons)
        forbidden = sorted(set(case.get("forbid_reasons", [])) & reasons)
        if missing_reasons or forbidden:
            raise ValueError(f"Golden case {case['id']} failed: missing={missing_reasons}, forbidden={forbidden}")
        results.append({"id": case["id"], "status": "PASS", "reasons": sorted(reasons),
                        "automated_ground_truth": False})
    return {"schema_version": 1, "status": "PASS", "cases": results,
            "interpretation": "behavior_regression_not_accuracy_benchmark"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    try:
        value = run_manifest(args.manifest)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(json.dumps(value, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
