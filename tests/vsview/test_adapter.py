"""Focused tests for the VSView adapter and generated session contract."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import sys
import types
from contextlib import suppress
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
    _run_vsview_command,
    check_vsview_availability,
    launch_alignment_verification_session,
)
from frame_compare.vsview.alignment_review_contract import (
    ALIGNMENT_REVIEW_METADATA_VERSION,
    AlignmentReviewContractError,
)
from frame_compare.vsview.errors import VSViewError
from frame_compare.vsview.session_script import (
    _build_script_content,
    _build_script_header,
    write_vsview_session_script,
)


def _audio_review_map(offsets: dict[str, int | None]) -> dict[str, str]:
    return {
        key: json.dumps(
            {
                "current_authority": {
                    "origin": "shared_computed_offsets" if offset is not None else "none",
                    "frame_offset": offset,
                },
                "evidence_availability": (
                    "historical_details_unavailable" if offset is not None else "not_computed"
                ),
                "audio_attempt": None,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        for key, offset in offsets.items()
    }


def _session_request(tmp_path: Path) -> VSViewSessionRequest:
    return VSViewSessionRequest(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comparison.mkv"],
        suggested_offsets_by_key={"ref:comparison": 4},
        cache_dir=tmp_path,
        audio_review_by_key=_audio_review_map({"ref:comparison": 4}),
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
    monkeypatch.setenv("PYTHONPATH", "/caller/python-path")
    monkeypatch.setenv("PYTHONHOME", "/caller/python-home")
    monkeypatch.setenv("PYTHONSTARTUP", "/caller/startup.py")
    monkeypatch.setenv("PYTHONINSPECT", "1")
    monkeypatch.setenv("PYTHONUSERBASE", "/caller/user-base")
    monkeypatch.delenv("NO_COLOR", raising=False)
    parent_env = os.environ.copy()

    child_env = _build_vsview_child_env(no_color=True)

    assert child_env["PYTHONWARNINGS"] == "error::ResourceWarning"
    assert child_env["PYTHONSAFEPATH"] == "1"
    assert child_env["PYTHONNOUSERSITE"] == "1"
    assert "PYTHONPATH" not in child_env
    assert "PYTHONHOME" not in child_env
    assert "PYTHONSTARTUP" not in child_env
    assert "PYTHONINSPECT" not in child_env
    assert "PYTHONUSERBASE" not in child_env
    assert child_env["NO_COLOR"] == "1"
    assert os.environ == parent_env


def test_windows_portable_child_env_relies_on_managed_embedded_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "windows-portable")
    monkeypatch.setenv("FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT", "managed-fingerprint")
    monkeypatch.setenv("PYTHONPATH", r"C:\bundle\app\src;C:\bundle\app\site-packages")

    child_env = _build_vsview_child_env(no_color=False)

    assert child_env["FRAME_COMPARE_RUNTIME_KIND"] == "windows-portable"
    assert child_env["FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT"] == "managed-fingerprint"
    assert "PYTHONPATH" not in child_env
    build_script = (
        Path(__file__).parents[2] / "tools" / "windows_portable" / "build_portable.ps1"
    ).read_text(encoding="utf-8")
    assert r'"..\\app\\site-packages"' in build_script
    assert r'"..\\app\\src"' in build_script
    assert '"import site"' in build_script


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

    assert result.public_probe_failure_details() == {"exception_type": "ValueError"}
    assert result.public_probe_failure_reason() == "availability probe failed (ValueError)"
    assert "private details" not in result.public_probe_failure_reason()


@pytest.mark.parametrize(
    "python_args",
    [
        ("-c", "import json"),
        ("-m", "json.tool", "--help"),
    ],
)
def test_managed_python_children_ignore_hostile_inherited_python_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    python_args: tuple[str, ...],
) -> None:
    hostile_python_path = tmp_path / "hostile-python-path"
    hostile_python_path.mkdir()
    sitecustomize_marker = tmp_path / "hostile-sitecustomize-imported"
    shadow_marker = tmp_path / "hostile-json-imported"
    (hostile_python_path / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(sitecustomize_marker)!r}).touch()\n",
        encoding="utf-8",
    )
    (hostile_python_path / "json.py").write_text(
        f"from pathlib import Path\nPath({str(shadow_marker)!r}).touch()\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(hostile_python_path))
    child_env = _build_vsview_child_env(no_color=False)

    returncode, _wait_seconds = _run_vsview_command(
        [sys.executable, *python_args],
        env=child_env,
    )

    assert returncode == 0
    assert not sitecustomize_marker.exists()
    assert not shadow_marker.exists()


def test_run_vsview_command_returns_measured_wait_with_fake_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import frame_compare.vsview.adapter as adapter

    clock = iter([100.0, 142.5])
    monkeypatch.setattr(adapter, "monotonic", lambda: next(clock))

    class _FakeProcess:
        def __enter__(self) -> _FakeProcess:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 0

    monkeypatch.setattr(adapter.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())

    returncode, wait_seconds = _run_vsview_command(["vsview"], env={})

    assert returncode == 0
    assert wait_seconds == pytest.approx(42.5)


def test_preloaded_vapoursynth_wins_over_hostile_generated_session_module(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    session = write_vsview_session_script(
        reference=Path("ref.mkv"),
        comparisons=[Path("comparison.mkv")],
        suggested_offsets_by_key={"ref:comparison": 0},
        audio_review_by_key=_audio_review_map({"ref:comparison": 0}),
        cache_dir=workspace / "generated",
    )
    hostile_marker = tmp_path / "hostile-vapoursynth-imported"
    (session.parent / "vapoursynth.py").write_text(
        f"from pathlib import Path\nPath({str(hostile_marker)!r}).touch()\n"
        "raise RuntimeError('hostile VapourSynth shadow loaded')\n",
        encoding="utf-8",
    )

    runtime_dir = tmp_path / "selected-runtime"
    runtime_dir.mkdir()
    safe_marker = tmp_path / "selected-vapoursynth-imported"
    (runtime_dir / "vapoursynth.py").write_text(
        f"from pathlib import Path\nPath({str(safe_marker)!r}).touch()\ncore = object()\n",
        encoding="utf-8",
    )
    source_dir = Path(__file__).parents[2] / "src"
    probe_code = f"""
import sys
sys.path.insert(0, {str(source_dir)!r})
sys.path.insert(0, {str(runtime_dir)!r})
from frame_compare.vsview.launcher import preload_vapoursynth_runtime
preload_vapoursynth_runtime()
sys.path.insert(0, {str(session.parent)!r})
import vapoursynth
assert vapoursynth.__file__ == {str(runtime_dir / "vapoursynth.py")!r}
"""

    result = subprocess.run(  # nosec B603
        [sys.executable, "-c", probe_code],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=10.0,
        env=_build_vsview_child_env(no_color=False),
        cwd=Path(sys.executable).resolve().parent,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert safe_marker.exists()
    assert not hostile_marker.exists()


@pytest.mark.parametrize("timeout", [False, True], ids=["missing-panel", "timeout"])
def test_startup_probe_failure_reports_reason_and_redacted_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timeout: bool
) -> None:
    secret = "timeout-secret-token"
    monkeypatch.setenv("FRAME_COMPARE_SECRET", secret)
    _mock_available_runtime(monkeypatch)
    failure = (
        MagicMock(
            side_effect=subprocess.TimeoutExpired(
                [sys.executable], 10.0, stderr=f"waiting with {secret}".encode()
            )
        )
        if timeout
        else MagicMock(
            return_value=subprocess.CompletedProcess(
                [], 1, "", "RuntimeError: Frame Compare alignment panel entry point is unavailable"
            )
        )
    )
    monkeypatch.setattr("frame_compare.vsview.adapter.subprocess.run", failure)
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.subprocess.Popen",
        MagicMock(side_effect=AssertionError("Failed startup checks must not launch VSView")),
    )
    with pytest.raises(VSViewError) as excinfo:
        launch_alignment_verification_session(
            _session_request(tmp_path), VSViewConfig(enabled=True)
        )
    if timeout:
        assert excinfo.value.public_reason == "startup dependency check timed out"
        assert excinfo.value.startup_stderr == "waiting with <redacted>"
    else:
        assert excinfo.value.public_reason == "VSView failed its startup dependency check."
        assert "entry point is unavailable" in (excinfo.value.startup_stderr or "")


def test_launch_uses_managed_launcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_available_runtime(monkeypatch)
    monkeypatch.setenv("PYTHONPATH", "/caller/python-path")
    monkeypatch.setenv("PYTHONHOME", "/caller/python-home")
    mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr("frame_compare.vsview.adapter.subprocess.run", mock_run)
    process = MagicMock()
    process.wait.return_value = 0
    popen = MagicMock(return_value=process)
    monkeypatch.setattr("frame_compare.vsview.adapter.subprocess.Popen", popen)

    session, _wait_seconds = launch_alignment_verification_session(
        _session_request(tmp_path),
        VSViewConfig(enabled=True),
    )

    assert popen.call_args.args[0] == [
        sys.executable,
        "-m",
        "frame_compare.vsview.launcher",
        str(session.script_path),
    ]
    launch_env = popen.call_args.kwargs["env"]
    assert "PYTHONPATH" not in launch_env
    assert "PYTHONHOME" not in launch_env
    assert launch_env["PYTHONSAFEPATH"] == "1"
    assert launch_env["PYTHONNOUSERSITE"] == "1"
    process.terminate.assert_not_called()
    process.kill.assert_not_called()


def test_disabled_launch_writes_vsview_named_session_without_starting_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    availability = MagicMock(side_effect=AssertionError("disabled launch must not probe"))
    monkeypatch.setattr("frame_compare.vsview.adapter.check_vsview_availability", availability)

    session, wait_seconds = launch_alignment_verification_session(
        _session_request(tmp_path),
        VSViewConfig(enabled=False),
    )

    assert wait_seconds == 0.0
    assert session.script_path.parent == tmp_path / "vsview_sessions"
    assert session.script_path.name.startswith("vsview_ref_")
    assert session.result_path.name.endswith(".alignment-result.json")


def test_session_setup_contract_failure_raises_typed_vsview_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_failure = AlignmentReviewContractError("invalid VSView session script filename")
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.alignment_review_session_from_script",
        MagicMock(side_effect=contract_failure),
    )

    with pytest.raises(VSViewError, match="VSView session setup failed"):
        launch_alignment_verification_session(
            _session_request(tmp_path),
            VSViewConfig(enabled=False),
        )


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


def test_launch_timeout_kills_child_when_terminate_does_not_reap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_available_runtime(monkeypatch)
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.subprocess.run",
        MagicMock(return_value=subprocess.CompletedProcess([], 0, "", "")),
    )
    process = MagicMock()
    process.wait.side_effect = [
        subprocess.TimeoutExpired(["vsview"], 1),
        subprocess.TimeoutExpired(["vsview"], 1),
        0,
    ]
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.subprocess.Popen", MagicMock(return_value=process)
    )

    with pytest.raises(VSViewError, match="timed out"):
        launch_alignment_verification_session(
            _session_request(tmp_path),
            VSViewConfig(enabled=True),
        )

    process.terminate.assert_called_once_with()
    process.kill.assert_called_once_with()
    assert all(call.kwargs == {"timeout": 5.0} for call in process.wait.call_args_list[1:])


def test_run_vsview_command_reaps_child_after_interruption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = MagicMock()
    process.wait.side_effect = [KeyboardInterrupt(), 0]
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.subprocess.Popen", MagicMock(return_value=process)
    )

    with pytest.raises(KeyboardInterrupt):
        _run_vsview_command(["vsview"], env={})

    process.terminate.assert_called_once_with()
    process.kill.assert_not_called()
    assert process.wait.call_args_list[1].kwargs == {"timeout": 5.0}


@pytest.mark.skipif(os.name == "nt", reason="SIGINT wait interruption is POSIX-specific")
def test_real_child_is_reaped_after_interruption(tmp_path: Path) -> None:
    """Exercise the signal boundary that a Popen mock cannot model."""
    marker = tmp_path / "child.pid"
    child_code = (
        "import os, time\n"
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text(str(os.getpid()), encoding='ascii')\n"
        "time.sleep(60)\n"
    )
    helper_code = (
        "import os, signal, sys, threading, time\n"
        "from pathlib import Path\n"
        "from frame_compare.vsview.adapter import _run_vsview_command\n"
        "marker = Path(sys.argv[1])\n"
        "child_code = sys.argv[2]\n"
        "def interrupt_parent():\n"
        "    startup_deadline = time.monotonic() + 2.0\n"
        "    while not marker.exists() and time.monotonic() < startup_deadline:\n"
        "        time.sleep(0.01)\n"
        "    os.kill(os.getpid(), signal.SIGINT)\n"
        "threading.Thread(target=interrupt_parent, daemon=True).start()\n"
        "try:\n"
        "    _run_vsview_command([sys.executable, '-c', child_code], env=os.environ.copy())\n"
        "except KeyboardInterrupt:\n"
        "    deadline = time.monotonic() + 2.0\n"
        "    while not marker.exists() and time.monotonic() < deadline:\n"
        "        time.sleep(0.01)\n"
        "    if not marker.exists():\n"
        "        raise SystemExit('child startup marker was not written before the deadline')\n"
        "    child_pid = int(marker.read_text(encoding='ascii'))\n"
        "    while time.monotonic() < deadline:\n"
        "        try:\n"
        "            os.kill(child_pid, 0)\n"
        "        except ProcessLookupError:\n"
        "            raise SystemExit(0)\n"
        "        time.sleep(0.01)\n"
        "    raise SystemExit('child still exists after interruption cleanup')\n"
        "else:\n"
        "    raise SystemExit('expected KeyboardInterrupt')\n"
    )

    runner = subprocess.Popen(  # noqa: S603 - test uses an explicit interpreter argv
        [sys.executable, "-c", helper_code, str(marker), child_code],
        cwd=Path(__file__).parents[2],
        env=os.environ.copy(),
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        try:
            stdout, stderr = runner.communicate(timeout=5.0)
        except subprocess.TimeoutExpired as exc:
            pytest.fail(f"interruption helper exceeded bound: {exc}")
        assert runner.returncode == 0, f"stdout={stdout!r}\nstderr={stderr!r}"
    finally:
        if runner.poll() is None:
            with suppress(ProcessLookupError):
                os.killpg(runner.pid, signal.SIGKILL)
            runner.wait(timeout=2.0)
        if marker.exists():
            child_pid = int(marker.read_text(encoding="ascii"))
            with suppress(ProcessLookupError):
                os.kill(child_pid, signal.SIGKILL)


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
    audio_review_by_key: dict[str, str] | None = None,
    overlay_sink: list[str] | None = None,
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
        def Text(self, clip: FakeClip, text: str, *, alignment: int) -> FakeClip:
            assert alignment == 7
            if overlay_sink is not None:
                overlay_sink.append(text)
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
        audio_review_by_key=(
            _audio_review_map(suggested_offsets_by_key)
            if audio_review_by_key is None
            else audio_review_by_key
        ),
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
    output_calls, output_metadata, _props, _loader_calls = _execute_generated_script(
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
    assert {metadata["frame_compare_contract_version"] for metadata in output_metadata} == {
        ALIGNMENT_REVIEW_METADATA_VERSION
    }
    assert {metadata["frame_compare_session_id"] for metadata in output_metadata} == {"1" * 32}


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

    assert loader_calls == [
        ("ref", str(source_index_path(tmp_path / "ref.mkv")), None),
        ("ref", None, 0),
        ("a", str(source_index_path(tmp_path / "a.mkv")), None),
        ("a", None, 0),
    ]
    assert output_calls == [("ref", 0, "Reference"), ("a", 1, "Comparison 1")]
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


def test_generated_session_applies_bt709_defaults_for_unspecified_color_metadata(
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


def test_generated_session_keeps_accepted_provisional_and_unavailable_copy_distinct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlays: list[str] = []
    candidate = {
        "frame_offset": 0,
        "time_offset_seconds": 0.0,
        "subframe_estimate": 0.0,
        "basis": "audio_only",
    }
    reviews = {
        "ref:accepted": json.dumps(
            {
                "current_authority": {"origin": "computed_this_run", "frame_offset": 0},
                "evidence_availability": "current_attempt",
                "audio_attempt": {
                    "decision": {
                        "state": "trusted_automatic",
                        "candidate": candidate,
                        "primary_reason": "accepted",
                        "failed_gates": [],
                    }
                },
            }
        ),
        "ref:provisional": json.dumps(
            {
                "current_authority": {"origin": "none", "frame_offset": None},
                "evidence_availability": "current_attempt",
                "audio_attempt": {
                    "decision": {
                        "state": "provisional",
                        "candidate": candidate,
                        "primary_reason": "audio_only",
                        "failed_gates": [],
                    }
                },
            }
        ),
        "ref:unavailable": json.dumps(
            {
                "current_authority": {"origin": "none", "frame_offset": None},
                "evidence_availability": "current_attempt",
                "audio_attempt": {
                    "decision": {
                        "state": "unavailable",
                        "candidate": None,
                        "primary_reason": "insufficient_signal",
                        "failed_gates": ["insufficient_signal"],
                    }
                },
            }
        ),
    }

    _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        comparison_stems=("accepted", "provisional", "unavailable"),
        suggested_offsets_by_key={
            "ref:accepted": 0,
            "ref:provisional": None,
            "ref:unavailable": None,
        },
        audio_review_by_key=reviews,
        overlay_sink=overlays,
    )

    joined = "\n".join(overlays)
    assert "Audio alignment accepted: +0f" in joined
    assert "Provisional +0f - NOT APPLIED" in joined
    assert "No usable audio candidate" in joined
    assert "no trusted audio hint" not in joined


def test_generated_script_suppresses_only_redundant_vsview_load_success() -> None:
    logger = logging.getLogger("vsview.app.workspace.loader")
    existing_filters = tuple(logger.filters)
    namespace: dict[str, object] = {}
    exec(_build_script_header(), namespace)  # noqa: S102
    added_filters = [item for item in logger.filters if item not in existing_filters]

    try:
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
        audio_review_by_key=_audio_review_map({"ref:a": 0}),
        presentation_names_by_stem={"ref": "2160p \u00b7 REF", "a": "2160p \u00b7 A"},
        short_names_by_stem={"a": "ShortA"},
    )

    # Burned-in overlays keep the ASCII arrow; the ready step renders it via _arrow().
    assert generated.count("Open Tool Panel -> Frame Compare Alignment Review.") == 2
    assert (
        "  2  Unlink playheads, then position every source on the same visible moment." in generated
    )
    assert (
        "  3  Save the alignment in the panel, then close VSView to continue Frame Compare."
        in generated
    )
    assert "VSView is open" in generated


def test_write_vsview_session_script_uses_unique_uuid_paths(
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
        audio_review_by_key=_audio_review_map({"ref:a": 1}),
        cache_dir=tmp_path,
    )
    second = write_vsview_session_script(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={"ref:a": 1},
        audio_review_by_key=_audio_review_map({"ref:a": 1}),
        cache_dir=tmp_path,
    )

    assert first.parent.name == "vsview_sessions"
    assert first.name.startswith("vsview_ref_")
    assert re.fullmatch(r"vsview_ref_\d{8}T\d{6}Z_[0-9a-f]{32}\.py", first.name)
    assert re.fullmatch(r"vsview_ref_\d{8}T\d{6}Z_[0-9a-f]{32}\.py", second.name)
    assert first != second


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
        audio_review_by_key=_audio_review_map({"ref:a": 1}),
        cache_dir=tmp_path,
    )

    assert script.name.endswith(f"_{'2' * 32}.py")
