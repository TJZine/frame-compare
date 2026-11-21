from __future__ import annotations

import pytest

from frame_compare.utils.terminal_sections import Section, run_output_spacing
from frame_compare.utils.terminal_theme import human_console
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
    assert captured.err == ""

    with run_output_spacing():
        Section("Review").print(human_console(stderr=True, no_color=True))
        print_vsview_review_result(accepted=False, message="Invalid [red] result", no_color=True)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.endswith(
        "╰─\n\n! VSView review   Invalid [red] result; current offsets were kept.\n"
    )
    assert "╰─\n\n\n!" not in captured.err
