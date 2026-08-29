"""Tests for _persist_probe_snapshots_for_run merge semantics."""

import multiprocessing
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from typing import Protocol

import pytest

import frame_compare.orchestration.probing.probe_cache as probe_cache
from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot
from frame_compare.orchestration.preparation import (
    _persist_probe_snapshots_for_run,
    _probe_input_videos,
)
from frame_compare.orchestration.probing.probe_cache import (
    compute_probe_cache_key,
    load_clip_probe_cache,
    merge_shared_clip_probe_cache,
    save_clip_probe_cache,
)
from frame_compare.orchestration.types import RunDependencies
from frame_compare.utils.file_lock import exclusive_file_lock
from frame_compare.utils.types import WorkspacePaths

_PROCESS_TIMEOUT_SECONDS = 5.0
_LOCK_BLOCK_PROBE_SECONDS = 0.2


class _ProcessEvent(Protocol):
    def set(self) -> None: ...

    def wait(self, timeout: float | None = None) -> bool: ...


def _snapshot(
    name: str,
    *,
    size: int = 1024,
    mtime: int = 5000,
    width: int = 1920,
) -> ClipProbeSnapshot:
    return ClipProbeSnapshot(
        fingerprint=ClipFingerprint(Path(name), size, mtime),
        width=width,
        height=1080,
        num_frames=100,
        fps=Fraction(24000, 1001),
        is_hdr=False,
    )


def _run_folder_workspace(root: Path) -> WorkspacePaths:
    """Build a canonical workspace with shared and run-local cache paths."""
    return WorkspacePaths(
        root=root,
        input_dir=root / "input",
        generated_root=root / "generated",
        run_dir=root / "generated" / "run1",
        screenshots_dir=root / "generated" / "run1" / "screenshots",
        generated_dir=root / "generated" / "run1" / "generated",
        config_dir=root / "config",
        config_file=None,
        analysis_cache_dir=root / "generated" / "cache" / "analysis",
        alignment_cache_dir=root / "generated" / "cache" / "alignment",
    )


def _merge_cache_in_child(
    cache_path: Path,
    snapshot: ClipProbeSnapshot,
    started: _ProcessEvent,
    completed: _ProcessEvent,
) -> None:
    cache_key = compute_probe_cache_key(snapshot.fingerprint)
    started.set()
    merge_shared_clip_probe_cache(cache_path, {cache_key: snapshot})
    completed.set()


def _clean_up_process(process: multiprocessing.Process) -> None:
    if process.pid is None:
        return
    if process.is_alive():
        process.terminate()
    process.join(timeout=_PROCESS_TIMEOUT_SECONDS)
    if process.is_alive():
        process.kill()
        process.join(timeout=_PROCESS_TIMEOUT_SECONDS)


def test_run_folder_preserves_existing_shared_entries(tmp_path: Path) -> None:
    """Run-local writes must not discard earlier shared entries."""
    workspace = _run_folder_workspace(tmp_path)
    cache_path = workspace.shared_analysis_cache_dir.parent.parent / "clip_probe.toml"

    snap_a = _snapshot("video_a.mkv")
    key_a = compute_probe_cache_key(snap_a.fingerprint)
    save_clip_probe_cache(cache_path, {key_a: snap_a})
    assert key_a in load_clip_probe_cache(cache_path)

    snap_b = _snapshot("video_b.mkv", size=2048, mtime=9000)
    _persist_probe_snapshots_for_run(
        workspace=workspace,
        snapshots_by_path={Path("video_b.mkv"): snap_b},
    )

    key_b = compute_probe_cache_key(snap_b.fingerprint)
    shared_result = load_clip_probe_cache(cache_path)
    assert set(shared_result) == {key_a, key_b}

    run_path = workspace.generated_dir / "clip_probe.toml"
    run_result = load_clip_probe_cache(run_path)
    assert set(run_result) == {key_b}


def test_shared_merge_locks_cross_process_read_modify_write(tmp_path: Path) -> None:
    cache_path = tmp_path / "clip_probe.toml"
    lock_path = cache_path.with_name(f"{cache_path.name}.lock")
    snap_a = _snapshot("video_a.mkv")
    snap_b = _snapshot("video_b.mkv", size=2048, mtime=9000)
    key_a = compute_probe_cache_key(snap_a.fingerprint)
    key_b = compute_probe_cache_key(snap_b.fingerprint)
    context = multiprocessing.get_context("spawn")
    started = context.Event()
    completed = context.Event()
    process = context.Process(
        target=_merge_cache_in_child,
        args=(cache_path, snap_b, started, completed),
    )

    try:
        with exclusive_file_lock(lock_path):
            process.start()
            assert started.wait(timeout=_PROCESS_TIMEOUT_SECONDS)
            assert not completed.wait(timeout=_LOCK_BLOCK_PROBE_SECONDS)
            save_clip_probe_cache(cache_path, {key_a: snap_a})

        assert completed.wait(timeout=_PROCESS_TIMEOUT_SECONDS)
        process.join(timeout=_PROCESS_TIMEOUT_SECONDS)
        assert not process.is_alive()
        assert process.exitcode == 0
    finally:
        _clean_up_process(process)

    assert set(load_clip_probe_cache(cache_path)) == {key_a, key_b}


def test_shared_merge_keeps_load_and_save_inside_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_path = tmp_path / "clip_probe.toml"
    lock_path = cache_path.with_name(f"{cache_path.name}.lock")
    existing = _snapshot("video_a.mkv")
    current = _snapshot("video_b.mkv", size=2048, mtime=9000)
    existing_key = compute_probe_cache_key(existing.fingerprint)
    current_key = compute_probe_cache_key(current.fingerprint)
    events: list[str] = []

    @contextmanager
    def _fake_lock(path: Path) -> Iterator[None]:
        assert path == lock_path
        events.append("lock_enter")
        try:
            yield
        finally:
            events.append("lock_exit")

    def _fake_load(path: Path) -> dict[str, ClipProbeSnapshot]:
        assert path == cache_path
        assert events == ["lock_enter"]
        events.append("load")
        return {existing_key: existing}

    def _fake_save(path: Path, entries: Mapping[str, ClipProbeSnapshot]) -> None:
        assert path == cache_path
        assert events == ["lock_enter", "load"]
        assert set(entries) == {existing_key, current_key}
        events.append("save")

    monkeypatch.setattr(probe_cache, "exclusive_file_lock", _fake_lock)
    monkeypatch.setattr(probe_cache, "_load_shared_clip_probe_cache_for_update", _fake_load)
    monkeypatch.setattr(probe_cache, "save_clip_probe_cache", _fake_save)

    probe_cache.merge_shared_clip_probe_cache(cache_path, {current_key: current})

    assert events == ["lock_enter", "load", "save", "lock_exit"]


def test_run_folder_preserves_historical_fingerprint(tmp_path: Path) -> None:
    """A changed fingerprint is retained alongside the prior cache entry."""
    workspace = _run_folder_workspace(tmp_path)
    cache_path = workspace.shared_analysis_cache_dir.parent.parent / "clip_probe.toml"

    snap_old = _snapshot("video.mkv", size=1024, mtime=1000)
    key_old = compute_probe_cache_key(snap_old.fingerprint)
    save_clip_probe_cache(cache_path, {key_old: snap_old})

    snap_new = _snapshot("video.mkv", size=1024, mtime=2000)
    key_new = compute_probe_cache_key(snap_new.fingerprint)

    _persist_probe_snapshots_for_run(
        workspace=workspace,
        snapshots_by_path={Path("video.mkv"): snap_new},
    )

    result = load_clip_probe_cache(cache_path)
    assert set(result) == {key_old, key_new}


def test_run_folder_current_entry_wins_on_cache_key_conflict(tmp_path: Path) -> None:
    workspace = _run_folder_workspace(tmp_path)
    cache_path = workspace.shared_analysis_cache_dir.parent.parent / "clip_probe.toml"
    existing = _snapshot("video.mkv", width=1280)
    current = _snapshot("video.mkv", width=1920)
    cache_key = compute_probe_cache_key(current.fingerprint)
    save_clip_probe_cache(cache_path, {cache_key: existing})

    _persist_probe_snapshots_for_run(
        workspace=workspace,
        snapshots_by_path={Path("video.mkv"): current},
    )

    assert load_clip_probe_cache(cache_path)[cache_key].width == 1920


def test_normal_run_folder_probe_cache_excludes_unrelated_shared_entries(tmp_path: Path) -> None:
    workspace = _run_folder_workspace(tmp_path)
    current_path = tmp_path / "current.mkv"
    unrelated_path = tmp_path / "unrelated.mkv"
    current_path.write_bytes(b"current")
    unrelated_path.write_bytes(b"unrelated")
    current = _snapshot_from_file(current_path)
    unrelated = _snapshot_from_file(unrelated_path)
    current_key = compute_probe_cache_key(current.fingerprint)
    unrelated_key = compute_probe_cache_key(unrelated.fingerprint)
    shared_path = workspace.shared_analysis_cache_dir.parent.parent / "clip_probe.toml"
    save_clip_probe_cache(
        shared_path,
        {current_key: current, unrelated_key: unrelated},
    )

    _probe_input_videos(
        workspace=workspace,
        input_videos=[current_path],
        deps=RunDependencies(),
        config=ConfigSchema(),
        overrides_by_path={},
        labels_by_path={current_path: current_path.stem},
        release_identities_by_path={},
        explicit_labels_by_path={},
    )

    run_path = workspace.generated_dir / "clip_probe.toml"
    assert set(load_clip_probe_cache(run_path)) == {current_key}
    assert set(load_clip_probe_cache(shared_path)) == {current_key, unrelated_key}


def _snapshot_from_file(path: Path) -> ClipProbeSnapshot:
    stats = path.stat()
    return ClipProbeSnapshot(
        fingerprint=ClipFingerprint(path, stats.st_size, stats.st_mtime_ns),
        width=1920,
        height=1080,
        num_frames=100,
        fps=Fraction(24000, 1001),
        is_hdr=False,
    )
