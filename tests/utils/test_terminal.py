import pytest

from frame_compare.utils.terminal import no_color_requested, stream_is_tty


class _BrokenTTY:
    def isatty(self) -> bool:
        raise ValueError("closed stream")


class _InteractiveTTY:
    def isatty(self) -> bool:
        return True


def test_no_color_requested_respects_explicit_flag_and_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert no_color_requested(explicit_no_color=True) is True
    monkeypatch.setenv("NO_COLOR", "")
    assert no_color_requested() is True
    monkeypatch.delenv("NO_COLOR")
    assert no_color_requested() is False


def test_stream_is_tty_handles_missing_and_broken_streams() -> None:
    assert stream_is_tty(object()) is False
    assert stream_is_tty(_BrokenTTY()) is False
    assert stream_is_tty(_InteractiveTTY()) is True
