from unittest.mock import MagicMock

from src.frame_compare import alignment_runner


def test_reuse_vspreview_manual_offsets_normalizes_negative_trims():
    # Setup
    plan1 = MagicMock()
    plan1.path.name = "clip1.mkv"
    plan1.trim_start = 0
    plan1.source_num_frames = 100
    plan1.has_trim_start_override = False

    plan2 = MagicMock()
    plan2.path.name = "clip2.mkv"
    plan2.trim_start = 0
    plan2.source_num_frames = 100
    plan2.has_trim_start_override = False

    plans = [plan1, plan2]

    # Simulate VSPreview offsets: clip2 has -5 (padding)
    vspreview_reuse = {
        "clip1.mkv": 0,
        "clip2.mkv": -5
    }

    display_data = MagicMock()
    display_data.manual_trim_lines = []

    # Execute
    alignment_runner._apply_manual_offsets_logic(
        plans, vspreview_reuse, display_data, {p.path: p.path.name for p in plans}
    )

    # Assert
    # clip2 had -5. Min is -5. Shift is +5.
    # clip1: 0 + 5 = 5
    # clip2: -5 + 5 = 0

    assert plan1.trim_start == 5
    assert plan2.trim_start == 0
    assert plan1.has_trim_start_override is True
    # plan2 trim didn't change (0 -> 0), so override flag remains False
    assert plan2.has_trim_start_override is False

    # Check display lines
    assert len(display_data.manual_trim_lines) > 0
    print(display_data.manual_trim_lines)

def test_reuse_vspreview_manual_offsets_no_negative_trims():
    # Setup
    plan1 = MagicMock()
    plan1.path.name = "clip1.mkv"
    plan1.trim_start = 10

    plan2 = MagicMock()
    plan2.path.name = "clip2.mkv"
    plan2.trim_start = 20

    plans = [plan1, plan2]

    # Simulate VSPreview offsets: clip2 has +5
    vspreview_reuse = {
        "clip2.mkv": 5
    }

    display_data = MagicMock()
    display_data.manual_trim_lines = []

    # Execute
    alignment_runner._apply_manual_offsets_logic(
        plans, vspreview_reuse, display_data, {p.path: p.path.name for p in plans}
    )

    # Assert
    # clip1: baseline 10. delta 0 (not in reuse). proposed 10.
    # clip2: baseline 20. delta 5. proposed 25.
    # min 10. shift 0.

    assert plan1.trim_start == 10
    assert plan2.trim_start == 25
