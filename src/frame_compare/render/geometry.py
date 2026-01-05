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

    ratio = source_width / source_height

    if max_width is not None and max_height is None:
        new_width = min(source_width, max_width)
        return (new_width, int(new_width / ratio))

    if max_height is not None and max_width is None:
        new_height = min(source_height, max_height)
        return (int(new_height * ratio), new_height)

    # Both are set
    if max_width is not None and max_height is not None:
        # Option 1: Constrain by width
        w_width = min(source_width, max_width)
        w_height = int(w_width / ratio)

        # Option 2: Constrain by height
        h_height = min(source_height, max_height)
        h_width = int(h_height * ratio)

        # Pick the one that fits within both
        if w_width <= max_width and w_height <= max_height:
            return (w_width, w_height)
        return (h_width, h_height)

    # Fallback for type safety, though logically unreachable
    return (source_width, source_height)


def calculate_overlay_position(
    image_size: tuple[int, int],
    overlay_size: tuple[int, int],
    position: str,
    margin: int = 10,
) -> tuple[int, int]:
    """
    Calculate overlay top-left corner.

    Valid positions: {"top-left", "top-right", "bottom-left", "bottom-right"}.

    Algorithm:
    - top-left: (margin, margin)
    - top-right: (image_width - overlay_width - margin, margin)
    - bottom-left: (margin, image_height - overlay_height - margin)
    - bottom-right: (image_width - overlay_width - margin, image_height - overlay_height - margin)

    Invalid inputs:
    - position not in valid set: raise ValueError.
    - image_size or overlay_size non-positive: raise ValueError.
    - Overlay + margin exceeds image dimensions: clamp coordinates to 0.

    Raises:
        ValueError: If inputs are invalid.
    """
    valid_positions = {"top-left", "top-right", "bottom-left", "bottom-right"}
    if position not in valid_positions:
        raise ValueError(f"invalid position: {position}")

    img_w, img_h = image_size
    ovr_w, ovr_h = overlay_size

    if img_w <= 0 or img_h <= 0 or ovr_w <= 0 or ovr_h <= 0:
        raise ValueError("dimensions must be positive")

    if position == "top-left":
        x, y = margin, margin
    elif position == "top-right":
        x, y = img_w - ovr_w - margin, margin
    elif position == "bottom-left":
        x, y = margin, img_h - ovr_h - margin
    else:  # bottom-right
        x, y = img_w - ovr_w - margin, img_h - ovr_h - margin

    return (max(0, x), max(0, y))


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
