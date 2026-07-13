Status: Active
Scope: Lossless quality-backend experiment and exact window-bounded brightness/motion analysis, each isolated behind its own Windows benchmark gate
Owner: Codex (primary controller)
Updated: 2026-07-13

# Analysis metric performance execution plan

## 1. Executive decision

Proceed in two separately measured work packages:

1. evaluate a full-resolution, no-resize VapourSynth PlaneStats implementation as
   an internal candidate for the existing `quality` backend; and
2. after that candidate is accepted or rejected, calculate metrics only for the
   prepared selectable window, with the one-frame motion lookbehind needed to
   preserve existing results.

Neither package adds a public analysis mode. `quality` and `performance` remain
the only public modes. A candidate may replace the internal `quality`
implementation only after dense metric, ranking, selected-frame, and multi-clip
Windows evidence proves that it is lossless and materially faster. Window
bounding applies to both accepted backends and must preserve the exact source
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

### Non-goals

- No third public mode in this workstream.
- No additional downscaling, bit-depth reduction, frame subsampling, approximate
  motion algorithm, or other quality reduction.
- No concurrent VapourSynth frame scheduling; the measured concurrent experiment
  increased CPU without a normalized throughput gain and has been reverted.
- No demand-aware omission of luminance or motion. The common workload requests
  both, and partial cache payloads would add disproportionate state complexity.
- No NVIDIA/GPU-specific decoding path or hardware-dependent branching.
- No change to `sources.analysis_source = "fastest"`. It already exists and can
  be evaluated later as a configuration-only experiment.
- No changes to CLI flags, config schema, mode names, default mode, selection
  counts, quantiles, or public JSON output.
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
the analysis metric cache schema from v6 to v7. Old cache files must miss through
the existing version-mismatch path; do not migrate or partially accept them.

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
- dense luminance and motion values satisfy
  `allclose(rtol=0, atol=1e-12)`;
- maximum and mean absolute errors are reported even when the tolerance passes;
- identical dark, bright, and motion selected frame lists;
- identical production top-K rankings for every requested category; and
- no changed cache, source-frame, or active-rectangle identity.

Do not loosen the tolerance silently. Any failure is a stop condition for
production migration and must be explained from the first differing frame.

The candidate passes performance only when each case is faster in at least two
of three paired repetitions and its median metric wall time improves by at least
5 percent. Also report the median delta against the larger of the two observed
trial population standard deviations; results inside that noise band are
inconclusive, not a win. CPU-to-wall and memory regressions must be reported and
may reject the candidate even when wall time improves.

### 4.3 Window-bounding acceptance gate

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
equivalence. Dense values use the quality tolerance appropriate to the accepted
backend: exact equality for an unchanged algorithm, or the frozen `1e-12`
quality migration tolerance if PlaneStats quality was accepted.

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

Gate result (2026-07-13): rejected. The required 4K HDR Witch case improved
median compute time from 235.086 seconds to 64.009 seconds and preserved exact
selected frames and top-50 orderings, but motion exceeded the frozen
`allclose(rtol=0, atol=1e-12)` limit (`8.80e-9` maximum absolute error). Because
every required case had to pass, this single failure is decisive and additional
candidate clips cannot rescue the migration. Package 2 is skipped; the candidate
remains benchmark-only and NumPy remains production `quality`.

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

Commit: `perf(analysis): use lossless PlaneStats quality metrics`

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
- Package 2 has its own algorithm identity and commit, so reverting restores the
  NumPy quality backend; v7 or later cache isolation prevents accepting arrays
  produced by another identity.
- Package 3 is a single cache-schema boundary. Revert its code and authority-doc
  commit together; v7 entries then fail the restored v6 loader rather than alias.
- Never preserve a failed optimization by weakening equivalence thresholds,
  padding arrays, accepting stale cache metadata, or adding a hidden fallback.

## 8. Deferred options

After this plan is complete, reassess only with new evidence:

- `sources.analysis_source = "fastest"` as a configuration experiment;
- a deliberately lower-quality third mode with explicit product semantics;
- demand-aware metric payloads if real workloads frequently request only one
  metric family; or
- hardware-specific decoding if a portable, maintainable runtime contract can be
  proved across supported environments.
