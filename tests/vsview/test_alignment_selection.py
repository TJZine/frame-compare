import pytest

from frame_compare.vsview.alignment_selection import OpeningHint


@pytest.mark.parametrize(
    "n,own,target,count,expected,status,weak",
    [
        (96, 504, 0, 20000, 600, "available", False),
        (96, 504, -12, 20000, 612, "available", True),
        (612, -12, 504, 20000, 96, "available", False),
        (0, 0, 0, 1, 0, "available", False),
        (7, -7, 0, 1, 0, "available", False),
        (7, -8, 0, 100, None, "outside source range", False),
        (7, 3, 0, 10, None, "outside source range", False),
        (7, None, 0, 100, None, "unavailable", False),
        (7, 0, None, 100, None, "unavailable", False),
    ],
)
def test_shared_projection(n, own, target, count, expected, status, weak):
    from frame_compare.vsview.alignment_selection import project_frame

    result = project_frame(n, OpeningHint(own, weak), OpeningHint(target), count)
    assert (result.frame, result.status) == (expected, status)
    assert result.provisional == (weak and expected is not None)
