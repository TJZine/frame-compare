"""Geometry calculation utilities for screenshot rendering."""


def calculate_dimensions(
    source_width: int,
    source_height: int,
    max_width: int | None = None,
    max_height: int | None = None,
) -> tuple[int, int]:
    """
    Calculate output dimensions preserving aspect ratio.

    Algorithm:
    1. If both max_width and max_height are None, return (source_width, source_height).
    2. Compute aspect ratio: ratio = source_width / source_height.
    3. If only max_width is set: new_width = min(source_width, max_width),
       new_height = int(new_width / ratio).
    4. If only max_height is set: new_height = min(source_height, max_height),
       new_width = int(new_height * ratio).
    5. If both are set: compute width-constrained and height-constrained sizes;
       pick the one that fits within *both* constraints.
    6. Round down (truncate) to integer; never exceed constraints.

    Raises:
        ValueError: If dimensions are non-positive.
    """
    if source_width <= 0 or source_height <= 0:
        raise ValueError("source dimensions must be positive")
    if (max_width is not None and max_width <= 0) or (max_height is not None and max_height <= 0):
        raise ValueError("max dimensions must be positive")

    if max_width is None and max_height is None:
        return (source_width, source_height)

    width_scale = (max_width / source_width) if max_width is not None else 1.0
    height_scale = (max_height / source_height) if max_height is not None else 1.0
    scale = min(1.0, width_scale, height_scale)

    new_width = max(1, int(source_width * scale))
    new_height = max(1, int(source_height * scale))
    return (new_width, new_height)

def ensure_mod2(width: int, height: int) -> tuple[int, int]:
    """
    Round dimensions up to nearest even values for video encoding compatibility.

    Algorithm:
    - Round each dimension up to the nearest even number:
      (width + width % 2, height + height % 2).

    Raises:
        ValueError: If dimensions are non-positive.
    """
    if width <= 0 or height <= 0:
        raise ValueError("dimensions must be positive")

    return (width + width % 2, height + height % 2)
