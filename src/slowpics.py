from __future__ import annotations
from typing import List
from pathlib import Path
from .datatypes import SlowpicsConfig

class SlowpicsAPIError(RuntimeError):
    pass

def upload_comparison(image_files: List[str], screen_dir: Path, cfg: SlowpicsConfig) -> str:
    """Stub; Codex will implement slow.pics API session + upload and return the collection URL."""
    return "https://slow.pics/c/placeholder"
