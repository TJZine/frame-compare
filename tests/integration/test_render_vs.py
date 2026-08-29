from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from frame_compare.render.encoders import render_frame
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
        diagnostic_source=clip,
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


@pytest.mark.integration
@pytest.mark.vs_required
def test_vs_render_converts_rgbs_to_png(tmp_path: Path):
    """Verify VapourSynth renderer converts float RGBS clips for PNG output."""
    core = vs.core
    # Float RGB uses normalized 0..1 values.
    clip = core.std.BlankClip(
        width=32,
        height=32,
        length=1,
        format=vs.RGBS,
        color=[0.25, 0.5, 0.75],
    )

    output_path = tmp_path / "vs_frame_rgbs.png"
    request = RenderRequest(
        clip=clip,
        diagnostic_source=clip,
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
        extrema = img.getextrema()
        assert extrema is not None
        assert all(channel_max > 0 for _, channel_max in extrema)
