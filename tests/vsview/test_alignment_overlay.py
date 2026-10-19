from __future__ import annotations

import concurrent.futures
import gc
import json
import sys
import threading
import time
import types
import weakref
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest

from frame_compare.vsview import alignment_overlay as overlay
from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewAudioReview,
    AlignmentReviewComparisonMetadata,
    AlignmentReviewCurrentAuthority,
    AlignmentReviewReferenceMetadata,
    AlignmentReviewWorkspaceMetadata,
)
from tests.alignment_review_test_support import audio_review, provisional_audio_attempt


def model(*, offset: int | None = 504, role: overlay.Role = "CMP", count: int = 8):
    del offset  # Older native failure fixtures vary offsets; labels now contain only identity/n.
    return overlay.LaunchOverlay(
        role, "FoRM1080p" if role == "CMP" else "MainFrame4K", count, 1 if role == "CMP" else 0
    )


@pytest.mark.parametrize("n", [True, -1, 8, 1.2])
def test_invalid_original_frames_are_rejected(n):
    with pytest.raises(ValueError):
        model().live_lines(n)


def test_native_label_copy_is_source_and_number_only():
    m = model(count=20000)
    assert m.live_lines(10490) == (
        "CMP 1 - FoRM1080p",
        "Original frame 10,490",
        "Select frame numbers in Alignment Review",
    )
    static = "\n".join(m.static_lines())
    assert "FoRM1080p" in static and "Static labels" in static
    assert "Original frame " not in static and "Suggested" not in static and "504" not in static


def test_workspace_authority_precedence_identity_names_and_mixed_reference():
    reviews = (
        AlignmentReviewAudioReview(
            AlignmentReviewCurrentAuthority("preexisting_manual_override", 0),
            "current_attempt",
            provisional_audio_attempt(ordinal=1, frame_offset=504),
        ),
        AlignmentReviewAudioReview(
            AlignmentReviewCurrentAuthority("none", None),
            "current_attempt",
            provisional_audio_attempt(ordinal=2, frame_offset=-504),
        ),
        AlignmentReviewAudioReview(
            AlignmentReviewCurrentAuthority("shared_computed_offsets", 504),
            "historical_details_unavailable",
            None,
        ),
    )
    workspace = AlignmentReviewWorkspaceMetadata(
        "a" * 32,
        AlignmentReviewReferenceMetadata(0, 20_000, "a" * 32, "REF full name"),
        tuple(
            AlignmentReviewComparisonMetadata(
                100 + i,
                20_000 - i,
                "a" * 32,
                f"key-{i}",
                i,
                "Full comparison name",
                r.current_authority.frame_offset,
                r,
            )
            for i, r in enumerate(reviews, 1)
        ),
    )
    names = {0: "\n日本語\x00" * 20, 101: "\n日本語\x00" * 20, 102: "same", 103: "same"}
    models = overlay.build_launch_overlays(workspace, names)
    assert len({m.name for m in models.values()}) == 4
    assert all(
        overlay._cells(m.name) <= 24 and "\n" not in m.name and "\0" not in m.name
        for m in models.values()
    )
    assert "CMP 1" in models[101].name and "REF" in models[0].name
    assert models[101].ordinal == 1 and models[102].own_count == 19998
    assert names[101].startswith("\n")
    tricky = overlay.build_launch_overlays(
        workspace, {0: "Reference", 101: "Same", 102: "Same", 103: "Same (CMP 1)"}
    )
    assert len({m.name for m in tricky.values()}) == 4


def native():
    # Native cases report a capability skip explicitly on hosts without VapourSynth.
    return pytest.importorskip("vapoursynth")


def frame_arrays(f):
    return [np.asarray(f[p]).copy() for p in range(f.format.num_planes)]


def assert_pixels(f, expected):
    assert all(np.array_equal(np.asarray(f[p]), a) for p, a in enumerate(expected))


def coded_source(vs, *, delay=False, source_error=False):
    raw = vs.core.std.BlankClip(
        width=642,
        height=240,
        format=vs.RGB24,
        length=8,
        color=[33, 45, 57],
        fpsnum=24000,
        fpsden=1001,
    )

    def code(n, f):
        if source_error and n == 6:
            raise RuntimeError("SOURCE_ERROR_OVERLAY_UNIQUE")
        if delay and n == 2:
            time.sleep(0.02)
        out = f.copy()
        for p in range(3):
            a = np.asarray(out[p])
            for bit in range(3):
                a[220:230, bit * 16 : (bit + 1) * 16] = 200 if n & (1 << bit) else 20
            del a
        out.props["SourceIndex"] = n
        out.props["Sentinel"] = "immutable"
        return out

    return vs.core.std.ModifyFrame(raw, raw, code)


def test_concrete_identity_pixels_and_cached_requests(monkeypatch):
    vs = native()
    source = coded_source(vs)
    layouts = []
    prepare = overlay._live_layout

    def capture_layout(*args):
        result = prepare(*args)
        layouts.append(result)
        return result

    monkeypatch.setattr(overlay, "_live_layout", capture_layout)
    node = overlay.apply_alignment_overlay(vs.core, source, model())
    assert node is not source
    for n in (0, 1, 5, 2, 5, 7):
        raw = source.get_frame(n)
        before = frame_arrays(raw)
        f = node.get_frame(n)
        assert dict(f.props) == dict(raw.props) and f.props["SourceIndex"] == n
        assert (node.fps_num, node.fps_den) == (source.fps_num, source.fps_den)
        assert node.num_frames == 8 and f.format.id == vs.RGB24
        a = np.asarray(f[0])
        assert sum(1 << b for b in range(3) if a[222, b * 16] == 200) == n
        assert np.array_equal(a[210:], before[0][210:])
        assert not np.array_equal(a, before[0])
        # Read actual painted number cells against independently specified values.
        # Do not call target()/live_lines() to derive the expected target digits.
        layout = layouts[0]
        text = str(n)
        for y0, x0 in [(layout.number_y, layout.number_x)]:
            height = layout.glyphs["0"].foreground.shape[0]
            width = (
                sum(layout.advances[c] for c in text[:-1])
                + layout.glyphs[text[-1]].foreground.shape[1]
            )
            expected_fg = np.zeros((height, width), dtype=np.uint8)
            expected_stroke = expected_fg.copy()
            cursor = 0
            for char in text:
                glyph = layout.glyphs[char]
                end = cursor + glyph.foreground.shape[1]
                expected_fg[:, cursor:end] = np.maximum(
                    expected_fg[:, cursor:end], glyph.foreground
                )
                expected_stroke[:, cursor:end] = np.maximum(
                    expected_stroke[:, cursor:end], glyph.coverage
                )
                cursor += layout.advances[char]
            fg, stroke = (
                expected_fg.astype(np.float32) / 255,
                expected_stroke.astype(np.float32) / 255,
            )
            expected = np.rint((33 * (1 - stroke) + 16 * stroke) * (1 - fg) + 235 * fg).astype(
                np.uint8
            )
            x, y = 10 + x0, 10 + y0
            assert np.array_equal(a[y : y + height, x : x + width], expected)
        assert_pixels(raw, before)
    delayed = coded_source(vs, delay=True)
    fresh = overlay.apply_alignment_overlay(vs.core, delayed, model())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        seen = list(pool.map(lambda n: fresh.get_frame(n).props["SourceIndex"], [2, 3, 0, 7]))
    assert seen == [2, 3, 0, 7]


@pytest.mark.parametrize(
    "fmt_name", ["YUV420P8", "YUV420P10", "YUV444P16", "RGBS", "GRAY8", "RGBH", "GRAYH"]
)
def test_concrete_format_partial_write_fallback_and_lifetime(monkeypatch, fmt_name):
    vs = native()
    fmt = getattr(vs, fmt_name)
    floating = fmt_name in ("RGBS", "RGBH", "GRAYH")
    colors = (
        [0.3]
        if fmt_name.startswith("GRAY") and floating
        else [90]
        if fmt_name == "GRAY8"
        else [0.2, 0.3, 0.4]
        if floating
        else [100, 128, 128]
        if fmt_name == "YUV420P8"
        else [400, 512, 512]
        if fmt_name == "YUV420P10"
        else [20000, 32768, 32768]
    )
    source = vs.core.std.BlankClip(
        width=642, height=240, format=fmt, length=8, color=colors, fpsnum=24000, fpsden=1001
    )
    source = vs.core.std.SetFrameProps(
        source, Sentinel=23, _Range=0, _Transfer=16, _Primaries=9, _Matrix=9
    )
    raw = source.get_frame(5)
    before = frame_arrays(raw)
    # Independent static-only graph is fully evaluated before any live injection.
    with monkeypatch.context() as setup:
        setup.setattr(
            overlay,
            "_live_layout",
            lambda *_: (_ for _ in ()).throw(ValueError("live unavailable")),
        )
        expected_node = overlay.apply_alignment_overlay(
            vs.core, source, model(), warn=lambda _: None
        )
    expected_frame = expected_node.get_frame(5)
    expected = frame_arrays(expected_frame)
    original = overlay._paint
    references: list[weakref.ReferenceType[Any]] = []
    calls = []

    def fail_after_write(f, raster):
        calls.append("static" if references else "live")
        if len(calls) == 1:
            partial = original(f, raster)
            a = np.asarray(partial[0])
            a[0, 0] = 0.9 if floating else 123  # outside either text footprint
            references.extend((weakref.ref(partial), weakref.ref(a)))
            try:
                raise TypeError("nested owned error")
            except TypeError as cause:
                raise ValueError("AFTER_IDENTIFIABLE_LIVE_WRITE") from cause
        gc.collect()
        assert all(r() is None for r in references), (
            "failed frame/array/traceback survives into static"
        )
        return original(f, raster)

    monkeypatch.setattr(overlay, "_paint", fail_after_write)
    warnings = []
    node = overlay.apply_alignment_overlay(vs.core, source, model(), warn=warnings.append)
    # Earlier successful evaluated requests, then an uncached failing request.
    with monkeypatch.context() as successful:
        successful.setattr(overlay, "_paint", original)
        node.get_frame(0)
        node.get_frame(1)
    f = node.get_frame(5)
    assert calls == ["live", "static"]
    assert_pixels(f, expected)
    assert_pixels(raw, before)
    assert dict(f.props) == dict(raw.props) and f.format.id == fmt
    assert (node.fps_num, node.fps_den) == (source.fps_num, source.fps_den)
    assert node.num_frames == source.num_frames
    assert len(warnings) == 1 and "static" in warnings[0]
    for p, a in enumerate(frame_arrays(f)):
        # Text resources cannot reach the bottom 40 source pixels on this geometry.
        tail = 20 if p and f.format.color_family == vs.YUV else 40
        assert np.array_equal(a[-tail:], before[p][-tail:])
        assert np.asarray(f[p]).strides[0] >= a.shape[1] * a.dtype.itemsize


def test_stride_subsampling_edge_and_native_levels():
    vs = native()
    for fmt, color, black, white, neutral in [
        (vs.YUV420P8, [100, 128, 128], 16, 235, 128),
        (vs.YUV420P10, [400, 512, 512], 64, 940, 512),
        (vs.YUV444P16, [20000, 32768, 32768], 4096, 60160, 32768),
        (vs.RGBS, [0.2, 0.3, 0.4], 0, 1, 0),
        (vs.GRAY8, [100], 16, 235, 0),
    ]:
        src = vs.core.std.BlankClip(width=642, height=120, format=fmt, length=1, color=color)
        raw = src.get_frame(0)
        before = frame_arrays(raw)
        foreground = np.zeros((19, 21), dtype=np.uint8)
        foreground[2:, 2:] = 255
        coverage = np.full((19, 21), 255, dtype=np.uint8)
        raster = overlay._Raster(foreground, coverage, x=621, y=101)
        out = overlay._paint(raw, raster)
        for p, expected in enumerate(before):
            a = np.asarray(out[p])
            sw = out.format.subsampling_w if p and out.format.color_family == vs.YUV else 0
            sh = out.format.subsampling_h if p and out.format.color_family == vs.YUV else 0
            x, y = 621 >> sw, 101 >> sh
            expected = expected.copy()
            if p and out.format.color_family == vs.YUV:
                expected[y:, x:] = neutral
            else:
                expected[y:, x:] = black
                expected[y + 2 :, x + 2 :] = white
            assert np.array_equal(a, expected)
        assert_pixels(raw, before)


def test_source_error_and_native_return_validation_are_not_recovered(monkeypatch):
    vs = native()
    warnings = []
    source = coded_source(vs, source_error=True)
    node = overlay.apply_alignment_overlay(vs.core, source, model(), warn=warnings.append)
    with pytest.raises(vs.Error, match="SOURCE_ERROR_OVERLAY_UNIQUE"):
        node.get_frame(6)
    assert warnings == []
    wrong = vs.core.std.BlankClip(width=642, height=240, format=vs.GRAY8, length=8).get_frame(0)
    monkeypatch.setattr(overlay, "_paint", lambda *_: wrong)
    invalid = overlay.apply_alignment_overlay(
        vs.core, coded_source(vs), model(), warn=warnings.append
    )
    with pytest.raises(vs.Error, match="wrong format"):
        invalid.get_frame(0)
    assert warnings == []


def test_double_failure_raw_dedupe_logging_failure_and_setup_degradation(monkeypatch):
    vs = native()
    source = coded_source(vs)
    warnings = []
    original = overlay._paint
    with monkeypatch.context() as fail:
        fail.setattr(overlay, "_paint", lambda *_: (_ for _ in ()).throw(ValueError("owned")))
        node = overlay.apply_alignment_overlay(vs.core, source, model(), warn=warnings.append)
        for n in (5, 6):
            assert_pixels(node.get_frame(n), frame_arrays(source.get_frame(n)))
        assert len(warnings) == 1 and "raw preview" in warnings[0]

        def broken(_):
            raise OSError("logger failed")

        safe = overlay.apply_alignment_overlay(vs.core, source, model(), warn=broken)
        assert_pixels(safe.get_frame(5), frame_arrays(source.get_frame(5)))
    assert overlay._paint is original
    with monkeypatch.context() as absent:
        absent.setattr(
            overlay, "_raster", lambda *_: (_ for _ in ()).throw(ValueError("static absent"))
        )
        raw = overlay.apply_alignment_overlay(vs.core, source, model(), warn=warnings.append)
        assert raw is source and "unsupported" in warnings[-1]


def test_layout_fit_uses_static_or_explicit_raw_degradation():
    vs = native()
    warnings = []
    narrow = vs.core.std.BlankClip(width=180, height=360, format=vs.GRAY8, length=8, color=[90])
    static = overlay.apply_alignment_overlay(vs.core, narrow, model(), warn=warnings.append)
    assert static is not narrow
    assert warnings == []  # Minimal labels now fit live; fallback faults are covered separately.
    assert not np.array_equal(
        np.asarray(static.get_frame(5)[0]), np.asarray(narrow.get_frame(5)[0])
    )
    tiny = vs.core.std.BlankClip(width=80, height=60, format=vs.GRAY8, length=8, color=[90])
    raw = overlay.apply_alignment_overlay(vs.core, tiny, model(), warn=warnings.append)
    assert raw is tiny and "unsupported" in warnings[-1]


def test_cross_source_selector_overlap_has_independent_outputs(monkeypatch):
    vs = native()
    original = overlay._paint
    active = 0
    peak = 0
    lock = threading.Lock()

    def delayed(f, raster):
        nonlocal active, peak
        out = original(f, raster)
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)  # controlled GIL-release probe, not natural memcpy-overlap evidence
        with lock:
            active -= 1
        return out

    monkeypatch.setattr(overlay, "_paint", delayed)
    sources = [
        vs.core.std.BlankClip(width=642, height=240, format=vs.GRAY8, length=8, color=[c])
        for c in (33, 77)
    ]
    nodes = [overlay.apply_alignment_overlay(vs.core, s, model()) for s in sources]

    def request(key):
        sid, n = key
        f = nodes[sid].get_frame(n)
        assert np.asarray(f[0])[220, 600] == (33, 77)[sid]
        return frame_arrays(f)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(request, [(0, 0), (1, 5), (0, 7), (1, 2)]))
    assert len(results) == 4 and peak == 2 and active == 0


def test_runtime_wires_native_previews_using_strict_launch_workspace(tmp_path, monkeypatch):
    vs = native()
    monkeypatch.setenv("VSVIEW_HDR", "1")
    from frame_compare.vsview import session_runtime as runtime

    sources = {name: coded_source(vs) for name in ("ref", "a", "b")}
    loaded = []

    def load(path, **_kwargs):
        key = Path(path).stem
        loaded.append(key)
        return sources[key]

    monkeypatch.setattr(
        runtime, "resolve_lwlibavsource", lambda _: SimpleNamespace(LWLibavSource=load)
    )
    registered = []

    def register(clip, index, name, *, hdr, **metadata):
        assert hdr is False
        assert loaded == ["ref", "a", "b"]
        registered.append((clip, index, name, metadata))

    viewer = types.ModuleType("vsview")
    monkeypatch.setattr(viewer, "set_output", register, raising=False)
    monkeypatch.setitem(sys.modules, "vsview", viewer)
    for name in sources:
        (tmp_path / f"{name}.mkv").touch()
    targets = {}
    for ordinal, name in enumerate(("a", "b"), 1):
        evidence = (
            audio_review(0)
            if ordinal == 1
            else json.dumps(
                {
                    "current_authority": {"origin": "none", "frame_offset": None},
                    "evidence_availability": "current_attempt",
                    "audio_attempt": asdict(provisional_audio_attempt(ordinal=2, frame_offset=504)),
                }
            )
        )
        targets[name] = {
            "path": str(tmp_path / f"{name}.mkv"),
            "index_path": str(tmp_path / f"{name}.index"),
            "display_name": name,
            "comparison_key": f"ref:{name}",
            "suggested_offset": 0 if ordinal == 1 else None,
            "audio_review": evidence,
        }
    data = cast(
        runtime.SessionData,
        {
            "reference": {
                "label": "ref",
                "path": str(tmp_path / "ref.mkv"),
                "index_path": str(tmp_path / "ref.index"),
                "display_name": "Full reference",
            },
            "targets": targets,
            "short_names": {"ref": "REF short", "a": "A short", "b": "B short"},
            "frame_props_by_label": {
                name: {"_Matrix": 1, "_Transfer": 1, "_Primaries": 1, "_Range": 0}
                for name in sources
            },
            "memory_limit_mb": None,
        },
    )
    runtime.run_session(data, tmp_path / f"session_{'1' * 32}.py")
    assert [(i, n) for _, i, n, _ in registered] == [
        (0, "Reference"),
        (1, "Comparison 1"),
        (2, "Comparison 2"),
    ]
    assert registered[2][3]["frame_compare_suggested_offset"] is None
    for clip, _, _, metadata in registered:
        assert metadata["frame_compare_contract_version"] == 5
        assert clip.num_frames == 8 and clip.fps == sources["ref"].fps
        frame = clip.get_frame(5)
        assert frame.props["SourceIndex"] == 5
        assert np.asarray(frame[0])[222, 0] == 200


@pytest.mark.parametrize(
    "format_name",
    [
        "YUV420P10",
        "YUV422P10",
        "YUV410P8",
        "YUV411P8",
        "YUV444PS",
        "RGBH",
        "GRAY8",
    ],
)
def test_antialias_pixels_match_full_frame_chroma_footprint_oracle(format_name):
    """Odd cropped ROI must agree with a separate full-frame block-reduction oracle."""
    vs = native()
    floating = format_name in ("YUV444PS", "RGBH")
    color = (
        [0.3, 0.1, -0.1]
        if format_name == "YUV444PS"
        else [0.2, 0.3, 0.4]
        if floating
        else [90]
        if format_name == "GRAY8"
        else [400, 512, 512]
        if format_name.endswith("P10")
        else [100, 128, 128]
    )
    clip = vs.core.std.BlankClip(
        width=64, height=32, format=getattr(vs, format_name), length=1, color=color
    )
    frame = clip.get_frame(0).copy()
    for p in range(frame.format.num_planes):
        a = np.asarray(frame[p])
        pattern = np.arange(a.size).reshape(a.shape) % 13
        a[:] = pattern * 0.01 + 0.25 if floating else pattern * 3 + 40
        del a
    before = frame_arrays(frame)
    rng = np.random.default_rng(119)
    coverage = rng.integers(0, 256, size=(7, 9), dtype=np.uint8)
    foreground = np.minimum(coverage, rng.integers(0, 256, size=(7, 9), dtype=np.uint8))
    coverage[0, 0], foreground[0, 0] = 255, 255
    coverage[-1, -1] = 0
    foreground[-1, -1] = 0
    raster = overlay._Raster(foreground, coverage, x=3, y=5)
    full_coverage = np.zeros((32, 64), dtype=np.uint8)
    full_foreground = full_coverage.copy()
    full_coverage[5:12, 3:12] = coverage
    full_foreground[5:12, 3:12] = foreground
    out = overlay._paint(frame, raster)
    fmt = frame.format
    for p, raw in enumerate(before):
        if p and fmt.color_family == vs.YUV:
            sx, sy = 1 << fmt.subsampling_w, 1 << fmt.subsampling_h
            # Global blocks establish expected expansion independently of ROI padding
            # or the compositor's strided maximum implementation.
            alpha = (
                full_coverage.reshape(32 // sy, sy, 64 // sx, sx)
                .max(axis=(1, 3))
                .astype(np.float32)
                / 255
            )
            neutral = 0.0 if floating else float(1 << (fmt.bits_per_sample - 1))
            expected = raw.astype(np.float32) * (1 - alpha) + neutral * alpha
        else:
            alpha, fg = (
                full_coverage.astype(np.float32) / 255,
                full_foreground.astype(np.float32) / 255,
            )
            black = 0.0 if floating else float(16 << (fmt.bits_per_sample - 8))
            white = 1.0 if floating else float(235 << (fmt.bits_per_sample - 8))
            expected = (raw.astype(np.float32) * (1 - alpha) + black * alpha) * (
                1 - fg
            ) + white * fg
        if not floating:
            expected = np.rint(expected)
        assert np.array_equal(np.asarray(out[p]), expected.astype(raw.dtype))
    assert_pixels(frame, before)
    assert dict(out.props) == dict(frame.props)


def test_tight_layout_reserves_complete_original_frame_number():
    count = 2**63 - 1
    m = overlay.LaunchOverlay("CMP", "C", count, 1)
    layout = overlay._live_layout(m, overlay._font(2160), 3820, 2140)
    value = count - 1
    raster = layout.render(value)
    text = f"{value:,}"
    x = layout.number_x + sum(layout.advances[c] for c in text[:-1])
    glyph = layout.glyphs[text[-1]].foreground
    actual = raster.foreground[
        layout.number_y : layout.number_y + glyph.shape[0], x : x + glyph.shape[1]
    ]
    assert np.all(actual >= glyph)


def test_narrow_native_digits_follow_wrapped_prefix_without_overwriting_it():
    from math import ceil

    from PIL import Image, ImageDraw

    vs = native()
    font = overlay._font(720)
    # Measured width fits each word and the largest number, but not the full prefix.
    width = ceil(max(font.getlength(word) for word in ("Original", "frame", "REF - A"))) + 8
    assert font.getlength("Original frame") > width - 4
    assert 3 * max(ceil(font.getlength(c)) for c in "0123456789,") + 4 < width
    source = vs.core.std.BlankClip(
        width=width + 20, height=720, format=vs.GRAY8, length=128, color=[90]
    )
    warnings = []
    node = overlay.apply_alignment_overlay(
        vs.core, source, overlay.LaunchOverlay("REF", "A", 128), warn=warnings.append
    )
    bbox = font.getbbox("Ag09")
    step = ceil(bbox[3] - bbox[1]) + 7
    # Independent physical rows: heading, two prefix words, then the numeric row.
    # These masks deliberately do not use _live_layout's number_y or rendered masks.
    for number in (0, 127):
        foreground = Image.new("L", (width, 4 * step))
        coverage = Image.new("L", foreground.size)
        fg_draw, stroke_draw = ImageDraw.Draw(foreground), ImageDraw.Draw(coverage)
        for row, text in enumerate(("REF - A", "Original", "frame", "")):
            xy = (2, 2 + row * step - bbox[1])
            fg_draw.text(xy, text, font=font, fill=255)
            stroke_draw.text(xy, text, font=font, fill=255, stroke_width=2, stroke_fill=255)
        # Independent per-digit masks combine by maximum, preserving antialiased
        # edges where neighboring strokes overlap instead of painting over them.
        fg_array, stroke_array = np.asarray(foreground).copy(), np.asarray(coverage).copy()
        x = 4  # numeric slot origin plus the glyph mask's two-pixel inset
        for char in str(number):
            glyph_fg = Image.new("L", foreground.size)
            glyph_stroke = Image.new("L", foreground.size)
            xy = (x, 2 + 3 * step - bbox[1])
            ImageDraw.Draw(glyph_fg).text(xy, char, font=font, fill=255)
            ImageDraw.Draw(glyph_stroke).text(
                xy, char, font=font, fill=255, stroke_width=2, stroke_fill=255
            )
            np.maximum(fg_array, np.asarray(glyph_fg), out=fg_array)
            np.maximum(stroke_array, np.asarray(glyph_stroke), out=stroke_array)
            x += ceil(font.getlength(char))
        fg = fg_array.astype(np.float32) / 255
        stroke = stroke_array.astype(np.float32) / 255
        expected = np.rint((90 * (1 - stroke) + 16 * stroke) * (1 - fg) + 235 * fg).astype(np.uint8)
        raw = source.get_frame(number)
        before = frame_arrays(raw)
        painted = node.get_frame(number)
        actual = np.asarray(painted[0])[10 : 10 + 4 * step, 10 : 10 + width]
        assert np.array_equal(actual, expected), (
            "prefix rows or separate numeric row were overwritten"
        )
        assert_pixels(raw, before)
    assert warnings == []
