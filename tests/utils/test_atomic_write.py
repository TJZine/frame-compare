from pathlib import Path

import pytest

from frame_compare.utils.atomic_write import write_bytes_atomic, write_text_atomic


def test_write_text_atomic_replaces_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "out.toml"
    target.write_text("old", encoding="utf-8")

    write_text_atomic(target, "new", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "new"


def test_write_text_atomic_writes_empty(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"

    write_text_atomic(target, "", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == ""


def test_write_bytes_atomic_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "data.bin"

    write_bytes_atomic(target, b"abc")

    assert target.read_bytes() == b"abc"


def test_write_bytes_atomic_writes_empty(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"

    write_bytes_atomic(target, b"")

    assert target.read_bytes() == b""


def test_write_text_atomic_does_not_replace_target_on_os_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.toml"
    target.write_text("old", encoding="utf-8")

    def _boom(_src: str, _dst: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("frame_compare.utils.atomic_write.os.replace", _boom)

    with pytest.raises(OSError, match="replace failed"):
        write_text_atomic(target, "new", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob(".out.toml.*")) == []


def test_write_bytes_atomic_does_not_replace_target_on_os_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.bin"
    target.write_bytes(b"old")

    def _boom(_src: str, _dst: Path) -> None:
        raise PermissionError("replace failed")

    monkeypatch.setattr("frame_compare.utils.atomic_write.os.replace", _boom)

    with pytest.raises(PermissionError, match="replace failed"):
        write_bytes_atomic(target, b"new")

    assert target.read_bytes() == b"old"
    assert list(tmp_path.glob(".out.bin.*")) == []
