"""Focused tests for the VSView adapter and generated session contract."""

from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from frame_compare.vs.source import source_index_path
from frame_compare.vsview.adapter import (
    VSViewAvailability,
    VSViewAvailabilityStatus,
    VSViewConfig,
    VSViewSessionRequest,
    _build_vsview_child_env,
    _check_startup_readiness,
    _resolve_launch_command,
    check_vsview_availability,
    launch_alignment_verification_session,
)
from frame_compare.vsview.errors import VSViewError
from frame_compare.vsview.session_script import (
    _build_helpers_section,
    _build_script_content,
    _build_script_header,
    write_vsview_session_script,
)


class _FakeVSViewProcess:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode

    def __enter__(self) -> _FakeVSViewProcess:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        return None

    def wait(self) -> int:
        return self.returncode


def _available() -> VSViewAvailability:
    return VSViewAvailability(
        status=VSViewAvailabilityStatus.AVAILABLE,
        message="available",
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
    ("executable", "modules", "expected"),
    [
        ("/usr/bin/vsview", frozenset(), VSViewAvailabilityStatus.AVAILABLE),
        (None, frozenset({"vsview", "PySide6"}), VSViewAvailabilityStatus.AVAILABLE),
        (None, frozenset({"vsview"}), VSViewAvailabilityStatus.MISSING_QT_BACKEND),
        (None, frozenset(), VSViewAvailabilityStatus.MISSING_EXEC_AND_MODULE),
    ],
)
def test_check_vsview_availability_uses_only_documented_backend(
    monkeypatch: pytest.MonkeyPatch,
    executable: str | None,
    modules: frozenset[str],
    expected: VSViewAvailabilityStatus,
) -> None:
    calls: list[str] = []

    def fake_find_spec(name: str) -> object | None:
        calls.append(name)
        return object() if name in modules else None

    monkeypatch.setattr("frame_compare.vsview.adapter.shutil.which", lambda _: executable)
    monkeypatch.setattr("frame_compare.vsview.adapter.importlib.util.find_spec", fake_find_spec)

    result = check_vsview_availability()

    assert result.status is expected
    assert result.is_available is (expected is VSViewAvailabilityStatus.AVAILABLE)
    if executable is None and "PySide6" in modules:
        assert calls == ["vsview", "PySide6"]


def test_check_vsview_availability_redacts_probe_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("frame_compare.vsview.adapter.shutil.which", lambda _: None)
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
    assert "compat" not in probe_code


def test_windows_startup_readiness_preloads_before_vsview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_run = MagicMock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr("frame_compare.vsview.adapter.subprocess.run", mock_run)
    monkeypatch.setattr("frame_compare.vsview.adapter.runtime_kind", lambda: "windows-portable")

    _check_startup_readiness([sys.executable, "-m", "vsview", "session.py"], env={})

    probe_code = mock_run.call_args.args[0][2]
    assert probe_code.index("preload_vapoursynth_runtime()") < probe_code.index("import PySide6")


def test_startup_readiness_does_not_probe_external_launcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_run = MagicMock()
    monkeypatch.setattr("frame_compare.vsview.adapter.subprocess.run", mock_run)

    _check_startup_readiness(["external-vsview", "session.py"], env={})

    mock_run.assert_not_called()


def test_startup_failure_is_bounded_redacted_and_prevents_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "timeout-secret-token"
    monkeypatch.setenv("FRAME_COMPARE_SECRET", secret)
    monkeypatch.setattr("frame_compare.vsview.adapter.check_vsview_availability", _available)
    monkeypatch.setattr(
        "frame_compare.vsview.adapter._resolve_launch_command",
        lambda script_path: [sys.executable, "-m", "vsview", str(script_path)],
    )
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
            VSViewSessionRequest(
                reference=Path("ref.mkv"),
                comparisons=[Path("a.mkv")],
                suggested_offsets_by_key={},
                cache_dir=tmp_path,
            ),
            VSViewConfig(enabled=True),
        )

    assert excinfo.value.public_reason == "startup dependency check timed out"
    assert excinfo.value.startup_stderr == "waiting with <redacted>"
    popen.assert_not_called()


def test_resolve_launch_command_uses_native_launcher_for_managed_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("frame_compare.vsview.adapter.runtime_kind", lambda: "windows-portable")
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.shutil.which",
        lambda _: pytest.fail("managed runtime must not use an external executable"),
    )

    assert _resolve_launch_command(Path("generated/session.py")) == [
        sys.executable,
        "-m",
        "frame_compare.vsview.launcher",
        str(Path("generated/session.py")),
    ]


def test_resolve_launch_command_uses_external_executable_when_module_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("frame_compare.vsview.adapter.runtime_kind", lambda: "unmanaged")
    monkeypatch.setattr("frame_compare.vsview.adapter.importlib.util.find_spec", lambda _: None)
    monkeypatch.setattr(
        "frame_compare.vsview.adapter.shutil.which",
        lambda command: "/usr/local/bin/vsview" if command == "vsview" else None,
    )

    assert _resolve_launch_command(Path("generated/session.py")) == [
        "/usr/local/bin/vsview",
        str(Path("generated/session.py")),
    ]


def test_disabled_launch_writes_vsview_named_session_without_starting_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    availability = MagicMock(side_effect=AssertionError("disabled launch must not probe"))
    monkeypatch.setattr("frame_compare.vsview.adapter.check_vsview_availability", availability)

    script_path = launch_alignment_verification_session(
        VSViewSessionRequest(
            reference=tmp_path / "ref.mkv",
            comparisons=[tmp_path / "comparison.mkv"],
            suggested_offsets_by_key={"ref:comparison": 4},
            cache_dir=tmp_path,
        ),
        VSViewConfig(enabled=False),
    )

    assert script_path.parent == tmp_path / "vsview_sessions"
    assert script_path.name.startswith("vsview_ref_")
    script = script_path.read_text(encoding="utf-8")
    assert "from vsview import set_output" in script
    assert 'set_output(ref_clip, reference_output, "Reference")' in script
    assert "set_output(comp_clip, comparison_output" in script


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
) -> tuple[
    list[tuple[str, int, str]],
    dict[str, dict[str, int]],
    list[tuple[str, str | None, int | None]],
]:
    reference = tmp_path / "ref.mkv"
    comparisons = [tmp_path / f"{stem}.mkv" for stem in comparison_stems]
    reference.touch()
    for comparison in comparisons:
        comparison.touch()

    output_calls: list[tuple[str, int, str]] = []
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

    def set_output(clip: FakeClip, index: int, name: str) -> None:
        output_calls.append((clip.stem, index, name))

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
        {"__name__": "vsview_loaded_script", "__file__": str(tmp_path / "session.py")},
    )
    return output_calls, applied_props, loader_calls


def test_generated_session_registers_named_outputs_in_input_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_calls, _props, _loader_calls = _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        comparison_stems=("zeta", "alpha"),
        suggested_offsets_by_key={"ref:zeta": 4, "ref:alpha": None},
    )

    assert output_calls == [
        ("ref", 0, "Reference"),
        ("zeta", 1, "Comparison 1"),
        ("ref", 2, "Reference"),
        ("alpha", 3, "Comparison 2"),
    ]


def test_generated_session_preserves_lsmash_indexes_and_only_retries_index_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_calls, _props, loader_calls = _execute_generated_script(
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


def test_generated_session_keeps_bt709_defaults_and_overlay_hints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_calls, applied_props, _loader_calls = _execute_generated_script(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        comparison_stems=("a",),
        suggested_offsets_by_key={"ref:a": 7},
        frame_props_by_stem={"ref": {"_Matrix": 2, "_Transfer": 2, "_Primaries": 2}},
    )

    assert output_calls == [("ref", 0, "Reference"), ("a", 1, "Comparison 1")]
    assert applied_props["ref"] == {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1}


def test_generated_script_header_and_helpers_are_self_contained() -> None:
    generated = _build_script_header() + _build_helpers_section()

    assert "import logging" not in generated


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
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
