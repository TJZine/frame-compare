"""Production-path audio-alignment benchmark over a labelled pair file.

Reads a maintainer-supplied label file, prepares each pair through the normal
orchestration path, runs production alignment once (result cache disabled),
prints a sanitized summary (pair ids and categories only; no media paths or
titles), and writes the full per-pair JSON to the output directory.

Label schema (media paths are relative to the label file's directory)::

    {"pairs": [
        {"id": "bs-1", "category": "development",
         "reference": "A.mkv", "comparison": "B.mkv", "expected_frame": 0,
         "expected_automatic": "applied"},
        {"id": "neg-1", "category": "negative_control",
         "reference": "C.mkv", "comparison": "D.mkv",
         "expected_automatic": "not_applied"}]}

Labels run at pure defaults. ``speed_change`` pairs use the production
``sources.match_fps = "assume_reference"`` preparation setting.

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
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal, cast

from frame_compare.orchestration import preparation
from frame_compare.orchestration.context import ClipActiveRect, RunContext
from frame_compare.orchestration.phase_alignment import run_align_phase
from frame_compare.orchestration.types import RunDependencies, RunRequest
from frame_compare.utils.alignment_review_projection import build_audio_review_presentation
from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.utils.paths import require_managed_immediate_child
from frame_compare.vs.loader import DefaultVSLoader

SPEED_CHANGE_CATEGORY = "speed_change"
NOT_APPLIED = "not_applied"
APPLIED = "applied"
type ExpectedAutomatic = Literal["applied", "not_applied"]
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
    expected_automatic: ExpectedAutomatic


def classify_outcome(
    *,
    expected_frame: int | None,
    expected_automatic: ExpectedAutomatic,
    applied: bool,
    frame_offset: int | None,
    state: str,
) -> str:
    """Classify visual correctness independently from expected automation."""
    if expected_automatic == NOT_APPLIED:
        if applied:
            return "wrong_applied"
        if expected_frame is not None and state != "provisional":
            return "unavailable"
        return "correctly_withheld"
    if expected_frame is None:
        raise ValueError("an automatically applied pair requires expected_frame")
    if applied:
        return "correct_applied" if frame_offset == expected_frame else "wrong_applied"
    return "unavailable" if state == "unavailable" else "provisional"


def refusal_counts(records: Sequence[Mapping[str, object]]) -> tuple[int, int]:
    """Count (refused, eligible) pairs for the refusal rate."""
    eligible = [record for record in records if record["expected_automatic"] == APPLIED]
    refused = [record for record in eligible if record["outcome"] in ("provisional", "unavailable")]
    return len(refused), len(eligible)


def refusal_rate(records: Sequence[Mapping[str, object]]) -> float | None:
    """Provisional-plus-unavailable share over expected automatic applications."""
    refused, eligible = refusal_counts(records)
    if not eligible:
        return None
    return refused / eligible


def benchmark_passed(records: Sequence[Mapping[str, object]]) -> bool:
    """Require every pair to reach its labelled automatic outcome."""
    return all(record["outcome"] in ("correct_applied", "correctly_withheld") for record in records)


def load_labels(path: Path) -> list[LabelledPair]:
    """Parse and validate the label file, failing closed on any defect."""
    try:
        payload_raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read label file {path}: {exc}") from exc
    if not isinstance(payload_raw, dict):
        raise ValueError(f"label file {path} must hold a top-level 'pairs' list")
    payload = cast(dict[str, Any], payload_raw)
    entries_raw = payload.get("pairs")
    if not isinstance(entries_raw, list):
        raise ValueError(f"label file {path} must hold a top-level 'pairs' list")
    entries = cast(list[Any], entries_raw)
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
    entry = cast(dict[str, Any], entry)
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
    if pair_id in (".", "..") or any(
        path.name != pair_id for path in (PurePosixPath(pair_id), PureWindowsPath(pair_id))
    ):
        raise ValueError(f"{where} 'id' must be a single path-free name")
    if pair_id in seen:
        raise ValueError(f"{where} duplicates pair id '{pair_id}'")
    seen.add(pair_id)
    expected_frame, expected_automatic = _parse_expected(where, entry)
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
        expected_automatic=expected_automatic,
    )


def _parse_expected(where: str, entry: dict[str, Any]) -> tuple[int | None, ExpectedAutomatic]:
    expected_automatic = entry.get("expected_automatic")
    if expected_automatic not in (APPLIED, NOT_APPLIED):
        raise ValueError(f'{where} needs "expected_automatic": "applied" or "not_applied"')
    expected_frame = entry.get("expected_frame")
    if expected_frame is not None and (
        isinstance(expected_frame, bool) or not isinstance(expected_frame, int)
    ):
        raise ValueError(f"{where} 'expected_frame' must be an integer when present")
    if expected_automatic == APPLIED and expected_frame is None:
        raise ValueError(f"{where} expected automatic application needs 'expected_frame'")
    return expected_frame, expected_automatic


def _ensure_media_link(link: Path, target: Path) -> None:
    if link.is_symlink() and link.resolve() == target.resolve():
        return
    if link.exists() or link.is_symlink():
        raise RuntimeError(f"benchmark workspace path already exists: {link}")
    link.symlink_to(target)


def _pair_config(pair: LabelledPair) -> str:
    match_fps = "assume_reference" if pair.category == SPEED_CHANGE_CATEGORY else "disabled"
    return f'''[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[audio_alignment]
enable = true
max_offset_seconds = 30.0
use_vsview = false
force_interactive = false
cache_results = false
channel_strategy = "mono_downmix"
previous_offsets = "disabled"

[screenshots]
use_ffmpeg = true

[report]
enable = false

[sources]
reference = "00-reference{pair.reference.suffix}"
match_fps = "{match_fps}"
'''


def _active_rect_payload(rect: ClipActiveRect | None) -> dict[str, object] | None:
    if rect is None:
        return None
    return {
        "x": rect.x,
        "y": rect.y,
        "width": rect.width,
        "height": rect.height,
        "source": rect.source,
        "detection_mode": rect.detection_mode,
    }


async def _prepare_pair(
    pair: LabelledPair, pair_root: Path, loader: DefaultVSLoader
) -> preparation.PrepState:
    workspace_root = require_managed_immediate_child(pair_root, pair_root / "workspace")
    input_dir = require_managed_immediate_child(
        workspace_root, workspace_root / "comparison_videos"
    )
    config_dir = require_managed_immediate_child(workspace_root, workspace_root / "config")
    require_managed_immediate_child(workspace_root, workspace_root / "generated")
    pair_root.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    reference_link = input_dir / f"00-reference{pair.reference.suffix}"
    comparison_link = input_dir / f"01-comparison{pair.comparison.suffix}"
    _ensure_media_link(reference_link, pair.reference)
    _ensure_media_link(comparison_link, pair.comparison)
    write_text_atomic(config_dir / "config.toml", _pair_config(pair), encoding="utf-8")
    return await preparation.execute_prep(
        RunRequest(
            root=workspace_root,
            skip_analysis=True,
            skip_metadata=True,
            no_upload=True,
        ),
        RunDependencies(vs_loader=loader),
    )


async def align_pair(
    pair: LabelledPair,
    output_dir: Path,
    loader: DefaultVSLoader,
) -> dict[str, object]:
    """Align one pair through the production path and record its evidence."""
    pairs_root = require_managed_immediate_child(output_dir, output_dir / "pairs")
    pair_root = require_managed_immediate_child(pairs_root, pairs_root / pair.pair_id)
    started = time.monotonic()
    prep = await _prepare_pair(pair, pair_root, loader)
    ctx = RunContext(
        config=prep.config,
        workspace=prep.workspace,
        reference=prep.clips[0],
        comparisons=prep.clips[1:],
        analysis_selection_domain=prep.analysis_selection_domain,
        selection_window=prep.selection_window,
        analysis_clip=prep.analysis_clip,
    )
    phase = await run_align_phase(
        ctx,
        selected_frames=[],
        vs_loader=loader,
        quiet=True,
    )
    (comparison,) = phase.comparisons
    elapsed = time.monotonic() - started
    attempt = comparison.audio_attempt
    if attempt is None:
        raise RuntimeError(f"production result for {pair.pair_id} omitted its attempt")
    review = build_audio_review_presentation(attempt)
    applied_frame = (
        None if comparison.alignment is None else comparison.alignment.relative_offset_frames
    )
    applied = comparison.alignment is not None
    return {
        "pair_id": pair.pair_id,
        "category": pair.category,
        "expected_frame": pair.expected_frame,
        "expected_automatic": pair.expected_automatic,
        "reference": pair.reference.name,
        "comparison": pair.comparison.name,
        "reference_active_rect": _active_rect_payload(prep.clips[0].active_rect),
        "comparison_active_rect": _active_rect_payload(prep.clips[1].active_rect),
        "selected_streams": [asdict(stream) for stream in attempt.selected_streams],
        "x_subframe": attempt.audio.subframe_estimate,
        "r_audio_rounded": attempt.audio.rounded_frame,
        "c_video_confirmed": attempt.video_check.confirmed_offset,
        "applied_frame": applied_frame,
        "state": attempt.decision.state,
        "primary_reason": attempt.decision.primary_reason,
        "reasons": list(review.reasons),
        "video_wins": review.video_wins,
        "video_margin": review.video_margin,
        "target_count": len(attempt.video_check.targets),
        "elapsed_seconds": elapsed,
        "outcome": classify_outcome(
            expected_frame=pair.expected_frame,
            expected_automatic=pair.expected_automatic,
            applied=applied,
            frame_offset=applied_frame,
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


async def run_benchmark(labels: Path, output: Path) -> bool:
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
        refused, eligible = refusal_counts(records)
        print(f"refusal_rate={rate:.2f} ({refused}/{eligible} same-content pairs)", flush=True)
    payload = {
        "pairs": records,
        "summary": {
            "counts": summary_counts,
            "refusal_rate": rate,
            "passed": benchmark_passed(records),
        },
        "total_elapsed_seconds": time.monotonic() - started,
    }
    write_text_atomic(
        output / "pair-results.json",
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return benchmark_passed(records)


def main() -> None:
    """Parse ``--labels`` and ``--output`` and run the benchmark."""
    parser = argparse.ArgumentParser(
        description="Align every labelled pair through the production path."
    )
    parser.add_argument("--labels", type=Path, required=True, help="Label file to run.")
    parser.add_argument("--output", type=Path, required=True, help="Directory for JSON output.")
    args = parser.parse_args()
    if not asyncio.run(run_benchmark(labels=args.labels, output=args.output)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
