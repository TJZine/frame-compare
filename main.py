from __future__ import annotations
import sys
from pathlib import Path
import click
from rich import print
from natsort import os_sorted

from src.config_loader import load_config
from src.datatypes import AppConfig
from src.utils import parse_filename_metadata
from src import vs_core
from src.analysis import select_frames
from src.screenshot import generate_screenshots
from src.slowpics import upload_comparison

SUPPORTED_EXTS = ('.mkv','.m2ts','.mp4','.webm','.ogm','.mpg','.vob','.iso','.ts','.mts','.mov','.qv','.yuv','.flv','.avi','.rm','.rmvb','.m2v','.m4v','.mp2','.mpeg','.mpe','.mpv','.wmv','.avc','.hevc','.264','.265','.av1')

@click.command()
@click.option("--config", "config_path", default="config.toml", show_default=True, help="Path to config.toml")
@click.option("--input", "input_dir", default=None, help="Override [paths.input_dir] from config.toml")
def main(config_path: str, input_dir: str | None) -> None:
    cfg: AppConfig = load_config(config_path)
    if input_dir:
        cfg.paths.input_dir = input_dir

    root = Path(cfg.paths.input_dir).resolve()
    if not root.exists():
        print(f"[red]Input directory not found:[/red] {root}")
        sys.exit(1)

    files = [p for p in root.iterdir() if p.suffix.lower() in SUPPORTED_EXTS]
    files = list(os_sorted(files))
    if len(files) < 2:
        print("[red]Need at least two video files to compare.[/red]")
        sys.exit(2)

    print("[green]Files found:[/green]")
    for p in files:
        print(f" - {p.name}")

    analyze_file = str(files[0])
    clip = vs_core.init_clip(analyze_file)
    frames = select_frames(clip, cfg.analysis, [p.name for p in files], analyze_file)

    out_dir = root / cfg.screenshots.directory_name
    generated = generate_screenshots([clip], frames, [p.name for p in files], out_dir, cfg.screenshots)
    print(f"Generated {len(generated)} placeholder images in {out_dir}")

    if cfg.slowpics.auto_upload:
        url = upload_comparison(generated, out_dir, cfg.slowpics)
        print(f"Slow.pics: {url}")

if __name__ == "__main__":
    main()
