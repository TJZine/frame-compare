from __future__ import annotations
from typing import List
from .datatypes import AnalysisConfig

def select_frames(clip, cfg: AnalysisConfig, files: List[str], file_under_analysis: str) -> List[int]:
    """Return the list of frame indices to compare.
    NOTE: Placeholder picks the middle frame. Codex will port lazylist/dedupe/quantile logic here.
    """
    try:
        mid = max(0, getattr(clip, "num_frames", 1) // 2)
        return [mid]
    except Exception:
        return [0]
