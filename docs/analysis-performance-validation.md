# Analysis Performance Validation

Use `tools/benchmark_analysis_tiers.py` to compare `performance` against
`quality` on local clips that are not committed to the repository.

Example:

```bash
.venv/bin/python tools/benchmark_analysis_tiers.py \
  --root /path/to/workspace \
  --config config/config.toml \
  --output generated/analysis-tier-benchmark.json \
  --window-start 0 \
  --window-end-exclusive 2400 \
  reference.mkv comparison.mkv
```

The benchmark defaults to three cold-metric-cache repetitions per mode. It
deletes only the exact mode/domain metric cache entry before each timed trial,
rotates mode order deterministically between repetitions, and runs the optional
decode-throughput baseline only after all timed mode trials. Use
`--metric-cache-policy reuse` to measure cache reuse instead, or
`--repetitions N` to change the sample count.

Use `--require-warm-source-index` when a comparison is intended to measure warm
L-SMASH source indexes. The check recognizes adjacent `.lwi` files and fails
before timed trials when the selected analysis source has no detected index. It
never deletes source indexes. Use `--skip-decode-baseline` to omit the post-trial
concurrent PlaneStats throughput baseline.

Pass `--inspect-frame-types` to run an additional, untimed ffprobe scan after the
mode trials. That scan records I/P/B counts, keyframe count, and keyframe-gap
statistics for GOP-sensitive experiments. It can be expensive on long sources
and is intentionally opt-in. `--ffprobe-timeout` bounds each inspection command.

The script writes a stable structured JSON artifact with the quality baseline,
candidate mode comparisons, selected-frame overlap, nearest-frame distances,
miss rates, Spearman rank correlations, top-K overlap, algorithm identity, and
warnings for unavailable runtime details. Each mode includes individual trials
and aggregate count/min/max/mean/median/population-standard-deviation summaries
for total analysis, selection, total trial, process CPU, CPU-to-wall ratio, and
every observed analysis subphase. Trials also record proven cache hit/miss state,
cache-write outcome, and the process-wide peak RSS observed by that point.

Detailed subphases distinguish cache lookup, source load, graph construction,
frame rendering, metric computation/property reads, and cache writing. The
runtime section records Python, platform, CPU count, FFmpeg/ffprobe,
VapourSynth/API versions, core thread count, and core cache limit. Source facts
record stream/container metadata and detected adjacent source indexes. Peak RSS
is process-wide and cumulative; compare it as a high-water mark rather than a
per-trial allocation delta. It is reported as `null` on Windows, where the
standard-library high-water-mark API used by this benchmark is unavailable.

By default, the script renders trial-level Rich progress to stderr while keeping
stdout reserved for the final output JSON path. Pass `--no-progress` when a
scripted run needs no terminal progress display.

Pass the exact source-frame window used for review with `--window-start` and
`--window-end-exclusive`. Pass the orchestration selection-domain token from a
prepared run with `--selection-domain` whenever the benchmark uses a non-default
reference or analysis source, active-rect detection policy, source trim, effective
FPS override, or explicit active rectangle. The tool rejects those non-default
domains without the token so its cache cannot alias production analysis state.
Without explicit window arguments, the script records warnings and compares the
full analysis metric domain.

The benchmark script uses the configured `paths.generated_dir` for analysis
cache by default and resolves explicit `sources.analysis_source` selectors before
running metrics. It supports per-source `effective_fps` overrides and explicit
`sources.overrides.<selector>.active_rect` overrides for the selected analysis
source. Active rectangles affect both `quality` and `performance` metric arrays
and cache identity, so benchmark evidence for letterboxed or pillarboxed sources
should use the same configured analysis source and explicit active rectangle as
a normal run. When no explicit active rectangle is configured, the benchmark
loads `generated/clip_probe.toml` and applies the same static active-picture
resolver used by preparation so metric metadata preserves the prepared rectangle,
source, detection mode, and resolver algorithm ID. If the probe snapshot is not
available, the tool fails instead of fabricating full-frame provenance; run a
normal preparation path first or configure an explicit active rectangle for the
selected analysis source. For `screenshots.active_rect_detection = "auto"`, the
benchmark cannot run content refinement by itself and fails when the prepared
static rectangle remains full-frame. Normal runtime analysis uses the resolved
active picture prepared from explicit `sources.overrides.<selector>.active_rect`,
trusted static metadata, configured dimension/aspect-ratio inference, opt-in
content detection, or full-frame fallback. The benchmark tool does not support
`sources.analysis_source = "fastest"` or automatic `sources.match_fps` policies;
use an explicit analysis source and explicit effective-FPS overrides for
benchmark evidence.

## Local Evidence

This evidence is local, hardware-dependent, and not a full validation matrix.
Treat it as support for tuning decisions, not a release-wide guarantee.

### 2026-06-10: The Witch UHD Clip Pair, Mode Simplification Decision

Benchmark artifact:
`generated/analysis-tier-benchmark-warm-index.json`

This run compared the old three-mode experiment before the public surface was
reduced to `quality` and `performance`. The result favored keeping the
320px Bicubic dense PlaneStats implementation as `performance` and removing the
extra experimental low-resolution mode.

Inputs:

- `The Witch [2015] 2160p UHD BDRip DV HDR10 x265 DTS-HD MA 5.1-Kira.Clip.mkv`
- `The.VVitch.A.New-England.Folktale.2015.2160p.UHD.BluRay.DTS-HD.MA.5.1.DoVi.x265-CtrlHD.Clip.mkv`

Configuration:

- `config/benchmark.config.toml`
- `sources.analysis_source = "reference"`
- `sources.match_fps = "disabled"`
- Window: frames `0..2400`
- Counts: 20 random, 10 dark, 10 bright, 10 motion
- Warm source indexes were present before this run.
- No orchestration selection-domain token was provided, so cache identity may
  differ from a full run with trims, active rectangles, or source overrides.

Timing:

| Mode | Analyze time | Relative to `quality` |
| --- | ---: | ---: |
| `quality` | 430.34s | 1.00x |
| `performance` | 130.27s | 3.30x faster |
| removed experimental mode | 171.11s | 2.51x faster |

Selection agreement versus `quality`:

| Mode | Category | Exact overlap | Miss rate at tolerance | Max nearest distance |
| --- | --- | ---: | ---: | ---: |
| `performance` | bright | 10/10 | 0.0 | 0 |
| `performance` | dark | 7/10 | 0.3 | 32 |
| `performance` | motion | 10/10 | 0.0 | 0 |
| removed experimental mode | bright | 9/10 | 0.0 | 1 |
| removed experimental mode | dark | 6/10 | 0.3 | 102 |
| removed experimental mode | motion | 8/10 | 0.2 | 1036 |

Ranking agreement:

| Mode | Luminance Spearman | Motion Spearman | Highest motion top-50 overlap |
| --- | ---: | ---: | ---: |
| `performance` | 0.999970 | 0.957701 | 50/50 |
| removed experimental mode | 0.999969 | 0.689946 | 45/50 |

Decision signal:

- `performance` is the preferred candidate for this clip pair: it was faster
  than `quality` and the removed experimental mode, preserved all bright and
  motion selections, and kept high motion-rank agreement.
- The removed experimental mode is not accepted: it was slower than
  `performance`, had a large motion miss, and had materially weaker motion-rank
  agreement.
- The `performance` dark-frame differences should be visually reviewed before
  treating this clip class as validated.

## Clip Classes

Manual validation should cover local examples of:

- SDR 8-bit live action.
- HDR PQ or HLG high-bit-depth source.
- Animation with flat fills and line art.
- Grainy or noisy film source.
- Static low-motion scene.
- High-motion action scene.
- Rapid camera pan.
- Hard cuts.
- Fades to black and from black.
- One-frame or very short flashes.
- Letterboxed or pillarboxed source.
- Subtitles, credits, logos, or UI overlays.
- Clipped highlights and near-black shadow detail.
- Short clip near `analysis.min_window_seconds`.
- Source trims and effective FPS overrides.

If a class is unavailable locally, record it as unavailable in the handoff. Do
not treat absent classes as validated.

## Review Labels

Inspect category misses beyond tolerance and label each as one of:

- `acceptable near-duplicate`
- `downscale lost small local feature`
- `temporal sampling missed event`
- `tie/ranking ambiguity`
- `source trim/window issue`
- `bug requiring implementation fix`

Performance tolerances are 2 frames for dark/bright and 3 frames for motion.
