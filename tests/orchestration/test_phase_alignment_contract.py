from dataclasses import replace
from pathlib import Path

import pytest

from frame_compare.orchestration.phase_alignment import _alignment_clip_request
from tests.orchestration.phase_task_helpers import _clip


def test_alignment_request_uses_untrimmed_probe_frame_count(tmp_path: Path) -> None:
    clip = _clip(tmp_path / "source.mkv", label="Source", num_frames=321).with_trim(
        trim_start_frames=20,
        trim_end_frame_inclusive=99,
    )

    request = _alignment_clip_request(clip, selected_audio_stream=None)

    assert request.source_frame_count == 321


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_alignment_request_requires_positive_integer_source_frame_count(
    tmp_path: Path, value: int | float | bool
) -> None:
    clip = _clip(tmp_path / "source.mkv", label="Source")
    request = _alignment_clip_request(clip, selected_audio_stream=None)

    with pytest.raises(ValueError, match="positive integer"):
        replace(request, source_frame_count=value)
