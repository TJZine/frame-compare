"""Executable owner for generated VSView sessions; native imports stay at launch."""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Mapping
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
    """Per-session stream setup and presentation without mutable module state."""

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

    def header(self, text: str) -> str:
        return self.style(text, self.accent_code())

    def key(self, text: str) -> str:
        return self.style(text, "2")

    def value(self, text: str) -> str:
        return text

    def hint(self, text: str) -> str:
        return self.style(text, "2")

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
    """Resolve LWLibavSource from the VapourSynth R81 core.lsmas namespace."""
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


# ─── Main ─────────────────────────────────────────────────────────────────────
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
    """Load all sources before registering the native review workspace outputs."""
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

    # Apply overlay to reference (best-effort)
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
    ready_hints: list[tuple[str, str]] = []

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

        # FPS harmonization: apply AssumeFPS to match reference
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
            # U4 video-confirm seam: U3 decisions never reach trusted_automatic.
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

        ready_hints.append((label, audio_hint))

        # Apply comparison identity, hint, and review guidance (best-effort)
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

    if preview_assumptions:
        console.safe_print("\n" + console.status_line("[WARN]", "VSView Display Assumptions"))
        for assumption_number, assumption in enumerate(preview_assumptions):
            if assumption_number:
                console.safe_print()
            console.safe_print(
                f"    {console.key('source')}      {console.value(assumption['source'])}"
            )
            if "preview" in assumption:
                console.safe_print(
                    f"    {console.key('preview')}     {console.hint(assumption['preview'])}"
                )
            if "range" in assumption:
                console.safe_print(
                    f"    {console.key('range')}       {console.hint(assumption['range'])}"
                )
            console.safe_print(
                f"    {console.key('impact')}      "
                f"{console.hint('Preview only; source, render, and report unchanged')}"
            )

    ready_prefix = "\n" if preview_assumptions else ""
    console.safe_print(
        ready_prefix
        + console.header(f"{console.glyph('waiting')} VSView is open \u00b7 waiting for you")
    )
    console.safe_print(
        "  1  Open Tool Panel " + console.arrow() + " Frame Compare Alignment Review."
    )
    console.safe_print(
        "  2  Unlink playheads, then position every source on the same visible moment."
    )
    console.safe_print(
        "  3  Save the alignment in the panel, then close VSView to continue Frame Compare."
    )
    console.safe_print("")
    console.safe_print("  outputs  0  " + reference["display_name"])
    for comparison_number, _label, target, _comparison_clip in prepared_comparisons:
        console.safe_print("           " + str(comparison_number) + "  " + target["display_name"])
    ready_hint_rows: list[tuple[str, str]] = []
    for label, audio_hint in ready_hints:
        ready_hint_rows.append((short_names.get(label, targets[label]["display_name"]), audio_hint))
    if ready_hint_rows:
        hint_width = max(len(name) for name, _hint_text in ready_hint_rows)
        first_hint_name, first_hint_text = ready_hint_rows[0]
        console.safe_print(
            "  hints    " + first_hint_name.ljust(hint_width) + "  " + first_hint_text
        )
        for hint_name, hint_text in ready_hint_rows[1:]:
            console.safe_print("           " + hint_name.ljust(hint_width) + "  " + hint_text)
