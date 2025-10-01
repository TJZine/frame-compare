#!/usr/bin/env python3
"""
align_videos.py — Coarse video alignment via keyframes (ffprobe).
Builds a piecewise linear mapping (EDL JSON) from video A's timeline to video B's,
handling extra/missing frames and small editorial differences.

FEATURES
- Keyframe lists via ffprobe (I-frame timestamps)
- DTW-based matching of event sequences (robust to insertions/deletions)
- Segmenter that produces a piecewise linear time-map (A_time -> B_time) with near-1.0 slope
- Optional CSV dump of matches and offsets for inspection

REQUIREMENTS
- Python 3.9+
- ffprobe/ffmpeg accessible in PATH
- numpy

USAGE (one line):
  python align_videos.py "A.mkv" "B.mkv" --fps 23.976 --use-keyframes --out alignment.json

TIP:
  Keyframes provide a fast coarse alignment. You can limit analysis to a window with --start/--dur (seconds).

OUTPUT
- JSON file (default: alignment.json) with a list of segments like:
  [
    {"a_start": 0.0, "a_end": 41.25, "b_start": 0.0, "slope": 1.0},
    {"a_start": 41.25, "a_end": 73.42, "b_start": 41.49, "slope": 1.0}
  ]
- Optional CSV of matched event pairs and local offsets (for debugging)

LIMITATIONS
- DTW is O(N*M) in event counts; for very long lists, consider --max-events to sample events.
- Streams with sparse I-frames may require longer ffprobe scans; the tool now falls back to start/end markers when no keyframes exist.
  Keyframes alone are usually sufficient for coarse alignment.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict

import numpy as np


# -------------------------- Utilities --------------------------

def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run(cmd: List[str]) -> str:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSTDERR:\n{proc.stderr}")
    return proc.stdout


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# -------------------------- FFprobe keyframes --------------------------

def ffprobe_keyframes(path: str, stream_index: int = 0,
                      start: Optional[float] = None, dur: Optional[float] = None,
                      max_events: Optional[int] = None) -> List[float]:
    """
    Return a list of I-frame timestamps (seconds) for the selected video stream.
    """
    if not which("ffprobe"):
        raise RuntimeError("ffprobe not found in PATH")
    sel = ["-select_streams", f"v:{stream_index}"]
    show = ["-show_frames", "-show_entries", "frame=pkt_pts_time,pict_type", "-of", "json"]
    ss = ["-read_intervals", f"%+{dur}"] if (start is None and dur is not None) else []
    # If start specified, use -read_intervals start%+dur, else whole file
    if start is not None:
        if dur is None:
            ss = ["-read_intervals", f"{start}%"]
        else:
            ss = ["-read_intervals", f"{start}%+{dur}"]

    cmd = ["ffprobe", "-v", "error", *sel, *ss, *show, path]
    out = run(cmd)
    data = json.loads(out)
    frames = data.get("frames", [])
    kf = []
    for fr in frames:
        if fr.get("pict_type") == "I":
            t = fr.get("pkt_pts_time")
            if t is not None:
                try:
                    kf.append(float(t))
                except ValueError:
                    pass
    # Optionally sample down to max_events evenly
    if max_events and len(kf) > max_events:
        idx = np.linspace(0, len(kf) - 1, max_events).round().astype(int)
        kf = [kf[i] for i in idx]
    return kf


# -------------------------- Duration helper --------------------------

def ffprobe_duration(path: str) -> Optional[float]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        path,
    ]
    try:
        out = run(cmd)
        data = json.loads(out)
        duration = data.get("format", {}).get("duration")
        if duration is None:
            return None
        return float(duration)
    except Exception:
        return None


# -------------------------- DTW alignment --------------------------

@dataclass
class MatchResult:
    pairs: List[Tuple[float, float]]  # matched (tA, tB)
    cost: float


def dtw_align(seq_a: List[float], seq_b: List[float],
              gap_penalty: float = 0.4) -> MatchResult:
    """
    Align two sorted timestamp lists using simple DTW.
    cost(i,j) = (a[i]-b[j])^2; insertion/deletion cost = gap_penalty
    Returns matched pairs (tA, tB).
    """
    A = np.asarray(seq_a, dtype=np.float64)
    B = np.asarray(seq_b, dtype=np.float64)
    n, m = len(A), len(B)
    if n == 0 or m == 0:
        return MatchResult([], float("inf"))

    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0.0
    back = np.zeros((n + 1, m + 1), dtype=np.uint8)  # 1=diag, 2=up, 3=left

    for i in range(1, n + 1):
        D[i, 0] = i * gap_penalty
        back[i, 0] = 2
    for j in range(1, m + 1):
        D[0, j] = j * gap_penalty
        back[0, j] = 3

    for i in range(1, n + 1):
        ai = A[i - 1]
        for j in range(1, m + 1):
            bj = B[j - 1]
            c = (ai - bj) ** 2
            d_diag = D[i - 1, j - 1] + c
            d_up = D[i - 1, j] + gap_penalty
            d_left = D[i, j - 1] + gap_penalty
            if d_diag <= d_up and d_diag <= d_left:
                D[i, j] = d_diag
                back[i, j] = 1
            elif d_up <= d_left:
                D[i, j] = d_up
                back[i, j] = 2
            else:
                D[i, j] = d_left
                back[i, j] = 3

    # Backtrack
    i, j = n, m
    pairs = []
    while i > 0 or j > 0:
        move = back[i, j]
        if move == 1:
            pairs.append((A[i - 1], B[j - 1]))
            i -= 1; j -= 1
        elif move == 2:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return MatchResult(pairs=pairs, cost=float(D[n, m]))


# -------------------------- Segment building --------------------------

@dataclass
class Segment:
    a_start: float
    a_end: float
    b_start: float
    slope: float  # ideally ~1.0


def build_segments(pairs: List[Tuple[float, float]],
                   offset_tol: float = 0.25,
                   min_pairs: int = 3) -> List[Segment]:
    """
    Given matched pairs (tA, tB), build piecewise linear segments.
    We track local offset = tB - tA. When offset jumps by > offset_tol seconds, start a new segment.
    Fit a slope/intercept per segment via least squares.
    """
    if not pairs:
        return []

    arr = np.array(pairs, dtype=np.float64)
    a = arr[:, 0]; b = arr[:, 1]
    offsets = b - a

    segments: List[Segment] = []
    start_idx = 0
    ref = offsets[0]
    for i in range(1, len(offsets)):
        if abs(offsets[i] - ref) > offset_tol:
            # end previous segment at i-1
            seg = fit_segment(a[start_idx:i], b[start_idx:i], min_pairs)
            if seg:
                segments.append(seg)
            start_idx = i
            ref = offsets[i]
        else:
            # update running reference (robust) via small EMA
            ref = 0.9 * ref + 0.1 * offsets[i]

    # last segment
    seg = fit_segment(a[start_idx:], b[start_idx:], min_pairs)
    if seg:
        segments.append(seg)

    # Merge adjacent nearly-identical segments
    merged: List[Segment] = []
    for s in segments:
        if merged and abs(merged[-1].slope - s.slope) < 0.001 and abs(
                (merged[-1].b_start + (s.a_start - merged[-1].a_start) * merged[-1].slope) - s.b_start) < 0.05:
            # extend previous
            merged[-1].a_end = s.a_end
        else:
            merged.append(s)
    return merged


def fit_segment(a: np.ndarray, b: np.ndarray, min_pairs: int) -> Optional[Segment]:
    if len(a) < min_pairs:
        return None
    # Linear fit: b = m*a + c
    m, c = np.polyfit(a, b, 1)
    a0, a1 = float(a[0]), float(a[-1])
    b0 = m * a0 + c
    return Segment(a_start=a0, a_end=a1, b_start=b0, slope=float(m))


# -------------------------- CSV dump --------------------------

def dump_matches_csv(pairs: List[Tuple[float, float]], path: str, fps: float) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tA_sec", "tB_sec", "offset_sec", "offset_frames"])
        for ta, tb in pairs:
            off = tb - ta
            w.writerow([f"{ta:.3f}", f"{tb:.3f}", f"{off:.3f}", f"{off*fps:.2f}"])


# -------------------------- Main --------------------------

def main():
    p = argparse.ArgumentParser(description="Align two videos via keyframes extracted with ffprobe.")
    p.add_argument("video_a")
    p.add_argument("video_b")
    p.add_argument("--fps", type=float, default=23.976, help="Assumed FPS for reporting (does not change decode)")
    p.add_argument("--start", type=float, default=None, help="Start time (sec) for analysis window")
    p.add_argument("--dur", type=float, default=None, help="Duration (sec) for analysis window")
    p.add_argument(
        "--use-keyframes",
        action="store_true",
        default=True,
        help="Use ffprobe I-frames as events (default).",
    )
    p.add_argument("--max-events", type=int, default=4000, help="Max events per source (down-sampled if exceeded)")
    p.add_argument("--gap-penalty", type=float, default=0.4, help="DTW insertion/deletion penalty (seconds^2 units)")
    p.add_argument("--offset-tol", type=float, default=0.25, help="Offset jump (sec) to split segments")
    p.add_argument("--min-pairs", type=int, default=3, help="Minimum matched pairs per segment")
    p.add_argument("--out", default="alignment.json", help="Output JSON path")
    p.add_argument("--pairs-csv", default=None, help="Optional CSV path to dump matched event pairs")
    args = p.parse_args()

    if not args.use_keyframes:
        print("No detector selected. Enable --use-keyframes to generate events.", file=sys.stderr)
        sys.exit(2)

    # Collect events for A and B
    events_a: List[float] = []
    events_b: List[float] = []

    if args.use_keyframes:
        print("Extracting keyframes (ffprobe)...")
        events_a_kf = ffprobe_keyframes(args.video_a, start=args.start, dur=args.dur, max_events=args.max_events)
        events_b_kf = ffprobe_keyframes(args.video_b, start=args.start, dur=args.dur, max_events=args.max_events)
        print(f" A keyframes: {len(events_a_kf)}   B keyframes: {len(events_b_kf)}")
        events_a.extend(events_a_kf)
        events_b.extend(events_b_kf)

    # Deduplicate and sort
    def uniq_sorted(seq: List[float]) -> List[float]:
        seq = sorted(seq)
        out = []
        last = None
        for t in seq:
            if last is None or abs(t - last) > 1e-6:
                out.append(t); last = t
        return out

    events_a = uniq_sorted(events_a)
    events_b = uniq_sorted(events_b)

    if not events_a:
        fallback_a = [0.0]
        duration_a = ffprobe_duration(args.video_a)
        if duration_a and duration_a > 0:
            fallback_a.append(duration_a)
        events_a = uniq_sorted(fallback_a)
        print("[WARN] No keyframes found for A; fell back to start/end markers.", file=sys.stderr)

    if not events_b:
        fallback_b = [0.0]
        duration_b = ffprobe_duration(args.video_b)
        if duration_b and duration_b > 0:
            fallback_b.append(duration_b)
        events_b = uniq_sorted(fallback_b)
        print("[WARN] No keyframes found for B; fell back to start/end markers.", file=sys.stderr)

    if not events_a or not events_b:
        print("No events extracted; nothing to align.", file=sys.stderr)
        sys.exit(1)

    print(f"Total events after merge:  A={len(events_a)}  B={len(events_b)}")

    # Align via DTW
    print("Running DTW alignment...")
    match = dtw_align(events_a, events_b, gap_penalty=args.gap_penalty)
    print(f"Matched pairs: {len(match.pairs)}   DTW cost: {match.cost:.2f}")

    # Build segments
    segments = build_segments(match.pairs, offset_tol=args.offset_tol, min_pairs=args.min_pairs)
    if not segments:
        print("No segments produced. Try adjusting --offset-tol or check event quality.", file=sys.stderr)
        sys.exit(1)

    # Save JSON
    out_json = [{"a_start": s.a_start, "a_end": s.a_end, "b_start": s.b_start, "slope": s.slope} for s in segments]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out_json, f, indent=2)
    print(f"Wrote segments: {args.out}  (count={len(segments)})")

    # Optional CSV pairs dump
    if args.pairs_csv:
        dump_matches_csv(match.pairs, args.pairs_csv, args.fps)
        print(f"Wrote match pairs CSV: {args.pairs_csv}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
