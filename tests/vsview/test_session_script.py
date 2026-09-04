from __future__ import annotations

from pathlib import Path

import pytest

from frame_compare.vsview.session_script import write_vsview_session_script


def test_write_vsview_session_script_removes_reserved_path_after_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(
        "frame_compare.vsview.session_script.write_text_atomic",
        fail_write,
    )

    with pytest.raises(OSError, match="disk full"):
        write_vsview_session_script(
            reference=Path("ref.mkv"),
            comparisons=[Path("comparison.mkv")],
            suggested_offsets_by_key={"ref:comparison": 0},
            cache_dir=tmp_path,
        )

    sessions_dir = tmp_path / "vsview_sessions"
    assert sessions_dir.is_dir()
    assert list(sessions_dir.iterdir()) == []
