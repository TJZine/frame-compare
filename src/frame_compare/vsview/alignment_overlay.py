"""Immutable session-open guidance, composed on the native frame being requested.

Only owned composition is recoverable here. Source acquisition precedes the selector;
native validation after its return is outside this boundary. Imports used for native
painting/font setup stay lazy so importing session data does not load media libraries.
"""

from __future__ import annotations

import sys
import threading
import traceback
import unicodedata
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Protocol, cast

from frame_compare.vsview.alignment_review_contract import AlignmentReviewWorkspaceMetadata

if TYPE_CHECKING:
    import numpy as np
    import vapoursynth as vs
    from numpy.typing import NDArray
    from PIL import ImageFont

type Mask = NDArray[np.uint8]
type Font = ImageFont.FreeTypeFont | ImageFont.ImageFont
type Role = Literal["REF", "CMP"]
type Plane = NDArray[np.uint8 | np.uint16 | np.float16 | np.float32]


class _CopyableFrame(Protocol):
    # The repository's minimal VS stub omits this public native method.
    def copy(self) -> vs.VideoFrame: ...


PANEL_LABEL_EXPLANATION = (
    "Video labels use the alignment evidence from session open. Suggested frames are "
    "calculated from the frame shown; they do not show or move the other playhead. "
    "Saved choices and current status are shown here. The preview remains untrimmed."
)
_STATUS = "Saved choices/status: Alignment Review panel"
_UNAVAILABLE = "No alignment suggestion at session open"


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def suggested_frame(
    n: int, own_count: int, other_count: int, offset: int | None, *, role: Role
) -> int | None:
    """Map original source coordinates; never clamp or apply base trims."""
    if (
        role not in ("REF", "CMP")
        or not _integer(n)
        or not _integer(own_count)
        or not 0 <= n < own_count
    ):
        raise ValueError("original frame is outside the source")
    if not _integer(other_count) or other_count <= 0:
        raise ValueError("other source frame count must be positive")
    if offset is None:
        return None
    if not _integer(offset):
        raise ValueError("alignment offset must be an integer or unavailable")
    target = n + offset if role == "CMP" else n - offset
    return target if 0 <= target < other_count else None


def _cells(text: str) -> int:
    return sum(
        0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in "WF" else 1
        for c in text
    )


def _bounded_name(text: str, suffix: str = "") -> str:
    text = " ".join(
        "".join(" " if unicodedata.category(c).startswith("C") else c for c in text).split()
    )
    text = unicodedata.normalize("NFC", text) or "Source"
    budget = 24 - _cells(suffix)
    result = ""
    for c in text:
        if len(result) >= 96:
            break
        if _cells(result + c) > budget:
            break
        result += c
    return result.rstrip() + suffix


@dataclass(frozen=True, slots=True)
class LaunchPair:
    comparison_key: str
    ordinal: int
    other_name: str
    other_count: int
    offset: int | None
    classification: str

    def __post_init__(self) -> None:
        if not self.comparison_key or not _integer(self.ordinal) or self.ordinal <= 0:
            raise ValueError("invalid alignment pair identity")
        if not _integer(self.other_count) or self.other_count <= 0:
            raise ValueError("invalid alignment pair frame count")
        if self.offset is not None and not _integer(self.offset):
            raise ValueError("invalid alignment pair offset")

    @property
    def unavailable_line(self) -> str:
        return f"Offset unavailable at session open for {self.other_name} - match manually"


@dataclass(frozen=True, slots=True)
class LaunchOverlay:
    role: Role
    name: str
    own_count: int
    pairs: tuple[LaunchPair, ...]
    ordinal: int = 0

    def __post_init__(self) -> None:
        if self.role not in ("REF", "CMP") or not _integer(self.own_count) or self.own_count <= 0:
            raise ValueError("invalid overlay source")
        if self.role == "CMP" and (
            len(self.pairs) != 1
            or not _integer(self.ordinal)
            or self.ordinal <= 0
            or self.ordinal != self.pairs[0].ordinal
        ):
            raise ValueError("comparison overlay requires its own pair")

    @property
    def heading(self) -> str:
        role = "REF" if self.role == "REF" else f"CMP {self.ordinal}"
        return f"{role} - {self.name}"

    @property
    def visible_pairs(self) -> tuple[LaunchPair, ...]:
        return self.pairs[:2] if self.role == "REF" else self.pairs

    def target(self, n: int, pair: LaunchPair) -> int | None:
        return suggested_frame(n, self.own_count, pair.other_count, pair.offset, role=self.role)

    def live_lines(self, n: int) -> tuple[str, ...]:
        suggested_frame(n, self.own_count, self.own_count, 0, role=self.role)
        lines = [self.heading, f"Original frame {n:,}"]
        for pair in self.visible_pairs:
            target = self.target(n, pair)
            lines.append(
                f"Suggested match in {pair.other_name}: {target:,}"
                if target is not None
                else f"No overlap at this frame in {pair.other_name}"
                if pair.offset is not None
                else pair.unavailable_line
            )
            lines.append(pair.classification)
        return (*lines, *self.overflow_lines(), _STATUS)

    def overflow_lines(self) -> tuple[str, ...]:
        count = len(self.pairs) - len(self.visible_pairs)
        return (f"+{count:,} more comparisons - see Alignment Review",) if count else ()

    def static_lines(self) -> tuple[str, ...]:
        lines = [self.heading]
        for pair in self.visible_pairs:
            if pair.offset is None:
                lines.append(pair.unavailable_line)
            elif pair.offset == 0:
                lines.append(f"Same original frame numbers in {self.name} and {pair.other_name}")
            else:
                amount = abs(pair.offset)
                higher = (pair.offset > 0) == (self.role == "REF")
                direction = "higher" if higher else "lower"
                lines.extend(
                    (
                        f"Offset amount at session open: {amount:,} original frames",
                        f"Matching {self.name} frame numbers are {amount:,} {direction} "
                        f"than {pair.other_name}",
                    )
                )
            lines.append(pair.classification)
        return (*lines, *self.overflow_lines(), f"Static labels - {_STATUS.lower()}")


def build_launch_overlays(
    workspace: AlignmentReviewWorkspaceMetadata, short_names: Mapping[int, str]
) -> dict[int, LaunchOverlay]:
    """Consume the existing strict workspace model; never infer identity from names."""
    sources = (workspace.reference, *workspace.comparisons)
    names = {
        s.output_id: _bounded_name(short_names.get(s.output_id, s.presentation_name))
        for s in sources
    }
    collisions = {name for name in names.values() if list(names.values()).count(name) > 1}
    for source in sources:
        if names[source.output_id] in collisions:
            suffix = (
                " (REF)"
                if source.output_id == workspace.reference.output_id
                else f" (CMP {next(c.comparison_ordinal for c in workspace.comparisons if c.output_id == source.output_id)})"
            )
            names[source.output_id] = _bounded_name(names[source.output_id], suffix)
    # A supplied name may itself equal a generated disambiguation. Resolve such
    # second-order collisions with stable source roles, never shortened identity.
    roles = {workspace.reference.output_id: "REF"}
    roles.update({c.output_id: f"CMP {c.comparison_ordinal}" for c in workspace.comparisons})
    while len(set(names.values())) < len(names):
        repeated = {name for name in names.values() if list(names.values()).count(name) > 1}
        names = {key: roles[key] if name in repeated else name for key, name in names.items()}
    ref = workspace.reference
    ref_pairs: list[LaunchPair] = []
    result: dict[int, LaunchOverlay] = {}
    for comparison in workspace.comparisons:
        authority = comparison.audio_review.current_authority
        offset = authority.frame_offset
        if offset is not None:
            if authority.origin == "computed_this_run":
                classification = "Accepted audio alignment at session open"
            elif authority.origin == "shared_computed_offsets":
                classification = "Reused audio alignment at session open"
            else:
                classification = "Manually confirmed alignment at session open"
                if authority.origin == "shared_previous_offsets":
                    classification = "Reused manually confirmed alignment at session open"
        else:
            classification = _UNAVAILABLE
            attempt = comparison.audio_review.audio_attempt
            if attempt is not None and attempt.decision.state == "provisional":
                candidate = attempt.decision.candidate
                if candidate is not None:
                    offset = candidate.frame_offset
                    classification = "Provisional audio suggestion at session open"
        ref_pairs.append(
            LaunchPair(
                other_name=names[comparison.output_id],
                other_count=comparison.source_frame_count,
                comparison_key=comparison.comparison_key,
                ordinal=comparison.comparison_ordinal,
                offset=offset,
                classification=classification,
            )
        )
        pair = LaunchPair(
            other_name=names[ref.output_id],
            other_count=ref.source_frame_count,
            comparison_key=comparison.comparison_key,
            ordinal=comparison.comparison_ordinal,
            offset=offset,
            classification=classification,
        )
        result[comparison.output_id] = LaunchOverlay(
            "CMP",
            names[comparison.output_id],
            comparison.source_frame_count,
            (pair,),
            comparison.comparison_ordinal,
        )
    result[ref.output_id] = LaunchOverlay(
        "REF", names[ref.output_id], ref.source_frame_count, tuple(ref_pairs)
    )
    return result


@dataclass(frozen=True, slots=True)
class _Raster:
    foreground: Mask
    coverage: Mask
    x: int = 10
    y: int = 10


def _font(height: int) -> Font:
    from PIL import ImageFont

    size = max(10, min(48, round(height * 20 / 720)))
    try:
        return ImageFont.truetype(
            str(Path(__file__).resolve().parent.parent / "assets/fonts/Inter-Regular.ttf"), size
        )
    except OSError:
        return ImageFont.load_default(size=size)


def _wrap(text: str, font: Font, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if font.getlength(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = ""
        for char in word:
            if font.getlength(current + char) > width:
                if not current:
                    raise ValueError("label cannot fit at readable size")
                lines.append(current)
                current = ""
            current += char
    return [*lines, current] if current else lines


def _raster(lines: tuple[str, ...], font: Font, width: int, height: int) -> _Raster:
    import numpy as np
    from PIL import Image, ImageDraw

    wrapped = [part for line in lines for part in (_wrap(line, font, width - 4) or [""])]
    bbox = font.getbbox("Ag09")
    step = ceil(bbox[3] - bbox[1]) + 7
    used_height = step * len(wrapped)
    if width <= 4 or used_height > height:
        raise ValueError("labels cannot fit at readable size")
    foreground = Image.new("L", (width, used_height))
    coverage = Image.new("L", (width, used_height))
    fg_draw, stroke_draw = ImageDraw.Draw(foreground), ImageDraw.Draw(coverage)
    for i, text in enumerate(wrapped):
        xy = (2, 2 + i * step - bbox[1])
        fg_draw.text(xy, text, font=font, fill=255)
        stroke_draw.text(xy, text, font=font, fill=255, stroke_width=2, stroke_fill=255)
    fg, stroke = np.array(foreground), np.array(coverage)
    # Layout wraps against the available source width, but painting need only
    # touch actual ink. Copy the trimmed buffers so setup retains no wide backing
    # canvas. Live layout adds its reserved numeric/alternate extents separately.
    columns = np.flatnonzero(np.any(stroke, axis=0))
    used_width = int(columns[-1]) + 1 if len(columns) else 1
    fg, stroke = fg[:, :used_width].copy(), stroke[:, :used_width].copy()
    fg.setflags(write=False)
    stroke.setflags(write=False)
    return _Raster(fg, stroke)


@dataclass(frozen=True, slots=True)
class _NumberRow:
    y: int
    x: int
    pair: LaunchPair | None
    no_overlap: _Raster | None


@dataclass(frozen=True, slots=True)
class _LiveLayout:
    base: _Raster
    rows: tuple[_NumberRow, ...]
    glyphs: Mapping[str, _Raster]
    advances: Mapping[str, int]
    cell: int
    model: LaunchOverlay

    def render(self, n: int) -> _Raster:
        import numpy as np

        # Validates n independently of the engine's current request admission.
        suggested_frame(n, self.model.own_count, self.model.own_count, 0, role=self.model.role)
        fg, coverage = self.base.foreground.copy(), self.base.coverage.copy()
        for row in self.rows:
            value = n if row.pair is None else self.model.target(n, row.pair)
            if value is None:
                assert row.no_overlap is not None
                stamp = row.no_overlap
                h, w = stamp.foreground.shape
                fg[row.y : row.y + h] = 0
                coverage[row.y : row.y + h] = 0
                fg[row.y : row.y + h, :w] = stamp.foreground
                coverage[row.y : row.y + h, :w] = stamp.coverage
                continue
            x = row.x
            for char in f"{value:,}":
                glyph = self.glyphs[char]
                h, w = glyph.foreground.shape
                np.maximum(
                    fg[row.y : row.y + h, x : x + w],
                    glyph.foreground,
                    out=fg[row.y : row.y + h, x : x + w],
                )
                np.maximum(
                    coverage[row.y : row.y + h, x : x + w],
                    glyph.coverage,
                    out=coverage[row.y : row.y + h, x : x + w],
                )
                x += self.advances[char]
        return _Raster(fg, coverage)


def _live_layout(model: LaunchOverlay, font: Font, width: int, height: int) -> _LiveLayout:
    # Finite glyph advances preserve readable comma-grouped numbers without any
    # font calls in the selector. Stroke margins may overlap adjacent glyph cells.
    advances = {c: ceil(font.getlength(c)) for c in "0123456789,"}
    cell = max(advances.values())
    glyphs = {c: _raster((c,), font, cell + 4, height) for c in "0123456789,"}
    row_height = glyphs["0"].foreground.shape[0]
    lines = [model.heading]
    slots: list[tuple[int, int, LaunchPair | None, _Raster | None]] = []
    reserved_rights: list[int] = []

    def number_line(prefix: str, count: int, pair: LaunchPair | None) -> None:
        # Put numbers on their own line if a named prefix needs wrapping.
        reserve = len(f"{count - 1:,}") * cell + 4
        if reserve >= width:
            raise ValueError("frame number cannot fit")
        wrapped = _wrap(prefix, font, width - 4)
        lines.extend(wrapped[:-1])
        tail = wrapped[-1]
        x = int(font.getlength(tail) + 6)
        if x + reserve > width:
            lines.append(tail)
            tail, x = "", 2
        index = len(lines)
        lines.append(tail)
        replacement = None
        if pair is not None:
            replacement = _raster(
                (f"No overlap at this frame in {pair.other_name}",), font, width, height
            )
            if replacement.foreground.shape[0] > row_height:
                raise ValueError("no-overlap guidance cannot fit its row")
        slots.append((index, x, pair, replacement))
        reserved_rights.append(x + reserve)
        if replacement is not None:
            reserved_rights.append(replacement.foreground.shape[1])

    number_line("Original frame", model.own_count, None)
    for pair in model.visible_pairs:
        if pair.offset is None:
            lines.append(pair.unavailable_line)
        else:
            number_line(f"Suggested match in {pair.other_name}:", pair.other_count, pair)
        lines.append(pair.classification)
    lines.extend((*model.overflow_lines(), _STATUS))
    # _raster wraps general lines; account for that before translating slot line indices.
    wrapped_lines: list[str] = []
    positions: dict[int, int] = {}
    for i, line in enumerate(lines):
        positions[i] = len(wrapped_lines)
        wrapped_lines.extend(_wrap(line, font, width - 4) if line else [""])
    base = _raster(tuple(line or " " for line in wrapped_lines), font, width, height)
    required_width = max(base.foreground.shape[1], *reserved_rights)
    if required_width > base.foreground.shape[1]:
        import numpy as np

        padding = ((0, 0), (0, required_width - base.foreground.shape[1]))
        fg, coverage = np.pad(base.foreground, padding), np.pad(base.coverage, padding)
        fg.setflags(write=False)
        coverage.setflags(write=False)
        base = _Raster(fg, coverage)
    bbox = font.getbbox("Ag09")
    step = ceil(bbox[3] - bbox[1]) + 7
    rows = tuple(
        _NumberRow(positions[i] * step, x, pair, replacement) for i, x, pair, replacement in slots
    )
    if any(row.y + row_height > base.foreground.shape[0] for row in rows):
        raise ValueError("digit row cannot fit")
    return _LiveLayout(
        base, rows, MappingProxyType(glyphs), MappingProxyType(advances), cell, model
    )


def _paint(frame: vs.VideoFrame, raster: _Raster) -> vs.VideoFrame:
    import numpy as np
    import vapoursynth as vs

    out = cast(_CopyableFrame, frame).copy()
    fmt = out.format
    # The rectangular ROI includes transparent letter interiors/spacing. Gather
    # only covered samples: this preserves the same float32 operation order while
    # avoiding full-rectangle conversion, blending and masked copy-back.
    rows, columns = np.nonzero(raster.coverage)
    fg = raster.foreground[rows, columns].astype(np.float32) / 255
    coverage = raster.coverage[rows, columns].astype(np.float32) / 255
    luma_rows, luma_columns = rows + raster.y, columns + raster.x
    chroma_samples = None
    if fmt.color_family == vs.YUV and fmt.num_planes > 1:
        sx, sy = 1 << fmt.subsampling_w, 1 << fmt.subsampling_h
        left, top = raster.x % sx, raster.y % sy
        h, w = raster.coverage.shape
        # The two chroma planes share coverage. Max on uint8 is exact before the
        # monotone float conversion; strided elementwise maxima avoid the costly
        # general reduction over interleaved (row, column) block axes.
        padding = ((top, (-top - h) % sy), (left, (-left - w) % sx))
        expanded = (
            np.pad(raster.coverage, padding) if any(a or b for a, b in padding) else raster.coverage
        )
        reduced = expanded[::sy, ::sx].copy()
        for dy in range(sy):
            for dx in range(sx):
                if dx or dy:
                    np.maximum(reduced, expanded[dy::sy, dx::sx], out=reduced)
        rows, columns = np.nonzero(reduced)
        chroma_samples = (
            rows + (raster.y // sy),
            columns + (raster.x // sx),
            reduced[rows, columns].astype(np.float32) / 255,
        )
    for p in range(fmt.num_planes):
        a = cast("Plane", np.asarray(out[p]))
        chroma = fmt.color_family == vs.YUV and p > 0
        if chroma:
            assert chroma_samples is not None
            rows, columns, alpha = chroma_samples
            neutral = 0.0 if fmt.sample_type == vs.FLOAT else float(1 << (fmt.bits_per_sample - 1))
            view = a[rows, columns]
            values = view.astype(np.float32) * (1 - alpha) + neutral * alpha
        else:
            alpha = coverage
            rows, columns = luma_rows, luma_columns
            view = a[rows, columns]
            # Match R81 native Text's numeric convention, without changing source props/range.
            black = 0.0 if fmt.sample_type == vs.FLOAT else float(16 << (fmt.bits_per_sample - 8))
            white = 1.0 if fmt.sample_type == vs.FLOAT else float(235 << (fmt.bits_per_sample - 8))
            values = view.astype(np.float32) * (1 - alpha) + black * alpha
            values = values * (1 - fg) + white * fg
        if fmt.sample_type == vs.INTEGER:
            values = np.rint(values)
        a[rows, columns] = values.astype(a.dtype)
        del view, a, values
    return out


def _discard_failure(failure: Exception) -> None:
    """Clear unwound frame/array locals, including chained exceptions, before fallback."""
    seen: set[int] = set()
    pending: list[BaseException] = [failure]
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        pending.extend(e for e in (item.__cause__, item.__context__) if e is not None)
        if item.__traceback__ is not None:
            traceback.clear_frames(item.__traceback__)
        item.__traceback__ = None
        item.__cause__ = item.__context__ = None


class _Renderer:
    def __init__(
        self, static: _Raster, live: _LiveLayout | None, warn: Callable[[str], None]
    ) -> None:
        self.static, self.live, self.warn = static, live, warn
        self._lock = threading.Lock()
        self._failed_live = live is None
        self._warned: set[str] = set()

    def warning(self, kind: str) -> None:
        with self._lock:
            if kind in self._warned:
                return
            self._warned.add(kind)
        message = (
            "Alignment video labels unavailable; using raw preview and Alignment Review panel."
            if kind == "raw"
            else "Live alignment video labels unavailable; using static session-open labels."
        )
        # Diagnostics are never a reason to fail an already acquired video frame.
        with suppress(Exception):
            self.warn(message)

    def _attempt(self, frame: vs.VideoFrame, n: int, *, live: bool) -> vs.VideoFrame | None:
        try:
            raster = self.live.render(n) if live and self.live is not None else self.static
            return _paint(frame, raster)
        except Exception as failure:
            # This scope owns ONLY layout/mask/copy/blend. No source acquisition or
            # engine validation occurs here. The helper returns before static starts.
            _discard_failure(failure)
            return None

    def __call__(self, n: int, f: vs.VideoFrame) -> vs.VideoFrame:
        with self._lock:
            try_live = not self._failed_live
        if try_live:
            result = self._attempt(f, n, live=True)
            if result is not None:
                return result
            with self._lock:
                self._failed_live = True
        result = self._attempt(f, n, live=False)
        if result is not None:
            if try_live:
                self.warning("static")
            return result
        self.warning("raw")
        return f


def _stderr_warning(message: str) -> None:
    sys.stderr.write(f"[WARN] {message}\n")


def apply_alignment_overlay(
    core: vs.Core,
    clip: vs.VideoNode,
    model: LaunchOverlay,
    *,
    warn: Callable[[str], None] = _stderr_warning,
) -> vs.VideoNode:
    """Prepare independent static resources first, then one source-local selector."""
    import vapoursynth as vs

    try:
        fmt = cast("vs.VideoFormat | None", clip.format)
        if (
            fmt is None
            or (fmt.color_family not in (vs.RGB, vs.YUV) and fmt.num_planes != 1)
            or (fmt.sample_type == vs.INTEGER and not 8 <= fmt.bits_per_sample <= 16)
            or (fmt.sample_type == vs.FLOAT and fmt.bits_per_sample not in (16, 32))
            or clip.num_frames != model.own_count
        ):
            raise ValueError("unsupported native overlay format/source")
        font = _font(clip.height)
        width, height = clip.width - 20, clip.height - 20
        static = _raster(model.static_lines(), font, width, height)
    except Exception as failure:
        _discard_failure(failure)
        with suppress(Exception):
            warn(
                "Alignment video labels unsupported; using raw preview and Alignment Review panel."
            )
        return clip
    try:
        live = _live_layout(model, font, width, height)
    except Exception as failure:
        _discard_failure(failure)
        live = None
    renderer = _Renderer(static, live, warn)
    if live is None:
        renderer.warning("static")
    try:
        return core.std.ModifyFrame(clip, clip, renderer)
    except Exception as failure:
        _discard_failure(failure)
        renderer.warning("raw")
        return clip
