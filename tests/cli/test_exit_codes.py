from pathlib import Path

from frame_compare.cli.entry import handle_error
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.errors import (
    FrameExtractionError,
    GenericInternalError,
    NoVideosFoundError,
)
from frame_compare.services.errors import SlowpicsError
from frame_compare.vs.errors import (
    TonemapRequiresVapourSynthError,
    VapourSynthNotFoundError,
)


def test_handle_error_returns_exit_codes():
    # Config -> 2
    assert handle_error(ConfigNotFoundError(Path("/x")), no_color=True, verbose=False) == 2

    # Dependency -> 3
    assert handle_error(VapourSynthNotFoundError(), no_color=True, verbose=False) == 3
    assert handle_error(TonemapRequiresVapourSynthError(), no_color=True, verbose=False) == 3

    # Input -> 4
    assert handle_error(NoVideosFoundError(Path("/x")), no_color=True, verbose=False) == 4

    # Processing -> 5
    assert handle_error(FrameExtractionError(0, "clip"), no_color=True, verbose=False) == 5

    # Network -> 6
    assert handle_error(SlowpicsError("timeout"), no_color=True, verbose=False) == 6

    # Internal -> 1
    assert handle_error(GenericInternalError("fail"), no_color=True, verbose=False) == 1

    # Non FrameCompareError -> 1
    assert handle_error(ValueError("nope"), no_color=True, verbose=False) == 1
