from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from frame_compare.render import render_frame
from frame_compare.render.types import EncoderSettings, RenderRequest

# Skip policy at module level
vs = pytest.importorskip("vapoursynth")
if isinstance(vs, MagicMock):
    pytest.skip("vapoursynth is mocked", allow_module_level=True)


@pytest.mark.integration
@pytest.mark.vs_required
def test_vs_render_creates_valid_png(tmp_path: Path):
    """Verify VapourSynth renderer creates a valid PNG."""
    core = vs.core
    # BlankClip with width=100, height=100, length=3, format=vs.RGB24 (8-bit)
    clip = core.std.BlankClip(width=100, height=100, length=3, format=vs.RGB24, color=[255, 0, 0])

    output_path = tmp_path / "vs_frame_00000.png"
    request = RenderRequest(
        clip=clip,
        frame_number=0,
        output_path=output_path,
        overlay=None,
        encoder_settings=EncoderSettings(),
    )

    result = render_frame(request, renderer="vapoursynth")

    assert result == output_path
    assert output_path.exists()

    with Image.open(output_path) as img:
        assert img.format == "PNG"
