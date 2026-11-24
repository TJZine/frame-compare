"""Bounded archive and Windows path handling for the portable assembler."""

from __future__ import annotations

import hashlib
import re
import stat
import struct
import zipfile
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

MAX_ARCHIVE = 1024**3
MAX_MEMBER = 256 * 1024**2
MAX_EXPANDED = 2 * 1024**3
MAX_ENTRIES = 20000
MAX_DIRECTORY = 8 * 1024**2
CHUNK = 1024**2

_DEVICE = re.compile(r"(?:con|conin\$|conout\$|prn|aux|nul|com[0-9]|lpt[0-9])", re.I)
_UNSAFE = re.compile(r'[\\:*?"<>|~\x00-\x1f\x7f]')


def check_path(name: str) -> str:
    # The pinned layout is ASCII. This also excludes Unicode aliases and the
    # tilde used by DOS short-name aliases on Windows volumes.
    parts = name.split("/")
    if (
        not name.isascii()
        or len(name) > 512
        or len(parts) > 32
        or _UNSAFE.search(name)
        or any(
            not part
            or len(part) > 240
            or part.endswith((".", " "))
            or _DEVICE.fullmatch(part.split(".")[0].rstrip(" "))
            for part in parts
        )
    ):
        raise ValueError(f"Unsafe portable member path: {name!r}")
    return name


class PathIndex:
    """Tracks exact path spelling, including implicit directory components."""

    def __init__(self) -> None:
        self.files: set[str] = set()
        self.directories: set[str] = set()
        self._spellings: dict[str, str] = {}

    def _register(self, name: str) -> None:
        if self._spellings.setdefault(name.lower(), name) != name:
            raise ValueError(f"Case-colliding portable member: {name}")

    def add(self, name: str, *, directory: bool = False) -> None:
        check_path(name)
        self._register(name)
        if name in self.files or (not directory and name in self.directories):
            raise ValueError(f"Conflicting or duplicate portable member: {name}")
        parent = name
        while "/" in parent:
            parent = parent.rsplit("/", 1)[0]
            self._register(parent)
            if parent in self.files:
                raise ValueError(f"Portable member has a file as parent: {name}")
            self.directories.add(parent)
        (self.directories if directory else self.files).add(name)


def copy_exact(source: BinaryIO, length: int, target: BinaryIO | None = None) -> str:
    digest = hashlib.sha256()
    remaining = length
    while remaining:
        block = source.read(min(remaining, CHUNK))
        if not block:
            raise ValueError("Truncated portable input")
        remaining -= len(block)
        digest.update(block)
        if target is not None:
            target.write(block)
    if source.read(1):
        raise ValueError("Portable input exceeds its declared size")
    return digest.hexdigest()


def digest_file(path: Path) -> str:
    with path.open("rb") as source:
        return copy_exact(source, path.stat().st_size)


def _zip_directory(source: BinaryIO) -> tuple[int, int]:
    length = source.seek(0, 2)
    if not 22 <= length <= MAX_ARCHIVE:
        raise ValueError("Portable ZIP exceeds archive size limits")
    # Our formats have either no comment or the git archive commit comment.
    source.seek(-min(length, 62), 2)
    tail = source.read()
    end = tail.rfind(b"PK\x05\x06")
    if end < 0 or len(tail) - end < 22:
        raise ValueError("Missing portable ZIP end record")
    disk, start_disk, disk_count, count, size, offset, comment = struct.unpack_from(
        "<HHHHIIH", tail, end + 4
    )
    if (
        disk
        or start_disk
        or count != disk_count
        or count > MAX_ENTRIES
        or size > MAX_DIRECTORY
        or comment not in (0, 40)
        or len(tail) - end != 22 + comment
        or (comment and not re.fullmatch(rb"[a-f0-9]{40}", tail[-comment:]))
        or offset + size != length - 22 - comment
    ):
        raise ValueError("Unsupported or overlong portable ZIP directory")
    end_offset = length - 22 - comment
    if end_offset >= 20:
        source.seek(end_offset - 20)
        if source.read(4) == b"PK\x06\x07":
            raise ValueError("ZIP64 is outside the portable archive format")
    return count, offset


def _validate_extras(extra: bytes) -> None:
    # Only timestamp and ownership metadata used by the pinned FFmpeg archive
    # are allowed. No path aliases, alternate sizes or special-file records.
    seen = set()
    while extra:
        if len(extra) < 4:
            raise ValueError("Truncated portable ZIP extra field")
        kind, size = struct.unpack_from("<HH", extra)
        if kind not in (0x5455, 0x7875) or kind in seen or size > len(extra) - 4:
            raise ValueError("Unsupported or ambiguous portable ZIP extra field")
        seen.add(kind)
        extra = extra[4 + size :]


def _validate_stream(source: BinaryIO, offset: int, entry: zipfile.ZipInfo) -> None:
    # ZipExtFile stops at the declared expanded length. Check the raw stream
    # too so a prefix with a valid CRC cannot hide additional inflated bytes.
    source.seek(offset)
    remaining = entry.compress_size
    produced = crc = 0
    decompressor = zlib.decompressobj(-15) if entry.compress_type == zipfile.ZIP_DEFLATED else None
    while remaining:
        chunk = source.read(min(remaining, 65536))
        if not chunk:
            raise ValueError("Truncated portable ZIP compressed data")
        remaining -= len(chunk)
        while chunk:
            if decompressor is None:
                block, chunk = chunk, b""
            else:
                block = decompressor.decompress(chunk, min(CHUNK, entry.file_size - produced + 1))
                chunk = decompressor.unconsumed_tail
                if decompressor.unused_data or (decompressor.eof and (remaining or chunk)):
                    raise ValueError(
                        f"Extra compressed data in portable ZIP member: {entry.filename}"
                    )
            produced += len(block)
            if produced > entry.file_size:
                raise ValueError(f"Portable ZIP member exceeds declared size: {entry.filename}")
            crc = zlib.crc32(block, crc)
    if produced != entry.file_size or crc != entry.CRC or (decompressor and not decompressor.eof):
        raise ValueError(f"Portable ZIP stream does not match its directory: {entry.filename}")


@contextmanager
def checked_zip(path: Path) -> Iterator[zipfile.ZipFile]:
    with path.open("rb") as source:
        count, offset = _zip_directory(source)
        with zipfile.ZipFile(source) as archive:
            index = PathIndex()
            members: set[str] = set()
            total = 0
            ranges: list[tuple[int, int, int, zipfile.ZipInfo]] = []
            for entry in archive.infolist():
                name = entry.orig_filename
                directory = name.endswith("/")
                mode = stat.S_IFMT(entry.external_attr >> 16)
                attrs = entry.external_attr & 0xFFFF
                if (
                    name in members
                    or entry.filename != name
                    or attrs & 0x400
                    or (directory and (mode not in (0, stat.S_IFDIR) or entry.file_size))
                    or (not directory and (mode not in (0, stat.S_IFREG) or attrs & 0x10))
                    or entry.flag_bits & ~0x80E
                    or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                ):
                    raise ValueError(f"Unsafe or duplicate portable ZIP member: {name!r}")
                members.add(name)
                index.add(name.removesuffix("/"), directory=directory)
                total += entry.file_size
                if (
                    entry.file_size > MAX_MEMBER
                    or total > MAX_EXPANDED
                    or entry.file_size > 1000 * max(1, entry.compress_size)
                ):
                    raise ValueError("Portable ZIP exceeds expanded size limits")
                start = entry.header_offset
                if not 0 <= start <= offset - 30:
                    raise ValueError("Invalid portable ZIP local header offset")
                source.seek(start)
                header = source.read(30)
                if header[:4] != b"PK\x03\x04":
                    raise ValueError("Invalid portable ZIP local header")
                flags, method = struct.unpack_from("<HH", header, 6)
                crc, compressed, expanded, name_size, extra = struct.unpack_from(
                    "<IIIHH", header, 14
                )
                data_offset = start + 30 + name_size + extra
                end = data_offset + entry.compress_size
                if (
                    flags != entry.flag_bits
                    or method != entry.compress_type
                    or source.read(name_size) != name.encode("ascii")
                    or end > offset
                ):
                    raise ValueError(f"Ambiguous portable ZIP member: {name}")
                _validate_extras(entry.extra)
                _validate_extras(source.read(extra))
                if entry.comment:
                    raise ValueError(f"Unsupported portable ZIP member comment: {name}")
                if flags & 8:
                    source.seek(end)
                    descriptor = source.read(16)
                    if descriptor.startswith(b"PK\x07\x08"):
                        end += 4
                        descriptor = descriptor[4:]
                    end += 12
                    if descriptor[:12] != struct.pack(
                        "<III", entry.CRC, entry.compress_size, entry.file_size
                    ):
                        raise ValueError(f"Invalid portable ZIP data descriptor: {name}")
                    if (crc, compressed, expanded) != (0, 0, 0):
                        raise ValueError(f"Ambiguous portable ZIP data descriptor: {name}")
                elif (crc, compressed, expanded) != (
                    entry.CRC,
                    entry.compress_size,
                    entry.file_size,
                ):
                    raise ValueError(f"Inconsistent portable ZIP member sizes: {name}")
                ranges.append((start, end, data_offset, entry))
            cursor = 0
            for start, end, _, _ in sorted(ranges, key=lambda value: value[0]):
                if start != cursor:
                    raise ValueError("Portable ZIP has overlapping or hidden local entries")
                cursor = end
            if cursor != offset or len(members) != count:
                raise ValueError("Portable ZIP entry count or local directory mismatch")
            for _, _, data_offset, entry in ranges:
                _validate_stream(source, data_offset, entry)
            yield archive


def read_member(archive: zipfile.ZipFile, name: str, limit: int) -> bytes:
    entry = archive.getinfo(name)
    if entry.file_size > limit:
        raise ValueError(f"Portable metadata exceeds size limit: {name}")
    with archive.open(entry) as source:
        data = source.read(limit + 1)
    if len(data) != entry.file_size:
        raise ValueError(f"Truncated portable metadata: {name}")
    return data
