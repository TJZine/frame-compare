#!/usr/bin/env python3
"""
audio_offset_check.py
--------------------
Estimate time/frame offset between two or more videos via audio onset cross-correlation.
Adds two conveniences:
  1) Auto-discover video files in the same directory as THIS script (or a chosen dir).
  2) A progress bar with ETA for batch processing.

Output includes:
  - Offset in seconds (positive => B ahead of A; seek B backward by this amount to align to A)
  - Approx frame difference using A's and B's FPS (auto-detected via ffprobe unless --fps is supplied)
  - Correlation strength (rough confidence indicator; higher typically better)

Dependencies:
  - System: ffmpeg, ffprobe (in PATH)
  - Python: numpy, librosa, soundfile, tqdm

Install (one line):
  pip install numpy librosa soundfile tqdm

Usage examples:
  # Single pair (explicit files)
  python audio_offset_check.py "Ref_A.mkv" "Alt_B.mkv"

  # Auto-scan the script's directory for videos and align each to the chosen reference (first by default)
  python audio_offset_check.py

  # Auto-scan a specific directory
  python audio_offset_check.py --scan-dir "/path/to/videos"

  # Use a specific reference name (exact filename in scan list)
  python audio_offset_check.py --ref "Ref_A.mkv"

  # Compute all pairwise offsets among discovered files
  python audio_offset_check.py --pairwise

  # Faster analysis by limiting to first 600 seconds
  python audio_offset_check.py --duration 600

  # If you know the intended FPS (e.g., 23.976), force it for frame conversion
  python audio_offset_check.py "A.mkv" "B.mkv" --fps 23.976
"""
import argparse
import subprocess
import tempfile
import numpy as np
import soundfile as sf
import librosa
import os
import sys
from shutil import which
from itertools import combinations
from tqdm import tqdm

VIDEO_EXTS = {".mkv", ".mp4", ".mov", ".avi", ".ts", ".m2ts", ".webm"}

def check_ffmpeg():
    if which("ffmpeg") is None or which("ffprobe") is None:
        print("ERROR: ffmpeg/ffprobe not found in PATH.", file=sys.stderr)
        sys.exit(2)

def extract_audio(infile, start=None, duration=None, sr=16000):
    """
    Extract mono WAV at sample rate 'sr'. Returns (wav_path, samplerate).
    """
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    out.close()
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", f"{start}"]
    cmd += ["-i", infile]
    if duration is not None:
        cmd += ["-t", f"{duration}"]
    cmd += ["-map", "a:0", "-ac", "1", "-ar", str(sr), "-vn", "-y", out.name]
    subprocess.run(cmd, check=True)
    return out.name, sr

def onset_envelope(wav_path, sr, hop_length=512):
    y, native_sr = sf.read(wav_path)
    if native_sr != sr:
        # Safety: resample if reader didn't produce expected sr
        y = librosa.resample(y, orig_sr=native_sr, target_sr=sr)
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    # Normalize
    m = np.max(np.abs(y))
    if m > 0:
        y = y / m
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    return onset_env.astype(np.float32), hop_length

def xcorr_offset(a, b):
    """
    Cross-correlate 1D arrays a and b to find lag that best aligns b to a.
    Returns (lag_frames, corr_max), where lag_frames is in onset frames (not video frames).
    Positive lag means b ahead of a.
    """
    a = (a - np.mean(a)) / (np.std(a) + 1e-8)
    b = (b - np.mean(b)) / (np.std(b) + 1e-8)
    corr = np.correlate(b, a, mode="full")
    lag = np.argmax(corr) - (len(a) - 1)
    return lag, float(np.max(corr))

def estimate_offset_seconds(file_a, file_b, start=None, duration=None, sr=16000, hop_length=512):
    wav_a, sr = extract_audio(file_a, start=start, duration=duration, sr=sr)
    wav_b, _  = extract_audio(file_b, start=start, duration=duration, sr=sr)
    try:
        env_a, hl_a = onset_envelope(wav_a, sr, hop_length=hop_length)
        env_b, hl_b = onset_envelope(wav_b, sr, hop_length=hop_length)
        assert hl_a == hl_b
        lag_frames, strength = xcorr_offset(env_a, env_b)
        seconds_per_frame = hop_length / float(sr)
        offset_sec = lag_frames * seconds_per_frame
        return offset_sec, strength
    finally:
        for p in (wav_a, wav_b):
            try:
                os.unlink(p)
            except Exception:
                pass

def get_fps(infile):
    """
    Returns average frame rate (float FPS) via ffprobe. Falls back to None on failure.
    """
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=avg_frame_rate",
            "-of", "default=nw=1:nk=1", infile
        ], stderr=subprocess.STDOUT).decode("utf-8", errors="ignore").strip()
        if out and out != "0/0":
            if "/" in out:
                num, den = out.split("/")
                num = float(num)
                den = float(den)
                if den != 0:
                    return num / den
                else:
                    return num
            else:
                return float(out)
    except Exception:
        pass
    return None

def discover_videos(scan_dir):
    files = []
    try:
        for name in os.listdir(scan_dir):
            path = os.path.join(scan_dir, name)
            if os.path.isfile(path) and os.path.splitext(name)[1].lower() in VIDEO_EXTS:
                files.append(path)
    except FileNotFoundError:
        print(f"ERROR: scan directory not found: {scan_dir}", file=sys.stderr)
        sys.exit(2)
    return sorted(files)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Estimate time/frame offset between videos using audio onset correlation. "
                    "Positive offset => B ahead of A (seek B backward by offset to align to A)."
    )
    parser.add_argument("video_a", nargs="?", help="Reference (A). If omitted, use auto-scan mode.")
    parser.add_argument("video_b", nargs="?", help="To align (B). If omitted, use auto-scan mode.")
    parser.add_argument("--start", type=float, default=None, help="Optional start (seconds) for analysis window")
    parser.add_argument("--duration", type=float, default=None, help="Optional duration (seconds) for analysis window")
    parser.add_argument("--sr", type=int, default=16000, help="Audio sample rate (Hz) for extraction")
    parser.add_argument("--hop", type=int, default=512, help="Hop length for onset frames")
    parser.add_argument("--fps", type=float, default=None, help="Force FPS for frame conversion (uses A's FPS if omitted)")
    parser.add_argument("--ref", type=str, default=None, help="Reference filename to use in auto-scan mode (exact filename match)")
    parser.add_argument("--pairwise", action="store_true", help="Compute all pairwise offsets among discovered files")
    parser.add_argument("--scan-dir", type=str, default=None,
                        help="Directory to scan for videos (default: directory where THIS script resides)")
    return parser.parse_args()

def print_table(rows):
    # rows: list of dicts with keys: A, B, off_s, corr, fps_a, fps_b, frames_a, frames_b
    # Determine widths
    headers = ["Reference (A)", "Aligned (B)", "Offset (s)", "Frames@A", "Frames@B", "Corr"]
    lines = []
    widths = [len(h) for h in headers]
    for r in rows:
        cols = [
            os.path.basename(r["A"]),
            os.path.basename(r["B"]),
            f'{r["off_s"]:+.3f}',
            f'{r["frames_a"]:+d}' if r["frames_a"] is not None else "n/a",
            f'{r["frames_b"]:+d}' if r["frames_b"] is not None else "n/a",
            f'{r["corr"]:.2f}'
        ]
        widths = [max(w, len(c)) for w, c in zip(widths, cols)]
        lines.append(cols)
    # Print header
    fmt = " | ".join("{:<" + str(w) + "}" for w in widths)
    sep = "-+-".join("-" * w for w in widths)
    print(fmt.format(*headers))
    print(sep)
    for cols in lines:
        print(fmt.format(*cols))

def main():
    check_ffmpeg()
    args = parse_args()

    # Determine mode
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scan_dir = args.scan_dir or script_dir

    # If both A and B provided => single pair
    if args.video_a and args.video_b:
        files = [args.video_a, args.video_b]
        pairs = [(args.video_a, args.video_b)]
    else:
        # Auto-scan mode
        files = discover_videos(scan_dir)
        if len(files) < 2:
            print(f"ERROR: Found {len(files)} video(s) in '{scan_dir}'. Need at least 2.", file=sys.stderr)
            sys.exit(2)
        # Choose reference
        ref_path = None
        if args.ref is not None:
            # Match by basename
            for f in files:
                if os.path.basename(f) == args.ref:
                    ref_path = f
                    break
            if ref_path is None:
                print(f"ERROR: --ref '{args.ref}' not found in scan list.", file=sys.stderr)
                print("Files discovered:")
                for f in files:
                    print(" ", os.path.basename(f))
                sys.exit(2)
        else:
            ref_path = files[0]  # default to first (sorted) file

        if args.pairwise:
            pairs = list(combinations(files, 2))
        else:
            pairs = [(ref_path, f) for f in files if f != ref_path]

        print(f"Discovered {len(files)} video files in: {scan_dir}")
        for f in files:
            print(" -", os.path.basename(f))
        print("\nReference:", os.path.basename(ref_path) if not args.pairwise else "(pairwise mode)")
        print(f"Planned comparisons: {len(pairs)}\n")

    rows = []
    # Progress bar over pair count gives an ETA for total completion
    with tqdm(total=len(pairs), desc="Alignments", unit="pair") as pbar:
        for A, B in pairs:
            try:
                off_s, corr = estimate_offset_seconds(
                    A, B, start=args.start, duration=args.duration, sr=args.sr, hop_length=args.hop
                )
                # FPS handling
                fps_a = args.fps if args.fps else get_fps(A)
                fps_b = args.fps if args.fps else get_fps(B)
                frames_a = int(round(off_s * fps_a)) if fps_a else None
                frames_b = int(round(off_s * fps_b)) if fps_b else None
                rows.append({
                    "A": A, "B": B, "off_s": off_s, "corr": corr,
                    "fps_a": fps_a, "fps_b": fps_b, "frames_a": frames_a, "frames_b": frames_b
                })
            except subprocess.CalledProcessError as e:
                print(f"ffmpeg error processing pair:\n  A={A}\n  B={B}\n  {e}", file=sys.stderr)
                rows.append({
                    "A": A, "B": B, "off_s": float("nan"), "corr": 0.0,
                    "fps_a": None, "fps_b": None, "frames_a": None, "frames_b": None
                })
            finally:
                pbar.update(1)

    print("\nResults (positive => B ahead of A; seek B backward by this amount):\n")
    print_table(rows)
    print("\nNotes:")
    print(" - 'Frames@A' uses A's FPS; 'Frames@B' uses B's FPS (auto-detected unless --fps is provided).")
    print(" - Correlation 'Corr' is a rough confidence indicator only; inspect manually if values are low.")
    print(" - For perfect alignment, consider testing multiple windows (e.g., --start and --duration).")

if __name__ == "__main__":
    main()
