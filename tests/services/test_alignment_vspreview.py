"""Direct tests for alignment VSPreview launch policy."""

import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import frame_compare.services.alignment_vspreview as alignment_vspreview
from frame_compare.services.alignment_vspreview import maybe_launch_alignment_vspreview
from frame_compare.services.errors import AudioAlignmentError
from frame_compare.services.types import AlignmentConfig
from frame_compare.vspreview.adapter import (
    VSPreviewAvailability,
    VSPreviewAvailabilityStatus,
    VSPreviewSessionRequest,
)
from frame_compare.vspreview.errors import VSPreviewError
from frame_compare.vspreview.overrides import load_manual_overrides


def _call_maybe_launch(
    *,
    tmp_path: Path,
    config: AlignmentConfig,
    progress: object | None = None,
) -> None:
    maybe_launch_alignment_vspreview(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        cache_dir=tmp_path,
        config=config,
        progress=progress,
    )


def _set_tty(monkeypatch: pytest.MonkeyPatch, is_tty: bool) -> None:
    monkeypatch.setattr(alignment_vspreview.sys.stdin, "isatty", lambda: is_tty)
    monkeypatch.setattr(alignment_vspreview.sys.stdout, "isatty", lambda: is_tty)
    monkeypatch.setattr(alignment_vspreview.sys.stderr, "isatty", lambda: is_tty)


def _set_tty_streams(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdin: bool,
    stdout: bool,
    stderr: bool,
) -> None:
    monkeypatch.setattr(alignment_vspreview.sys.stdin, "isatty", lambda: stdin)
    monkeypatch.setattr(alignment_vspreview.sys.stdout, "isatty", lambda: stdout)
    monkeypatch.setattr(alignment_vspreview.sys.stderr, "isatty", lambda: stderr)


def _set_broken_tty_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_closed_stream() -> bool:
        raise ValueError("closed stream")

    monkeypatch.setattr(alignment_vspreview.sys.stdin, "isatty", _raise_closed_stream)
    monkeypatch.setattr(alignment_vspreview.sys.stdout, "isatty", _raise_closed_stream)
    monkeypatch.setattr(alignment_vspreview.sys.stderr, "isatty", _raise_closed_stream)


def _availability(status: VSPreviewAvailabilityStatus) -> VSPreviewAvailability:
    if status == VSPreviewAvailabilityStatus.PROBE_FAILED:
        return VSPreviewAvailability(
            status=status,
            message="probe failed",
            hint="check install",
            error_details={"exception_type": "RuntimeError", "exception": "raw detail"},
        )
    return VSPreviewAvailability(
        status=status,
        message=status.value,
        hint="install VSPreview",
    )


def test_disabled_config_returns_without_availability_or_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(side_effect=AssertionError("availability should not be checked")),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=AssertionError("VSPreview should not launch")),
    )

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vspreview=False))


def test_force_interactive_unavailable_raises_without_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(
            return_value=_availability(VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE),
        ),
    )
    mock_launch = MagicMock()
    monkeypatch.setattr(alignment_vspreview, "launch_alignment_verification_session", mock_launch)

    with pytest.raises(AudioAlignmentError, match="VSPreview is not available"):
        _call_maybe_launch(
            tmp_path=tmp_path,
            config=AlignmentConfig(use_vspreview=True, force_interactive=True),
        )

    mock_launch.assert_not_called()


@pytest.mark.parametrize(
    ("status", "expected_warning"),
    [
        (VSPreviewAvailabilityStatus.MISSING_EXEC_AND_MODULE, "vspreview_unavailable"),
        (VSPreviewAvailabilityStatus.PROBE_FAILED, "vspreview_availability_probe_failed"),
    ],
)
def test_optional_unavailable_generates_script_without_launch_and_logs_warning(
    status: VSPreviewAvailabilityStatus,
    expected_warning: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(status)),
    )
    mock_launch = MagicMock(return_value=tmp_path / "vspreview.py")
    mock_warning = MagicMock()
    monkeypatch.setattr(alignment_vspreview, "launch_alignment_verification_session", mock_launch)
    monkeypatch.setattr(alignment_vspreview.log, "warning", mock_warning)

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vspreview=True))

    mock_launch.assert_called_once()
    _, launch_kwargs = mock_launch.call_args
    assert isinstance(launch_kwargs["request"], VSPreviewSessionRequest)
    assert launch_kwargs["config"].enabled is False
    warning_args, warning_kwargs = mock_warning.call_args_list[0]
    assert warning_args == (expected_warning,)
    assert warning_kwargs["hint"] in {"install VSPreview", "check install"}
    if status == VSPreviewAvailabilityStatus.PROBE_FAILED:
        assert warning_kwargs["reason"] == "availability probe failed (RuntimeError)"
        assert warning_kwargs["exception_type"] == "RuntimeError"


def test_available_without_tty_generates_script_disabled_and_logs_no_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty_streams(monkeypatch, stdin=False, stdout=True, stderr=False)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    mock_launch = MagicMock(return_value=tmp_path / "vspreview.py")
    mock_warning = MagicMock()
    monkeypatch.setattr(alignment_vspreview, "launch_alignment_verification_session", mock_launch)
    monkeypatch.setattr(alignment_vspreview.log, "warning", mock_warning)

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vspreview=True))

    mock_launch.assert_called_once()
    _, launch_kwargs = mock_launch.call_args
    assert isinstance(launch_kwargs["request"], VSPreviewSessionRequest)
    assert launch_kwargs["config"].enabled is False
    mock_warning.assert_called_once()
    warning_args, warning_kwargs = mock_warning.call_args
    assert warning_args == ("vspreview_no_tty",)
    assert warning_kwargs["stdin_tty"] is False
    assert warning_kwargs["stdout_tty"] is True
    assert warning_kwargs["stderr_tty"] is False


def test_available_with_broken_tty_probe_treats_streams_as_non_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_broken_tty_streams(monkeypatch)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    mock_launch = MagicMock(return_value=tmp_path / "vspreview.py")
    mock_warning = MagicMock()
    monkeypatch.setattr(alignment_vspreview, "launch_alignment_verification_session", mock_launch)
    monkeypatch.setattr(alignment_vspreview.log, "warning", mock_warning)

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vspreview=True))

    mock_launch.assert_called_once()
    _, launch_kwargs = mock_launch.call_args
    assert launch_kwargs["config"].enabled is False
    mock_warning.assert_called_once()
    warning_args, warning_kwargs = mock_warning.call_args
    assert warning_args == ("vspreview_no_tty",)
    assert warning_kwargs["stdin_tty"] is False
    assert warning_kwargs["stdout_tty"] is False
    assert warning_kwargs["stderr_tty"] is False


def test_forced_available_without_tty_raises_without_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty_streams(monkeypatch, stdin=False, stdout=True, stderr=False)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    mock_launch = MagicMock()
    monkeypatch.setattr(alignment_vspreview, "launch_alignment_verification_session", mock_launch)

    with pytest.raises(AudioAlignmentError, match="no interactive terminal"):
        _call_maybe_launch(
            tmp_path=tmp_path,
            config=AlignmentConfig(use_vspreview=True, force_interactive=True),
        )

    mock_launch.assert_not_called()


def test_optional_launch_error_logs_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=VSPreviewError("launch exited with code 7")),
    )
    mock_warning = MagicMock()
    monkeypatch.setattr(alignment_vspreview.log, "warning", mock_warning)

    _call_maybe_launch(tmp_path=tmp_path, config=AlignmentConfig(use_vspreview=True))

    mock_warning.assert_called_once()
    warning_args, warning_kwargs = mock_warning.call_args
    assert warning_args == ("vspreview_optional_launch_failed",)
    assert warning_kwargs["reason"] == "VSPreview failed: launch exited with code 7"
    assert warning_kwargs["code"] == "FC-4019"


def test_forced_launch_error_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "launch_alignment_verification_session",
        MagicMock(side_effect=VSPreviewError("launch exited with code 7")),
    )

    with pytest.raises(VSPreviewError, match="launch exited with code 7"):
        _call_maybe_launch(
            tmp_path=tmp_path,
            config=AlignmentConfig(use_vspreview=False, force_interactive=True),
        )


def test_prompt_for_confirmed_offsets_writes_to_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(alignment_vspreview.sys, "stdin", io.StringIO("120 108\n"))

    confirmed = alignment_vspreview._prompt_for_confirmed_offsets(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        no_color=True,
    )

    captured = capsys.readouterr()
    assert confirmed == {"ref:comp": 12}
    assert captured.out == ""
    assert "VSPreview Confirmation" in captured.err
    assert "ref" in captured.err
    assert "comp" in captured.err
    assert "+4" in captured.err
    assert "\x1b[" not in captured.err
    assert "[bold cyan]" not in captured.err


def test_prompt_for_confirmed_offsets_does_not_show_numeric_hint_when_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(alignment_vspreview.sys, "stdin", io.StringIO("120 108\n"))

    confirmed = alignment_vspreview._prompt_for_confirmed_offsets(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": None},
        no_color=True,
    )

    captured = capsys.readouterr()
    assert confirmed == {"ref:comp": 12}
    assert "comp" in captured.err
    assert "+0" not in captured.err


def test_prompt_for_confirmed_offsets_accepts_zero_source_frame_offset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_vspreview.sys, "stdin", io.StringIO("42, 42\n"))

    confirmed = alignment_vspreview._prompt_for_confirmed_offsets(
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
    monkeypatch.setattr(alignment_vspreview.sys, "stdin", io.StringIO(user_input))

    confirmed = alignment_vspreview._prompt_for_confirmed_offsets(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
    )

    assert confirmed == {}


def test_prompt_for_confirmed_offsets_eof_returns_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_vspreview.sys, "stdin", io.StringIO(""))

    confirmed = alignment_vspreview._prompt_for_confirmed_offsets(
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
        alignment_vspreview.sys,
        "stdin",
        io.StringIO("120 108\nskip\n210 216\n"),
    )
    comparisons = [
        tmp_path / "zeta.mkv",
        tmp_path / "alpha.mkv",
        tmp_path / "mid.mkv",
    ]

    confirmed = alignment_vspreview._prompt_for_confirmed_offsets(
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
        alignment_vspreview.sys,
        "stdin",
        io.StringIO("\n12\n12.5 9\ntrue 9\n-1 9\n120 108\n"),
    )

    confirmed = alignment_vspreview._prompt_for_confirmed_offsets(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
    )

    captured = capsys.readouterr()
    assert confirmed == {"ref:comp": 12}
    assert confirmed != {"ref:comp": 4}
    assert "source frames" in captured.err
    assert "non-negative" in captured.err


def test_maybe_launch_blank_then_valid_source_frames_saves_only_computed_offset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alignment_vspreview.sys, "stdin", io.StringIO("\n120 108\n"))
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "launch_alignment_verification_session",
        MagicMock(return_value=tmp_path / "vspreview.py"),
    )

    confirmed = maybe_launch_alignment_vspreview(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        cache_dir=tmp_path,
        config=AlignmentConfig(use_vspreview=True),
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
    monkeypatch.setattr(alignment_vspreview.sys, "stdin", io.StringIO(user_input))
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "launch_alignment_verification_session",
        MagicMock(return_value=tmp_path / "vspreview.py"),
    )

    confirmed = maybe_launch_alignment_vspreview(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        cache_dir=tmp_path,
        config=AlignmentConfig(use_vspreview=True),
        progress=None,
    )

    assert confirmed == expected_confirmed
    assert load_manual_overrides(tmp_path) == {}


def test_maybe_launch_confirm_skip_confirm_saves_only_confirmed_offsets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        alignment_vspreview.sys,
        "stdin",
        io.StringIO("120 108\nskip\n210 216\n"),
    )
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "launch_alignment_verification_session",
        MagicMock(return_value=tmp_path / "vspreview.py"),
    )

    confirmed = maybe_launch_alignment_vspreview(
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
        config=AlignmentConfig(use_vspreview=True),
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
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "launch_alignment_verification_session",
        MagicMock(return_value=tmp_path / "vspreview.py"),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "_prompt_for_confirmed_offsets",
        MagicMock(return_value={"ref:comp": 4}),
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "_save_confirmed_offsets",
        MagicMock(),
    )
    progress = MagicMock()

    _call_maybe_launch(
        tmp_path=tmp_path,
        config=AlignmentConfig(use_vspreview=True),
        progress=progress,
    )

    progress.set_description.assert_called_once_with("Alignment verification")
    progress.suspend.assert_called_once_with()
    progress.resume.assert_called_once_with()


def test_maybe_launch_propagates_no_color_to_launch_and_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_tty(monkeypatch, is_tty=True)
    monkeypatch.setattr(
        alignment_vspreview,
        "check_vspreview_availability",
        MagicMock(return_value=_availability(VSPreviewAvailabilityStatus.AVAILABLE)),
    )
    mock_launch = MagicMock(return_value=tmp_path / "vspreview.py")
    mock_prompt = MagicMock(return_value=None)
    monkeypatch.setattr(
        alignment_vspreview,
        "launch_alignment_verification_session",
        mock_launch,
    )
    monkeypatch.setattr(
        alignment_vspreview,
        "_prompt_for_confirmed_offsets",
        mock_prompt,
    )

    maybe_launch_alignment_vspreview(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "comp.mkv"],
        offsets_by_key={"ref:comp": 4},
        cache_dir=tmp_path,
        config=AlignmentConfig(use_vspreview=True, no_color=True),
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
