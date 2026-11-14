"""Color matrix policy shared by the screenshot renderers."""

from __future__ import annotations

from typing import Literal

# BT.2020 10-bit transfer, used when a constant-luminance signal omits it.
BT2020_CL_TRANSFER = 14

MATRIX_TO_ZIMG: dict[int, str] = {
    1: "709",
    4: "fcc",
    5: "470bg",
    6: "170m",
    7: "240m",
    8: "ycgco",
    9: "2020ncl",
    10: "2020cl",
}


def untagged_matrix(width: int, height: int, *, is_hdr: bool) -> Literal["2020ncl", "170m", "709"]:
    """Choose a matrix from the coded source dimensions and HDR evidence."""
    if is_hdr:
        return "2020ncl"
    return "170m" if width <= 1024 and height <= 576 else "709"
