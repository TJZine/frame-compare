"""Runtime proof for exact-frame picture facts on a tiny deterministic GOP."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image, ImageDraw

from frame_compare.config.schema import ColorConfig, ConfigSchema, OverlayMode, ReportConfig
from frame_compare.render.batch.orchestrator import render_screenshots_from_batch_detailed
from frame_compare.render.encoders import render_frame_detailed
from frame_compare.render.errors import FrameExtractionError
from frame_compare.render.types import (
    BatchRenderOptions,
    EncoderSettings,
    OverlayConfig,
    RenderedFrameResult,
    RenderRequest,
    ScreenshotBatchRequest,
    SelectedScreenshot,
)
from frame_compare.services.report.payload import (
    ClipInfo,
    ReportClipDisplayInfo,
    ReportData,
    ReportImageInfo,
    ReportRenderingInfo,
    build_report_payload,
)
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    RenderedGeometryFacts,
    SourceSignalFacts,
)
from frame_compare.utils.subproc import run_subprocess
from frame_compare.vs.env import detect_plugins
from frame_compare.vs.loader import DefaultVSLoader

vs = pytest.importorskip("vapoursynth")
if isinstance(vs, MagicMock):
    pytest.skip("vapoursynth is mocked", allow_module_level=True)
if not detect_plugins(vs.core).get("lsmas", False):
    pytest.skip("lsmas plugin not available", allow_module_level=True)


@pytest.mark.integration
@pytest.mark.vs_required
def test_deterministic_gop_picture_facts_match_vs_and_ffmpeg(tmp_path: Path) -> None:
    """Compare test-only frame truth with both production exact-frame backends."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe unavailable")
    encoders = run_subprocess(
        ["ffmpeg", "-hide_banner", "-encoders"],
        timeout_seconds=10,
    )
    if b"libx264" not in encoders.stdout:
        pytest.skip("ffmpeg libx264 encoder unavailable")

    # Adaptive B-frame placement is disabled intentionally: I/P/B presence is
    # a fixture invariant, so missing B after a successful libx264 encode is a
    # test failure rather than an environment skip.
    fixture = tmp_path / "gop.mkv"
    for ordinal in range(8):
        image = Image.new("RGB", (64, 64), "gray")
        draw = ImageDraw.Draw(image)
        for bit in range(3):
            level = "white" if ordinal & (1 << bit) else "black"
            draw.rectangle((bit * 16, 48, bit * 16 + 15, 63), fill=level)
        image.save(tmp_path / f"source-{ordinal}.png")
    run_subprocess(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            "24",
            "-i",
            str(tmp_path / "source-%d.png"),
            "-frames:v",
            "8",
            "-c:v",
            "libx264",
            "-g",
            "4",
            "-keyint_min",
            "4",
            "-bf",
            "1",
            "-b_strategy",
            "0",
            "-sc_threshold",
            "0",
            "-pix_fmt",
            "yuv420p",
            str(fixture),
        ],
        timeout_seconds=20,
    )

    # Complete-frame inspection is test-only: it establishes ground truth for
    # this tiny generated fixture and is never imported by production modules.
    scan = run_subprocess(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=pict_type",
            "-of",
            "json",
            str(fixture),
        ],
        timeout_seconds=10,
    )
    expected = [frame["pict_type"] for frame in json.loads(scan.stdout)["frames"]]
    selected = [
        index for index, picture_type in enumerate(expected) if picture_type in {"I", "P", "B"}
    ]
    assert selected
    assert {expected[index] for index in selected} >= {"I", "P", "B"}

    source_info = DefaultVSLoader().load(fixture)
    geometry = RenderedGeometryFacts(
        source_size=(64, 64),
        active_picture=ActivePictureFacts(0, 0, 64, 64, "full_frame", True),
        cropped_size=(64, 64),
        scaled_size=(64, 64),
        final_canvas_size=(64, 64),
        is_noop=True,
    )
    signal = SourceSignalFacts(is_hdr=False, primaries=1, transfer=1, matrix=1)
    results_by_backend: dict[str, list[RenderedFrameResult]] = {
        "VapourSynth": [],
        "FFmpeg": [],
    }
    for index in selected:
        overlay = OverlayConfig(
            mode=OverlayMode.MINIMAL,
            label="GOP proof",
            comparison_frame=index,
            source_frame=index,
            source_total_frames=len(expected),
            include_frame_number=True,
            selection_label=None,
            file_size_bytes=fixture.stat().st_size,
            source_resolution=(64, 64),
            signal=signal,
            presentation_state=PresentationState.SDR,
            tonemap=None,
            geometry=geometry,
            font_path=None,
            font_size=12,  # Keep the overlay above the ordinal strip.
        )
        vs_result = render_frame_detailed(
            RenderRequest(
                clip=source_info.clip,
                diagnostic_source=source_info.clip,
                frame_number=index,
                output_path=tmp_path / f"vs-{index}.png",
                overlay=overlay,
                encoder_settings=EncoderSettings(),
            ),
            renderer="vapoursynth",
        )
        ffmpeg_result = render_frame_detailed(
            RenderRequest(
                clip=fixture,
                diagnostic_source=fixture,
                frame_number=index,
                output_path=tmp_path / f"ffmpeg-{index}.png",
                overlay=overlay,
                encoder_settings=EncoderSettings(),
            ),
            renderer="ffmpeg",
        )
        assert vs_result.facts.picture_type == expected[index]
        assert ffmpeg_result.facts.picture_type == expected[index]
        for result in (vs_result, ffmpeg_result):
            with Image.open(result.path) as image:
                luma = image.convert("L").tobytes()
                ordinal = sum(
                    1 << bit for bit in range(3) if luma[56 * image.width + 8 + 16 * bit] > 128
                )
            assert ordinal == index, result.path.name
        results_by_backend["VapourSynth"].append(vs_result)
        results_by_backend["FFmpeg"].append(ffmpeg_result)

    clips = [
        ClipInfo(
            name=backend.lower(),
            path=fixture,
            frame_count=len(expected),
            resolution=(64, 64),
            fps=24.0,
            size_bytes=fixture.stat().st_size,
            signal=signal,
            presentation_state=PresentationState.SDR,
            tonemap=None,
            active_picture=geometry.active_picture,
            images=[
                ReportImageInfo(result.path, index, result.facts)
                for index, result in zip(selected, results, strict=True)
            ],
            display=ReportClipDisplayInfo(
                primary=backend,
                release="",
                control=backend,
                micro=backend,
                filename=fixture.name,
            ),
            label=backend,
        )
        for backend, results in results_by_backend.items()
    ]
    payload = build_report_payload(
        ReportData(
            clips=clips,
            frames=selected,
            rendering=ReportRenderingInfo(
                overlay_mode=OverlayMode.MINIMAL,
                include_frame_number=True,
                geometry_by_label=dict.fromkeys(results_by_backend, geometry),
            ),
        ),
        ReportConfig(embed_images=False),
        report_dir=tmp_path,
    )
    for frame_index, frame in enumerate(payload["frames"]):
        assert [image["picture_type"] for image in frame["images"]] == [
            expected[selected[frame_index]],
            expected[selected[frame_index]],
        ]


@pytest.mark.integration
@pytest.mark.vs_required
def test_ffmpeg_refuses_repeat_flagged_mpeg2_on_lsmash_timeline(
    tmp_path: Path, require_ffmpeg: None
) -> None:
    video = tmp_path / "repeat-first-field.m2v"
    run_subprocess(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=96x64:rate=25",
            "-frames:v",
            "4",
            "-c:v",
            "mpeg2video",
            "-g",
            "1",
            "-f",
            "mpeg2video",
            str(video),
        ],
        timeout_seconds=10,
    )

    stream = video.read_bytes()
    extension = b"\x00\x00\x01\xb5"
    # Extension id 8 identifies a picture coding extension. Set repeat_first_field
    # on only the first progressive picture, where it requests one extra display.
    first_picture_extension = next(
        offset
        for offset in range(len(stream) - 7)
        if stream.startswith(extension, offset) and stream[offset + 4] >> 4 == 8
    )
    data = bytearray(stream)
    data[first_picture_extension + 7] |= 0b10
    video.write_bytes(data)

    source = DefaultVSLoader().load(video)
    assert source.num_frames == 5
    request = ScreenshotBatchRequest(
        clip_path=video,
        label="Repeated picture",
        frames=(SelectedScreenshot(1, 1, None),),
        size_bytes=video.stat().st_size,
        source_resolution=(source.width, source.height),
        source_total_frames=source.num_frames,
        signal=SourceSignalFacts(is_hdr=False),
        active_picture=ActivePictureFacts(0, 0, source.width, source.height, "full_frame", True),
    )
    output_dir = tmp_path / "screenshots"
    with pytest.raises(
        FrameExtractionError,
        match="FFmpeg decoded 4 frames but the prepared L-SMASH timeline has 5",
    ) as exc:
        render_screenshots_from_batch_detailed(
            [request],
            output_dir,
            ConfigSchema(color=ColorConfig(enable_tonemap=False)),
            BatchRenderOptions(renderer="ffmpeg", overlay_mode=OverlayMode.NONE),
        )

    assert video.name in exc.value.context.message
    assert exc.value.context.hint == "Use the VapourSynth renderer"
    assert not list(output_dir.glob("*.png"))
