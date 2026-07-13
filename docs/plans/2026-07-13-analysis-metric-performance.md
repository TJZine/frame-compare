Status: Active
Scope: Practical-equivalence quality migration, exact window-bounded brightness/motion analysis, benchmark-only sparse performance candidates, and an isolated NVIDIA decoder experiment, each independently measurable on Windows
Owner: Codex (primary controller)
Updated: 2026-07-13

# Analysis metric performance execution plan

## 1. Executive decision

Proceed in five separately measured workstreams:

1. evaluate a full-resolution, no-resize VapourSynth PlaneStats implementation as
   an internal candidate for the existing `quality` backend; and
2. benchmark dense software-decoder quality reductions that could make
   `performance` meaningfully faster than the accepted PlaneStats quality
   backend without changing frame coverage or motion semantics; and
3. after the backend decisions are frozen, calculate metrics only for the
   prepared selectable window, with the one-frame motion lookbehind needed to
   preserve existing results;
4. benchmark full-resolution PlaneStats on deterministic contiguous bursts at
   25%, 12.5%, and 6.25% window coverage, with skip-loop filtering retained only
   as a separately attributable variant; and
5. benchmark the bundled L-SMASH Works NVIDIA preference in isolation, recording
   fallback/verification state rather than assuming that a successful load used
   hardware decoding.

None of these workstreams adds a public analysis mode. `quality` and `performance` remain
the only public modes. A candidate may replace the internal `quality`
implementation after explicit maintainer acceptance of practical selection/ranking
equivalence, tightly bounded float drift, and a material speedup. The maintainer
accepted implementation after the 4K HDR evidence; the next Windows matrix validates
the combined production path rather than acting as a pre-implementation block.
Window bounding applies to both accepted backends and must preserve the exact source
frames selected by today's full-source calculation followed by slicing.

This is a high-risk analysis, cache-persistence, orchestration, and runtime
integration change. Production migration therefore requires full verification,
authority-document updates, Windows benchmark artifacts, and independent review.

## 2. Goals and non-goals

### Goals

1. Determine whether full-resolution PlaneStats can replace NumPy quality
   metrics without any user-visible selection-quality change.
2. Measure dense luminance and motion differences instead of inferring
   equivalence only from the selected frames.
3. Avoid calculating brightness and motion for source frames that trims and the
   shared lead/trail ignore window have already made unavailable for selection.
4. Preserve source-frame numbering, user/random-frame behavior, active-rectangle
   behavior, and the motion value at the first selectable frame.
5. Make metric-window cache identity and payload semantics explicit and
   fail-closed, with no fabricated full-source arrays.
6. Keep every experiment and production migration independently revertible and
   committed with conventional commit messages.
7. Determine whether a dense every-frame decoder-fast backend can make
   `performance` at least 1.5x faster than full-resolution PlaneStats quality.
8. Determine whether deterministic contiguous-burst sampling can make
   `performance` at least 1.5x faster while retaining useful automatic selection.
9. Measure NVIDIA decoding independently and fail closed when actual hardware use
   cannot be corroborated.

### Non-goals

- No third public mode is added before sparse benchmark evidence justifies one.
- No additional spatial downscaling or bit-depth reduction. The measured resize
  path did not reduce the dominant decode/render cost.
- No concurrent VapourSynth frame scheduling; the measured concurrent experiment
  increased CPU without a normalized throughput gain and has been reverted.
- No demand-aware omission of luminance or motion. The common workload requests
  both, and partial cache payloads would add disproportionate state complexity.
- No automatic production NVIDIA enablement or silent hardware-success claim;
  NVIDIA remains benchmark-only until the runtime can prove a maintainable
  effective-decoder contract.
- No change to `sources.analysis_source = "fastest"`. It already exists and can
  be evaluated later as a configuration-only experiment.
- No changes to application CLI flags, config schema, public mode names, default
  mode, selection counts, quantiles, or public JSON output.
- No benchmarking claim based only on a single clip, a single timing sample, or
  a benchmark window that still computes metrics for the full source.

## 3. Frozen behavioral contracts

### 3.1 Quality candidate

The candidate is benchmark-only until accepted. It must:

- operate on the same selected analysis source and prepared active rectangle as
  current quality mode;
- preserve the source format's full luma resolution and bit depth when extracting
  the Y plane; non-YUV input follows the same YUV conversion already performed by
  quality mode;
- perform no 320-pixel performance-mode resize;
- produce one luminance and one motion value for every requested metric frame;
- compute `PlaneStatsAverage` and `PlaneStatsDiff` from one combined synchronous
  graph traversal;
- define motion frame zero as `0.0`, matching the current quality contract; and
- stay unreachable from config, CLI mode parsing, and normal production dispatch
  until the acceptance gate is passed.

The implementation seam for the experiment is an analysis-owned, explicitly
candidate-named callable in
`src/frame_compare/analysis/metric_strategies.py`. The benchmark tool may invoke
that callable directly. It must not add an enum member, public mode, compatibility
alias, or cache entry that normal runs can load.

If accepted, a later isolated migration changes only the internal implementation
of public `quality`, updates the stable quality algorithm/backend identity, and
thereby invalidates legacy quality cache entries. Experimental dispatch and
candidate-only identity are then removed; tests may retain fixed legacy NumPy
fixtures or a private reference oracle.

If rejected, normal runtime behavior remains unchanged. Candidate production code
is removed unless it is required by the checked-in benchmark proof; any retained
benchmark-only implementation must remain clearly named and unreachable from
normal dispatch.

### 3.2 Exact metric window

The prepared shared `SelectionWindow` is expressed in the reference's
post-source-trim frame domain. For the chosen analysis clip, the requested metric
domain is frozen as:

```text
metric_source_start = analysis_clip.trim.trim_start_frames + selection_window.start_frame
metric_source_end_exclusive = metric_source_start + selection_window.frame_count
metric_frame_count = metric_source_end_exclusive - metric_source_start
```

Preparation must reject or clamp impossible domains using the same established
prepared-clip bounds policy before metric calculation; analysis must not silently
invent frames. Metric arrays are window-local: array index `i` represents source
frame `metric_source_start + i`.

Motion preserves the legacy full-source-then-slice result:

- if `metric_source_start == 0`, returned motion index 0 is `0.0`;
- if `metric_source_start > 0`, returned motion index 0 compares source frame
  `metric_source_start` with source frame `metric_source_start - 1`;
- the lookbehind frame is decoded only as an input and is never returned as an
  additional luminance or motion entry.

Frame selection receives window-local arrays and translates selected analysis
indices back to the existing reference/source frame domains exactly once.
Explicit user frames and random-frame planning remain independent of metric-array
availability and retain current behavior.

### 3.3 Metric metadata and cache schema v7

`MetricsMetadata.frame_count` becomes the number of stored metric entries, which
must equal both array lengths. Add these explicit integer fields:

| Field | Meaning |
| --- | --- |
| `source_frame_count` | Original selected analysis source frame count before metric windowing. |
| `metric_source_start` | Inclusive source-frame offset represented by metric array index zero. |
| `metric_source_end_exclusive` | Exclusive source-frame boundary represented by the arrays. |

The invariant is
`frame_count == metric_source_end_exclusive - metric_source_start`, with
`0 <= metric_source_start <= metric_source_end_exclusive <= source_frame_count`.
Do not create full-source arrays padded with zero, NaN, or sentinel values.

Add the same exact window boundaries and expected source frame count to
`MetricCacheRequest`. Include them in the cache fingerprint, serialized payload,
request-aware load validation, cache-only prevalidation, and diagnostics. Bump
the analysis metric cache schema from v6 to v7. Because the version is part of
the filename fingerprint, realistic v6 entries fail closed as cache misses; a v6
payload placed under a current fingerprint is rejected through the explicit
version-mismatch path. Do not migrate or partially accept either form.

The selection-domain token continues to include the prepared shared window, but
it is not a substitute for typed metric-request validation.

## 4. Measurement and acceptance matrix

### 4.1 Evidence recorded for every candidate trial

The benchmark artifact must record, per trial and as min/max/mean/median/
population-standard-deviation summaries where applicable:

- total analyze wall time and candidate metric wall time;
- source-load, graph-build, frame-render, metric-read/compute, and cache-write
  subphase times;
- process CPU time and CPU-to-wall ratio;
- frame throughput and the post-trial decode/PlaneStats machine-condition
  baseline;
- algorithm/backend identity, source facts, active rectangle, source metric
  window, metric array length, and proven cache state;
- maximum absolute error, mean absolute error, and first differing index for
  dense luminance and motion arrays;
- exact dark, bright, and motion selected frames;
- exact top-K ordering for luminance ascending, luminance descending, and motion
  descending, including ties resolved by production policy; and
- peak RSS where the platform can report it, with Windows unavailability stated
  rather than fabricated.

Use cold metric caches, warm source indexes, rotating trial order, and at least
three repetitions per candidate on the same machine. Keep decode baselines after
timed trials so they cannot warm the trials.

### 4.2 Quality candidate acceptance gate

Evaluate at least these source classes on Windows:

1. the established 4K HDR Witch case;
2. an 8-bit SDR live-action case; and
3. an animation or grain-heavy case that stresses ties and frame differences.

For each case, use the same source indexes, active rectangle, selection domain,
window, config, and machine state for legacy quality and the candidate.

The candidate passes quality only when all of the following hold for every case:

- exact array lengths and domains;
- maximum absolute luminance and motion error is no greater than `1e-7`;
- maximum and mean absolute errors are reported even when the tolerance passes;
- identical dark, bright, and motion selected frame lists;
- identical production top-K rankings for every requested category; and
- no changed cache, source-frame, or active-rectangle identity.

The artifact continues to report `allclose(rtol=0, atol=1e-12)` as a strict
numerical diagnostic. It is not the product gate after the maintainer's explicit
decision that selection/ranking equivalence with tightly bounded float drift is
the quality contract. Any failure of the frozen `1e-7`, selection, ranking, or
domain gates is a stop condition and must be explained from the first differing
frame.

The candidate passes performance only when each case is faster in at least two
of three paired repetitions and its median metric wall time improves by at least
5 percent. Also report the median delta against the larger of the two observed
trial population standard deviations; results inside that noise band are
inconclusive, not a win. CPU-to-wall and memory regressions must be reported and
may reject the candidate even when wall time improves.

### 4.3 Dense fast-decoder performance gate

Compare current `performance` and both benchmark-only decoder candidates against
the full-resolution PlaneStats candidate in the same rotating three-repetition
run. Both candidates use the current dense 320px synchronous PlaneStats graph;
one loads LWLibavSource with `ff_options = "skip_loop_filter=all"`, and the
other also passes the host logical CPU count as the explicit decoder thread
count. No candidate enters config, cache identity, or normal dispatch.

For every required clip class, record median speedup, percent time reduction,
median delta, both population standard deviations, the larger standard
deviation as a noise band, and paired-trial wins. A candidate passes only if it:

- is at least `1.5x` faster than full-resolution PlaneStats quality;
- wins a majority of repetition-paired trials;
- improves outside the larger observed timing standard deviation; and
- produces exact dense frame counts, windows, and source-frame mapping.

Treat `2x` as the desired performance result. For approximate quality, report
exact overlap, nearest-frame distances, top-K overlap, and rank correlations.
Additionally require every candidate dark selection to fall within legacy
quality's darkest 25 percent, every bright selection within its brightest 25
percent, and every motion selection within its highest-motion 20 percent. Exact
selected-frame equality is not required for `performance`.

If neither candidate reaches `1.5x`, do not lower spatial resolution again. A
later sparse reference/key-frame or fixed-budget experiment requires a separate
product and data-model decision because only analyzed source frames may be
selected and inter-frame source decoding cannot be assumed to disappear.

### 4.4 Window-bounding acceptance gate

For both accepted public backends, compare the new window-local result with a
legacy full-source calculation sliced to the same domain. Prove these cases:

- start zero and full end;
- nonzero start with the motion lookbehind;
- shortened end;
- simultaneous nonzero start and shortened end;
- source trim plus lead/trail ignore settings;
- active rectangle plus window;
- one-frame and minimum-window boundary cases; and
- cold-cache miss, exact cache hit, changed-window miss, and v6-version miss.

Require exact selected-frame, ranking, source-frame-number, and metadata-domain
equivalence. Dense values use exact equality for an unchanged backend; the
PlaneStats migration's `1e-7` bound applies only when comparing that backend
with the legacy NumPy oracle.

Windows timing must include at least one materially trimmed 4K HDR case. Report
excluded-frame percentage and metric-time reduction; the optimization is
accepted when the median improvement is positive outside the observed noise
band and scales plausibly with excluded frames. A no-trim/full-window run must
show no material regression (no more than 5 percent median metric-time loss).

## 5. Execution packages and commit boundaries

### Package 0: durable plan

Permitted file:

- `docs/plans/2026-07-13-analysis-metric-performance.md`

Verification: `git diff --check` and direct plan inspection.

Commit: `docs(analysis): plan metric performance improvements`

### Package 1: full-resolution PlaneStats experiment

Assigned to one bounded implementation worker after this plan is committed.

Permitted files:

- `src/frame_compare/analysis/metric_strategies.py`
- `tools/benchmark_analysis_tiers.py`
- `tests/analysis/test_metric_strategies.py`
- `tests/test_benchmark_analysis_tiers.py`
- `docs/analysis-performance-validation.md`

Required implementation:

- add the benchmark-only full-resolution PlaneStats candidate seam;
- expose it from the benchmark tool only through
  `--mode quality-planestats-candidate`; this string is not a config enum value;
- have the candidate trial load the source through `DefaultVSLoader`, call the
  candidate seam directly, construct non-cacheable in-memory `FrameMetrics`, and
  report cache state as bypassed/not-written; give the artifact the explicit
  experimental identity `quality_fullres_planestats_candidate_v1` and backend
  `vapoursynth-planestats-fullres`;
- report a comparable cold compute-pipeline duration for every tier, defined as
  total analyze duration minus cache lookup and cache write. Use this duration,
  which retains source load and metric work, for the 5-percent performance gate;
  do not claim a win from the candidate merely skipping persistence;
- add focused fake-clip tests for graph construction, active-rect behavior,
  first-frame motion, length/error handling, and non-reachability from normal
  mode dispatch;
- add benchmark candidate selection and dense difference/ranking output;
- document exact Windows PowerShell commands for the three source classes and a
  compact artifact comparison command; and
- preserve all current `quality` and `performance` runtime identities and output.

Focused proof:

```bash
.venv/bin/pytest -q tests/analysis/test_metric_strategies.py tests/test_benchmark_analysis_tiers.py
.venv/bin/pyright --warnings
.venv/bin/ruff check src/frame_compare/analysis/metric_strategies.py tools/benchmark_analysis_tiers.py tests/analysis/test_metric_strategies.py tests/test_benchmark_analysis_tiers.py
git diff --check
```

Worker stop conditions: any need to edit config/enums, cache/runtime dispatch,
files outside the permitted list, or ambiguity in the dense comparison contract.
The worker does not commit. The controller audits, re-verifies, and commits:

`perf(analysis): add lossless quality backend experiment`

### Gate A: Windows quality-candidate decision

The maintainer runs the documented Windows matrix and adds distinct JSON
artifacts under `generated/`. The controller adjudicates every quality and
performance criterion before allowing Package 2. Failed or incomplete evidence
stops migration but does not block proceeding later with independently safe
window bounding on the existing NumPy quality backend.

Gate status (2026-07-13): accepted for implementation by explicit maintainer
decision under the practical-equivalence contract. The Witch run improved
median compute time from 235.086 seconds to 64.009 seconds, preserved exact
selected frames and top-50 orderings, and had `8.80e-9` maximum motion error.
The original strict `1e-12` rejection was superseded by the maintainer's explicit
practical-equivalence contract and its frozen `1e-7` dense-error ceiling. The
8-bit SDR and animation/grain-heavy cases remain required release evidence, but
now validate the implemented combined path instead of blocking Package 2.

### Package 1b: dense fast-decoder benchmark experiments

This package is benchmark-only and may proceed while the remaining Gate A clips
are collected. Permitted implementation files:

- `src/frame_compare/vs/source.py`;
- `src/frame_compare/analysis/metric_strategies.py`;
- `tools/benchmark_analysis_tiers.py`; and
- directly corresponding focused tests.

Permitted documentation files:

- `docs/analysis-performance-validation.md`; and
- this plan.

Required outcome:

- add typed optional LWLibavSource decoder options without changing default
  source loading;
- expose the existing dense 320px PlaneStats calculation for exact reuse by the
  benchmark candidates;
- add `performance-skip-loop-filter-candidate` and
  `performance-skip-loop-filter-max-threads-candidate` only to the developer
  benchmark tool;
- keep both strings invalid as application performance modes and bypass
  production metric caches;
- record exact decoder identity, quality-category retention, and timing relative
  to the full-resolution PlaneStats candidate; and
- document the three-class Windows commands and `1.5x`/desired-`2x` gate.

Focused proof:

```bash
.venv/bin/pytest -q tests/vs/test_source.py tests/analysis/test_metric_strategies.py tests/test_benchmark_analysis_tiers.py
.venv/bin/pyright --warnings
.venv/bin/ruff check src/frame_compare/vs/source.py src/frame_compare/analysis/metric_strategies.py tools/benchmark_analysis_tiers.py tests/vs/test_source.py tests/analysis/test_metric_strategies.py tests/test_benchmark_analysis_tiers.py
git diff --check
```

The worker does not commit. The controller audits, re-verifies, and commits:

`perf(analysis): add decoder-fast benchmark candidates`

### Package 2: accepted quality migration, conditional

This package exists only if Gate A passes. Before delegation, the controller
freezes a bounded packet against the then-current diff. Expected permitted files:

- `src/frame_compare/analysis/metric_strategies.py`
- `src/frame_compare/analysis/metric_identity.py`
- focused strategy/identity/cache tests;
- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- `docs/analysis-performance-validation.md`

Required outcome: public `quality` uses the accepted backend, its stable
algorithm/backend identity changes, legacy quality caches miss, and no
candidate-only public surface remains.

Commit: `perf(analysis): use PlaneStats quality metrics`

If Gate A fails, replace this package with removal or benchmark-only containment
of the rejected candidate and record the decision in the validation document.

### Package 3: exact metric-window model and cache v7

This begins only after the quality backend decision, so window equivalence uses
one frozen baseline. Assign it to one worker because the model, cache, calculation,
and orchestration changes share invariants and are not safely disjoint.

Permitted production files:

- `src/frame_compare/analysis/types.py`
- `src/frame_compare/analysis/cache_io.py`
- `src/frame_compare/analysis/metrics.py`
- `src/frame_compare/analysis/metric_strategies.py`
- `src/frame_compare/orchestration/phase_selection.py`
- `src/frame_compare/orchestration/preparation.py`
- `src/frame_compare/orchestration/execute_run_helpers.py`

Permitted proof/documentation files:

- directly corresponding tests under `tests/analysis/` and
  `tests/orchestration/`;
- `tools/benchmark_analysis_tiers.py`;
- `tests/test_benchmark_analysis_tiers.py`;
- `docs/analysis-performance-validation.md`;
- `docs/current-architecture.md`;
- `docs/current-cli-contract.md`.

Before delegation, the controller must trace and list the exact cache-only request
construction sites from the current tree; the worker stops if another production
file is required. Required implementation is the frozen contract in sections 3.2
and 3.3, legacy-full-versus-window proof support, and no selection-policy change.

Focused proof must cover strategy slicing/lookbehind, metadata invariants, cache
serialization/validation/version mismatch, orchestration translation, cache-only
prevalidation, and benchmark JSON. The controller then runs full verification.

Commit boundaries:

1. `perf(analysis): bound metrics to selection window`
2. `docs(analysis): document windowed metric validation`

Split documentation only if code and authority docs remain consistent at every
commit; otherwise use one atomic conventional commit.

### Gate B: Windows window-performance decision

Run the documented cold-cache trimmed and full-window controls for both public
modes. Add JSON artifacts without overwriting Gate A or historical artifacts.
Any frame/ranking mismatch, incorrect first-window motion, changed source-frame
number, cache alias, or unexplained full-window regression stops acceptance.

### Package 3b: sparse and NVIDIA benchmark candidates

This package is benchmark-only. It adds no config enum, public mode, or reusable
production cache payload.

Implementation files:

- `tools/benchmark_analysis_tiers.py`;
- `tests/test_benchmark_analysis_tiers.py`;
- the typed optional `prefer_hw=1` loader seam in `src/frame_compare/vs/source.py`
  and its focused tests; and
- `docs/analysis-performance-validation.md`.

Required sparse outcome:

- exact deterministic 25%, 12.5%, and 6.25% contiguous-burst budgets;
- separate normal-decoder and skip-loop-filter variants;
- one non-selectable lookbehind for every nonzero burst;
- an explicit sampled-index to source-frame map with source-space exclusions and
  minimum gaps;
- full-window user/random behavior;
- bounded production quality as the timing/reference domain; and
- timing, selected-frame drift, category retention, sampled fidelity/ranking,
  quality-extreme coverage, and nearest-sample diagnostics in JSON.

Required NVIDIA outcome:

- full-resolution bounded PlaneStats with `LWLibavSource(prefer_hw=1)`;
- preflight failure when `nvidia-smi` cannot establish an NVIDIA runtime;
- GPU/driver and system-wide decoder-utilization evidence; and
- an explicit unverified/fallback-possible status. GPU presence, successful load,
  or decoder utilization must never be reported as proof that CUVID was the
  effective decoder.

Commit boundaries:

1. `feat(benchmark): expose NVIDIA decoder preference`
2. `feat(benchmark): add sparse analysis candidates`
3. `feat(benchmark): add NVIDIA analysis candidate`
4. `docs(analysis): document performance candidate validation`

### Gate C: Windows sparse/NVIDIA decision

Run the documented three-class sparse matrix and isolated NVIDIA command. No
sparse candidate becomes a public third mode unless it passes the frozen timing
gate on every required clip and the maintainer accepts its measured selection
quality. NVIDIA remains experimental unless a maintainable effective-decoder
contract can be proven; speed alone cannot satisfy that contract.

### Package 4: independent review and closeout

After both accepted packages are present, assign a read-only production reviewer
to inspect the complete commit range. The reviewer must focus on metric-domain
correctness, PlaneStats/NumPy equivalence evidence, cache v7 fail-closed behavior,
selection index translation, public-contract drift, and missing boundary tests.
The controller adjudicates findings, applies accepted fixes in focused conventional
commits, reruns full verification, audits the final diff, and marks this plan
`Status: Historical` only when no required work remains.

## 6. Full verification and handoff

Run after each production migration and again after review fixes:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
git diff --check
```

Windows benchmark execution is a required external proof, not replaced by the
local fake-clip suite. The final handoff lists every artifact, candidate decision,
median/noise result, dense-error maximum/mean, selected-frame result, cache schema
result, reviewer finding disposition, and commit hash.

## 7. Rollback

- Package 1 is experimental and can be reverted without changing runtime modes.
- Package 2 has its own algorithm identity and commit; reverting its migration
  together with the legacy-helper cleanup restores the former NumPy quality
  backend. v7 or later cache isolation prevents accepting arrays produced by
  another identity.
- Package 3 is a single cache-schema boundary. Revert its code and authority-doc
  commit together; v7 entries then fail the restored v6 loader rather than alias.
- Never preserve a failed optimization by weakening equivalence thresholds,
  padding arrays, accepting stale cache metadata, or adding a hidden fallback.

## 8. Deferred options

After this plan is complete, reassess only with new evidence:

- `sources.analysis_source = "fastest"` as a configuration experiment;
- promotion or rejection of a sparse fixed-budget performance backend after the
  new three-class artifacts are adjudicated;
- demand-aware metric payloads if real workloads frequently request only one
  metric family; or
- hardware-specific decoding only if evidence beyond the current unverified
  NVIDIA request can prove a portable, maintainable effective-decoder contract.
