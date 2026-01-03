from pathlib import Path

import pytest
from PIL import Image

from frame_compare.render import apply_overlay, render_batch, render_frame
from frame_compare.render.types import (
    EncoderSettings,
    OverlayConfig,
    OverlayMode,
    RenderRequest,
)


@pytest.mark.integration
def test_ffmpeg_render_creates_valid_png(mock_video_path: Path, integration_output_dir: Path):
    """Verify FFmpeg renderer creates a valid PNG."""
    output_path = integration_output_dir / "frame_00000.png"
    request = RenderRequest(
        clip=mock_video_path,
        frame_number=0,
        output_path=output_path,
        overlay=None,
        encoder_settings=EncoderSettings(),
    )

    result = render_frame(request, renderer="ffmpeg")

    assert result == output_path
    assert output_path.exists()

    with Image.open(output_path) as img:
        assert img.format == "PNG"


@pytest.mark.integration
def test_overlay_application_adds_visible_content(sample_image_path: Path):
    """Verify overlay application modifies the image content.

    This test does NOT depend on mock_video_path so it runs even if FFmpeg is missing.
    """
    with Image.open(sample_image_path) as img:
        # Initial image is solid red
        config = OverlayConfig(
            mode=OverlayMode.STANDARD,
            label="Test",
            frame_number=1,
            resolution=(100, 100),
            hdr_info=None,
            font_path=None,
            font_size=24,
            position="top-left",
        )

        result = apply_overlay(img, config)

        # Check that we have more than one color (originally solid red)
        # Use compatible approach that works with Pillow < 14 and >= 14
        try:
            # Pillow >= 14 preferred method
            pixel_data = result.get_flattened_data()
        except AttributeError:
            # Pillow < 14 fallback (getdata still works, suppress warning)
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                pixel_data = list(result.getdata())
        assert len(set(pixel_data)) > 1


@pytest.mark.integration
def test_render_batch_ordering_contract(mock_video_path: Path, integration_output_dir: Path):
    """Verify render_batch preserves input ordering."""
    requests = []
    for i in range(3):
        req = RenderRequest(
            clip=mock_video_path,
            frame_number=i,
            output_path=integration_output_dir / f"frame_{i:05d}.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
        )
        requests.append(req)

    results = render_batch(requests, parallelism=1)

    assert len(results) == 3
    for i in range(3):
        # Result order must match input order
        assert results[i] == requests[i].output_path
        assert results[i].exists()
        with Image.open(results[i]) as img:
            assert img.format == "PNG"
