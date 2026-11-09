import asyncio
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from frame_compare.render.backend.ffmpeg import DefaultFFmpegRunner
from frame_compare.render.batch.orchestrator import render_clip_jobs
from frame_compare.render.encoders import render_ffmpeg_batch_detailed, render_frame_detailed
from frame_compare.render.errors import FrameExtractionError
from frame_compare.render.overlay import apply_overlay
from frame_compare.render.types import (
    EncoderSettings,
    OverlayConfig,
    OverlayMode,
    RenderRequest,
)
from frame_compare.utils.cancellation import _RunInterrupt, cancellation_checkpoint
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedFrameFacts,
    RenderedGeometryFacts,
    SourceSignalFacts,
)
from frame_compare.utils.subproc import resolve_executable, run_subprocess
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
def test_default_ffmpeg_runner_extract_frame_preserves_literal_output_name(
    mock_video_path: Path, tmp_path: Path
) -> None:
    output = tmp_path / "shots" / "source%03d.png"
    output.parent.mkdir()
    sentinel = output.with_name("source001.png")
    sentinel.write_bytes(b"sentinel")

    DefaultFFmpegRunner().extract_frame(mock_video_path, 1, output)

    assert sentinel.read_bytes() == b"sentinel"
    with Image.open(output) as image:
        assert image.size == (100, 100)


@pytest.mark.integration
def test_default_ffmpeg_runner_rejects_zero_output(mock_video_path: Path, tmp_path: Path) -> None:
    output = tmp_path / "existing.png"
    output.write_bytes(b"existing image")

    with pytest.raises(FrameExtractionError, match="produced no image"):
        DefaultFFmpegRunner().extract_frame(mock_video_path, 99, output)

    assert output.read_bytes() == b"existing image"
    assert not list(tmp_path.glob(".frame-compare-ffmpeg-*"))


@pytest.mark.integration
def test_ffmpeg_batch_treats_output_ancestor_as_literal(
    mock_video_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    source = Path(mock_video_path.name)
    output_dir = Path("shots%03d")
    runner = DefaultFFmpegRunner()
    requests = [
        RenderRequest(
            source, source, frame, output_dir / f"{frame}.png", None, EncoderSettings(), runner
        )
        for frame in (0, 1)
    ]

    results = render_ffmpeg_batch_detailed(requests)

    for result in results:
        with Image.open(result.path) as image:
            assert image.size == (100, 100)


@pytest.mark.integration
@pytest.mark.skipif(os.name == "nt", reason="POSIX relative PATH and executable symlink")
def test_ffmpeg_batch_resolves_relative_path_from_caller(
    mock_video_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ffmpeg = Path(resolve_executable("ffmpeg")).absolute()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "ffmpeg").symlink_to(ffmpeg)
    (bin_dir / "ffprobe").symlink_to(Path(resolve_executable("ffprobe")).absolute())
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FRAME_COMPARE_FFMPEG_EXECUTABLE", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_FFPROBE_EXECUTABLE", raising=False)
    monkeypatch.setenv("PATH", "bin")

    staging = Path("staging")
    frames = DefaultFFmpegRunner().extract_frames(mock_video_path, [0, 1], staging)

    assert [frame.source_frame for frame in frames] == [0, 1]
    for index in range(2):
        with Image.open(staging / f"{index:09d}.png") as image:
            assert image.size == (100, 100)


@pytest.mark.integration
@pytest.mark.skipif(os.name == "nt", reason="POSIX ffprobe SIGINT exit status")
@pytest.mark.parametrize("interrupt", [True, False], ids=["interrupt", "unrelated_failure"])
def test_ffprobe_count_handles_child_exit_with_cancellation_pending(
    tmp_path: Path, require_ffmpeg: None, monkeypatch: pytest.MonkeyPatch, interrupt: bool
) -> None:
    returncodes: list[int] = []

    class CountProcess(subprocess.Popen[bytes]):
        def poll(self) -> int | None:
            if self.returncode is not None:
                return self.returncode
            if interrupt:
                os.kill(self.pid, signal.SIGINT)
            # Queue cancellation before the real exit status reaches run_subprocess.
            # This forces the race without relying on the scheduler or polling interval.
            try:
                code = super().wait(timeout=5)
            finally:
                if self.stdin is not None:
                    self.stdin.close()
            returncodes.append(code)
            task = asyncio.current_task()
            assert task is not None
            task.cancel()
            return code

    def start_count(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        assert kwargs["start_new_session"] is True
        if interrupt:
            kwargs["stdin"] = subprocess.PIPE
        return CountProcess(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", start_count)
    runner = DefaultFFmpegRunner()
    source = Path("pipe:0") if interrupt else tmp_path / "absent.mkv"

    async def run_count() -> None:
        if interrupt:
            with pytest.raises(_RunInterrupt):
                runner.validate_source_frame_count(source, 4, 1)
        else:
            with pytest.raises(FrameExtractionError, match="Could not count") as exc:
                runner.validate_source_frame_count(source, 4, 1)
            assert isinstance(exc.value.__cause__, subprocess.CalledProcessError)
        await cancellation_checkpoint()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_count())
    assert returncodes == [-signal.SIGINT if interrupt else 1]


@pytest.mark.integration
@pytest.mark.parametrize("batch", [False, True], ids=["single", "batch"])
def test_ffmpeg_render_preserves_coded_orientation(
    tmp_path: Path, require_ffmpeg: None, batch: bool
) -> None:
    coded = tmp_path / "coded.mp4"
    run_subprocess(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=96x64:r=5,drawbox=x=0:y=0:w=28:h=20:color=red:t=fill",
            "-frames:v",
            "2",
            "-c:v",
            "libx264",
            str(coded),
        ],
        timeout_seconds=10,
    )
    tagged = tmp_path / "rotated.mp4"
    run_subprocess(
        [
            "ffmpeg",
            "-display_rotation",
            "90",
            "-i",
            str(coded),
            "-c",
            "copy",
            str(tagged),
        ],
        timeout_seconds=10,
    )
    runner = DefaultFFmpegRunner()
    requests = [
        RenderRequest(
            tagged, tagged, frame, tmp_path / f"{frame}.png", None, EncoderSettings(), runner
        )
        for frame in (0, 1)
    ]
    results = (
        render_ffmpeg_batch_detailed(requests) if batch else [render_frame_detailed(requests[0])]
    )

    for result in results:
        with Image.open(result.path) as image:
            assert image.size == (96, 64)
            rgb = image.convert("RGB")
            landmark = rgb.getpixel((10, 10))
            background = rgb.getpixel((85, 54))
            assert isinstance(landmark, tuple) and isinstance(background, tuple)
            red, green, blue = landmark
            assert red > 220 and green < 30 and blue < 30
            assert max(background) < 30


@pytest.mark.integration
@pytest.mark.parametrize("frame_nums", [(5,), (1, 5)], ids=["single", "batch"])
def test_ffmpeg_render_refuses_filtergraph_reconfiguration(
    tmp_path: Path, require_ffmpeg: None, frame_nums: tuple[int, ...]
) -> None:
    for index, (size, frame_count) in enumerate((("96x64", 3), ("128x80", 7))):
        run_subprocess(
            [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size={size}:rate=5",
                "-frames:v",
                str(frame_count),
                "-c:v",
                "libx264",
                "-bf",
                "0",
                str(tmp_path / f"segment{index}.mkv"),
            ],
            timeout_seconds=10,
        )
    playlist = tmp_path / "concat.txt"
    playlist.write_text("file segment0.mkv\nfile segment1.mkv\n", encoding="utf-8")
    source = tmp_path / "resized.mkv"
    run_subprocess(
        ["ffmpeg", "-f", "concat", "-i", str(playlist), "-c", "copy", str(source)],
        timeout_seconds=10,
    )
    runner = DefaultFFmpegRunner()
    requests = [
        RenderRequest(
            source, source, frame, tmp_path / f"{frame}.png", None, EncoderSettings(), runner
        )
        for frame in frame_nums
    ]

    with pytest.raises(FrameExtractionError, match="reconfigured its filter graph") as exc:
        if len(requests) == 1:
            render_frame_detailed(requests[0])
        else:
            render_ffmpeg_batch_detailed(requests)

    assert exc.value.context.hint == "Use the VapourSynth renderer"
    assert not any(request.output_path.exists() for request in requests)


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
@pytest.mark.parametrize("pixel_format", ["yuv420p", "yuv420p10le"])
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
    crop_origin: tuple[int, int],
    pad_origin: tuple[int, int],
) -> None:
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
        assert output.read_bytes()[24:26] == bytes((8, 2))
        with Image.open(output) as image:
            assert image.size == canvas
            pixels = image.convert("RGB")
            for row in range(canvas[1]):
                for column in range(canvas[0]):
                    expected = 255 if left <= column < left + 6 and top <= row < top + 4 else 0
                    pixel = pixels.getpixel((column, row))
                    assert isinstance(pixel, tuple)
                    assert all(abs(channel - expected) <= 3 for channel in pixel)


@pytest.mark.integration
def test_ffmpeg_padding_preserves_lossless_rgb_samples(
    tmp_path: Path, require_ffmpeg: None
) -> None:
    from frame_compare.render.geometry import GeometryRect, SourceGeometry, plan_render_geometry

    video = tmp_path / "rgb.mkv"
    source = Image.new("RGB", (64, 96))
    source.putdata([(x * 4, y * 2, (3 * x + 5 * y) % 256) for y in range(96) for x in range(64)])
    source.save(tmp_path / "rgb.png")
    run_subprocess(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(tmp_path / "rgb.png"),
            "-c:v",
            "ffv1",
            "-pix_fmt",
            "bgr0",
            str(video),
        ],
        timeout_seconds=10,
    )
    plan, _ = plan_render_geometry(
        (
            SourceGeometry(64, 96, GeometryRect(0, 0, 64, 96), "full_frame"),
            SourceGeometry(96, 96, GeometryRect(0, 0, 96, 96), "full_frame"),
        ),
        mode="aligned",
    )
    output = tmp_path / "padded.png"
    DefaultFFmpegRunner().extract_frame(video, 0, output, geometry_plan=plan)
    with Image.open(output) as image:
        assert image.size == (96, 96)
        assert image.crop((0, 0, 16, 96)).getbbox() is None
        assert image.crop((16, 0, 80, 96)).tobytes() == source.tobytes()
        assert image.crop((80, 0, 96, 96)).getbbox() is None
