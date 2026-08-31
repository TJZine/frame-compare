"""Tests for shared alignment previous-offset prompt output."""

from __future__ import annotations

import io
import os
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import frame_compare.services.alignment_reuse_prompt as reuse_prompt
from frame_compare.services.alignment_reuse_prompt import (
    PROMPT_UNAVAILABLE_MESSAGE,
    REUSE_PREVIOUS_OFFSETS_PROMPT,
    PreviousOffsetPromptRow,
    previous_offset_prompt_input_from_rows,
    prompt_for_previous_offset_reuse,
)
from frame_compare.utils.types import (
    AlignmentCacheSettings,
    AlignmentClipIdentity,
    AlignmentClipRequest,
    AlignmentRequest,
)


class _TTYStringIO(io.StringIO):
    def __init__(self, value: str, *, is_tty: bool) -> None:
        super().__init__(value)
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty


class _EchoingTTYStringIO(_TTYStringIO):
    def __init__(self, value: str, *, is_tty: bool, echo_to: io.StringIO) -> None:
        super().__init__(value, is_tty=is_tty)
        self._echo_to = echo_to

    def readline(self, *_args: object, **_kwargs: object) -> str:
        response = super().readline()
        self._echo_to.write(response)
        return response


class _FailingTTYStringIO(_TTYStringIO):
    def readline(self, *_args: object, **_kwargs: object) -> str:
        raise OSError("input unavailable")


def _clip(path: Path, *, label: str) -> AlignmentClipRequest:
    return AlignmentClipRequest(
        path=path,
        label=label,
        identity=AlignmentClipIdentity(path=path, size_bytes=10, mtime_ns=20),
        trim_start_frames=0,
        trim_end_frame_inclusive=None,
        effective_fps_num=24000,
        effective_fps_den=1001,
        source_frame_count=100,
    )


def _request(tmp_path: Path) -> AlignmentRequest:
    return AlignmentRequest(
        reference=_clip(tmp_path / "ref [bold red].mkv", label="Reference [bold]"),
        selected_reference_relationship="explicit",
        comparisons=[
            _clip(
                tmp_path / "comp [green]/A [red].mkv",
                label="Comparison [cyan] <one>",
            ),
            _clip(tmp_path / "B.mkv", label="Comparison two"),
        ],
        previous_offsets="prompt",
        generated_dir=tmp_path / "generated",
        shared_alignment_cache_dir=tmp_path / "generated" / "cache" / "alignment",
        settings=AlignmentCacheSettings(
            sample_rate=8000,
            max_offset_seconds=30.0,
            correlation_mode="raw_fft",
            preprocessing_mode="none",
            channel_strategy="mono_downmix",
            confidence_threshold=0.0,
            ambiguity_peak_ratio=1.0,
            window_length_seconds=0.0,
            window_stride_seconds=0.0,
            minimum_valid_windows=1,
            consensus_minimum_ratio=1.0,
            refinement_mode="disabled",
            refinement_sample_rate=None,
        ),
    )


def _prompt_input(request: AlignmentRequest) -> reuse_prompt.PreviousOffsetPromptInput:
    rows: list[PreviousOffsetPromptRow] = []
    for index, comparison in enumerate(request.comparisons):
        rows.append(
            PreviousOffsetPromptRow(
                label=comparison.label,
                stem=comparison.path.stem,
                filename=comparison.path.name,
                path=str(comparison.path),
                frame_offset=12 if index == 0 else -4,
                time_offset_seconds=0.5 if index == 0 else -0.166,
                accepted_at="2026-06-06T12:34:56Z" if index == 0 else "2026-06-06T13:00:00Z",
                source="computed" if index == 0 else "confirmed",
            )
        )
    return previous_offset_prompt_input_from_rows(request=request, rows=rows)


def _fallback_only_output(stderr_output: str) -> bool:
    return stderr_output.strip() == PROMPT_UNAVAILABLE_MESSAGE


def test_prompt_prints_rich_safe_table_to_stderr_and_accepts_yes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = _request(tmp_path)
    stderr = _TTYStringIO("", is_tty=True)
    monkeypatch.setattr(reuse_prompt.sys, "stdin", _TTYStringIO("yes\n", is_tty=True))
    monkeypatch.setattr(reuse_prompt.sys, "stderr", stderr)

    accepted = prompt_for_previous_offset_reuse(
        prompt_input=_prompt_input(request),
        progress=None,
        no_color=True,
    )

    captured = capsys.readouterr()
    stderr_output = stderr.getvalue()
    assert accepted is True
    assert captured.out == ""
    assert "[WAIT] Alignment reuse" in stderr_output
    assert "[y/N]" in stderr_output
    panel_line = next(
        line for line in stderr_output.splitlines() if "[WAIT] Alignment reuse" in line
    )
    assert panel_line.startswith("  ")
    assert not panel_line.startswith("   ")
    prompt_line = next(
        line for line in stderr_output.splitlines() if "Reuse these offsets?" in line
    )
    assert prompt_line == f"    {REUSE_PREVIOUS_OFFSETS_PROMPT}"
    assert stderr_output.index("[WAIT] Alignment reuse") < stderr_output.index(
        "    Reuse these offsets?"
    )
    assert "Comparison [cyan]" in stderr_output
    assert "<one>" in stderr_output
    assert "A [red].mkv" in stderr_output
    assert stderr_output.count("A [red].mkv") == 1
    assert "+12 frames" in stderr_output
    assert "-4 frames" in stderr_output
    assert "0.5" in stderr_output
    assert "-0.166" in stderr_output
    assert "2026-06-06 12:34:56 UTC" in stderr_output
    assert "Computed" in stderr_output
    assert "Preview-confirmed" in stderr_output
    assert "cached" not in stderr_output
    assert stderr_output.index("+12 frames") < stderr_output.index("Computed")
    assert stderr_output.index("Computed") < stderr_output.index("Accepted")
    assert stderr_output.index("Accepted") < stderr_output.index("Cache")


def test_prompt_leaves_one_blank_line_after_a_normal_answer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    stderr = _TTYStringIO("", is_tty=True)
    monkeypatch.setattr(
        reuse_prompt.sys,
        "stdin",
        _EchoingTTYStringIO("yes\n", is_tty=True, echo_to=stderr),
    )
    monkeypatch.setattr(reuse_prompt.sys, "stderr", stderr)

    assert prompt_for_previous_offset_reuse(
        prompt_input=_prompt_input(request),
        progress=None,
        no_color=True,
    )

    stderr.write("  [OK] ALIGN  Completed in 20s\n")
    rendered = stderr.getvalue()
    assert rendered.endswith(
        f"    {REUSE_PREVIOUS_OFFSETS_PROMPT}yes\n\n  [OK] ALIGN  Completed in 20s\n"
    )
    assert (
        rendered.index("[WAIT] Alignment reuse")
        < rendered.index("    Reuse these offsets?")
        < rendered.index("  [OK] ALIGN")
    )


def test_prompt_shows_full_filename_once_when_label_equals_stem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    prompt_input = _prompt_input(request)
    first_row = prompt_input.rows[0]
    prompt_input = replace(
        prompt_input,
        reference_label=Path(prompt_input.reference_filename).stem,
        shared_cache_path=Path("generated/cache/alignment/alignment_reuse.toml"),
        rows=(replace(first_row, label=first_row.stem),),
    )
    stderr = _TTYStringIO("", is_tty=True)
    monkeypatch.setattr(reuse_prompt.sys, "stdin", _TTYStringIO("n\n", is_tty=True))
    monkeypatch.setattr(reuse_prompt.sys, "stderr", stderr)

    prompt_for_previous_offset_reuse(prompt_input=prompt_input, progress=None, no_color=True)

    output = stderr.getvalue()
    assert output.count(prompt_input.reference_filename) == 1
    assert output.count(first_row.filename) == 1
    assert str(prompt_input.shared_cache_path) in "".join(output.split())


def test_prompt_renders_prebuilt_compact_identity_with_cache_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    request = replace(
        request,
        reference=replace(
            request.reference,
            presentation_name="2160p | PMTP WEB-DL | DV HDR10+ | Kitsune",
        ),
        presentation_content="Avatar Aang The Last Airbender (2026)",
    )
    prompt_input = _prompt_input(request)
    prompt_input = replace(
        prompt_input,
        shared_cache_path=Path("generated/cache/alignment/alignment_reuse.toml"),
        rows=(
            replace(
                prompt_input.rows[0],
                presentation_name="2160p | ATV WEB-DL | DV HDR10+ | REPACK | Kitsune",
            ),
        ),
    )
    stderr = _TTYStringIO("", is_tty=True)
    monkeypatch.setattr(reuse_prompt.sys, "stdin", _TTYStringIO("\n", is_tty=True))
    monkeypatch.setattr(reuse_prompt.sys, "stderr", stderr)

    assert not prompt_for_previous_offset_reuse(
        prompt_input=prompt_input, progress=None, no_color=True
    )
    output = stderr.getvalue()
    assert "[WAIT] Alignment reuse" in output
    assert "Avatar Aang The Last Airbender (2026)" in output
    assert "PMTP WEB-DL" in output
    assert "ATV WEB-DL" in output
    assert str(request.reference.path) not in output
    assert str(request.comparisons[0].path) not in output
    assert "Cache" in output
    assert str(prompt_input.shared_cache_path) in "".join(output.split())


def test_prompt_does_not_use_unbounded_terminal_width(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    console_widths: list[int | None] = []
    original_console = reuse_prompt.Console

    class RecordingConsole(original_console):
        def __init__(self, *args: object, **kwargs: object) -> None:
            console_widths.append(kwargs.get("width"))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(
        reuse_prompt.shutil,
        "get_terminal_size",
        lambda **_: os.terminal_size((240, 24)),
    )
    monkeypatch.setattr(reuse_prompt, "Console", RecordingConsole)
    monkeypatch.setattr(reuse_prompt.sys, "stdin", _TTYStringIO("n\n", is_tty=True))
    monkeypatch.setattr(reuse_prompt.sys, "stderr", _TTYStringIO("", is_tty=True))

    accepted = prompt_for_previous_offset_reuse(
        prompt_input=_prompt_input(request),
        progress=None,
        no_color=True,
    )

    assert accepted is False
    assert console_widths
    assert all(width is not None and width < 240 for width in console_widths)


@pytest.mark.parametrize("columns", [60, 80, 120, 240])
def test_prompt_uses_actual_narrow_terminal_width(
    columns: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(
        reuse_prompt.shutil,
        "get_terminal_size",
        lambda **_: os.terminal_size((columns, 24)),
    )
    monkeypatch.setattr(reuse_prompt.sys, "stdin", _TTYStringIO("n\n", is_tty=True))
    stderr = _TTYStringIO("", is_tty=True)
    monkeypatch.setattr(reuse_prompt.sys, "stderr", stderr)

    assert (
        prompt_for_previous_offset_reuse(
            prompt_input=_prompt_input(request),
            progress=None,
            no_color=True,
        )
        is False
    )
    stderr_output = stderr.getvalue()
    assert "[WAIT] Alignment reuse" in stderr_output
    assert REUSE_PREVIOUS_OFFSETS_PROMPT in stderr_output
    assert "\x1b[" not in stderr_output
    assert all(len(line) <= columns for line in stderr_output.splitlines())


@pytest.mark.parametrize("response", ["\n", "n\n", "NO\n", "anything else\n"])
def test_prompt_defaults_to_no_for_blank_no_or_unrecognized_input(
    response: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(reuse_prompt.sys, "stdin", _TTYStringIO(response, is_tty=True))
    monkeypatch.setattr(reuse_prompt.sys, "stderr", _TTYStringIO("", is_tty=True))

    accepted = prompt_for_previous_offset_reuse(
        prompt_input=_prompt_input(request),
        progress=None,
        no_color=True,
    )

    assert accepted is False


def test_prompt_non_tty_stdin_prints_only_fallback_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = _request(tmp_path)
    stderr = _TTYStringIO("", is_tty=True)
    monkeypatch.setattr(reuse_prompt.sys, "stdin", _TTYStringIO("yes\n", is_tty=False))
    monkeypatch.setattr(reuse_prompt.sys, "stderr", stderr)

    accepted = prompt_for_previous_offset_reuse(
        prompt_input=_prompt_input(request),
        progress=None,
        no_color=True,
    )

    captured = capsys.readouterr()
    stderr_output = stderr.getvalue()
    assert accepted is False
    assert captured.out == ""
    assert _fallback_only_output(stderr_output)
    assert "Alignment reuse" not in stderr_output
    assert "[y/N]" not in stderr_output
    assert "Comparison [cyan] <one>" not in stderr_output


@pytest.mark.parametrize(
    "stdin", [_TTYStringIO("", is_tty=True), _FailingTTYStringIO("", is_tty=True)]
)
def test_prompt_visible_prompt_path_fallbacks_on_eof_or_read_failure(
    stdin: io.StringIO,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = _request(tmp_path)
    stderr = _TTYStringIO("", is_tty=True)
    monkeypatch.setattr(reuse_prompt.sys, "stdin", stdin)
    monkeypatch.setattr(reuse_prompt.sys, "stderr", stderr)

    accepted = prompt_for_previous_offset_reuse(
        prompt_input=_prompt_input(request),
        progress=None,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert accepted is False
    assert captured.out == ""
    stderr_output = stderr.getvalue()
    assert "[WAIT] Alignment reuse" in stderr_output
    assert "[y/N]" in stderr_output
    expected_prompt = f"    {REUSE_PREVIOUS_OFFSETS_PROMPT}"
    assert f"{expected_prompt}\n{PROMPT_UNAVAILABLE_MESSAGE}" in stderr_output
    assert f"    {PROMPT_UNAVAILABLE_MESSAGE}" not in stderr_output


def test_prompt_emits_no_human_diagnostic_when_stderr_is_not_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = _request(tmp_path)
    stderr = _TTYStringIO("", is_tty=False)
    monkeypatch.setattr(reuse_prompt.sys, "stdin", _TTYStringIO("yes\n", is_tty=True))
    monkeypatch.setattr(reuse_prompt.sys, "stderr", stderr)

    accepted = prompt_for_previous_offset_reuse(
        prompt_input=_prompt_input(request),
        progress=None,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert accepted is False
    assert stderr.getvalue() == ""
    assert captured.out == ""


def test_prompt_suspends_and_resumes_progress_around_table_and_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    progress = MagicMock()
    monkeypatch.setattr(reuse_prompt.sys, "stdin", _TTYStringIO("y\n", is_tty=True))
    monkeypatch.setattr(reuse_prompt.sys, "stderr", _TTYStringIO("", is_tty=True))

    accepted = prompt_for_previous_offset_reuse(
        prompt_input=_prompt_input(request),
        progress=progress,
        no_color=True,
    )

    assert accepted is True
    progress.suspend.assert_called_once_with()
    progress.resume.assert_called_once_with()


@pytest.mark.parametrize(
    ("stdin", "stderr"),
    [
        (_TTYStringIO("yes\n", is_tty=False), _TTYStringIO("", is_tty=True)),
        (_TTYStringIO("yes\n", is_tty=True), _TTYStringIO("", is_tty=False)),
    ],
)
def test_prompt_hidden_or_noninteractive_paths_do_not_suspend_progress(
    stdin: io.StringIO,
    stderr: io.StringIO,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(tmp_path)
    progress = MagicMock()
    monkeypatch.setattr(reuse_prompt.sys, "stdin", stdin)
    monkeypatch.setattr(reuse_prompt.sys, "stderr", stderr)

    accepted = prompt_for_previous_offset_reuse(
        prompt_input=_prompt_input(request),
        progress=progress,
        no_color=True,
    )

    assert accepted is False
    progress.suspend.assert_not_called()
    progress.resume.assert_not_called()


def test_prompt_falls_back_to_filename_when_labels_are_blank(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request = _request(tmp_path)
    request = AlignmentRequest(
        reference=AlignmentClipRequest(
            path=request.reference.path,
            label="   ",
            identity=request.reference.identity,
            trim_start_frames=request.reference.trim_start_frames,
            trim_end_frame_inclusive=request.reference.trim_end_frame_inclusive,
            effective_fps_num=request.reference.effective_fps_num,
            effective_fps_den=request.reference.effective_fps_den,
            source_frame_count=request.reference.source_frame_count,
            selected_audio_stream=request.reference.selected_audio_stream,
        ),
        selected_reference_relationship=request.selected_reference_relationship,
        comparisons=[
            AlignmentClipRequest(
                path=request.comparisons[0].path,
                label="",
                identity=request.comparisons[0].identity,
                trim_start_frames=request.comparisons[0].trim_start_frames,
                trim_end_frame_inclusive=request.comparisons[0].trim_end_frame_inclusive,
                effective_fps_num=request.comparisons[0].effective_fps_num,
                effective_fps_den=request.comparisons[0].effective_fps_den,
                source_frame_count=request.comparisons[0].source_frame_count,
                selected_audio_stream=request.comparisons[0].selected_audio_stream,
            ),
            request.comparisons[1],
        ],
        previous_offsets=request.previous_offsets,
        generated_dir=request.generated_dir,
        shared_alignment_cache_dir=request.shared_alignment_cache_dir,
        settings=request.settings,
    )
    prompt_input = previous_offset_prompt_input_from_rows(
        request=request,
        rows=[
            PreviousOffsetPromptRow(
                label="",
                stem=request.comparisons[0].path.stem,
                filename=request.comparisons[0].path.name,
                path=str(request.comparisons[0].path),
                frame_offset=12,
                time_offset_seconds=0.5,
                accepted_at="2026-06-06T12:34:56Z",
                source="computed",
            )
        ],
    )
    monkeypatch.setattr(reuse_prompt.sys, "stdin", _TTYStringIO("n\n", is_tty=True))
    monkeypatch.setattr(reuse_prompt.sys, "stderr", _TTYStringIO("", is_tty=True))

    accepted = prompt_for_previous_offset_reuse(
        prompt_input=prompt_input,
        progress=None,
        no_color=True,
    )

    captured = capsys.readouterr()
    assert accepted is False
    stderr_output = reuse_prompt.sys.stderr.getvalue()
    assert captured.out == ""
    assert request.reference.path.name in stderr_output
    assert request.comparisons[0].path.name in stderr_output
