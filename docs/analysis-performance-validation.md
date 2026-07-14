# Analysis Performance Validation

This guide is the production-only Windows workflow for comparing Frame Compare's
locked `quality` and `performance` analysis modes. Historical candidate commands
and decisions live in [Analysis Benchmark History](analysis-benchmark-history.md),
not in this runbook.

## Mode contract under test

| Mode | Brightness and motion coverage | Expected behavior |
| --- | --- | --- |
| `quality` | Full-resolution luma PlaneStats for every eligible frame | Default and highest-confidence automatic selection |
| `performance` | The same metrics for exactly `ceil(eligible frames * 0.25)` frames in up to eight deterministic centered contiguous bursts | Faster, approximate automatic selection |

Both modes:

- use the selected analysis source and prepared active picture rectangle;
- return metrics only for frames inside the shared selectable window after source
  trims and configured leading/trailing exclusions;
- preserve adjacent-frame motion at the start of every analyzed range with an
  unreturned lookbehind frame; and
- isolate metric caches by mode and algorithm identity.

Performance metric categories can choose only sampled frames. Configured user
frames and seeded random frames remain eligible across the entire selectable
window. Different dark, bright, or motion frame numbers are expected, and short
events between bursts can be missed.

## Benchmark profiles

Keep these two profiles separate. They answer different questions.

### Decision profile

The checked-in `config/benchmark.config.toml` preserves the profile used to
choose the 25% mode:

```toml
[analysis]
random_frame_count = 20
dark_frame_count = 10
bright_frame_count = 10
motion_frame_count = 10
dark_quantile = 0.20
bright_quantile = 0.80
```

Use it when comparing a new result with the retained Witch and Dan Da Dan
evidence. Its wider 20%/80% category pools are deliberate research settings,
not shipped defaults.

### Shipped-default quantile control

Frame Compare ships `dark_quantile = 0.05` and `bright_quantile = 0.95`. Metric
category counts ship as zero, so a useful control keeps the benchmark's 10
dark/bright/motion requests while changing only the quantiles.

Create an ignored local copy from PowerShell:

```powershell
Copy-Item `
  'config\benchmark.config.toml' `
  'config\benchmark-default-quantiles.config.toml' `
  -Force

$DefaultConfig = 'config\benchmark-default-quantiles.config.toml'
$Text = Get-Content $DefaultConfig -Raw
$Text = $Text.Replace('dark_quantile = 0.20', 'dark_quantile = 0.05')
$Text = $Text.Replace('bright_quantile = 0.80', 'bright_quantile = 0.95')
Set-Content -LiteralPath $DefaultConfig -Value $Text -Encoding UTF8
```

Run this control before describing performance-mode quality as validated under
the shipped quantiles. Do not combine its timing or selections with the decision
profile as if they were one sample series.

## One-time Windows setup

Run commands from a clean source checkout on the Windows machine used for the
comparison.

```powershell
git status --short
git rev-parse HEAD
uv sync --group dev --frozen
uv run --no-sync frame-compare doctor --json
New-Item -ItemType Directory -Force 'generated' | Out-Null
```

For every comparable run:

- connect AC power and keep the same Windows power mode;
- close unrelated CPU-, GPU-, memory-, and disk-intensive applications;
- keep the same commit, Python environment, config, ordered inputs, source
  indexes, active rectangle, and source-frame window;
- avoid Windows Update, antivirus scans, and media indexing during timing; and
- record unusual background activity rather than silently accepting a noisy run.

The benchmark JSON records the Git commit, dirty state, and porcelain status
under `provenance`. Preserve the separate `git rev-parse HEAD` output as an
independent check when a run will support a product decision.

## Prepare the fixed corpus

Use the same ordered reference/comparison pair for every rerun. The examples
below match the retained evidence; change paths only when intentionally adding a
new corpus.

```powershell
$WitchReference = (Resolve-Path -LiteralPath `
  'comparison_videos\The Witch [2015] 2160p UHD BDRip DV HDR10 x265 DTS-HD MA 5.1-Kira.Clip.mkv').Path
$WitchComparison = (Resolve-Path -LiteralPath `
  'comparison_videos\The.VVitch.A.New-England.Folktale.2015.2160p.UHD.BluRay.DTS-HD.MA.5.1.DoVi.x265-CtrlHD.Clip.mkv').Path

$AnimeReference = (Resolve-Path -LiteralPath `
  'comparison_videos\DAN.DA.DAN.S02E01.Like.This.Is.the.Legend.of.the.Giant.Snake.1080p.BluRay.REMUX.AVC.FLAC.2.0-NAN0.mkv').Path
$AnimeComparison = (Resolve-Path -LiteralPath `
  'comparison_videos\DAN.DA.DAN.S02E01.Like.This.Is.the.Legend.of.the.Giant.Snake.REPACK.1080p.CR.WEB-DL.DUAL.DDP2.0.H.264-Kitsune.mkv').Path
```

Prepare probe data and warm the adjacent L-SMASH `.lwi` source indexes through a
normal application run before timing. Point `--input` at a directory containing
only the fixed case under test:

```powershell
uv run --no-sync frame-compare run `
  --root . `
  --config config/benchmark.config.toml `
  --input 'C:\Benchmarks\witch-case' `
  --no-upload
```

The cold benchmark policy removes only the exact analysis metric cache entry. It
does not delete source indexes. `--require-warm-source-index` fails early when
the selected analysis source is not ready.

## Primary cold benchmarks

The retained decision window is source frames `240..2640`: 2,400 eligible
frames with a nonzero start. Use three repetitions for routine comparison and
five when a close result or high variance will decide a change.

### 4K HDR Witch

```powershell
uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-production-witch-4k-hdr.json `
  --window-start 240 `
  --window-end-exclusive 2640 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  --inspect-frame-types `
  --ffprobe-timeout 300 `
  $WitchReference $WitchComparison
```

### Dan Da Dan animation

```powershell
uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-production-dandadan-s02e01-1080p.json `
  --window-start 240 `
  --window-end-exclusive 2640 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  --inspect-frame-types `
  --ffprobe-timeout 300 `
  $AnimeReference $AnimeComparison
```

Cold runs are the primary algorithm-performance evidence. Confirm every quality
and performance trial reports a cache miss and a successful cache write. Frame
type inspection runs after timed trials and is diagnostic only. The benchmark
fails closed if a cold trial does not observe both the miss and successful write.

## Shipped-default quantile control

Repeat at least the primary Witch case with the copied default-quantile config:

```powershell
uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark-default-quantiles.config.toml `
  --output generated/analysis-production-witch-default-quantiles.json `
  --window-start 240 `
  --window-end-exclusive 2640 `
  --repetitions 3 `
  --metric-cache-policy cold `
  --require-warm-source-index `
  --skip-decode-baseline `
  $WitchReference $WitchComparison
```

Repeat on the second corpus when the result will support a release-wide claim.
The purpose of this control is selection quality at the narrower pools; it does
not replace the decision-profile timing history.

## Cache-reuse control

Run reuse only after a matching cold run has populated both mode caches:

```powershell
uv run --no-sync python tools/benchmark_analysis_tiers.py `
  --root . `
  --config config/benchmark.config.toml `
  --output generated/analysis-production-witch-reuse.json `
  --window-start 240 `
  --window-end-exclusive 2640 `
  --repetitions 3 `
  --metric-cache-policy reuse `
  --require-warm-source-index `
  --skip-decode-baseline `
  $WitchReference $WitchComparison
```

Every reuse trial must report a cache hit. This control measures cache loading
and selection, not uncached brightness/motion computation, so never substitute
it for the cold result. The benchmark fails closed if a reuse trial misses.

## Summarize results

This PowerShell summary works with the production `quality` reference and
`performance` comparison fields:

```powershell
$Files = @(
  'generated/analysis-production-witch-4k-hdr.json',
  'generated/analysis-production-dandadan-s02e01-1080p.json'
)

$Files | ForEach-Object {
  $Report = Get-Content $_ -Raw | ConvertFrom-Json
  $Quality = $Report.quality
  $Performance = $Report.comparisons.performance
  $QualitySeconds = $Quality.timing_summary.compute_pipeline_seconds.median
  $PerformanceSeconds = $Performance.timing_summary.compute_pipeline_seconds.median

  [PSCustomObject]@{
    File = Split-Path $_ -Leaf
    QualitySeconds = [math]::Round($QualitySeconds, 3)
    PerformanceSeconds = [math]::Round($PerformanceSeconds, 3)
    Speedup = [math]::Round($QualitySeconds / $PerformanceSeconds, 3)
    QualityStdDev = [math]::Round(
      $Quality.timing_summary.compute_pipeline_seconds.pstdev, 3)
    PerformanceStdDev = [math]::Round(
      $Performance.timing_summary.compute_pipeline_seconds.pstdev, 3)
    DarkExact = $Performance.comparisons.dark.overlap_count
    BrightExact = $Performance.comparisons.bright.overlap_count
    MotionExact = $Performance.comparisons.motion.overlap_count
    DarkMissRate = $Performance.comparisons.dark.miss_rate_at_tolerance
    BrightMissRate = $Performance.comparisons.bright.miss_rate_at_tolerance
    MotionMissRate = $Performance.comparisons.motion.miss_rate_at_tolerance
    MetricSamples = $Performance.metadata.frame_count
    Warnings = ($Report.warnings -join '; ')
  }
} | Format-Table -AutoSize
```

Inspect the JSON directly when a field is absent or the benchmark schema has
changed; do not convert missing evidence to zero.

## Acceptance and interpretation

Evaluate results in this order:

1. Confirm the commit, config, input order, window, active rectangle, warm source
   indexes, repetitions, and cache policy.
2. Confirm cold misses/writes or reuse hits match the intended experiment.
3. Verify performance analyzed exactly `ceil(window frames * 0.25)` mapped source
   frames across no more than eight bursts, all inside the eligible window.
4. Use median compute-pipeline time as the primary timing. Population standard
   deviation is a noise warning; rerun unstable results.
5. Require at least `1.5x` speedup for a meaningful distinct mode. Treat `2x` as
   the desired result, not a platform-wide guarantee.
6. Review category-pool retention, exact overlap, nearest-frame distance, and
   miss rate. Performance need not reproduce quality frame numbers.
7. Treat exact sampled ranking/metrics only as proof that sampled PlaneStats
   values are correct. It does not measure unsampled events.
8. Visually inspect consequential misses, especially brief flashes, cuts,
   high-motion events, credits, subtitles, and near-black/highlight detail.

Useful review labels are:

- `acceptable near-duplicate`
- `temporal sampling missed event`
- `tie/ranking ambiguity`
- `source trim/window issue`
- `active-rectangle issue`
- `bug requiring implementation fix`

## Production-domain proof

An explicit benchmark window proves the metric algorithm over that fixed source
range. A report with `selection_domain = null` does not prove production cache
identity for source trims, effective-FPS overrides, non-reference analysis
sources, or active-rectangle overrides.

For those configurations, run the normal application path twice with the actual
config and fixed input directory. Confirm the first run computes/writes metrics,
the second reuses the cache, the reported selectable window reflects the leading
and trailing exclusions, and all chosen source frames are inside that window.
Treat this as production integration proof alongside—not instead of—the cold
algorithm benchmark.

## Evidence retention

Keep new output in ignored `generated/` while reviewing it. When a result changes
a product decision:

- add its commit, corpus, window, repetitions, cache policy, profile, environment,
  timing, selection evidence, and caveats to
  [Analysis Benchmark History](analysis-benchmark-history.md);
- keep raw JSON only in ignored `generated/` while reviewing and transcribing
  the decision-grade results; and
- delete the raw JSON after the history entry is complete rather than tracking
  benchmark reports in the repository.

Do not retain superseded matrices, transient probes, lock files, cache payloads,
per-frame arrays, or reports whose material result is captured in the ledger.
