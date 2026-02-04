from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from frame_compare.errors import VapourSynthError, VapourSynthNotFoundError
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.orchestration.probe_cache import load_clip_probe_cache
from frame_compare.vs.env import detect_plugins, ensure_vs_environment
from frame_compare.vs.loader import DefaultVSLoader, VSLoader
from frame_compare.vs.types import SourceInfo

if TYPE_CHECKING:
    import vapoursynth as vs  # type: ignore

# Skip policy at module level (Docker gate requires zero skips there)
vs_mod = pytest.importorskip("vapoursynth")
if isinstance(vs_mod, MagicMock):
    pytest.skip("vapoursynth is mocked", allow_module_level=True)

try:
    _core = ensure_vs_environment()
except (VapourSynthNotFoundError, VapourSynthError) as exc:
    pytest.skip(f"vapoursynth not available: {exc}", allow_module_level=True)

if not detect_plugins(_core).get("lsmas", False):
    pytest.skip("lsmas plugin not available", allow_module_level=True)


def _write_minimal_config(root: Path) -> None:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text("", encoding="utf-8")


def _prepare_workspace(root: Path, template_video: Path) -> list[Path]:
    input_dir = root / "comparison_videos"
    input_dir.mkdir(parents=True, exist_ok=True)
    (root / "generated").mkdir(parents=True, exist_ok=True)

    ref_path = input_dir / "a_ref.mp4"
    comp_path = input_dir / "b_comp.mp4"
    shutil.copy2(template_video, ref_path)
    shutil.copy2(template_video, comp_path)
    return [ref_path, comp_path]


@pytest.mark.integration
@pytest.mark.vs_required
@pytest.mark.anyio
async def test_loadsources_writes_clip_probe_cache_file(
    tmp_path: Path, mock_video_path: Path
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _write_minimal_config(workspace_root)
    input_videos = _prepare_workspace(workspace_root, mock_video_path)

    request = RunRequest(root=workspace_root, quiet=True)
    deps = RunDependencies(vs_loader=DefaultVSLoader())
    result = await execute_run(request, deps=deps)

    assert result.success is True

    cache_path = workspace_root / "generated" / "clip_probe.toml"
    assert cache_path.exists()

    entries = load_clip_probe_cache(cache_path)
    assert entries

    cached_names = {snapshot.fingerprint.path.name for snapshot in entries.values()}
    assert cached_names == {path.name for path in input_videos}


class _RaisingVSLoader(VSLoader):
    def load(self, path: Path) -> SourceInfo:
        raise AssertionError(f"VS loader should not be called: {path}")

    def ensure_core(self) -> vs.Core:
        raise AssertionError("VS core should not be requested when cache is warm")


@pytest.mark.integration
@pytest.mark.vs_required
@pytest.mark.anyio
async def test_loadsources_reuses_clip_probe_cache_file(
    tmp_path: Path, mock_video_path: Path
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    _write_minimal_config(workspace_root)
    _prepare_workspace(workspace_root, mock_video_path)

    request = RunRequest(root=workspace_root, quiet=True)
    deps = RunDependencies(vs_loader=DefaultVSLoader())
    result = await execute_run(request, deps=deps)
    assert result.success is True

    cache_path = workspace_root / "generated" / "clip_probe.toml"
    cache_before = cache_path.read_text(encoding="utf-8")

    reuse_deps = RunDependencies(vs_loader=_RaisingVSLoader())
    reuse_result = await execute_run(request, deps=reuse_deps)
    assert reuse_result.success is True

    cache_after = cache_path.read_text(encoding="utf-8")
    assert cache_after == cache_before
