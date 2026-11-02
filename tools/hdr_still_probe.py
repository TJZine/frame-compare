"""Bounded, side-by-side native checkpoints; no media/config/installation mutations.

This initial fixture is NOT epsilon/RPU/fault/eviction acceptance. It captures
native16 and corrected sRGB8 from one evaluation and can disqualify a candidate.
Run each mode/history in a fresh bounded subprocess, using verify_hdr_still.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["stock-fresh", "candidate-fresh", "candidate-independent", "stock-sequence"],
        required=True,
    )
    parser.add_argument(
        "--history",
        choices=["direct", "helper", "forward", "reverse", "repeated", "parallel"],
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plugin", type=Path)
    args = parser.parse_args()
    # Never overwrite a previous checkpoint/evidence directory.
    args.output.mkdir(parents=True, exist_ok=False)
    result = {
        "status": "running",
        "mode": args.mode,
        "history": args.history,
        "platform": platform.platform(),
        "python": sys.version,
        "boundary": "Synthetic Stage1 screening only; no native fault/cancellation/RPU/epsilon/VRAM proof; timings include checkpoint work.",
    }
    try:
        import numpy as np
        import vapoursynth as vs

        from frame_compare.vs.tonemap_conversion import (
            apply_post_processing,
            libplacebo_output_to_srgb,
            normalize_rgb_props,
            resolve_hdr_tonemap_inputs,
        )
        from frame_compare.vs.tonemap_libplacebo import build_libplacebo_tonemap_kwargs
        from frame_compare.vs.types import TonemapSettings

        core = vs.core
        core.num_threads = 4
        core.max_cache_size = 64
        namespace = core.placebo
        if args.mode.startswith("candidate"):
            if args.plugin is None or not args.plugin.is_file():
                raise RuntimeError("Candidate requires an explicit side-by-side plugin file")
            core.std.LoadPlugin(
                path=str(args.plugin.resolve()),
                forcens="placebo_stage1",
                forceid="com.framecompare.stage1",
            )
            namespace = core.placebo_stage1
        loaded = Path(namespace.plugin_path)
        result.update(
            plugin_path=str(loaded),
            plugin_sha256=sha(loaded),
            signature=namespace.Tonemap.signature,
            vapoursynth=str(vs.__version__),
        )
        if (
            args.mode == "candidate-independent"
            and "independent:int:opt;" not in namespace.Tonemap.signature
        ):
            raise RuntimeError("Candidate does not advertise independent:int:opt;")

        # Same gradual peak fixture used in prior independence proof, plus black.
        peaks = [180, 260, 225, 210, 245, 200, 230, 190, 250, 0]
        blank = core.std.BlankClip(width=64, height=32, format=vs.RGB48, length=len(peaks))

        def fill(n, f):
            frame = f.copy()
            lum = np.zeros((1, 64)) if peaks[n] == 0 else np.linspace(0.18, peaks[n], 64)[None, :]
            for plane, factor in enumerate([1.0, 0.8, 0.6]):
                x = (lum * factor / 10000) ** (2610 / 16384)
                pq = ((3424 / 4096 + 2413 / 128 * x) / (1 + 2392 / 128 * x)) ** (2523 / 32)
                np.copyto(
                    np.asarray(frame[plane]),
                    np.broadcast_to(np.rint(pq * 65535).astype(np.uint16), (32, 64)),
                )
            return frame

        source = blank.std.ModifyFrame(clips=blank, selector=fill).std.SetFrameProps(
            _Matrix=0,
            _Transfer=16,
            _Primaries=9,
            _ColorRange=0,
            _Range=1,
            MasteringDisplayMinLuminance=0.0001,
            MasteringDisplayMaxLuminance=1000.0,
            ContentLightLevelMax=1000.0,
            ContentLightLevelAverage=100.0,
        )
        settings = TonemapSettings()
        kwargs = build_libplacebo_tonemap_kwargs(
            settings=settings,
            target_nits=settings.target_nits,
            inputs=resolve_hdr_tonemap_inputs(source, None),
        )
        source = normalize_rgb_props(source, transfer=16, primaries=9)
        result.update(
            settings=asdict(settings),
            tone_kwargs=kwargs,
            fixture={
                "peaks_nits": peaks,
                "size": [64, 32],
                "input": "RGB48 PQ/BT2020 full",
                "rpu": False,
            },
        )
        requests = {
            "direct": [2],
            "helper": [0, 2],
            "forward": list(range(10)),
            "reverse": list(reversed(range(10))),
            "repeated": [8, 2, 1, 2, 0, 2],
            "parallel": [8, 2, 1, 2, 0, 2],
        }[args.history]

        # Count constructor calls and checkpoint evaluations. They do NOT prove
        # how often native pl_render_image executes: add native counters for eviction proof.
        counts = {"constructors": 0, "checkpoint_evaluations": 0}
        lock = threading.Lock()

        def construct(clip, **extra):
            with lock:
                counts["constructors"] += 1
            return namespace.Tonemap(clip, **kwargs, **extra)

        if args.mode.endswith("fresh"):
            first = construct(source[0]).std.Loop(times=source.num_frames)

            def evaluate(n):
                return first if n == 0 else construct(source[n]).std.Loop(times=source.num_frames)

            native = core.std.FrameEval(first, eval=evaluate, clip_src=[source])
        elif args.mode == "candidate-independent":
            native = construct(source, independent=1)
        else:
            native = construct(source)
        assert native.format.bits_per_sample == 16 and native.format.color_family == vs.RGB
        captures = {}

        def tap(n, f):
            frame = f
            samples = np.stack([np.asarray(frame[p]).copy() for p in range(3)])
            with lock:
                counts["checkpoint_evaluations"] += 1
                token = counts["checkpoint_evaluations"]
                captures[token] = (n, samples)
            frame = frame.copy()
            frame.props["_FCStage1Token"] = token
            frame.props["_FCStage1NativeHash"] = hashlib.sha256(samples.tobytes()).hexdigest()
            return frame

        tapped = native.std.ModifyFrame(clips=native, selector=tap)
        corrected = libplacebo_output_to_srgb(
            apply_post_processing(tapped.resize.Point(format=vs.RGBS), settings),
            black_nits=settings.dst_min_nits,
            white_nits=settings.target_nits,
        )
        # Production RGB8 quantization, without a second helper-triggered request.
        # Helper history explicitly requests0 through the SAME checkpoint graph.
        rgb8 = corrected.resize.Point(format=vs.RGB24)
        rows = []
        started = time.monotonic()
        futures = (
            [rgb8.get_frame_async(n) for n in requests] if args.history == "parallel" else None
        )
        for i, n in enumerate(requests):
            with futures[i].result() if futures else rgb8.get_frame(n) as frame:
                token = frame.props["_FCStage1Token"]
                actual_n, native_samples = captures[token]
                assert actual_n == n
                final = np.stack([np.asarray(frame[p]).copy() for p in range(3)])
                h16 = hashlib.sha256(native_samples.tobytes()).hexdigest()
                carried_hash = frame.props["_FCStage1NativeHash"]
                if isinstance(carried_hash, bytes):
                    carried_hash = carried_hash.decode("ascii")
                assert carried_hash == h16
                assert frame.props["_Transfer"] == 13 and frame.props["_Primaries"] == 1
                assert frame.props["_Matrix"] == 0 and frame.props["_Range"] == 1
                file = f"request-{i:02d}-frame-{n}.npz"
                np.savez_compressed(args.output / file, native16=native_samples, srgb8=final)
                rows.append(
                    {
                        "request": i,
                        "n": n,
                        "token": token,
                        "native16_sha256": h16,
                        "srgb8_sha256": hashlib.sha256(final.tobytes()).hexdigest(),
                        "arrays": file,
                    }
                )
        result.update(
            status="passed",
            requests=requests,
            rows=rows,
            counters=counts,
            elapsed_seconds=time.monotonic() - started,
            instrumentation="Native16 tap token/hash propagates through unchanged sRGB pipeline to finalRGB8; active plane samples, no stride padding. Tap count is not native invocation count.",
        )
        return 0
    except Exception as exc:
        result.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        (args.output / "result.json").write_text(
            json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    raise SystemExit(main())
