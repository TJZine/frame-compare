from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from frame_compare.config.schema import ConfigSchema
from frame_compare.config.schema_enums import OverlayMode
from frame_compare.config.schema_models import SourcesConfig
from frame_compare.orchestration.source_selection import resolve_source_selection
from frame_compare.render.batch.expansion import (
    expand_batch_render_requests,
    validate_batch_requests,
)
from frame_compare.render.types import PreparedRenderSource, ScreenshotBatchRequest
from frame_compare.utils.media_facts import (
    ActivePictureFacts,
    PresentationState,
    SourceSignalFacts,
)


def _request(label: str = "ref") -> ScreenshotBatchRequest:
    return ScreenshotBatchRequest(
        clip_path=Path(f"{label}.mkv"),
        label=label,
        source_frames=[10, 20],
        comparison_frames=[12, 22],
        selection_labels=["Dark", "Bright"],
        size_bytes=100,
        source_resolution=(1920, 1080),
        source_total_frames=100,
        signal=SourceSignalFacts(is_hdr=False),
        active_picture=ActivePictureFacts(0, 0, 1920, 1080, "full_frame", True),
    )


def _prepared(*, state: PresentationState = PresentationState.SDR) -> PreparedRenderSource:
    original = MagicMock(name="original")
    return PreparedRenderSource(
        diagnostic_source=original,
        prepared_clip=MagicMock(name="prepared"),
        source_dimensions=(1920, 1080),
        source_total_frames=101,
        source_is_hdr=state != PresentationState.SDR,
        presentation_state=state,
        tonemap_settings=None,
    )


def test_validate_batch_requests_rejects_duplicate_labels() -> None:
    with pytest.raises(ValueError, match="Duplicate label"):
        validate_batch_requests([_request(), _request()])


@pytest.mark.parametrize("dimensions", [(0, 1080), (1920, 0), (-1, 1080)])
def test_validate_batch_requests_rejects_non_positive_source_dimensions(
    dimensions: tuple[int, int],
) -> None:
    with pytest.raises(ValueError, match="requires positive source dimensions"):
        validate_batch_requests([replace(_request(), source_resolution=dimensions)])


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expansion_preserves_source_mapping_and_prepared_source(
    mock_prepare: MagicMock,
    tmp_path: Path,
) -> None:
    prepared = _prepared()
    mock_prepare.return_value = prepared
    batch = _request()
    requests, ranges, facts = expand_batch_render_requests(
        [batch],
        output_dir=tmp_path / "out",
        config=ConfigSchema(),
        overlay_mode=OverlayMode.NONE,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )

    assert [request.frame_number for request in requests] == [10, 20]
    assert [request.output_path.name for request in requests] == [
        "12 - ref.png",
        "22 - ref.png",
    ]
    assert all(request.diagnostic_source is prepared.diagnostic_source for request in requests)
    assert all(request.clip is prepared.prepared_clip for request in requests)
    assert all(request.progress_label is None for request in requests)
    assert mock_prepare.call_args.kwargs["source_is_hdr"] is False
    assert ranges == {"ref": range(0, 2)}
    assert facts["ref"].source_total_frames == 101
    assert facts["ref"].presentation_state is PresentationState.SDR


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expansion_copies_progress_label_without_changing_overlay_label(
    mock_prepare: MagicMock,
    tmp_path: Path,
) -> None:
    mock_prepare.return_value = _prepared()
    batch = replace(_request(), progress_label="Reference | ATV WEB-DL")

    requests, _, _ = expand_batch_render_requests(
        [batch],
        output_dir=tmp_path / "out",
        config=ConfigSchema(),
        overlay_mode=OverlayMode.STANDARD,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )

    assert requests[0].progress_label == "Reference | ATV WEB-DL"
    assert requests[0].overlay is not None
    assert requests[0].overlay.label == "ref"


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expansion_uses_actual_preparation_state_and_overlay_facts(
    mock_prepare: MagicMock,
    tmp_path: Path,
) -> None:
    prepared = _prepared(state=PresentationState.HDR_TONEMAP_OFF)
    mock_prepare.return_value = prepared
    batch = _request()
    batch = replace(batch, signal=SourceSignalFacts(is_hdr=True))
    requests, _, facts = expand_batch_render_requests(
        [batch],
        output_dir=tmp_path / "out",
        config=ConfigSchema(),
        overlay_mode=OverlayMode.DIAGNOSTIC,
        renderer="vapoursynth",
        ffmpeg_runner=MagicMock(),
    )
    assert facts["ref"].presentation_state is PresentationState.HDR_TONEMAP_OFF
    assert requests[0].overlay is not None
    assert requests[0].overlay.presentation_state is PresentationState.HDR_TONEMAP_OFF
    assert requests[0].overlay.source_frame == 10
    assert requests[0].overlay.comparison_frame == 12


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_expansion_rejects_out_of_range_source_frame(
    mock_prepare: MagicMock, tmp_path: Path
) -> None:
    mock_prepare.return_value = _prepared()
    request = replace(
        _request(), source_frames=[101], comparison_frames=[101], selection_labels=[None]
    )
    with pytest.raises(ValueError, match="outside valid range"):
        expand_batch_render_requests(
            [request],
            output_dir=tmp_path / "out",
            config=ConfigSchema(),
            overlay_mode=OverlayMode.NONE,
            renderer="vapoursynth",
            ffmpeg_runner=MagicMock(),
        )


@pytest.mark.parametrize("labels", [("Bad?Name", "Bad:Name"), ("A" * 300 + "?", "A" * 300 + ":")])
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_final_output_collisions_refused_before_preparation(
    mock_prepare: MagicMock, labels: tuple[str, str], tmp_path: Path
) -> None:
    from frame_compare.render.errors import ScreenshotOutputCollisionError

    batches = [replace(_request(label), filename_label=label) for label in labels]
    with (
        pytest.raises(ScreenshotOutputCollisionError) as caught,
    ):
        expand_batch_render_requests(
            batches,
            output_dir=tmp_path,
            config=ConfigSchema(),
            overlay_mode=OverlayMode.NONE,
            renderer="vapoursynth",
            ffmpeg_runner=MagicMock(),
        )
    assert caught.value.code == "FC-4021"
    assert caught.value.name == "SCREENSHOT_OUTPUT_COLLISION"
    assert caught.value.context.hint is not None
    if len(labels[0]) > 255:
        assert "~" in caught.value.context.message
    mock_prepare.assert_not_called()


@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_final_duplicate_frame_refused_before_preparation(
    mock_prepare: MagicMock, tmp_path: Path
) -> None:
    from frame_compare.render.errors import ScreenshotOutputCollisionError

    batch = replace(_request(), comparison_frames=[12, 12])
    with pytest.raises(ScreenshotOutputCollisionError):
        expand_batch_render_requests(
            [batch],
            output_dir=tmp_path,
            config=ConfigSchema(),
            overlay_mode=OverlayMode.NONE,
            renderer="vapoursynth",
            ffmpeg_runner=MagicMock(),
        )
    mock_prepare.assert_not_called()


@pytest.mark.parametrize(
    "stems", [("Movie", "movie"), ("Ç", "ç"), ("é", "e\u0301"), ("Straße", "Strasse"), ("Ç", "c")]
)
@patch("frame_compare.render.batch.expansion.prepare_clip_for_render")
def test_source_stem_aliases_follow_output_filesystem(
    mock_prepare: MagicMock, tmp_path: Path, stems: tuple[str, str]
) -> None:
    from frame_compare.render.batch.orchestrator import render_screenshots_from_batch_detailed
    from frame_compare.render.errors import ScreenshotOutputCollisionError
    from frame_compare.render.types import BatchRenderOptions

    # Different input extensions coexist even on a case-insensitive input volume.
    sources = [tmp_path / f"{stems[0]}.mkv", tmp_path / f"{stems[1]}.mp4"]
    for source in sources:
        source.touch()
    selection = resolve_source_selection(
        input_dir=tmp_path, discovered_paths=sources, config=SourcesConfig()
    )
    assert selection.ordered_paths == sources
    batches = [
        replace(_request(source.stem), clip_path=source, filename_label=source.stem)
        for source in selection.ordered_paths
    ]
    mock_prepare.return_value = _prepared()
    output_dir = tmp_path / "screenshots"
    output_dir.mkdir()
    first = output_dir / f"12 - {stems[0]}.png"
    first.touch()
    alias = output_dir / f"12 - {stems[1]}.png"
    filesystem_distinct = not (alias.exists() and alias.samefile(first))
    first.unlink()
    with (
        patch(
            "frame_compare.render.batch.orchestrator.render_batch_detailed", return_value=[]
        ) as render,
    ):
        if filesystem_distinct:
            requests, _, _ = expand_batch_render_requests(
                batches,
                output_dir=tmp_path / "screenshots",
                config=ConfigSchema(),
                overlay_mode=OverlayMode.NONE,
                renderer="vapoursynth",
                ffmpeg_runner=MagicMock(),
            )
            assert [request.output_path.name for request in requests] == [
                f"{frame} - {stem}.png" for stem in stems for frame in (12, 22)
            ]
            assert mock_prepare.call_count == 2
        else:
            with pytest.raises(ScreenshotOutputCollisionError):
                render_screenshots_from_batch_detailed(
                    batches,
                    tmp_path / "screenshots",
                    ConfigSchema(),
                    BatchRenderOptions(renderer="vapoursynth"),
                )
            mock_prepare.assert_not_called()
            render.assert_not_called()
