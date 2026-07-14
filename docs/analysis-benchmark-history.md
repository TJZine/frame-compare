# Analysis Benchmark History

This is the curated record of analysis-mode performance decisions. It preserves
the material timing and selection evidence while keeping superseded benchmark
JSON and experimental commands out of the active documentation.

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

The sparse reports contain several different measurements that must not be
treated as interchangeable:

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

The retained runs used the deliberate decision profile in
`config/benchmark.config.toml`: 20 random frames, 10 frames in each metric
category, `dark_quantile = 0.20`, and `bright_quantile = 0.80`. Shipped defaults
use `0.05` and `0.95`, and ship with metric-category counts set to zero. These
reports therefore validate the benchmark decision profile, not the shipped
default quantile pools.

## Corpus and protocol

Decision runs used three cold metric-cache repetitions with warm L-SMASH source
indexes and a fixed 2,400-frame window. The final sparse runs used source frames
`240..2640` so nonzero-start motion lookbehind behavior was exercised.

The primary corpus was the 4K HDR Witch pair, analyzed from the reference inside
a dimension-derived `3600x2160` rectangle at `(120, 0)`. The secondary corpus was
the 1920x1080 H.264 Dan Da Dan S02E01 pair, using the full frame. Measurements
were collected on Windows with 24 logical CPUs, Python 3.13.7, VapourSynth R76,
and API R4.2. The NVIDIA diagnostic also recorded a GeForce RTX 5080 with driver
610.62.

Results are machine-, decoder-build-, source-, and window-dependent. Speedups
below are paired within a single report; wall-clock medians from different
reports are not combined.

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
| `4f6b4108` | [`analysis-sparse-final-witch-4k-hdr.json`](benchmark-evidence/analysis-sparse-final-witch-4k-hdr.json) | Quality was 27.793s. The 25% candidate was 13.507s (2.058x; 51.40% reduction) with 100% category-pool retention. Exact bright/dark/motion overlap was 1/10, 0/10, and 3/10. The 12.5% candidate was 2.468x but retained only 90% of bright selections. | Accepted 25% as the balanced performance contract; rejected 12.5% as a public mode. |
| `4f6b4108` | `analysis-nvidia-cuvid-final-witch-4k-hdr.json` (raw report removed) | NVIDIA request was 1.239x with exact selections, but `effective_decoder_proven` remained false. | Rejected from production; the ledger is sufficient evidence. |
| `7dec388e` | [`analysis-sparse-final-dandadan-s02e01-1080p.json`](benchmark-evidence/analysis-sparse-final-dandadan-s02e01-1080p.json) | Quality was 4.317s. The 25% candidate was 1.717s (2.514x; 60.22% reduction) with 100% category-pool retention but only 1/10 exact overlap in each metric category. The 12.5% candidate was 3.817x with 100% pool retention. | Confirmed that 25% creates a meaningful speed tier on a second corpus. The faster 12.5% result did not outweigh its Witch miss or the cost of another public tradeoff. |

The evidence commits above identify when each report entered version control.
The historical JSON schema did not embed the benchmark checkout commit or dirty
state, so the exact executed checkout cannot be reconstructed from those files
alone. Future reports should record both automatically.

## Retained evidence and cleanup policy

The repository retains only the two final sparse decision reports:

- 4K HDR Witch, which contains the accepted 25% result and the decisive 12.5%
  bright-category miss; and
- Dan Da Dan animation, which provides the second-corpus timing and selection
  result.

Superseded baseline, implementation, decoder, full-matrix, and NVIDIA JSON is
removed after its material result is captured in this ledger. New benchmark
outputs belong in ignored `generated/` while under review. Promote only the
smallest decision-grade evidence into `docs/benchmark-evidence/`.

## Remaining validation

- Run the locked production modes with 10 metric selections per category at the
  shipped `0.05`/`0.95` quantiles before making release-wide default-profile
  quality claims.
- The retained final reports have `selection_domain = null`; they are fixed-window
  algorithm evidence, not complete proof of production cache identity with trims
  or source overrides. Verify those through the normal application path.
- Add an SDR live-action or especially grain-heavy corpus when available.
- Re-baseline after meaningful VapourSynth, L-SMASH, FFmpeg, Python, driver, or
  benchmark-config changes.
