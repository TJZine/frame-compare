"""Runtime data structures and CLI helpers shared between Click wiring and the runner."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Protocol,
    Tuple,
    TypedDict,
    TypeVar,
    cast,
)

from rich.console import Console
from rich.markup import escape
from rich.progress import Progress, ProgressColumn

from src.cli_layout import CliLayoutError, CliLayoutRenderer, load_cli_layout

if TYPE_CHECKING:  # pragma: no cover
    from src.datatypes import AppConfig


def _color_text(text: str, style: Optional[str]) -> str:
    """
    Wrap the given text with a Rich style tag if a style is provided.

    Parameters:
        text (str): The text to style.
        style (Optional[str]): A Rich style name or markup; if ``None`` or empty, no styling is applied.

    Returns:
        str: The input text wrapped with Rich style markup (for example ``"[style]text[/]"``) when ``style`` is provided; otherwise
            the original text.
    """
    if style:
        return f"[{style}]{text}[/]"
    return text


def _format_kv(
    label: str,
    value: object,
    *,
    label_style: Optional[str] = "dim",
    value_style: Optional[str] = "bright_white",
    sep: str = "=",
) -> str:
    """
    Format a label/value pair as a single string with optional Rich styling.

    Parameters:
        label (str): The left-side label text.
        value (object): The right-side value; converted to string.
        label_style (Optional[str]): Rich style name applied to the label, or ``None`` for no styling.
        value_style (Optional[str]): Rich style name applied to the value, or ``None`` for no styling.
        sep (str): Separator string placed between label and value.

    Returns:
        str: A single string containing the styled (or plain) label, the separator, and the styled (or plain) value.
    """
    label_text = escape(str(label))
    value_text = escape(str(value))
    return f"{_color_text(label_text, label_style)}{sep}{_color_text(value_text, value_style)}"


@dataclass
class _ClipPlan:
    """
    Internal plan describing how a source clip should be processed.

    Attributes:
        path (Path): Path to the source media file.
        metadata (Dict[str, str]): Metadata parsed from the source file name.
        trim_start (int): Leading frames to skip before analysis.
        trim_end (Optional[int]): Final frame index (exclusive) or ``None`` to include the full clip.
        fps_override (Optional[Tuple[int, int]]): Rational frame-rate override applied during processing.
        use_as_reference (bool): Whether the clip should drive alignment decisions.
        clip (Optional[object]): Lazily populated VapourSynth clip reference.
        effective_fps (Optional[Tuple[int, int]]): Frame rate after alignment adjustments.
        applied_fps (Optional[Tuple[int, int]]): Frame rate enforced by user configuration.
        source_fps (Optional[Tuple[int, int]]): Native frame rate detected from the source file.
        source_num_frames (Optional[int]): Total number of frames available in the source clip.
        source_width (Optional[int]): Source clip width in pixels.
        source_height (Optional[int]): Source clip height in pixels.
        has_trim_start_override (bool): ``True`` when a manual trim start was supplied.
        has_trim_end_override (bool): ``True`` when a manual trim end was supplied.
        alignment_frames (int): Number of frames trimmed during audio alignment.
        alignment_status (str): Human-friendly status describing the alignment result.
    """

    path: Path
    metadata: Dict[str, str]
    trim_start: int = 0
    trim_end: Optional[int] = None
    fps_override: Optional[Tuple[int, int]] = None
    use_as_reference: bool = False
    clip: Optional[object] = None
    effective_fps: Optional[Tuple[int, int]] = None
    applied_fps: Optional[Tuple[int, int]] = None
    source_fps: Optional[Tuple[int, int]] = None
    source_num_frames: Optional[int] = None
    source_width: Optional[int] = None
    source_height: Optional[int] = None
    has_trim_start_override: bool = False
    has_trim_end_override: bool = False
    alignment_frames: int = 0
    alignment_status: str = ""


def _plan_label(plan: _ClipPlan) -> str:
    """
    Determine a user-facing label for a clip plan using metadata fallbacks.
    """

    metadata = plan.metadata
    for key in ("label", "title", "anime_title", "file_name"):
        value = metadata.get(key)
        if value:
            text = str(value).strip()
            if text:
                return text
    return plan.path.name


def _normalise_vspreview_mode(raw: object) -> str:
    """Return a canonical VSPreview mode label (``baseline`` or ``seeded``)."""

    text = str(raw or "baseline").strip().lower()
    return "seeded" if text == "seeded" else "baseline"


_OverrideValue = TypeVar("_OverrideValue")


class SlowpicsTitleInputs(TypedDict):
    resolved_base: Optional[str]
    collection_name: Optional[str]
    collection_suffix: str


class SlowpicsTitleBlock(TypedDict):
    inputs: SlowpicsTitleInputs
    final: Optional[str]


class SlowpicsJSON(TypedDict):
    enabled: bool
    title: SlowpicsTitleBlock
    url: Optional[str]
    shortcut_path: Optional[str]
    deleted_screens_dir: bool
    is_public: bool
    is_hentai: bool
    remove_after_days: int


class AudioAlignmentJSON(TypedDict, total=False):
    enabled: bool
    reference_stream: Optional[str]
    target_stream: dict[str, object]
    offsets_sec: dict[str, object]
    offsets_frames: dict[str, object]
    measurements: dict[str, dict[str, object]]
    stream_lines: list[str]
    stream_lines_text: str
    offset_lines: list[str]
    offset_lines_text: str
    preview_paths: list[str]
    confirmed: bool | str | None
    offsets_filename: str
    use_vspreview: bool
    vspreview_manual_offsets: dict[str, object]
    vspreview_manual_deltas: dict[str, object]
    vspreview_reference_trim: Optional[int]
    manual_trim_summary: list[str]
    suggestion_mode: bool
    suggested_frames: dict[str, int]
    manual_trim_starts: dict[str, int]
    vspreview_script: Optional[str]
    vspreview_invoked: bool
    vspreview_exit_code: Optional[int]


class TrimClipEntry(TypedDict):
    lead_f: int
    trail_f: int
    lead_s: float
    trail_s: float


class TrimsJSON(TypedDict):
    per_clip: dict[str, TrimClipEntry]


class ReportJSON(TypedDict, total=False):
    enabled: bool
    path: Optional[str]
    output_dir: str
    open_after_generate: bool
    opened: bool
    mode: str


class ViewerJSON(TypedDict, total=False):
    mode: str
    mode_display: str
    destination: Optional[str]
    destination_label: str


class JsonTail(TypedDict):
    clips: list[dict[str, object]]
    trims: TrimsJSON
    window: dict[str, object]
    alignment: dict[str, object]
    audio_alignment: AudioAlignmentJSON
    analysis: dict[str, object]
    render: dict[str, object]
    tonemap: dict[str, object]
    overlay: dict[str, object]
    verify: dict[str, object]
    cache: dict[str, object]
    slowpics: SlowpicsJSON
    report: ReportJSON
    viewer: ViewerJSON
    warnings: list[str]
    workspace: dict[str, object]
    vspreview_mode: Optional[str]
    suggested_frames: int
    suggested_seconds: float
    vspreview_offer: Optional[dict[str, object]]


class ClipRecord(TypedDict):
    label: str
    width: int
    height: int
    fps: float
    frames: int
    duration: float
    duration_tc: str
    path: str


class TrimSummary(TypedDict):
    label: str
    lead_frames: int
    lead_seconds: float
    trail_frames: int
    trail_seconds: float


def _coerce_str_mapping(value: object) -> dict[str, object]:
    """Return a shallow copy of *value* if it is a mapping with string-like keys."""

    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            key_str = key if isinstance(key, str) else str(key)
            result[key_str] = item
        return result
    return {}


def _ensure_audio_alignment_block(json_tail: JsonTail) -> AudioAlignmentJSON:
    """Ensure the audio alignment block exists and return a mutable mapping."""

    block = json_tail.get("audio_alignment")
    if isinstance(block, dict):
        return cast(AudioAlignmentJSON, block)
    new_block = cast(AudioAlignmentJSON, {})
    json_tail["audio_alignment"] = new_block
    return new_block


def _ensure_slowpics_block(json_tail: JsonTail, cfg: "AppConfig") -> SlowpicsJSON:
    """Ensure that ``json_tail`` contains a slow.pics block and return it."""

    block = json_tail.get("slowpics")
    if not isinstance(block, dict):
        block = SlowpicsJSON(
            enabled=bool(cfg.slowpics.auto_upload),
            title=SlowpicsTitleBlock(
                inputs=SlowpicsTitleInputs(
                    resolved_base=None,
                    collection_name=None,
                    collection_suffix=getattr(cfg.slowpics, "collection_suffix", ""),
                ),
                final=None,
            ),
            url=None,
            shortcut_path=None,
            deleted_screens_dir=False,
            is_public=bool(cfg.slowpics.is_public),
            is_hentai=bool(cfg.slowpics.is_hentai),
            remove_after_days=int(cfg.slowpics.remove_after_days),
        )
        json_tail["slowpics"] = block
    else:
        block = cast(SlowpicsJSON, block)
        if "url" not in block:
            block["url"] = None
        if "shortcut_path" not in block:
            block["shortcut_path"] = None
        if "deleted_screens_dir" not in block:
            block["deleted_screens_dir"] = False
    return cast(SlowpicsJSON, block)


class CLIAppError(RuntimeError):
    """Raised when the CLI cannot complete its work."""

    def __init__(self, message: str, *, code: int = 1, rich_message: Optional[str] = None) -> None:
        super().__init__(message)
        self.code = code
        self.rich_message = rich_message or message


from src.frame_compare import alignment_runner as _alignment_runner_module  # noqa: E402

_AudioAlignmentSummary = _alignment_runner_module._AudioAlignmentSummary
_AudioMeasurementDetail = _alignment_runner_module._AudioMeasurementDetail
_AudioAlignmentDisplayData = _alignment_runner_module._AudioAlignmentDisplayData


class CliOutputManagerProtocol(Protocol):
    quiet: bool
    verbose: bool
    console: Console
    flags: Dict[str, Any]
    values: Dict[str, Any]

    def set_flag(self, key: str, value: Any) -> None: ...

    def update_values(self, mapping: Mapping[str, Any]) -> None: ...

    def warn(self, text: str) -> None: ...

    def get_warnings(self) -> List[str]: ...

    def render_sections(self, section_ids: Iterable[str]) -> None: ...

    def create_progress(self, progress_id: str, *, transient: bool = False) -> Progress: ...

    def update_progress_state(self, progress_id: str, **state: Any) -> None: ...

    def banner(self, text: str) -> None: ...

    def section(self, title: str) -> None: ...

    def line(self, text: str) -> None: ...

    def verbose_line(self, text: str) -> None: ...

    def progress(self, *columns: ProgressColumn, transient: bool = False) -> Progress: ...

    def iter_warnings(self) -> List[str]: ...


class CliOutputManager:
    """Layout-driven CLI presentation controller."""

    def __init__(
        self,
        *,
        quiet: bool,
        verbose: bool,
        no_color: bool,
        layout_path: Path,
        console: Console | None = None,
    ) -> None:
        self.quiet = quiet
        self.verbose = verbose and not quiet
        self.no_color = no_color
        self.console = console or Console(no_color=no_color, highlight=False)
        try:
            self.layout = load_cli_layout(layout_path)
        except CliLayoutError as exc:
            raise CLIAppError(str(exc)) from exc
        self.renderer = CliLayoutRenderer(
            self.layout,
            self.console,
            quiet=quiet,
            verbose=self.verbose,
            no_color=no_color,
        )
        self.flags: Dict[str, Any] = {
            "quiet": quiet,
            "verbose": self.verbose,
            "no_color": no_color,
        }
        self.values: Dict[str, Any] = {
            "theme": {
                "colors": dict(self.layout.theme.colors),
                "symbols": dict(self.renderer.symbols),
            }
        }
        self._warnings: List[str] = []

    def set_flag(self, key: str, value: Any) -> None:
        self.flags[key] = value

    def update_values(self, mapping: Mapping[str, Any]) -> None:
        self.values.update(mapping)

    def warn(self, text: str) -> None:
        self._warnings.append(text)

    def get_warnings(self) -> List[str]:
        return list(self._warnings)

    def render_sections(self, section_ids: Iterable[str]) -> None:
        target_ids = set(section_ids)
        self.renderer.bind_context(self.values, self.flags)
        for section in self.layout.sections:
            section_id = section.get("id")
            if section_id in target_ids:
                self.renderer.render_section(section, self.values, self.flags)

    def create_progress(self, progress_id: str, *, transient: bool = False) -> Progress:
        self.renderer.bind_context(self.values, self.flags)
        return self.renderer.create_progress(progress_id, transient=transient)

    def update_progress_state(self, progress_id: str, **state: Any) -> None:
        self.renderer.update_progress_state(progress_id, state=state)

    def banner(self, text: str) -> None:
        if self.quiet:
            self.console.print(text)
            return
        self.console.print(f"[bold bright_cyan]{escape(text)}[/]")

    def section(self, title: str) -> None:
        if self.quiet:
            return
        self.console.print(f"[bold cyan]{title}[/]")

    def line(self, text: str) -> None:
        if self.quiet:
            return
        self.console.print(text)

    def verbose_line(self, text: str) -> None:
        if self.quiet or not self.verbose:
            return
        if not text:
            return
        self.console.print(f"[dim]{escape(text)}[/]")

    def progress(self, *columns: ProgressColumn, transient: bool = False) -> Progress:
        return Progress(*columns, console=self.console, transient=transient)

    def iter_warnings(self) -> List[str]:
        return list(self._warnings)


class NullCliOutputManager(CliOutputManagerProtocol):
    """
    Minimal CliOutputManager implementation that discards console output.

    Used by automation callers (or quiet runs) that want to suppress Rich layout
    rendering while still collecting warnings and JSON-tail metadata.
    """

    def __init__(
        self,
        *,
        quiet: bool,
        verbose: bool,
        no_color: bool,
        layout_path: Path | None = None,
        console: Console | None = None,
    ) -> None:
        self.quiet = True
        self.verbose = False
        self.no_color = no_color
        self.console = console or Console(
            file=io.StringIO(),
            no_color=True,
            highlight=False,
            force_terminal=False,
            width=80,
        )
        self.layout = None
        self.flags: Dict[str, Any] = {
            "quiet": True,
            "verbose": False,
            "no_color": no_color,
        }
        self.values: Dict[str, Any] = {}
        self._warnings: List[str] = []

    def set_flag(self, key: str, value: Any) -> None:
        self.flags[key] = value

    def update_values(self, mapping: Mapping[str, Any]) -> None:
        self.values.update(mapping)

    def warn(self, text: str) -> None:
        self._warnings.append(text)

    def get_warnings(self) -> List[str]:
        return list(self._warnings)

    def render_sections(self, section_ids: Iterable[str]) -> None:  # noqa: ARG002
        return None

    def create_progress(self, progress_id: str, *, transient: bool = False) -> Progress:  # noqa: ARG002
        return Progress(console=self.console, transient=transient)

    def update_progress_state(self, progress_id: str, **state: Any) -> None:  # noqa: ARG002
        return None

    def banner(self, text: str) -> None:  # noqa: ARG002
        return None

    def section(self, title: str) -> None:  # noqa: ARG002
        return None

    def line(self, text: str) -> None:  # noqa: ARG002
        return None

    def verbose_line(self, text: str) -> None:  # noqa: ARG002
        return None

    def progress(self, *columns: ProgressColumn, transient: bool = False) -> Progress:
        return Progress(*columns, console=self.console, transient=transient)

    def iter_warnings(self) -> List[str]:
        return list(self._warnings)


__all__ = [
    "CLIAppError",
    "CliOutputManager",
    "CliOutputManagerProtocol",
    "NullCliOutputManager",
    "JsonTail",
    "SlowpicsJSON",
    "SlowpicsTitleBlock",
    "SlowpicsTitleInputs",
    "ViewerJSON",
    "_AudioAlignmentDisplayData",
    "_AudioAlignmentSummary",
    "_AudioMeasurementDetail",
    "_ClipPlan",
    "_coerce_str_mapping",
    "_color_text",
    "_ensure_audio_alignment_block",
    "_ensure_slowpics_block",
    "_format_kv",
    "_normalise_vspreview_mode",
    "_plan_label",
    "AudioAlignmentJSON",
    "ClipRecord",
    "ReportJSON",
    "TrimClipEntry",
    "TrimSummary",
    "TrimsJSON",
]
