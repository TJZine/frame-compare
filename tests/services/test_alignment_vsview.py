"""Direct tests for alignment VSView launch policy."""

import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import frame_compare.services.alignment_vsview as alignment_vsview
import frame_compare.vsview.output as vsview_output
from frame_compare.services.alignment_manual_overrides import load_manual_overrides
from frame_compare.services.alignment_vsview import maybe_launch_alignment_vsview
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig
from frame_compare.vsview.adapter import (
    VSViewAvailability,
    VSViewAvailabilityStatus,
    VSViewSessionRequest,
)
from frame_compare.vsview.errors import VSViewError


def _call_maybe_launch(
    *,
    tmp_path: Path,
    config: AlignmentConfig,
    progress: object | None = None,
    verbose: bool = False,
) -> None:
    maybe_launch_alignment_vsview(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        cache_dir=tmp_path,
        config=config,
        progress=progress,
        verbose=verbose,
    )


def _set_tty(monkeypatch: pytest.MonkeyPatch, is_tty: bool) -> None:
    monkeypatch.setattr(alignment_vsview.sys.stdin, "isatty", lambda: is_tty)
    monkeypatch.setattr(alignment_vsview.sys.stdout, "isatty", lambda: is_tty)
    monkeypatch.setattr(alignment_vsview.sys.stderr, "isatty", lambda: is_tty)


def _set_tty_streams(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdin: bool,
    stdout: bool,
    stderr: bool,
) -> None:
    monkeypatch.setattr(alignment_vsview.sys.stdin, "isatty", lambda: stdin)
    monkeypatch.setattr(alignment_vsview.sys.stdout, "isatty", lambda: stdout)
    monkeypatch.setattr(alignment_vsview.sys.stderr, "isatty", lambda: stderr)


def _set_broken_tty_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_closed_stream() -> bool:
        raise ValueError("closed stream")

    monkeypatch.setattr(alignment_vsview.sys.stdin, "isatty", _raise_closed_stream)
    monkeypatch.setattr(alignment_vsview.sys.stdout, "isatty", _raise_closed_stream)
    monkeypatch.setattr(alignment_vsview.sys.stderr, "isatty", _raise_closed_stream)


def _availability(status: VSViewAvailabilityStatus) -> VSViewAvailability:
    if status == VSViewAvailabilityStatus.PROBE_FAILED:
        return VSViewAvailability(
            status=status,
            message="probe failed",
            hint="check install",
            error_details={"exception_type": "RuntimeError", "exception": "raw detail"},
        )
    return VSViewAvailability(
        status=status,
        message=status.value,
        hint="install VSView",
    )


def test_disabled_config_returns_without_availability_or_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(side_effect=AssertionError("availability should not be checked")),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=AssertionError("VSView should not launch")),
    )

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vsview=False))


def test_force_interactive_unavailable_raises_without_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(
            return_value=_availability(VSViewAvailabilityStatus.MISSING_EXEC_AND_MODULE),
        ),
    )
    mock_launch = MagicMock()
    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", mock_launch)

    with pytest.raises(AudioAlignmentError, match="VSView is not available"):
        _call_maybe_launch(
            tmp_path=tmp_path,
            config=AlignmentConfig(use_vsview=True, force_interactive=True),
        )

    mock_launch.assert_not_called()


@pytest.mark.parametrize(
    ("status", "expected_warning"),
    [
        (VSViewAvailabilityStatus.MISSING_EXEC_AND_MODULE, "vsview_unavailable"),
        (VSViewAvailabilityStatus.PROBE_FAILED, "vsview_availability_probe_failed"),
    ],
)
def test_optional_unavailable_generates_script_with_one_human_warning(
    status: VSViewAvailabilityStatus,
    expected_warning: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(status)),
    )
    mock_launch = MagicMock(return_value=tmp_path / "vsview.py")
    mock_warning = MagicMock()
    mock_human_warning = MagicMock()
    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", mock_launch)
    monkeypatch.setattr(alignment_vsview.log, "warning", mock_warning)
    monkeypatch.setattr(alignment_vsview, "print_vsview_unavailable", mock_human_warning)

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vsview=True))

    mock_launch.assert_called_once()
    _, launch_kwargs = mock_launch.call_args
    assert isinstance(launch_kwargs["request"], VSViewSessionRequest)
    assert launch_kwargs["config"].enabled is False
    mock_warning.assert_not_called()
    expected_reason = (
        "VSView availability check failed."
        if expected_warning == "vsview_availability_probe_failed"
        else "VSView is not installed."
    )
    mock_human_warning.assert_called_once_with(reason=expected_reason, no_color=False)


def test_available_without_tty_generates_script_disabled_and_logs_no_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty_streams(monkeypatch, stdin=False, stdout=True, stderr=False)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(VSViewAvailabilityStatus.AVAILABLE)),
    )
    mock_launch = MagicMock(return_value=tmp_path / "vsview.py")
    mock_warning = MagicMock()
    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", mock_launch)
    monkeypatch.setattr(alignment_vsview.log, "warning", mock_warning)

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vsview=True))

    mock_launch.assert_called_once()
    _, launch_kwargs = mock_launch.call_args
    assert isinstance(launch_kwargs["request"], VSViewSessionRequest)
    assert launch_kwargs["config"].enabled is False
    mock_warning.assert_called_once()
    warning_args, warning_kwargs = mock_warning.call_args
    assert warning_args == ("vsview_no_tty",)
    assert warning_kwargs["stdin_tty"] is False
    assert warning_kwargs["stdout_tty"] is True
    assert warning_kwargs["stderr_tty"] is False


def test_available_with_broken_tty_probe_treats_streams_as_non_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_broken_tty_streams(monkeypatch)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(VSViewAvailabilityStatus.AVAILABLE)),
    )
    mock_launch = MagicMock(return_value=tmp_path / "vsview.py")
    mock_warning = MagicMock()
    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", mock_launch)
    monkeypatch.setattr(alignment_vsview.log, "warning", mock_warning)

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vsview=True))

    mock_launch.assert_called_once()
    _, launch_kwargs = mock_launch.call_args
    assert launch_kwargs["config"].enabled is False
    mock_warning.assert_called_once()
    warning_args, warning_kwargs = mock_warning.call_args
    assert warning_args == ("vsview_no_tty",)
    assert warning_kwargs["stdin_tty"] is False
    assert warning_kwargs["stdout_tty"] is False
    assert warning_kwargs["stderr_tty"] is False


def test_forced_available_without_tty_raises_without_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty_streams(monkeypatch, stdin=False, stdout=True, stderr=False)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(VSViewAvailabilityStatus.AVAILABLE)),
    )
    mock_launch = MagicMock()
    monkeypatch.setattr(alignment_vsview, "launch_alignment_verification_session", mock_launch)

    with pytest.raises(AudioAlignmentError, match="no interactive terminal"):
        _call_maybe_launch(
            tmp_path=tmp_path,
            config=AlignmentConfig(use_vsview=True, force_interactive=True),
        )

    mock_launch.assert_not_called()


def test_optional_launch_error_has_one_human_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(VSViewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=VSViewError("launch exited with code 7")),
    )
    mock_warning = MagicMock()
    mock_human_warning = MagicMock()
    monkeypatch.setattr(alignment_vsview.log, "warning", mock_warning)
    monkeypatch.setattr(alignment_vsview, "print_vsview_unavailable", mock_human_warning)

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vsview=True))

    mock_warning.assert_not_called()
    mock_human_warning.assert_called_once_with(
        reason="launch exited with code 7",
        no_color=False,
    )


def test_verbose_optional_startup_failure_adds_bounded_forensic_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(VSViewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(
            side_effect=VSViewError(
                "Missing optional dependency: vsview_cli",
                missing_module="vsview_cli",
                command=("python", "-m", "vsview", "session.py"),
                returncode=1,
                startup_stderr="captured traceback tail",
            )
        ),
    )
    details = MagicMock()
    monkeypatch.setattr(alignment_vsview, "print_vsview_failure_details", details)

    _call_maybe_launch(
        tmp_path=tmp_path,
        config=AlignmentConfig(use_vsview=True),
        verbose=True,
    )

    details.assert_called_once_with(
        command=("python", "-m", "vsview", "session.py"),
        reason="Missing optional dependency: vsview_cli",
        returncode=1,
        startup_stderr="captured traceback tail",
        no_color=False,
    )


def test_forced_launch_error_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(VSViewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=VSViewError("launch exited with code 7")),
    )

    with pytest.raises(VSViewError, match="launch exited with code 7"):
        _call_maybe_launch(
            tmp_path=tmp_path,
            config=AlignmentConfig(use_vsview=False, force_interactive=True),
        )


@pytest.mark.parametrize("no_color", [False, True])
def test_prompt_for_confirmed_offsets_writes_to_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    no_color: bool,
) -> None:
    monkeypatch.setattr(alignment_vsview.sys, "stdin", io.StringIO("120 108\n"))

    confirmed = alignment_vsview._prompt_for_confirmed_offsets(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        no_color=no_color,
    )

    captured = capsys.readouterr()
    normalized = " ".join(captured.err.split())
    assert confirmed == {"ref:comp": 12}
    assert captured.out == ""
    lines = captured.err.splitlines()
    wait_line = next(line for line in lines if "[WAIT] VSView Confirmation" in line)
    assert wait_line == "  [WAIT] VSView Confirmation"
    assert "ref" in captured.err
    assert "Comparison 1 | comp" in captured.err
    for key in (
        "reference",
        "domain",
        "task",
        "enter",
        "result",
        "skip",
        "comparison",
        "audio hint",
        "match frames",
    ):
        matching_line = next(line for line in lines if line.lstrip().startswith(key))
        assert matching_line.startswith(f"    {key}")
    assert "    domain       Untrimmed source-frame indices" in captured.err
    assert "Find the same visible moment in both VSView outputs" in normalized
    assert "reference_frame comparison_frame" in normalized
    assert "reference first; e.g. 120 108" in normalized
    assert "Frame Compare calculates the offset and required trim" in normalized
    assert "'skip' or 's' leaves the audio result unchanged (if any)" in normalized
    assert "+4f | Reference 4 <-> Comparison 0 | trim 4 from reference" in normalized
    assert "    match frames reference comparison >" in captured.err
    assert captured.err.endswith("\n")
    assert "\x1b[" not in captured.err
    assert "[bold cyan]" not in captured.err


def test_prompt_for_confirmed_offsets_does_not_show_numeric_hint_when_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(alignment_vsview.sys, "stdin", io.StringIO("120 108\n"))

    confirmed = alignment_vsview._prompt_for_confirmed_offsets(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": None},
        no_color=True,
    )

    captured = capsys.readouterr()
    assert confirmed == {"ref:comp": 12}
    assert "comp" in captured.err
    assert "+0" not in captured.err
    assert "audio hint   no trusted audio hint" in captured.err
    assert "match frames reference comparison >" in captured.err


@pytest.mark.parametrize(
    ("suggested_offset", "expected_fragments"),
    [
        (-147, ("-147f", "Reference 0 <->", "Comparison 147", "trim 147 from comparison")),
        (0, ("+0f", "Reference 0 <-> Comparison 0", "no trim")),
    ],
)
def test_vsview_prompt_explains_audio_hint_direction(
    suggested_offset: int,
    expected_fragments: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    vsview_output.write_vsview_prompt(
        label="Comparison 1 | Encode",
        suggested_offset=suggested_offset,
        no_color=True,
    )

    output = " ".join(capsys.readouterr().err.split())
    assert all(fragment in output for fragment in expected_fragments)


def test_prompt_for_confirmed_offsets_uses_prepared_names_but_keeps_stem_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(alignment_vsview.sys, "stdin", io.StringIO("120 108\n"))

    confirmed = alignment_vsview._prompt_for_confirmed_offsets(
        reference=tmp_path / "raw-reference-stem.mkv",
        comparisons=[tmp_path / "raw-comparison-stem.mkv"],
        offsets_by_key={"raw-reference-stem:raw-comparison-stem": 4},
        presentation_names_by_stem={
            "raw-reference-stem": "PMTP WEB-DL | DV HDR10+ | Kitsune",
            "raw-comparison-stem": "ATV WEB-DL | DV HDR10+ | Kitsune",
        },
        no_color=True,
    )

    output = capsys.readouterr().err
    assert confirmed == {"raw-reference-stem:raw-comparison-stem": 12}
    assert "PMTP WEB-DL | DV HDR10+ | Kitsune" in output
    assert "Comparison 1 | ATV WEB-DL | DV HDR10+ | Kitsune" in output
    assert "raw-reference-stem" not in output
    assert "raw-comparison-stem" not in output


def test_wait_status_text_styles_only_marker(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("TERM", "xterm-256color")

    vsview_output.print_vsview_confirmation_header(
        reference_name="Reference",
        no_color=False,
    )

    output = capsys.readouterr().err
    assert "\x1b[35m[WAIT]\x1b[0m VSView Confirmation" in output
    assert "\x1b[35m[WAIT] VSView Confirmation\x1b[0m" not in output


def test_prompt_for_confirmed_offsets_accepts_zero_source_frame_offset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_vsview.sys, "stdin", io.StringIO("42, 42\n"))

    confirmed = alignment_vsview._prompt_for_confirmed_offsets(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
    )

    assert confirmed == {"ref:comp": 0}


@pytest.mark.parametrize("user_input", ["skip\n", "s\n"])
def test_prompt_for_confirmed_offsets_skip_omits_comparison_key(
    user_input: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_vsview.sys, "stdin", io.StringIO(user_input))

    confirmed = alignment_vsview._prompt_for_confirmed_offsets(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
    )

    assert confirmed == {}


def test_prompt_for_confirmed_offsets_eof_returns_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_vsview.sys, "stdin", io.StringIO(""))

    confirmed = alignment_vsview._prompt_for_confirmed_offsets(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
    )

    assert confirmed is None


def test_prompt_for_confirmed_offsets_confirm_skip_confirm_preserves_confirmed_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        alignment_vsview.sys,
        "stdin",
        io.StringIO("120 108\nskip\n210 216\n"),
    )
    comparisons = [
        tmp_path / "zeta.mkv",
        tmp_path / "alpha.mkv",
        tmp_path / "mid.mkv",
    ]

    confirmed = alignment_vsview._prompt_for_confirmed_offsets(
        reference=tmp_path / "ref.mkv",
        comparisons=comparisons,
        offsets_by_key={
            "ref:zeta": 4,
            "ref:alpha": None,
            "ref:mid": -2,
        },
        no_color=True,
    )

    captured = capsys.readouterr()
    assert confirmed == {"ref:zeta": 12, "ref:mid": -6}
    assert "ref:alpha" not in confirmed
    assert captured.err.index("zeta") < captured.err.index("alpha") < captured.err.index("mid")
    assert "+4" in captured.err
    assert "-2" in captured.err


def test_prompt_for_confirmed_offsets_reprompts_after_blank_and_malformed_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        alignment_vsview.sys,
        "stdin",
        io.StringIO("\n12\n12.5 9\ntrue 9\n-1 9\n120 108\n"),
    )

    confirmed = alignment_vsview._prompt_for_confirmed_offsets(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        no_color=True,
    )

    captured = capsys.readouterr()
    assert confirmed == {"ref:comp": 12}
    assert confirmed != {"ref:comp": 4}
    assert "source frames" in captured.err
    assert "non-negative" in captured.err
    assert captured.err.count("    Hint") == 5


def test_vsview_input_hint_has_wait_content_indent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    vsview_output.print_vsview_input_hint("Retry the frame pair.", no_color=True)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "    Hint Retry the frame pair.\n"


def test_maybe_launch_blank_then_valid_source_frames_saves_only_computed_offset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_vsview.sys, "stdin", io.StringIO("\n120 108\n"))
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(VSViewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(return_value=tmp_path / "vsview.py"),
    )

    confirmed = maybe_launch_alignment_vsview(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        cache_dir=tmp_path,
        config=AlignmentConfig(use_vsview=True),
        progress=None,
    )

    assert confirmed == {"ref:comp": 12}
    manual_overrides = load_manual_overrides(tmp_path)
    assert manual_overrides["ref:comp"].frame_offset == 12


@pytest.mark.parametrize(
    ("user_input", "expected_confirmed"),
    [
        ("skip\n", {}),
        ("", None),
    ],
)
def test_maybe_launch_skip_or_eof_writes_no_override(
    user_input: str,
    expected_confirmed: dict[str, int] | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_vsview.sys, "stdin", io.StringIO(user_input))
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(VSViewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(return_value=tmp_path / "vsview.py"),
    )

    confirmed = maybe_launch_alignment_vsview(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        cache_dir=tmp_path,
        config=AlignmentConfig(use_vsview=True),
        progress=None,
    )

    assert confirmed == expected_confirmed
    assert load_manual_overrides(tmp_path) == {}


def test_maybe_launch_confirm_skip_confirm_saves_only_confirmed_offsets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_vsview.sys,
        "stdin",
        io.StringIO("120 108\nskip\n210 216\n"),
    )
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(VSViewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(return_value=tmp_path / "vsview.py"),
    )

    confirmed = maybe_launch_alignment_vsview(
        reference=tmp_path / "ref.mkv",
        comparisons=[
            tmp_path / "zeta.mkv",
            tmp_path / "alpha.mkv",
            tmp_path / "mid.mkv",
        ],
        offsets_by_key={
            "ref:zeta": 4,
            "ref:alpha": None,
            "ref:mid": -2,
        },
        cache_dir=tmp_path,
        config=AlignmentConfig(use_vsview=True),
        progress=None,
    )

    assert confirmed == {"ref:zeta": 12, "ref:mid": -6}
    manual_overrides = load_manual_overrides(tmp_path)
    assert set(manual_overrides) == {"ref:zeta", "ref:mid"}
    assert manual_overrides["ref:zeta"].frame_offset == 12
    assert manual_overrides["ref:mid"].frame_offset == -6


def test_available_with_tty_suspends_progress_during_launch_and_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(VSViewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        MagicMock(return_value=tmp_path / "vsview.py"),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "_prompt_for_confirmed_offsets",
        MagicMock(return_value={"ref:comp": 4}),
    )
    monkeypatch.setattr(
        alignment_vsview,
        "_save_confirmed_offsets",
        MagicMock(),
    )
    progress = MagicMock()

    _call_maybe_launch(
        tmp_path=tmp_path,
        config=AlignmentConfig(use_vsview=True),
        progress=progress,
    )

    progress.set_description.assert_called_once_with("ALIGN | Interactive verification")
    progress.suspend.assert_called_once_with()
    progress.resume.assert_called_once_with()


def test_maybe_launch_propagates_no_color_to_launch_and_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vsview,
        "check_vsview_availability",
        MagicMock(return_value=_availability(VSViewAvailabilityStatus.AVAILABLE)),
    )
    mock_launch = MagicMock(return_value=tmp_path / "vsview.py")
    mock_prompt = MagicMock(return_value=None)
    monkeypatch.setattr(
        alignment_vsview,
        "launch_alignment_verification_session",
        mock_launch,
    )
    monkeypatch.setattr(
        alignment_vsview,
        "_prompt_for_confirmed_offsets",
        mock_prompt,
    )

    maybe_launch_alignment_vsview(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        cache_dir=tmp_path,
        config=AlignmentConfig(use_vsview=True, no_color=True),
        progress=None,
        frame_props_by_stem={
            "ref": {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1},
            "comp": {"_Matrix": 1, "_Transfer": 16, "_Primaries": 9},
        },
    )

    _, launch_kwargs = mock_launch.call_args
    assert launch_kwargs["config"].no_color is True
    assert launch_kwargs["request"].frame_props_by_stem == {
        "ref": {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1},
        "comp": {"_Matrix": 1, "_Transfer": 16, "_Primaries": 9},
    }
    _, prompt_kwargs = mock_prompt.call_args
    assert prompt_kwargs["no_color"] is True
