"""Runtime proof for exact-frame picture facts on a tiny deterministic GOP."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.config.schema import OverlayMode, ReportConfig
from frame_compare.render.encoders import render_frame_detailed
from frame_compare.render.types import (
    EncoderSettings,
    OverlayConfig,
    RenderedFrameResult,
    RenderRequest,
)
from frame_compare.services.report.payload import (
    ClipInfo,
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
from frame_compare.vs.loader import DefaultVSLoader

vs = pytest.importorskip("vapoursynth")
if isinstance(vs, MagicMock):
    pytest.skip("vapoursynth is mocked", allow_module_level=True)


@pytest.mark.integration
@pytest.mark.vs_required
def test_deterministic_gop_picture_facts_match_vs_and_ffmpeg(tmp_path: Path) -> None:
    """Compare test-only frame truth with both production exact-frame backends."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe unavailable")

    fixture = tmp_path / "gop.mkv"
    run_subprocess(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=64x64:rate=24",
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
            tonemap_settings=None,
            geometry=geometry,
            font_path=None,
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
        assert vs_result.path.exists()
        assert ffmpeg_result.path.exists()
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
            tonemap_settings=None,
            active_picture=geometry.active_picture,
            images=[
                ReportImageInfo(result.path, index, result.facts)
                for index, result in zip(selected, results, strict=True)
            ],
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
                tonemap_settings=None,
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
