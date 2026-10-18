from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TextIO, TypedDict, cast

from frame_compare.utils.alignment_evidence import AudioAlignmentDecision, evidence_from_payload
from frame_compare.vs.source import INDEX_CONSTRUCTION_FAILURE_MARKER
from frame_compare.vsview.alignment_review_contract import (
    ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY,
    ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY,
    ALIGNMENT_REVIEW_METADATA_NAME_KEY,
    ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY,
    ALIGNMENT_REVIEW_METADATA_ROLE_KEY,
    ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY,
    ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY,
    ALIGNMENT_REVIEW_METADATA_VERSION,
    ALIGNMENT_REVIEW_METADATA_VERSION_KEY,
)

if TYPE_CHECKING:
    import vapoursynth as vs


_ANSI_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True, slots=True)
class _SectionKeyValue:
    key: str
    value: str


class ReferenceSource(TypedDict):
    label: str
    path: str
    index_path: str
    display_name: str


class ComparisonSource(TypedDict):
    path: str
    index_path: str
    display_name: str
    comparison_key: str
    suggested_offset: int | None
    audio_review: str


class SessionData(TypedDict):
    reference: ReferenceSource
    targets: dict[str, ComparisonSource]
    frame_props_by_label: dict[str, dict[str, str | int]]
    short_names: dict[str, str]
    memory_limit_mb: int | None


class AudioReviewAuthority(TypedDict):
    origin: str
    frame_offset: int | None


class AudioReviewPayload(TypedDict):
    current_authority: AudioReviewAuthority
    audio_attempt: dict[str, object] | None


class _VideoNodeWithFps(Protocol):
    fps: Fraction


class OutputRegistrar(Protocol):
    def __call__(self, clip: vs.VideoNode, index: int, name: str, **metadata: object) -> None: ...


class PreviewSourceLoader(Protocol):
    def LWLibavSource(self, path: str, **kwargs: int | str) -> vs.VideoNode: ...


REVIEW_METADATA_VERSION = ALIGNMENT_REVIEW_METADATA_VERSION
REVIEW_METADATA_KEYS = {
    "version": ALIGNMENT_REVIEW_METADATA_VERSION_KEY,
    "session_id": ALIGNMENT_REVIEW_METADATA_SESSION_ID_KEY,
    "alignment_key": ALIGNMENT_REVIEW_METADATA_ALIGNMENT_KEY,
    "ordinal": ALIGNMENT_REVIEW_METADATA_ORDINAL_KEY,
    "role": ALIGNMENT_REVIEW_METADATA_ROLE_KEY,
    "name": ALIGNMENT_REVIEW_METADATA_NAME_KEY,
    "suggested_offset": ALIGNMENT_REVIEW_METADATA_SUGGESTED_OFFSET_KEY,
    "audio_review": ALIGNMENT_REVIEW_METADATA_AUDIO_REVIEW_KEY,
}


def _workspace_log_filter(record: logging.LogRecord) -> bool:
    return not (record.levelno == logging.INFO and record.msg == "Content loaded successfully: %r")


def install_workspace_log_filter() -> None:
    logger = logging.getLogger("vsview.app.workspace.loader")
    if _workspace_log_filter not in logger.filters:
        logger.addFilter(_workspace_log_filter)


class SessionConsole:
    def __init__(self) -> None:
        self._original_stderr_encoding = getattr(sys.stderr, "encoding", "") or ""
        self.reconfigure_text_stream(sys.stdout)
        self.reconfigure_text_stream(sys.stderr)

    def reconfigure_text_stream(self, stream: TextIO) -> bool:
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            return False
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, LookupError, OSError, TypeError, UnicodeError, ValueError):
            return False
        return True

    def ansi_enabled(self) -> bool:
        return "NO_COLOR" not in os.environ and getattr(sys.stderr, "isatty", lambda: False)()

    def use_ascii(self) -> bool:
        return not str(self._original_stderr_encoding).lower().startswith("utf")

    def glyph(self, kind: str) -> str:
        table = {"warning": ("!", "!"), "failed": ("✗", "x"), "waiting": ("›", ">")}
        glyph, fallback = table[kind]
        return fallback if self.use_ascii() else glyph

    def arrow(self) -> str:
        return "->" if self.use_ascii() else "→"

    def accent_code(self) -> str:
        colorterm = os.environ.get("COLORTERM", "")
        if colorterm in ("truecolor", "24bit") or "WT_SESSION" in os.environ:
            return "38;2;210;172;107"
        if "256color" in os.environ.get("TERM", ""):
            return "38;5;180"
        return "33"

    def style(self, text: str, code: str) -> str:
        if not self.ansi_enabled():
            return text
        return f"\x1b[{code}m{text}\x1b[0m"

    def dim(self, text: str) -> str:
        return self.style(text, "2")

    def header(self, text: str) -> str:
        return self.style(text, self.accent_code())

    def key(self, text: str) -> str:
        return self.style(text, "2")

    def hint(self, text: str) -> str:
        return self.style(text, "2")

    def ascii_fallback(self, text: str) -> str:
        if not self.use_ascii():
            return text
        return text.translate(
            str.maketrans(
                {
                    "╭": "+",
                    "─": "-",
                    "│": "|",
                    "╰": "+",
                    "·": "|",
                    "›": ">",
                    "…": "...",
                    "×": "x",
                    "●": "*",
                    "○": "o",
                }
            )
        )

    def _section_border(self, side: str) -> str:
        if self.use_ascii():
            return "+-" if side in {"top", "bottom"} else "|"
        return {"top": "╭─", "body": "│", "bottom": "╰─"}[side]

    def _section_title(self, text: str) -> str:
        heading, separator, detail = text.partition(" · ")
        title = self.style(self.ascii_fallback(heading), f"{self.accent_code()};1")
        if separator:
            title += self.dim(self.ascii_fallback(separator + detail))
        return title

    def _section_body(self, text: str) -> str:
        text = self.ascii_fallback(text)
        rail = self.style(self._section_border("body"), self.accent_code())
        return rail if not text else f"{rail} {text}"

    def terminal_width(self) -> int:
        return max(1, min(shutil.get_terminal_size(fallback=(120, 24)).columns, 120))

    def _wrap_ansi(self, text: str, width: int) -> list[str]:
        """Fold an ANSI-styled string without counting SGR sequences as width."""
        lines: list[str] = []
        current: list[str] = []
        visible_width = 0
        active_style = ""
        for token_match in re.finditer(r"\x1b\[[0-9;]*m|.", text, re.DOTALL):
            token = token_match.group()
            ansi_match = _ANSI_SGR_RE.fullmatch(token)
            if ansi_match is not None:
                current.append(token)
                active_style = "" if token == "\x1b[0m" else token
                continue
            for character in token:
                if character == "\n":
                    lines.append("".join(current))
                    current = [active_style] if active_style else []
                    visible_width = 0
                    continue
                if visible_width == width:
                    if active_style:
                        current.append("\x1b[0m")
                    lines.append("".join(current))
                    current = [active_style] if active_style else []
                    visible_width = 0
                current.append(character)
                visible_width += 1
        if current or not lines:
            lines.append("".join(current))
        return lines

    def _section_lines(self, line: str | _SectionKeyValue, body_width: int) -> list[str]:
        if isinstance(line, _SectionKeyValue):
            key = self.ascii_fallback(line.key)
            value = self.ascii_fallback(line.value)
            value_width = max(1, body_width - 16)
            value_lines = self._wrap_ansi(value, value_width)
            return [
                f"{key}  {value_lines[0]}",
                *(f"{' ' * 16}{value_line}" for value_line in value_lines[1:]),
            ]
        return self._wrap_ansi(self.ascii_fallback(line), body_width)

    def section(self, title: str, body: Sequence[str | _SectionKeyValue]) -> None:
        """Print one G1 section with the VSView console's ANSI styling."""
        rail_code = self.accent_code()
        body_width = max(1, self.terminal_width() - 2)
        self.safe_print()
        self.safe_print(
            self.style(self._section_border("top") + " ", rail_code) + self._section_title(title)
        )
        for line in body:
            for wrapped_line in self._section_lines(line, body_width):
                self.safe_print(self._section_body(wrapped_line))
        self.safe_print(self.style(self._section_border("bottom"), rail_code))
        self.safe_print()

    def key_value(self, key: str, value: str) -> _SectionKeyValue:
        return _SectionKeyValue(self.key(f"{key:<14}"), value)

    def note(self, kind: str, text: str) -> str:
        glyph = self.glyph(kind)
        code = "33" if kind == "warning" else "2"
        return f"{self.style(glyph, code)} {text}"

    def _audio_output_state(self, audio_review: AudioReviewPayload) -> tuple[str, bool]:
        authority = audio_review["current_authority"]
        origin = authority["origin"]
        offset = authority["frame_offset"]
        attempt = audio_review["audio_attempt"]
        decision_raw = attempt.get("decision") if isinstance(attempt, dict) else None
        decision = cast(dict[str, object], decision_raw) if isinstance(decision_raw, dict) else None
        state = decision.get("state") if decision is not None else None
        candidate_raw = decision.get("candidate") if decision is not None else None
        candidate = (
            cast(dict[str, object], candidate_raw) if isinstance(candidate_raw, dict) else None
        )
        candidate_offset = candidate.get("frame_offset") if candidate is not None else None

        if origin == "computed_this_run" and state == "trusted_automatic" and offset is not None:
            return f"audio {offset:+d}f", False
        if origin == "shared_computed_offsets" and offset is not None:
            return f"audio {offset:+d}f · reused", False
        if (
            origin in {"interactive_confirmed_this_run", "shared_previous_offsets"}
            and offset is not None
        ):
            return f"previously confirmed {offset:+d}f", False
        if origin == "preexisting_manual_override" and offset is not None:
            return f"manual offset {offset:+d}f", False
        if state == "provisional" and isinstance(candidate_offset, int):
            return f"audio {candidate_offset:+d}f · not applied", True
        return "no audio match", True

    def _output_table_rows(
        self,
        reference: ReferenceSource,
        targets: Mapping[str, ComparisonSource],
        short_names: Mapping[str, str],
    ) -> list[_SectionKeyValue]:
        source_names = [short_names.get(reference["label"], reference["display_name"])]
        source_names.extend(
            short_names.get(label, target["display_name"]) for label, target in targets.items()
        )
        name_width = max(map(len, source_names))
        rows = [
            self.key_value(
                "outputs",
                f"0  {source_names[0].ljust(name_width)}  {self.dim('reference')}",
            )
        ]
        for index, ((_label, target), name) in enumerate(
            zip(targets.items(), source_names[1:], strict=True), start=1
        ):
            audio_review = cast(AudioReviewPayload, json.loads(target["audio_review"]))
            state, warning = self._audio_output_state(audio_review)
            state_text = self.style(state, "33") if warning else self.dim(state)
            rows.append(
                self.key_value(
                    "",
                    f"{index}  {name.ljust(name_width)}  {state_text}",
                )
            )
        return rows

    def vsview_section_body(
        self,
        reference: ReferenceSource,
        targets: Mapping[str, ComparisonSource],
        short_names: Mapping[str, str],
        preview_assumptions: list[dict[str, str]],
    ) -> list[str | _SectionKeyValue]:
        body: list[str | _SectionKeyValue] = [
            "1  Open Tool Panel " + self.arrow() + " Frame Compare Alignment Review.",
            "2  Unlink playheads, then position every source on the same visible moment.",
            "3  Save the alignment in the panel, then close VSView to continue Frame Compare.",
            "",
            *self._output_table_rows(reference, targets, short_names),
        ]
        if preview_assumptions:
            body.extend(("", self.note("warning", "VSView display assumptions")))
            for assumption_number, assumption in enumerate(preview_assumptions):
                if assumption_number:
                    body.append("")
                body.append(self.key_value("source", assumption["source"]))
                if "preview" in assumption:
                    body.append(self.key_value("preview", self.hint(assumption["preview"])))
                if "range" in assumption:
                    body.append(self.key_value("range", self.hint(assumption["range"])))
                body.append(
                    self.key_value(
                        "impact",
                        self.hint("Preview only; source, render, and report unchanged"),
                    )
                )
        return body

    def status(self, marker: str) -> str:
        kinds = {"[WARN]": ("warning", "33"), "[FAIL]": ("failed", "31")}
        kind, code = kinds[marker]
        return self.style(self.glyph(kind), code)

    def status_line(self, marker: str, text: str) -> str:
        return f"  {self.status(marker)} {text}"

    def safe_print(self, *args: object) -> None:
        try:
            print(*args, file=sys.stderr)
        except UnicodeEncodeError:
            # Preserve diagnostics on legacy consoles that cannot be reconfigured.
            text = " ".join(str(arg) for arg in args)
            print(text.encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)


def resolve_lwlibavsource(core: vs.Core) -> PreviewSourceLoader:
    if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
        return cast(PreviewSourceLoader, core.lsmas)
    raise RuntimeError("LWLibavSource not found on core.lsmas")


def load_preview_source(
    loader: PreviewSourceLoader,
    path: Path,
    index_path: Path,
    display_name: str,
    console: SessionConsole,
) -> vs.VideoNode:
    try:
        return loader.LWLibavSource(str(path), cachefile=str(index_path))
    except Exception as original_error:
        if INDEX_CONSTRUCTION_FAILURE_MARKER not in str(original_error).casefold():
            raise

        console.safe_print(
            console.status_line(
                "[WARN]",
                f"Retrying {display_name} without an L-SMASH index cache after index construction failed",
            )
        )
        try:
            return loader.LWLibavSource(str(path), cache=0)
        except Exception as fallback_error:
            raise original_error from fallback_error


FRAME_PROP_ALIASES = {
    "_Matrix": ("_Matrix", "Matrix"),
    "_Transfer": ("_Transfer", "Transfer"),
    "_Primaries": ("_Primaries", "Primaries"),
}
UNSPECIFIED_FRAME_PROP = 2


def _parse_frame_prop_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, bytes):
        try:
            value = value.decode("ascii")
        except UnicodeDecodeError:
            return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdecimal():
            return int(stripped)
    return None


def _read_prop(props: Mapping[str, str | int], canonical_key: str) -> str | int:
    for key in FRAME_PROP_ALIASES[canonical_key]:
        if key in props:
            return props[key]
    raise KeyError(canonical_key)


def _range_issue(props: Mapping[str, str | int]) -> str | None:
    if "_Range" not in props:
        return "missing"
    parsed_value = _parse_frame_prop_int(props["_Range"])
    if parsed_value in (0, 1):
        return None
    if parsed_value == UNSPECIFIED_FRAME_PROP:
        return "unspecified"
    return "invalid"


def collect_preview_assumption(
    label: str, display_name: str, frame_props_by_label: Mapping[str, Mapping[str, str | int]]
) -> dict[str, str] | None:
    props = frame_props_by_label.get(label)
    if props is None:
        return None

    color_metadata_incomplete = False
    for key in FRAME_PROP_ALIASES:
        try:
            raw_value = _read_prop(props, key)
        except Exception:
            color_metadata_incomplete = True
            continue

        parsed_value = _parse_frame_prop_int(raw_value)
        if parsed_value is None or parsed_value == UNSPECIFIED_FRAME_PROP:
            color_metadata_incomplete = True

    range_issue = _range_issue(props)
    if not color_metadata_incomplete and range_issue is None:
        return None

    assumption = {"source": display_name}
    if color_metadata_incomplete:
        assumption["preview"] = (
            "Color metadata incomplete; using standard display defaults (BT.709)"
        )
    if range_issue is not None:
        assumption["range"] = f"Color-range metadata {range_issue}; VSView infers preview range"
    return assumption


def apply_preview_defaults(
    core: vs.Core,
    clip: vs.VideoNode,
    label: str,
    frame_props_by_label: Mapping[str, Mapping[str, str | int]],
) -> vs.VideoNode:
    props = frame_props_by_label.get(label)
    if props is None:
        return clip

    defaults: dict[str, int] = {}
    for key in FRAME_PROP_ALIASES:
        try:
            parsed_value = _parse_frame_prop_int(_read_prop(props, key))
        except Exception:
            parsed_value = None
        if parsed_value is None or parsed_value == UNSPECIFIED_FRAME_PROP:
            defaults[key] = 1
    if not defaults:
        return clip
    return core.std.SetFrameProps(clip, **defaults)


def _reference_metadata(session_id: str, reference: ReferenceSource) -> dict[str, str | int]:
    return {
        REVIEW_METADATA_KEYS["version"]: REVIEW_METADATA_VERSION,
        REVIEW_METADATA_KEYS["session_id"]: session_id,
        REVIEW_METADATA_KEYS["role"]: "reference",
        REVIEW_METADATA_KEYS["name"]: reference["display_name"],
    }


def _comparison_metadata(
    session_id: str, target: ComparisonSource, comparison_number: int
) -> dict[str, str | int | None]:
    return {
        REVIEW_METADATA_KEYS["version"]: REVIEW_METADATA_VERSION,
        REVIEW_METADATA_KEYS["session_id"]: session_id,
        REVIEW_METADATA_KEYS["alignment_key"]: target["comparison_key"],
        REVIEW_METADATA_KEYS["ordinal"]: comparison_number,
        REVIEW_METADATA_KEYS["role"]: "comparison",
        REVIEW_METADATA_KEYS["name"]: target["display_name"],
        REVIEW_METADATA_KEYS["suggested_offset"]: target["suggested_offset"],
        REVIEW_METADATA_KEYS["audio_review"]: target["audio_review"],
    }


def run_session(data: SessionData, script_path: Path) -> None:
    console = SessionConsole()
    install_workspace_log_filter()
    reference = data["reference"]
    targets = data["targets"]
    frame_props_by_label = data["frame_props_by_label"]
    short_names = data["short_names"]
    if not targets:
        console.safe_print(
            console.status_line("[FAIL]", "Alignment review requires every comparison")
        )
        sys.exit(1)
    try:
        import vapoursynth as vs
    except ImportError:
        console.safe_print(console.status_line("[FAIL]", "VapourSynth is unavailable"))
        sys.exit(1)
    try:
        from vsview import set_output as native_set_output  # pyright: ignore[reportUnknownVariableType]
    except ImportError:
        console.safe_print(console.status_line("[FAIL]", "VSView output API is unavailable"))
        sys.exit(1)
    set_output = cast(OutputRegistrar, native_set_output)
    core = vs.core
    if data["memory_limit_mb"] is not None:
        core.max_cache_size = data["memory_limit_mb"]
    try:
        load_source = resolve_lwlibavsource(core)
    except RuntimeError as e:
        console.safe_print(
            console.status_line("[FAIL]", f"Failed to resolve LWLibavSource loader: {e}")
        )
        sys.exit(1)

    ref_path = Path(reference["path"])
    if not ref_path.exists():
        console.safe_print(console.status_line("[FAIL]", f"Reference not found: {ref_path}"))
        sys.exit(1)

    try:
        ref_clip = load_preview_source(
            load_source,
            ref_path,
            Path(reference["index_path"]),
            reference["display_name"],
            console,
        )
    except Exception as e:
        console.safe_print(
            console.status_line("[FAIL]", f"Reference source could not be loaded: {e}")
        )
        sys.exit(1)

    ref_fps = cast(_VideoNodeWithFps, ref_clip).fps
    ref_fps_num = ref_fps.numerator
    ref_fps_den = ref_fps.denominator
    preview_assumptions: list[dict[str, str]] = []
    ref_assumption = collect_preview_assumption(
        reference["label"], reference["display_name"], frame_props_by_label
    )
    if ref_assumption is not None:
        preview_assumptions.append(ref_assumption)
    ref_clip = apply_preview_defaults(core, ref_clip, reference["label"], frame_props_by_label)

    try:
        ref_clip = core.text.Text(
            ref_clip,
            f"REF: {reference['display_name']}\n"
            "Open Tool Panel -> Frame Compare Alignment Review.\n"
            "Unlink playheads, then position every source on the same visible moment.",
            alignment=7,
        )
    except Exception:
        console.safe_print(console.status_line("[WARN]", "Could not apply reference text overlay"))

    prepared_comparisons: list[tuple[int, str, ComparisonSource, vs.VideoNode]] = []

    for comparison_number, (label, target) in enumerate(targets.items(), start=1):
        comp_path = Path(target["path"])
        display_name = target["display_name"]
        if not comp_path.exists():
            console.safe_print(
                console.status_line("[FAIL]", f"Comparison source not found: {comp_path}")
            )
            sys.exit(1)

        try:
            comp_clip = load_preview_source(
                load_source,
                comp_path,
                Path(target["index_path"]),
                display_name,
                console,
            )
        except Exception as e:
            console.safe_print(
                console.status_line("[FAIL]", f"Comparison source could not be loaded: {e}")
            )
            sys.exit(1)

        comp_assumption = collect_preview_assumption(label, display_name, frame_props_by_label)
        if comp_assumption is not None:
            preview_assumptions.append(comp_assumption)

        comp_clip = core.std.AssumeFPS(comp_clip, fpsnum=ref_fps_num, fpsden=ref_fps_den)
        comp_clip = apply_preview_defaults(core, comp_clip, label, frame_props_by_label)

        suggested_offset = target["suggested_offset"]
        audio_review = cast(AudioReviewPayload, json.loads(target["audio_review"]))
        audio_attempt = audio_review["audio_attempt"]
        raw_decision = audio_attempt.get("decision") if isinstance(audio_attempt, dict) else None
        try:
            audio_decision = (
                None
                if raw_decision is None
                else evidence_from_payload(AudioAlignmentDecision, raw_decision)
            )
        except ValueError:
            audio_decision = None
        candidate_offset = (
            None
            if audio_decision is None or audio_decision.candidate is None
            else audio_decision.candidate.frame_offset
        )
        audio_attempt_unusable = audio_attempt is not None and (
            audio_decision is None or candidate_offset is None
        )
        authority = audio_review["current_authority"]
        if (
            audio_decision is not None
            and audio_decision.state == "provisional"
            and candidate_offset is not None
        ):
            audio_hint = f"Provisional {candidate_offset:+d}f - NOT APPLIED"
            hint_pair = "Verify manually; this candidate is not a confirmed alignment"
            trim_hint = f"Reason: {audio_decision.primary_reason}"
        elif audio_decision is not None and audio_decision.state == "trusted_automatic":
            accepted_offset = cast(int, suggested_offset)
            audio_hint = f"Audio alignment accepted: {accepted_offset:+d}f"
            hint_pair = (
                "No relative audio correction required"
                if accepted_offset == 0
                else f"Accepted origin pair: REF {max(accepted_offset, 0)} <-> "
                f"CMP {max(-accepted_offset, 0)}"
            )
            trim_hint = "Accepted by the recorded automatic policy"
        elif authority["origin"] in {
            "interactive_confirmed_this_run",
            "shared_previous_offsets",
            "preexisting_manual_override",
        }:
            audio_hint = f"Current alignment: {suggested_offset:+d}f — manually confirmed"
            hint_pair = "Historical audio details unavailable"
            trim_hint = "Manual authority is separate from audio evidence"
        elif audio_attempt_unusable or suggested_offset is None:
            audio_hint = "No usable audio candidate"
            hint_pair = "No automatic correction applied"
            trim_hint = "Enter known offsets or align the sources manually"
        else:
            audio_hint = f"Reused accepted audio alignment: {suggested_offset:+d}f"
            hint_pair = "Historical chunk and selected-stream details unavailable"
            trim_hint = "No audio analysis ran this time"

        try:
            overlay_text = (
                f"CMP: {display_name}\n"
                f"Audio hint: {audio_hint}\n"
                f"{hint_pair}\n"
                f"{trim_hint}\n"
                "Open Tool Panel -> Frame Compare Alignment Review.\n"
                "Unlink playheads, then position every source on the same visible moment."
            )
            comp_clip = core.text.Text(comp_clip, overlay_text, alignment=7)
        except Exception:
            console.safe_print(
                console.status_line("[WARN]", "Could not apply comparison text overlay")
            )

        prepared_comparisons.append((comparison_number, label, target, comp_clip))

    session_id = script_path.stem.rpartition("_")[2]
    try:
        set_output(ref_clip, 0, "Reference", **_reference_metadata(session_id, reference))
        for comparison_number, _label, target, comparison_clip in prepared_comparisons:
            set_output(
                comparison_clip,
                comparison_number,
                f"Comparison {comparison_number}",
                **_comparison_metadata(session_id, target, comparison_number),
            )
    except Exception as e:
        console.safe_print(
            console.status_line("[FAIL]", f"Alignment review outputs could not be registered: {e}")
        )
        sys.exit(1)

    console.section(
        f"{console.glyph('waiting')} VSView is open · waiting for you",
        console.vsview_section_body(reference, targets, short_names, preview_assumptions),
    )
