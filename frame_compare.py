from __future__ import annotations

import re
import sys
import shutil
import webbrowser
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import click
from rich import print
from natsort import os_sorted

from src.config_loader import ConfigError, load_config
from src.datatypes import AppConfig
from src.utils import parse_filename_metadata
from src import vs_core
from src.analysis import FrameMetricsCacheInfo, select_frames
from src.screenshot import generate_screenshots, ScreenshotError
from src.slowpics import SlowpicsAPIError, upload_comparison

SUPPORTED_EXTS = (
    ".mkv",
    ".m2ts",
    ".mp4",
    ".webm",
    ".ogm",
    ".mpg",
    ".vob",
    ".iso",
    ".ts",
    ".mts",
    ".mov",
    ".qv",
    ".yuv",
    ".flv",
    ".avi",
    ".rm",
    ".rmvb",
    ".m2v",
    ".m4v",
    ".mp2",
    ".mpeg",
    ".mpe",
    ".mpv",
    ".wmv",
    ".avc",
    ".hevc",
    ".264",
    ".265",
    ".av1",
)


@dataclass
class _ClipPlan:
    path: Path
    metadata: Dict[str, str]
    trim_start: int = 0
    trim_end: Optional[int] = None
    fps_override: Optional[Tuple[int, int]] = None
    use_as_reference: bool = False
    clip: Optional[object] = None
    effective_fps: Optional[Tuple[int, int]] = None
    applied_fps: Optional[Tuple[int, int]] = None


def _discover_media(root: Path) -> List[Path]:
    return [p for p in os_sorted(root.iterdir()) if p.suffix.lower() in SUPPORTED_EXTS]


def _parse_metadata(files: Sequence[Path], naming_cfg) -> List[Dict[str, str]]:
    metadata: List[Dict[str, str]] = []
    for file in files:
        info = parse_filename_metadata(
            file.name,
            prefer_guessit=naming_cfg.prefer_guessit,
            always_full_filename=naming_cfg.always_full_filename,
        )
        metadata.append(info)
    _dedupe_labels(metadata, files, naming_cfg.always_full_filename)
    return metadata


_VERSION_PATTERN = re.compile(r"(?:^|[^0-9A-Za-z])(?P<tag>v\d{1,3})(?!\d)", re.IGNORECASE)


def _extract_version_suffix(file_path: Path) -> str | None:
    match = _VERSION_PATTERN.search(file_path.stem)
    if not match:
        return None
    tag = match.group("tag")
    return tag.upper() if tag else None


def _dedupe_labels(
    metadata: Sequence[Dict[str, str]],
    files: Sequence[Path],
    prefer_full_name: bool,
) -> None:
    counts = Counter((meta.get("label") or "") for meta in metadata)
    duplicate_groups: dict[str, list[int]] = defaultdict(list)
    for idx, meta in enumerate(metadata):
        label = meta.get("label") or ""
        if not label:
            meta["label"] = files[idx].name
            continue
        if counts[label] > 1:
            duplicate_groups[label].append(idx)

    if prefer_full_name:
        for indices in duplicate_groups.values():
            for idx in indices:
                metadata[idx]["label"] = files[idx].name
        return

    for label, indices in duplicate_groups.items():
        for idx in indices:
            version = _extract_version_suffix(files[idx])
            if version:
                metadata[idx]["label"] = f"{label} {version}".strip()

        temp_counts = Counter(metadata[idx].get("label") or "" for idx in indices)
        for idx in indices:
            resolved = metadata[idx].get("label") or label
            if temp_counts[resolved] <= 1:
                continue
            order = indices.index(idx) + 1
            metadata[idx]["label"] = f"{resolved} #{order}"

    for idx, meta in enumerate(metadata):
        if not (meta.get("label") or "").strip():
            meta["label"] = files[idx].name


def _pick_analyze_file(files: Sequence[Path], metadata: Sequence[Mapping[str, str]], target: str | None) -> Path:
    if not files:
        raise ValueError("No files to analyze")
    target = (target or "").strip()
    if not target:
        return files[0]

    target_lower = target.lower()

    # Allow numeric index selection
    if target.isdigit():
        idx = int(target)
        if 0 <= idx < len(files):
            return files[idx]

    for idx, file in enumerate(files):
        if file.name.lower() == target_lower or file.stem.lower() == target_lower:
            return file
        meta = metadata[idx]
        for key in ("label", "release_group", "anime_title", "file_name"):
            value = str(meta.get(key) or "")
            if value and value.lower() == target_lower:
                return file
        if target_lower == str(idx):
            return file

    return files[0]


def _normalise_override_mapping(raw: Mapping[str, object]) -> Dict[str, object]:
    normalised: Dict[str, object] = {}
    for key, value in raw.items():
        key_str = str(key).strip().lower()
        if key_str:
            normalised[key_str] = value
    return normalised


def _match_override(
    index: int,
    file: Path,
    metadata: Mapping[str, str],
    mapping: Mapping[str, object],
) -> Optional[object]:
    candidates = [
        str(index),
        file.name,
        file.stem,
        metadata.get("release_group", ""),
        metadata.get("file_name", ""),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        value = mapping.get(candidate.lower())
        if value is not None:
            return value
    return None


def _build_plans(files: Sequence[Path], metadata: Sequence[Dict[str, str]], cfg: AppConfig) -> List[_ClipPlan]:
    trim_map = _normalise_override_mapping(cfg.overrides.trim)
    trim_end_map = _normalise_override_mapping(cfg.overrides.trim_end)
    fps_map = _normalise_override_mapping(cfg.overrides.change_fps)

    plans: List[_ClipPlan] = []
    for idx, file in enumerate(files):
        meta = dict(metadata[idx])
        plan = _ClipPlan(path=file, metadata=meta)

        trim_val = _match_override(idx, file, meta, trim_map)
        if trim_val is not None:
            plan.trim_start = int(trim_val)

        trim_end_val = _match_override(idx, file, meta, trim_end_map)
        if trim_end_val is not None:
            plan.trim_end = int(trim_end_val)

        fps_val = _match_override(idx, file, meta, fps_map)
        if isinstance(fps_val, str):
            if fps_val.lower() == "set":
                plan.use_as_reference = True
        elif isinstance(fps_val, list):
            if len(fps_val) == 2:
                plan.fps_override = (int(fps_val[0]), int(fps_val[1]))
        elif fps_val is not None:
            raise ValueError("Unsupported change_fps override type")

        plans.append(plan)

    return plans


def _extract_clip_fps(clip: object) -> Tuple[int, int]:
    num = getattr(clip, "fps_num", None)
    den = getattr(clip, "fps_den", None)
    if isinstance(num, int) and isinstance(den, int) and den:
        return (num, den)
    return (24000, 1001)


def _init_clips(plans: Sequence[_ClipPlan], runtime_cfg) -> None:
    vs_core.set_ram_limit(runtime_cfg.ram_limit_mb)

    reference_index = next((idx for idx, plan in enumerate(plans) if plan.use_as_reference), None)
    reference_fps: Optional[Tuple[int, int]] = None

    if reference_index is not None:
        plan = plans[reference_index]
        clip = vs_core.init_clip(
            str(plan.path),
            trim_start=plan.trim_start,
            trim_end=plan.trim_end,
        )
        plan.clip = clip
        plan.effective_fps = _extract_clip_fps(clip)
        reference_fps = plan.effective_fps

    for idx, plan in enumerate(plans):
        if idx == reference_index and plan.clip is not None:
            continue
        fps_override = plan.fps_override
        if fps_override is None and reference_fps is not None and idx != reference_index:
            fps_override = reference_fps

        clip = vs_core.init_clip(
            str(plan.path),
            trim_start=plan.trim_start,
            trim_end=plan.trim_end,
            fps_map=fps_override,
        )
        plan.clip = clip
        plan.applied_fps = fps_override
        plan.effective_fps = _extract_clip_fps(clip)


def _build_cache_info(root: Path, plans: Sequence[_ClipPlan], cfg: AppConfig, analyze_index: int) -> Optional[FrameMetricsCacheInfo]:
    if not cfg.analysis.save_frames_data:
        return None

    analyzed = plans[analyze_index]
    fps_num, fps_den = analyzed.effective_fps or (24000, 1001)
    if fps_den <= 0:
        fps_den = 1

    cache_path = (root / cfg.analysis.frame_data_filename).resolve()
    return FrameMetricsCacheInfo(
        path=cache_path,
        files=[plan.path.name for plan in plans],
        analyzed_file=analyzed.path.name,
        release_group=analyzed.metadata.get("release_group", ""),
        trim_start=analyzed.trim_start,
        trim_end=analyzed.trim_end,
        fps_num=fps_num,
        fps_den=fps_den,
    )


def _print_summary(files: Sequence[Path], frames: Sequence[int], out_dir: Path, url: str | None) -> None:
    print("[green]Comparison ready[/green]")
    print(f"  Files     : {len(files)}")
    print(f"  Frames    : {len(frames)} -> {frames}")
    print(f"  Output dir: {out_dir}")
    if url:
        print(f"  Slow.pics : {url}")


@click.command()
@click.option("--config", "config_path", default="config.toml", show_default=True, help="Path to config.toml")
@click.option("--input", "input_dir", default=None, help="Override [paths.input_dir] from config.toml")
def main(config_path: str, input_dir: str | None) -> None:
    try:
        cfg: AppConfig = load_config(config_path)
    except ConfigError as exc:
        print(f"[red]Config error:[/red] {exc}")
        sys.exit(2)

    if input_dir:
        cfg.paths.input_dir = input_dir

    root = Path(cfg.paths.input_dir).expanduser().resolve()
    if not root.exists():
        print(f"[red]Input directory not found:[/red] {root}")
        sys.exit(1)

    try:
        files = _discover_media(root)
    except OSError as exc:
        print(f"[red]Failed to list input directory:[/red] {exc}")
        sys.exit(1)

    if len(files) < 2:
        print("[red]Need at least two video files to compare.[/red]")
        sys.exit(1)

    metadata = _parse_metadata(files, cfg.naming)
    labels = [meta.get("label") or file.name for meta, file in zip(metadata, files)]
    print("[green]Files detected:[/green]")
    for label, file in zip(labels, files):
        print(f"  - {label} ({file.name})")

    plans = _build_plans(files, metadata, cfg)
    analyze_path = _pick_analyze_file(files, metadata, cfg.analysis.analyze_clip)

    try:
        _init_clips(plans, cfg.runtime)
    except vs_core.ClipInitError as exc:
        print(f"[red]Failed to open clip:[/red] {exc}")
        sys.exit(1)

    clips = [plan.clip for plan in plans]
    if any(clip is None for clip in clips):
        print("[red]Internal error:[/red] Clip initialisation failed")
        sys.exit(1)

    analyze_index = [plan.path for plan in plans].index(analyze_path)
    analyze_clip = plans[analyze_index].clip
    if analyze_clip is None:
        print("[red]Internal error:[/red] Missing clip for analysis")
        sys.exit(1)

    cache_info = _build_cache_info(root, plans, cfg, analyze_index)

    try:
        frames = select_frames(
            analyze_clip,
            cfg.analysis,
            [plan.path.name for plan in plans],
            analyze_path.name,
            cache_info=cache_info,
        )
    except Exception as exc:
        print(f"[red]Frame selection failed:[/red] {exc}")
        sys.exit(1)

    if not frames:
        print("[red]No frames were selected; cannot continue.[/red]")
        sys.exit(1)

    out_dir = (root / cfg.screenshots.directory_name).resolve()
    try:
        image_paths = generate_screenshots(
            clips,
            frames,
            [str(plan.path) for plan in plans],
            [plan.metadata for plan in plans],
            out_dir,
            cfg.screenshots,
            trim_offsets=[plan.trim_start for plan in plans],
        )
    except ScreenshotError as exc:
        print(f"[red]Screenshot generation failed:[/red] {exc}")
        sys.exit(1)

    slowpics_url: str | None = None
    if cfg.slowpics.auto_upload:
        try:
            slowpics_url = upload_comparison(image_paths, out_dir, cfg.slowpics)
        except SlowpicsAPIError as exc:
            print(f"[red]slow.pics upload failed:[/red] {exc}")
            sys.exit(1)

    _print_summary([plan.path for plan in plans], frames, out_dir, slowpics_url)

    if slowpics_url:
        if cfg.slowpics.open_in_browser:
            try:
                webbrowser.open(slowpics_url)
            except Exception:
                print("[yellow]Warning:[/yellow] Unable to open browser for slow.pics URL")
        try:
            import pyperclip  # type: ignore

            pyperclip.copy(slowpics_url)
        except Exception:
            pass
        if cfg.slowpics.delete_screen_dir_after_upload:
            try:
                shutil.rmtree(out_dir)
                print(f"[yellow]Screenshot directory removed:[/yellow] {out_dir}")
            except OSError as exc:
                print(f"[yellow]Warning:[/yellow] Failed to delete screenshot directory: {exc}")


if __name__ == "__main__":
    main()




