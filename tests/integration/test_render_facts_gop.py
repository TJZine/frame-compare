"""Runtime proof for exact-frame picture facts on a tiny deterministic GOP."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image, ImageDraw

from frame_compare.config.schema import ConfigSchema, OverlayMode, ReportConfig
from frame_compare.render.batch.orchestrator import render_screenshots_from_batch_detailed
from frame_compare.render.encoders import render_frame_detailed
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
def test_deterministic_gop_picture_facts_from_vapoursynth(tmp_path: Path) -> None:
    """Check VapourSynth screenshot facts and pixels against independent frame truth."""
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
    results: list[RenderedFrameResult] = []
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
        )
        assert vs_result.facts.picture_type == expected[index]
        with Image.open(vs_result.path) as image:
            luma = image.convert("L").tobytes()
            ordinal = sum(
                1 << bit for bit in range(3) if luma[56 * image.width + 8 + 16 * bit] > 128
            )
        assert ordinal == index, vs_result.path.name
        results.append(vs_result)

    clip = ClipInfo(
        name="vapoursynth",
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
            primary="VapourSynth",
            release="",
            control="VapourSynth",
            micro="VapourSynth",
            filename=fixture.name,
        ),
        label="VapourSynth",
    )
    payload = build_report_payload(
        ReportData(
            clips=[clip],
            frames=selected,
            rendering=ReportRenderingInfo(
                overlay_mode=OverlayMode.MINIMAL,
                include_frame_number=True,
                geometry_by_label={"VapourSynth": geometry},
            ),
        ),
        ReportConfig(embed_images=False),
        report_dir=tmp_path,
    )
    for frame_index, frame in enumerate(payload["frames"]):
        assert [image["picture_type"] for image in frame["images"]] == [
            expected[selected[frame_index]],
        ]


@pytest.mark.integration
@pytest.mark.vs_required
@pytest.mark.parametrize(
    ("size", "matrix_tag", "decoded_hdr", "signal", "expected"),
    [
        pytest.param(
            (704, 576), None, False, SourceSignalFacts(False), (179, 72, 1), id="untagged-sd"
        ),
        pytest.param(
            (1280, 536),
            None,
            False,
            SourceSignalFacts(False),
            (191, 80, 0),
            id="untagged-hd-cropped-to-sd",
        ),
        pytest.param(
            (704, 576),
            "bt709",
            True,
            SourceSignalFacts(True, 9, 16, 1),
            (191, 80, 0),
            id="tagged-hdr",
        ),
        pytest.param(
            (704, 576),
            None,
            True,
            SourceSignalFacts(True, 9, 16),
            (185, 72, 0),
            id="untagged-hdr",
        ),
        pytest.param(
            (704, 576),
            None,
            False,
            SourceSignalFacts(True, 9, 16, 1),
            (191, 80, 0),
            id="prepared-matrix-before-hdr",
        ),
        pytest.param(
            (704, 576),
            None,
            False,
            SourceSignalFacts(True, 9, 16),
            (185, 72, 0),
            id="prepared-hdr-before-sd",
        ),
    ],
)
def test_vapoursynth_chooses_matrix_from_tag_hdr_or_coded_size(
    tmp_path: Path,
    require_ffmpeg: None,
    size: tuple[int, int],
    matrix_tag: str | None,
    decoded_hdr: bool,
    signal: SourceSignalFacts,
    expected: tuple[int, int, int],
) -> None:
    width, height = size
    video = tmp_path / "patch.mkv"
    signal_filter = f"setparams=range=limited:colorspace={matrix_tag or 'unknown'}"
    if decoded_hdr:
        signal_filter += ":color_primaries=bt2020:color_trc=smpte2084"
    run_subprocess(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=s={width}x{height}:r=1,geq=lum=100:cb=80:cr=180,{signal_filter}",
            "-frames:v",
            "2",
            "-c:v",
            "libx264",
            "-qp",
            "0",
            str(video),
        ],
        timeout_seconds=15,
    )

    # Check the decoder sees the intended bitstream tags before testing rendering.
    source = DefaultVSLoader().load(video)
    assert source.is_hdr is decoded_hdr
    assert source.clip.get_frame(0).props["_Matrix"] == (1 if matrix_tag else 2)

    # The selected picture fits the SD rule even when the coded source does not.
    active = ActivePictureFacts(0, 0, 704, min(height, 576), "explicit", width == 704)
    request = ScreenshotBatchRequest(
        clip_path=video,
        label="Patch",
        frames=tuple(SelectedScreenshot(i, i, None) for i in range(2)),
        size_bytes=video.stat().st_size,
        source_resolution=size,
        source_total_frames=2,
        signal=signal,
        active_picture=active,
    )
    config = ConfigSchema.model_validate(
        {"color": {"enable_tonemap": False}, "screenshots": {"geometry_mode": "aligned"}}
    )
    _assert_rendered_patch(tmp_path, request, config, (active.width, active.height), expected)


@pytest.mark.integration
@pytest.mark.vs_required
@pytest.mark.parametrize(
    ("matrix_name", "matrix", "transfer", "expected"),
    [
        # Direct matrix conversions of the generated 10-bit patch, before any
        # crop, scale or pad. Both differ from the NCL/BT.601 controls.
        pytest.param("ycgco", 8, None, (191, 54, 93), id="ycgco"),
        pytest.param("bt2020c", 10, 14, (161, 101, 41), id="bt2020-constant-luminance"),
        pytest.param("bt2020c", 10, None, (161, 101, 41), id="bt2020-cl-implicit-transfer"),
    ],
)
def test_vapoursynth_preserves_tagged_matrix_through_geometry(
    tmp_path: Path,
    require_ffmpeg: None,
    matrix_name: str,
    matrix: int,
    transfer: int | None,
    expected: tuple[int, int, int],
) -> None:
    video = tmp_path / "patch.mkv"
    signal = f"setparams=range=limited:colorspace={matrix_name}:color_primaries=bt2020"
    if transfer is not None:
        signal += ":color_trc=bt2020-10"
    run_subprocess(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=s=64x48:r=1,format=yuv444p10le,geq=lum=400:cb=360:cr=680,{signal}",
            "-frames:v",
            "2",
            "-c:v",
            "ffv1",
            str(video),
        ],
        timeout_seconds=15,
    )
    props = DefaultVSLoader().load(video).clip.get_frame(0).props
    assert props["_Matrix"] == matrix
    assert props["_Transfer"] == (transfer if transfer is not None else 2)

    request = ScreenshotBatchRequest(
        clip_path=video,
        label="Patch",
        frames=tuple(SelectedScreenshot(i, i, None) for i in range(2)),
        size_bytes=video.stat().st_size,
        source_resolution=(64, 48),
        source_total_frames=2,
        signal=SourceSignalFacts(False, primaries=9, transfer=transfer, matrix=matrix),
        active_picture=ActivePictureFacts(0, 0, 60, 48, "explicit", False),
    )
    config = ConfigSchema.model_validate(
        {
            "color": {"enable_tonemap": False},
            "screenshots": {
                "geometry_mode": "aligned",
                "aligned_scale_policy": "explicit_size",
                "aligned_target_width": 40,
                "aligned_target_height": 40,
            },
        }
    )
    _assert_rendered_patch(tmp_path, request, config, (40, 40), expected)


def _assert_rendered_patch(
    tmp_path: Path,
    request: ScreenshotBatchRequest,
    config: ConfigSchema,
    canvas: tuple[int, int],
    expected: tuple[int, int, int],
) -> None:
    (clip,) = render_screenshots_from_batch_detailed(
        [request],
        tmp_path / "vapoursynth-2",
        config,
        BatchRenderOptions(overlay_mode=OverlayMode.NONE),
    )
    assert len(clip.screenshots) == 2
    assert clip.clip_facts.signal == request.signal
    mismatches = []
    for screenshot in clip.screenshots:
        with Image.open(screenshot.result.path) as image:
            assert image.size == canvas
            pixel = image.getpixel((canvas[0] // 2, canvas[1] // 2))
            assert isinstance(pixel, tuple)
            if any(
                abs(channel - target) > 3 for channel, target in zip(pixel, expected, strict=True)
            ):
                mismatches.append((pixel, expected))
    assert not mismatches
