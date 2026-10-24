from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from frame_compare.config.loader import get_default_config
from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_enums import OverlayMode
from frame_compare.render.batch.expansion import expand_batch_render_requests
from frame_compare.render.types import PreparedRenderSource, ScreenshotBatchRequest
from frame_compare.utils.media_facts import ActivePictureFacts, PresentationState, SourceSignalFacts
from tests.render_test_support import selections


def _request() -> ScreenshotBatchRequest:
    return ScreenshotBatchRequest(
        clip_path=Path("source.mkv"),
        label="CtrlHD",
        frames=selections([1855], [1842], ["Bright"]),
        size_bytes=int(17.42 * 1024**3),
        source_resolution=(3840, 2160),
        source_total_frames=143892,
        signal=SourceSignalFacts(is_hdr=False),
        active_picture=ActivePictureFacts(0, 0, 3840, 2160, "full_frame", True),
    )


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_overlay_config_contains_structured_facts_and_original_diagnostic_source(
    mock_prepare: MagicMock,
) -> None:
    original = MagicMock(name="decoded_source")
    prepared_graph = MagicMock(name="prepared_graph")
    mock_prepare.return_value = PreparedRenderSource(
        diagnostic_source=original,
        prepared_clip=prepared_graph,
        source_dimensions=(3840, 2160),
        source_total_frames=143892,
        source_is_hdr=False,
        presentation_state=PresentationState.SDR,
        tonemap=None,
    )
    jobs = expand_batch_render_requests(
        [_request()],
        output_dir=Path("out"),
        config=get_default_config(),
        overlay_mode=OverlayMode.DIAGNOSTIC,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )
    requests = [request for job in jobs for request in job.requests]
    facts = {job.label: job.clip_facts for job in jobs}
    request = requests[0]
    assert request.clip is prepared_graph
    assert request.diagnostic_source is original
    assert request.overlay is not None
    assert request.overlay.label == "CtrlHD"
    assert request.overlay.comparison_frame == 1842
    assert request.overlay.source_frame == 1855
    assert request.overlay.source_total_frames == 143892
    assert request.overlay.file_size_bytes == int(17.42 * 1024**3)
    assert request.overlay.geometry is facts["CtrlHD"].geometry


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_none_overlay_mode_does_not_create_overlay_config(mock_prepare: MagicMock) -> None:
    source = MagicMock()
    mock_prepare.return_value = PreparedRenderSource(
        diagnostic_source=source,
        prepared_clip=source,
        source_dimensions=(3840, 2160),
        source_total_frames=143892,
        source_is_hdr=False,
        presentation_state=PresentationState.SDR,
        tonemap=None,
    )
    jobs = expand_batch_render_requests(
        [_request()],
        output_dir=Path("out"),
        config=get_default_config(),
        overlay_mode=OverlayMode.NONE,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )
    requests = [request for job in jobs for request in job.requests]
    assert requests[0].overlay is None


def test_actual_preparation_preserves_mixed_applied_facts_and_fallback_graph(
    tmp_path: Path,
) -> None:
    from dataclasses import replace
    from fractions import Fraction

    import vapoursynth as vs

    from frame_compare.config.schema import ColorConfig, ToneCurve
    from frame_compare.render.overlay_text import compose_overlay_text_lines
    from frame_compare.utils.media_facts import RenderedFrameFacts
    from frame_compare.vs.types import FallbackTonemap, HDRMetadata, LibplaceboTonemap, SourceInfo

    graphs = [MagicMock(name="placebo_source"), MagicMock(name="fallback_source")]
    for graph in graphs:
        graph.format.id = vs.RGBS
        graph.format.color_family = vs.RGB
        graph.format.bits_per_sample = 32
        graph.get_frame.return_value.props = {"_Matrix": 0, "_Primaries": 9, "_Transfer": 16}
        graph.resize.Bicubic.return_value = graph
        graph.resize.Point.return_value = graph
        graph.std.SetFrameProps.return_value = graph
        graph.std.Expr.return_value = graph
    sources = [
        SourceInfo(
            graph,
            3840,
            2160,
            143892,
            Fraction(24),
            graph.format,
            {},
            True,
            HDRMetadata(None, 609, None, 9, 16, 0),
        )
        for graph in graphs
    ]
    config = ConfigSchema(
        color=ColorConfig(enable_tonemap=True, tone_curve=ToneCurve.SPLINE, target_nits=203)
    )
    with (
        patch("frame_compare.vs.loader.DefaultVSLoader") as loader,
        patch("frame_compare.vs.env.detect_plugins", return_value={"libplacebo": True}),
        patch("frame_compare.vs.tonemap._libplacebo_runtime_usable", return_value=True),
        patch("vapoursynth.core", MagicMock()) as core,
    ):
        loader.return_value.load.side_effect = sources
        core.placebo.Tonemap.side_effect = [graphs[0], RuntimeError("device failed")]
        jobs = expand_batch_render_requests(
            [_request(), replace(_request(), label="Fallback", clip_path=Path("fallback.mkv"))],
            output_dir=Path("out"),
            config=config,
            overlay_mode=OverlayMode.DIAGNOSTIC,
            renderer="vapoursynth",
            ffmpeg_runner=MagicMock(),
        )
        requests = [request for job in jobs for request in job.requests]
        facts = {job.label: job.clip_facts for job in jobs}
    assert facts["CtrlHD"].tonemap is not None
    assert facts["Fallback"].tonemap is not None
    assert requests[1].overlay is not None
    assert isinstance(facts["CtrlHD"].tonemap.transform, LibplaceboTonemap)
    assert facts["CtrlHD"].tonemap.transform.frame_policy == "independent_frames"
    assert isinstance(facts["Fallback"].tonemap.transform, FallbackTonemap)
    assert facts["Fallback"].tonemap.transform.cause.value == "runtime_call_failed"
    assert facts["Fallback"].tonemap.transform.source_peak.nits == 609
    assert requests[1].overlay.tonemap is facts["Fallback"].tonemap
    lines = compose_overlay_text_lines(requests[1].overlay, RenderedFrameFacts(1855, "B"))
    assert "Tonemap: fallback (peak-scaled) → 203 nits" in lines
    assert all("Spline" not in line for line in lines)
    graphs[1].std.Expr.assert_called_once_with(expr=["x 3 * dup 1 + / 2 * 0 max 1 min"] * 3)
    graphs[1].std.SetFrameProps.assert_called_once_with(
        _Matrix=0, _ColorRange=0, _Transfer=16, _Primaries=9
    )

    # Carry the records from actual dispatch/preparation through the real serializer.
    from frame_compare.config.schema import ReportConfig
    from frame_compare.services.report.payload import (
        ClipInfo,
        ReportClipDisplayInfo,
        ReportData,
        ReportImageInfo,
        ReportRenderingInfo,
        build_report_payload,
    )

    clips = []
    for label, clip_facts in facts.items():
        image = tmp_path / f"{label}.png"
        image.write_bytes(b"png")
        clips.append(
            ClipInfo(
                name=label,
                path=Path(f"{label}.mkv"),
                frame_count=143892,
                resolution=(3840, 2160),
                fps=24,
                size_bytes=clip_facts.size_bytes,
                signal=clip_facts.signal,
                presentation_state=clip_facts.presentation_state,
                tonemap=clip_facts.tonemap,
                active_picture=clip_facts.geometry.active_picture,
                images=[ReportImageInfo(image, 1855, RenderedFrameFacts(1855, "B"))],
                display=ReportClipDisplayInfo(label, label, label, label, f"{label}.mkv"),
            )
        )
    data = ReportData(
        clips=clips,
        frames=[1842],
        rendering=ReportRenderingInfo(
            OverlayMode.DIAGNOSTIC,
            True,
            {label: item.geometry for label, item in facts.items()},
        ),
    )
    payload = build_report_payload(data, ReportConfig(embed_images=False), report_dir=tmp_path)
    assert payload["rendering"]["tonemap"]["shared"] is None
    left = payload["clips"][0]["presentation"]["tonemap"]
    right = payload["clips"][1]["presentation"]["tonemap"]
    assert left is not None and right is not None
    assert left["implementation"] == "libplacebo"
    assert right["implementation"] == "fallback"
    assert left["source_peak_nits"] == right["source_peak_nits"] == 609
    all_placebo = replace(data, clips=[clips[0], replace(clips[1], tonemap=clips[0].tonemap)])
    assert (
        build_report_payload(all_placebo, ReportConfig(embed_images=False), report_dir=tmp_path)[
            "report_id"
        ]
        != payload["report_id"]
    )
