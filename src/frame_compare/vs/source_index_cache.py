"""Own the on-disk L-SMASH index transaction for one workspace."""

from __future__ import annotations

import json
import logging
import os
import secrets
import stat
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import file_digest, sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict

from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.file_lock import exclusive_file_lock
from frame_compare.vs.runtime_contract import index_cache_token

log = logging.getLogger(__name__)


class _IndexMetadata(TypedDict):
    schema_version: int
    source_key: str
    runtime_token: str
    source_device: int
    source_inode: int
    source_size: int
    source_mtime_ns: int
    source_change_time: int
    index_size: int
    index_sha256: str


@dataclass(frozen=True, slots=True)
class _Entry:
    source: Path
    key: str
    index: Path
    metadata: Path
    lock: Path


@dataclass(frozen=True, slots=True)
class _SourceIdentity:
    device: int
    inode: int
    size: int
    mtime_ns: int
    change_time: int


def _redirected(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _directory_info(path: Path) -> os.stat_result:
    info = path.lstat()
    if _redirected(info) or not stat.S_ISDIR(info.st_mode):
        raise OSError("Source index directory is not a real directory")
    return info


def _regular_info(path: Path) -> os.stat_result:
    info = path.lstat()
    if _redirected(info) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise OSError("Source index entry is not an owned regular file")
    return info


def is_unredirected_index_leaf(path: Path) -> bool:
    """Check that a previously validated path still names a local regular file."""
    try:
        return path.resolve(strict=True) == path and _regular_info(path).st_size > 0
    except (OSError, RuntimeError, ValueError):
        return False


@contextmanager
def private_index_directory() -> Generator[Path]:
    """Isolate cache-free native calls from any existing on-disk index."""
    with TemporaryDirectory(prefix="frame-compare-no-index-") as directory:
        yield Path(directory)


class ManagedSourceIndexCache:
    """Use a validated committed index or build one under a private lease."""

    def __init__(self, generated_root: Path, *, lock_timeout_seconds: float = 30.0) -> None:
        self._generated_root = generated_root
        self.root = generated_root / "cache" / "source-indexes"
        self.runtime_token = index_cache_token()
        self._lock_timeout_seconds = lock_timeout_seconds

    def _entry(self, path: Path) -> _Entry:
        source = path.resolve(strict=True)
        identity = os.fsencode(os.path.normcase(source))
        key = sha256(identity + b"\0" + self.runtime_token.encode("ascii")).hexdigest()
        return _Entry(
            source,
            key,
            self.root / f"{key}.lwi",
            self.root / f"{key}.json",
            self.root / f"{key}.lock",
        )

    def _check_root(self, *, create: bool) -> None:
        # Use the preflight-resolved owner as the anchor. Cache components may
        # not redirect even to a sibling inside generated data.
        if self._generated_root.resolve() != self._generated_root:
            raise OSError("Source index cache owner is redirected")
        if create:
            self._generated_root.mkdir(parents=True, exist_ok=True)
        for directory in (self._generated_root, self.root.parent, self.root):
            if create and directory != self._generated_root:
                directory.mkdir(mode=0o700, exist_ok=True)
            _directory_info(directory)

    @contextmanager
    def _lease(
        self, path: Path, *, create: bool, abort_check: Callable[[], None] = raise_if_cancelling
    ) -> Generator[_Entry]:
        abort_check()
        self._check_root(create=create)
        entry = self._entry(path)
        try:
            _regular_info(entry.lock)
        except FileNotFoundError:
            if not create:
                raise
        with exclusive_file_lock(
            entry.lock, timeout_seconds=self._lock_timeout_seconds, abort_check=abort_check
        ):
            self._check_root(create=False)
            yield entry

    def _metadata(self, entry: _Entry, source: _SourceIdentity, index_path: Path) -> _IndexMetadata:
        index = _regular_info(index_path)
        if index.st_size <= 0:
            raise OSError("Source index is empty")
        with index_path.open("rb") as handle:
            digest = file_digest(handle, "sha256").hexdigest()
        return {
            "schema_version": 3,
            "source_key": entry.key,
            "runtime_token": self.runtime_token,
            "source_device": source.device,
            "source_inode": source.inode,
            "source_size": source.size,
            "source_mtime_ns": source.mtime_ns,
            "source_change_time": source.change_time,
            "index_size": index.st_size,
            "index_sha256": digest,
        }

    def _is_valid(self, entry: _Entry, source: _SourceIdentity) -> bool:
        try:
            # Metadata contains only fixed-size fields. Bound reads of damaged files.
            if _regular_info(entry.metadata).st_size > 4096:
                return False
            with entry.metadata.open("rb") as handle:
                metadata = handle.read(4097)
            expected = json.dumps(self._metadata(entry, source, entry.index), sort_keys=True)
            return metadata == expected.encode("ascii")
        except OSError:
            return False

    def validated_index(self, path: Path) -> Path | None:
        """Return a current committed index for read-only consumers, if available."""
        try:
            with self._lease(path, create=False) as entry:
                source = _source_identity(entry.source)
                if self._is_valid(entry, source) and _same_source(path, entry.source, source):
                    return entry.index
        except (OSError, RuntimeError, ValueError):
            pass
        return None

    def try_open_validated[T](
        self,
        path: Path,
        expected_index: Path,
        open_source: Callable[[Path, int, Path], T],
        *,
        abort_check: Callable[[], None] = raise_if_cancelling,
    ) -> T | None:
        """Open an existing index only while its owner lease and authority remain valid."""
        try:
            with self._lease(path, create=False, abort_check=abort_check) as entry:
                if expected_index != entry.index:
                    return None
                source = _source_identity(entry.source)
                if not self._is_valid(entry, source) or not _same_source(
                    path, entry.source, source
                ):
                    return None
                abort_check()
                return _try_open(open_source, entry.source, 0, entry.index)
        except (OSError, RuntimeError, ValueError) as error:
            log.debug("Managed L-SMASH index could not be reopened: %s", type(error).__name__)
            return None

    def try_load[T](
        self,
        path: Path,
        open_source: Callable[[Path, int, Path], T],
        *,
        abort_check: Callable[[], None] = raise_if_cancelling,
    ) -> T | None:
        """Open through this cache. A miss with failed construction needs a private retry."""
        try:
            with self._lease(path, create=True, abort_check=abort_check) as entry:
                source = _source_identity(entry.source)
                if self._is_valid(entry, source) and _same_source(path, entry.source, source):
                    abort_check()
                    return _try_open(open_source, entry.source, 0, entry.index)
                return self._build(path, entry, source, open_source, abort_check)
        except (OSError, RuntimeError, ValueError) as error:
            log.debug("Managed L-SMASH index unavailable: %s", type(error).__name__)
            return None

    def _build[T](
        self,
        path: Path,
        entry: _Entry,
        source: _SourceIdentity,
        open_source: Callable[[Path, int, Path], T],
        abort_check: Callable[[], None],
    ) -> T | None:
        with self._stage() as (directory, stage_info):
            index_path = directory / "index.lwi"
            metadata_path = directory / "metadata.json"
            abort_check()
            clip = _try_open(open_source, entry.source, 1, index_path)
            if clip is None:
                return None
            abort_check()
            self._check_root(create=False)
            if not os.path.samestat(stage_info, _directory_info(directory)):
                return None
            _sync_regular_file(index_path)
            metadata = self._metadata(entry, source, index_path)
            with metadata_path.open("x", encoding="ascii") as handle:
                json.dump(metadata, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            abort_check()
            if not _same_source(path, entry.source, source):
                return None
            # Replace directory entries directly. In particular, never open a
            # rejected stable leaf (which could be a link) for writing.
            entry.metadata.unlink(missing_ok=True)
            os.replace(index_path, entry.index)
            _sync_directory(self.root)
            abort_check()
            if not _same_source(path, entry.source, source):
                return None
            os.replace(metadata_path, entry.metadata)
            _sync_directory(self.root)
            return clip

    @contextmanager
    def _stage(self) -> Generator[tuple[Path, os.stat_result]]:
        directory = self.root / f".stage-{secrets.token_hex(16)}"
        directory.mkdir(mode=0o700)
        stage_info = _directory_info(directory)
        try:
            yield directory, stage_info
        finally:
            try:
                self._check_root(create=False)
                if os.path.samestat(stage_info, _directory_info(directory)):
                    (directory / "index.lwi").unlink(missing_ok=True)
                    (directory / "metadata.json").unlink(missing_ok=True)
                    directory.rmdir()
            except OSError as error:
                log.debug("Could not clean private L-SMASH index staging: %s", type(error).__name__)


def _source_identity(path: Path) -> _SourceIdentity:
    if os.name == "nt":
        with path.open("rb") as handle:
            info = os.fstat(handle.fileno())
            change_time = _windows_change_time(handle.fileno())
    else:
        info = path.stat()
        change_time = info.st_ctime_ns
    return _SourceIdentity(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, change_time)


def _windows_change_time(fd: int) -> int:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _FileBasicInfo(ctypes.Structure):
        _fields_ = [
            ("creation_time", ctypes.c_longlong),
            ("last_access_time", ctypes.c_longlong),
            ("last_write_time", ctypes.c_longlong),
            ("change_time", ctypes.c_longlong),
            ("file_attributes", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_volume_info = kernel32.GetVolumeInformationByHandleW
    get_volume_info.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.LPDWORD,
        wintypes.LPDWORD,
        wintypes.LPDWORD,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    get_volume_info.restype = wintypes.BOOL
    get_file_info = kernel32.GetFileInformationByHandleEx
    get_file_info.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    get_file_info.restype = wintypes.BOOL

    handle = msvcrt.get_osfhandle(fd)
    filesystem = ctypes.create_unicode_buffer(261)  # MAX_PATH + 1
    if not get_volume_info(handle, None, 0, None, None, None, filesystem, len(filesystem)):
        raise ctypes.WinError(ctypes.get_last_error())
    # Filesystems without NTFS change-time semantics use the cache-free path.
    if filesystem.value != "NTFS":
        raise OSError("Managed source indexes on Windows require NTFS change time")
    basic = _FileBasicInfo()
    if not get_file_info(handle, 0, ctypes.byref(basic), ctypes.sizeof(basic)):  # FileBasicInfo
        raise ctypes.WinError(ctypes.get_last_error())
    if basic.change_time <= 0:
        raise OSError("Source change time is unavailable")
    return basic.change_time


def _same_source(path: Path, resolved: Path, before: _SourceIdentity) -> bool:
    return path.resolve(strict=True) == resolved and _source_identity(resolved) == before


def _sync_regular_file(path: Path) -> None:
    expected = _regular_info(path)
    # Windows fsync requires a write-capable handle. The staged bytes must survive.
    with path.open("r+b" if os.name == "nt" else "rb") as handle:
        if not os.path.samestat(expected, os.fstat(handle.fileno())):
            raise OSError("Source index changed before durable publication")
        os.fsync(handle.fileno())


def _sync_directory(path: Path) -> None:
    """Persist publication ordering where directory fsync is supported."""
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _try_open[T](
    open_source: Callable[[Path, int, Path], T], source: Path, cache: int, index: Path
) -> T | None:
    try:
        return open_source(source, cache, index)
    except Exception as error:
        log.debug("L-SMASH rejected managed index operation: %s", type(error).__name__)
        return None
