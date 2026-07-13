# Analysis Performance Validation

Use `tools/benchmark_analysis_tiers.py` to compare production and benchmark-only
analysis backends on local clips that are not committed to the repository.

For the curated cross-run results, retained evidence, and cleanup policy, see
[Analysis Benchmark History](analysis-benchmark-history.md). This file remains
the procedural validation runbook.

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
  $PracticalDenseGate =
    ($Dense.luminance.max_absolute_error -le 1e-7) -and
    ($Dense.motion.max_absolute_error -le 1e-7)
  $SelectionGate = $Candidate.exact_selected_equality.dark -and
    $Candidate.exact_selected_equality.bright -and
    $Candidate.exact_selected_equality.motion
  $TopKGate = $TopK.dark.equal -and $TopK.bright.equal -and $TopK.motion.equal
  $GateAPass = $FrameCountsEqual -and $WindowDomainsEqual -and $TrialCountGate -and
    $PracticalDenseGate -and $SelectionGate -and
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
    PracticalDenseGate = $PracticalDenseGate
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
false timing advantage. Accept the practical quality migration only when
luminance and motion each have maximum absolute error no greater than `1e-7`,
all selected-category booleans are true, and all exact top-K booleans are true
for every case. The stricter `allclose(rtol=0, atol=1e-12)` result remains
visible as a diagnostic, but it is no longer the migration gate. Then apply the
timing and noise gate from the active performance plan. `first_differing_index` and
`first_differing_source_frame` report the first raw float inequality even when it
is within tolerance; the separate `first_outside_tolerance_*` fields explain an
`allclose = false` result. The displayed `GateAPass` combines every frozen
objective criterion available in the artifact. CPU-to-wall medians remain
visible for separate regression review. Standard-library peak RSS is unavailable
on Windows and remains `$null`; do not convert it to zero or treat it as proof of
unchanged memory use.

### Benchmark the dense fast-decoder performance candidates

These benchmark-only modes test whether a deliberately cheaper software decode
can make `performance` meaningfully distinct after full-resolution PlaneStats
becomes `quality`:

| Mode | Decoder | Metric graph |
| --- | --- | --- |
| `performance` | Normal production decoder settings | Current dense 320px PlaneStats |
| `performance-skip-loop-filter-candidate` | FFmpeg `skip_loop_filter=all`, automatic decoder threads | Current dense 320px PlaneStats |
| `performance-skip-loop-filter-max-threads-candidate` | The same decoder option with the host logical CPU count passed explicitly | Current dense 320px PlaneStats |

All three modes analyze every source frame. The candidates preserve dense source
frame numbering and adjacent-frame motion semantics; their intended quality loss
comes from skipping decoder loop filtering, not temporal sampling. They remain
invalid application config values and bypass the production metric cache. The
decoder option is supported by the bundled L-SMASH Works `ff_options` seam and
the FFmpeg `skip_loop_filter` codec option:
[L-SMASH Works options](https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works/blob/0079a06ee384061ecdadd0de03df4e0493dd56ab/VapourSynth/README.md),
[FFmpeg codec options](https://ffmpeg.org/ffmpeg-codecs.html).

Run the full matrix in one process so mode order rotates under the same machine
conditions. Use the exact same three clip classes and windows as the quality
candidate gate:

```powershell
uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-decoder-candidates-witch-4k-hdr.json `
  --mode quality-planestats-candidate `
  --mode performance `
  --mode performance-skip-loop-filter-candidate `
  --mode performance-skip-loop-filter-max-threads-candidate `
  --window-start 0 `
  --window-end-exclusive 2400 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  --inspect-frame-types `
  $WitchReference $WitchComparison

uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-decoder-candidates-sdr-8bit.json `
  --mode quality-planestats-candidate `
  --mode performance `
  --mode performance-skip-loop-filter-candidate `
  --mode performance-skip-loop-filter-max-threads-candidate `
  --window-start 0 `
  --window-end-exclusive 2400 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  --inspect-frame-types `
  $SdrReference $SdrComparison

uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-decoder-candidates-animation-grain.json `
  --mode quality-planestats-candidate `
  --mode performance `
  --mode performance-skip-loop-filter-candidate `
  --mode performance-skip-loop-filter-max-threads-candidate `
  --window-start 0 `
  --window-end-exclusive 2400 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  --inspect-frame-types `
  $AnimationReference $AnimationComparison
```

Summarize all three outputs without manually calculating speed or retention:

```powershell
$DecoderFiles = @(
  'generated/analysis-decoder-candidates-witch-4k-hdr.json',
  'generated/analysis-decoder-candidates-sdr-8bit.json',
  'generated/analysis-decoder-candidates-animation-grain.json'
)
$PerformanceModes = @(
  'performance',
  'performance-skip-loop-filter-candidate',
  'performance-skip-loop-filter-max-threads-candidate'
)

$DecoderFiles | ForEach-Object {
  $Report = Get-Content $_ -Raw | ConvertFrom-Json
  foreach ($Mode in $PerformanceModes) {
    $Timing = $Report.quality_planestats_candidate_timing_comparisons.PSObject.Properties[$Mode].Value
    $ComparisonResult = $Report.comparisons.PSObject.Properties[$Mode].Value
    $Retention = $ComparisonResult.quality_category_retention
    [PSCustomObject]@{
      File = Split-Path $_ -Leaf
      Mode = $Mode
      Speedup = [math]::Round($Timing.speedup, 3)
      TimeReductionPercent = [math]::Round($Timing.percent_time_reduction, 2)
      OutsideNoise = $Timing.outside_noise_band
      PairedWins = "$($Timing.paired_faster_count)/$($Timing.paired_count)"
      Meets1_5x = $Timing.meets_1_5x_speedup
      Meets2x = $Timing.meets_2x_speedup
      DarkRetention = $Retention.dark.passing_fraction
      BrightRetention = $Retention.bright.passing_fraction
      MotionRetention = $Retention.motion.passing_fraction
      DarkExactOverlap = $ComparisonResult.comparisons.dark.overlap_count
      BrightExactOverlap = $ComparisonResult.comparisons.bright.overlap_count
      MotionExactOverlap = $ComparisonResult.comparisons.motion.overlap_count
      LumaSpearman = $ComparisonResult.ranking.luminance_spearman
      MotionSpearman = $ComparisonResult.ranking.motion_spearman
    }
  }
} | Format-Table -AutoSize
```

Promote neither candidate from a single clip. A candidate passes the performance
gate only when it is at least `1.5x` faster than the full-resolution PlaneStats
candidate on every required class, is faster in a majority of paired
repetitions, and its median improvement exceeds the larger timing population
standard deviation. Treat `2x` as the desired result rather than a mandatory
minimum.

For approximate-quality review, use the report's exact overlap, nearest-frame
distances, top-K overlap, and rank correlations, plus its quality-baseline
category-retention diagnostics. Every candidate-selected dark frame must remain
inside quality's darkest 25 percent, every bright frame inside its brightest 25
percent, and every motion frame inside its highest-motion 20 percent. Exact
frame equality is informative but is not required for `performance`.

If neither dense decoder candidate reaches `1.5x`, reject additional spatial
downscaling as the next lever. The measured 320px/full-resolution gap shows that
it cannot remove the dominant decode cost. Only then open a separate benchmark
for a sparse reference/key-frame or fixed-budget backend with explicit source
frame mapping; do not assume `SelectEvery` avoids decoding inter-frame
dependencies.

The `--window-start` and `--window-end-exclusive` options now bound production
dense metric calculation as well as selection and comparison. A nonzero start
includes one unreturned source-frame lookbehind so the first retained motion
value preserves full-source adjacent-pair semantics. Benchmark artifacts record
the compact metric range and array length; they do not pad excluded frames.
An explicit window requires the selected source's frame count from
`generated/clip_probe.toml`; the tool fails closed instead of timing a full-source
calculation when that prepared probe is unavailable, including when an explicit
active rectangle otherwise supplies metric provenance. A nonzero `--window-start`
also requires `--window-end-exclusive`; start-only post-calculation slicing is
rejected.

### Benchmark exact production window bounding

Run a materially excluded window and a full-window control on the same clip. The
first command models a 10-second lead/trail exclusion for a 24 fps, 2400-frame
case; adjust the frame boundaries to the prepared window for other frame rates.
Both `quality` and `performance` use the exact bounded production calculation.

```powershell
uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-window-bounded-witch-4k-hdr.json `
  --mode performance `
  --window-start 240 `
  --window-end-exclusive 2160 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  $WitchReference $WitchComparison

uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-window-full-control-witch-4k-hdr.json `
  --mode performance `
  --window-start 0 `
  --window-end-exclusive 2400 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  $WitchReference $WitchComparison
```

For a run with configured source trims, active-rectangle overrides, or a
non-default analysis source, also pass the prepared run's exact
`--selection-domain` token. Compare each mode's
`timing_summary.compute_pipeline_seconds.median`, confirm the compact metadata
range, and verify selected source-frame lists against the full-window baseline.
The benchmark currently rejects a non-default analysis source when its
`trim_start_frames` differs from the reference because that case requires
reference/analysis coordinate translation to report production-equivalent frame
numbers. Use the reference analysis source or equal trim starts for this benchmark.

### Benchmark sparse contiguous-burst candidates

Sparse candidates are developer-only modes. They analyze full-resolution luma
in eight deterministic centered bursts with exact 25%, 12.5%, or 6.25% frame
budgets. Each nonzero burst includes one unreturned motion lookbehind. Normal
and skip-loop-filter variants are separate so temporal sampling and decoder
quality loss remain attributable.

```powershell
uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-sparse-candidates-witch-4k-hdr.json `
  --mode performance-sparse-25pct-candidate `
  --mode performance-sparse-25pct-skip-loop-filter-candidate `
  --mode performance-sparse-12_5pct-candidate `
  --mode performance-sparse-12_5pct-skip-loop-filter-candidate `
  --mode performance-sparse-6_25pct-candidate `
  --mode performance-sparse-6_25pct-skip-loop-filter-candidate `
  --window-start 0 `
  --window-end-exclusive 2400 `
  --sparse-burst-count 8 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  --inspect-frame-types `
  $WitchReference $WitchComparison
```

Repeat that command for the SDR and animation/grain-heavy pairs with distinct
output filenames. Summarize one artifact with:

```powershell
$Report = Get-Content 'generated/analysis-sparse-candidates-witch-4k-hdr.json' -Raw | ConvertFrom-Json
$Report.comparisons.PSObject.Properties | ForEach-Object {
  $Mode = $_.Name
  $Result = $_.Value
  [PSCustomObject]@{
    Mode = $Mode
    Speedup = [math]::Round($Result.timing_comparison.speedup, 3)
    OutsideNoise = $Result.timing_comparison.outside_noise_band
    PairedWins = "$($Result.timing_comparison.paired_faster_count)/$($Result.timing_comparison.paired_count)"
    AnalyzedFrames = $Result.sampling.analyzed_frame_count
    ActualFraction = [math]::Round($Result.sampling.sampling_fraction_actual, 4)
    DarkRetention = $Result.quality_category_retention.dark.passing_fraction
    BrightRetention = $Result.quality_category_retention.bright.passing_fraction
    MotionRetention = $Result.quality_category_retention.motion.passing_fraction
    DarkExtremeCoverage = $Result.quality_extreme_coverage.dark.sampled_extreme_fraction
    BrightExtremeCoverage = $Result.quality_extreme_coverage.bright.sampled_extreme_fraction
    MotionExtremeCoverage = $Result.quality_extreme_coverage.motion.sampled_extreme_fraction
  }
} | Format-Table -AutoSize
```

#### Current sparse follow-up after the 2026-07-13 Witch matrix

The first Witch matrix eliminated the 6.25 percent candidates because motion
category retention fell to 60 percent. Skip-loop-filter added only about eight
percent beyond sparse sampling while introducing another approximation. The
current decision run therefore compares only the normal-decoder 25 and 12.5
percent candidates.

The original result artifact used the older generic
`sampled_ranking.luminance` schema and its 120-second frame-type inspection
timed out. Before rerunning, verify that the checkout contains the final split
dark/bright ranking schema:

```powershell
git status --short
git rev-parse --short HEAD
if (-not (Select-String -Path 'tools/benchmark_analysis_tiers.py' -Pattern '"dark_luminance"' -Quiet)) {
  throw 'The benchmark checkout predates the final sparse-ranking schema. Pull the latest stage1 commit.'
}
```

Use a nonzero 2,400-frame window to exercise the production motion-lookbehind
path while keeping the workload comparable to the first Witch run. Run the
second command on an animation/grain-heavy pair because it is the strongest
second-source challenge for temporal sampling. If that class is unavailable,
use the fixed 8-bit SDR pair instead. Both selected analysis sources must contain
at least 2,640 frames; otherwise reduce both window values while preserving a
nonzero start and equal window length.

```powershell
uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-sparse-final-witch-4k-hdr.json `
  --mode performance-sparse-25pct-candidate `
  --mode performance-sparse-12_5pct-candidate `
  --window-start 240 `
  --window-end-exclusive 2640 `
  --sparse-burst-count 8 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  --inspect-frame-types `
  --ffprobe-timeout 300 `
  $WitchReference $WitchComparison

uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-sparse-final-animation-grain.json `
  --mode performance-sparse-25pct-candidate `
  --mode performance-sparse-12_5pct-candidate `
  --window-start 240 `
  --window-end-exclusive 2640 `
  --sparse-burst-count 8 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  --inspect-frame-types `
  --ffprobe-timeout 300 `
  $AnimationReference $AnimationComparison
```

Summarize both final artifacts with the final ranking schema:

```powershell
$SparseFiles = @(
  'generated/analysis-sparse-final-witch-4k-hdr.json',
  'generated/analysis-sparse-final-animation-grain.json'
)
$SparseModes = @(
  'performance-sparse-25pct-candidate',
  'performance-sparse-12_5pct-candidate'
)

$SparseFiles | ForEach-Object {
  $Report = Get-Content $_ -Raw | ConvertFrom-Json
  foreach ($Mode in $SparseModes) {
    $Result = $Report.comparisons.PSObject.Properties[$Mode].Value
    [PSCustomObject]@{
      File = Split-Path $_ -Leaf
      Mode = $Mode
      Speedup = [math]::Round($Result.timing_comparison.speedup, 3)
      OutsideNoise = $Result.timing_comparison.outside_noise_band
      PairedWins = "$($Result.timing_comparison.paired_faster_count)/$($Result.timing_comparison.paired_count)"
      DarkRetention = $Result.quality_category_retention.dark.passing_fraction
      BrightRetention = $Result.quality_category_retention.bright.passing_fraction
      MotionRetention = $Result.quality_category_retention.motion.passing_fraction
      DarkTopK = $Result.sampled_ranking.dark_luminance.top_k_overlap_fraction
      BrightTopK = $Result.sampled_ranking.bright_luminance.top_k_overlap_fraction
      MotionTopK = $Result.sampled_ranking.motion.top_k_overlap_fraction
      FrameTypesAvailable = $Report.source.analysis_source.frame_types.available
    }
  }
} | Format-Table -AutoSize
```

Use the existing `1.5x` minimum/desired `2x` timing gate on every required clip
class. Judge quality with category retention, exact/nearest selection results,
sampled metric fidelity/ranking, extreme-pool coverage, and nearest-sample
distance. Sparse modes remain invalid application configuration values until the
maintainer accepts a distinct quality/performance tradeoff from this evidence.
`sampled_ranking.dark_luminance` reports lowest-luminance top-K overlap,
`sampled_ranking.bright_luminance` reports highest-luminance top-K overlap, and
`sampled_ranking.motion` reports highest-motion top-K overlap; each includes its
direction explicitly.

### Benchmark the isolated NVIDIA request

This experiment requests `LWLibavSource(prefer_hw=1)` with full-resolution
PlaneStats and the same exact metric window as production quality. L-SMASH Works
may silently fall back to software, so a successful run is not proof of CUVID.
The tool fails before timing when `nvidia-smi` cannot identify an NVIDIA GPU and
records system-wide decoder utilization only as corroborating, unattributed
evidence. Both utilization probes run outside analysis, selection, and total-trial
timers, so their subprocess overhead cannot bias the candidate speedup.

```powershell
uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-nvidia-cuvid-request-witch-4k-hdr.json `
  --mode quality-nvidia-cuvid-candidate `
  --window-start 0 `
  --window-end-exclusive 2400 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  $WitchReference $WitchComparison

$Report = Get-Content 'generated/analysis-nvidia-cuvid-request-witch-4k-hdr.json' -Raw | ConvertFrom-Json
$Result = $Report.comparisons.'quality-nvidia-cuvid-candidate'
[PSCustomObject]@{
  GPU = $Report.nvidia_preflight.gpus[0].name
  Driver = $Report.nvidia_preflight.gpus[0].driver_version
  Speedup = [math]::Round($Result.timing_comparison.speedup, 3)
  EffectiveDecoderProven = $Result.decoder_evidence.effective_decoder_proven
  VerificationStatus = $Result.decoder_evidence.verification_status
  BeforeDecoderUtilization = $Result.decoder_evidence.decoder_utilization_percent_before
  AfterDecoderUtilization = $Result.decoder_evidence.decoder_utilization_percent_after
} | Format-List
```

Never promote this experiment based only on GPU presence or nonzero utilization:
the current integration cannot attribute
decoder-engine activity to the process or prove that L-SMASH did not fall back.

#### Establishing whether CUVID actually decoded the candidate

`prefer_hw=1` is a preference, not a requirement. L-SMASH Works tries the
codec-specific `_cuvid` decoder when a CUDA device and matching decoder are
available, but otherwise retains the default software decoder, as shown by its
[decoder-selection source](https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works/blob/10614318db0b231a8d5bff855946442c7b976799/common/decode.c)
and [VapourSynth documentation](https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works/blob/10614318db0b231a8d5bff855946442c7b976799/VapourSynth/README.md).
Its VapourSynth surface does not expose the selected `AVCodec` name or wrapper,
so the current benchmark JSON cannot prove backend identity by itself.

Use these evidence levels:

1. **Backend-identity proof:** a diagnostic L-SMASH Works build must expose the
   opened codec name and wrapper from `AVCodecContext`. Accept only a codec such
   as `hevc_cuvid`, wrapper `cuvid`, with a CUDA hardware context. This is the
   definitive internal proof, but it requires a custom/upstream plugin change.
2. **Process-attributed operational proof:** monitor video-decoder utilization
   for the exact benchmark Python PID. During a one-repetition run, the software
   `quality` trial must remain at zero and the following NVIDIA candidate trial
   must show nonzero `VideoDecode` utilization. The
   [NVIDIA NVML API](https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html)
   exposes PID plus decoder utilization through
   `nvmlDeviceGetProcessUtilization`; use that API when supported by the
   installed driver.
3. **Windows fallback proof:** if per-process NVML returns `NOT_SUPPORTED`, use
   the built-in `GPU Engine` performance counters or a
   [GPUView ETW capture](https://learn.microsoft.com/en-us/windows/win32/direct2d/profiling-directx-applications)
   for the exact Python PID. Device-wide `nvidia-smi utilization.decoder`
   remains corroboration only. Do not use `nvidia-smi pmon` as the Windows proof
   path; the [NVIDIA command documentation](https://docs.nvidia.com/deploy/nvidia-smi/index.html)
   limits that process-monitoring command to supported bare-metal 64-bit Linux
   systems.

For the Windows counter check, copy this one-repetition control/candidate pair
into the first PowerShell window, but do not start it yet. Repetition zero always
runs software `quality` first and the NVIDIA candidate second:

```powershell
uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-nvidia-cuvid-pid-proof.json `
  --mode quality-nvidia-cuvid-candidate `
  --window-start 240 `
  --window-end-exclusive 2640 `
  --repetitions 1 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  --skip-decode-baseline `
  $WitchReference $WitchComparison
```

In a second PowerShell window, start the following monitor. It waits for the
benchmark's `python.exe`, captures its PID automatically, then samples only that
PID's Video Decode engine. Immediately after starting the monitor, start the
benchmark in the first window. Increase `-MaxSamples` if that benchmark runs
longer than 60 seconds on the test machine.

```powershell
do {
  $BenchmarkProcess = Get-CimInstance Win32_Process |
    Where-Object {
      $_.Name -eq 'python.exe' -and
      $_.CommandLine -like '*benchmark_analysis_tiers.py*'
    } |
    Sort-Object CreationDate -Descending |
    Select-Object -First 1
  if ($null -eq $BenchmarkProcess) {
    Start-Sleep -Milliseconds 100
  }
} until ($null -ne $BenchmarkProcess)

$BenchmarkPid = [int]$BenchmarkProcess.ProcessId
Write-Host "Monitoring benchmark PID $BenchmarkPid"
$VideoDecodeSamples = Get-Counter '\GPU Engine(*)\Utilization Percentage' -SampleInterval 1 -MaxSamples 60 |
  ForEach-Object { $_.CounterSamples } |
  Where-Object {
    $_.InstanceName -like "*pid_$($BenchmarkPid)_*" -and
    $_.InstanceName -match 'engtype_VideoDecode'
  } |
  Select-Object Timestamp, InstanceName, CookedValue

$VideoDecodeSamples |
  Export-Csv 'generated/nvidia-cuvid-pid-video-decode.csv' -NoTypeInformation
$VideoDecodeSamples | Format-Table -AutoSize
```

Record the transition shown by benchmark progress: the first `quality` interval
must have no positive samples; the subsequent NVIDIA-candidate interval must
have repeatable positive samples for that same PID. This establishes that the
candidate process used NVIDIA's video-decoder engine. It is sufficient
operational evidence for performance evaluation, but only the plugin-internal
codec/wrapper report establishes the exact CUVID decoder identity.

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
statistics for GOP-sensitive experiments. When an explicit benchmark window and
prepared source FPS are available, frame decoding is bounded to that window with
`-read_intervals`; otherwise the scan covers the full source and may be expensive
on long clips. `--ffprobe-timeout` bounds each inspection command. The report's
`frame_type_inspection_scope` records the inspected range, while
`frame_types.error` preserves a timeout or other ffprobe failure instead of
reducing it to an unexplained `available = false` result.

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
An explicit end also requires the selected source's prepared frame count; there
is no full-source fallback. A non-default analysis source with a different
`trim_start_frames` from the reference is rejected until coordinate translation
is implemented in this developer tool.

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

### 2026-07-13: Full-resolution quality PlaneStats candidate reopened under practical equivalence

Benchmark artifact:
the historical report summarized in
[Analysis Benchmark History](analysis-benchmark-history.md). The generated raw
JSON was removed after its decision metrics were recorded.

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

The original strict lossless gate rejected this result because motion exceeded
`allclose(rtol=0, atol=1e-12)`. After reviewing the numerical meaning and product
goal, the maintainer explicitly changed the quality contract to practical
selection/ranking equivalence with tightly bounded float drift. Under that
contract, the Witch result passes the provisional quality gate: selected frames
and top-50 orderings are exact, and the maximum motion error is well below the
new `1e-7` bound.

Decision update: the maintainer subsequently accepted production implementation
under this practical-equivalence contract so the combined PlaneStats, exact-window,
sparse, and NVIDIA candidates can be validated through one Windows benchmark
cycle. The required 8-bit SDR and animation/grain-heavy runs remain release
evidence, but no longer block implementing the production quality dispatch. This
is a recorded contract change, not a silent post-result relaxation.

### 2026-06-10: The Witch UHD Clip Pair, Mode Simplification Decision

Benchmark artifact:
the historical June report summarized in
[Analysis Benchmark History](analysis-benchmark-history.md). Its generated
scratch JSON was removed after the decision metrics were recorded.

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
