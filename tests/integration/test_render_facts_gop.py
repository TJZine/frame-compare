"""Runtime proof for exact-frame picture facts on a tiny deterministic GOP."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from frame_compare.render.encoders import render_frame_detailed
from frame_compare.render.types import EncoderSettings, RenderRequest
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
    for index in selected:
        vs_result = render_frame_detailed(
            RenderRequest(
                clip=source_info.clip,
                diagnostic_source=source_info.clip,
                frame_number=index,
                output_path=tmp_path / f"vs-{index}.png",
                overlay=None,
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
                overlay=None,
                encoder_settings=EncoderSettings(),
            ),
            renderer="ffmpeg",
        )
        assert vs_result.facts.picture_type == expected[index]
        assert ffmpeg_result.facts.picture_type == expected[index]
        assert vs_result.path.exists()
        assert ffmpeg_result.path.exists()
