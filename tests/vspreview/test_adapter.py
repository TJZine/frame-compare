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
    monkeypatch.setattr("frame_compare.vspreview.adapter.is_vspreview_available", lambda: True)
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
    """Verify that script content is correctly split into sections and assembled."""
    reference = Path("ref.mkv")
    comparisons = [Path("comp_a.mkv"), Path("comp_b.mkv")]
    suggested_offsets = {"ref:comp_a": 10, "ref:comp_b": -5}
    bootstrap_paths = [Path("/w"), Path("/w/src")]

    # Direct validation of section content/structure
    from frame_compare.vspreview.adapter import (
        _build_bootstrap_section,
        _build_clip_data_section,
        _build_helpers_section,
        _build_main_execution_section,
        _build_script_header,
    )

    header = _build_script_header()
    assert "#!/usr/bin/env python3" in header
    assert '"""VSPreview alignment verification session.' in header

    bootstrap = _build_bootstrap_section(bootstrap_paths)
    assert (
        "# ─── sys.path Bootstrap ───────────────────────────────────────────────────────"
        in bootstrap
    )
    assert '"/w"' in bootstrap
    assert '"/w/src"' in bootstrap

    helpers = _build_helpers_section()
    assert (
        "# ─── Safe Print Helper ────────────────────────────────────────────────────────"
        in helpers
    )
    assert "def safe_print(*args, **kwargs):" in helpers
    assert "def resolve_lwlibavsource(core):" in helpers

    clip_data = _build_clip_data_section(reference, comparisons, suggested_offsets)
    assert (
        "# ─── Clip Data ────────────────────────────────────────────────────────────────"
        in clip_data
    )
    assert '"label": "ref"' in clip_data
    assert '"comp_a": "comp_a.mkv"' in clip_data
    assert '"ref:comp_a": 10' in clip_data
    assert '"comp_a": 10' in clip_data

    main_section = _build_main_execution_section()
    assert (
        "# ─── Main ─────────────────────────────────────────────────────────────────────"
        in main_section
    )
    assert "def main():" in main_section
    assert "if __name__ == '__main__':" not in main_section  # it should be "__main__"

    # Assemble and verify complete script matches the output of _build_script_content
    script = _build_script_content(reference, comparisons, suggested_offsets, bootstrap_paths)
    assert script.startswith(header)
    assert bootstrap in script
    assert helpers in script
    assert clip_data in script
    assert script.endswith(main_section)
