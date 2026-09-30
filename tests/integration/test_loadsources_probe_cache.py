from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from frame_compare.analysis.metrics import calculate_metrics
from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import RuntimeConfig
from frame_compare.orchestration.coordinator import RunDependencies, RunRequest, execute_run
from frame_compare.orchestration.probing.probe_cache import load_clip_probe_cache
from frame_compare.render.prepare import prepare_clip_for_render
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.env import detect_plugins, ensure_vs_environment
from frame_compare.vs.errors import VapourSynthError, VapourSynthNotFoundError
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

_PROBE_CACHE_CONFIG = """\
[paths]

[analysis]
random_frame_count = 1

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[color]
enable_tonemap = false

[slowpics]
auto_upload = false

[tmdb]
enabled = false

[report]
enable = false

"""


def _write_minimal_config(root: Path) -> None:
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text(_PROBE_CACHE_CONFIG, encoding="utf-8")


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

    request = RunRequest(
        root=workspace_root,
        quiet=True,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
    )
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

    request = RunRequest(
        root=workspace_root,
        quiet=True,
        skip_analysis=True,
        skip_metadata=True,
        no_upload=True,
    )
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


@pytest.fixture
def runtime_clip(tmp_path: Path) -> Path:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    run_subprocess(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=24:duration=6",
            "-c:v",
            "ffv1",
            str(input_dir / "fixture.mkv"),
        ],
        timeout_seconds=30,
    )
    return input_dir / "fixture.mkv"


@pytest.mark.parametrize("memory_limit_mb,injected", [(None, False), (1024, False), (1024, True)])
def test_configured_run_uses_shared_real_loader(
    tmp_path: Path,
    runtime_clip: Path,
    monkeypatch: pytest.MonkeyPatch,
    memory_limit_mb: int | None,
    injected: bool,
) -> None:
    core = ensure_vs_environment()
    original = core.max_cache_size
    assert runtime_clip.parent == tmp_path / "input"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    runtime = "" if memory_limit_mb is None else "[runtime]\nmemory_limit_mb = 1024\n"
    (config_dir / "config.toml").write_text(
        runtime + '\n[paths]\ninput_dir = "input"\n'
        "[analysis]\nuser_frames = [0]\nrandom_frame_count = 0\ndark_frame_count = 1\n"
        "[audio_alignment]\nenable = false\n"
        '[screenshots]\nuse_ffmpeg = true\nactive_rect_detection = "aspect_ratio"\n'
        "[color]\nenable_tonemap = false\n[report]\nenable = false\n",
        encoding="utf-8",
    )
    used_loaders: list[DefaultVSLoader] = []
    cache_sizes: list[int] = []
    original_load = DefaultVSLoader.load

    def observe_load(self: DefaultVSLoader, path: Path) -> SourceInfo:
        source = original_load(self, path)
        used_loaders.append(self)
        cache_sizes.append(self.ensure_core().max_cache_size)
        return source

    monkeypatch.setattr(DefaultVSLoader, "load", observe_load)
    injected_loader = DefaultVSLoader(memory_limit_mb=1536) if injected else None
    try:
        result = asyncio.run(
            execute_run(
                RunRequest(
                    root=tmp_path,
                    skip_metadata=True,
                    no_upload=True,
                    quiet=True,
                ),
                RunDependencies(vs_loader=injected_loader),
            )
        )
        assert result.success
        assert used_loaders
        assert len({id(loader) for loader in used_loaders}) == 1
        expected = 1536 if injected else original if memory_limit_mb is None else 1024
        assert cache_sizes == [expected] * len(cache_sizes)
        if injected:
            assert all(loader is injected_loader for loader in used_loaders)
    finally:
        core.max_cache_size = original


def test_real_render_and_metric_fallbacks_apply_cache_limit(
    runtime_clip: Path, tmp_path: Path
) -> None:
    core = ensure_vs_environment()
    original = core.max_cache_size
    config = get_default_config()
    config.runtime = RuntimeConfig(memory_limit_mb=1024)
    config.color.enable_tonemap = False
    try:
        prepared = prepare_clip_for_render(runtime_clip, "vapoursynth", config)
        assert not isinstance(prepared.prepared_clip, Path)
        prepared.prepared_clip.get_frame(0).close()
        assert core.max_cache_size == 1024
        core.max_cache_size = original
        metrics = calculate_metrics(
            [runtime_clip], config.analysis, tmp_path / "cache", memory_limit_mb=1024
        )
        assert metrics.metadata.frame_count == 144
        assert core.max_cache_size == 1024
    finally:
        core.max_cache_size = original
