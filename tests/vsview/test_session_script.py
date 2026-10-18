from __future__ import annotations

import io
import json
import re
import sys
import types
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from rich.cells import cell_len

from frame_compare.vsview.session_runtime import AudioReviewPayload, SessionConsole
from frame_compare.vsview.session_script import (
    _build_script_content,
    write_vsview_session_script,
)


def test_write_vsview_session_script_removes_reserved_path_after_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(
        "frame_compare.vsview.session_script.write_text_atomic",
        fail_write,
    )

    with pytest.raises(OSError, match="disk full"):
        write_vsview_session_script(
            reference=Path("ref.mkv"),
            comparisons=[Path("comparison.mkv")],
            suggested_offsets_by_key={"ref:comparison": 0},
            audio_review_by_key={
                "ref:comparison": json.dumps(
                    {
                        "current_authority": {
                            "origin": "shared_computed_offsets",
                            "frame_offset": 0,
                        },
                        "evidence_availability": "historical_details_unavailable",
                        "audio_attempt": None,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            },
            cache_dir=tmp_path,
        )

    sessions_dir = tmp_path / "vsview_sessions"
    assert sessions_dir.is_dir()
    assert list(sessions_dir.iterdir()) == []


def _session_console(*, stderr: io.TextIOBase) -> SessionConsole:
    with redirect_stderr(stderr):
        return SessionConsole()


class _StubStderr(io.StringIO):
    encoding = "utf-8"

    def isatty(self) -> bool:
        return True


class _AsciiStderr(_StubStderr):
    encoding = "ascii"


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"COLORTERM": "truecolor"}, "38;2;210;172;107"),
        ({"COLORTERM": "24bit"}, "38;2;210;172;107"),
        ({"WT_SESSION": "1"}, "38;2;210;172;107"),
        ({"WT_SESSION": ""}, "38;2;210;172;107"),
        ({"TERM": "xterm-256color"}, "38;5;180"),
        ({"TERM": "xterm"}, "33"),
        ({}, "33"),
    ],
)
def test_generated_accent_colour_tiers(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], expected: str
) -> None:
    for key in ("COLORTERM", "WT_SESSION", "TERM", "NO_COLOR"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    helpers = _session_console(stderr=_StubStderr())

    assert helpers.accent_code() == expected


def test_generated_helpers_honour_no_color(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("COLORTERM", "WT_SESSION", "TERM"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    helpers = _session_console(stderr=_StubStderr())

    with redirect_stderr(_StubStderr()):
        assert helpers.header("text") == "text"
        assert helpers.style("text", "33") == "text"


def test_generated_glyph_and_arrow_ascii_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    ascii_stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    helpers = _session_console(stderr=ascii_stderr)

    assert helpers.glyph("waiting") == ">"
    assert helpers.glyph("failed") == "x"
    assert helpers.glyph("warning") == "!"
    assert helpers.arrow() == "->"
    ascii_stderr.close()

    helpers = _session_console(stderr=_StubStderr())

    assert helpers.glyph("waiting") == "\u203a"
    assert helpers.glyph("failed") == "\u2717"
    assert helpers.arrow() == "\u2192"


def _decision_payload(*, state: str) -> dict[str, object]:
    return {
        "state": state,
        "candidate": {
            "frame_offset": 0,
            "time_offset_seconds": 0.0,
            "subframe_estimate": 0.0,
            "basis": "audio_only",
        },
        "primary_reason": "test",
        "failed_gates": [],
    }


def _accepted_review() -> str:
    return json.dumps(
        {
            "current_authority": {"origin": "shared_computed_offsets", "frame_offset": 0},
            "evidence_availability": "historical_details_unavailable",
            "audio_attempt": {"decision": _decision_payload(state="trusted_automatic")},
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _provisional_review() -> str:
    return json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "not_computed",
            "audio_attempt": {"decision": _decision_payload(state="provisional")},
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _malformed_review() -> str:
    return json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "not_computed",
            "audio_attempt": {"decision": {"state": "provisional"}},
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _execute_ready_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    stderr_encoding: str,
    audio_review_by_key: dict[str, str] | None = None,
    frame_props_by_stem: dict[str, dict[str, str | int | float]] | None = None,
) -> str:
    reference = tmp_path / "ref.mkv"
    comparisons = [tmp_path / "a.mkv", tmp_path / "b.mkv"]
    reference.touch()
    for comparison in comparisons:
        comparison.touch()

    class FakeClip:
        def __init__(self, stem: str) -> None:
            self.stem = stem
            self.num_frames = 20_000
            self.fps = SimpleNamespace(numerator=24, denominator=1)

    clips = {path.stem: FakeClip(path.stem) for path in (reference, *comparisons)}

    class FakeLsmas:
        def LWLibavSource(self, path: str, **_kwargs: object) -> FakeClip:
            return clips[Path(path).stem]

    class FakeStd:
        def AssumeFPS(self, clip: FakeClip, **_kwargs: object) -> FakeClip:
            return clip

        def SetFrameProps(self, clip: FakeClip, **_kwargs: object) -> FakeClip:
            return clip

    core = SimpleNamespace(lsmas=FakeLsmas(), std=FakeStd())
    fake_vapoursynth = types.ModuleType("vapoursynth")
    fake_vapoursynth.core = core  # pyright: ignore[reportAttributeAccessIssue]
    fake_vsview = types.ModuleType("vsview")
    fake_vsview.set_output = lambda *args, **kwargs: None  # pyright: ignore[reportAttributeAccessIssue]
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vapoursynth)
    monkeypatch.setitem(sys.modules, "vsview", fake_vsview)
    monkeypatch.setenv("NO_COLOR", "1")

    script = _build_script_content(
        reference=reference,
        comparisons=comparisons,
        suggested_offsets_by_key={"ref:a": 0, "ref:b": None},
        audio_review_by_key=audio_review_by_key
        if audio_review_by_key is not None
        else {"ref:a": _accepted_review(), "ref:b": _provisional_review()},
        frame_props_by_stem=frame_props_by_stem
        if frame_props_by_stem is not None
        else {
            stem: {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1, "_Range": 0}
            for stem in ("ref", "a", "b")
        },
        presentation_names_by_stem={
            "ref": "2160p \u00b7 REF",
            "a": "2160p \u00b7 A",
            "b": "2160p \u00b7 B",
        },
        short_names_by_stem={"ref": "Ref", "a": "ShortA", "b": "LongerB"},
    )
    stderr: io.StringIO = _AsciiStderr() if stderr_encoding == "ascii" else _StubStderr()
    with redirect_stderr(stderr):
        exec(
            compile(script, "<vsview-ready>", "exec"),
            {"__name__": "vsview_ready", "__file__": str(tmp_path / "session_x.py")},
        )
    return stderr.getvalue()


@pytest.mark.parametrize("case", ["utf8", "ascii", "malformed"])
def test_generated_ready_block_output_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    output = _execute_ready_block(
        tmp_path,
        monkeypatch,
        stderr_encoding="ascii" if case == "ascii" else "utf-8",
        audio_review_by_key={"ref:a": _accepted_review(), "ref:b": _malformed_review()}
        if case == "malformed"
        else None,
    )
    if case == "utf8":
        assert "VSView is open \u00b7 waiting for you" in output
        assert "Open Tool Panel \u2192 Frame Compare Alignment Review." in output
        assert "Unlink playheads, then position every source on the same visible moment." in output
        assert (
            "Save the alignment in the panel, then close VSView to continue Frame Compare."
            in output
        )
        assert "outputs" in output
        assert "Ref" in output
        assert "ShortA" in output
        assert "LongerB" in output
        assert "audio +0f · reused" in output
        assert "audio +0f · not applied" in output
        assert "hints" not in output
    elif case == "ascii":
        assert "+- > VSView is open | waiting for you" in output.splitlines()
        assert "| 1  Open Tool Panel -> Frame Compare Alignment Review." in output.splitlines()
        assert "audio +0f | reused" in output
        assert "hints" not in output
    else:
        assert "ShortA" in output and "audio +0f · reused" in output
        assert "LongerB" in output and "no audio match" in output
        assert "hints" not in output


def test_generated_ready_block_keeps_display_assumptions_inside_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _execute_ready_block(
        tmp_path,
        monkeypatch,
        stderr_encoding="utf-8",
        frame_props_by_stem={
            "ref": {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1},
            "a": {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1, "_Range": 0},
            "b": {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1, "_Range": 0},
        },
    )

    lines = output.splitlines()
    assert "│ ! VSView display assumptions" in lines
    note_index = lines.index("│ ! VSView display assumptions")
    assert lines[note_index + 1].startswith("│ source")
    assert "│ range" in lines[note_index + 2]
    assert "│ impact" in lines[note_index + 3]
    assert lines[-2] == "╰─"
    assert "VSView Display Assumptions" not in output


@pytest.mark.parametrize(
    "value", ["very-long-source-name-" * 4, "日本語映像" * 9, "Cafe\u0301" * 20]
)
@pytest.mark.parametrize("no_color", [False, True])
def test_session_section_wraps_key_values_and_list_rows_at_terminal_width(
    monkeypatch: pytest.MonkeyPatch, value: str, no_color: bool
) -> None:
    if no_color:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(
        "frame_compare.vsview.session_runtime.shutil.get_terminal_size",
        lambda **_kwargs: SimpleNamespace(columns=40, lines=24),
    )
    stderr = _StubStderr()
    with redirect_stderr(stderr):
        console = SessionConsole()
        console.section(
            "› VSView is open · waiting for you",
            [
                console.key_value("source", console.dim(value)),
                "A long instruction row that must continue after the rail without losing text.",
                console.note("warning", "A long warning row that also needs to wrap."),
            ],
        )

    output = stderr.getvalue()
    lines = output.splitlines()
    visible_lines = [re.sub(r"\x1b\[[0-9;]*m", "", line) for line in lines]
    assert all(cell_len(line) <= 40 for line in visible_lines)
    assert any(line.startswith("│                 ") for line in visible_lines)
    assert any(
        line.startswith("│ ") and not line.startswith("│                 ")
        for line in visible_lines[2:-2]
    )
    source_start = next(
        index for index, line in enumerate(visible_lines) if line.startswith("│ source")
    )
    source_lines = []
    for line in visible_lines[source_start:]:
        if source_lines and not line.startswith("│                 "):
            break
        source_lines.append(line[18:])
    assert "".join(source_lines) == value
    assert "instruction row" in output
    assert "warning row" in output


@pytest.mark.parametrize(
    ("origin", "offset", "decision", "expected", "warning"),
    [
        ("computed_this_run", 4, "trusted_automatic", "audio +4f", False),
        ("shared_computed_offsets", -2, None, "audio -2f · reused", False),
        ("interactive_confirmed_this_run", 3, None, "previously confirmed +3f", False),
        ("shared_previous_offsets", 5, None, "previously confirmed +5f", False),
        ("preexisting_manual_override", -1, None, "manual offset -1f", False),
        ("none", None, "provisional", "audio +6f · not applied", True),
        ("none", None, "unavailable", "no audio match", True),
    ],
)
def test_audio_output_state_preserves_authority_and_candidate_state(
    origin: str,
    offset: int | None,
    decision: str | None,
    expected: str,
    warning: bool,
) -> None:
    attempt: dict[str, object] | None = None
    if decision is not None:
        candidate: dict[str, object] | None = (
            {"frame_offset": 4 if decision == "trusted_automatic" else 6}
            if decision != "unavailable"
            else None
        )
        attempt = {"decision": {"state": decision, "candidate": candidate}}
    payload = cast(
        AudioReviewPayload,
        {
            "current_authority": {"origin": origin, "frame_offset": offset},
            "audio_attempt": attempt,
        },
    )
    console = _session_console(stderr=_StubStderr())

    assert console._audio_output_state(payload) == (expected, warning)


def test_short_names_by_stem_defaults_to_display_names(tmp_path: Path) -> None:
    reference = Path("ref.mkv")
    comparisons = [Path("a.mkv")]
    kwargs: dict[str, Any] = {
        "reference": reference,
        "comparisons": comparisons,
        "suggested_offsets_by_key": {"ref:a": 0},
        "audio_review_by_key": {"ref:a": _accepted_review()},
        "presentation_names_by_stem": {"ref": "REF", "a": "A"},
    }
    explicit = _build_script_content(short_names_by_stem={}, **kwargs)
    defaulted = _build_script_content(**kwargs)
    named = _build_script_content(short_names_by_stem={"a": "ShortA"}, **kwargs)

    assert explicit == defaulted
    assert '"ShortA"' in named
    assert named != defaulted


@pytest.mark.parametrize("memory_limit_mb", [None, 1024])
def test_session_script_optional_frame_cache_limit(
    memory_limit_mb: int | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[tuple[int, int | None]] = []
    core = SimpleNamespace(max_cache_size=321)
    fake_vapoursynth = types.ModuleType("vapoursynth")
    fake_vapoursynth.core = core  # pyright: ignore[reportAttributeAccessIssue]
    fake_vsview = types.ModuleType("vsview")
    fake_vsview.set_output = lambda *args, **kwargs: None  # pyright: ignore[reportAttributeAccessIssue]
    monkeypatch.setitem(sys.modules, "vapoursynth", fake_vapoursynth)
    monkeypatch.setitem(sys.modules, "vsview", fake_vsview)

    def observe_loader(_core: object) -> object:
        observed.append((core.max_cache_size, memory_limit_mb))
        raise RuntimeError("stop after observing cache admission")

    monkeypatch.setattr(
        "frame_compare.vsview.session_runtime.resolve_lwlibavsource", observe_loader
    )
    script = _build_script_content(
        reference=tmp_path / "ref.mkv",
        comparisons=[tmp_path / "cmp.mkv"],
        suggested_offsets_by_key={"ref:cmp": 0},
        audio_review_by_key={"ref:cmp": _accepted_review()},
        memory_limit_mb=memory_limit_mb,
    )
    with pytest.raises(SystemExit) as caught:
        exec(compile(script, "session.py", "exec"), {"__file__": "session_x.py"})
    assert caught.value.code == 1
    assert observed == [(321 if memory_limit_mb is None else memory_limit_mb, memory_limit_mb)]


def test_session_output_names_pad_by_terminal_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    from frame_compare.vsview.session_runtime import ComparisonSource, ReferenceSource

    monkeypatch.setenv("NO_COLOR", "1")
    stderr = _StubStderr()
    with redirect_stderr(stderr):
        console = SessionConsole()
        reference = ReferenceSource(
            label="ref", path="ref.mkv", index_path="ref.lwi", display_name="日本語"
        )
        target = ComparisonSource(
            path="a.mkv",
            index_path="a.lwi",
            display_name="Cafe\u0301",
            comparison_key="ref:a",
            suggested_offset=0,
            audio_review=_accepted_review(),
        )
        console.section("Outputs", console._output_table_rows(reference, {"a": target}, {}))
    lines = stderr.getvalue().splitlines()
    reference_line = next(line for line in lines if "reference" in line)
    comparison_line = next(line for line in lines if "audio +0f" in line)
    assert cell_len(reference_line[: reference_line.index("reference")]) == 29
    assert cell_len(comparison_line[: comparison_line.index("audio")]) == 29
    assert "Cafe\u0301" in comparison_line
