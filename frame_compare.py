from __future__ import annotations

import sys
import shutil
import webbrowser
from pathlib import Path
from typing import Iterable, List, Sequence

import click
from rich import print
from natsort import os_sorted

from src.config_loader import ConfigError, load_config
from src.datatypes import AppConfig
from src.utils import parse_filename_metadata
from src import vs_core
from src.analysis import select_frames
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


def _discover_media(root: Path) -> List[Path]:
    return [p for p in os_sorted(root.iterdir()) if p.suffix.lower() in SUPPORTED_EXTS]


def _pick_analyze_file(files: Sequence[Path], target: str | None) -> Path:
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
        metadata = parse_filename_metadata(file.name)
        for key in ("label", "release_group", "anime_title"):
            value = metadata.get(key) or ""
            if value and value.lower() == target_lower:
                return file
        if target_lower == str(idx):
            return file

    return files[0]


def _init_clips(files: Sequence[Path]) -> List[object]:
    clips: List[object] = []
    for file in files:
        clip = vs_core.init_clip(str(file))
        clips.append(clip)
    return clips


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

    labels = [parse_filename_metadata(file.name).get("label") or file.name for file in files]
    print("[green]Files detected:[/green]")
    for label, file in zip(labels, files):
        print(f"  - {label} ({file.name})")

    analyze_path = _pick_analyze_file(files, cfg.analysis.analyze_clip)

    try:
        clips = _init_clips(files)
    except vs_core.ClipInitError as exc:
        print(f"[red]Failed to open clip:[/red] {exc}")
        sys.exit(1)

    analyze_clip = clips[files.index(analyze_path)]

    try:
        frames = select_frames(analyze_clip, cfg.analysis, [f.name for f in files], analyze_path.name)
    except Exception as exc:
        print(f"[red]Frame selection failed:[/red] {exc}")
        sys.exit(1)

    if not frames:
        print("[red]No frames were selected; cannot continue.[/red]")
        sys.exit(1)

    out_dir = (root / cfg.screenshots.directory_name).resolve()
    try:
        image_paths = generate_screenshots(clips, frames, [str(f) for f in files], out_dir, cfg.screenshots)
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

    _print_summary(files, frames, out_dir, slowpics_url)\r\n\r\n    if slowpics_url:\r\n        if cfg.slowpics.open_in_browser:\r\n            try:\r\n                webbrowser.open(slowpics_url)\r\n            except Exception:\r\n                print("[yellow]Warning:[/yellow] Unable to open browser for slow.pics URL")\r\n        try:\r\n            import pyperclip  # type: ignore\r\n\r\n            pyperclip.copy(slowpics_url)\r\n        except Exception:\r\n            pass\r\n        if cfg.slowpics.delete_screen_dir_after_upload:\r\n            try:\r\n                shutil.rmtree(out_dir)\r\n                print(f"[yellow]Screenshot directory removed:[/yellow] {out_dir}")\r\n            except OSError as exc:\r\n                print(f"[yellow]Warning:[/yellow] Failed to delete screenshot directory: {exc}")\r\n

if __name__ == "__main__":
    main()




