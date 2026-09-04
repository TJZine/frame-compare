"""Focused tests for the VSView adapter and generated session contract."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from frame_compare.vs.source import source_index_path
from frame_compare.vsview.adapter import (
    VSViewAvailabilityStatus,
    VSViewConfig,
    VSViewSessionRequest,
    _build_vsview_child_env,
    _check_startup_readiness,
    _run_vsview_command,
    check_vsview_availability,
    launch_alignment_verification_session,
)
from frame_compare.vsview.alignment_review_contract import AlignmentReviewContractError
from frame_compare.vsview.errors import VSViewError
from frame_compare.vsview.session_script import (
    _build_script_content,
    _build_script_header,
    write_vsview_session_script,
)


def _session_request(tmp_path: Path) -> VSViewSessionRequest:
    return VSViewSessionRequest(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comparison.mkv"],
        suggested_offsets_by_key={"ref:comparison": 4},
        cache_dir=tmp_path,
    )


def _mock_available_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.importlib.util.find_spec",
        lambda _name: object(),
    )
    entry_point = SimpleNamespace(
        name="frame-compare-alignment-review",
        value="frame_compare.vsview.alignment_review_panel",
    )
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.importlib.metadata.entry_points",
        lambda **_kwargs: [entry_point],
    )


def test_child_environment_isolated_and_preserves_warning_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONWARNINGS", "error::ResourceWarning")
    monkeypatch.delenv("NO_COLOR", raising=False)
    parent_env = os.environ.copy()

    child_env = _build_vsview_child_env(no_color=True)

    assert child_env["PYTHONWARNINGS"] == "error::ResourceWarning"
    assert child_env["NO_COLOR"] == "1"
    assert os.environ == parent_env


@pytest.mark.parametrize(
    ("modules", "has_plugin", "expected"),
    [
        (frozenset({"vsview", "PySide6"}), True, VSViewAvailabilityStatus.AVAILABLE),
        (frozenset({"vsview", "PySide6"}), False, VSViewAvailabilityStatus.MISSING_PLUGIN),
        (frozenset({"vsview"}), True, VSViewAvailabilityStatus.MISSING_RUNTIME),
        (frozenset(), True, VSViewAvailabilityStatus.MISSING_RUNTIME),
    ],
)
def test_check_vsview_availability_requires_same_environment_panel(
    monkeypatch: pytest.MonkeyPatch,
    modules: frozenset[str],
    has_plugin: bool,
    expected: VSViewAvailabilityStatus,
) -> None:
    calls: list[str] = []

    def fake_find_spec(name: str) -> object | None:
        calls.append(name)
        return object() if name in modules else None

    monkeypatch.setattr("frame_compare.vsview.adapter.importlib.util.find_spec", fake_find_spec)
    entry_point = SimpleNamespace(
        name="frame-compare-alignment-review",
        value="frame_compare.vsview.alignment_review_panel",
    )
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.importlib.metadata.entry_points",
        lambda **_kwargs: [entry_point] if has_plugin else [],
    )

    result = check_vsview_availability()

    assert result.status is expected
    assert result.is_available is (expected is VSViewAvailabilityStatus.AVAILABLE)
    assert calls == ["vsview", "PySide6"]


def test_check_vsview_availability_redacts_probe_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.importlib.util.find_spec",
        MagicMock(side_effect=ValueError("private details")),
    )

    result = check_vsview_availability()

    assert result.status is VSViewAvailabilityStatus.PROBE_FAILED
    assert result.public_probe_failure_details() == {"exception_type": "ValueError"}
    assert result.public_probe_failure_reason() == "availability probe failed (ValueError)"
    assert "private details" not in result.public_probe_failure_reason()


def test_startup_readiness_probes_pyside6_vsview_and_output_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr("frame_compare.vsview.adapter.subprocess.run", mock_run)

    _check_startup_readiness([sys.executable, "-m", "vsview", "session.py"], env={})

    mock_run.assert_called_once()
    probe_code = mock_run.call_args.args[0][2]
    assert "import PySide6" in probe_code
    assert "import vsview" in probe_code
    assert "from vsview import set_output" in probe_code
    assert "frame-compare-alignment-review" in probe_code
    assert "eps[0].load()" in probe_code
    assert "raise RuntimeError" in probe_code
    assert "compat" not in probe_code
    assert mock_run.call_args.kwargs["cwd"] == Path(sys.executable).resolve().parent


def test_managed_launcher_ignores_modules_from_calling_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile_workspace = tmp_path / "hostile-workspace"
    hostile_workspace.mkdir()
    marker = tmp_path / "hostile-launch-module-imported"
    (hostile_workspace / "child_cwd_probe.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n",
        encoding="utf-8",
    )
    safe_module_root = tmp_path / "safe-module-root"
    safe_module_root.mkdir()
    (safe_module_root / "child_cwd_probe.py").write_text("pass\n", encoding="utf-8")
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = str(safe_module_root)
    monkeypatch.chdir(hostile_workspace)

    returncode = _run_vsview_command(
        [sys.executable, "-m", "child_cwd_probe"],
        env=child_env,
    )

    assert returncode == 0
    assert not marker.exists()


def test_launch_rejects_missing_panel_entry_point(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_available_runtime(monkeypatch)
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.subprocess.run",
        MagicMock(
            return_value=subprocess.CompletedProcess(
                [],
                1,
                "",
                "RuntimeError: Frame Compare alignment panel entry point is unavailable",
            )
        ),
    )
    popen = MagicMock()
    monkeypatch.setattr("frame_compare.vsview.adapter.subprocess.Popen", popen)

    with pytest.raises(VSViewError) as excinfo:
        launch_alignment_verification_session(
            _session_request(tmp_path),
            VSViewConfig(enabled=True),
        )

    assert excinfo.value.public_reason == "VSView failed its startup dependency check."
    assert "entry point is unavailable" in (excinfo.value.startup_stderr or "")
    popen.assert_not_called()


def test_windows_startup_readiness_preloads_before_vsview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr("frame_compare.vsview.adapter.subprocess.run", mock_run)
    monkeypatch.setattr("frame_compare.vsview.adapter.runtime_kind", lambda: "windows-portable")

    _check_startup_readiness([sys.executable, "-m", "vsview", "session.py"], env={})

    probe_code = mock_run.call_args.args[0][2]
    assert probe_code.index("preload_vapoursynth_runtime()") < probe_code.index("import PySide6")


def test_startup_failure_is_bounded_redacted_and_prevents_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "timeout-secret-token"
    monkeypatch.setenv("FRAME_COMPARE_SECRET", secret)
    _mock_available_runtime(monkeypatch)
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.subprocess.run",
        MagicMock(
            side_effect=subprocess.TimeoutExpired(
                [sys.executable], 10.0, stderr=f"waiting with {secret}".encode()
            )
        ),
    )
    popen = MagicMock()
    monkeypatch.setattr("frame_compare.vsview.adapter.subprocess.Popen", popen)

    with pytest.raises(VSViewError) as excinfo:
        launch_alignment_verification_session(
            _session_request(tmp_path),
            VSViewConfig(enabled=True),
        )

    assert excinfo.value.public_reason == "startup dependency check timed out"
    assert excinfo.value.startup_stderr == "waiting with <redacted>"
    popen.assert_not_called()


def test_launch_uses_managed_launcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_available_runtime(monkeypatch)
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.subprocess.run",
        MagicMock(return_value=subprocess.CompletedProcess([], 0, "", "")),
    )
    process = MagicMock()
    process.__enter__.return_value = process
    process.wait.return_value = 0
    popen = MagicMock(return_value=process)
    monkeypatch.setattr("frame_compare.vsview.adapter.subprocess.Popen", popen)

    session = launch_alignment_verification_session(
        _session_request(tmp_path),
        VSViewConfig(enabled=True),
    )

    assert popen.call_args.args[0] == [
        sys.executable,
        "-m",
        "frame_compare.vsview.launcher",
        str(session.script_path),
    ]


def test_disabled_launch_writes_vsview_named_session_without_starting_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    availability = MagicMock(side_effect=AssertionError("disabled launch must not probe"))
    monkeypatch.setattr("frame_compare.vsview.adapter.check_vsview_availability", availability)

    session = launch_alignment_verification_session(
        _session_request(tmp_path),
        VSViewConfig(enabled=False),
    )

    assert session.script_path.parent == tmp_path / "vsview_sessions"
    assert session.script_path.name.startswith("vsview_ref_")
    assert session.result_path.name.endswith(".alignment-result.json")
    script = session.script_path.read_text(encoding="utf-8")
    assert "from vsview import set_output" in script
    assert "**_reference_metadata(" in script
    assert "**_comparison_metadata(" in script


def test_session_setup_contract_failure_raises_typed_vsview_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_failure = AlignmentReviewContractError("invalid VSView session script filename")
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.alignment_review_session_from_script",
        MagicMock(side_effect=contract_failure),
    )

    with pytest.raises(VSViewError, match="VSView session setup failed") as excinfo:
        launch_alignment_verification_session(
            _session_request(tmp_path),
            VSViewConfig(enabled=False),
        )

    assert excinfo.value.__cause__ is contract_failure


def test_launch_timeout_terminates_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_available_runtime(monkeypatch)
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.subprocess.run",
        MagicMock(return_value=subprocess.CompletedProcess([], 0, "", "")),
    )
    process = MagicMock()
    process.__enter__.return_value = process
    process.wait.side_effect = [subprocess.TimeoutExpired(["vsview"], 1), 0]
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.subprocess.Popen", MagicMock(return_value=process)
    )

    with pytest.raises(VSViewError, match="timed out"):
        launch_alignment_verification_session(
            _session_request(tmp_path),
            VSViewConfig(enabled=True),
        )

    process.terminate.assert_called_once_with()
    process.kill.assert_not_called()


def _execute_generated_script(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    comparison_stems: tuple[str, ...],
    suggested_offsets_by_key: dict[str, int | None],
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
    presentation_names_by_stem: dict[str, str] | None = None,
    unusable_index_stems: set[str] | None = None,
    cache_free_failure_stems: set[str] | None = None,
    output_sink: list[tuple[str, int, str]] | None = None,
) -> tuple[
    list[tuple[str, int, str]],
    list[dict[str, object]],
    dict[str, dict[str, int]],
    list[tuple[str, str | None, int | None]],
]:
    reference = tmp_path / "ref.mkv"
    comparisons = [tmp_path / f"{stem}.mkv" for stem in comparison_stems]
    reference.touch()
    for comparison in comparisons:
        comparison.touch()

    output_calls = output_sink if output_sink is not None else []
    output_metadata: list[dict[str, object]] = []
    applied_props: dict[str, dict[str, int]] = {}
    loader_calls: list[tuple[str, str | None, int | None]] = []
    default_props: dict[str, dict[str, str | int | float]] = {
        stem: {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1, "_Range": 0}
        for stem in ("ref", *comparison_stems)
    }
    default_props.update(frame_props_by_stem or {})
    rejected_indexes = unusable_index_stems or set()
    rejected_cache_free = cache_free_failure_stems or set()

    class FakeClip:
        def __init__(self, stem: str) -> None:
            self.stem = stem
            self.fps = SimpleNamespace(numerator=24, denominator=1)

    clips = {stem: FakeClip(stem) for stem in ("ref", *comparison_stems)}

    class FakeLsmas:
        def LWLibavSource(
            self,
            path: str,
            *,
            cachefile: str | None = None,
            cache: int | None = None,
        ) -> FakeClip:
            stem = Path(path).stem
            loader_calls.append((stem, cachefile, cache))
            if cachefile is not None and stem in rejected_indexes:
                raise RuntimeError("failed to construct index")
            if cache == 0 and stem in rejected_cache_free:
                raise RuntimeError("cache-free fallback failed")
            return clips[stem]

    class FakeText:
        def Text(self, clip: FakeClip, _text: str, *, alignment: int) -> FakeClip:
            assert alignment == 7
            return clip

    class FakeStd:
        def AssumeFPS(self, clip: FakeClip, *, fpsnum: int, fpsden: int) -> FakeClip:
            assert (fpsnum, fpsden) == (24, 1)
            return clip

        def SetFrameProps(self, clip: FakeClip, **props: int) -> FakeClip:
            applied_props[clip.stem] = props
            return clip

    core = SimpleNamespace(lsmas=FakeLsmas(), text=FakeText(), std=FakeStd())
    fake_vapoursynth = types.ModuleType("vapoursynth")
    fake_vapoursynth.core = core  # pyright: ignore[reportAttributeAccessIssue]
    fake_vsview = types.ModuleType("vsview")

    def set_output(clip: FakeClip, index: int, name: str, **kwargs: object) -> None:
        output_calls.append((clip.stem, index, name))
        output_metadata.append(kwargs)

    fake_vsview.set_output = set_output  # pyright: ignore[reportAttributeAccessIssue]
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vapoursynth)
    monkeypatch.setitem(sys.modules, "vsview", fake_vsview)

    script = _build_script_content(
        reference=reference,
        comparisons=comparisons,
        suggested_offsets_by_key=suggested_offsets_by_key,
        bootstrap_paths=[tmp_path],
        frame_props_by_stem=default_props,
        presentation_names_by_stem=presentation_names_by_stem,
    )
    exec(
        compile(script, "<vsview-generated>", "exec"),
        {
            "__name__": "vsview_loaded_script",
            "__file__": str(tmp_path / f"session_{'1' * 32}.py"),
        },
    )
    return output_calls, output_metadata, applied_props, loader_calls


def test_generated_session_registers_named_outputs_in_input_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_calls, output_metadata, _props, loader_calls = _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        comparison_stems=("zeta", "alpha"),
        suggested_offsets_by_key={"ref:zeta": 4, "ref:alpha": None},
    )

    assert output_calls == [
        ("ref", 0, "Reference"),
        ("zeta", 1, "Comparison 1"),
        ("alpha", 2, "Comparison 2"),
    ]
    assert [metadata["frame_compare_output_role"] for metadata in output_metadata] == [
        "reference",
        "comparison",
        "comparison",
    ]
    assert "frame_compare_comparison_ordinal" not in output_metadata[0]
    assert "frame_compare_alignment_key" not in output_metadata[0]
    assert "frame_compare_suggested_offset" not in output_metadata[0]
    assert [metadata["frame_compare_comparison_ordinal"] for metadata in output_metadata[1:]] == [
        1,
        2,
    ]
    assert {metadata["frame_compare_contract_version"] for metadata in output_metadata} == {1}
    assert {metadata["frame_compare_session_id"] for metadata in output_metadata} == {"1" * 32}
    assert [stem for stem, _cachefile, _cache in loader_calls].count("ref") == 1


def test_generated_session_preserves_lsmash_indexes_and_only_retries_index_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_calls, _metadata, _props, loader_calls = _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        comparison_stems=("a",),
        suggested_offsets_by_key={"ref:a": 0},
        unusable_index_stems={"ref", "a"},
    )

    assert output_calls == [("ref", 0, "Reference"), ("a", 1, "Comparison 1")]
    assert loader_calls == [
        ("ref", str(source_index_path(tmp_path / "ref.mkv")), None),
        ("ref", None, 0),
        ("a", str(source_index_path(tmp_path / "a.mkv")), None),
        ("a", None, 0),
    ]
    assert capsys.readouterr().err.count("without an L-SMASH index cache") == 2


def test_generated_session_load_failure_registers_no_partial_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_calls: list[tuple[str, int, str]] = []

    with pytest.raises(SystemExit) as excinfo:
        _execute_generated_script(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            comparison_stems=("a", "b"),
            suggested_offsets_by_key={"ref:a": 0, "ref:b": 1},
            unusable_index_stems={"b"},
            cache_free_failure_stems={"b"},
            output_sink=output_calls,
        )

    assert excinfo.value.code == 1
    assert output_calls == []


def test_generated_session_keeps_bt709_defaults_and_overlay_hints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_calls, _metadata, applied_props, _loader_calls = _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        comparison_stems=("a",),
        suggested_offsets_by_key={"ref:a": 7},
        frame_props_by_stem={"ref": {"_Matrix": 2, "_Transfer": 2, "_Primaries": 2}},
    )

    assert output_calls == [("ref", 0, "Reference"), ("a", 1, "Comparison 1")]
    assert applied_props["ref"] == {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1}


def test_generated_script_suppresses_only_redundant_vsview_load_success() -> None:
    logger = logging.getLogger("vsview.app.workspace.loader")
    existing_filters = tuple(logger.filters)
    namespace: dict[str, object] = {}
    exec(_build_script_header(), namespace)  # noqa: S102
    added_filters = [item for item in logger.filters if item not in existing_filters]

    try:
        assert len(added_filters) == 1
        cases = (
            (logging.INFO, "Content loaded successfully: %r", False),
            (logging.INFO, "Content reloaded successfully: %r", True),
            (logging.ERROR, "Failed to load content: %r", True),
        )
        for level, message, expected in cases:
            record = logging.LogRecord(logger.name, level, "loader.py", 1, message, (), None)
            assert bool(logger.filter(record)) is expected
    finally:
        for item in added_filters:
            logger.removeFilter(item)


def test_generated_session_guides_panel_discovery_and_unlinked_playheads(
    tmp_path: Path,
) -> None:
    generated = _build_script_content(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "a.mkv"],
        suggested_offsets_by_key={"ref:a": 0},
        bootstrap_paths=[tmp_path],
    )

    assert generated.count("Open Tool Panel -> Frame Compare Alignment Review.") == 3
    assert generated.count("Unlink playheads") == 3
    assert "       Open Tool Panel -> Frame Compare Alignment Review." in generated
    assert "       Save the alignment in the panel" in generated


def test_write_vsview_session_script_is_atomic_and_deterministic_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []

    def fake_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        calls.append(path)
        path.write_text(content, encoding=encoding)

    monkeypatch.setattr("frame_compare.vsview.session_script.write_text_atomic", fake_write)
    first = write_vsview_session_script(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={"ref:a": 1},
        cache_dir=tmp_path,
    )
    second = write_vsview_session_script(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={"ref:a": 1},
        cache_dir=tmp_path,
    )

    assert calls == [first, second]
    assert first.parent.name == "vsview_sessions"
    assert first.name.startswith("vsview_ref_")
    assert re.fullmatch(r"vsview_ref_\d{8}T\d{6}Z_[0-9a-f]{32}\.py", first.name)
    assert re.fullmatch(r"vsview_ref_\d{8}T\d{6}Z_[0-9a-f]{32}\.py", second.name)
    assert first != second
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


def test_write_vsview_session_script_retries_uuid_path_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_ids = iter(("1" * 32, "2" * 32))
    attempts: list[Path] = []

    monkeypatch.setattr(
        "frame_compare.vsview.session_script.uuid.uuid4",
        lambda: SimpleNamespace(hex=next(session_ids)),
    )

    def reserve(path: Path) -> bool:
        attempts.append(path)
        if len(attempts) == 1:
            return False
        path.touch(exist_ok=False)
        return True

    monkeypatch.setattr("frame_compare.vsview.session_script._reserve_empty_file", reserve)

    script = write_vsview_session_script(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={"ref:a": 1},
        cache_dir=tmp_path,
    )

    assert len(attempts) == 2
    assert attempts[0].name.endswith(f"_{'1' * 32}.py")
    assert script.name.endswith(f"_{'2' * 32}.py")
