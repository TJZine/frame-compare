"""Utility modules for Frame Compare.

Cross-cutting utilities shared by all layers.
"""

from frame_compare.utils.result import Err, Ok, Result, err, ok
from frame_compare.utils.types import RunMetrics, WorkspacePaths

__all__ = [
    "Err",
    "Ok",
    "Result",
    "RunMetrics",
    "WorkspacePaths",
    "err",
    "ok",
]
