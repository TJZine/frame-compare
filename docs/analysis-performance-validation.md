# Analysis Performance Validation

Use `tools/benchmark_analysis_tiers.py` to compare `balanced` and `fast` against
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

The script writes deterministic JSON with the quality baseline, candidate tier
comparisons, selected-frame overlap, nearest-frame distances, miss rates,
Spearman rank correlations, top-K overlap, total analysis wall-clock time,
algorithm identity, and warnings for unavailable runtime details.

By default, the script renders tier-level Rich progress to stderr while keeping
stdout reserved for the final output JSON path. Pass `--no-progress` when a
scripted run needs no terminal progress display.

When source trims, effective FPS overrides, or shared selection windows matter,
pass the exact source-frame window used for review with `--window-start` and
`--window-end-exclusive`. If an orchestration selection-domain token is available
from a prepared run, pass it with `--selection-domain` so cache identity matches
that run. Without those arguments, the script records warnings and compares the
full analysis metric domain.

The benchmark script uses the configured `paths.generated_dir` for analysis
cache by default and resolves explicit `sources.analysis_source` selectors before
running metrics. It supports per-source `effective_fps` overrides. It does not
support `sources.analysis_source = "fastest"` or automatic `sources.match_fps`
policies; use an explicit analysis source and explicit effective-FPS overrides
for benchmark evidence.

## Local Evidence

This evidence is local, hardware-dependent, and not a full validation matrix.
Treat it as support for tuning decisions, not a release-wide guarantee. Entries
that cover superseded algorithms are labeled as such.

### 2026-06-10: The Witch UHD Clip Pair, Pre-Dense `fast`

Benchmark artifact:
`generated/analysis-tier-benchmark-warm-index.json`

This run used the previous `fast` algorithm: 160px Bicubic luma with
coarse-to-refined adjacent-pair motion and zero-filled motion outside refined
windows. It motivated replacing `fast` with dense 160px Bilinear Planestats
motion; it should not be used as validation evidence for the current `fast`
implementation.

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
  differ from a full run with trims or source overrides.

Timing:

| Mode | Analyze time | Relative to `quality` |
| --- | ---: | ---: |
| `quality` | 430.34s | 1.00x |
| `balanced` | 130.27s | 3.30x faster |
| `fast` | 171.11s | 2.51x faster |

Selection agreement versus `quality`:

| Mode | Category | Exact overlap | Miss rate at tolerance | Max nearest distance |
| --- | --- | ---: | ---: | ---: |
| `balanced` | bright | 10/10 | 0.0 | 0 |
| `balanced` | dark | 7/10 | 0.3 | 32 |
| `balanced` | motion | 10/10 | 0.0 | 0 |
| `fast` | bright | 9/10 | 0.0 | 1 |
| `fast` | dark | 6/10 | 0.3 | 102 |
| `fast` | motion | 8/10 | 0.2 | 1036 |

Ranking agreement:

| Mode | Luminance Spearman | Motion Spearman | Highest motion top-50 overlap |
| --- | ---: | ---: | ---: |
| `balanced` | 0.999970 | 0.957701 | 50/50 |
| `fast` | 0.999969 | 0.689946 | 45/50 |

Decision signal:

- `balanced` is the preferred candidate for this clip pair: it was faster than
  both `quality` and `fast`, preserved all bright and motion selections, and
  kept high motion-rank agreement.
- `fast` is not accepted from this evidence alone: it was slower than
  `balanced`, had a large motion miss, and had materially weaker motion-rank
  agreement.
- The `balanced` dark-frame differences should be visually reviewed before
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

Balanced tolerances are 2 frames for dark/bright and 3 frames for motion. Fast
tolerances are 3 frames for dark/bright and 5 frames for motion.
