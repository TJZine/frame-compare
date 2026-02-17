"""Unit tests for VSPreview adapter launch behavior.

These tests do NOT require VSPreview, VapourSynth, FFmpeg, or any display.
"""

from __future__ import annotations

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
    )

    compile(script, "<vspreview>", "exec")
    assert '"label": "ref"x"' not in script
    assert '"\nprint(123)\n#' not in script
    assert "\\nprint(123)\\n" in script


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
