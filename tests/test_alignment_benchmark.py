"""Pure-logic tests for the production alignment benchmark tool."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_script() -> ModuleType:
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "alignment_benchmark.py"
    name = f"alignment_benchmark_test_{id(path)}_{len(sys.modules)}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("expected_frame", "expected_automatic", "applied", "frame_offset", "state", "outcome"),
    [
        pytest.param(
            147, "applied", True, 147, "trusted_automatic", "correct_applied", id="applied-truth"
        ),
        pytest.param(
            0, "applied", True, 0, "trusted_automatic", "correct_applied", id="applied-zero"
        ),
        pytest.param(
            147, "applied", True, 146, "trusted_automatic", "wrong_applied", id="applied-wrong"
        ),
        pytest.param(147, "applied", False, None, "provisional", "provisional", id="provisional"),
        pytest.param(147, "applied", False, None, "unavailable", "unavailable", id="unavailable"),
        pytest.param(
            0,
            "not_applied",
            False,
            None,
            "unavailable",
            "unavailable",
            id="visual-withhold-unavailable",
        ),
        pytest.param(
            0,
            "not_applied",
            False,
            None,
            "provisional",
            "correctly_withheld",
            id="withheld-visual-truth",
        ),
        pytest.param(
            None,
            "not_applied",
            False,
            None,
            "unavailable",
            "correctly_withheld",
            id="withheld-control",
        ),
        pytest.param(
            None, "not_applied", True, 0, "trusted_automatic", "wrong_applied", id="control-applied"
        ),
    ],
)
def test_classify_outcome(
    expected_frame: int | None,
    expected_automatic: Any,
    applied: bool,
    frame_offset: int | None,
    state: str,
    outcome: str,
) -> None:
    script = _load_script()

    assert (
        script.classify_outcome(
            expected_frame=expected_frame,
            expected_automatic=expected_automatic,
            applied=applied,
            frame_offset=frame_offset,
            state=state,
        )
        == outcome
    )


def test_refusal_rate_counts_same_content_pairs_only() -> None:
    script = _load_script()
    records: list[dict[str, Any]] = [
        {"outcome": "correct_applied", "expected_automatic": "applied"},
        {"outcome": "correct_applied", "expected_automatic": "applied"},
        {"outcome": "provisional", "expected_automatic": "applied"},
        {"outcome": "unavailable", "expected_automatic": "applied"},
        {"outcome": "correctly_withheld", "expected_automatic": "not_applied"},
        {"outcome": "correctly_withheld", "expected_automatic": "not_applied"},
    ]

    assert script.refusal_rate(records) == pytest.approx(0.5)
    assert script.refusal_counts(records) == (2, 4)


def test_refusal_rate_without_eligible_pairs_is_none() -> None:
    script = _load_script()

    assert (
        script.refusal_rate(
            [{"outcome": "correctly_withheld", "expected_automatic": "not_applied"}]
        )
        is None
    )


@pytest.mark.parametrize(
    ("outcomes", "passed"),
    [
        (["correct_applied", "correctly_withheld"], True),
        (["correct_applied", "wrong_applied"], False),
        (["correct_applied", "provisional"], False),
        (["correct_applied", "unavailable"], False),
    ],
)
def test_benchmark_passed_requires_every_labelled_outcome(
    outcomes: list[str], passed: bool
) -> None:
    script = _load_script()

    assert script.benchmark_passed([{"outcome": outcome} for outcome in outcomes]) is passed


def test_load_labels_keeps_visual_truth_separate_from_automatic_outcome(
    tmp_path: Path,
) -> None:
    script = _load_script()
    (tmp_path / "reference.mkv").touch()
    (tmp_path / "comparison.mkv").touch()
    labels = tmp_path / "labels.json"
    labels.write_text(
        """{
          "pairs": [{
            "id": "delay-1",
            "category": "container_delay",
            "reference": "reference.mkv",
            "comparison": "comparison.mkv",
            "expected_frame": 0,
            "expected_automatic": "not_applied",
            "active_rect_detection": "auto",
            "reference_stream": 1,
            "comparison_stream": 0,
            "video_check_positions": 24
          }]
        }""",
        encoding="utf-8",
    )

    (pair,) = script.load_labels(labels)

    assert pair.expected_frame == 0
    assert pair.expected_automatic == "not_applied"
    assert pair.active_rect_detection.value == "auto"
    assert pair.reference_stream == 1
    assert pair.comparison_stream == 0
    assert pair.video_check_positions == 24


def test_pair_config_uses_production_fps_and_stream_settings(tmp_path: Path) -> None:
    script = _load_script()
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.touch()
    comparison.touch()
    pair = script.LabelledPair(
        pair_id="speed-1",
        category="speed_change",
        reference=reference,
        comparison=comparison,
        expected_frame=692,
        expected_automatic="applied",
        active_rect_detection=script.ScreenshotActiveRectDetection.AUTO,
        reference_stream=1,
        comparison_stream=0,
        video_check_positions=24,
    )

    config = script._pair_config(pair, "01-comparison")

    assert 'match_fps = "assume_reference"' in config
    assert 'active_rect_detection = "auto"' in config
    assert "reference_stream = 1" in config
    assert 'comparison_streams = { "01-comparison" = 0 }' in config
    assert "video_check_positions = 24" in config


@pytest.mark.parametrize("value", [True, 5, 49, "24"])
def test_load_labels_rejects_invalid_video_check_positions(tmp_path: Path, value: object) -> None:
    script = _load_script()
    (tmp_path / "reference.mkv").touch()
    (tmp_path / "comparison.mkv").touch()
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "id": "pair",
                        "category": "test",
                        "reference": "reference.mkv",
                        "comparison": "comparison.mkv",
                        "expected_frame": 0,
                        "expected_automatic": "applied",
                        "video_check_positions": value,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="video_check_positions"):
        script.load_labels(labels)


def test_media_link_rerun_accepts_same_target_and_rejects_stale_target(tmp_path: Path) -> None:
    script = _load_script()
    target = tmp_path / "target.mkv"
    stale = tmp_path / "stale.mkv"
    link = tmp_path / "workspace" / "reference.mkv"
    target.touch()
    stale.touch()
    link.parent.mkdir()
    link.symlink_to(target)

    script._ensure_media_link(link, target)

    with pytest.raises(RuntimeError, match="already exists"):
        script._ensure_media_link(link, stale)


def test_main_exits_nonzero_when_benchmark_gate_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = _load_script()

    async def fail_benchmark(*_args: object, **_kwargs: object) -> bool:
        return False

    monkeypatch.setattr(script, "run_benchmark", fail_benchmark)
    monkeypatch.setattr(
        sys,
        "argv",
        ["alignment_benchmark.py", "--labels", str(tmp_path), "--output", str(tmp_path)],
    )

    with pytest.raises(SystemExit) as exc_info:
        script.main()

    assert exc_info.value.code == 1
