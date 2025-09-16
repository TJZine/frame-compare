from __future__ import annotations
from pathlib import Path
from typing import List
from .datatypes import ScreenshotConfig

def generate_screenshots(clips, frames: List[int], files: List[str], out_dir: Path, cfg: ScreenshotConfig) -> List[str]:
    """Create placeholder images; Codex will port fpng/ffmpeg writers and mod-crop plan."""
    out_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for f in files:
        for n in frames:
            name = f"{Path(f).stem}_frame{n:06d}.png"
            (out_dir / name).write_bytes(b"placeholder\n")
            created.append(str(out_dir / name))
    return created
