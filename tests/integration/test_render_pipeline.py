from pathlib import Path

import pytest
from PIL import Image

from frame_compare.render.batch.orchestrator import render_clip_jobs
from frame_compare.render.encoders import render_frame_detailed
from frame_compare.render.overlay import apply_overlay
from frame_compare.render.types import (
    EncoderSettings,
    OverlayConfig,
    OverlayMode,
    RenderRequest,
)
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)
from tests.render_test_support import frame_results, prepared_jobs


def _overlay_config() -> OverlayConfig:
    geometry = RenderedGeometryFacts(
        source_size=(100, 100),
        active_picture=ActivePictureFacts(0, 0, 100, 100, "full_frame", True),
        cropped_size=(100, 100),
        scaled_size=(100, 100),
        final_canvas_size=(100, 100),
        is_noop=True,
    )
    return OverlayConfig(
        mode=OverlayMode.STANDARD,
        label="Test",
        comparison_frame=1,
        source_frame=1,
        source_total_frames=10,
        include_frame_number=True,
        selection_label="Selected",
        file_size_bytes=1024,
        source_resolution=(100, 100),
        signal=SourceSignalFacts(is_hdr=False),
        presentation_state=PresentationState.SDR,
        tonemap=None,
        geometry=geometry,
        font_path=None,
        font_size=24,
    )


@pytest.mark.integration
def test_ffmpeg_render_creates_valid_png(mock_video_path: Path, integration_output_dir: Path):
    output_path = integration_output_dir / "frame_00000.png"
    request = RenderRequest(
        clip=mock_video_path,
        diagnostic_source=mock_video_path,
        frame_number=0,
        output_path=output_path,
        overlay=None,
        encoder_settings=EncoderSettings(),
    )

    result = render_frame_detailed(request, renderer="ffmpeg").path

    assert result == output_path
    assert output_path.exists()

    with Image.open(output_path) as img:
        assert img.format == "PNG"


@pytest.mark.integration
def test_overlay_application_adds_visible_content(sample_image_path: Path):
    with Image.open(sample_image_path) as img:
        config = _overlay_config()

        result = apply_overlay(img, config, RenderedFrameFacts(source_frame=1, picture_type="I"))

        pixel_data = result.get_flattened_data()
        assert len(set(pixel_data)) > 1


@pytest.mark.integration
def test_render_batch_ordering_contract(mock_video_path: Path, integration_output_dir: Path):
    requests = []
    for i in range(3):
        req = RenderRequest(
            clip=mock_video_path,
            diagnostic_source=mock_video_path,
            frame_number=i,
            output_path=integration_output_dir / f"frame_{i:05d}.png",
            overlay=None,
            encoder_settings=EncoderSettings(),
        )
        requests.append(req)

    results = [
        rendered.path
        for rendered in frame_results(render_clip_jobs(prepared_jobs(requests), parallelism=1))
    ]

    assert len(results) == 3
    for i in range(3):
        assert results[i] == requests[i].output_path
        assert results[i].exists()
        with Image.open(results[i]) as img:
            assert img.format == "PNG"


@pytest.mark.integration
def test_render_batch_empty_requests_returns_empty() -> None:
    assert render_clip_jobs(()) == ()


@pytest.mark.integration
@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
@pytest.mark.parametrize("pixel_format, png_depth", [("yuv420p", 8), ("yuv420p10le", 16)])
@pytest.mark.parametrize(
    "crop_origin, pad_origin",
    [((0, 0), (1, 0)), ((0, 0), (0, 1)), ((1, 1), (0, 0)), ((2, 2), (2, 2))],
    ids=["odd-left", "odd-top", "odd-crop", "even-control"],
)
def test_ffmpeg_geometry_preserves_exact_pixels(
    tmp_path: Path,
    require_ffmpeg: None,
    batch: bool,
    pixel_format: str,
    png_depth: int,
    crop_origin: tuple[int, int],
    pad_origin: tuple[int, int],
) -> None:
    from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
    from frame_compare.render.geometry import (
        GeometryMargins,
        GeometryRect,
        RenderGeometryPlan,
        SourceGeometry,
    )
    from frame_compare.utils.subproc import run_subprocess

    # A white rectangle on black makes a one-pixel crop/pad displacement visible.
    x, y = crop_origin
    left, top = pad_origin
    source_size = (6 + 2 * x, 4 + 2 * y)
    source_filter = f"color=white:s={source_size[0]}x{source_size[1]}:r=1"
    if x:
        source_filter += f",drawbox=x=0:y=0:w={x}:h=ih:color=black:t=fill"
    if y:
        source_filter += f",drawbox=x=0:y=0:w=iw:h={y}:color=black:t=fill"
    video = tmp_path / "white.mkv"
    run_subprocess(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            source_filter,
            "-frames:v",
            "2",
            "-c:v",
            "ffv1",
            "-pix_fmt",
            pixel_format,
            str(video),
        ],
        timeout_seconds=10,
    )
    rect = GeometryRect(0, 0, *source_size)
    crop = GeometryRect(x, y, 6, 4)
    canvas = (6 + 2 * left, 4 + 2 * top)
    plan = RenderGeometryPlan(
        source=SourceGeometry(*source_size, rect, "full_frame"),
        source_rect=rect,
        active_rect=crop,
        provenance="full_frame",
        crop_rect=crop,
        crop=GeometryMargins(x, y, x, y),
        cropped_size=(6, 4),
        scaled_size=(6, 4),
        pad=GeometryMargins(left, top, left, top),
        final_canvas_size=canvas,
        content_origin=(left, top),
        overlay_origin=(left, top),
    )
    runner = DefaultFFmpegRunner()
    if batch:
        runner.extract_frames(video, [0, 1], tmp_path / "batch", geometry_plan=plan)
        outputs = sorted((tmp_path / "batch").glob("*.png"))
        assert len(outputs) == 2
    else:
        output = tmp_path / "single.png"
        runner.extract_frame(video, 0, output, geometry_plan=plan)
        outputs = [output]
    for output in outputs:
        assert output.read_bytes()[24] == png_depth
        with Image.open(output) as image:
            assert image.size == canvas
            pixels = image.convert("RGB")
            for row in range(canvas[1]):
                for column in range(canvas[0]):
                    expected = 255 if left <= column < left + 6 and top <= row < top + 4 else 0
                    pixel = pixels.getpixel((column, row))
                    assert isinstance(pixel, tuple)
                    assert all(abs(channel - expected) <= 3 for channel in pixel)
