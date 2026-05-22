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


def test_write_text_atomic_uses_normal_new_file_permissions(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"

    write_text_atomic(target, "content", encoding="utf-8")

    expected = tmp_path / "expected.txt"
    expected.write_text("content", encoding="utf-8")
    assert (target.stat().st_mode & 0o777) == (expected.stat().st_mode & 0o777)


def test_write_text_atomic_does_not_read_process_umask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.txt"

    def _fail_umask(_mask: int) -> int:
        raise AssertionError("atomic writes must not mutate process umask")

    monkeypatch.setattr("frame_compare.utils.atomic_write.os.umask", _fail_umask)

    write_text_atomic(target, "content", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "content"


def test_write_text_atomic_rejects_none_and_cleans_up(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"

    with pytest.raises(TypeError):
        write_text_atomic(target, None, encoding="utf-8")  # type: ignore[arg-type]

    assert not target.exists()
    assert list(tmp_path.glob(".out.txt.*")) == []


def test_write_bytes_atomic_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "data.bin"

    write_bytes_atomic(target, b"abc")

    assert target.read_bytes() == b"abc"


def test_write_bytes_atomic_writes_empty(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"

    write_bytes_atomic(target, b"")

    assert target.read_bytes() == b""


def test_write_bytes_atomic_rejects_none_and_cleans_up(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"

    with pytest.raises(TypeError):
        write_bytes_atomic(target, None)  # type: ignore[arg-type]

    assert not target.exists()
    assert list(tmp_path.glob(".out.bin.*")) == []


def test_write_bytes_atomic_preserves_existing_file_permissions(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    target.write_bytes(b"old")
    target.chmod(0o640)

    write_bytes_atomic(target, b"new")

    assert target.read_bytes() == b"new"
    assert (target.stat().st_mode & 0o777) == 0o640


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
