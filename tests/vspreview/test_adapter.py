"""Unit tests for VSPreview adapter launch behavior.

These tests do NOT require VSPreview, VapourSynth, FFmpeg, or any display.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest

from frame_compare.vspreview.adapter import (
    VSPreviewAvailability,
    VSPreviewAvailabilityStatus,
    VSPreviewConfig,
    VSPreviewSessionRequest,
    _check_startup_readiness,
    _resolve_launch_command,
    check_vspreview_availability,
    launch_alignment_verification_session,
)
from frame_compare.vspreview.errors import VSPreviewError
from frame_compare.vspreview.session_script import (
    _build_helpers_section,
    _build_script_content,
    write_vspreview_session_script,
)

_EXPECTED_VSTOOLS_WARNING_FILTER = "ignore:Starting from R74:SyntaxWarning:vstools.enums.color"


class _FakeVSPreviewProcess:
    def __init__(self, returncode: int = 0) -> None:
        self._returncode = returncode

    def __enter__(self) -> _FakeVSPreviewProcess:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None

    def wait(self) -> int:
        return self._returncode


def _launch_and_capture_child_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    no_color: bool = False,
) -> dict[str, str]:
    popen = MagicMock(return_value=_FakeVSPreviewProcess())

    with monkeypatch.context() as launch_patches:
        launch_patches.setattr(
            "frame_compare.vspreview.adapter.check_vspreview_availability",
            lambda: VSPreviewAvailability(
                status=VSPreviewAvailabilityStatus.AVAILABLE,
                message="available",
            ),
        )
        launch_patches.setattr(
            "frame_compare.vspreview.adapter._resolve_launch_command",
            lambda script_path: ["vspreview", str(script_path)],
        )
        launch_patches.setattr(
            "frame_compare.vspreview.adapter.subprocess.Popen",
            popen,
        )
        launch_alignment_verification_session(
            VSPreviewSessionRequest(
                reference=Path("ref.mkv"),
                comparisons=[Path("comparison.mkv")],
                suggested_offsets_by_key={},
                cache_dir=tmp_path,
            ),
            VSPreviewConfig(enabled=True, no_color=no_color),
        )
    env = popen.call_args.kwargs["env"]
    assert isinstance(env, dict)
    return cast("dict[str, str]", env)


def test_launch_session_child_env_adds_only_narrow_filter_without_mutating_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTHONWARNINGS", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    parent_env = os.environ.copy()

    child_env = _launch_and_capture_child_env(tmp_path, monkeypatch, no_color=True)

    assert child_env["PYTHONWARNINGS"] == _EXPECTED_VSTOOLS_WARNING_FILTER
    assert child_env["NO_COLOR"] == "1"
    assert os.environ == parent_env


def test_launch_session_child_env_preserves_later_user_warning_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_filters = "error::ResourceWarning"
    monkeypatch.setenv("PYTHONWARNINGS", user_filters)

    child_env = _launch_and_capture_child_env(tmp_path, monkeypatch)

    assert child_env["PYTHONWARNINGS"] == (f"{_EXPECTED_VSTOOLS_WARNING_FILTER},{user_filters}")
    assert os.environ["PYTHONWARNINGS"] == user_filters


def test_launch_session_child_warning_filter_is_narrow_in_real_python_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warning_message = (
        "Starting from R74, VS props values and Zimg (resize plugin) values are the same"
    )
    for package_dir in (
        tmp_path / "vstools",
        tmp_path / "vstools" / "enums",
        tmp_path / "another_package",
    ):
        package_dir.mkdir(exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
    target_module = tmp_path / "vstools" / "enums" / "color.py"
    target_module.write_text(
        f"import warnings\nwarnings.warn({warning_message!r}, SyntaxWarning)\n",
        encoding="utf-8",
    )
    (tmp_path / "another_package" / "color.py").write_text(
        f"import warnings\nwarnings.warn({warning_message!r}, SyntaxWarning)\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PYTHONWARNINGS", raising=False)
    env = _launch_and_capture_child_env(tmp_path, monkeypatch)
    inherited_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(tmp_path) + (
        f"{os.pathsep}{inherited_pythonpath}" if inherited_pythonpath else ""
    )

    target_result = subprocess.run(
        [sys.executable, "-c", "import vstools.enums.color"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    target_module.write_text(
        "import warnings\nwarnings.warn('Different important warning', SyntaxWarning)\n",
        encoding="utf-8",
    )
    different_message_result = subprocess.run(
        [sys.executable, "-c", "import vstools.enums.color"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    different_module_result = subprocess.run(
        [sys.executable, "-c", "import another_package.color"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )

    assert target_result.returncode == 0
    assert target_result.stdout == ""
    assert target_result.stderr == ""
    assert different_message_result.returncode == 0
    assert "Different important warning" in different_message_result.stderr
    assert different_module_result.returncode == 0
    assert warning_message in different_module_result.stderr
    assert "another_package" in different_module_result.stderr


def test_launch_session_child_warning_filter_keeps_later_user_override_authoritative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warning_message = (
        "Starting from R74, VS props values and Zimg (resize plugin) values are the same"
    )
    module_dir = tmp_path / "vstools" / "enums"
    module_dir.mkdir(parents=True)
    (tmp_path / "vstools" / "__init__.py").write_text("", encoding="utf-8")
    (module_dir / "__init__.py").write_text("", encoding="utf-8")
    (module_dir / "color.py").write_text(
        f"import warnings\nwarnings.warn({warning_message!r}, SyntaxWarning)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "PYTHONWARNINGS",
        "error:Starting from R74:SyntaxWarning:vstools.enums.color",
    )
    env = _launch_and_capture_child_env(tmp_path, monkeypatch)
    env["PYTHONPATH"] = str(tmp_path)

    result = subprocess.run(
        [sys.executable, "-c", "import vstools.enums.color"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )

    assert result.returncode != 0
    assert warning_message in result.stderr


def test_startup_readiness_accepts_healthy_current_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr("frame_compare.vspreview.adapter.subprocess.run", mock_run)

    _check_startup_readiness([sys.executable, "-m", "vspreview", "session.py"], env={})

    mock_run.assert_called_once()
    probe_command = mock_run.call_args.args[0]
    assert "prepare_vspreview_compatibility" in probe_command[2]
    assert "import vspreview.init" in probe_command[2]


def test_launch_session_returns_safe_missing_module_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "tiny"
    monkeypatch.setenv("FRAME_COMPARE_API_TOKEN", secret)
    stderr = (
        "Traceback (most recent call last):\n"
        '  File "C:\\private\\vspreview.py", line 1\n'
        f"  inherited token: {secret}\n"
        "ModuleNotFoundError: No module named 'vstools.utils.gpu'\n"
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.AVAILABLE,
            message="available",
        ),
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter._resolve_launch_command",
        lambda script_path: [sys.executable, "-m", "vspreview", str(script_path)],
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.subprocess.run",
        MagicMock(return_value=subprocess.CompletedProcess([], 1, "", stderr)),
    )
    popen = MagicMock()
    monkeypatch.setattr("frame_compare.vspreview.adapter.subprocess.Popen", popen)

    with pytest.raises(VSPreviewError) as excinfo:
        launch_alignment_verification_session(
            VSPreviewSessionRequest(
                reference=Path("ref.mkv"),
                comparisons=[Path("a.mkv")],
                suggested_offsets_by_key={},
                cache_dir=tmp_path,
            ),
            VSPreviewConfig(enabled=True),
        )

    assert excinfo.value.public_reason == "Missing optional dependency: vstools.utils.gpu"
    assert excinfo.value.missing_module == "vstools.utils.gpu"
    assert excinfo.value.startup_stderr is not None
    assert secret not in excinfo.value.startup_stderr
    assert "<redacted>" in excinfo.value.startup_stderr
    assert "vstools.utils.gpu" in excinfo.value.startup_stderr
    assert "C:\\private" not in str(excinfo.value)
    popen.assert_not_called()


def test_startup_readiness_does_not_probe_external_launcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_run = MagicMock()
    monkeypatch.setattr("frame_compare.vspreview.adapter.subprocess.run", mock_run)

    _check_startup_readiness(["external-vspreview", "session.py"], env={})

    mock_run.assert_not_called()


def test_launch_session_startup_timeout_is_bounded_redacted_and_prevents_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "timeout-secret-token"
    monkeypatch.setenv("FRAME_COMPARE_SECRET", secret)
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.AVAILABLE,
            message="available",
        ),
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter._resolve_launch_command",
        lambda script_path: [sys.executable, "-m", "vspreview", str(script_path)],
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.subprocess.run",
        MagicMock(
            side_effect=subprocess.TimeoutExpired(
                [sys.executable],
                10.0,
                stderr=f"waiting with {secret}".encode(),
            )
        ),
    )
    popen = MagicMock()
    monkeypatch.setattr("frame_compare.vspreview.adapter.subprocess.Popen", popen)

    with pytest.raises(VSPreviewError) as excinfo:
        launch_alignment_verification_session(
            VSPreviewSessionRequest(
                reference=Path("ref.mkv"),
                comparisons=[Path("a.mkv")],
                suggested_offsets_by_key={},
                cache_dir=tmp_path,
            ),
            VSPreviewConfig(enabled=True),
        )

    assert excinfo.value.public_reason == "startup dependency check timed out"
    assert "Traceback" not in str(excinfo.value)
    assert excinfo.value.startup_stderr == "waiting with <redacted>"
    popen.assert_not_called()


def test_portable_windows_launch_preloads_media_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("frame_compare.vspreview.adapter.runtime_kind", lambda: "windows-portable")
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.shutil.which",
        lambda _command: pytest.fail("portable launch must not select an external executable"),
    )

    script_path = Path("generated/session.py")

    assert _resolve_launch_command(script_path) == [
        sys.executable,
        "-m",
        "frame_compare.vspreview.launcher",
        str(script_path),
    ]


def test_current_interpreter_launch_uses_compatibility_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("frame_compare.vspreview.adapter.runtime_kind", lambda: "unmanaged")
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.importlib.util.find_spec",
        lambda module: SimpleNamespace() if module == "vspreview" else None,
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.shutil.which",
        lambda _command: pytest.fail("Current interpreter must use compatibility bootstrap"),
    )
    script_path = Path("generated/session.py")

    assert _resolve_launch_command(script_path) == [
        sys.executable,
        "-m",
        "frame_compare.vspreview.launcher",
        str(script_path),
    ]


def test_external_vspreview_executable_is_used_when_current_interpreter_cannot_import_vspreview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("frame_compare.vspreview.adapter.runtime_kind", lambda: "unmanaged")
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.importlib.util.find_spec", lambda _module: None
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.shutil.which",
        lambda command: "C:/external/vspreview.exe" if command == "vspreview" else None,
    )

    assert _resolve_launch_command(Path("generated/session.py")) == [
        "C:/external/vspreview.exe",
        str(Path("generated/session.py")),
    ]


def _execute_generated_script(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suggested_offsets_by_key: dict[str, int | None],
    comparison_stems: tuple[str, ...],
    num_frames_by_stem: dict[str, int] | None = None,
    frame_props_by_stem: dict[str, dict[str, object]] | None = None,
    overlay_failure_stems: set[str] | None = None,
    presentation_names_by_stem: dict[str, str] | None = None,
    native_loader_output: bool = False,
    load_failure_stems: set[str] | None = None,
) -> tuple[
    dict[str, list[tuple[int | None, int | None, int | None]]],
    list[int],
    list[str],
]:
    reference = tmp_path / "ref.mkv"
    comparisons = [tmp_path / f"{stem}.mkv" for stem in comparison_stems]
    reference.touch()
    for comparison in comparisons:
        comparison.touch()

    resolved_num_frames = {"ref": 20, **(num_frames_by_stem or {})}
    slice_history: dict[str, list[tuple[int | None, int | None, int | None]]] = {
        "ref": [],
        **{stem: [] for stem in comparison_stems},
    }
    output_indices: list[int] = []
    output_stems: list[str] = []
    resolved_frame_props = {
        stem: {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1} for stem in ("ref", *comparison_stems)
    }
    if frame_props_by_stem is not None:
        resolved_frame_props.update(frame_props_by_stem)
    resolved_overlay_failure_stems = overlay_failure_stems or set()
    resolved_load_failure_stems = load_failure_stems or set()

    class FakeClip:
        def __init__(self, stem: str, num_frames: int) -> None:
            self.stem = stem
            self.num_frames = num_frames
            self.fps = SimpleNamespace(numerator=24, denominator=1)

        def __getitem__(self, key: slice) -> FakeClip:
            assert isinstance(key, slice)
            slice_history[self.stem].append((key.start, key.stop, key.step))
            return self

        def set_output(self, index: int) -> None:
            output_indices.append(index)
            output_stems.append(self.stem)

        def get_frame(self, _index: int) -> object:
            raise AssertionError("generated VSPreview diagnostics must not decode source frames")

    clips = {
        stem: FakeClip(stem, resolved_num_frames.get(stem, 20))
        for stem in ("ref", *comparison_stems)
    }

    class FakeLsmas:
        def LWLibavSource(self, path: str) -> FakeClip:
            if native_loader_output:
                print("NATIVE INDEX OUTPUT", file=sys.stderr)
            stem = Path(path).stem
            if stem in resolved_load_failure_stems:
                raise RuntimeError("load failed")
            return clips[stem]

    class FakeText:
        def Text(self, clip: FakeClip, _text: str, *, alignment: int) -> FakeClip:
            if clip.stem in resolved_overlay_failure_stems:
                raise RuntimeError("overlay failed")
            return clip

    class FakeStd:
        def AssumeFPS(self, clip: FakeClip, *, fpsnum: int, fpsden: int) -> FakeClip:
            return clip

    class FakeCore:
        lsmas = FakeLsmas()
        text = FakeText()
        std = FakeStd()

    fake_vapoursynth = types.ModuleType("vapoursynth")
    fake_vapoursynth.core = FakeCore()
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vapoursynth)

    script = _build_script_content(
        reference=reference,
        comparisons=comparisons,
        suggested_offsets_by_key=suggested_offsets_by_key,
        bootstrap_paths=[tmp_path],
        frame_props_by_stem=resolved_frame_props,
        presentation_names_by_stem=presentation_names_by_stem,
    )

    exec(
        compile(script, "<vspreview-generated>", "exec"),
        {"__name__": "vspreview_loaded_script", "__file__": str(tmp_path / "session.py")},
    )

    return slice_history, output_indices, output_stems


def test_launch_alignment_verification_session_waits_for_vspreview_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Force launch path
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.AVAILABLE,
            message="available",
        ),
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter._resolve_launch_command",
        lambda script_path: [sys.executable, "-m", "vspreview", str(script_path)],
    )
    readiness_run = MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr("frame_compare.vspreview.adapter.subprocess.run", readiness_run)

    run_calls: list[tuple[object, object]] = []

    def _fake_popen(command: object, **kwargs: object) -> _FakeVSPreviewProcess:
        run_calls.append((command, kwargs))
        return _FakeVSPreviewProcess()

    monkeypatch.setattr("frame_compare.vspreview.adapter.subprocess.Popen", _fake_popen)

    cfg = VSPreviewConfig(enabled=True)
    script_path = launch_alignment_verification_session(
        request=VSPreviewSessionRequest(
            reference=Path("ref.mkv"),
            comparisons=[Path("a.mkv")],
            suggested_offsets_by_key={},
            cache_dir=tmp_path,
        ),
        config=cfg,
    )

    assert script_path.exists()
    assert len(run_calls) == 1
    command, kwargs = run_calls[0]
    assert command == [sys.executable, "-m", "vspreview", str(script_path)]
    readiness_run.assert_called_once()
    readiness_env = readiness_run.call_args.kwargs["env"]
    assert readiness_env is kwargs["env"]
    assert "timeout" not in kwargs
    assert kwargs["stdin"] is None
    assert kwargs["stdout"] is None
    assert kwargs["stderr"] is None
    assert "text" not in kwargs
    assert "errors" not in kwargs
    assert "bufsize" not in kwargs
    assert "VSPreview Session" not in capsys.readouterr().err


def test_launch_alignment_verification_session_writes_launch_telemetry_to_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.AVAILABLE,
            message="available",
        ),
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter._resolve_launch_command",
        lambda script_path: ["vspreview", str(script_path)],
    )
    run_kwargs: dict[str, object] = {}

    def _fake_popen(command: object, **kwargs: object) -> _FakeVSPreviewProcess:
        run_kwargs.update(kwargs)
        return _FakeVSPreviewProcess()

    monkeypatch.setattr("frame_compare.vspreview.adapter.subprocess.Popen", _fake_popen)

    launch_alignment_verification_session(
        request=VSPreviewSessionRequest(
            reference=Path("ref.mkv"),
            comparisons=[Path("a.mkv")],
            suggested_offsets_by_key={},
            cache_dir=tmp_path,
        ),
        config=VSPreviewConfig(enabled=True, no_color=True, verbose=True),
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "VSPreview Session" in captured.err
    assert "script" in captured.err
    assert "command" in captured.err
    assert "Frame Compare diagnostics inherited on stderr" in captured.err
    assert "\x1b[" not in captured.err
    assert "[bold cyan]" not in captured.err
    env = run_kwargs["env"]
    assert isinstance(env, dict)
    assert env["NO_COLOR"] == "1"


def test_launch_alignment_verification_session_redacts_probe_failure_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.PROBE_FAILED,
            message="VSPreview availability probe failed",
            error_details={
                "exception_type": "RuntimeError",
                "exception": "secret token at /tmp/private.log",
            },
        ),
    )

    cfg = VSPreviewConfig(enabled=True)

    with pytest.raises(VSPreviewError) as excinfo:
        launch_alignment_verification_session(
            request=VSPreviewSessionRequest(
                reference=Path("ref.mkv"),
                comparisons=[Path("a.mkv")],
                suggested_offsets_by_key={},
                cache_dir=tmp_path,
            ),
            config=cfg,
        )

    assert "availability probe failed (RuntimeError)" in str(excinfo.value)
    assert "secret token" not in str(excinfo.value)
    assert "/tmp/private.log" not in str(excinfo.value)


def test_launch_alignment_verification_session_reports_missing_launcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.AVAILABLE,
            message="available",
        ),
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter._resolve_launch_command",
        lambda script_path: ["vspreview", str(script_path)],
    )

    def _raise_missing_launcher(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("secret missing launcher path")

    monkeypatch.setattr("frame_compare.vspreview.adapter.subprocess.Popen", _raise_missing_launcher)

    cfg = VSPreviewConfig(enabled=True)

    with pytest.raises(VSPreviewError) as excinfo:
        launch_alignment_verification_session(
            request=VSPreviewSessionRequest(
                reference=Path("ref.mkv"),
                comparisons=[Path("a.mkv")],
                suggested_offsets_by_key={},
                cache_dir=tmp_path,
            ),
            config=cfg,
        )

    assert "launcher command was not found" in str(excinfo.value)
    assert "secret missing launcher path" not in str(excinfo.value)


def test_launch_alignment_verification_session_reports_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.check_vspreview_availability",
        lambda: VSPreviewAvailability(
            status=VSPreviewAvailabilityStatus.AVAILABLE,
            message="available",
        ),
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter._resolve_launch_command",
        lambda script_path: ["vspreview", str(script_path)],
    )
    monkeypatch.setattr(
        "frame_compare.vspreview.adapter.subprocess.Popen",
        lambda _command, **_kwargs: _FakeVSPreviewProcess(returncode=7),
    )

    with pytest.raises(VSPreviewError, match="launch exited with code 7"):
        launch_alignment_verification_session(
            request=VSPreviewSessionRequest(
                reference=Path("ref.mkv"),
                comparisons=[Path("a.mkv")],
                suggested_offsets_by_key={},
                cache_dir=tmp_path,
            ),
            config=VSPreviewConfig(enabled=True),
        )


def test_build_script_content_escapes_path_literals() -> None:
    """Generated script should remain valid Python for hostile filenames."""
    reference = Path('/tmp/ref"x.mkv')
    comparisons = [Path('/tmp/bad"\nprint(123)\n#.mkv')]

    script = _build_script_content(
        reference=reference,
        comparisons=comparisons,
        suggested_offsets_by_key={},
        bootstrap_paths=[Path("/workspace"), Path("/workspace/src")],
    )

    compile(script, "<vspreview>", "exec")
    assert '"label": "ref"x"' not in script
    assert '"\nprint(123)\n#' not in script
    assert "\\nprint(123)\\n" in script


def test_build_script_content_warns_when_comparison_overlay_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:a": None},
        comparison_stems=("a",),
        overlay_failure_stems={"a"},
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Could not apply comparison text overlay" in captured.err


def test_generated_stream_reconfigure_helper_is_best_effort_for_known_stream_failures() -> None:
    class StreamWithoutReconfigure:
        def write(self, _text: str) -> None:
            return

        def flush(self) -> None:
            return

    class StreamWithEncodingFailure:
        def reconfigure(self, **_kwargs: object) -> None:
            raise UnicodeError("encoding unavailable")

        def write(self, _text: str) -> None:
            return

        def flush(self) -> None:
            return

    fake_sys = SimpleNamespace(
        stdout=StreamWithoutReconfigure(),
        stderr=StreamWithEncodingFailure(),
    )

    exec(_build_helpers_section(), {"sys": fake_sys})


@pytest.mark.parametrize(
    ("core_attrs", "expected_loader"),
    [
        (("lsmas", "lw"), "lsmas"),
        (("lw",), "lw"),
    ],
)
def test_build_script_content_resolves_lwlibavsource_preference_and_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    core_attrs: tuple[str, ...],
    expected_loader: str,
) -> None:
    reference = tmp_path / "ref.mkv"
    comparison = tmp_path / "a.mkv"
    reference.touch()
    comparison.touch()
    loader_calls: list[str] = []

    class FakeClip:
        num_frames = 20
        fps = SimpleNamespace(numerator=24, denominator=1)

        def set_output(self, _index: int) -> None:
            return

        def get_frame(self, _index: int) -> object:
            raise AssertionError("generated VSPreview diagnostics must not decode source frames")

    class FakeLoaderNamespace:
        def __init__(self, name: str) -> None:
            self.name = name

        def LWLibavSource(self, _path: str) -> FakeClip:  # noqa: N802
            loader_calls.append(self.name)
            return FakeClip()

    class FakeText:
        def Text(self, clip: FakeClip, _text: str, *, alignment: int) -> FakeClip:
            return clip

    class FakeStd:
        def AssumeFPS(self, clip: FakeClip, *, fpsnum: int, fpsden: int) -> FakeClip:
            return clip

    fake_core = SimpleNamespace(text=FakeText(), std=FakeStd())
    for attr in core_attrs:
        setattr(fake_core, attr, FakeLoaderNamespace(attr))
    fake_vapoursynth = types.ModuleType("vapoursynth")
    fake_vapoursynth.core = fake_core
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vapoursynth)

    script = _build_script_content(
        reference=reference,
        comparisons=[comparison],
        suggested_offsets_by_key={},
        bootstrap_paths=[tmp_path],
    )

    exec(
        compile(script, "<vspreview-generated>", "exec"),
        {"__name__": "vspreview_loaded_script", "__file__": str(tmp_path / "session.py")},
    )

    assert loader_calls == [expected_loader, expected_loader]


def test_generated_script_sets_outputs_when_loaded_as_vspreview_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slice_history, output_indices, output_stems = _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:a": 9},
        comparison_stems=("a",),
    )

    assert output_indices == [0, 1]
    assert output_stems == ["ref", "a"]
    assert slice_history["ref"] == []
    assert slice_history["a"] == []


def test_generated_script_uses_untrimmed_outputs_for_mixed_sign_offset_hints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slice_history, output_indices, output_stems = _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:comp_a": 3, "ref:comp_b": -2},
        comparison_stems=("comp_b", "comp_a"),
    )

    assert output_indices == [0, 1, 2, 3]
    assert output_stems == ["ref", "comp_b", "ref", "comp_a"]
    assert slice_history["ref"] == []
    assert slice_history["comp_a"] == []
    assert slice_history["comp_b"] == []


def test_generated_script_output_order_matches_prompt_input_order_for_unsorted_comparisons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _slice_history, output_indices, output_stems = _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={
            "ref:zeta": 4,
            "ref:alpha": None,
            "ref:mid": -2,
        },
        comparison_stems=("zeta", "alpha", "mid"),
    )

    captured = capsys.readouterr()
    assert output_indices == [0, 1, 2, 3, 4, 5]
    assert output_stems == ["ref", "zeta", "ref", "alpha", "ref", "mid"]
    assert captured.out == ""
    for token in ("comparison 1", "zeta", "alpha", "mid", "audio hint", "outputs"):
        assert token in captured.err


def test_generated_script_current_human_output_organization_without_launching_vspreview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:a": 4, "ref:b": None},
        comparison_stems=("a", "b"),
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "  [RUN] VSPreview Bootstrap" in captured.err
    assert "reference" in captured.err
    assert "loaded" not in captured.err
    assert "Reference 0 | Comparison 1 1" in captured.err
    assert "Reference 2 | Comparison 2 3" in captured.err
    assert (
        captured.err.index("comparison 1")
        < captured.err.index("Reference 0 | Comparison 1 1")
        < captured.err.index("comparison 2")
    )
    assert captured.err.index("comparison 2") < captured.err.index("Reference 2 | Comparison 2 3")
    assert "[OK] VSPreview Ready" in captured.err
    assert (
        "  [OK] VSPreview Ready\n"
        "    Inspect the untrimmed clips in VSPreview, then return here to confirm frames."
    ) in captured.err
    assert "next" not in captured.err
    assert "          Inspect the untrimmed clips" not in captured.err
    assert "VSPreview Assumptions" not in captured.err
    assert "a" in captured.err
    assert "b" in captured.err


def test_generated_script_uses_prepared_names_without_changing_internal_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:long-comparison-stem": 7},
        comparison_stems=("long-comparison-stem",),
        presentation_names_by_stem={
            "ref": "PMTP WEB-DL | DV HDR10+ | Kitsune",
            "long-comparison-stem": "ATV WEB-DL | DV HDR10+ | Kitsune",
        },
    )

    output = capsys.readouterr().err
    assert "PMTP WEB-DL | DV HDR10+ | Kitsune" in output
    assert "ATV WEB-DL | DV HDR10+ | Kitsune" in output
    assert "long-comparison-stem" not in output
    assert "+7f" in output
    assert "Reference 0 | Comparison 1 1" in output
    assert "\x1b[" not in output


def test_generated_assumptions_use_prepared_names_not_internal_stems(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:very-long-raw-comparison-stem": 7},
        comparison_stems=("very-long-raw-comparison-stem",),
        presentation_names_by_stem={
            "ref": "PMTP WEB-DL | DV HDR10+ | Kitsune",
            "very-long-raw-comparison-stem": "ATV WEB-DL | DV HDR10+ | Kitsune",
        },
        frame_props_by_stem={
            "ref": {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1},
            "very-long-raw-comparison-stem": {"_Transfer": 2},
        },
    )

    output = capsys.readouterr().err
    assert "ATV WEB-DL | DV HDR10+ | Kitsune missing" in output
    assert "very-long-raw-comparison-stem" not in output


def test_failed_comparison_keeps_visible_warning_and_truthful_output_grouping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:a": 1, "ref:b": 2},
        comparison_stems=("a", "b"),
        load_failure_stems={"a"},
    )

    output = capsys.readouterr().err
    assert "comparison 1  a" in output
    assert "[WARN] Comparison source could not be loaded" in output
    assert "comparison 2  b" in output
    assert "Reference 0 | Comparison 2 1" in output
    assert "Comparison 1 1" not in output


def test_generated_bootstrap_precedes_native_source_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:a": 0},
        comparison_stems=("a",),
        native_loader_output=True,
    )

    output = capsys.readouterr().err
    assert output.index("[RUN] VSPreview Bootstrap") < output.index("NATIVE INDEX OUTPUT")
    assert output.index("reference") < output.index("NATIVE INDEX OUTPUT")
    assert output.index("fps") > output.index("NATIVE INDEX OUTPUT")


def test_generated_script_collects_preview_assumptions_before_outputs_and_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:a": 4, "ref:b": None},
        comparison_stems=("a", "b"),
        frame_props_by_stem={
            "ref": {"_Transfer": 2, "_Primaries": "oops"},
            "a": {"_Matrix": "9", "_Transfer": "16", "_Primaries": 9},
            "b": {"_Matrix": "not-an-int", "_Transfer": 1},
        },
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "VSPreview Assumptions" in captured.err
    for token in ("ref", "b", "_Matrix", "_Transfer", "_Primaries"):
        assert token in captured.err
    assert "display-safe defaults" in captured.err
    assert "preview only" in captured.err
    assert "render/report semantics" in captured.err
    assert "a missing" not in captured.err


def test_generated_script_serializes_non_finite_preview_props_as_assumptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:a": 4},
        comparison_stems=("a",),
        frame_props_by_stem={
            "ref": {"_Matrix": float("nan"), "_Transfer": float("inf"), "_Primaries": 1},
            "a": {"_Matrix": 1.0, "_Transfer": 1, "_Primaries": 1},
        },
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "VSPreview Assumptions" in captured.err
    assert "ref" in captured.err
    assert "_Matrix" in captured.err
    assert "_Transfer" in captured.err
    assert "a missing" not in captured.err


def test_generated_script_does_not_slice_source_clips_from_suggested_offsets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slice_history, output_indices, output_stems = _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:comp_a": 1, "ref:comp_b": 12},
        comparison_stems=("comp_a", "comp_b"),
        num_frames_by_stem={"ref": 30, "comp_a": 15, "comp_b": 25},
    )

    assert output_indices == [0, 1, 2, 3]
    assert output_stems == ["ref", "comp_a", "ref", "comp_b"]
    assert slice_history["ref"] == []
    assert slice_history["comp_a"] == []
    assert slice_history["comp_b"] == []


def test_generated_script_omits_numeric_hint_when_suggestion_is_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        suggested_offsets_by_key={"ref:a": None},
        comparison_stems=("a",),
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "no trusted audio hint" in captured.err
    assert "audio hint: 0" not in captured.err


def test_generated_script_reports_missing_lwlibavsource_without_traceback(tmp_path: Path) -> None:
    (tmp_path / "vapoursynth.py").write_text(
        """\
class _Core:
    pass


core = _Core()
""",
        encoding="utf-8",
    )
    reference = tmp_path / "ref.mkv"
    comparison = tmp_path / "a.mkv"
    reference.touch()
    comparison.touch()
    cache_dir = tmp_path / "generated" / "cache"
    cache_dir.mkdir(parents=True)

    script_path = write_vspreview_session_script(
        reference=reference,
        comparisons=[comparison],
        suggested_offsets_by_key={},
        cache_dir=cache_dir,
    )

    result = subprocess.run(
        [sys.executable, str(script_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "[FAIL] Failed to resolve LWLibavSource loader:" in result.stderr
    assert "LWLibavSource not found on core.lsmas or core.lw" in result.stderr
    assert "Traceback" not in result.stderr


def test_generate_vspreview_script_bootstraps_nested_legacy_workspace(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workspace_root = repo_root / "workspace"
    cache_dir = workspace_root / "generated" / "cache"
    (repo_root / "src" / "frame_compare").mkdir(parents=True)
    (workspace_root / "config").mkdir(parents=True)
    cache_dir.mkdir(parents=True)

    script_path = write_vspreview_session_script(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={},
        cache_dir=cache_dir,
    )

    script = script_path.read_text(encoding="utf-8")

    assert json.dumps(str(repo_root)) in script
    assert json.dumps(str(repo_root / "src")) in script
    assert json.dumps(str(workspace_root)) in script
    assert "_THIS_FILE.parents[4]" not in script


def test_generate_vspreview_script_bootstraps_run_folder_workspace(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workspace_root = repo_root / "workspace"
    cache_dir = workspace_root / "input" / "Movie (2024)" / "generated" / "cache"
    (repo_root / "src" / "frame_compare").mkdir(parents=True)
    (workspace_root / "config").mkdir(parents=True)
    cache_dir.mkdir(parents=True)

    script_path = write_vspreview_session_script(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={},
        cache_dir=cache_dir,
    )

    script = script_path.read_text(encoding="utf-8")

    assert json.dumps(str(repo_root)) in script
    assert json.dumps(str(repo_root / "src")) in script
    assert json.dumps(str(workspace_root)) in script
    assert str(cache_dir / "vspreview_sessions") not in script


def test_generate_vspreview_script_uses_atomic_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []

    def _fake_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        calls.append(path)
        path.write_text(content, encoding=encoding)

    monkeypatch.setattr("frame_compare.vspreview.session_script.write_text_atomic", _fake_write)

    script_path = write_vspreview_session_script(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={},
        cache_dir=tmp_path,
    )

    assert calls == [script_path]
    assert script_path.exists()


def test_generate_vspreview_script_handles_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import datetime

    # Freeze the time to ensure the timestamp is predictable in the test
    class MockDatetime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 5, 20, 19, 45, 0, tzinfo=tz)

    monkeypatch.setattr("frame_compare.vspreview.session_script.datetime", MockDatetime)

    timestamp = "20260520T194500Z"
    sessions_dir = tmp_path / "vspreview_sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # Pre-create the first two candidates
    first_path = sessions_dir / f"vspreview_ref_{timestamp}.py"
    first_path.touch()
    second_path = sessions_dir / f"vspreview_ref_{timestamp}_1.py"
    second_path.touch()

    # Call the generator
    script_path = write_vspreview_session_script(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={},
        cache_dir=tmp_path,
    )

    # Verify it used the next suffix (_2)
    assert script_path == sessions_dir / f"vspreview_ref_{timestamp}_2.py"
    assert script_path.exists()


@pytest.mark.parametrize(
    (
        "executable",
        "importable_modules",
        "probe_error",
        "expected_status",
        "expected_message",
    ),
    [
        pytest.param(
            "/usr/bin/vspreview",
            frozenset(),
            None,
            VSPreviewAvailabilityStatus.AVAILABLE,
            "available",
            id="executable",
        ),
        pytest.param(
            None,
            frozenset({"vspreview", "PyQt6"}),
            None,
            VSPreviewAvailabilityStatus.AVAILABLE,
            "available",
            id="pyqt6",
        ),
        pytest.param(
            None,
            frozenset({"vspreview", "PySide6"}),
            None,
            VSPreviewAvailabilityStatus.AVAILABLE,
            "available",
            id="pyside6",
        ),
        pytest.param(
            None,
            frozenset({"vspreview", "PyQt5"}),
            None,
            VSPreviewAvailabilityStatus.AVAILABLE,
            "available",
            id="pyqt5",
        ),
        pytest.param(
            None,
            frozenset(),
            None,
            VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE,
            "not installed",
            id="missing-module",
        ),
        pytest.param(
            None,
            frozenset({"vspreview"}),
            None,
            VSPreviewAvailabilityStatus.MISSING_QT_BACKEND,
            "Qt backend missing",
            id="missing-qt",
        ),
        pytest.param(
            None,
            frozenset(),
            ValueError("simulated import error"),
            VSPreviewAvailabilityStatus.PROBE_FAILED,
            "probe failed",
            id="probe-failed",
        ),
    ],
)
def test_check_vspreview_availability_by_owner_branch(
    monkeypatch: pytest.MonkeyPatch,
    executable: str | None,
    importable_modules: frozenset[str],
    probe_error: ValueError | None,
    expected_status: VSPreviewAvailabilityStatus,
    expected_message: str,
) -> None:
    find_spec_calls: list[str] = []

    def fake_find_spec(name: str) -> object | None:
        find_spec_calls.append(name)
        if probe_error is not None:
            raise probe_error
        return object() if name in importable_modules else None

    monkeypatch.setattr(
        "shutil.which", lambda command: executable if command == "vspreview" else None
    )
    monkeypatch.setattr("importlib.util.find_spec", fake_find_spec)

    result = check_vspreview_availability()

    assert result.status is expected_status
    assert result.is_available is (expected_status is VSPreviewAvailabilityStatus.AVAILABLE)
    assert expected_message in result.message
    expected_hints = {
        VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE: (
            "Provide VSPreview; see https://tjzine.github.io/frame-compare/getting-started/native/"
        ),
        VSPreviewAvailabilityStatus.MISSING_QT_BACKEND: (
            "Provide a supported Qt backend for VSPreview; see "
            "https://tjzine.github.io/frame-compare/getting-started/native/"
        ),
        VSPreviewAvailabilityStatus.PROBE_FAILED: (
            "Check the optional VSPreview setup, then rerun doctor; see "
            "https://tjzine.github.io/frame-compare/getting-started/native/"
        ),
    }
    assert result.hint == expected_hints.get(expected_status)
    if executable is not None:
        assert find_spec_calls == []
    if expected_status is VSPreviewAvailabilityStatus.PROBE_FAILED:
        assert result.error_details == {
            "exception_type": "ValueError",
            "exception": "simulated import error",
        }
    if result.hint is not None:
        assert "pip install" not in result.hint
        assert "README.md" not in result.hint
