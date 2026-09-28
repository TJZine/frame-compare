"""Production-path audio-alignment benchmark over a labelled pair file.

Reads a maintainer-supplied label file (pair ids, categories, expected frames),
drives the production alignment path once per pair (result cache disabled,
per-pair diagnostics directories), classifies each pair, prints a sanitized
summary (pair ids and categories only; no media paths or titles), and writes
the full per-pair JSON to the output directory.

Label schema (media paths are relative to the label file's directory)::

    {"pairs": [
        {"id": "bs-1", "category": "development",
         "reference": "A.mkv", "comparison": "B.mkv", "expected_frame": 0},
        {"id": "neg-1", "category": "negative_control",
         "reference": "C.mkv", "comparison": "D.mkv",
         "expected": "not_applied"}]}

``speed_change`` pairs run with the comparison's effective FPS set to the
reference's probed FPS, matching ``sources.match_fps = "assume_reference"``.

Docker invocation (native macOS L-SMASH is broken; run in the test service):

    mkdir -p /tmp/u5-real-media && docker compose run --rm \\
      --volume "$PWD/comparison_videos:/media:ro" \\
      --volume "/tmp/u5-real-media:/proof" \\
      frame-compare-test -lc \\
      'python tools/alignment_benchmark.py --labels /media/alignment_labels.json --output /proof'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from frame_compare.services.alignment import align_clips_from_request
from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.alignment_review_projection import build_audio_review_presentation
from frame_compare.utils.types import (
    AlignmentCacheSettings,
    AlignmentClipIdentity,
    AlignmentClipRequest,
    AlignmentRequest,
)
from frame_compare.vs.loader import DefaultVSLoader

SPEED_CHANGE_CATEGORY = "speed_change"
NOT_APPLIED = "not_applied"
OUTCOME_NAMES = (
    "correct_applied",
    "wrong_applied",
    "provisional",
    "unavailable",
    "correctly_withheld",
)


@dataclass(frozen=True)
class LabelledPair:
    """One labelled pair with media paths resolved against the label file."""

    pair_id: str
    category: str
    reference: Path
    comparison: Path
    expected_frame: int | None


def classify_outcome(
    *,
    expected_frame: int | None,
    applied: bool,
    frame_offset: int | None,
    state: str,
) -> str:
    """Classify one pair; a withheld ``not_applied`` pair reports separately."""
    if expected_frame is None:
        return "correctly_withheld" if not applied else "wrong_applied"
    if applied:
        return "correct_applied" if frame_offset == expected_frame else "wrong_applied"
    return "unavailable" if state == "unavailable" else "provisional"


def refusal_rate(records: Sequence[Mapping[str, object]]) -> float | None:
    """Provisional-plus-unavailable share over pairs carrying an expected frame."""
    eligible = [record for record in records if record["expected_frame"] is not None]
    if not eligible:
        return None
    refused = [record for record in eligible if record["outcome"] in ("provisional", "unavailable")]
    return len(refused) / len(eligible)


def load_labels(path: Path) -> list[LabelledPair]:
    """Parse and validate the label file, failing closed on any defect."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read label file {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("pairs"), list):
        raise ValueError(f"label file {path} must hold a top-level 'pairs' list")
    entries: list[Any] = payload["pairs"]
    if not entries:
        raise ValueError(f"label file {path} must hold at least one pair")
    pairs: list[LabelledPair] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        pairs.append(_parse_pair(path, index, entry, seen))
    return pairs


def _parse_pair(path: Path, index: int, entry: Any, seen: set[str]) -> LabelledPair:
    where = f"label file {path} pair index {index}"
    if not isinstance(entry, dict):
        raise ValueError(f"{where} must be an object")
    pair_id = entry.get("id")
    category = entry.get("category")
    reference = entry.get("reference")
    comparison = entry.get("comparison")
    for name, value in (
        ("id", pair_id),
        ("category", category),
        ("reference", reference),
        ("comparison", comparison),
    ):
        if not isinstance(value, str) or not value:
            raise ValueError(f"{where} needs a non-empty string '{name}'")
    assert isinstance(pair_id, str) and isinstance(category, str)
    assert isinstance(reference, str) and isinstance(comparison, str)
    if pair_id in seen:
        raise ValueError(f"{where} duplicates pair id '{pair_id}'")
    seen.add(pair_id)
    expected_frame = _parse_expected(where, entry)
    media_root = path.parent
    reference_path = media_root / reference
    comparison_path = media_root / comparison
    for role, media_path in (("reference", reference_path), ("comparison", comparison_path)):
        if not media_path.is_file():
            raise ValueError(f"{where} {role} file is missing: {media_path}")
    return LabelledPair(
        pair_id=pair_id,
        category=category,
        reference=reference_path,
        comparison=comparison_path,
        expected_frame=expected_frame,
    )


def _parse_expected(where: str, entry: dict[str, Any]) -> int | None:
    has_frame = "expected_frame" in entry
    has_marker = "expected" in entry
    if has_frame == has_marker:
        raise ValueError(
            f'{where} needs exactly one of \'expected_frame\' or "expected": "not_applied"'
        )
    if has_marker:
        if entry["expected"] != NOT_APPLIED:
            raise ValueError(f"{where} has an unknown 'expected' marker: {entry['expected']!r}")
        return None
    expected_frame = entry["expected_frame"]
    if isinstance(expected_frame, bool) or not isinstance(expected_frame, int):
        raise ValueError(f"{where} 'expected_frame' must be an integer")
    return expected_frame


def _clip_request(
    path: Path,
    *,
    effective_fps: Fraction,
    source_fps: Fraction,
    source_frame_count: int,
) -> AlignmentClipRequest:
    stat = path.stat()
    return AlignmentClipRequest(
        path=path,
        label=path.stem,
        identity=AlignmentClipIdentity(path, stat.st_size, stat.st_mtime_ns),
        trim_start_frames=0,
        trim_end_frame_inclusive=None,
        effective_fps_num=effective_fps.numerator,
        effective_fps_den=effective_fps.denominator,
        source_fps_num=source_fps.numerator,
        source_fps_den=source_fps.denominator,
        source_frame_count=source_frame_count,
    )


async def align_pair(
    pair: LabelledPair,
    output_dir: Path,
    loader: DefaultVSLoader,
) -> dict[str, object]:
    """Align one pair through the production path and record its evidence."""
    reference_source = loader.load(pair.reference)
    comparison_source = loader.load(pair.comparison)
    reference_fps = reference_source.fps
    comparison_effective_fps = (
        reference_fps if pair.category == SPEED_CHANGE_CATEGORY else comparison_source.fps
    )
    reference = _clip_request(
        pair.reference,
        effective_fps=reference_fps,
        source_fps=reference_source.fps,
        source_frame_count=reference_source.num_frames,
    )
    comparison = _clip_request(
        pair.comparison,
        effective_fps=comparison_effective_fps,
        source_fps=comparison_source.fps,
        source_frame_count=comparison_source.num_frames,
    )
    pair_root = output_dir / "pairs" / pair.pair_id
    pair_root.mkdir(parents=True, exist_ok=True)
    config = AlignmentConfig(
        cache_results=False,
        max_offset_seconds=30.0,
        use_vsview=False,
        channel_strategy="mono_downmix",
    )
    request = AlignmentRequest(
        reference=reference,
        selected_reference_relationship="auto",
        comparisons=[comparison],
        previous_offsets="disabled",
        generated_dir=pair_root,
        shared_alignment_cache_dir=output_dir / "cache",
        settings=AlignmentCacheSettings(30.0, "mono_downmix"),
        alignment_diagnostics_dir=pair_root / "alignment_diagnostics",
        alignment_diagnostics_root=output_dir / "pairs",
    )
    started = time.monotonic()
    (result,) = await align_clips_from_request(
        request,
        config,
        reference_fps=Fraction(reference.effective_fps_num, reference.effective_fps_den),
        vs_loader=loader,
        quiet=True,
    )
    elapsed = time.monotonic() - started
    attempt = result.audio_attempt
    if attempt is None:
        raise RuntimeError(f"production result for {pair.pair_id} omitted its attempt")
    review = build_audio_review_presentation(attempt)
    return {
        "pair_id": pair.pair_id,
        "category": pair.category,
        "expected_frame": pair.expected_frame,
        "reference": pair.reference.name,
        "comparison": pair.comparison.name,
        "x_subframe": attempt.audio.subframe_estimate,
        "r_audio_rounded": attempt.audio.rounded_frame,
        "c_video_confirmed": attempt.video_check.confirmed_offset,
        "applied_frame": result.frame_offset,
        "state": attempt.decision.state,
        "primary_reason": attempt.decision.primary_reason,
        "reasons": list(review.reasons),
        "video_wins": review.video_wins,
        "video_margin": review.video_margin,
        "target_count": len(attempt.video_check.targets),
        "elapsed_seconds": elapsed,
        "outcome": classify_outcome(
            expected_frame=pair.expected_frame,
            applied=result.applied,
            frame_offset=result.frame_offset,
            state=attempt.decision.state,
        ),
    }


def _format(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:+.2f}"
    return str(value)


def _print_table_header() -> None:
    print(
        f"{'pair':<9} {'category':<16} {'expected':>8} {'x':>8} {'r':>5} {'c':>5} "
        f"{'applied':>7} {'state':<17} {'reason':<34} {'outcome':<18} {'s':>7}",
        flush=True,
    )


def _print_table_row(record: Mapping[str, object]) -> None:
    print(
        f"{record['pair_id']!s:<9} {record['category']!s:<16} "
        f"{_format(record['expected_frame']):>8} {_format(record['x_subframe']):>8} "
        f"{_format(record['r_audio_rounded']):>5} {_format(record['c_video_confirmed']):>5} "
        f"{_format(record['applied_frame']):>7} {record['state']!s:<17} "
        f"{record['primary_reason']!s:<34} {record['outcome']!s:<18} "
        f"{record['elapsed_seconds']:.1f}",
        flush=True,
    )


async def run_benchmark(labels: Path, output: Path) -> None:
    """Run every labelled pair, print the sanitized summary, and write the JSON."""
    pairs = load_labels(labels)
    output.mkdir(parents=True, exist_ok=True)
    loader = DefaultVSLoader()
    started = time.monotonic()
    records: list[dict[str, object]] = []
    _print_table_header()
    for pair in pairs:
        record = await align_pair(pair, output, loader)
        records.append(record)
        _print_table_row(record)
    counts = Counter(str(record["outcome"]) for record in records)
    summary_counts = {name: counts.get(name, 0) for name in OUTCOME_NAMES}
    rate = refusal_rate(records)
    print(" ".join(f"{name}={summary_counts[name]}" for name in OUTCOME_NAMES), flush=True)
    if rate is None:
        print("refusal_rate=n/a (no same-content pairs with an expected frame)", flush=True)
    else:
        eligible = sum(1 for record in records if record["expected_frame"] is not None)
        refused = sum(
            1
            for record in records
            if record["expected_frame"] is not None
            and record["outcome"] in ("provisional", "unavailable")
        )
        print(f"refusal_rate={rate:.2f} ({refused}/{eligible} same-content pairs)", flush=True)
    payload = {
        "pairs": records,
        "summary": {"counts": summary_counts, "refusal_rate": rate},
        "total_elapsed_seconds": time.monotonic() - started,
    }
    (output / "pair-results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def main() -> None:
    """Parse ``--labels`` and ``--output`` and run the benchmark."""
    parser = argparse.ArgumentParser(
        description="Align every labelled pair through the production path."
    )
    parser.add_argument("--labels", type=Path, required=True, help="Label file to run.")
    parser.add_argument("--output", type=Path, required=True, help="Directory for JSON output.")
    args = parser.parse_args()
    asyncio.run(run_benchmark(labels=args.labels, output=args.output))


if __name__ == "__main__":
    main()
