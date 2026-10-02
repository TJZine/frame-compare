"""Factories for tests that exercise the typed alignment service boundary."""

from pathlib import Path

from frame_compare.services.types import AlignmentConfig
from frame_compare.utils.types import (
    AlignmentCacheSettings,
    AlignmentClipIdentity,
    AlignmentClipRequest,
    AlignmentRequest,
)
from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewSession,
    alignment_review_session_from_script,
)


def alignment_request(
    *,
    reference: Path,
    comparisons: list[Path],
    config: AlignmentConfig,
    generated_dir: Path,
    shared_alignment_cache_dir: Path | None = None,
    fps_num: int = 24,
    fps_den: int = 1,
) -> AlignmentRequest:
    def clip(path: Path, *, selected_audio_stream: int | None) -> AlignmentClipRequest:
        stat = path.stat()
        return AlignmentClipRequest(
            path=path,
            label=path.stem,
            identity=AlignmentClipIdentity(
                path=path,
                size_bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            ),
            trim_start_frames=0,
            trim_end_frame_inclusive=None,
            effective_fps_num=fps_num,
            effective_fps_den=fps_den,
            source_fps_num=fps_num,
            source_fps_den=fps_den,
            source_frame_count=100,
            selected_audio_stream=selected_audio_stream,
        )

    return AlignmentRequest(
        reference=clip(reference, selected_audio_stream=config.reference_stream),
        selected_reference_relationship="auto",
        comparisons=[
            clip(
                comparison,
                selected_audio_stream=config.comparison_streams.get(comparison.stem),
            )
            for comparison in comparisons
        ],
        previous_offsets=config.previous_offsets,
        generated_dir=generated_dir,
        shared_alignment_cache_dir=(
            shared_alignment_cache_dir or generated_dir / "shared-alignment"
        ),
        settings=AlignmentCacheSettings(
            max_offset_seconds=config.max_offset_seconds,
            channel_strategy=config.channel_strategy,
        ),
    )


VSVIEW_SESSION_ID = "12345678123456781234567812345678"


def vsview_session(tmp_path: Path) -> AlignmentReviewSession:
    """Build a generated-session fixture for native VSView review tests."""
    sessions_dir = tmp_path / "vsview_sessions"
    sessions_dir.mkdir(exist_ok=True)
    script = sessions_dir / f"vsview_ref_20260831T000000Z_{VSVIEW_SESSION_ID}.py"
    script.write_text("# generated\n", encoding="utf-8")
    return alignment_review_session_from_script(script, require_result_absent=True)
