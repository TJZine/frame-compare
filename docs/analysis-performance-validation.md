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

## Windows Baseline Collection Before Implementation

Run this workflow from a source checkout on the Windows machine that will be
used for performance decisions. The benchmark is a developer tool under
`tools/`; it is not currently exposed as a command in the packaged portable
application. The checkout must include commits `9ed39cce` and `719ad206`.

### 1. Stabilize the machine and checkout

- Connect AC power and use the same Windows power mode for every run.
- Close unrelated CPU-, GPU-, disk-, and memory-intensive applications.
- Keep the same Frame Compare commit, Python environment, config, source files,
  source-frame window, and source indexes throughout baseline collection.
- Do not compare results collected while Windows Update, antivirus scanning, or
  media indexing is actively consuming resources.

From PowerShell at the repository root:

```powershell
git log -2 --oneline
uv sync --group dev --frozen
uv run --no-sync frame-compare doctor --json
```

Record the current commit with each evidence set:

```powershell
git rev-parse HEAD
```

### 2. Select a fixed corpus and config

Start with the clip pair that motivated the performance work, then add locally
available representatives from the [clip-class list](#clip-classes). Use the
same ordered inputs for every baseline and later candidate run. Do not infer a
general speedup from one codec, resolution, or content class.

Create a local, uncommitted benchmark config if one is not already available:

```powershell
uv run --no-sync frame-compare wizard --root . --config config/benchmark.config.toml
```

For the simplest reproducible baseline, use the first input as both reference
and analysis source, disable automatic FPS matching, and keep the default
aspect-ratio active-rect policy:

```toml
[sources]
analysis_source = "reference"
match_fps = "disabled"

[screenshots]
active_rect_detection = "aspect_ratio"

[analysis]
random_frame_count = 20
dark_frame_count = 10
bright_frame_count = 10
motion_frame_count = 10
```

The benchmark config is local evidence and may contain machine-specific paths or
secrets. Store or share a redacted copy with the result JSON rather than
committing it by default.

### 3. Prepare probe data and warm the source index

Run the same inputs once through the normal application path before timing. This
creates or refreshes `generated/clip_probe.toml` and lets L-SMASH create its
adjacent `.lwi` source index. For an input directory containing only the fixed
case under test:

```powershell
uv run --no-sync frame-compare run `
  --root . `
  --config config/benchmark.config.toml `
  --input 'C:\Benchmarks\case-01' `
  --no-upload
```

The benchmark's cold policy deletes only the exact analysis metric cache entry;
it intentionally preserves the `.lwi` source index. Use
`--require-warm-source-index` in timed runs so a missing selected-source index
fails instead of silently turning one result into an index-generation test.

Non-default references or analysis sources, trims, effective-FPS overrides,
explicit active rectangles, and non-default active-rect detection require the
exact `--selection-domain` token from the prepared production run. Establish the
default-domain baseline first unless the experiment specifically targets one of
those features.

### 4. Run the cold baseline

Set paths once in PowerShell, then run three repetitions per mode. A 2,400-frame
window is a useful initial sample when it contains representative content; use a
different fixed window when the target event lies elsewhere.

```powershell
$Reference = 'C:\Benchmarks\case-01\reference.mkv'
$Comparison = 'C:\Benchmarks\case-01\comparison.mkv'

uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/case-01-windows-cold.json `
  --window-start 0 `
  --window-end-exclusive 2400 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  --inspect-frame-types `
  $Reference $Comparison
```

This is the primary algorithm-performance artifact. It includes the post-trial
decode/PlaneStats baseline. If a run is noisy or will decide between close
candidates, repeat it with five repetitions rather than combining results from
different machine conditions.

### 5. Run the cache-reuse control

Run this after the cold baseline so matching metric caches exist. GOP inspection
and the decode baseline need not be repeated:

```powershell
uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/case-01-windows-reuse.json `
  --window-start 0 `
  --window-end-exclusive 2400 `
  --repetitions 3 `
  --metric-cache-policy reuse `
  --require-warm-source-index `
  --skip-decode-baseline `
  $Reference $Comparison
```

The reuse control measures cache loading and frame selection, not uncached
brightness or motion calculation. Confirm that its trials report cache hits;
do not substitute it for the cold result.

### 6. Preserve and interpret the evidence

Keep the following together for each case:

- cold and reuse JSON artifacts;
- redacted benchmark config;
- `git rev-parse HEAD` output;
- input ordering and exact source-frame window;
- Windows power mode and notes about unusual background activity;
- unavailable clip classes and visual labels for selection misses.

Use the evidence in this order before choosing an implementation:

1. Confirm cold trials are cache misses with successful cache writes and reuse
   trials are cache hits.
2. Use median time as the primary result and population standard deviation as
   the noise warning. Re-run unstable cases before drawing conclusions.
3. Compare `frame_render` against the decode/PlaneStats baseline. A small gap
   points toward decode, VapourSynth scheduling, or graph costs; a large gap
   leaves more room in the brightness/motion strategy itself.
4. Compare graph construction, metric/property work, source loading, and cache
   phases. Optimize the measured dominant phase rather than lowering unrelated
   knobs.
5. Compare brightness and motion rank correlation, top-K overlap, category miss
   rates, and nearest-frame distances against `quality`.
6. Visually review misses outside tolerance using the [review labels](#review-labels).
7. Choose a candidate only after its likely speed ceiling and acceptable quality
   loss are supported across the available clip classes.

Do not change the existing modes before these baseline artifacts are saved. For
each later implementation experiment, rerun the same cold command on the same
machine, inputs, config, and windows, writing a new output file rather than
overwriting the baseline.

### 7. Benchmark the combined and concurrent PlaneStats experiments

The checked-in Witch baseline at commit `5202aa65` measured a 232.49-second
`quality` median and a 115.03-second `performance` median. Two later commits
isolate the proposed rendering improvements:

| Commit | Experiment |
| --- | --- |
| `d058d354` | Calculate luminance and motion in one synchronous PlaneStats traversal. |
| `b2f6c5ee` | Evaluate that combined graph with concurrent VapourSynth frame iteration. |

Run both commits on the same Windows machine and source indexes used for the
baseline. The following PowerShell block uses the checked-in Witch filenames,
keeps the original three-repetition cold-cache policy, writes distinct result
files, and returns to the branch that was active when the block started. It
omits the optional frame-type scan because the baseline already attempted that
untimed inspection; the decode baseline still runs as a machine-condition
control.

Before running it, confirm `git status --short` shows no tracked modifications.
Untracked benchmark JSON outputs do not prevent the temporary detached checkouts.

```powershell
$ReturnBranch = git branch --show-current
if (-not $ReturnBranch) {
  $ReturnBranch = 'stage1'
}

$Reference = (Resolve-Path -LiteralPath 'comparison_videos\The Witch [2015] 2160p UHD BDRip DV HDR10 x265 DTS-HD MA 5.1-Kira.Clip.mkv').Path
$Comparison = (Resolve-Path -LiteralPath 'comparison_videos\The.VVitch.A.New-England.Folktale.2015.2160p.UHD.BluRay.DTS-HD.MA.5.1.DoVi.x265-CtrlHD.Clip.mkv').Path

try {
  git switch --detach d058d354
  if ($LASTEXITCODE -ne 0) { throw 'Could not check out d058d354' }

  uv run --no-sync python tools/benchmark_analysis_tiers.py `
    --root . `
    --config config/benchmark.config.toml `
    --output generated/analysis-tier-benchmark-witch-combined-sync.json `
    --window-start 0 `
    --window-end-exclusive 2400 `
    --repetitions 3 `
    --metric-cache-policy cold `
    --require-warm-source-index `
    $Reference $Comparison
  if ($LASTEXITCODE -ne 0) { throw 'Combined synchronous benchmark failed' }

  git switch --detach b2f6c5ee
  if ($LASTEXITCODE -ne 0) { throw 'Could not check out b2f6c5ee' }

  uv run --no-sync python tools/benchmark_analysis_tiers.py `
    --root . `
    --config config/benchmark.config.toml `
    --output generated/analysis-tier-benchmark-witch-combined-concurrent.json `
    --window-start 0 `
    --window-end-exclusive 2400 `
    --repetitions 3 `
    --metric-cache-policy cold `
    --require-warm-source-index `
    $Reference $Comparison
  if ($LASTEXITCODE -ne 0) { throw 'Combined concurrent benchmark failed' }
}
finally {
  git switch $ReturnBranch
}
```

After both runs, produce a compact comparison table in PowerShell:

```powershell
$ResultFiles = @(
  'generated/analysis-tier-benchmark-witch-baseline.json',
  'generated/analysis-tier-benchmark-witch-combined-sync.json',
  'generated/analysis-tier-benchmark-witch-combined-concurrent.json'
)

$ResultFiles | ForEach-Object {
  $Report = Get-Content $_ -Raw | ConvertFrom-Json
  $Performance = $Report.comparisons.performance
  $Phases = $Performance.timing_summary.phase_timings_seconds
  $RenderSeconds = if ($null -ne $Phases.performance_frame_render) {
    $Phases.performance_frame_render.median
  } else {
    $Phases.luminance_frame_render.median + $Phases.motion_frame_render.median
  }

  [PSCustomObject]@{
    File = Split-Path $_ -Leaf
    QualitySeconds = [math]::Round($Report.quality.analyze_seconds, 2)
    PerformanceSeconds = [math]::Round($Performance.analyze_seconds, 2)
    Speedup = [math]::Round(
      $Report.quality.analyze_seconds / $Performance.analyze_seconds,
      2
    )
    RenderSeconds = [math]::Round($RenderSeconds, 2)
    TrialStdDev = [math]::Round(
      $Performance.timing_summary.analyze_seconds.pstdev,
      2
    )
    BrightMissRate = $Performance.comparisons.bright.miss_rate_at_tolerance
    DarkMissRate = $Performance.comparisons.dark.miss_rate_at_tolerance
    MotionMissRate = $Performance.comparisons.motion.miss_rate_at_tolerance
    LuminanceSpearman = [math]::Round($Performance.ranking.luminance_spearman, 6)
    MotionSpearman = [math]::Round($Performance.ranking.motion_spearman, 6)
  }
} | Format-Table -AutoSize
```

Acceptance for these implementation-only optimizations requires equivalent
performance metric arrays in automated strategy tests and equivalent selected
frames in the Windows artifacts, not merely results within the looser tier
tolerances. The benchmark JSON does not serialize the full dense metric arrays.
Treat any changed dark, bright, or motion selection as a regression to
investigate before accepting the timing improvement. Compare the synchronous
artifact against the baseline to isolate the combined traversal, then compare
the concurrent artifact against the synchronous artifact to isolate scheduling.

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
