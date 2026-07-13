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

### Benchmark the full-resolution quality PlaneStats candidate

`quality-planestats-candidate` is a benchmark-tool-only experiment. It is not the
production `quality` mode, is not accepted by application config, and never reads
or writes the analysis metric cache. Each candidate artifact still runs the
production `quality` backend as its paired baseline. Candidate runs require
`--metric-cache-policy cold`; the tool rejects `reuse` so a quality cache hit
cannot be compared with fresh candidate computation.

Run the candidate on the same Windows machine with three cold repetitions for
each required source class. Replace the SDR and animation paths with fixed local
cases; keep those exact files for every rerun. The selected analysis source must
have an adjacent warm `.lwi` index.

```powershell
$WitchReference = (Resolve-Path -LiteralPath 'comparison_videos\The Witch [2015] 2160p UHD BDRip DV HDR10 x265 DTS-HD MA 5.1-Kira.Clip.mkv').Path
$WitchComparison = (Resolve-Path -LiteralPath 'comparison_videos\The.VVitch.A.New-England.Folktale.2015.2160p.UHD.BluRay.DTS-HD.MA.5.1.DoVi.x265-CtrlHD.Clip.mkv').Path
$SdrReference = (Resolve-Path -LiteralPath 'C:\Benchmarks\sdr-8bit\reference.mkv').Path
$SdrComparison = (Resolve-Path -LiteralPath 'C:\Benchmarks\sdr-8bit\comparison.mkv').Path
$AnimationReference = (Resolve-Path -LiteralPath 'C:\Benchmarks\animation-grain\reference.mkv').Path
$AnimationComparison = (Resolve-Path -LiteralPath 'C:\Benchmarks\animation-grain\comparison.mkv').Path

uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/quality-planestats-candidate-witch-4k-hdr.json `
  --mode quality-planestats-candidate `
  --window-start 0 `
  --window-end-exclusive 2400 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  $WitchReference $WitchComparison

uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/quality-planestats-candidate-sdr-8bit.json `
  --mode quality-planestats-candidate `
  --window-start 0 `
  --window-end-exclusive 2400 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  $SdrReference $SdrComparison

uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/quality-planestats-candidate-animation-grain.json `
  --mode quality-planestats-candidate `
  --window-start 0 `
  --window-end-exclusive 2400 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  $AnimationReference $AnimationComparison
```

If a case uses a non-default reference, analysis source, effective FPS, trim, or
active rectangle, also pass the exact `--selection-domain` token from its
prepared production run. Use a representative fixed window for each clip; do
not force `0..2400` when that range misses the content class being tested.

Inspect all three artifacts with this compact PowerShell summary:

```powershell
$CandidateFiles = @(
  'generated/quality-planestats-candidate-witch-4k-hdr.json',
  'generated/quality-planestats-candidate-sdr-8bit.json',
  'generated/quality-planestats-candidate-animation-grain.json'
)

$CandidateFiles | ForEach-Object {
  $Report = Get-Content $_ -Raw | ConvertFrom-Json
  $Candidate = $Report.comparisons.'quality-planestats-candidate'
  $Dense = $Candidate.dense_metric_differences
  $TopK = $Candidate.exact_top_k_ordering
  $QualityCompute = $Report.quality.timing_summary.compute_pipeline_seconds
  $CandidateCompute = $Candidate.timing_summary.compute_pipeline_seconds
  $QualityTrials = @($Report.quality.trials)
  $CandidateTrials = @($Candidate.trials)
  $MedianDelta = $QualityCompute.median - $CandidateCompute.median
  $ImprovementPercent = if ($QualityCompute.median -gt 0) {
    100 * $MedianDelta / $QualityCompute.median
  } else { 0 }
  $NoiseBand = [math]::Max($QualityCompute.pstdev, $CandidateCompute.pstdev)
  $OutsideNoise = $MedianDelta -gt $NoiseBand
  $FasterPairedTrials = @(0..($CandidateTrials.Count - 1) | Where-Object {
    $CandidateTrials[$_].compute_pipeline_seconds -lt $QualityTrials[$_].compute_pipeline_seconds
  }).Count
  $RequiredPairedWins = [math]::Floor($QualityTrials.Count / 2) + 1
  $QualityColdMisses = @($QualityTrials | Where-Object { $_.cache_state -eq 'miss' }).Count
  $CandidateBypasses = @($CandidateTrials | Where-Object { $_.cache_state -eq 'bypassed' }).Count
  $FrameCountsEqual = $Report.quality.metadata.frame_count -eq $Candidate.metadata.frame_count
  $WindowDomainsEqual =
    ($Report.quality.window.start_frame -eq $Candidate.window.start_frame) -and
    ($Report.quality.window.end_frame_exclusive -eq $Candidate.window.end_frame_exclusive)
  $TrialCountGate = ($QualityTrials.Count -ge 3) -and
    ($CandidateTrials.Count -eq $QualityTrials.Count)
  $DenseGate = $Dense.luminance.allclose -and $Dense.motion.allclose
  $SelectionGate = $Candidate.exact_selected_equality.dark -and
    $Candidate.exact_selected_equality.bright -and
    $Candidate.exact_selected_equality.motion
  $TopKGate = $TopK.dark.equal -and $TopK.bright.equal -and $TopK.motion.equal
  $GateAPass = $FrameCountsEqual -and $WindowDomainsEqual -and $TrialCountGate -and
    $DenseGate -and $SelectionGate -and
    $TopKGate -and ($QualityColdMisses -eq $QualityTrials.Count) -and
    ($CandidateBypasses -eq $CandidateTrials.Count) -and
    ($FasterPairedTrials -ge $RequiredPairedWins) -and
    ($ImprovementPercent -ge 5) -and $OutsideNoise

  [PSCustomObject]@{
    File = Split-Path $_ -Leaf
    QualityComputeMedian = [math]::Round($QualityCompute.median, 3)
    QualityComputePstdev = [math]::Round($QualityCompute.pstdev, 3)
    CandidateComputeMedian = [math]::Round($CandidateCompute.median, 3)
    CandidateComputePstdev = [math]::Round($CandidateCompute.pstdev, 3)
    MedianDelta = [math]::Round($MedianDelta, 3)
    ImprovementPercent = [math]::Round($ImprovementPercent, 2)
    NoiseBand = [math]::Round($NoiseBand, 3)
    OutsideNoise = $OutsideNoise
    FasterPairedTrials = $FasterPairedTrials
    RequiredPairedWins = $RequiredPairedWins
    QualityColdMisses = $QualityColdMisses
    CandidateBypasses = $CandidateBypasses
    FrameCountsEqual = $FrameCountsEqual
    WindowDomainsEqual = $WindowDomainsEqual
    TrialCountGate = $TrialCountGate
    LumaAllclose = $Dense.luminance.allclose
    LumaMaxError = $Dense.luminance.max_absolute_error
    LumaMeanError = $Dense.luminance.mean_absolute_error
    LumaFirstDifference = $Dense.luminance.first_differing_index
    LumaFirstDifferenceSourceFrame = $Dense.luminance.first_differing_source_frame
    LumaFirstOutsideTolerance = $Dense.luminance.first_outside_tolerance_index
    MotionAllclose = $Dense.motion.allclose
    MotionMaxError = $Dense.motion.max_absolute_error
    MotionMeanError = $Dense.motion.mean_absolute_error
    MotionFirstDifference = $Dense.motion.first_differing_index
    MotionFirstDifferenceSourceFrame = $Dense.motion.first_differing_source_frame
    MotionFirstOutsideTolerance = $Dense.motion.first_outside_tolerance_index
    DarkSelectedExact = $Candidate.exact_selected_equality.dark
    BrightSelectedExact = $Candidate.exact_selected_equality.bright
    MotionSelectedExact = $Candidate.exact_selected_equality.motion
    DarkTopKExact = $TopK.dark.equal
    BrightTopKExact = $TopK.bright.equal
    MotionTopKExact = $TopK.motion.equal
    QualityCpuToWallMedian = $Report.quality.timing_summary.cpu_to_wall_ratio.median
    CandidateCpuToWallMedian = $Candidate.timing_summary.cpu_to_wall_ratio.median
    QualityPeakRssBytes = $QualityTrials[-1].peak_rss_bytes
    CandidatePeakRssBytes = $CandidateTrials[-1].peak_rss_bytes
    GateAPass = $GateAPass
  }
} | Format-Table -AutoSize
```

Use `compute_pipeline_seconds`, not raw `analyze_seconds`, for the candidate
performance decision. It subtracts only cache lookup and cache write, retaining
source loading and metric work so the cache-bypassing candidate cannot gain a
false timing advantage. Accept quality only when both dense arrays are allclose
at `rtol=0, atol=1e-12`, all selected-category booleans are true, and all exact
top-K booleans are true for every case. Then apply the timing and noise gate from
the active performance plan. `first_differing_index` and
`first_differing_source_frame` report the first raw float inequality even when it
is within tolerance; the separate `first_outside_tolerance_*` fields explain an
`allclose = false` result. The displayed `GateAPass` combines every frozen
objective criterion available in the artifact. CPU-to-wall medians remain
visible for separate regression review. Standard-library peak RSS is unavailable
on Windows and remains `$null`; do not convert it to zero or treat it as proof of
unchanged memory use.

The current `--window-start` and `--window-end-exclusive` options slice the dense
arrays for selection and comparison only after full-source metric calculation.
They do not yet benchmark window-bounded metric computation; that is a separate
later experiment.

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

### 2026-07-13: Full-resolution quality PlaneStats candidate rejected

Benchmark artifact:
`generated/quality-planestats-candidate-witch-4k-hdr.json`

The three-repetition cold-cache Windows run compared production NumPy `quality`
with the benchmark-only full-resolution PlaneStats candidate on the established
4K HDR Witch source, using the prepared dimension-derived active rectangle and
frames `0..2400`.

| Measure | Production quality | Candidate |
| --- | ---: | ---: |
| Median compute pipeline | 235.086s | 64.009s |
| Population standard deviation | 0.853s | 0.556s |
| Median process CPU | 585.516s | 563.266s |
| Median CPU-to-wall ratio | 2.488 | 8.799 |

The candidate was 3.67x faster, a 72.77% reduction in median compute time. The
171.08-second median improvement was far outside the 0.853-second noise band,
and every paired candidate trial was faster. All three quality trials were
proven cache misses and every candidate trial bypassed the metric cache.

Quality evidence:

- luminance passed `allclose(rtol=0, atol=1e-12)`, with maximum absolute error
  `5.55e-17`;
- motion failed that frozen lossless threshold beginning at source frame 1,
  with maximum absolute error `8.80e-9` and mean absolute error `4.21e-10`;
- dark, bright, and motion selected-frame lists were exactly identical; and
- dark, bright, and motion top-50 ordering was exactly identical.

Decision: reject production quality migration. The speedup and practical
selection agreement do not override the predeclared lossless gate, and the
tolerance is not loosened after observing the result. Additional source classes
cannot make a mandatory per-case failure pass, so the 8-bit SDR and
animation/grain-heavy candidate runs are unnecessary for this migration
decision. Keep NumPy as production `quality`; keep the candidate benchmark-only
as reproducible evidence. Proceed independently with exact window-bounded metric
calculation for NumPy `quality` and synchronous PlaneStats `performance`.

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
