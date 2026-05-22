"""Unit tests for VSPreview adapter launch behavior.

These tests do NOT require VSPreview, VapourSynth, FFmpeg, or any display.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from frame_compare.errors import VSPreviewError
from frame_compare.vspreview.adapter import (
    VSPreviewAvailability,
    VSPreviewAvailabilityStatus,
    VSPreviewConfig,
    _build_script_content,
    _generate_vspreview_script,
    launch_alignment_verification_session,
)


def test_launch_alignment_verification_session_respects_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
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
        lambda script_path: ["vspreview", str(script_path)],
    )

    def _raise_timeout(*_args: object, **_kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd=["vspreview"], timeout=1.0)

    monkeypatch.setattr("frame_compare.vspreview.adapter.subprocess.run", _raise_timeout)

    cfg = VSPreviewConfig(enabled=True, timeout_seconds=1.0)
    with pytest.raises(VSPreviewError, match="timed out"):
        launch_alignment_verification_session(
            reference=Path("ref.mkv"),
            comparisons=[Path("a.mkv")],
            suggested_offsets_by_key={},
            cache_dir=tmp_path,
            config=cfg,
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


def test_build_script_content_warns_when_comparison_overlay_fails() -> None:
    script = _build_script_content(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={},
        bootstrap_paths=[Path("/workspace"), Path("/workspace/src")],
    )

    warning = 'safe_print("Warning: Could not apply text overlay (plugin missing?)")'

    assert warning in script
    assert "pass  # Overlay is best-effort" not in script
    assert script.count(warning) == 2


def test_build_script_content_resolves_lwlibavsource_with_lsmas_then_lw_fallback() -> None:
    script = _build_script_content(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={},
        bootstrap_paths=[Path("/workspace"), Path("/workspace/src")],
    )

    assert "core.lsmas.LWLibavSource(str(" not in script
    assert "load_source = resolve_lwlibavsource(core)" in script
    assert 'if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):' in script
    assert "return core.lsmas.LWLibavSource" in script
    assert 'if hasattr(core, "lw") and hasattr(core.lw, "LWLibavSource"):' in script
    assert "return core.lw.LWLibavSource" in script
    assert script.index("return core.lsmas.LWLibavSource") < script.index(
        "return core.lw.LWLibavSource"
    )
    assert "ref_clip = load_source(str(ref_path))" in script
    assert "comp_clip = load_source(str(comp_path))" in script


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

    script_path = _generate_vspreview_script(
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
    assert "ERROR: Failed to resolve LWLibavSource loader:" in result.stdout
    assert "LWLibavSource not found on core.lsmas or core.lw" in result.stdout
    assert "Traceback" not in result.stderr


def test_generate_vspreview_script_bootstraps_nested_legacy_workspace(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workspace_root = repo_root / "workspace"
    cache_dir = workspace_root / "generated" / "cache"
    (repo_root / "src" / "frame_compare").mkdir(parents=True)
    (workspace_root / "config").mkdir(parents=True)
    cache_dir.mkdir(parents=True)

    script_path = _generate_vspreview_script(
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

    script_path = _generate_vspreview_script(
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

    monkeypatch.setattr("frame_compare.vspreview.adapter.write_text_atomic", _fake_write)

    script_path = _generate_vspreview_script(
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

    monkeypatch.setattr("frame_compare.vspreview.adapter.datetime", MockDatetime)

    timestamp = "20260520T194500Z"
    sessions_dir = tmp_path / "vspreview_sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    # Pre-create the first two candidates
    first_path = sessions_dir / f"vspreview_ref_{timestamp}.py"
    first_path.touch()
    second_path = sessions_dir / f"vspreview_ref_{timestamp}_1.py"
    second_path.touch()

    # Call the generator
    script_path = _generate_vspreview_script(
        reference=Path("ref.mkv"),
        comparisons=[Path("a.mkv")],
        suggested_offsets_by_key={},
        cache_dir=tmp_path,
    )

    # Verify it used the next suffix (_2)
    assert script_path == sessions_dir / f"vspreview_ref_{timestamp}_2.py"
    assert script_path.exists()


def test_build_script_content_assert_by_section() -> None:
    """Verify that the generated script contains the expected major sections."""
    reference = Path("ref.mkv")
    comparisons = [Path("comp_a.mkv"), Path("comp_b.mkv")]
    suggested_offsets = {"ref:comp_a": 10, "ref:comp_b": -5}
    bootstrap_paths = [Path("/w"), Path("/w/src")]

    script = _build_script_content(reference, comparisons, suggested_offsets, bootstrap_paths)
    assert script.startswith("#!/usr/bin/env python3\n")
    assert '"""VSPreview alignment verification session.' in script
    assert "# ─── sys.path Bootstrap " in script
    assert "# ─── Safe Print Helper " in script
    assert "# ─── Clip Data " in script
    assert "# ─── Main " in script
    assert script.index("# ─── sys.path Bootstrap ") < script.index("# ─── Safe Print Helper ")
    assert script.index("# ─── Safe Print Helper ") < script.index("# ─── Clip Data ")
    assert script.index("# ─── Clip Data ") < script.index("# ─── Main ")
    assert json.dumps(str(bootstrap_paths[0])) in script
    assert json.dumps(str(bootstrap_paths[1])) in script
    assert "def safe_print(*args, **kwargs):" in script
    assert "def resolve_lwlibavsource(core):" in script
    assert '"label": "ref"' in script
    assert '"comp_a": "comp_a.mkv"' in script
    assert '"ref:comp_a": 10' in script
    assert '"comp_a": 10' in script
    assert "def main():" in script
    assert script.rstrip().endswith("main()")


def test_check_vspreview_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    from frame_compare.vspreview.adapter import (
        VSPreviewAvailabilityStatus,
        check_vspreview_availability,
    )

    # 1. Executable available
    monkeypatch.setattr(
        "shutil.which", lambda cmd: "/usr/bin/vspreview" if cmd == "vspreview" else None
    )
    res = check_vspreview_availability()
    assert res.status == VSPreviewAvailabilityStatus.AVAILABLE
    assert res.is_available is True

    # 2. Executable missing, but module and PySide6 available
    monkeypatch.setattr("shutil.which", lambda cmd: None)

    def mock_find_spec(name: str):
        if name in ("vspreview", "PySide6"):
            from importlib.machinery import ModuleSpec

            return ModuleSpec(name, None)
        return None

    monkeypatch.setattr("importlib.util.find_spec", mock_find_spec)
    res = check_vspreview_availability()
    assert res.status == VSPreviewAvailabilityStatus.AVAILABLE
    assert res.is_available is True

    # 3. Executable missing, module present, but no Qt backend
    def mock_find_spec_no_qt(name: str):
        if name == "vspreview":
            from importlib.machinery import ModuleSpec

            return ModuleSpec(name, None)
        return None

    monkeypatch.setattr("importlib.util.find_spec", mock_find_spec_no_qt)
    res = check_vspreview_availability()
    assert res.status == VSPreviewAvailabilityStatus.MISSING_QT_BACKEND
    assert res.is_available is False
    assert "Qt backend missing" in res.message
    assert res.hint == "Install with: pip install PySide6 (or: pip install PyQt5)"
    assert "VSPreview not installed" not in res.message

    # 4. Nothing available
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    res = check_vspreview_availability()
    assert res.status == VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE
    assert res.is_available is False

    # 5. Unexpected exception
    def mock_find_spec_error(name: str):
        raise ValueError("simulated import error")

    monkeypatch.setattr("importlib.util.find_spec", mock_find_spec_error)
    res = check_vspreview_availability()
    assert res.status == VSPreviewAvailabilityStatus.PROBE_FAILED
    assert res.is_available is False
    assert res.error_details is not None
    assert res.error_details["exception_type"] == "ValueError"
    assert res.error_details["exception"] == "simulated import error"
