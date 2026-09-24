from __future__ import annotations

import io
import json
import os
import sys
import types
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from frame_compare.vsview.session_script import (
    _build_helpers_section,
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


def _exec_generated_helpers(*, stderr: io.StringIO) -> dict[str, Any]:
    namespace: dict[str, Any] = {"sys": SimpleNamespace(stdout=io.StringIO(), stderr=stderr)}
    namespace["os"] = os
    exec(
        compile(_build_helpers_section(), "<generated-helpers>", "exec"),
        namespace,
    )
    return namespace


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
    helpers = _exec_generated_helpers(stderr=_StubStderr())

    assert helpers["_accent_code"]() == expected


def test_generated_helpers_honour_no_color(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("COLORTERM", "WT_SESSION", "TERM"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    helpers = _exec_generated_helpers(stderr=_StubStderr())

    assert helpers["_header"]("text") == "text"
    assert helpers["_style"]("text", "33") == "text"


def test_generated_glyph_and_arrow_ascii_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    helpers = _exec_generated_helpers(stderr=_AsciiStderr())

    assert helpers["_glyph"]("waiting") == ">"
    assert helpers["_glyph"]("failed") == "x"
    assert helpers["_glyph"]("warning") == "!"
    assert helpers["_arrow"]() == "->"

    helpers = _exec_generated_helpers(stderr=_StubStderr())

    assert helpers["_glyph"]("waiting") == "\u203a"
    assert helpers["_glyph"]("failed") == "\u2717"
    assert helpers["_arrow"]() == "\u2192"


def _accepted_review() -> str:
    return json.dumps(
        {
            "current_authority": {"origin": "shared_computed_offsets", "frame_offset": 0},
            "evidence_availability": "historical_details_unavailable",
            "audio_attempt": {"decision": {"state": "trusted_automatic"}},
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _provisional_review() -> str:
    return json.dumps(
        {
            "current_authority": {"origin": "none", "frame_offset": None},
            "evidence_availability": "not_computed",
            "audio_attempt": {
                "decision": {
                    "state": "provisional",
                    "candidate": {"frame_offset": 0},
                    "primary_reason": "test",
                }
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _execute_ready_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    stderr_encoding: str,
) -> str:
    reference = tmp_path / "ref.mkv"
    comparisons = [tmp_path / "a.mkv", tmp_path / "b.mkv"]
    reference.touch()
    for comparison in comparisons:
        comparison.touch()

    class FakeClip:
        def __init__(self, stem: str) -> None:
            self.stem = stem
            self.fps = SimpleNamespace(numerator=24, denominator=1)

    clips = {path.stem: FakeClip(path.stem) for path in (reference, *comparisons)}

    class FakeLsmas:
        def LWLibavSource(self, path: str, **_kwargs: object) -> FakeClip:
            return clips[Path(path).stem]

    class FakeText:
        def Text(self, clip: FakeClip, _text: str, *, alignment: int) -> FakeClip:
            assert alignment == 7
            return clip

    class FakeStd:
        def AssumeFPS(self, clip: FakeClip, **_kwargs: object) -> FakeClip:
            return clip

        def SetFrameProps(self, clip: FakeClip, **_kwargs: object) -> FakeClip:
            return clip

    core = SimpleNamespace(lsmas=FakeLsmas(), text=FakeText(), std=FakeStd())
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
        audio_review_by_key={"ref:a": _accepted_review(), "ref:b": _provisional_review()},
        frame_props_by_stem={
            stem: {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1, "_Range": 0}
            for stem in ("ref", "a", "b")
        },
        presentation_names_by_stem={
            "ref": "2160p \u00b7 REF",
            "a": "2160p \u00b7 A",
            "b": "2160p \u00b7 B",
        },
        short_names_by_stem={"a": "ShortA", "b": "LongerB"},
    )
    stderr: io.StringIO = _AsciiStderr() if stderr_encoding == "ascii" else _StubStderr()
    with redirect_stderr(stderr):
        exec(
            compile(script, "<vsview-ready>", "exec"),
            {"__name__": "vsview_ready", "__file__": str(tmp_path / "session_x.py")},
        )
    return stderr.getvalue()


def test_generated_ready_block_reports_outputs_and_hints_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _execute_ready_block(tmp_path, monkeypatch, stderr_encoding="utf-8")

    assert output.splitlines() == [
        "\u203a VSView is open \u00b7 waiting for you",
        "  1  Open Tool Panel \u2192 Frame Compare Alignment Review.",
        "  2  Unlink playheads, then position every source on the same visible moment.",
        "  3  Save the alignment in the panel, then close VSView to continue Frame Compare.",
        "",
        "  outputs  0  2160p \u00b7 REF",
        "           1  2160p \u00b7 A",
        "           2  2160p \u00b7 B",
        "  hints    ShortA   Audio alignment accepted: +0f",
        "           LongerB  Provisional +0f - NOT APPLIED",
    ]


def test_generated_ready_block_ascii_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _execute_ready_block(tmp_path, monkeypatch, stderr_encoding="ascii")

    assert "> VSView is open \u00b7 waiting for you" in output.splitlines()
    assert "  1  Open Tool Panel -> Frame Compare Alignment Review." in output.splitlines()
    assert "  hints    ShortA   Audio alignment accepted: +0f" in output.splitlines()


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
    assert "SHORT_NAMES = {}" in defaulted
    assert '"ShortA"' in named
    assert named != defaulted
