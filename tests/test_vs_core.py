import types

from src import vs_core


def test_pick_verify_frame_warns_when_no_frames():
    clip = types.SimpleNamespace(num_frames=0)
    cfg = types.SimpleNamespace(
        verify_frame=None,
        verify_auto=True,
        verify_start_seconds=10.0,
        verify_step_seconds=10.0,
        verify_max_seconds=90.0,
        verify_luma_threshold=0.10,
    )
    warnings: list[str] = []

    frame_idx, auto_selected = vs_core._pick_verify_frame(
        clip,
        cfg,
        fps=24.0,
        file_name="clip.mkv",
        warning_sink=warnings,
    )

    assert frame_idx == 0
    assert auto_selected is False
    assert warnings == ["[VERIFY] clip.mkv has no frames; using frame 0"]
