"""Pure-logic tests for the production alignment benchmark tool."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from frame_compare.errors import PathEscapesRootError


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


def _labelled_pair(script: ModuleType, tmp_path: Path, *, pair_id: str = "pair-1") -> Any:
    reference = tmp_path / "source-a.mkv"
    comparison = tmp_path / "source-b.mkv"
    reference.touch(exist_ok=True)
    comparison.touch(exist_ok=True)
    return script.LabelledPair(
        pair_id=pair_id,
        category="synthetic",
        reference=reference,
        comparison=comparison,
        expected_frame=0,
        expected_automatic="applied",
    )


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
            attempt_status="complete",
            collection_failure=None,
            decision_reason="audio_video_confirmed",
        )
        == outcome
    )


@pytest.mark.parametrize(
    ("attempt_status", "collection_failure", "decision_reason"),
    [
        pytest.param("aborted", object(), "no_usable_audio", id="aborted-decode"),
        pytest.param("complete", object(), "no_usable_audio", id="timeout"),
        pytest.param("complete", None, "video_check_unavailable", id="video-check-unavailable"),
    ],
)
def test_classify_outcome_rejects_operational_failures(
    attempt_status: str, collection_failure: object | None, decision_reason: str
) -> None:
    script = _load_script()

    assert (
        script.classify_outcome(
            expected_frame=None,
            expected_automatic="not_applied",
            applied=False,
            frame_offset=None,
            state="unavailable",
            attempt_status=attempt_status,
            collection_failure=collection_failure,
            decision_reason=decision_reason,
        )
        == "unavailable"
    )


def test_classify_outcome_keeps_completed_inconclusive_control_valid() -> None:
    script = _load_script()

    assert (
        script.classify_outcome(
            expected_frame=None,
            expected_automatic="not_applied",
            applied=False,
            frame_offset=None,
            state="unavailable",
            attempt_status="complete",
            collection_failure=None,
            decision_reason="video_check_inconclusive",
        )
        == "correctly_withheld"
    )


@pytest.mark.parametrize(
    ("records", "expected_rate", "expected_counts"),
    [
        (
            [
                {"outcome": "correct_applied", "expected_automatic": "applied"},
                {"outcome": "correct_applied", "expected_automatic": "applied"},
                {"outcome": "provisional", "expected_automatic": "applied"},
                {"outcome": "unavailable", "expected_automatic": "applied"},
                {"outcome": "correctly_withheld", "expected_automatic": "not_applied"},
                {"outcome": "correctly_withheld", "expected_automatic": "not_applied"},
            ],
            0.5,
            (2, 4),
        ),
        ([{"outcome": "correctly_withheld", "expected_automatic": "not_applied"}], None, None),
    ],
)
def test_refusal_rate_and_eligible_counts(
    records: list[dict[str, Any]],
    expected_rate: float | None,
    expected_counts: tuple[int, int] | None,
) -> None:
    script = _load_script()
    if expected_rate is None:
        assert script.refusal_rate(records) is None
    else:
        assert script.refusal_rate(records) == pytest.approx(expected_rate)
        assert script.refusal_counts(records) == expected_counts


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
            "expected_automatic": "not_applied"
          }]
        }""",
        encoding="utf-8",
    )

    (pair,) = script.load_labels(labels)

    assert pair.pair_id == "delay-1"
    assert pair.expected_frame == 0
    assert pair.expected_automatic == "not_applied"


@pytest.mark.parametrize(
    "pair_id",
    (
        "../pair-1",
        "/pair-1",
        "group/pair-1",
        r"..\pair-1",
        r"C:\pair-1",
        r"group\pair-1",
    ),
)
async def test_path_like_pair_ids_are_rejected_before_output_creation(
    tmp_path: Path, pair_id: str
) -> None:
    script = _load_script()
    (tmp_path / "source-a.mkv").touch()
    (tmp_path / "source-b.mkv").touch()
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "id": pair_id,
                        "category": "synthetic",
                        "reference": "source-a.mkv",
                        "comparison": "source-b.mkv",
                        "expected_frame": 0,
                        "expected_automatic": "applied",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"

    with pytest.raises(ValueError, match="single path-free name"):
        await script.run_benchmark(labels, output)

    assert not output.exists()


@pytest.mark.parametrize(
    ("redirect_name", "parts"),
    (
        ("pairs", ("pairs",)),
        ("pair", ("pairs", "pair-1")),
        ("workspace", ("pairs", "pair-1", "workspace")),
        ("input", ("pairs", "pair-1", "workspace", "comparison_videos")),
        ("config", ("pairs", "pair-1", "workspace", "config")),
        ("generated", ("pairs", "pair-1", "workspace", "generated")),
    ),
)
async def test_redirected_benchmark_directories_cannot_escape_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    redirect_name: str,
    parts: tuple[str, ...],
) -> None:
    script = _load_script()
    pair = _labelled_pair(script, tmp_path)
    output = tmp_path / "output"
    outside = tmp_path / f"outside-{redirect_name}"
    outside.mkdir()
    redirected = output.joinpath(*parts)
    redirected.parent.mkdir(parents=True, exist_ok=True)
    redirected.symlink_to(outside, target_is_directory=True)

    async def unexpected_preparation(*_args: object, **_kwargs: object) -> None:
        pytest.fail("production preparation must not run")

    monkeypatch.setattr(script.preparation, "execute_prep", unexpected_preparation)

    with pytest.raises(PathEscapesRootError):
        await script.align_pair(pair, output, object())

    assert list(outside.iterdir()) == []


async def test_config_write_replaces_symlink_without_touching_referent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = _load_script()
    pair = _labelled_pair(script, tmp_path)
    pair_root = tmp_path / "output" / "pairs" / pair.pair_id
    config_dir = pair_root / "workspace" / "config"
    config_dir.mkdir(parents=True)
    outside_config = tmp_path / "outside-config.toml"
    outside_config.write_text("unchanged", encoding="utf-8")
    config_file = config_dir / "config.toml"
    config_file.symlink_to(outside_config)
    prepared = object()

    async def execute_prep(*_args: object, **_kwargs: object) -> object:
        return prepared

    monkeypatch.setattr(script.preparation, "execute_prep", execute_prep)

    result = await script._prepare_pair(pair, pair_root, object())

    assert result is prepared
    assert not config_file.is_symlink()
    assert config_file.read_text(encoding="utf-8").startswith("[paths]")
    assert outside_config.read_text(encoding="utf-8") == "unchanged"


async def test_relative_label_media_paths_are_canonicalized_before_nested_symlinks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = _load_script()
    fixture_root = tmp_path / "fixture root with spaces"
    labels_dir = fixture_root / "label set"
    reference = fixture_root / "reference clip.mkv"
    comparison = fixture_root / "comparison clip.mkv"
    labels = labels_dir / "labels.json"
    labels_dir.mkdir(parents=True)
    reference.touch()
    comparison.touch()
    labels.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "id": "pair-1",
                        "category": "synthetic",
                        "reference": "../reference clip.mkv",
                        "comparison": str(comparison),
                        "expected_frame": 0,
                        "expected_automatic": "applied",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    (pair,) = script.load_labels(Path("fixture root with spaces/label set/labels.json"))

    assert pair.reference == reference.resolve()
    assert pair.comparison == comparison.resolve()
    pair_root = Path("benchmark output") / "pairs" / pair.pair_id
    prepared = object()

    async def execute_prep(*_args: object, **_kwargs: object) -> object:
        return prepared

    monkeypatch.setattr(script.preparation, "execute_prep", execute_prep)

    result = await script._prepare_pair(pair, pair_root, object())

    assert result is prepared
    assert (pair_root / "workspace" / "comparison_videos" / "00-reference.mkv").resolve() == (
        reference.resolve()
    )
    assert (pair_root / "workspace" / "comparison_videos" / "01-comparison.mkv").resolve() == (
        comparison.resolve()
    )


async def test_results_write_replaces_symlink_without_touching_referent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = _load_script()
    pair = _labelled_pair(script, tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    outside_results = tmp_path / "outside-results.json"
    outside_results.write_text("unchanged", encoding="utf-8")
    results_file = output / "pair-results.json"
    results_file.symlink_to(outside_results)
    record: dict[str, object] = {
        "pair_id": pair.pair_id,
        "category": pair.category,
        "expected_frame": 0,
        "expected_automatic": "applied",
        "x_subframe": 0.0,
        "r_audio_rounded": 0,
        "c_video_confirmed": 0,
        "applied_frame": 0,
        "state": "trusted_automatic",
        "primary_reason": "audio_video_confirmed",
        "outcome": "correct_applied",
        "elapsed_seconds": 0.0,
    }

    async def align_pair(*_args: object, **_kwargs: object) -> dict[str, object]:
        return record

    monkeypatch.setattr(script, "load_labels", lambda _path: [pair])
    monkeypatch.setattr(script, "DefaultVSLoader", lambda **_kwargs: object())
    monkeypatch.setattr(script, "align_pair", align_pair)

    assert await script.run_benchmark(tmp_path / "labels.json", output) is True
    assert not results_file.is_symlink()
    assert json.loads(results_file.read_text(encoding="utf-8"))["summary"]["passed"] is True
    assert outside_results.read_text(encoding="utf-8") == "unchanged"


async def test_align_pair_refuses_stale_prepared_source_before_measurement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = _load_script()
    pair = _labelled_pair(script, tmp_path)
    pair.reference.write_bytes(b"reference bytes")
    pair.comparison.write_bytes(b"comparison bytes")
    stale_reference = tmp_path / "source-a.stale.mkv"
    stale_reference.write_bytes(b"stale bytes")
    prepared = SimpleNamespace(
        clips=[
            SimpleNamespace(path=stale_reference, active_rect=None),
            SimpleNamespace(path=pair.comparison, active_rect=None),
        ],
        config=object(),
        workspace=object(),
        selection_domain=object(),
    )

    async def prepare(*_args: object, **_kwargs: object) -> object:
        return prepared

    async def unexpected_measurement(*_args: object, **_kwargs: object) -> object:
        pytest.fail("stale prepared source must be rejected before measurement")

    monkeypatch.setattr(script, "_prepare_pair", prepare)
    monkeypatch.setattr(script, "run_align_phase", unexpected_measurement)

    with pytest.raises(RuntimeError, match="prepared source order"):
        await script.align_pair(pair, tmp_path / "output", object())

    assert pair.reference.read_bytes() == b"reference bytes"
    assert pair.comparison.read_bytes() == b"comparison bytes"


def test_pair_config_uses_production_fps_at_pure_defaults(tmp_path: Path) -> None:
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
    )

    config = script._pair_config(pair)

    assert 'match_fps = "assume_reference"' in config
    assert "active_rect_detection" not in config
    assert "reference_stream" not in config
    assert "comparison_streams" not in config
    assert "max_offset_seconds = 30.0" in config


def test_summary_row_excludes_media_fields(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script()
    record = {
        "pair_id": "pair-7",
        "category": "synthetic",
        "reference": "REFERENCE_PRIVATE_SENTINEL",
        "comparison": "COMPARISON_PRIVATE_SENTINEL",
        "expected_frame": 12,
        "x_subframe": 12.25,
        "r_audio_rounded": 12,
        "c_video_confirmed": 12,
        "applied_frame": 12,
        "state": "trusted_automatic",
        "primary_reason": "audio_video_confirmed",
        "outcome": "correct_applied",
        "elapsed_seconds": 1.25,
    }

    script._print_table_row(record)

    summary = capsys.readouterr().out
    assert "pair-7" in summary
    assert "synthetic" in summary
    assert "correct_applied" in summary
    assert "REFERENCE_PRIVATE_SENTINEL" not in summary
    assert "COMPARISON_PRIVATE_SENTINEL" not in summary


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


def test_main_exits_nonzero_for_production_failed_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = _load_script()
    reference = tmp_path / "reference.mkv"
    comparison = tmp_path / "comparison.mkv"
    reference.write_bytes(b"reference")
    comparison.write_bytes(b"comparison")
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "id": "failed-1",
                        "category": "synthetic",
                        "reference": reference.name,
                        "comparison": comparison.name,
                        "expected_automatic": "not_applied",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"

    async def prepare(pair: Any, *_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(
            clips=[
                SimpleNamespace(path=pair.reference, active_rect=None),
                SimpleNamespace(path=pair.comparison, active_rect=None),
            ],
            config=object(),
            workspace=object(),
            selection_domain=object(),
        )

    attempt = SimpleNamespace(
        status="aborted",
        collection_failure=SimpleNamespace(category="nonzero_exit"),
        selected_streams=[],
        audio=SimpleNamespace(subframe_estimate=None, rounded_frame=None),
        video_check=SimpleNamespace(confirmed_offset=None, targets=[]),
        decision=SimpleNamespace(state="unavailable", primary_reason="no_usable_audio"),
    )

    async def align(*_args: object, **_kwargs: object) -> object:
        return SimpleNamespace(comparisons=[SimpleNamespace(audio_attempt=attempt, alignment=None)])

    monkeypatch.setattr(script, "_prepare_pair", prepare)
    monkeypatch.setattr(script, "run_align_phase", align)
    monkeypatch.setattr(
        script,
        "build_audio_review_presentation",
        lambda _attempt: SimpleNamespace(reasons=(), video_wins=(), video_margin=None),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["alignment_benchmark.py", "--labels", str(labels), "--output", str(output)],
    )

    with pytest.raises(SystemExit) as exc_info:
        script.main()

    assert exc_info.value.code == 1
    result = json.loads((output / "pair-results.json").read_text(encoding="utf-8"))
    record = result["pairs"][0]
    assert record["attempt_status"] == "aborted"
    assert record["failure_reason"] == "nonzero_exit"
    assert record["outcome"] == "unavailable"
    assert result["summary"]["passed"] is False
