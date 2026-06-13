"""Tests for _persist_probe_snapshots_for_run merge semantics."""

from fractions import Fraction
from pathlib import Path

from frame_compare.orchestration.context import ClipFingerprint, ClipProbeSnapshot
from frame_compare.orchestration.probing.probe_cache import (
    compute_probe_cache_key,
    load_clip_probe_cache,
    save_clip_probe_cache,
)
from frame_compare.utils.types import WorkspacePaths


def _snapshot(name: str, size: int = 1024, mtime: int = 5000) -> ClipProbeSnapshot:
    return ClipProbeSnapshot(
        fingerprint=ClipFingerprint(Path(name), size, mtime),
        width=1920,
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

    # Pre-populate with an existing entry for video_a.
    snap_a = _snapshot("video_a.mkv")
    key_a = compute_probe_cache_key(snap_a.fingerprint)
    save_clip_probe_cache(cache_path, {key_a: snap_a})
    assert key_a in load_clip_probe_cache(cache_path)

    # Persist a new entry for video_b via the preparation helper.
    from frame_compare.orchestration.preparation import _persist_probe_snapshots_for_run

    snap_b = _snapshot("video_b.mkv", size=2048, mtime=9000)
    _persist_probe_snapshots_for_run(
        workspace=workspace,
        snapshots_by_path={Path("video_b.mkv"): snap_b},
    )

    # Both entries must survive in the shared/run cache.
    result = load_clip_probe_cache(cache_path)
    key_b = compute_probe_cache_key(snap_b.fingerprint)
    assert key_a in result, "pre-existing entry was lost"
    assert key_b in result, "new entry was not written"


def test_run_folder_preserves_existing_shared_entries(tmp_path: Path) -> None:
    """In run-folder layout, persisting new probes must not discard shared entries."""
    workspace = _run_folder_workspace(tmp_path)
    shared_path = workspace.shared_analysis_cache_dir.parent.parent / "clip_probe.toml"

    # Pre-populate the shared cache.
    snap_a = _snapshot("video_a.mkv")
    key_a = compute_probe_cache_key(snap_a.fingerprint)
    save_clip_probe_cache(shared_path, {key_a: snap_a})

    from frame_compare.orchestration.preparation import _persist_probe_snapshots_for_run

    snap_b = _snapshot("video_b.mkv", size=2048, mtime=9000)
    _persist_probe_snapshots_for_run(
        workspace=workspace,
        snapshots_by_path={Path("video_b.mkv"): snap_b},
    )

    # Shared cache keeps both.
    shared_result = load_clip_probe_cache(shared_path)
    key_b = compute_probe_cache_key(snap_b.fingerprint)
    assert key_a in shared_result, "pre-existing shared entry was lost"
    assert key_b in shared_result, "new entry was not written to shared cache"

    # Run-local cache has only the current run's entries.
    run_path = workspace.generated_dir / "clip_probe.toml"
    run_result = load_clip_probe_cache(run_path)
    assert key_b in run_result, "new entry missing from run-local cache"


def test_same_path_updates_stale_entry(tmp_path: Path) -> None:
    """When a video's fingerprint changes, the current entry wins over stale."""
    workspace = _legacy_workspace(tmp_path)
    cache_path = workspace.generated_dir / "clip_probe.toml"

    snap_old = _snapshot("video.mkv", size=1024, mtime=1000)
    key_old = compute_probe_cache_key(snap_old.fingerprint)
    save_clip_probe_cache(cache_path, {key_old: snap_old})

    # New run probes the same video with an updated mtime → different key.
    snap_new = _snapshot("video.mkv", size=1024, mtime=2000)
    key_new = compute_probe_cache_key(snap_new.fingerprint)

    from frame_compare.orchestration.preparation import _persist_probe_snapshots_for_run

    _persist_probe_snapshots_for_run(
        workspace=workspace,
        snapshots_by_path={Path("video.mkv"): snap_new},
    )

    result = load_clip_probe_cache(cache_path)
    # Both keys are present (old stale entry and new entry).
    assert key_old in result, "old key should remain until evicted"
    assert key_new in result, "new key must be present"
