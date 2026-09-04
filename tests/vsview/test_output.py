from __future__ import annotations

import pytest

from frame_compare.vsview.output import print_vsview_review_result


def test_review_result_uses_standard_status_and_detail_indentation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    print_vsview_review_result(
        accepted=True,
        message="Accepted 2 confirmed pair(s).",
        no_color=True,
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "\n"
        "  [OK] VSView alignment review\n"
        "       Accepted 2 confirmed pair(s).\n"
    )
