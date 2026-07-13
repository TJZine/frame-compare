# Analysis Benchmark History

This document is the curated record of analysis-mode benchmark decisions. It
keeps the important speed, quality, environment, and evidence caveats in one
place without requiring every intermediate JSON report to remain in
`generated/`.

The procedural workflow and runnable commands remain in
[Analysis Performance Validation](analysis-performance-validation.md). Raw JSON
reports are evidence for the entries below; this document is the durable
summary to use when comparing later runs.

## Recording conventions

- Record the commit, corpus, source window, repetition count, cache policy,
  source-index state, and machine for every decision run.
- Calculate speedup only within one report: `reference median / candidate
  median`. Do not compare wall-clock medians from different commits or
  machines as if they were one series.
- Treat category retention, selected-frame equality, top-K/ranking agreement,
  and bounded metric error as the quality result. A faster candidate is not an
  accepted tier without the required quality evidence.
- The older baseline reports use `analyze_seconds`; later reports use
  `compute_pipeline_seconds`. The field change is recorded here because those
  timings should not be mixed without checking the report schema.
- A frame-type result is valid only when the report says
  `source.analysis_source.frame_types.available = true` and records a bounded
  benchmark-window inspection. Older timeout-based `available = false` results
  are historical timing evidence only.

## Established corpus and protocol

The primary corpus is the 4K HDR Witch pair:

- Reference: `The Witch [2015] 2160p UHD BDRip DV HDR10 x265 DTS-HD MA 5.1-Kira.Clip.mkv`
- Comparison: `The.VVitch.A.New-England.Folktale.2015.2160p.UHD.BluRay.DTS-HD.MA.5.1.DoVi.x265-CtrlHD.Clip.mkv`
- Analysis source: explicit `reference`.
- Metric rectangle: dimension-derived `3600x2160` at `(120, 0)` from the
  3840x2160 source.
- Standard sampling: 20 random, 10 dark, 10 bright, and 10 motion selections.
- Standard decision runs: three repetitions, cold metric cache, and warm source
  indexes.
- Earlier runs used frames `0..2400`. The final sparse decision run uses
  frames `240..2640` so the production motion lookbehind path is exercised.

The measurements currently available were collected on the same Windows
environment: 24 logical CPUs, VapourSynth R76/R4.2, Python 3.13.7, and an
NVIDIA GeForce RTX 5080 with driver 610.62 for the NVIDIA request run. These
results are hardware-dependent and are not release-wide performance claims.

A secondary animation corpus is the matching Dan Da Dan S02E01 pair:

- Reference: `DAN.DA.DAN.S02E01.Like.This.Is.the.Legend.of.the.Giant.Snake.1080p.BluRay.REMUX.AVC.FLAC.2.0-NAN0.mkv`
- Comparison: `DAN.DA.DAN.S02E01.Like.This.Is.the.Legend.of.the.Giant.Snake.REPACK.1080p.CR.WEB-DL.DUAL.DDP2.0.H.264-Kitsune.mkv`
- Format: 1920x1080 H.264 at 24000/1001 fps, full-frame metric rectangle.
- The releases differ in total duration by about nine seconds, so the fixed
  `240..2640` window is the comparable opening window used for this result.

## Decision ledger

| Date | Evidence | Result | Decision or status |
| --- | --- | --- | --- |
| 2026-06-10 | `analysis-tier-benchmark-warm-index.json` | Existing runbook record: `quality` 430.34s, `performance` 130.27s, or 3.30x faster. Bright and motion selections were 10/10; dark was 7/10. | Established the dense PlaneStats implementation as the practical performance direction. Dark-frame differences still required visual review. |
| 2026-07-12 | `analysis-tier-benchmark-witch-baseline.json` (raw report removed) | Older-schema `quality` median 232.491s versus `performance` 115.031s, about 2.02x faster. Bright and motion were 10/10; dark was 8/10. | Baseline for the later Witch optimization work. Keep separate from the June run because the schema and implementation context changed. |
| 2026-07-12 | `analysis-tier-witch-combined-sync.json` and `analysis-tier-witch-combined-concurrent.json` (raw reports removed) | Combined PlaneStats traversal reproduced the established luminance and motion top-50 sets (1.0 Jaccard overlap); Spearman correlation was 0.999969 for luminance and 0.960388 for motion. | Implementation evidence only. The artifacts were superseded by the accepted quality implementation and final candidate matrix. |
| 2026-07-13 | `quality-planestats-candidate-witch-4k-hdr.json` (raw report removed) | Full-resolution PlaneStats median 64.009s versus production NumPy quality 235.086s: 3.67x faster and 72.77% less compute time. Selected frames and top-50 orderings were exact; maximum motion drift was 8.80e-9. | Accepted under the practical-equivalence quality contract, which bounds float drift while requiring exact selections and rankings. SDR and animation/grain evidence remain required for release confidence. |
| 2026-07-13 | `analysis-decoder-candidates-witch-4k-hdr.json` (raw report removed) | Dense skip-loop-filter candidate: 65.098s versus the 68.749s PlaneStats candidate, about 1.056x faster. Max-threads variant: 66.801s, about 1.029x faster. Category retention was 100% in this run, but neither approached the 1.5x minimum target. | No separate dense third performance tier was justified by this evidence. |
| 2026-07-13 | `analysis-all-candidates-witch-4k-hdr.json` (raw report removed) | Relative to the report's 23.135s quality reference: normal 25% sparse was 2.075x, normal 12.5% sparse was 3.207x, and 6.25% sparse was 3.735x. The 6.25% modes retained only 60% of motion selections. Skip-loop sparse variants were faster again, but added another approximation. | Narrowed the final decision run to normal-decoder 25% and 12.5% sparse candidates, with animation/grain as the next required corpus. |
| 2026-07-13 | `analysis-nvidia-cuvid-request-witch-4k-hdr.json` (raw report removed) | CUVID-request candidate was 1.204x faster than the report's quality reference and retained 100% of bright, dark, and motion selections. | Diagnostic result only: GPU presence and device-wide utilization did not prove that L-SMASH selected CUVID instead of falling back to software. |
| 2026-07-13 | [`analysis-sparse-final-witch-4k-hdr.json`](../generated/analysis-sparse-final-witch-4k-hdr.json) | Corrected final Witch run over frames `240..2640`: 25% sparse was 13.507s versus the 27.793s quality reference (2.058x, 51.40% reduction) with 100% bright/dark/motion retention. 12.5% sparse was 11.260s (2.468x, 59.49% reduction) with 100% dark/motion but 90% bright retention. Both candidates had 1.0 sampled top-10 overlap and Spearman ranking in all three categories. Frame inspection is valid: 2,397 frames, with 22 I, 2,006 B, and 369 P frames. | Keep as the corrected Witch final evidence. The 25% candidate is the stronger provisional choice; 12.5% remains a faster candidate requiring cross-corpus confirmation because of the bright-category miss. |
| 2026-07-13 | [`analysis-nvidia-cuvid-final-witch-4k-hdr.json`](../generated/analysis-nvidia-cuvid-final-witch-4k-hdr.json) | Final Witch request over frames `240..2640` was 1.239x faster than its quality reference and retained 100% of bright, dark, and motion selections. | Keep as the current NVIDIA request evidence, but do not call it CUVID proof: `effective_decoder_proven` remains false. Frame inspection was not requested for this run. |
| 2026-07-13 | [`analysis-sparse-final-dandadan-s02e01-1080p.json`](../generated/analysis-sparse-final-dandadan-s02e01-1080p.json) | Animation quality reference median was 4.317s. The 25% candidate was 1.717s (2.514x, 60.22% reduction); 12.5% was 1.131s (3.817x, 73.80% reduction). Both retained 100% of bright, dark, and motion selections and had exact sampled top-10 overlap and Spearman ranking. Frame inspection reported 2,400 frames: 119 I, 1,406 B, and 875 P. | Both sparse candidates pass the 1.5x minimum and 2x desired timing gates on this animation corpus. The 12.5% candidate is now supported by both Witch and animation evidence, subject to additional corpus coverage before promotion. |

## Retention and cleanup policy

Keep the curated history and the smallest raw evidence set needed to reproduce
the current decisions:

- Keep this document and the procedural runbook.
- Keep the final Witch sparse report, final Witch NVIDIA diagnostic, and final
  animation sparse report as the current raw evidence set.
- Keep final SDR and future animation/grain reports when they are produced;
  these are the cross-corpus release evidence.
- Remove superseded baseline, combined traversal, quality-candidate,
  dense-decoder, full-matrix, and older NVIDIA request reports after their
  decision metrics are captured here.
- Remove ignored June scratch outputs (`analysis-tier-benchmark.json`, the
  warm-index/dense-fast/active-rect variants, and transient probe/lock files)
  only after no benchmark process is using `generated/`.

The July 13 active sparse rerun was allowed to finish before cleanup. Future
cleanup passes must first confirm that no `benchmark_analysis_tiers.py` process
is running, then preserve the final JSONs and update this ledger with their
actual frame counts, speedups, retention, and frame-type counts. NVIDIA reports
that did not request frame inspection do not need to be rerun for the
frame-type fix.

## Open evidence

- The 12.5% sparse candidate has a 10% bright-category miss on the final Witch
  window even though its sampled ranking was exact; the animation result passed
  that category, but more corpus coverage is still desirable.
- NVIDIA backend identity is still unproven; a CUVID request is not a CUVID
  proof.
- Results are machine- and decoder-build-dependent. Re-baseline after changing
  VapourSynth, L-SMASH, FFmpeg, GPU driver, Python, or benchmark config.
- Keep the benchmark commit and config path with every future row so speedups
  remain attributable to a specific implementation.
