"""Tests for _persist_probe_snapshots_for_run merge semantics."""

from fractions import Fraction
from pathlib import Path

from frame_compare.config.schema import ConfigSchema
from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot
from frame_compare.orchestration.preparation import (
    _persist_probe_snapshots_for_run,
    _probe_input_videos,
)
from frame_compare.orchestration.probing.probe_cache import (
    compute_probe_cache_key,
    load_clip_probe_cache,
    save_clip_probe_cache,
)
from frame_compare.orchestration.types import RunDependencies
from frame_compare.utils.types import WorkspacePaths


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


def _legacy_workspace(root: Path) -> WorkspacePaths:
    """Build a workspace where shared_cache_path == run_cache_path (legacy mode)."""
    return WorkspacePaths(
        root=root,
        input_dir=root / "input",
        run_dir=None,
        screenshots_dir=root / "screenshots",
        generated_dir=root / "generated",
        config_dir=root / "config",
        config_file=None,
    )


def _run_folder_workspace(root: Path) -> WorkspacePaths:
    """Build a workspace with a run folder (distinct shared vs run-local paths)."""
    base = _legacy_workspace(root)
    run_dir = root / "input" / "run1"
    return base.with_run_dir(run_dir)


def test_same_path_preserves_existing_shared_entries(tmp_path: Path) -> None:
    """In legacy layout, persisting new probes must not discard earlier shared entries."""
    workspace = _legacy_workspace(tmp_path)
    cache_path = workspace.generated_dir / "clip_probe.toml"

    snap_a = _snapshot("video_a.mkv")
    key_a = compute_probe_cache_key(snap_a.fingerprint)
    save_clip_probe_cache(cache_path, {key_a: snap_a})
    assert key_a in load_clip_probe_cache(cache_path)

    snap_b = _snapshot("video_b.mkv", size=2048, mtime=9000)
    _persist_probe_snapshots_for_run(
        workspace=workspace,
        snapshots_by_path={Path("video_b.mkv"): snap_b},
    )

    result = load_clip_probe_cache(cache_path)
    key_b = compute_probe_cache_key(snap_b.fingerprint)
    assert set(result) == {key_a, key_b}


def test_run_folder_preserves_existing_shared_entries(tmp_path: Path) -> None:
    """In run-folder layout, persisting new probes must not discard shared entries."""
    workspace = _run_folder_workspace(tmp_path)
    shared_path = workspace.shared_analysis_cache_dir.parent.parent / "clip_probe.toml"

    snap_a = _snapshot("video_a.mkv")
    key_a = compute_probe_cache_key(snap_a.fingerprint)
    save_clip_probe_cache(shared_path, {key_a: snap_a})

    snap_b = _snapshot("video_b.mkv", size=2048, mtime=9000)
    _persist_probe_snapshots_for_run(
        workspace=workspace,
        snapshots_by_path={Path("video_b.mkv"): snap_b},
    )

    shared_result = load_clip_probe_cache(shared_path)
    key_b = compute_probe_cache_key(snap_b.fingerprint)
    assert set(shared_result) == {key_a, key_b}

    run_path = workspace.generated_dir / "clip_probe.toml"
    run_result = load_clip_probe_cache(run_path)
    assert set(run_result) == {key_b}


def test_same_path_preserves_historical_fingerprint(tmp_path: Path) -> None:
    """A changed fingerprint is retained alongside the prior cache entry."""
    workspace = _legacy_workspace(tmp_path)
    cache_path = workspace.generated_dir / "clip_probe.toml"

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


def test_same_path_current_entry_wins_on_cache_key_conflict(tmp_path: Path) -> None:
    workspace = _legacy_workspace(tmp_path)
    cache_path = workspace.generated_dir / "clip_probe.toml"
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
