from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, Protocol, TextIO, TypedDict, cast

from pydantic import TypeAdapter

from frame_compare.vs.source import INDEX_CONSTRUCTION_FAILURE_MARKER
from frame_compare.vs.types import TonemapSettings
from frame_compare.vsview.alignment_overlay import apply_alignment_overlay, build_launch_overlays
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
    AlignmentReviewContractError,
    AlignmentReviewOutputCandidate,
    parse_alignment_review_workspace_metadata,
)

if TYPE_CHECKING:
    import vapoursynth as vs


_ANSI_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")


def _cell_width(text: str) -> int:
    """Measure terminal cells using only the VSView runtime's standard library."""
    return sum(
        0
        if unicodedata.category(character) in {"Mn", "Me", "Cf"}
        else 2
        if unicodedata.east_asian_width(character) in {"W", "F"}
        else 1
        for character in text
    )


def _pad_cells(text: str, width: int) -> str:
    return text + " " * max(0, width - _cell_width(text))


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
    preview_tonemap: NotRequired[dict[str, object] | None]


class AudioReviewAuthority(TypedDict):
    origin: str
    frame_offset: int | None


class AudioReviewPayload(TypedDict):
    current_authority: AudioReviewAuthority
    audio_attempt: dict[str, object] | None


class _VideoNodeWithFps(Protocol):
    fps: Fraction


class OutputRegistrar(Protocol):
    def __call__(
        self, clip: vs.VideoNode, index: int, name: str, *, hdr: bool, **metadata: object
    ) -> None: ...


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
                character_width = _cell_width(character)
                if character_width and visible_width + character_width > width and visible_width:
                    if active_style:
                        current.append("\x1b[0m")
                    lines.append("".join(current))
                    current = [active_style] if active_style else []
                    visible_width = 0
                current.append(character)
                visible_width += character_width
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
        return _SectionKeyValue(self.key(_pad_cells(key, 14)), value)

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
        name_width = max(map(_cell_width, source_names))
        rows = [
            self.key_value(
                "outputs",
                f"0  {_pad_cells(source_names[0], name_width)}  {self.dim('reference')}",
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
                    f"{index}  {_pad_cells(name, name_width)}  {state_text}",
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
            "2  Choose any source/Original frame as anchor; select matching numbers in the panel.",
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


def prepare_preview_clip(
    core: vs.Core,
    clip: vs.VideoNode,
    path: Path,
    label: str,
    display_name: str,
    frame_props_by_label: Mapping[str, Mapping[str, str | int]],
    settings: TonemapSettings | None,
) -> tuple[vs.VideoNode, dict[str, str] | None]:
    """Map original HDR evidence before any preview assumptions or overlays."""
    if settings is not None and settings.enabled:
        from frame_compare.vs.hdr_probe import probe_hdr_metadata
        from frame_compare.vs.props import detect_hdr, hdr_signal_is_unspecified
        from frame_compare.vs.tonemap import apply_tonemap

        props = dict(clip.get_frame(0).props)
        metadata = probe_hdr_metadata(path) if hdr_signal_is_unspecified(props) else None
        is_hdr, metadata = detect_hdr(props, metadata)
        if is_hdr:
            return apply_tonemap(clip, settings, metadata, still_image=False).clip, None
    return (
        apply_preview_defaults(core, clip, label, frame_props_by_label),
        collect_preview_assumption(label, display_name, frame_props_by_label),
    )


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
    raw_tonemap = data.get("preview_tonemap")
    preview_tonemap = (
        TypeAdapter(TonemapSettings).validate_python(raw_tonemap)
        if raw_tonemap is not None
        else None
    )
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
    ref_clip, ref_assumption = prepare_preview_clip(
        core,
        ref_clip,
        ref_path,
        reference["label"],
        reference["display_name"],
        frame_props_by_label,
        preview_tonemap,
    )
    if ref_assumption is not None:
        preview_assumptions.append(ref_assumption)

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

        comp_clip, comp_assumption = prepare_preview_clip(
            core, comp_clip, comp_path, label, display_name, frame_props_by_label, preview_tonemap
        )
        if comp_assumption is not None:
            preview_assumptions.append(comp_assumption)

        comp_clip = core.std.AssumeFPS(comp_clip, fpsnum=ref_fps_num, fpsden=ref_fps_den)

        prepared_comparisons.append((comparison_number, label, target, comp_clip))

    session_id = script_path.stem.rpartition("_")[2]
    # Parse the same metadata-v5 workspace the panel will consume, with actual
    # untrimmed frame counts, before deriving immutable display-only launch facts.
    candidates = (
        AlignmentReviewOutputCandidate(
            0, ref_clip.num_frames, _reference_metadata(session_id, reference)
        ),
        *(
            AlignmentReviewOutputCandidate(
                number, clip.num_frames, _comparison_metadata(session_id, target, number)
            )
            for number, _label, target, clip in prepared_comparisons
        ),
    )
    try:
        workspace = parse_alignment_review_workspace_metadata(candidates)
        names = {0: data["short_names"].get(reference["label"], reference["display_name"])}
        names.update(
            {
                number: data["short_names"].get(label, target["display_name"])
                for number, label, target, _clip in prepared_comparisons
            }
        )
        models = build_launch_overlays(workspace, names)
    except (AlignmentReviewContractError, ValueError):
        models = {}
        console.safe_print(
            console.status_line(
                "[WARN]",
                "Alignment video labels unavailable: invalid session evidence; using raw preview.",
            )
        )

    def overlay_warning(message: str) -> None:
        console.safe_print(console.status_line("[WARN]", message))

    if models:
        ref_clip = apply_alignment_overlay(core, ref_clip, models[0], warn=overlay_warning)
        prepared_comparisons = [
            (
                number,
                label,
                target,
                apply_alignment_overlay(core, clip, models[number], warn=overlay_warning),
            )
            for number, label, target, clip in prepared_comparisons
        ]
    try:
        set_output(
            ref_clip, 0, "Reference", hdr=False, **_reference_metadata(session_id, reference)
        )
        for comparison_number, _label, target, comparison_clip in prepared_comparisons:
            set_output(
                comparison_clip,
                comparison_number,
                f"Comparison {comparison_number}",
                hdr=False,
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
