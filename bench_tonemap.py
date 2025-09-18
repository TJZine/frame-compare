from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from src.config_loader import ConfigError, load_config
from src.tonemap.config import TMConfig
from src.tonemap.core import apply_tonemap
from src.tonemap.exceptions import TonemapError
from src import vs_core

logger = logging.getLogger("bench_tonemap")


def _coerce_tm_config(cfg: TMConfig, preset: str | None) -> TMConfig:
    if preset:
        return cfg.merged(preset=preset).resolved()
    return cfg


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark tonemap performance over N frames.")
    parser.add_argument("clip", help="Path to an input video file")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")
    parser.add_argument("--frames", type=int, default=120, help="Number of frames to process")
    parser.add_argument("--preset", help="Optional tonemap preset override")
    args = parser.parse_args()

    try:
        app_cfg = load_config(args.config)
    except ConfigError as exc:
        parser.error(f"Failed to load config: {exc}")

    tm_cfg = _coerce_tm_config(app_cfg.tonemap, args.preset)

    clip_path = Path(args.clip)
    if not clip_path.exists():
        parser.error(f"Clip not found: {clip_path}")

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    try:
        src_clip = vs_core.init_clip(str(clip_path), cache_dir=str(clip_path.parent))
    except vs_core.ClipInitError as exc:
        parser.error(f"Failed to init clip: {exc}")

    try:
        result = apply_tonemap(src_clip, tm_cfg)
    except TonemapError as exc:
        parser.error(f"Tonemap failed: {exc}")

    frame_total = max(1, int(args.frames))
    start = time.perf_counter()
    for idx in range(frame_total):
        try:
            result.clip.get_frame(idx)
        except AttributeError:
            # Fallback: request frame through VS core if available
            getattr(result.clip, "__getitem__", lambda _: None)(idx)
        except Exception:
            break
    elapsed = time.perf_counter() - start
    fps = frame_total / elapsed if elapsed > 0 else 0.0
    print(f"Processed {frame_total} frames in {elapsed:.3f}s ({fps:.2f} fps)")


if __name__ == "__main__":
    main()
