from pathlib import Path
from typing import cast

import pytest

from frame_compare.utils.atomic_write import write_bytes_atomic, write_text_atomic


def test_write_text_atomic_replaces_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "out.toml"
    target.write_text("old", encoding="utf-8")

    write_text_atomic(target, "new", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "new"


@pytest.mark.parametrize(("filename", "content"), [("out.txt", ""), ("out.bin", b"")])
def test_atomic_write_empty_content(tmp_path: Path, filename: str, content: str | bytes) -> None:
    target = tmp_path / filename
    if isinstance(content, str):
        write_text_atomic(target, content, encoding="utf-8")
        assert target.read_text(encoding="utf-8") == ""
    else:
        write_bytes_atomic(target, content)
        assert target.read_bytes() == b""


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


@pytest.mark.parametrize("filename", ["out.txt", "out.bin"])
def test_atomic_write_rejects_none_and_cleans_up(tmp_path: Path, filename: str) -> None:
    target = tmp_path / filename
    with pytest.raises(TypeError):
        if filename == "out.txt":
            write_text_atomic(target, cast(str, None), encoding="utf-8")
        else:
            write_bytes_atomic(target, cast(bytes, None))
    assert not target.exists()
    assert list(tmp_path.glob(f".{filename}.*")) == []


def test_write_text_atomic_cleans_up_on_fsync_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.txt"

    def _boom(_fd: int) -> None:
        raise OSError("fsync failed")

    monkeypatch.setattr("frame_compare.utils.atomic_write.os.fsync", _boom)

    with pytest.raises(OSError, match="fsync failed"):
        write_text_atomic(target, "content", encoding="utf-8")

    assert not target.exists()
    assert list(tmp_path.glob(".out.txt.*")) == []


def test_write_bytes_atomic_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "data.bin"

    write_bytes_atomic(target, b"abc")

    assert target.read_bytes() == b"abc"


def test_write_bytes_atomic_preserves_existing_file_permissions(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    target.write_bytes(b"old")
    target.chmod(0o640)
    expected_mode = target.stat().st_mode & 0o777

    write_bytes_atomic(target, b"new")

    assert target.read_bytes() == b"new"
    assert (target.stat().st_mode & 0o777) == expected_mode


@pytest.mark.parametrize(
    ("filename", "error_type"),
    [("out.toml", OSError), ("out.bin", PermissionError)],
)
def test_atomic_write_preserves_target_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    error_type: type[OSError],
) -> None:
    target = tmp_path / filename
    target.write_bytes(b"old")

    def fail_replace(_src: str, _dst: Path) -> None:
        raise error_type("replace failed")

    monkeypatch.setattr("frame_compare.utils.atomic_write.os.replace", fail_replace)
    with pytest.raises(error_type, match="replace failed"):
        if filename == "out.toml":
            write_text_atomic(target, "new", encoding="utf-8")
        else:
            write_bytes_atomic(target, b"new")
    assert target.read_bytes() == b"old"
    assert list(tmp_path.glob(f".{filename}.*")) == []


def test_write_text_atomic_does_not_mask_replace_failure_when_cleanup_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "out.toml"
    target.write_text("old", encoding="utf-8")
    original_unlink = Path.unlink

    def _fail_replace(_src: str, _dst: Path) -> None:
        raise OSError("replace failed")

    def _fail_cleanup(self: Path, *, missing_ok: bool = False) -> None:
        if self.name.startswith(".out.toml."):
            raise PermissionError("cleanup failed")
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr("frame_compare.utils.atomic_write.os.replace", _fail_replace)
    monkeypatch.setattr("frame_compare.utils.atomic_write.Path.unlink", _fail_cleanup)

    with pytest.raises(OSError, match="replace failed") as exc_info:
        write_text_atomic(target, "new", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "old"
    assert "cleanup failed" in "\n".join(exc_info.value.__notes__)
