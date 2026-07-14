# Analysis Benchmark History

This is the curated record of analysis-mode performance decisions. It preserves
the material timing and selection evidence without retaining raw benchmark JSON
or experimental commands in the repository.

For current Windows commands, see
[Analysis Performance Validation](analysis-performance-validation.md).

## Locked decision

As of 2026-07-13, Frame Compare has two public analysis modes:

| Mode | Locked implementation | Product position |
| --- | --- | --- |
| `quality` | Full-resolution luma PlaneStats for every eligible frame | Default; highest-confidence automatic selection |
| `performance` | The same metrics over exactly 25% temporal coverage in up to eight deterministic centered contiguous bursts | Approximate; materially faster in retained evidence, with different automatic frame choices expected |

Both modes analyze only the shared selectable window after source trims and
configured leading/trailing exclusions. Performance gives every nonzero burst a
one-frame motion lookbehind. User and random frames still span the whole eligible
window; only metric-based dark, bright, and motion choices are sample-limited.

The following alternatives are not part of the locked system:

- no third public analysis mode;
- no 12.5% or 6.25% production sampling tier;
- no decoder loop-filter shortcut or forced decoder thread count;
- no automatic NVIDIA/CUVID path; and
- no legacy 320-pixel metric backend.

## Reading the quality evidence

The final sparse decision data contains several different measurements that
must not be treated as interchangeable:

- **Category-pool retention** asks whether each performance-selected frame falls
  inside quality's configured dark, bright, or motion extreme pool. A 100% result
  does not mean the selected frame numbers are identical.
- **Exact overlap** compares the actual selected frame numbers. Low overlap is
  expected from a temporal sampler and is the clearest evidence that performance
  is an approximate mode.
- **Sampled ranking and metric agreement** compare quality and performance values
  only on frames that performance sampled. Exact agreement proves that the
  full-resolution PlaneStats calculation is intact on those frames; it says
  nothing about events between bursts.

The final runs used the deliberate decision profile in
`config/benchmark.config.toml`: 20 random frames, 10 frames in each metric
category, `dark_quantile = 0.20`, and `bright_quantile = 0.80`. Shipped defaults
use `0.05` and `0.95`, and ship with metric-category counts set to zero. These
measurements therefore validate the benchmark decision profile, not the shipped
default quantile pools.

## Corpus and protocol

Decision runs used three cold metric-cache repetitions with warm L-SMASH source
indexes and a fixed 2,400-frame window. The final sparse runs used source frames
`240..2640` so nonzero-start motion lookbehind behavior was exercised. Trial
order rotated deterministically, all three quality trials reported cache misses
and successful writes, and benchmark-only sparse candidates bypassed persistence.

| Runtime fact | Final sparse runs |
| --- | --- |
| Host | Windows 10 build 19045, AMD64, 24 logical CPUs |
| Python | 3.13.7 |
| VapourSynth | R76, API R4.2, 24 core threads, 4,096 MB core cache |
| FFmpeg/ffprobe | `git-2025-11-02-a677b38-ffmpeg-windows-build-helpers` |
| Metric cache | Cold; 3 misses and 3 successful writes for quality |
| Selection profile | 20 random; 10 each dark, bright, and motion; 20%/80% quantiles |

| Corpus | Analysis source facts | Active rectangle | Diagnostic frame types in the benchmark interval |
| --- | --- | --- | --- |
| Witch 4K HDR | HEVC Main 10, `yuv420p10le`, 3840x2160, 24000/1001 fps, 7,116 source frames | Dimension-derived 3600x2160 at `(120, 0)` | 2,006 B, 22 I, 369 P across 2,397 reported frames |
| Dan Da Dan S02E01 | H.264 High, `yuv420p`, 1920x1080, 24000/1001 fps, 34,502 source frames | Full frame | 1,406 B, 119 I, 875 P across 2,400 frames |

The NVIDIA diagnostic additionally recorded a GeForce RTX 5080 with driver
610.62, but it did not prove that CUVID was the effective decoder.

Results are machine-, decoder-build-, source-, and window-dependent. Speedups
below are paired within a single run; wall-clock medians from different runs are
not combined.

## Decision ledger

| Evidence commit | Evidence | Material result | Decision |
| --- | --- | --- | --- |
| Historical June record | `analysis-tier-benchmark-warm-index.json` (raw report removed) | Old NumPy quality was 430.34s; dense 320px performance was 130.27s, or 3.30x faster. Bright/motion exact overlap was 10/10; dark was 7/10. | Established the first practical performance direction; superseded by PlaneStats quality and temporal sampling. |
| `5202aa65` | `analysis-tier-benchmark-witch-baseline.json` (raw report removed) | Old quality median 232.491s versus old performance 115.031s, about 2.02x faster. | Baseline only; schema and both production implementations have since changed. |
| `5866c15f` | combined synchronous/concurrent reports (raw reports removed) | Combined PlaneStats preserved top-50 sets; concurrent traversal did not provide a useful normalized gain. | Kept one synchronous metric traversal; rejected concurrency as a performance lever. |
| `661c37de` | `quality-planestats-candidate-witch-4k-hdr.json` (raw report removed) | Full-resolution PlaneStats was 64.009s versus NumPy's 235.086s: 3.67x faster. Selected frames and top-50 orderings were exact; maximum motion drift was `8.80e-9`. | Accepted PlaneStats as quality under the practical-equivalence contract. |
| `00cd9dfd` | `analysis-decoder-candidates-witch-4k-hdr.json` (raw report removed) | Skip-loop-filter was 1.056x and forced max threads 1.029x relative to the dense comparison reference. | Rejected: neither reached the 1.5x minimum and each added complexity or approximation. |
| `6df04266` | `analysis-all-candidates-witch-4k-hdr.json` (raw report removed) | Normal 25%, 12.5%, and 6.25% sparse candidates measured 2.075x, 3.207x, and 3.735x relative to that report's quality reference. The 6.25% modes retained only 60% of motion selections. | Rejected 6.25% and skip-loop variants; narrowed the final run to normal-decoder 25% and 12.5%. |
| `6df04266` | `analysis-nvidia-cuvid-request-witch-4k-hdr.json` (raw report removed) | NVIDIA request was 1.204x with 100% category-pool retention, but GPU presence/utilization could not prove the effective decoder. | Diagnostic only; never promoted. |
| `4f6b4108` | final Witch sparse decision run (raw report removed) | Quality was 27.793s. The 25% candidate was 13.507s (2.058x; 51.40% reduction) with 100% category-pool retention. Exact bright/dark/motion overlap was 1/10, 0/10, and 3/10. The 12.5% candidate was 2.468x but retained only 90% of bright selections. | Accepted 25% as the balanced performance contract; rejected 12.5% as a public mode. |
| `4f6b4108` | `analysis-nvidia-cuvid-final-witch-4k-hdr.json` (raw report removed) | NVIDIA request was 1.239x with exact selections, but `effective_decoder_proven` remained false. | Rejected from production; the ledger is sufficient evidence. |
| `7dec388e` | final Dan Da Dan sparse decision run (raw report removed) | Quality was 4.317s. The 25% candidate was 1.717s (2.514x; 60.22% reduction) with 100% category-pool retention but only 1/10 exact overlap in each metric category. The 12.5% candidate was 3.817x with 100% pool retention. | Confirmed that 25% creates a meaningful speed tier on a second corpus. The faster 12.5% result did not outweigh its Witch miss or the cost of another public tradeoff. |

The evidence commits above identify when each report first entered version
control. The historical JSON schema did not embed the benchmark checkout commit
or dirty state, so the exact executed checkout cannot be reconstructed from
those files alone. The current benchmark harness records both automatically.

## Final sparse timing measurements

Times are compute-pipeline seconds from three paired cold repetitions. The
minimum, median, maximum, and population standard deviation are recorded so the
decision does not rely on a single central value.

| Corpus | Coverage | Samples | Min / median / max | Population SD | Speedup | Time reduction | Faster pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Witch | Quality, 100% | 2,400 | 27.209 / 27.793 / 28.204 | 0.408 | Reference | Reference | — |
| Witch | Sparse 25% | 600 | 13.481 / 13.507 / 14.579 | 0.511 | 2.058x | 51.40% | 3/3 |
| Witch | Sparse 12.5% | 300 | 11.162 / 11.260 / 12.176 | 0.457 | 2.468x | 59.49% | 3/3 |
| Dan Da Dan | Quality, 100% | 2,400 | 4.142 / 4.317 / 4.353 | 0.092 | Reference | Reference | — |
| Dan Da Dan | Sparse 25% | 600 | 1.645 / 1.717 / 1.735 | 0.039 | 2.514x | 60.22% | 3/3 |
| Dan Da Dan | Sparse 12.5% | 300 | 1.127 / 1.131 / 1.169 | 0.019 | 3.817x | 73.80% | 3/3 |

## Final sparse selection measurements

`Miss rate` is the fraction of sparse selections that were not within the stated
frame tolerance of any quality selection. `Nearest distance` records the median
and maximum absolute source-frame distance to the closest quality selection.

| Corpus | Coverage | Category | Quality-pool retention | Exact overlap | Miss rate | Tolerance | Nearest distance median / max |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Witch | 25% | Dark | 100% | 0/10 | 90% | 2 frames | 35.5 / 64 |
| Witch | 25% | Bright | 100% | 1/10 | 90% | 2 frames | 9.5 / 25 |
| Witch | 25% | Motion | 100% | 3/10 | 70% | 3 frames | 17.0 / 1,202 |
| Witch | 12.5% | Dark | 100% | 2/10 | 70% | 2 frames | 17.0 / 70 |
| Witch | 12.5% | Bright | 90% | 0/10 | 100% | 2 frames | 10.5 / 30 |
| Witch | 12.5% | Motion | 100% | 0/10 | 100% | 3 frames | 25.5 / 1,209 |
| Dan Da Dan | 25% | Dark | 100% | 1/10 | 80% | 2 frames | 11.0 / 80 |
| Dan Da Dan | 25% | Bright | 100% | 1/10 | 90% | 2 frames | 35.5 / 87 |
| Dan Da Dan | 25% | Motion | 100% | 1/10 | 90% | 3 frames | 80.5 / 261 |
| Dan Da Dan | 12.5% | Dark | 100% | 0/10 | 90% | 2 frames | 56.0 / 80 |
| Dan Da Dan | 12.5% | Bright | 100% | 0/10 | 80% | 2 frames | 43.5 / 75 |
| Dan Da Dan | 12.5% | Motion | 100% | 0/10 | 100% | 3 frames | 124.0 / 261 |

For both corpora and both sparse candidates, luminance and motion values on
sampled frames had zero maximum absolute error against quality at `1e-12`
tolerance. Within the sampled frames, dark, bright, and motion rankings all had
Spearman correlation `1.0` and 10/10 top-ten overlap. This proves metric fidelity
only on sampled frames; it does not reduce the temporal miss risk shown above.

The sampled share of quality's wider extreme pools also favored 25% coverage:

| Corpus | Coverage | Dark / bright / motion extreme frames sampled | Maximum distance to a sample, dark / bright / motion |
| --- | ---: | ---: | ---: |
| Witch | 25% | 30.17% / 20.83% / 28.33% | 113 / 113 / 113 frames |
| Witch | 12.5% | 14.33% / 9.00% / 18.13% | 132 / 131 / 131 frames |
| Dan Da Dan | 25% | 29.33% / 35.50% / 26.88% | 113 / 112 / 113 frames |
| Dan Da Dan | 12.5% | 15.67% / 20.00% / 13.75% | 132 / 131 / 132 frames |

## Evidence retention policy

Raw benchmark JSON is not retained in the repository. New outputs stay in the
ignored `generated/` directory only while they are being reviewed. When a run
changes a product decision, transcribe its decision-grade protocol, environment,
timing distribution, selection evidence, and caveats into this history, then
delete the raw output. Exact frame lists, per-frame metrics, probe payloads, and
other reproducible diagnostic arrays are intentionally omitted.

## Remaining validation

- Run the locked production modes with 10 metric selections per category at the
  shipped `0.05`/`0.95` quantiles before making release-wide default-profile
  quality claims.
- The final sparse runs used `selection_domain = null`; they are fixed-window
  algorithm evidence, not complete proof of production cache identity with trims
  or source overrides. Verify those through the normal application path.
- Add an SDR live-action or especially grain-heavy corpus when available.
- Re-baseline after meaningful VapourSynth, L-SMASH, FFmpeg, Python, driver, or
  benchmark-config changes.
