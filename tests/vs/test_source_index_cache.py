from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

import pytest

from frame_compare.utils.file_lock import exclusive_file_lock
from frame_compare.vs.source_admission import SourceAdmission, SourceGeometryError
from frame_compare.vs.source_index_cache import ManagedSourceIndexCache


@pytest.fixture
def source(tmp_path: Path) -> Path:
    media = tmp_path.resolve() / "media"
    media.mkdir()
    path = media / "source.mkv"
    path.write_bytes(b"video")
    return path


@pytest.fixture
def cache(tmp_path: Path) -> ManagedSourceIndexCache:
    return ManagedSourceIndexCache(tmp_path.resolve() / "generated")


@pytest.fixture
def admission() -> MagicMock:
    return MagicMock(spec=SourceAdmission, geometry_probe_token="a" * 64)


def _create_index(_source: Path, cache: int, index: Path) -> bool:
    if cache == 1:
        assert not index.exists()
        index.write_bytes(b"native index")
    return True


def _committed_index(cache: ManagedSourceIndexCache, source: Path, admission: MagicMock) -> Path:
    assert cache.try_load(source, _create_index, admission=admission, scan_frame_geometry=True)
    path = cache.validated_index(source)
    assert path is not None
    return path


def test_native_construction_only_targets_unique_private_staging_and_reuse_is_read_only(
    cache: ManagedSourceIndexCache, source: Path, admission: MagicMock
) -> None:
    calls: list[tuple[Path, int, Path]] = []

    def open_source(path: Path, mode: int, index: Path) -> bool:
        calls.append((path, mode, index))
        if mode == 1:
            assert index.parent.parent == cache.root
            assert list(index.parent.iterdir()) == []
        return _create_index(path, mode, index)

    assert cache.try_load(source, open_source, admission=admission)
    stable = cache.validated_index(source)
    assert stable is not None and stable.parent == cache.root
    before = stable.stat()
    assert cache.try_load(source, open_source, admission=admission)
    assert calls[1] == (source, 0, stable)
    assert stable.stat().st_mtime_ns == before.st_mtime_ns
    source.write_bytes(b"edited video")
    assert cache.try_load(source, open_source, admission=admission)
    assert [mode for _, mode, _ in calls] == [1, 0, 1]
    stages = [index for _, mode, index in calls if mode == 1]
    assert len({index.parent for index in stages}) == 2
    assert not any(index.parent.exists() for index in stages)
    assert cache.validated_index(source) == stable
    assert str(source) not in stable.with_suffix(".json").read_text(encoding="ascii")


def test_publication_replaces_managed_symlink_without_following_it(
    cache: ManagedSourceIndexCache, source: Path, admission: MagicMock, tmp_path: Path
) -> None:
    stable = _committed_index(cache, source, admission)
    stable.unlink()
    canary = tmp_path / "canary"
    canary.write_bytes(b"must survive")
    try:
        stable.symlink_to(canary)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    assert cache.validated_index(source) is None
    assert _committed_index(cache, source, admission) == stable
    assert not stable.is_symlink()
    assert canary.read_bytes() == b"must survive"


def test_redirected_cache_directory_is_unavailable(
    cache: ManagedSourceIndexCache, source: Path, admission: MagicMock, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    cache.root.parent.mkdir(parents=True)
    try:
        cache.root.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")
    assert cache.try_load(source, _create_index, admission=admission) is None
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "damage",
    ["bad-json", "wrong-token", "wrong-digest", "wrong-index", "legacy", "policy", "probe"],
)
def test_damaged_cache_entry_regenerates(
    cache: ManagedSourceIndexCache, source: Path, admission: MagicMock, damage: str
) -> None:
    stable = _committed_index(cache, source, admission)
    marker = stable.with_suffix(".json")
    original = marker.read_text(encoding="ascii")
    if damage == "bad-json":
        marker.write_bytes(b"{")
    elif damage == "wrong-token":
        metadata = json.loads(original)
        metadata["runtime_token"] = "unknown"
        marker.write_text(json.dumps(metadata, sort_keys=True), encoding="ascii")
    elif damage == "wrong-digest":
        metadata = json.loads(original)
        metadata["index_sha256"] = "0" * 64
        marker.write_text(json.dumps(metadata, sort_keys=True), encoding="ascii")
    elif damage == "wrong-index":
        stable.write_bytes(b"badbad index")
    else:
        metadata = json.loads(original)
        field, value = {
            "legacy": ("schema_version", 3),
            "policy": ("geometry_policy_version", 0),
            "probe": ("geometry_probe_token", "b" * 64),
        }[damage]
        metadata[field] = value
        if damage == "legacy":
            del metadata["geometry_policy_version"], metadata["geometry_probe_token"]
        marker.write_text(json.dumps(metadata, sort_keys=True), encoding="ascii")
    # A discovered path alone never grants native access.
    assert cache.try_open_validated(source, stable, _create_index, admission=admission) is None
    assert _committed_index(cache, source, admission) == stable
    assert admission.scan.call_count == 2
    assert marker.read_text(encoding="ascii") == original
    assert stable.read_bytes() == b"native index"


def test_atomic_same_size_same_mtime_source_replacement_invalidates_index(
    cache: ManagedSourceIndexCache, source: Path, admission: MagicMock, tmp_path: Path
) -> None:
    stable = _committed_index(cache, source, admission)
    original = source.stat()
    replacement = tmp_path / "replacement.mkv"
    replacement.write_bytes(b"other")
    os.utime(replacement, ns=(original.st_atime_ns, original.st_mtime_ns))
    os.replace(replacement, source)
    assert source.stat().st_size == original.st_size
    assert source.stat().st_mtime_ns == original.st_mtime_ns

    calls: list[int] = []

    def open_source(path: Path, mode: int, index: Path) -> bool:
        calls.append(mode)
        return _create_index(path, mode, index)

    assert cache.validated_index(source) is None
    assert cache.try_load(source, open_source, admission=admission)
    assert calls == [1]
    assert cache.validated_index(source) == stable


def _overwrite_with_restored_mtime(path: Path) -> None:
    before = path.stat()
    with path.open("r+b") as handle:
        handle.write(b"other")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = path.stat()
    assert os.path.samestat(before, after)
    assert after.st_size == before.st_size
    assert after.st_mtime_ns == before.st_mtime_ns


def test_cold_write_warm_hit_and_same_length_source_overwrite(
    cache: ManagedSourceIndexCache, source: Path, admission: MagicMock
) -> None:
    modes: list[int] = []

    def open_source(path: Path, mode: int, index: Path) -> bool:
        modes.append(mode)
        return _create_index(path, mode, index)

    assert cache.try_load(source, open_source, admission=admission, scan_frame_geometry=True)
    stable = cache.validated_index(source)
    assert stable is not None and stable.read_bytes() == b"native index"
    assert cache.try_load(source, open_source, admission=admission, scan_frame_geometry=True)
    assert modes == [1, 0]
    assert admission.scan.call_count == 1

    _overwrite_with_restored_mtime(source)
    assert cache.validated_index(source) is None
    assert cache.try_open_validated(source, stable, open_source, admission=admission) is None
    assert cache.try_load(source, open_source, admission=admission, scan_frame_geometry=True)
    assert modes == [1, 0, 1]
    assert admission.scan.call_count == 2
    assert cache.validated_index(source) == stable


def test_source_overwrite_after_index_replace_prevents_metadata_commit(
    cache: ManagedSourceIndexCache,
    source: Path,
    admission: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replace = os.replace

    def overwrite_after_index_replace(src: Path, dst: Path) -> None:
        replace(src, dst)
        if dst.suffix == ".lwi":
            _overwrite_with_restored_mtime(source)

    monkeypatch.setattr(os, "replace", overwrite_after_index_replace)
    assert cache.try_load(source, _create_index, admission=admission) is None
    assert cache.validated_index(source) is None
    assert not list(cache.root.glob("*.json"))
    assert not list(cache.root.glob(".stage-*"))


def test_validated_consumer_holds_lease_and_rejects_wrong_expected_path(
    cache: ManagedSourceIndexCache, source: Path, admission: MagicMock, tmp_path: Path
) -> None:
    stable = _committed_index(cache, source, admission)
    observed: list[tuple[Path, int, Path]] = []

    def open_source(path: Path, mode: int, index: Path) -> bool:
        observed.append((path, mode, index))
        with (
            pytest.raises(TimeoutError),
            exclusive_file_lock(stable.with_suffix(".lock"), timeout_seconds=0),
        ):
            pass
        return True

    assert cache.try_open_validated(source, stable, open_source, admission=admission)
    assert observed == [(source, 0, stable)]
    assert (
        cache.try_open_validated(source, tmp_path / "other.lwi", open_source, admission=admission)
        is None
    )
    assert observed == [(source, 0, stable)]


@pytest.mark.parametrize(
    "failure", ["source-mutated", "native-error", "cancelled", "publish-error"]
)
def test_failed_transaction_cleans_staging_and_never_commits(
    cache: ManagedSourceIndexCache,
    source: Path,
    admission: MagicMock,
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled = Event()

    def abort_check() -> None:
        if cancelled.is_set():
            raise InterruptedError

    def open_source(path: Path, mode: int, index: Path) -> bool:
        assert mode == 1
        _create_index(path, mode, index)
        if failure == "source-mutated":
            path.write_bytes(b"changed source")
        elif failure == "native-error":
            raise RuntimeError("failed to construct index")
        elif failure == "cancelled":
            cancelled.set()
        return True

    if failure == "publish-error":
        from frame_compare.vs import source_index_cache

        replace = source_index_cache.os.replace

        def reject_marker(src: Path, dst: Path) -> None:
            if dst.suffix == ".json":
                raise PermissionError("cannot publish marker")
            replace(src, dst)

        monkeypatch.setattr(source_index_cache.os, "replace", reject_marker)
    assert cache.try_load(source, open_source, admission=admission, abort_check=abort_check) is None
    assert cache.validated_index(source) is None
    assert not list(cache.root.glob(".stage-*"))
    assert not list(cache.root.glob("*.json"))


@pytest.mark.parametrize("failure", [SourceGeometryError("partial frame scan"), KeyboardInterrupt])
def test_incomplete_scan_never_opens_or_publishes_an_index(
    cache: ManagedSourceIndexCache,
    source: Path,
    admission: MagicMock,
    failure: BaseException | type[BaseException],
) -> None:
    admission.scan.side_effect = failure
    loader = MagicMock()
    with pytest.raises(failure if isinstance(failure, type) else type(failure)):
        cache.try_load(source, loader, admission=admission, scan_frame_geometry=True)
    loader.assert_not_called()
    assert not list(cache.root.glob("*.json"))
    assert not list(cache.root.glob("*.lwi"))
    assert not list(cache.root.glob(".stage-*"))


def test_opt_in_open_requires_scan_evidence_from_managed_index(
    cache: ManagedSourceIndexCache, source: Path, admission: MagicMock
) -> None:
    assert cache.try_load(source, _create_index, admission=admission)
    stable = cache.validated_index(source)
    assert stable is not None
    admission.scan.assert_not_called()
    assert cache.validated_index(source, scan_frame_geometry=True) is None
    native_open = MagicMock()
    assert (
        cache.try_open_validated(
            source, stable, native_open, admission=admission, scan_frame_geometry=True
        )
        is None
    )
    native_open.assert_not_called()

    assert cache.try_load(source, _create_index, admission=admission, scan_frame_geometry=True)
    assert cache.validated_index(source, scan_frame_geometry=True) == stable
    assert cache.try_load(source, _create_index, admission=admission, scan_frame_geometry=True)
    assert cache.try_load(source, _create_index, admission=admission)
    admission.scan.assert_called_once()


def test_lock_contention_times_out_without_calling_native_cache(
    cache: ManagedSourceIndexCache, source: Path, admission: MagicMock
) -> None:
    stable = _committed_index(cache, source, admission)
    impatient = ManagedSourceIndexCache(cache.root.parent.parent, lock_timeout_seconds=0)

    def unexpected(*_args: object) -> None:
        pytest.fail("native cache call while another writer owns the lock")

    with exclusive_file_lock(stable.with_suffix(".lock")):
        assert impatient.try_load(source, unexpected, admission=admission) is None
    assert cache.validated_index(source) == stable


def test_concurrent_callers_commit_one_entry_and_recheck_under_lock(
    cache: ManagedSourceIndexCache, source: Path, admission: MagicMock
) -> None:
    building = Event()
    contender_ready = Event()
    release = Event()
    modes: list[int] = []

    def open_source(path: Path, mode: int, index: Path) -> bool:
        modes.append(mode)
        if mode == 1:
            building.set()
            assert release.wait(5)
        return _create_index(path, mode, index)

    def contender() -> bool | None:
        second = ManagedSourceIndexCache(cache.root.parent.parent)
        return second.try_load(
            source, open_source, admission=admission, abort_check=contender_ready.set
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cache.try_load, source, open_source, admission=admission)
        try:
            assert building.wait(5)
            second = executor.submit(contender)
            assert contender_ready.wait(5)
        finally:
            release.set()
        assert first.result(timeout=5)
        assert second.result(timeout=5)
    assert modes == [1, 0]
    assert len(list(cache.root.glob("*.json"))) == 1
    assert len(list(cache.root.glob("*.lwi"))) == 1
