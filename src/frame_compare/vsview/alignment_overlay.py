"""Immutable source identity and original-frame labels, composed on the native frame being requested.

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

from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewReferenceMetadata,
    AlignmentReviewWorkspaceMetadata,
)
from frame_compare.vsview.alignment_selection import OpeningHint, opening_hint, project_frame

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
    "Match each row to the video’s Original frame number. "
    "Panel hints refer to the pinned anchor; video hints follow the viewed frame."
)
_PREDICTION_HEADER = "Predicted for this frame (opening hints)"


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


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
class OpeningSource:
    role: str
    name: str
    count: int
    hint: OpeningHint

    @property
    def heading(self) -> str:
        return f"{self.role} - {self.name}"


@dataclass(frozen=True, slots=True)
class LaunchOverlay:
    role: Role
    name: str
    own_count: int
    ordinal: int = 0
    hint: OpeningHint = OpeningHint(0)
    peers: tuple[OpeningSource, ...] = ()

    def __post_init__(self) -> None:
        if self.role not in ("REF", "CMP") or not _integer(self.own_count) or self.own_count <= 0:
            raise ValueError("invalid overlay source")
        if self.role == "CMP" and (not _integer(self.ordinal) or self.ordinal <= 0):
            raise ValueError("comparison overlay requires its source ordinal")

    @property
    def heading(self) -> str:
        role = "REF" if self.role == "REF" else f"CMP {self.ordinal}"
        return f"{role} - {self.name}"

    def validate_frame(self, n: int) -> None:
        if not _integer(n) or not 0 <= n < self.own_count:
            raise ValueError("original frame is outside the source")

    def live_lines(self, n: int) -> tuple[str, ...]:
        self.validate_frame(n)
        lines = [self.heading, f"Original frame {n:,}"]
        if self.peers:
            lines.append(_PREDICTION_HEADER)
            for peer in self.peers:
                projected = project_frame(n, self.hint, peer.hint, peer.count)
                value = f"{projected.frame:,}" if projected.frame is not None else projected.status
                if projected.provisional:
                    value += " (provisional)"
                lines.append(f"{peer.heading}: {value}")
        return tuple(lines)

    def static_lines(self) -> tuple[str, ...]:
        return (
            self.heading,
            "Static labels - live hints unavailable",
            "Panel shows pinned-anchor hints",
        )


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
    facts = {
        source.output_id: OpeningSource(
            roles[source.output_id],
            names[source.output_id],
            source.source_frame_count,
            OpeningHint(0)
            if isinstance(source, AlignmentReviewReferenceMetadata)
            else opening_hint(source),
        )
        for source in sources
    }
    return {
        source.output_id: LaunchOverlay(
            "REF" if isinstance(source, AlignmentReviewReferenceMetadata) else "CMP",
            names[source.output_id],
            source.source_frame_count,
            0
            if isinstance(source, AlignmentReviewReferenceMetadata)
            else source.comparison_ordinal,
            facts[source.output_id].hint,
            tuple(fact for output, fact in facts.items() if output != source.output_id),
        )
        for source in sources
    }


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
class _PeerRow:
    source: OpeningSource
    y: int
    x: int
    inline: bool
    unavailable: _Raster
    outside: _Raster
    provisional: _Raster | None


@dataclass(frozen=True, slots=True)
class _LiveLayout:
    base: _Raster
    number_y: int
    number_x: int
    glyphs: Mapping[str, _Raster]
    advances: Mapping[str, int]
    model: LaunchOverlay
    peers: tuple[_PeerRow, ...] = ()

    def render(self, n: int) -> _Raster:

        self.model.validate_frame(n)
        fg, coverage = self.base.foreground.copy(), self.base.coverage.copy()
        self._digits(fg, coverage, n, self.number_x, self.number_y)
        for row in self.peers:
            projected = project_frame(n, self.model.hint, row.source.hint, row.source.count)
            if projected.frame is None:
                mask = row.unavailable if projected.status == "unavailable" else row.outside
                self._stamp(fg, coverage, mask, row.x if row.inline else 0, row.y)
            else:
                end = self._digits(fg, coverage, projected.frame, row.x, row.y)
                if projected.provisional and row.provisional is not None:
                    self._stamp(
                        fg,
                        coverage,
                        row.provisional,
                        end + 4 if row.inline else 0,
                        row.y if row.inline else row.y + self.glyphs["0"].foreground.shape[0],
                    )
        return _Raster(fg, coverage)

    @staticmethod
    def _stamp(fg: Mask, coverage: Mask, mask: _Raster, x: int, y: int) -> None:
        import numpy as np

        h, w = mask.foreground.shape
        for target, stamp in ((fg, mask.foreground), (coverage, mask.coverage)):
            np.maximum(target[y : y + h, x : x + w], stamp, out=target[y : y + h, x : x + w])

    def _digits(self, fg: Mask, coverage: Mask, number: int, x: int, y: int) -> int:
        for char in f"{number:,}":
            self._stamp(fg, coverage, self.glyphs[char], x, y)
            x += self.advances[char]
        return x


def _live_layout(model: LaunchOverlay, font: Font, width: int, height: int) -> _LiveLayout:
    import numpy as np

    advances = {c: ceil(font.getlength(c)) for c in "0123456789,"}
    cell = max(advances.values())
    glyphs = {c: _raster((c,), font, cell + 4, height) for c in "0123456789,"}
    reserve = len(f"{model.own_count - 1:,}") * cell + 4
    if reserve >= width:
        raise ValueError("frame number cannot fit")
    lines = _wrap(model.heading, font, width - 4)
    prefix = "Original frame"
    x = ceil(font.getlength(prefix)) + 6
    if x + reserve > width:
        lines.extend(_wrap(prefix, font, width - 4))
        prefix, x = "", 2
    number_line = len(lines)
    lines.append(prefix)
    bbox = font.getbbox("Ag09")
    step = ceil(bbox[3] - bbox[1]) + 7
    rows: list[_PeerRow] = []
    if model.peers:
        lines.extend(_wrap(_PREDICTION_HEADER, font, width - 4))
        for peer in model.peers:
            if len(f"{peer.count - 1:,}") * cell + 6 > width:
                raise ValueError("complete predicted number cannot fit")
            unavailable = _raster(("unavailable",), font, width, height)
            outside = _raster(("outside source range",), font, width, height)
            provisional = (
                _raster(("(provisional)",), font, width, height)
                if model.hint.provisional or peer.hint.provisional
                else None
            )
            prefix = f"{peer.heading}:"
            number_x = ceil(font.getlength(prefix)) + 6
            numeric_extent = len(f"{peer.count - 1:,}") * cell + 4
            suffix_extent = 4 + provisional.foreground.shape[1] if provisional else 0
            # Every complete alternative must fit on one physical row; otherwise
            # retain the wrapped block for this entire peer, never a truncated value.
            inline = (
                number_x
                + max(
                    numeric_extent + suffix_extent,
                    ceil(font.getlength("unavailable")) + 4,
                    ceil(font.getlength("outside source range")) + 4,
                )
                <= width
            )
            if inline:
                y = len(lines) * step
                lines.append(prefix)
            else:
                lines.extend(_wrap(peer.heading, font, width - 4))
                number_x = 2
                y = len(lines) * step
                extent = max(
                    unavailable.foreground.shape[0],
                    outside.foreground.shape[0],
                    step + (provisional.foreground.shape[0] if provisional else 0),
                )
                lines.extend([""] * ceil(extent / step))
            rows.append(_PeerRow(peer, y, number_x, inline, unavailable, outside, provisional))
    base = _raster(tuple(line or " " for line in lines), font, width, height)
    required_width = max(
        base.foreground.shape[1],
        x + reserve,
        *(
            max(
                row.x
                + len(f"{row.source.count - 1:,}") * cell
                + 4
                + (
                    4 + row.provisional.foreground.shape[1] if row.inline and row.provisional else 0
                ),
                (row.x if row.inline else 0) + row.unavailable.foreground.shape[1],
                (row.x if row.inline else 0) + row.outside.foreground.shape[1],
                row.provisional.foreground.shape[1] if row.provisional else 0,
            )
            for row in rows
        ),
    )
    if required_width > base.foreground.shape[1]:
        padding = ((0, 0), (0, required_width - base.foreground.shape[1]))
        fg, coverage = np.pad(base.foreground, padding), np.pad(base.coverage, padding)
        fg.setflags(write=False)
        coverage.setflags(write=False)
        base = _Raster(fg, coverage)
    bbox = font.getbbox("Ag09")
    y = number_line * (ceil(bbox[3] - bbox[1]) + 7)
    if y + glyphs["0"].foreground.shape[0] > base.foreground.shape[0]:
        raise ValueError("digit row cannot fit")
    return _LiveLayout(
        base, y, x, MappingProxyType(glyphs), MappingProxyType(advances), model, tuple(rows)
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
            else "Live alignment video labels unavailable; using static labels; live hints unavailable. Panel shows pinned-anchor hints."
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
