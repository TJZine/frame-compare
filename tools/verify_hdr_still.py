"""Bounded native probe runner and strict two-checkpoint comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent


def compare(reference: Path, candidate: Path):
    def collect(directory):
        results = sorted(directory.glob("*/result.json"))
        assert results, f"No results under {directory}"
        found = {}
        inputs = []
        for path in results:
            result = json.loads(path.read_text())
            assert result["status"] == "passed", str(path)
            inputs.append(result)
            for row in result["rows"]:
                found.setdefault(row["n"], []).append((path.parent / row["arrays"], row))
        return found, inputs

    (refs, ref_inputs), (candidates, candidate_inputs) = collect(reference), collect(candidate)
    assert refs.keys() == candidates.keys(), "Frame coverage mismatch"
    # Native binary and mode intentionally differ. Input controls/runtime must not.
    fields = ["fixture", "settings", "tone_kwargs", "platform", "python", "vapoursynth"]
    fingerprint = {key: ref_inputs[0][key] for key in fields}
    mismatches = [
        key
        for item in ref_inputs + candidate_inputs
        for key in fields
        if key not in item or item[key] != fingerprint[key]
    ]
    expected_histories = {item["history"]: item["requests"] for item in ref_inputs}
    actual_histories = {item["history"]: item["requests"] for item in candidate_inputs}
    partial_negative = all(item["mode"] == "stock-sequence" for item in candidate_inputs)
    if not partial_negative and actual_histories != expected_histories:
        mismatches.append("history/request coverage")
    for history, requests in actual_histories.items():
        if expected_histories.get(history) != requests:
            mismatches.append("history/requests:" + history)
    if mismatches:
        return {
            "status": "failed",
            "observations": [],
            "input_mismatches": sorted(set(mismatches)),
            "tolerance": 0,
        }
    observations = []
    for n in sorted(refs):
        with np.load(refs[n][0][0], allow_pickle=False) as arrays:
            oracle = {key: arrays[key].copy() for key in ["native16", "srgb8"]}
        for path, _ in refs[n] + candidates[n]:
            with np.load(path, allow_pickle=False) as arrays:
                for key, expected in oracle.items():
                    actual = arrays[key]
                    assert actual.shape == expected.shape and actual.dtype == expected.dtype, str(
                        path
                    )
                    difference = np.abs(actual.astype(np.int64) - expected.astype(np.int64))
                    mismatch = np.argwhere(difference)
                    observations.append(
                        {
                            "n": n,
                            "file": str(path),
                            "checkpoint": key,
                            "different_samples": int(np.count_nonzero(difference)),
                            "max_difference": int(difference.max()),
                            "first_mismatch": mismatch[0].tolist() if len(mismatch) else None,
                        }
                    )
    return {
        "status": "passed" if all(r["different_samples"] == 0 for r in observations) else "failed",
        "observations": observations,
        "tolerance": 0,
        "comparison_fingerprint_sha256": hashlib.sha256(
            json.dumps(fingerprint, sort_keys=True).encode()
        ).hexdigest(),
        "boundary": "Recorded fixture/settings/kwargs/Python/VS/platform match. Exact source/GPU identities require separate receipts. Not cross-device identity or faults/RPU/eviction acceptance.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["stock-fresh", "candidate-fresh", "candidate-independent", "stock-sequence"],
    )
    parser.add_argument("--plugin", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument(
        "--history",
        action="append",
        choices=["direct", "helper", "forward", "reverse", "repeated", "parallel"],
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if args.self_test:
        # Verify comparator enforcement, rather than claiming another GPU test.
        for directory in ["ref/h", "good/h", "bad/h", "wrong-settings/h"]:
            d = args.output / directory
            d.mkdir(parents=True)
            a = np.arange(12, dtype=np.uint16).reshape(3, 2, 2)
            b = np.arange(12, dtype=np.uint8).reshape(3, 2, 2)
            if directory.startswith("bad"):
                a[0, 0, 0] += 1
            np.savez_compressed(d / "frame.npz", native16=a, srgb8=b)
            metadata = {
                "status": "passed",
                "rows": [{"n": 0, "arrays": "frame.npz"}],
                "fixture": "comparator-selftest-only",
                "settings": {},
                "tone_kwargs": {"smoothing_period": 45},
                "platform": "synthetic",
                "python": "synthetic",
                "vapoursynth": "synthetic",
                "history": "direct",
                "requests": [0],
                "mode": "stock-fresh",
            }
            if directory.startswith("wrong-settings"):
                metadata["tone_kwargs"]["smoothing_period"] = 0
            (d / "result.json").write_text(json.dumps(metadata))
        good = compare(args.output / "ref", args.output / "good")
        bad = compare(args.output / "ref", args.output / "bad")
        wrong_settings = compare(args.output / "ref", args.output / "wrong-settings")
        assert good["status"] == "passed" and bad["status"] == "failed"
        assert (
            wrong_settings["status"] == "failed"
            and "tone_kwargs" in wrong_settings["input_mismatches"]
        )
        assert any(
            r["checkpoint"] == "native16" and r["different_samples"] == 1
            for r in bad["observations"]
        )
        (args.output / "self-test.json").write_text(
            json.dumps(
                {
                    "status": "passed",
                    "known_good": good,
                    "deliberate_native_only_violation": bad,
                    "identical_pixels_wrong_settings": wrong_settings,
                },
                indent=2,
            )
        )
        print(
            "Comparator self-test passed: equal accepted; native-only one-code difference rejected."
        )
        return 0
    if not args.mode:
        parser.error("--mode is required unless --self-test")
    commands = []
    code = 0
    for history in args.history or [
        "direct",
        "helper",
        "forward",
        "reverse",
        "repeated",
        "parallel",
    ]:
        command = [
            sys.executable,
            str(ROOT / "hdr_still_probe.py"),
            "--mode",
            args.mode,
            "--history",
            history,
            "--output",
            str(args.output / history),
        ]
        if args.plugin:
            command += ["--plugin", str(args.plugin.resolve())]
        receipt = {
            "command": command,
            "cwd": str(Path.cwd()),
            "started_utc": datetime.now(UTC).isoformat(),
        }
        try:
            process = subprocess.run(command, capture_output=True, timeout=150)
            receipt["exit_code"] = process.returncode
            stdout, stderr = process.stdout, process.stderr
        except subprocess.TimeoutExpired as exc:
            receipt.update(exit_code=None, timeout_seconds=150)
            stdout, stderr = exc.stdout or b"", exc.stderr or b""
        (args.output / (history + ".stdout.txt")).write_bytes(stdout)
        (args.output / (history + ".stderr.txt")).write_bytes(stderr)
        commands.append(receipt)
        (args.output / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if receipt["exit_code"] != 0:
            code = 1
            break
    if not code and args.reference:
        comparison = compare(args.reference, args.output)
        (args.output / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
        if comparison["status"] != "passed":
            code = 1
    print(
        json.dumps(
            {
                "exit_code": code,
                "children": len(commands),
                "probe_sha256": hashlib.sha256(
                    (ROOT / "hdr_still_probe.py").read_bytes()
                ).hexdigest(),
            }
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
