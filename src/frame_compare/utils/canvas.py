"""Size policy shared by configuration and native media allocation boundaries."""

MAX_CANVAS_AXIS = 7680
MAX_CANVAS_PIXELS = 7680 * 4320  # The supported UHD 8K profile.
_SIZE_HINT = (
    f"Use a positive size of at most {MAX_CANVAS_AXIS:,} pixels per axis "
    f"and {MAX_CANVAS_PIXELS:,} pixels total."
)


def validate_canvas_size(width: int, height: int, *, label: str) -> None:
    """Reject unsafe sizes before multiplying or passing them to native code."""
    if (
        type(width) is not int
        or type(height) is not int
        or not 1 <= width <= MAX_CANVAS_AXIS
        or not 1 <= height <= MAX_CANVAS_AXIS
        or width * height > MAX_CANVAS_PIXELS
    ):
        raise ValueError(f"{label} dimensions are out of bounds. {_SIZE_HINT}")
