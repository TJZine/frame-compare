from pathlib import Path

import pytest

from frame_compare.cli.entry import handle_error
from frame_compare.config.errors import ConfigNotFoundError
from frame_compare.errors import ErrorContext, FrameCompareError
from frame_compare.orchestration.errors import NoVideosFoundError
from frame_compare.render.errors import FrameExtractionError
from frame_compare.services.errors import SlowpicsError
from frame_compare.vs.errors import (
    TonemapRequiresVapourSynthError,
    VapourSynthNotFoundError,
)


@pytest.mark.parametrize(
    ("error", "expected_exit"),
    [
        pytest.param(ConfigNotFoundError(Path("/x")), 2, id="config"),
        pytest.param(VapourSynthNotFoundError(), 3, id="vapoursynth"),
        pytest.param(TonemapRequiresVapourSynthError(), 3, id="tonemap"),
        pytest.param(NoVideosFoundError(Path("/x")), 4, id="input"),
        pytest.param(FrameExtractionError(0, "clip"), 5, id="processing"),
        pytest.param(SlowpicsError("timeout"), 6, id="network"),
        pytest.param(
            FrameCompareError(ErrorContext(code="FC-9000", name="INTERNAL", message="fail")),
            1,
            id="internal",
        ),
        pytest.param(ValueError("nope"), 1, id="unexpected"),
    ],
)
def test_handle_error_returns_exit_codes(error: Exception, expected_exit: int) -> None:
    assert handle_error(error, no_color=True, verbose=False) == expected_exit
