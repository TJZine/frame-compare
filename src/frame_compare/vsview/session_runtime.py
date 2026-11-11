from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from collections.abc import Mapping
from contextlib import suppress
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NotRequired, Protocol, TextIO, TypedDict, cast

from pydantic import TypeAdapter
from rich.cells import cell_len
from rich.color import Color
from rich.text import Text

from frame_compare.utils.cancellation import raise_if_cancelling
from frame_compare.utils.canvas import validate_canvas_size
from frame_compare.utils.terminal_sections import Section
from frame_compare.utils.terminal_theme import (
    ACCENT,
    FAIL,
    GLYPHS_ASCII,
    MUTED,
    WARN,
    glyphs_for_console,
    human_console,
)
from frame_compare.vs.source_admission import SourceAdmission, admit_source, bounded_decoder_options
from frame_compare.vs.source_index_cache import ManagedSourceIndexCache, private_index_directory
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


class ReferenceSource(TypedDict):
    label: str
    path: str
    managed_index_path: NotRequired[str]
    display_name: str


class ComparisonSource(TypedDict):
    path: str
    managed_index_path: NotRequired[str]
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
    source_index_generated_root: NotRequired[str]


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
        self._reconfigure_text_stream(sys.stdout, encoding="utf-8")
        # Keep the terminal's encoding so Rich selects the correct rail glyphs.
        self._reconfigure_text_stream(sys.stderr)
        width, height = shutil.get_terminal_size(fallback=(120, 24))
        self._accent = WARN
        color_system: Literal["standard", "256", "truecolor"] | None = None
        if "NO_COLOR" not in os.environ and sys.stderr.isatty():
            if os.environ.get("COLORTERM") in ("truecolor", "24bit") or "WT_SESSION" in os.environ:
                color_system = "truecolor"
                # Rich caches ANSI codes by style. Reserve the RGB spelling for
                # truecolor so it cannot reuse the shared hex style's downgrade.
                self._accent = Color.parse(ACCENT).get_truecolor().rgb
            elif "256color" in os.environ.get("TERM", ""):
                color_system, self._accent = "256", "color(180)"
            else:
                color_system = "standard"
        self._console = human_console(
            stderr=True,
            color_system=color_system,
            width=width,
            height=height,
        )
        self._glyphs = glyphs_for_console(self._console)

    @staticmethod
    def _reconfigure_text_stream(stream: TextIO, *, encoding: str | None = None) -> None:
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with suppress(
                AttributeError, LookupError, OSError, TypeError, UnicodeError, ValueError
            ):
                reconfigure(encoding=encoding, errors="replace")

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

    def _add_output_rows(
        self,
        section: Section,
        reference: ReferenceSource,
        targets: Mapping[str, ComparisonSource],
        short_names: Mapping[str, str],
    ) -> None:
        source_names = [short_names.get(reference["label"], reference["display_name"])]
        source_names.extend(
            short_names.get(label, target["display_name"]) for label, target in targets.items()
        )
        name_width = max(map(cell_len, source_names))
        ref_name = source_names[0]
        ref_padding = " " * (name_width - cell_len(ref_name) + 2)
        section.add_row(
            "outputs",
            Text.assemble(f"0  {ref_name}{ref_padding}", ("reference", MUTED)),
        )
        for index, (name, target) in enumerate(
            zip(source_names[1:], targets.values(), strict=True), start=1
        ):
            audio_review = cast(AudioReviewPayload, json.loads(target["audio_review"]))
            state, warning = self._audio_output_state(audio_review)
            if self._glyphs is GLYPHS_ASCII:
                state = state.replace(" · ", " | ")
            padding = " " * (name_width - cell_len(name) + 2)
            section.add_row(
                "",
                Text.assemble(f"{index}  {name}{padding}", (state, WARN if warning else MUTED)),
            )

    def print_ready(
        self,
        reference: ReferenceSource,
        targets: Mapping[str, ComparisonSource],
        short_names: Mapping[str, str],
        preview_assumptions: list[dict[str, str]],
    ) -> None:
        ascii_only = self._glyphs is GLYPHS_ASCII
        arrow = "->" if ascii_only else "→"
        separator = "|" if ascii_only else "·"
        title = f"[bold {self._accent}]{self._glyphs.waiting} VSView is open[/]"
        section = Section(f"{title} [dim]{separator} waiting for you[/]", rail_style=self._accent)
        section.add_line(Text(f"1  Open Tool Panel {arrow} Frame Compare Alignment Review."))
        section.add_line(
            Text(
                "2  Browse each source to the same visual moment; original frames update automatically."
            )
        )
        section.add_line(
            Text(
                "3  Confirm matching frames in the panel, then close VSView to continue Frame Compare."
            )
        )
        section.add_row("")
        self._add_output_rows(section, reference, targets, short_names)
        if preview_assumptions:
            section.add_row("")
            section.add_note("VSView display assumptions")
            for assumption_number, assumption in enumerate(preview_assumptions):
                if assumption_number:
                    section.add_row("")
                section.add_row("source", Text(assumption["source"]))
                if "preview" in assumption:
                    section.add_row("preview", Text(assumption["preview"], style=MUTED))
                if "range" in assumption:
                    section.add_row("range", Text(assumption["range"], style=MUTED))
                section.add_row(
                    "impact",
                    Text("Preview only; source, render, and report unchanged", style=MUTED),
                )
        self.safe_print(section)

    def status_line(self, marker: str, text: str) -> Text:
        glyph, style = {
            "[WARN]": (self._glyphs.warning, WARN),
            "[FAIL]": (self._glyphs.failed, FAIL),
        }[marker]
        return Text.assemble("  ", (glyph, style), " ", text)

    def safe_print(self, renderable: Section | Text) -> None:
        with self._console.capture() as capture:
            if isinstance(renderable, Section):
                renderable.print(self._console)
            else:
                self._console.print(renderable, soft_wrap=True)
        text = capture.get()
        try:
            sys.stderr.write(text)
        except UnicodeEncodeError:
            # Preserve diagnostics on legacy consoles that cannot be reconfigured.
            sys.stderr.write(text.encode("ascii", errors="replace").decode("ascii"))


def resolve_lwlibavsource(core: vs.Core) -> PreviewSourceLoader:
    if hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource"):
        return cast(PreviewSourceLoader, core.lsmas)
    raise RuntimeError("LWLibavSource not found on core.lsmas")


def load_preview_source(
    loader: PreviewSourceLoader,
    path: Path,
    managed_index_path: str | None,
    source_index_generated_root: str | None = None,
) -> tuple[vs.VideoNode, SourceAdmission]:
    if path.suffix.lower() == ".lwi":
        raise ValueError("An L-SMASH index cannot be used as source media")
    admission = admit_source(path, abort_check=raise_if_cancelling)
    ff_options = bounded_decoder_options()

    def open_source(source: Path, mode: int, index: Path) -> vs.VideoNode:
        if source.suffix.lower() == ".lwi":
            raise ValueError("An L-SMASH index cannot be used as source media")
        admission.verify(source)
        clip = loader.LWLibavSource(
            str(source), cache=mode, cachefile=str(index), ff_options=ff_options
        )
        admission.verify(source)
        return clip

    if managed_index_path is not None and source_index_generated_root is not None:
        cache = ManagedSourceIndexCache(Path(source_index_generated_root))
        clip = cache.try_open_validated(
            path, Path(managed_index_path), open_source, admission=admission
        )
        if clip is not None:
            return clip, admission
    admission.scan(path, abort_check=raise_if_cancelling)
    with private_index_directory() as directory:
        return open_source(path, 0, directory / "disabled.lwi"), admission


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
    *,
    admission: SourceAdmission,
) -> tuple[vs.VideoNode, dict[str, str] | None]:
    """Map original HDR evidence before any preview assumptions or overlays."""
    if settings is not None and settings.enabled:
        from frame_compare.vs.hdr_probe import probe_hdr_metadata
        from frame_compare.vs.props import detect_hdr, hdr_signal_is_unspecified
        from frame_compare.vs.tonemap import apply_tonemap

        props = dict(clip.get_frame(0).props)
        metadata = None
        if hdr_signal_is_unspecified(props):
            metadata = probe_hdr_metadata(path, streams=(admission.video_stream,))
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
        ref_clip, ref_admission = load_preview_source(
            load_source,
            ref_path,
            reference.get("managed_index_path"),
            data.get("source_index_generated_root"),
        )
        validate_canvas_size(ref_clip.width, ref_clip.height, label="Source video")
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
        admission=ref_admission,
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
            comp_clip, comp_admission = load_preview_source(
                load_source,
                comp_path,
                target.get("managed_index_path"),
                data.get("source_index_generated_root"),
            )
            validate_canvas_size(comp_clip.width, comp_clip.height, label="Source video")
        except Exception as e:
            console.safe_print(
                console.status_line("[FAIL]", f"Comparison source could not be loaded: {e}")
            )
            sys.exit(1)

        comp_clip, comp_assumption = prepare_preview_clip(
            core,
            comp_clip,
            comp_path,
            label,
            display_name,
            frame_props_by_label,
            preview_tonemap,
            admission=comp_admission,
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

    console.print_ready(reference, targets, short_names, preview_assumptions)
