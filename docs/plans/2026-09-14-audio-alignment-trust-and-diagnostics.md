---
search:
  exclude: true
---

Status: Active
Scope: Audio-alignment trust decisions, retained diagnostics, VSView review UX,
       and evidence-led estimator robustness
Owner: Frame Compare implementation session

# Audio-alignment trust and diagnostics — implementation plan

**Repository:** `TJZine/frame-compare`
**Target branch:** `dev/v0.6.0-review-remediation`
**Pinned starting SHA:** `326da610a1f6d9baee7ea58d509f05f59af0f004`
**Intended tracked path:** `docs/plans/2026-09-14-audio-alignment-trust-and-diagnostics.md`
**Plan date:** September 14, 2026
**Execution state:** P1 verified at `14d82237011da0e2efd518ed6c70e64e732d9a21`.
P2–P6 remain pending or evidence-gated as recorded below.

## Executive recommendation and report adjudication

Implement retained evidence and honest review UX before changing automatic acceptance. Preserve one immutable audio attempt, make its decision explicitly **trusted automatic**, **provisional**, or **unavailable**, and keep the offset authorized for trimming separate. Write a bounded, run-local diagnostic snapshot before review. A human decision is a second fact; it must not rewrite the first.

Then validate a conservative quality-qualified policy against continuous full-decode oracles and labeled negative controls. Keep `consensus_minimum_ratio = 1.0`; deliberately redefine its denominator to qualified voters in the new estimator policy, disclose that change, and add independent temporal-support requirements plus a credible-contradiction veto. Do not use a numeric majority threshold to excuse a real edit. The proposed fixed quality floors are a testable conservative policy proposal, not a calibrated probability or a finding from the original incident.

The first deliverable is packages P1–P2. They preserve current automatic results, including existing conservative rejections, while making them explainable. P3–P4 are required before claiming that automatic acceptance itself has been improved. P5 provides strictly diagnostic bounded rechecks only where the specified evidence gate justifies them. P6 supplies release acceptance, including visible native Windows proof.

| Report recommendation or finding | Decision in this plan |
| --- | --- |
| Weak successful dissent can veto four strong zero votes; failed windows disappear; evidence is lost before review | **Accept.** The pinned consensus and service sources confirm these mechanisms. They do not identify the original incident's cause. [R1–R4] |
| Observability before acceptance-policy relaxation | **Accept.** P1–P2 do not change offsets, gates, stream choice, extraction commands, or cache policy identity. |
| Separate trusted offset from a rejected candidate; preserve the original attempt after manual confirmation | **Accept.** No candidate is ever copied into the existing trusted-offset map. |
| The report's maximal hierarchy of stream/window/count/consensus/decision/envelope types | **Modify.** Use five small immutable records, reuse existing result/provenance owners, and derive counts and frame-bin distributions. Do not add separate counts, consensus, plan, event-bus, or evidence-repository abstractions. |
| A run-local audit artifact | **Accept, in P1.** Versioned, bounded, atomic, path-contained, diagnostic-only, and not read by cache lookup or trim application. |
| Quality-qualified voting and several independent intervals | **Accept as the target policy, gated by P3.** Specify exact support rules below. Weak/ambiguous estimates abstain; credible cross-frame contradictions veto. |
| Strong majority, a lower default ratio, or weighted votes | **Reject for this workstream.** No `1.0 → 0.8` fix, score-weighted vote, or adjacent-frame merge. |
| Disputed-window retry and explicit zero verification | **Modify.** At most one short disputed-interval recheck and one short zero-frame diagnostic, with a precomputed reservation and no votes or authority. Do not implement an unconditional retry framework. |
| Seek/grid, correction-radius, origin-mapping, rounding, algorithm or channel-search changes | **Defer production changes until their specific oracle gate.** Do not change any merely because the incident could involve it. |
| Missing duration should use container duration or unknown alignment should become zero | **Reject.** Preserve unavailable-timeline handling and the distinction between no correction and no evidence. |
| One visual zero proves constant alignment | **Reject.** Manual confirmation is a human-selected constant offset, not proof of a globally constant source relationship. |

**Important compatibility decision:** the future qualified-voter denominator is a public semantic change, not a transparent refactor. Existing numeric user settings remain in force; stronger settings are never lowered. The new policy must be named in normal alignment output and documented in the release/config contract. Users must not be told that `1.0` still means unanimity of every finite correlation. See §6.3.

## 1. Problem statement and evidence baseline

### 1.1 What is established

At the pinned snapshot, the normal long-source default selects five distributed 30-second reference windows. Every successfully correlated candidate votes, `minimum_valid_windows` defaults to one, and `consensus_minimum_ratio` defaults to `1.0`. Confidence and ambiguity are winner-level gates, not voter eligibility. Consequently four strong `+0f` candidates and one finite weak cross-frame candidate can reject, while one successful `+0f` candidate and four recoverable window failures can accept. [R1, R2, R5]

The `d7fbb2b8` change already groups by the integer frame correction. Small sample jitter inside a frame bin is not the remaining bug. Adjacent frame bins must remain distinct. `AlignmentConsensus` retains information that `AlignmentResult` discards; rejected sample offsets become null, the VSView map contains only accepted integers or null, and a manual replacement can erase the original rejection from downstream warnings/provenance. [R1–R4]

The selected-stream timing and metadata-driven stream choices are real inputs to the estimator. They are not evidence that the tracks contain matching language, mix, or edits. Missing selected-stream duration is an explicit pre-analysis rejection; container duration is not a permitted substitute. Early and late extraction follow different trim/resampling paths. FFmpeg documents that timestamp trimming and counting samples need not agree when timestamps are inexact; this justifies an oracle experiment, not a diagnosis. [R6, R7, X1, X2]

The native review boundary already validates session identity, the complete ordered comparison set, raw source-frame bounds, sidecar paths, and typed actions. Metadata and result versioning currently share a v1 constant. The cache is schema v2 and deliberately accepts reusable successful results, not arbitrary rejected attempts. [R8–R11]

### 1.2 Evidence limits and execution honesty

The supplied report's isolated consensus probes are accepted as prior evidence. This planning session read the pinned authority documents, relevant local skills, consensus, result/provenance, stream/planner/extraction, orchestration, cache identity, native contract/panel, and runtime-test surfaces. It did **not** rerun those probes, run pytest, execute FFmpeg, inspect the original media, or launch VSView.

The exact original incident cause remains unknown. Relevant missing facts include the original effective settings, selected streams, per-window data, runtime identity, and checks at separated video positions. Implementation must fix demonstrated mechanisms without recording any causal hypothesis as a confirmed incident diagnosis.

### 1.3 Fixed resource baseline

Preserve the current primary-analysis limits unless a separately approved change explicitly supersedes them: peak FFT size **2,097,152 points**, total **16,777,216 FFT points**, at most **16 selected analysis windows**, requested-rate scoring **3,000,000 samples per pair** and **15,000,000 samples total**, sequential pair lifetimes, ffprobe timeout **15 seconds**, and FFmpeg window timeout **120 seconds**. The current production seek preroll is five seconds. P5 explicitly budgets any additional work rather than treating a retry as free. [R5–R7]

## 2. Goals and explicit non-goals

### Goals

Explain every normal rejected audio attempt before optional VSView launch; distinguish accepted zero, provisional zero, and no candidate; preserve a useful rejected hypothesis without applying it; expose selected-stream and window evidence in terminal/VSView adapters; preserve the computed attempt after human review; close the minimum-one/failed-window support hole; keep genuine contradictory evidence fail-closed; retain bounded deterministic execution, JSON-only stdout, path containment, cache trust, and result validation.

### Non-goals

No claim to reproduce the original incident; no whole-track production decoding; no automatic edit matching, drift compensation, speech recognition, adaptive channel/track search, or new correlation algorithm; no implicit audio/video-origin correction; no adjacent-frame grouping; no weighted votes; no matrix of CLI/config flags; no shared negative cache; no cache-history reconstruction; no rich-evidence cache migration; no generic telemetry/logging framework; no report-viewer redesign; no native dependency update. Missing duration remains a truthful unavailable result rather than prompting unbounded duration discovery.

The proposed quality floors and support rules are safety filters, not estimates of the probability that alignment is correct. A high score, a stable diagnostic, a cache hit, and human confirmation are distinct facts.

## 3. Final product behavior

### 3.1 Three audio decision states and a separate application authority

| Audio decision | Required evidence | Application behavior | Review behavior |
| --- | --- | --- | --- |
| `trusted_automatic` | The active estimator policy accepted a concrete candidate | Existing computed authority may populate `frame_offset` and the trusted hint, including integer zero | Show accepted value, policy and support; allow manual replacement or keep-current |
| `provisional` | Automatic policy rejected, but a unique review-qualified frame group survives | `applied = false`; applied frame/time offsets remain null; the trusted hint stays null | Show the candidate, rejection reasons, disagreement and coverage; never populate confirmation inputs from it |
| `unavailable` | No single review-qualified candidate: no analysis, all unusable, only weak/ambiguous evidence, or tied qualified groups | No automatic authority or implied zero | Explain the cause; show any raw competing estimates only in details; offer manual input without a suggestion |

These are **audio** states, not a replacement for existing manual/cache provenance. An already validated manual offset may remain current even when historical audio evidence is unavailable. A reused computed result is labeled as previously accepted, not newly analyzed. The current authoritative offset and its origin are separately presented.

For P1–P2, `trusted_automatic` means accepted by the unchanged v5 policy. Do not silently apply the future P4 thresholds to old/cache results. In particular, P1 does not claim to have repaired the one-success/four-failures acceptance case.

### 3.2 Candidate selection for review, beginning in P1

Use a **display-only floor of score ≥ 0.90 and peak ratio ≥ 1.50**, with a finite requested-rate score, meaningful overlap under the existing correlation contract, an in-bounds requested-rate offset, and a valid frame conversion. An unbounded peak ratio may pass; a missing or NaN ratio may not. These fixed, conservative display thresholds are a product choice to avoid presenting arbitrary finite noise as a recommendation; they are not experimentally calibrated automatic thresholds.

For a rejected attempt, group review-qualified windows by the existing `samples_to_frames` conversion. Select a provisional candidate only when one group has a strictly larger support count than every other group. A single strong surviving window may be a **provisional** candidate, explicitly labeled `1 of 5 planned; insufficient temporal support`. Equal-sized qualified groups produce `unavailable` with `no_unique_candidate`, not a score-selected suggestion. Display all groups in details. The candidate's sample representative is an observed lower median from its own supporting windows.

Do **not** apply user automation thresholds to the display floor: a score of 0.99 rejected by an explicit 0.995 automation threshold is still useful for manual review. Show that configured gate as failed. Conversely, a result accepted by the unchanged legacy policy stays accepted even when it would not pass this new display floor; presentation must not retroactively change authority.

A strong rejected nonzero candidate follows exactly the same rules as zero. No branch fabricates a zero candidate from null, from failed analysis, or from a user leaving an input blank.

### 3.3 Normal terminal output

Emit a compact block after computation/cache resolution and **before** launching VSView or reporting that optional review is unavailable. Use the existing stderr/progress presentation boundary, temporarily clearing live progress as needed. This output must not depend on a later final-result warning, which a manual replacement can change.

Representative copy, with numbers populated from evidence:

```text
Comparison 1 — Audio alignment accepted: +0f.
No relative audio correction is required. Policy: v5; 5/5 correlated windows agree.
Streams: Reference a:0 -> Comparison a:1 (automatic metadata selection).
```

After P4, the support line becomes:

```text
Policy: quality-qualified-v1; 4/4 qualified windows agree; 3 independent intervals.
1 weak window abstained. No credible conflicting window was found in the sampled evidence.
```

Legacy-policy rejection with a useful zero:

```text
Comparison 1 — Audio alignment requires review. Provisional candidate: +0f (not applied).
4/5 correlated windows agree; configured consensus requires 100%. 1 weak window disagrees near 00:02:15.
Streams: Reference a:0 -> Comparison a:1 (automatic metadata selection).
Opening VSView for manual review. The candidate is a hint, not a confirmed alignment.
```

Credible contradiction after P4:

```text
Comparison 1 — Audio alignment requires review. Provisional candidate: +0f (not applied).
A credible +1f estimate conflicts near 00:02:15. A constant correction is not trusted.
Review separated points, including the conflicting interval.
```

Insufficient support:

```text
Comparison 1 — Audio alignment requires review. Provisional candidate: +0f (not applied).
Only 1 of 5 planned windows produced qualified evidence; 3 independent intervals are required. 4 windows failed.
```

No usable evidence:

```text
Comparison 1 — No usable audio candidate. No automatic correction applied.
5 windows planned; 0 usable estimates. 5 windows had insufficient signal.
```

Missing duration:

```text
Comparison 1 — Audio alignment was not computed. No usable candidate.
Selected comparison audio a:1 has no usable duration metadata. Container duration was not substituted.
```

Additional exact behavior:

- Stream summary names selected **audio ordinals**, not just “automatic.” Use `a:N` consistently; absolute stream index and metadata details belong in verbose/UI details. Report explicit selection as `explicit override`, and mixed selection per role rather than calling both automatic.
- Emit known language/commentary metadata mismatches in normal output: `Selected audio metadata differs (language/commentary); matching content is not established.` Unknown tags are unknown, not a match or a proven mismatch.
- For rejected results without review, finish with `Continuing without an accepted audio correction; rendering remains best-effort.` Existing source-set/configured trims may still apply. Never say that every source will remain literally untrimmed.
- Show one successful diagnostic location per run, relative to the run folder: `Audio diagnostics: alignment_diagnostics/`. Do not print an invented path when writing failed.
- When a strict user threshold caused rejection, include its actual value rather than only `low_confidence`.
- Reused computed zero: `Reused accepted audio alignment: +0f. Historical window and selected-stream details are unavailable; no audio analysis ran this time.` Do not substitute zero counts for missing counts.
- Reused human zero: `Reused manually confirmed alignment: +0f. Historical audio details are unavailable.` Do not call it audio-confirmed.
- After human zero: `Manually confirmed alignment: +0f. Original audio attempt remains rejected (insufficient_consensus); evidence retained.` Only claim retained-on-disk evidence after a successful write; otherwise say `evidence remains available in this run only`.

### 3.4 Verbose, quiet, JSON, plain-text and sanitization rules

Verbose stderr adds the complete bounded per-window table: stable ID, planned reference/search intervals, actual counts, analysis/requested rates, requested sample/frame lag, score and stage, peak ratio and stage, vote/review eligibility, failure category, and retry relation. Include selected ordinals/absolute indexes; codec, language, dispositions, channels/layout, rate; timing values and duration basis; selection ranking facts; configured/effective quality thresholds; all assessed failed gates; frame bins and denominator; independent-support calculation; budget reserved/used/skipped; runtime/policy identity and diagnostic path.

Do not emit raw arrays, full ffprobe payloads, full stderr, terminal control characters, or unsafe markup. Treat metadata labels as data in Rich and as plain text in Qt. Keep finite precision in human text; preserve full finite numeric values in the artifact. Scores are not percentages of correctness. A distribution percentage is explicitly a window fraction.

Reuse the existing verbosity/quiet and `no_color` controls; add no flag. Quiet mode retains the repository's suppression of routine accepted/status output and its minimal final success summary. Actionable rejection/write-failure warnings remain visible; P4 adds the single compatibility notice specified in §6.3 even in quiet mode. These are explicit stderr behavior changes, not a change to quiet success stdout. A requested GUI review always has the concise rejection explanation before launch. Non-TTY output is plain, static and nonblocking, using the existing ASCII status convention (`[OK]`, `[WARN]`, `[SKIP]`) rather than requiring Unicode or color. No reliance on cursor movement or interactive tables is permitted for meaning.

`run --json` stdout keeps its current success/error schema and contains JSON only. Preserve its existing pre-runtime incompatibility with `audio_alignment.use_vsview`, `force_interactive`, and prompted previous-offset reuse; this plan does not introduce JSON-plus-GUI sessions. Suppress new human blocks/tables in JSON mode. Emit rejection/write-failure and P4 policy notices only through the existing structured stderr logging boundary, with bounded scalar fields, not Rich output or a dump of the attempt. Do not add the new attempt object or warning fields to the public JSON result as an incidental dataclass serialization effect. Tests must separately parse stdout, inspect stderr, and prove incompatible JSON/review configurations still fail before estimation or launch. [R15]

### 3.5 Exact VSView presentation and interaction

Each comparison has a persistent **Audio evidence** summary independent of its manual draft. Expandable **Audio details** contains selected streams and the complete bounded window table; it must not import service policy or recompute eligibility. Replace generic `Stable` claims with `Offset variation: stable (diagnostic only)` when that summary is shown.

| State | Summary text | Marker text and behavior |
| --- | --- | --- |
| Trusted zero | `Audio alignment accepted: +0f` / `No relative audio correction required.` | `[ACCEPTED AUDIO] +0f — reference frame 0` and corresponding comparison marker |
| Trusted nonzero | `Audio alignment accepted: +Nf` / existing sign-correct trim explanation | `[ACCEPTED AUDIO] +Nf — reference frame R` / `comparison frame C` |
| Provisional | `Provisional audio candidate: +0f — NOT APPLIED` / reason and support, followed by `Verify manually; this candidate is not a confirmed alignment.` | `[PROVISIONAL — NOT APPLIED] +0f — reference frame R` / comparison equivalent; visually distinct from accepted markers but text carries the distinction |
| Unavailable | `No usable audio candidate` / specific cause / `Enter known offsets or align the sources manually.` | No candidate marker, including no implicit marker at zero |
| Cached computed, details absent | `Reused accepted audio alignment: +0f` / `Historical window and selected-stream details unavailable.` | `[REUSED ACCEPTED AUDIO]`; do not claim current-run support |
| Current human authority | `Current alignment: +0f — manually confirmed` plus the independently accurate audio summary | `[MANUAL ALIGNMENT]`, never an accepted-audio marker |

Use the existing canonical signed pair `(max(offset, 0), max(-offset, 0))` for origin hint markers. Validate each marker against raw source-frame bounds. Omit an out-of-range marker and explain it in details; never clamp it into a seemingly valid suggestion. A hint marker is an origin illustration, not a verified content landmark.

**No new “Accept candidate” button.** A provisional value must not prefill source-frame/known-offset fields, move playheads automatically, mark sources visited, increment readiness, or enable confirmation. Users may deliberately type the displayed value, including zero, and confirm through the existing validated manual route.

Use these primary button labels consistently:

- Source-frame basis: **Confirm these aligned positions**.
- Known-offset basis: **Confirm these known offsets**.
- Secondary whole-set action, in every state: **Keep current alignment**.

Keep-current help:

> Keeps each comparison's existing alignment. Provisional candidates are not applied or confirmed. Comparisons without an accepted or manually confirmed alignment remain unresolved.

Keep-current still writes one existing `keep_current` action per comparison; it never writes a confirmed zero for unresolved comparisons. Confirmation still requires every necessary source visit or every valid manual entry, then writes the complete ordered source set once. Do not add per-comparison save actions in this workstream.

Saved per-comparison text:

- Trusted: `Saved — accepted alignment +0f retained.`
- Provisional: `Saved — no automatic correction applied; provisional +0f was not confirmed.`
- Unavailable: `Saved — no accepted alignment; no audio candidate was available.`
- Existing human authority: `Saved — manually confirmed alignment +0f retained.`
- New manual confirmation after rejection: `Manually confirmed: +0f. Original audio attempt: rejected (insufficient_consensus).`
- New manual confirmation after accepted audio: `Manually confirmed: +0f. Original audio attempt: accepted (+Nf).`
- New manual confirmation without a usable candidate: `Manually confirmed: +0f. Original audio attempt: unavailable (<reason>).`
- New manual confirmation without a current computation: `Manually confirmed: +0f. No current audio attempt; historical audio details unavailable.`

Top-level saved text: `Alignment choices saved — close VSView to continue Frame Compare.` Disable save controls after a successful write, as today. Closing without saving is not keep-current or confirmation; preserve existing optional-versus-forced result handling. An optional missing/rejected result leaves prior authority unchanged; forced review follows the existing failure contract. Mixed trust states retain separate labels and authority throughout the one whole-set action.

## 4. Architecture and ownership decisions

Follow the existing import direction: orchestration → services → VSView → lower utility/runtime layers. VSView must not import `services.types` or implement estimator policy. The service maps its immutable domain evidence into a narrow native-review DTO; the panel renders validated DTOs. Do not introduce a service/orchestration back-reference. [R12]

| Owner seam / likely files | Responsibility and disposition |
| --- | --- |
| `services/types.py` | Cohesive growth: immutable attempt, decision and evidence leaf records; extend existing result/provenance by association, not inheritance or a second result workflow |
| `services/alignment_audio.py`, `services/errors.py` | Cohesive growth: selected stream/selection facts, planned and returned extraction facts, typed recoverable failure detail, and budget accounting. Only P3/P5-approved changes alter executable extraction |
| `services/alignment_correlation.py` | Correlation/scoring facts and typed signal failures; retain the sign, overlap and mode contracts. No presentation or persistence |
| `services/alignment_consensus.py` | Sole owner of grouping, review-candidate classification, automatic eligibility, coverage and contradiction policy. Build complete evidence even on rejection |
| `services/alignment.py` | Sequence original attempt, snapshot, pre-review presentation, native review, final authority and provenance. No new policy recomputation here |
| One focused adjacent diagnostics IO owner, likely `services/alignment_diagnostics.py` | New present-day responsibility: versioned bounded diagnostic serialization and atomic run-local writes. Not a reusable-offset repository or generic logger |
| Existing terminal presentation boundary, with a focused adjacent formatter only if needed | Render typed summaries/table to stderr. Move/reuse the existing rejected-warning formatter rather than duplicating reason interpretation in orchestration and UI |
| `services/alignment_vsview.py` | Translate service evidence into the native DTO; pass only existing trusted authority as the trusted hint; accept only validated whole-set results; report typed review outcome so provenance can distinguish keep-current, no result, and confirmation |
| `vsview/session_script.py`, `alignment_review_contract.py`, `alignment_review_panel.py` | Coordinated metadata v2 generation/strict parsing/rendering, unchanged result v1 validation, deterministic sessions and explicit UI semantics |
| `services/alignment_reuse_cache.py`, `alignment_previous_offsets.py` | Reusable accepted authority only. Reconstruct honest absence-of-history; explicitly exclude diagnostic payloads from cache serialization |
| `orchestration/phase_alignment.py`, `context.py`, relevant execution DTOs | Carry the original immutable attempt separately from applied alignment, including when `alignment` is null. Keep trim calculation dependent only on accepted/manual authority |
| `utils/types.py` / `WorkspacePaths`, `services/run_folder.py`, `utils/atomic_write.py` | Existing managed-path/atomic-write mechanics; register the new run descendant without changing the shared-cache exceptions |

A single immutable `audio_attempt` association on `AlignmentResult` survives manual replacement. Current-run provenance refers to that same value. At the orchestration boundary, carry it on the comparison's immutable state independently of whether an applied `ClipAlignmentState` exists; rejected attempts must not vanish because `alignment` remains null. Do not retain a parallel mutable dictionary owned by a UI callback.

The existing `AlignmentProvenance.computed_result` continues to mean an **accepted computed result eligible for embedded shared reuse**. Do not repurpose it to serialize rejected attempts into cache v2. The new attempt association supplies audit history instead. Preserve the final manual result's current cache eligibility, while explicitly serializing only the v2 fields it supports.

## 5. Typed contracts and invariants

### 5.1 Small cohesive model

Use five immutable records; the field descriptions are semantic contracts, not mandatory helper/class names. Reuse existing stability types. Do not add one class per stage, reason, counter, frame bin or output renderer.

| Record | Required fields / semantics |
| --- | --- |
| **Selected stream evidence** | Role and pathless source identity reference; resolved audio ordinal and absolute stream index; `explicit_override` or `automatic_metadata` selection; selected rank components/tie-break and comparison match/mismatch/unknown facts; codec, rate, channels/layout, language, default/original/commentary flags; stream start, input/container start, time base, selected duration and duration basis. Record normalized rational timing without pretending defaulted values were measured. |
| **Window record** | Stable logical ID; purpose (`primary`, `disputed_recheck`, `zero_check`); attempt number/parent ID; planned reference/search sample ranges and rates; actual returned counts per role/stage when observed; effective aligned overlap; origin basis (`planned_assumption` versus independently measured); local/coarse/global/requested lags when produced; requested frame candidate; requested-rate score and score stage; peak ratio and peak stage/rate; review-quality and configured-quality assessments; vote disposition; terminal stage/category; missing facts remain null. A zero-check child retains at most two local hypotheses, labeled `zero_bin` and `nonzero_bin`, reusing the candidate fields and their score/peak stages; other rows have no local hypotheses. |
| **Candidate** | Observed requested-rate sample representative and rate; frame correction; supporting logical IDs; median requested-rate score; minimum peak ratio, with its provenance available through member windows. Diagnostic time is derived from samples/rate, not substituted for frame correction. |
| **Audio decision** | Explicit tag `trusted_automatic`, `provisional`, or `unavailable`; candidate or null; primary reason; ordered assessed failed gates; unassessed gates when prerequisites were absent. Construction validates tag/candidate/authority relationships. |
| **Audio attempt** | Pair/source identity; attempt status (`complete`, `preanalysis_rejection`, `aborted`); actual estimator and diagnostic-policy identities; relevant runtime identity; effective config/FPS; selected streams; plan/rate/budget summary; all bounded window records; decision; existing compact stability summary if available. Counts/distribution/support are derived, or checked against the records when serialized. |

No separate `WindowCounts`, `ConsensusEvidence`, `PlanEvidence`, `TrustedAutomatic` subclass hierarchy, or generic `AlignmentEvidence` wrapper is necessary. A tagged decision with validated invariants explicitly represents the three cases. Adapter DTOs at the existing VSView boundary are justified, but are projections of this model rather than a second domain model.

For cache hits and preexisting manual overrides with no current computation, `audio_attempt` is absent with an explicit evidence-availability/origin value on the presentation/provenance boundary. Do not invent an empty current attempt. Cache origin and existing accepted values are sufficient to render the truthful historical state.

### 5.2 Facts retained per window and failure categories

Record one primary row for every planned logical interval, even if extraction or scoring fails. Default maximum primary rows remains 16. P5 records its bounded child checks without counting them as extra votes. Failed attempts must release arrays through the existing `finally` lifetime discipline.

Use finite categories with a separate stage, not regex classification of exception text:

| Stage | Categories to preserve |
| --- | --- |
| Selection / planning | `selected_audio_timeline_unavailable`, `selected_audio_timeline_empty`, `analysis_budget_exceeded`, plus the exact existing budget subreason |
| Decode | `decode_empty`, `decode_payload_invalid`, `decode_output_exceeded`, `decode_failed`, `decode_timeout`, `dependency_unavailable` |
| Signal / correlation / scoring | `non_finite_signal`, `insufficient_signal`, `insufficient_overlap`, `offset_out_of_bounds`, `scoring_bounds_invalid`, `correlation_failed` |
| Decision | `low_confidence`, `ambiguous_correlation_peak`, `insufficient_valid_windows`, `insufficient_consensus`, `insufficient_temporal_support`, `credible_conflict`, `no_unique_candidate`, `no_usable_windows` |

Unknown existing recoverable cases may use `correlation_failed` with a stage; never leak stderr to fill an explanatory gap. Preserve which role failed. Counts or origins not returned across a failed boundary are unknown, not zero. Record actual sample counts before releasing a successful pair; do not report the planned full span as decoded coverage when output was short.

Fatal FFmpeg/ffprobe dependency, startup, timeout and nonzero-exit failures retain their existing exception/exit behavior. A best-effort aborted diagnostic may capture their sanitized category, but they are **not** converted into recoverable window abstentions or an optional VSView session. Only the existing recoverable error family, with deliberately typed detail added at its throw sites, participates in the normal window loop.

Record the resolved stream choice at the selection owner, including the actual ranking facts used. Do not reproduce selection in a UI formatter or infer it from the configured override. The reference ranking considers commentary, default/original, channel count and ordinal; comparison ranking records the actual metadata similarity criteria used. Label that rationale “metadata selection,” never “verified matching soundtrack.” [R6]

P1 records measured returned counts, not measured first audio PTS. The current extractor does not return that observation. Mark decoded origins `planned_assumption`; mark audio-to-video origin evidence `not_measured` unless supplied by a genuinely measured later experiment. Retain a `metadata` versus `default_zero` basis for normalized stream/container starts so missing timestamps are distinguishable from a reported zero. Do not add a placeholder “measured origin” copied from the plan.

Runtime identity distinguishes the code-owned expected media-runtime fingerprint from observed FFmpeg/ffprobe version lines. P1 records versions only when already available from the current execution boundary; otherwise they are explicitly `not_observed`. It adds no version-discovery subprocess solely for instrumentation and never labels the expected fingerprint as a measured binary identity. P3's required native experiments record actual version lines independently. This bounded first-package limitation must be visible in verbose/artifact data.

### 5.3 Invariants that must be executable tests

1. Only an accepted automatic result, a validated manual result, or an eligible validated cache entry can authorize application. An artifact, candidate, score, stability label, or panel marker cannot.
2. `provisional` and `unavailable` computed results have `applied = false` and null applied frame/time offsets. A provisional `+0f` is an integer **inside the candidate only**.
3. A trusted computed result has a concrete candidate consistent with its applied frame correction. A final manual result may be applied while its attached original audio decision remains provisional/unavailable.
4. Zero is tested with `is None`, never truthiness. Blank manual input is not zero.
5. All raw successful estimates, weak estimates and failed-window facts survive. Rejection does not overwrite the candidate's score/sample value with the legacy aggregate placeholder zero.
6. The candidate's frame value uses the same `samples_to_frames` implementation as application. Retain raw sample jitter and the observed lower median; do not average two frame bins.
7. No second classifier changes the service's decision in terminal/VSView. Serialized counts and membership must agree with window IDs; retries never increase independent support.
8. Manual confirmation preserves the original attempt byte-for-byte in canonical diagnostic serialization. The final action is appended to the enclosing record, not merged into the audio decision.
9. Frames, ordinals and counts reject booleans; numbers are finite and bounded where appropriate. JSON contains neither `NaN` nor numeric `Infinity`. Encode an unbounded peak as the explicit string `"unbounded"`; null means not measured.
10. Evidence strings have bounded lengths and sanitized control characters. Invalid metadata/state combinations fail validation rather than falling back to zero or “accepted.”

### 5.4 Target acceptance policy after P3 evidence gate

**Quality proposal to validate:** base evidence quality is requested-rate score ≥ **0.90** and correlation peak ratio ≥ **1.50**, with valid signal/overlap/offset facts. These are the same conservative display floors from §3.2, proposed now as additional automatic safety floors. They do not become production acceptance rules until P3's predeclared controls pass.

Define populations separately:

- **Correlated:** a primary logical interval returned a valid, in-bounds requested-rate estimate, regardless of quality.
- **Credible / review-qualified:** it passes the base evidence-quality floors. This population identifies meaningful competing hypotheses.
- **Voting-qualified:** it is credible **and** passes the user's configured `confidence_threshold` and `ambiguity_peak_ratio`, and meets the coverage test for its observed overlap.
- **Independent support:** a temporally non-overlapping subset of the winning voting-qualified primary intervals, measured on the reference timeline's usable overlap. It is not simply a row count.

The configured effective score/peak minima for voting are `max(base_floor, configured_value)`. A raised user threshold must not hide a **credible** competing frame bin: the contradiction veto examines the base-credible population, including credible windows excluded by a stricter user threshold.

The new ratio is:

```text
qualified_consensus_ratio = winning_voting_qualified_windows / all_voting_qualified_windows
```

With zero voters the ratio is unavailable, not 1. Failed, weak, ambiguous and invalid/out-of-range intervals abstain from that denominator. They remain in the planned/correlated counts and reduce achievable temporal support. Qualified nonwinning windows count in the denominator and are also credible contradictions.

**Hard veto:** any primary credible estimate in a different frame bin prevents automatic acceptance of a constant correction, regardless of majority, configured ratio, stability label, or a favorable diagnostic recheck. A score tie-break never defeats this veto. This deliberately favors manual review for strong localized edits, drift and unresolved cross-frame extraction discrepancies.

Automatic acceptance requires all of the following: one selected frame group; configured minimum number of voting-qualified primary windows; configured ratio; configured quality thresholds; the temporal requirements below; no credible cross-frame contradiction; and a valid application-domain frame correction. No diagnostic child check can satisfy a missing requirement.

Retain `minimum_valid_windows` as an additional user floor, now over voting-qualified primary windows; an explicit value of five is never reduced to three. Retain all assessed failures with deterministic reason precedence: pre-analysis/fatal prerequisite, credible conflict, no candidate, insufficient configured window count, insufficient temporal support, confidence, ratio, ambiguity. P1 preserves the existing primary reason; P4 intentionally adopts the new documented precedence. Evaluate secondary gates only where their prerequisites exist.

**Ratio compatibility consequence:** under this initial conservative policy, a qualified cross-frame dissent already vetoes, so a configured ratio below 1.0 cannot make it safe. Keep the field and its numeric value; document that independent safety gates can dominate it. Do not invent weaker “almost qualified” votes just to make every ratio value change outcomes.

### 5.5 Temporal-support rules

Use `D`, the finite shared duration of the **selected audio streams**, not the video/container duration. Count support using actual useful aligned sample counts mapped to the reference timeline, explicitly retaining the assumed-origin limitation. Each contributing interval must deliver at least **90% of the aligned overlap that its plan/candidate made available**; preserve the existing minimum-sample/meaningful-signal check as well. This 90% rule is a proposed conservative coverage guard, validated by P3, not a substitute for signal quality.

| Shared selected-audio duration | Default plan after P4 | Automatic minimum |
| --- | --- | --- |
| `D ≤ 30 s` | One window over the full shared duration | One qualified full-overlap interval satisfying the observed-coverage guard, plus any larger explicit `minimum_valid_windows` requirement |
| `30 s < D < 90 s` | Normally two non-overlapping windows of length `min(30 s, D/2)`, beginning at 0 and `D - length`; explicit higher minimum counts are handled below | At least two non-overlapping qualified intervals reaching early and late coverage; any larger explicit count still applies |
| `D ≥ 90 s` | Retain five distributed 30-second windows by default | At least three non-overlapping supporting primary intervals, with support reaching the first and last thirds of the shared timeline; explicit larger count still applies |

“Reaching” means at least one contributing interval begins at or before `D/3`, and one ends at or after `2D/3`. Intervals selected for independent support must be pairwise disjoint on useful reference coverage, not just have different start times. Compute the maximum disjoint support deterministically by interval scheduling; verify the early/late requirement on an eligible support subset rather than accidentally losing it through an arbitrary greedy tie-break.

The medium-duration default-plan change is intentional: five overlapping 30-second intervals over a 65-second source are not five independent observations. It belongs to P4, with estimator-policy invalidation and native tests, not P1 instrumentation. With default window/stride settings and an explicit larger `minimum_valid_windows`, distribute `max(tier_default_count, minimum_valid_windows)` unique starts over the same available start range, including both endpoints, subject to the existing budgets. Preserve the tier's window length. Additional overlapping rows can satisfy the configured count but do not increase independent support. For example, a 65-second source with an explicit minimum of five gets five bounded 30-second rows and must have five qualified voters plus a qualifying two-interval disjoint subset. When only one unique full-duration window exists, do not duplicate it to satisfy a larger minimum; reject for insufficient valid windows.

For explicit window length/stride, retain the requested shape and bounded sampling grid. Do not silently shorten, densify or widen it to satisfy these safety rules. An explicit shape that cannot yield the required independent support produces provisional/unavailable review with `insufficient_temporal_support`. The numeric config remains valid. An explicit minimum that exceeds work capacity retains the existing budget rejection.

Very short sources can pass only when the full meaningful overlap is actually available and unambiguous; no arbitrary three-window requirement is imposed. Silence, repeated tones or too few meaningful samples do not become trusted because the file is short. P3 must include subsecond/short negative controls and the existing three-second positive controls. A single successful window on a long source never becomes trusted.

## 6. Persistence, versioning and compatibility

### 6.1 First-package diagnostic artifact

**Required in P1.** Use `<run-folder>/alignment_diagnostics/comparison-<ordinal>.json`, where the ordinal is the existing ordered comparison ordinal. Keep path construction in the focused diagnostics/managed-path owner. Do not derive names from untrusted titles or absolute input paths. This directory is a managed child of the reserved run folder, not `shared_alignment_cache_dir`.

Schema v1 is one pathless pair envelope:

```text
schema_version: 1
purpose: "diagnostic_only"
pair: reference identity digest, comparison identity digest, comparison ordinal,
      bounded presentation labels
original_audio_attempt: complete immutable attempt, or null with explicit historical absence
original_attempt_digest: canonical digest, or null when absent
review_outcome: pending | not_requested | confirmed | keep_current | no_result | rejected_result
final_resolution: validated origin, applied offset or null, and confirmed frame pair when available
```

Snapshot the completed/rejected attempt **before** starting native review. For runs without review, snapshot it before returning to orchestration. After review, atomically update the enclosing review/final-resolution fields while preserving the original attempt/digest. A fatal failure may write an aborted partial attempt and must re-raise the original exception. At most one pre-review and one final rewrite per pair; no append-only event stream, timestamped retry files or run-to-run accumulation. Compute `original_attempt_digest` as SHA-256 over UTF-8 JSON of the original attempt with sorted keys, compact separators, no numeric NaN/Infinity, and no trailing newline; the envelope, digest field and review/final-resolution fields are excluded. Pretty-printing the enclosing artifact may differ, but the original attempt's canonical bytes must remain identical before and after manual review. This digest detects accidental audit-history changes; it is not a signature or source of authority.

**Bound:** at most 16 primary records and the P5 maximum of two diagnostic child records, with no PCM/waveforms; **128 KiB maximum serialized UTF-8 bytes per comparison file** including the final outcome. At most one such file per comparison, so a run with `N` comparisons uses at most `N × 128 KiB`. This explicit input-scaled bound avoids introducing a new arbitrary source-count limit. Cap individual text fields at 256 characters, runtime version lines at 512, and all collections by the fixed plan/contract limits. The schema must fit its maximum supported records without silently dropping windows. A serializer overflow is a diagnostic write failure and a test/release defect, not permission to truncate the losing votes.

**Retention:** retain with the run folder until the user deletes it; no TTL daemon, automatic cross-run pruning, shared-cache entry, index or lookup path. Normal existing run-folder deletion removes diagnostics. Document that sharing a run folder also shares labels, file identity digests, metadata and timing facts.

**Privacy:** exclude absolute media paths, environment values, credentials, raw media, packet dumps, full subprocess stderr, and full path-bearing commands. Store source identity digests and bounded supplied labels; digests are pseudonymous references, not a promise of anonymization. Record a normalized extraction recipe with role placeholders, not a copied command line. Detailed oracle experiments may save command/PTS data only in their isolated test evidence directory and must be reviewed before sharing.

**Atomic and containment behavior:** use `write_text_atomic`/the current atomic owner with a same-directory temporary file. Validate the managed descendant, parent chain, and existing leaf; reject symlink/junction escapes and non-regular leaves under the existing Windows/POSIX containment contract. Do not follow a path supplied in metadata or a diagnostic file. Preserve the last valid snapshot on a failed final replacement and clean temporary files deterministically. A detected containment violation uses the existing typed fail-closed path behavior; it is not downgraded to a casual warning.

For ordinary disk-full/permission/write failures, preserve in-memory evidence and existing alignment authority, issue one stable stderr/run warning, and continue according to the existing media policy. Diagnostics are not a new prerequisite for trimming. Never claim that the artifact was saved. Tests must prove that a write failure cannot authorize a provisional result, alter a valid manual decision, suppress an original FFmpeg exception, or erase the initial snapshot.

**Trust rule:** production alignment/cache code never reads this artifact to select an offset or skip computation. VSView receives an in-memory-generated projection, not file-authorized evidence. Missing, corrupt, edited or unsupported diagnostic files cannot change trims and cannot become a negative cache. No diagnostic “repair” or migration reader is needed in P1.

### 6.2 Cache schema v2 and historical evidence

Keep shared reuse schema **v2** and run-local manual override schema **v1** throughout this plan. Continue validating the full source-set identity and existing compact stability fields. Do not serialize new rich evidence into the strict stability table. Do not add rejected attempts to the embedded-computed-result slot or write incomplete accepted source sets. Manual confirmation may still make a complete set eligible under existing rules; keep-current on an unresolved pair does not. [R9–R11]

P1–P2 leave the estimator-policy token unchanged because they do not change computation/application. Old/warm cache hits remain valid under existing identity checks, but presentation marks detailed historical evidence unavailable. Never run fresh stream selection merely to present it as the stream used by the historical computation.

A **cache schema bump would be required** if rich history became mandatory for cached authority, required fields/sign semantics changed, rejected attempts became reusable state, or complete-set/origin semantics changed. None is approved here. A diagnostic schema change alone does not force cache invalidation.

### 6.3 Estimator policy and user-configured policy

P4 must advance the estimator policy beyond pinned v5 before any result produced under the qualified-voter/coverage policy becomes reusable. Any production change to stream selection, extraction grid/preroll, effective scoring, rounding, candidate search, acceptance floors, minimum support or trust semantics likewise advances that identity. A display-only diagnostic-policy identity can change without changing reusable authority. If P5's rechecks remain read-only and cannot affect authority, they change diagnostic identity only.

The current estimator token keys both computed and human-confirmed shared entries. Preserve this conservative behavior: a P4 bump invalidates both origins' old shared hits. Do not split cache identities, rewrite old entries in place, or add a legacy-policy execution branch. Run-local explicit manual overrides retain their current precedence/schema.

Keep the configured default ratio at **1.0**. After P4 it means **100% of voting-qualified windows**, not 100% of finite correlations. The configured score, peak and minimum-window settings remain additional user constraints; never lower their explicit values or count fewer windows than requested. A high-quality contradiction remains a veto even for an explicit ratio of 0.8.

To make the semantic change non-silent, P4 must do all of the following in the same package:

1. Update the current CLI/config authority, guide, release notes and estimator identity.
2. Once per run before fresh estimation, emit stderr: `Audio policy: quality-qualified-v1. Consensus <value> applies to qualified windows; temporal support and credible-conflict checks also apply.` Emit this compatibility notice in quiet human mode too; do not add config-authorship detection or interpret an authored value differently from an equal default. JSON mode uses a structured stderr policy event instead of human text. Cache-only reuse prints no claim that fresh estimation ran.
3. Explain rejection with both raw and qualified counts, so `4/4` never hides the fifth weak or failed interval.
4. Make documentation explicit that setting `1.0` no longer requests unanimity of every successful raw correlation. This plan intentionally changes that public meaning; do not describe the release as acceptance-compatible. No special interpretation based on whether an authored `1.0` equals the default is permitted.

No new policy flag or config-authorship plumbing is required: this is one documented, versioned estimator contract, not two maintained estimators. The notice has one settled emission rule above. The numeric ratio is preserved, but its raw-voter meaning is not; release notes must identify this intentional compatibility break rather than suggesting that unchanged numeric configuration guarantees unchanged acceptance.

### 6.4 VSView metadata v2, result v1

Split the shared constant into explicit **metadata version 2** and **result version 1** at `alignment_review_contract.py`; keep the result wire schema and actions unchanged. Update generator, adapter, parser, panel, generated-session tests and native verifier fixtures atomically in P2. Do not ship a generator/parser mismatch. [R8]

Preserve all existing exact-key topology, role/ordinal/name/session fields. Retain `frame_compare_suggested_offset` as the trusted current-alignment integer or null only. Add exactly one metadata key, `frame_compare_audio_review`, whose value is a deterministic, strict JSON string. Its version is governed by metadata v2, not an independently evolving nested version. It contains:

- current entry authority/origin, separate from audio trust;
- audio decision, candidate/reasons and historical-evidence availability;
- bounded selected-stream and window projection, thresholds, support/denominator and diagnostic identity.

Freeze the payload's top-level key set as `current_authority`, `evidence_availability`, and `audio_attempt`. `current_authority` contains `origin` and nullable `frame_offset`; `origin` is `computed_this_run`, `shared_computed_offsets`, `interactive_confirmed_this_run`, `shared_previous_offsets`, `preexisting_manual_override`, or `none`. `evidence_availability` is `current_attempt`, `historical_details_unavailable`, or `not_computed`; `audio_attempt` is the bounded pathless projection of §5.1 or null. Each nested record has an explicit exact field set matching that semantic contract; reject duplicate keys and unsupported keys/types instead of relying on permissive dictionary defaults. A rejected current attempt has authority origin `none` unless a separately validated manual authority exists. Historical absence has a null attempt, never synthesized zero counts. The payload uses finite scalars, bounded strings/arrays, and the explicit unbounded-peak encoding. It is capped at **128 KiB per comparison**. Do not include a file path for the panel to follow. The service serializer owns domain projection; the native contract owns validation of that projection. Candidate/decision/trusted-hint consistency is checked, including the valid case of manual current authority with unavailable/rejected original audio.

The panel must never derive accepted authority from the new payload: its candidate information is presentation-only, and keep-current means retain what the service already holds. Only the unchanged result validator can admit manually confirmed frame pairs.

**Old sessions:** metadata v1 and unknown future versions are rejected for review, not upgraded. Exact UI copy: `Alignment review requires a newly generated session. This session uses metadata v1; this version requires v2.` Clear panel-owned markers and disable save controls. Ordinary non-Frame-Compare sessions remain inert without an alarming migration message. Malformed/mixed v2 sessions use the existing rejected-workspace path. An old result file cannot be imported into a fresh session merely because result schema v1 is still supported: session identity, trusted sibling path, absence-at-start, complete order and frame bounds remain mandatory.

Generated script bodies remain deterministic for identical inputs. Derive the diagnostic projection and identifiers from the existing pair/session identities; do not inject new timestamps, random IDs, machine paths or artifact write status into script bodies. Reserve the bounded child-hypothesis field in the v2 projection as empty until a justified P5 branch supplies it; adding that branch must not silently change the v2 key set.

## 7. Ordered implementation packages

Tracking: `[ ]` not started; `[~]` executing; `[x]` verified; `[deferred]` only with the explicit evidence-gate disposition described below. Record actual candidate SHA, commands/results, skips, artifacts and native host for each package; do not replace that record with “tests should pass.”

### [x] P1 — Immutable evidence, preserved rejection and diagnostic persistence

**Outcome.** Every new audio attempt retains selected streams, every planned window and categorized outcomes, plus a separate rejected review candidate. The original attempt survives manual replacement and is snapshotted before review. Automatic offsets and cache reuse remain unchanged.

**Owner seams / likely files.** `services/types.py`, `alignment_audio.py`, `alignment_correlation.py`, `alignment_consensus.py`, `alignment.py`, `alignment_vsview.py`, `alignment_reuse_cache.py`; one adjacent diagnostics IO owner; managed runtime path DTOs; `orchestration/phase_alignment.py` and comparison state. Restrict native-service changes to returning typed review outcome/provenance, not changing result acceptance or wire formats.

**Public behavior.** Add the run-local artifact and a basic pre-review rejection explanation containing reason and candidate/not-applied status. It is acceptable for the old panel to lack rich detail until P2, but the user must have the explanation before it opens. Historical cache details are explicitly unavailable. Record artifact write warnings without adding JSON stdout fields.

**Contracts/invariants.** Implement §5.1–5.3 and §6.1–6.2. Keep the v5 acceptance function's decisions, primary reasons, selected groups, applied samples/frames and cache identity unchanged. Derive the display candidate separately; evaluating additional gates for diagnostics must not affect application. Capture failure facts without broadening recoverable exceptions. Keep existing accepted `computed_result` cache semantics, using the new attempt association for rejected history.

**Dependencies.** None beyond the pinned baseline and authority/skill reads. Preserve unrelated local changes. Investigate any intervening changes at these seams before implementation; do not reset to the pinned SHA automatically.

**Focused automated tests.** Exercise the exported consensus/service seams with controlled loader/correlation boundaries: four strong zeros plus finite weak dissent retains provisional zero; one success/four recoverable failures retains history while preserving legacy acceptance; all failures produce unavailable; same-frame jitter preserves the exact current accepted representative; tied qualified groups expose no single provisional candidate; configured-high-confidence rejection retains a review-qualified candidate. Assert categorized decode/scoring failures, selected override/automatic facts, unknown duration, all assessed gates, finite serialization and no retained arrays. Add manual-zero preservation, complete-set cache eligibility, warm-cache absence, atomic replacement/write-failure, malicious-path/symlink, artifact-size maximum and “artifact editing cannot change trim” tests. Verify unchanged FFmpeg argv/selection and unchanged shared-cache keys.

**Runtime/integration/manual proof.** Run the existing FFmpeg alignment integration suite on an available supported runtime to check trace/stream/count accuracy; if unavailable, record this outstanding rather than claiming the mocks prove it. A native GUI change is not claimed by this package. Inject disk-full/permission failure and verify the original audio record survives where an initial write succeeded.

**Documentation.** Update architecture for evidence ownership, CLI contract for the artifact/pre-review stderr and unchanged JSON, audio-alignment guide for accepted/provisional/unavailable terminology, and this package's execution record. Do not claim revised acceptance yet.

**Acceptance criteria.** Every completed/planner-rejected computed attempt has a bounded immutable record and a truthful reason. A manual zero retains a byte-identical original attempt/digest. The candidate is never in the trusted hint or trim inputs. Cache v2 output remains schema-valid and contains no rejected embedded result. Full Python verification passes, and existing automatic outcome fixtures do not change except assertions about added diagnostics.

**Rollback.** Revert the package coherently before dependent packages land; preserve existing diagnostic files as inert generated output. No estimator or cache schema bump is needed. Never “roll back” by copying candidates into the old field or stripping manual authority checks.

**Stop and replan.** Any changed automatic offset/acceptance/cache key, unbounded retained arrays, required new filesystem trust bypass, fatal dependency error swallowed as abstention, or need for a general provenance/cache migration. Ordinary type/test repairs remain local implementation work.

**Execution record (2026-09-14/15, macOS arm64).** Implemented by
`14d82237011da0e2efd518ed6c70e64e732d9a21`
(`feat(alignment): retain audio alignment evidence`). The changed owner seams are the
service evidence model and v5 consensus instrumentation; selected-stream/timeline
projection; categorized recoverable error facts; run-local diagnostic persistence;
typed native-review outcome/provenance; alignment orchestration state and managed run
paths; and the directly governing architecture, CLI-contract and audio guide text.
No VSView metadata/result producer or parser, shared-cache serializer/key owner,
FFmpeg command builder, configuration option or estimator-policy identity changed.

Observed automatic-outcome equivalence was checked by running the existing distributed
consensus, FFmpeg argv and reuse-cache fixture files from an archive of pinned `HEAD`
and then from the candidate; both passed. New exact assertions retain these v5 facts:

- four strong same-frame zero estimates (`0`, `+1`, `-1`, `0` samples; scores
  `0.99/0.98/0.97/0.96`) plus one finite weak cross-frame estimate (`400` samples,
  score `0.40`) remains unapplied with null legacy sample/frame authority,
  `insufficient_consensus`, raw `5`, winning `4`, ratio `0.8`, aggregate score
  `0.975`, minimum winning peak ratio `2.0`; the separate provisional candidate is
  `0` samples / `+0f` with four supporting window IDs.
- one successful `0`-sample estimate plus four categorized recoverable failures keeps
  the v5 accepted result (`applied`, `0` samples, score `0.99`, one valid/consensus
  window, ratio `1.0`, peak ratio `2.0`) while retaining all five window records.
  Five unusable windows produce `unavailable` with null candidate and authority.
- same-frame raw-sample jitter keeps the existing observed lower-median representative;
  tied review-qualified frame groups remain unavailable. Fatal `FFmpegError` still
  propagates instead of becoming an abstention.

Manual zero proof snapshots the rejected attempt before native review and then records
validated source frames `80/80`, final `+0f`, and
`interactive_confirmed_this_run`; the original attempt object, canonical JSON bytes
and digest remain unchanged. The representative final artifact is
`/private/tmp/frame-compare-p1-final.siY9Dw/run/alignment_diagnostics/comparison-1.json`:
10,330 UTF-8 bytes, five windows, schema v1/purpose `diagnostic_only`, digest
`138ddec2e9458509170919d9997f16aa1d6b3ff9d07c8538cbbfb7c6e303523e`, and below the
128 KiB limit. The privacy scan found no generated-root or `/Users/` path, environment
assignment, token/password/private-key marker, or raw command-line field. The
maximum-16-primary-row fixture also serializes below the limit and preserves all rows.
Atomic replacement keeps the last valid snapshot on injected disk-full failure;
symlink containment fails closed. Edited/corrupt artifacts cannot alter trims or cache
reuse. Warm schema-v2 cache reuse retains its accepted value and reports
`historical_details_unavailable` with a null original attempt.

Exact verification commands and outcomes:

```text
uv sync --group dev --frozen                                      PASS (70 packages audited)
uv sync --extra vsview --group dev --frozen                       PASS
uv sync --extra vsview --group dev --group docs --locked          PASS
uv run --no-sync pytest -q tests/services -k alignment            PASS
uv run --no-sync pytest -q tests/orchestration -k alignment       PASS
uv run --no-sync pytest -q tests/cli tests/test_cli_contract_docs.py
                                                                  PASS; JSON stdout unchanged
uv run --no-sync pytest -q tests/vsview tests/services/test_alignment_vsview.py tests/services/test_alignment_workflow_vsview.py
                                                                  PASS; result wire unchanged
uv run --no-sync pytest -q tests/services/test_alignment_ffmpeg.py tests/services/test_alignment_reuse_cache.py tests/services/test_alignment_previous_offsets.py tests/integration/test_alignment_runtime.py tests/integration/test_alignment_audio_seek.py -rs
                                                                  PASS
(cd /tmp/frame-compare-p1-baseline.H0E33j && /Users/tristan/Software/frame-compare/.venv/bin/python -m pytest -q tests/services/test_alignment_distributed.py tests/services/test_alignment_ffmpeg.py tests/services/test_alignment_reuse_cache.py)
                                                                  PASS at pinned HEAD archive
uv run --no-sync pytest -q tests/services/test_alignment_distributed.py tests/services/test_alignment_ffmpeg.py tests/services/test_alignment_reuse_cache.py
                                                                  PASS on candidate
uv run --no-sync pyright --warnings                               PASS; 0 errors/warnings
uv run --no-sync ruff check .                                     PASS
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
                                                                  PASS; 0 medium/high issues
uv run --no-sync pytest -q                                        PASS
uv run --no-sync lint-imports --config importlinter.ini           PASS; 2 contracts kept
uv run --no-sync python scripts/generate_api_docs.py --check      PASS
uv run --no-sync zensical build --clean --strict                  PASS
git diff --check                                                  PASS
ffmpeg -version / ffprobe -version                                9.0.1 / 9.0.1
```

The full suite's recorded skips were host- or opt-in-specific: L-SMASH and libplacebo
runtime tests unavailable on this macOS runtime; live slow.pics/webhook tests disabled;
and Windows/PowerShell process, portable build/update and E2E tests unavailable on
macOS. Installing the locked VSView extra allowed PySide6/VSView static and focused
tests to pass locally. The canonical Docker integration gate was not run because P1
does not change FFmpeg execution or runtime integration contracts; native FFmpeg
alignment integration ran on macOS instead. Visible Windows review and portable
runtime proof remain P2/P6 gates, and the two-runtime real-media oracle remains P3.
No P1 stop condition was reached. Residual P1 risk is limited to those outstanding
host/runtime proofs and the deliberately unobserved FFmpeg/ffprobe version fields in
run artifacts; the independent native command above records the test host versions.

### [~] P2 — Complete terminal and native review UX, metadata v2

**Outcome.** Terminal and VSView show the same service decision and evidence. Accepted zero, provisional zero and absence are visibly distinct. Keeping current never implies confirmation of an unapplied candidate.

**Owner seams / likely files.** Terminal formatter/presentation owner, `services/alignment.py`, `alignment_vsview.py`, `vsview/session_script.py`, `alignment_review_contract.py`, `alignment_review_panel.py`; native package/verifier fixtures where they embed the contract. Preserve `adapter.py`/launcher behavior except any necessary argument plumbing; do not redesign process lifetime or plugin discovery.

**Public behavior.** Implement all copy, marker, details, normal/verbose and whole-set button behavior in §3. Switch metadata to v2 and reject old sessions with regeneration guidance. Result wire schema remains v1. No automatic-result behavior changes and no new CLI/config options.

**Contracts/invariants.** Coordinate generator/parser/panel rollout in one package. Keep the trusted integer/null field semantics and strict whole-set/session/raw-frame validation. A provisional marker does not seed a manual draft. Native DTO validation is shape/trust validation, not acceptance computation. Embedded projection is independent of the optional diagnostic file's existence.

**Dependencies.** P1's retained model, provenance and writer. Metadata version splitting and native verifiers must land together; do not merge a partly migrated producer/consumer pair.

**Focused automated tests.** `tests/vsview/test_alignment_review_contract.py`, `test_alignment_review_panel.py`, session-script tests and package tests: exact v2 keys, version splitting, mixed/old/malformed sessions, zero/null, stale result paths, duplicate/incomplete decisions, bounds, candidate/authority mismatches, finite/size limits, deterministic scripts, inert ordinary sessions. Assert actual Qt labels, accessible text, primary/secondary button readiness, no autofill/implicit visits, out-of-bounds marker omission, keep-current outcomes, manual zero and mixed trusted/provisional/unavailable comparisons. CLI tests cover normal/verbose/quiet/no-color/non-TTY/JSON and the explanation occurring before the mocked launch boundary.

**Runtime/integration/manual proof.** Run native panel construction/round-trip proof on a compatible host and the existing Linux GUI verifier when available. Execute visible native Windows acceptance for all three states and a mixed source set; capture source SHA, bundle/runtime identity and screenshots. Offscreen Qt assertions alone do not satisfy that gate. Verify that closing without saving, a malformed result, and forced-mode failure leave authority unchanged or fail exactly as documented.

**Documentation.** Current CLI contract, architecture native boundary, guide with exact button names and metadata compatibility; update any supported-runtime verifier notes only where the contract fixture changes. Do not add screenshots to the guide until actual Windows captures exist.

**Acceptance criteria.** No normal rejected route reaches VSView without an explanation. No standalone generic “no trusted audio hint” remains in generated Frame Compare sessions. Panel details include all bounded windows and resolved stream facts from fresh attempts. Mixed comparisons retain their own states. All result-validation negative tests pass. Python and required native integration proof are recorded; Windows-visible proof is a release blocker, not a connector-inferred pass.

**Rollback.** Revert generator, metadata parser, panel and verifier fixtures together, leaving result v1 unchanged. Regenerate sessions under the installed version. Keep P1 evidence/artifacts if reverting only presentation. Do not add a v1-to-v2 trust-upgrade shim.

**Stop and replan.** VSView cannot carry the bounded primitive projection through its actual supported metadata transport; the panel would need to import service policy; deterministic script generation is lost; native result safeguards need weakening; or the UI requires a new result action/per-comparison save model to meet the specified behavior.

**Execution record (2026-09-15, macOS arm64).** Implementation is complete at
`1d29ef131d6c307a1efa6f3b3512524ed8fd1d29`
(`feat(vsview): explain audio alignment trust`). The package remains `[~]`, rather
than `[x]`, solely because the required physical-Windows visible acceptance has not
been performed. No P2 stop condition was reached.

The service now presents accepted, provisional and unavailable evidence before the
optional native launch and projects the same immutable attempt into generated session
metadata. Orchestration forwards existing verbose/quiet/JSON context without adding a
flag or successful JSON field. Normal output stays compact; verbose output adds the
bounded stream, timing, threshold, gate, work and per-window facts; quiet suppresses
routine accepted/status evidence but retains actionable rejection; no-color and
non-TTY output remain static plain text; JSON suppresses human blocks and logs bounded
rejection scalars through the existing structured stderr boundary. Cached computed
and manually confirmed history remain separately labeled without invented current
details.

Representative terminal states asserted by the focused service tests are:

```text
Comparison 1 - Audio alignment accepted: +0f.
No relative audio correction is required. Policy: stream-timeline-distributed-2097152-v5; 4/5 correlated windows agree.

Comparison 1 - Audio alignment requires review. Provisional candidate: +0f (not applied).
4/5 correlated windows agree; configured consensus requires 100%.
Reason: insufficient_consensus.

Comparison 1 - No usable audio candidate. No automatic correction applied.
5 windows planned; 0 usable estimates. Reason: no_usable_windows.
```

Every fresh-attempt state also reports the selected `Reference a:N -> Comparison
a:N` stream pair. Provisional launch copy states that the candidate is a hint rather
than a confirmed alignment; unavailable launch copy states that no automatic candidate
exists. Historical representatives are `Reused accepted audio alignment: +7f` and
`Reused manually confirmed alignment: +3f`, with honest detail unavailability.

Metadata and result compatibility are deliberately split. Generated outputs now use
strict metadata v2. Reference metadata retains only version/session/role/name;
comparison metadata adds a deterministic, bounded `frame_compare_audio_review` JSON
string beside the existing trusted integer/null `frame_compare_suggested_offset`.
The projection contains current authority, evidence availability and the current
attempt or explicit absence. The parser validates exact keys, finite/bounded primitive
facts, ordered topology, session identity, stream/window/decision consistency and
candidate/authority agreement. Metadata v1, unknown and mixed Frame Compare sessions
fail with regeneration guidance; there is no migration or trust-upgrade shim. Ordinary
sessions without Frame Compare metadata remain inert. Result schema v1 is byte-shape
compatible and unchanged: only complete ordered `confirmed`/`keep_current` decisions
for the exact session and source topology are accepted, with authoritative raw-frame
bounds and sibling-path containment still enforced.

The native panel's representative states are:

```text
Audio alignment accepted: +0f
No relative audio correction required.
[ACCEPTED AUDIO] +0f - reference/comparison origin marker

Provisional audio candidate: +0f - NOT APPLIED
insufficient_consensus
Verify manually; this candidate is not a confirmed alignment.
[PROVISIONAL - NOT APPLIED] +0f - reference/comparison origin marker

No usable audio candidate
insufficient_signal
Enter known offsets or align the sources manually.
(no marker)
```

The actual Qt copy uses em dashes where shown in §3.5; the ASCII rendering above keeps
the ledger portable. `Confirm these aligned positions`, `Confirm these known offsets`
and `Keep current alignment` are the only whole-set actions. Keep-current writes one
unchanged result-v1 `keep_current` action per comparison. Saved labels separately state
accepted authority retained, provisional candidate not confirmed, no accepted
candidate available, or manually confirmed authority retained. Offscreen tests cover
accepted/provisional/unavailable/manual mixed sets, accepted and provisional `+0f`,
cached history, manual authority with retained rejected history, no field prefill,
no implicit visit/readiness, marker bounds, one ordered save, accessible labels,
scrolling, focus, close-without-save, write failure and ordinary-session inertness.

Exact verification and observed outcomes:

```text
uv sync --group dev --frozen                                      PASS
uv sync --extra vsview --group dev --frozen                       PASS
uv run --no-sync pytest -q tests/services -k alignment            PASS
uv run --no-sync pytest -q tests/vsview                            PASS (offscreen Qt/native contract)
uv run --no-sync pytest -q tests/orchestration -k alignment       PASS
uv run --no-sync pytest -q tests/cli tests/test_cli_contract_docs.py
                                                                  PASS
uv run --no-sync pytest -q tests/windows_portable/test_windows_portable_docs.py tests/workflows/test_docker_gui_contract.py
                                                                  PASS
uv run --no-sync pytest -q tests/integration/test_alignment_runtime.py -rs
                                                                  PASS
uv run --no-sync pytest -q tests/integration -k alignment -rs     PASS; unrelated L-SMASH/GOP cases skipped
bash -n tools/verify_docker_gui.sh                                 PASS
uv run --no-sync pyright --warnings                               PASS; 0 errors/warnings
uv run --no-sync ruff check .                                     PASS
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
                                                                  PASS; 0 medium/high issues
uv run --no-sync pytest -q                                        PASS
uv run --no-sync lint-imports --config importlinter.ini           PASS; 2 contracts kept
uv build + scripts/verify_distribution.py + clean wheel install + version/help
                                                                  PASS; wheel and sdist 0.6.0
uv sync --extra vsview --group dev --group docs --locked          PASS
uv run --no-sync python scripts/generate_api_docs.py --check      PASS
uv run --no-sync zensical build --clean --strict                  PASS
git diff --check                                                  PASS
ffmpeg -version / ffprobe -version                                9.0.1 / 9.0.1
```

The first full-suite run exposed one stale orchestration test double that did not
accept the newly forwarded existing quiet/JSON context; it was repaired and the
focused test plus complete canonical gate then passed. Recorded full-suite skips were
host/opt-in surfaces: local L-SMASH and libplacebo integration, live slow.pics/webhook,
and Windows PowerShell/process/portable/update/install E2E tests. PowerShell was not
available even for a local parser invocation. The Linux X11 GUI verifier was not run
because this host is Darwin and has no compatible Linux X11 desktop; its shell syntax,
fixture contract and generated-session path were tested statically.

**Outstanding physical-Windows handoff.** At candidate
`1d29ef131d6c307a1efa6f3b3512524ed8fd1d29`, build the portable bundle on Windows and
record the bundle/runtime identity. In visible VSView, capture accepted `+0f`,
provisional `+0f`, unavailable and mixed-source-set screenshots; verify marker positions,
expanded details/scrolling, keyboard and tab navigation, focus after save, both manual
input bases, no provisional prefill/playhead/readiness effect, keep-current saved labels,
close-without-save, malformed-result refusal and the actual result-v1 round trip. This
is the remaining P2 release blocker; macOS offscreen proof is not a substitute.

### [ ] P3 — Continuous-decode oracle and predeclared policy evaluation

**Outcome.** Establish whether bounded extraction changes frame decisions or quality eligibility relative to continuous decoding, and whether the fixed P4 policy improves the demonstrated failure without accepting negative controls. This is test/evidence work, not an unbounded production path or a release of new thresholds.

**Owner seams / likely files.** `tests/integration/test_alignment_runtime.py`, a focused adjacent oracle test module/support fixture if needed, `tests/services/test_alignment_distributed.py`, and isolated ignored test evidence. Read the supported runtime matrix; do not update FFmpeg/native versions as part of this package.

**Public behavior.** None. No production flag, new default, alternate estimator execution branch or artifact reader. Candidate display from P1 remains independent of the pending automatic-policy evaluation.

**Experiment definition.** Build deterministic, redistributable synthetic fixtures and supplement them with locally available legally usable real media. Use separate generation seeds for development and holdout controls, declare expected offsets/edit structure before running the target policy, and preserve hashes/commands/settings in the test evidence. Do not relabel a failed fixture after seeing its result.

For each source/rate/channel treatment, decode the selected stream **continuously from its origin**, resampling once, and slice by output sample count. Do not implement the oracle using the same positive-seek/timestamp-trim path being tested. Decode whole **test fixtures only**, each at most 180 seconds, sequentially into temporary storage; use at most one pair plus its comparison workspace at a time and cap retained raw temporary oracle data at 256 MiB per case. Store only scalar findings after cleanup. The production estimator never imports this helper.

Compare bounded windows with oracle slices at: origin; just before/after the five-second seek transition; default early/middle/late positions; and asymmetric reference/comparison origins near search boundaries. Record actual sample counts, independent packet/frame PTS observations, measured sample-grid lag, score, peak ratio, frame bin, runtime version and exact fixture identity. Distinguish a scalar-score change from a frame-bin or acceptance-gate change. Both source arrays must be checked against their own oracle; a same-file self-pair alone can conceal a common bias.

**Required fixture families.** Cover zero and signed nonzero controls; 24 and 24000/1001 FPS; 44.1/48 kHz sources and 4/8/48 kHz requested/analysis paths; PCM/Matroska with 960- and 1001-sample packetization; AAC/priming controls; equivalent remuxes; positive/negative stream/container starts; resampling-sensitive broadband/speech-like signals; explicit A/V-origin differences; short selected audio in longer video; exact silence, very quiet independent noise, steady tones and repeated segments. Include ≥150-second four-to-one cases so support can genuinely be non-overlapping, and move the weak/edited interval through each of the five positions. Include localized edit, insertion/deletion step, drift, unrelated audio, multiple shuffled/commentary/language streams, and explicit matching-stream override.

The weak-dissent fixture must demonstrably return a **finite** nonzero-frame estimate with low quality from the real pipeline; a zero-norm exception is not an acceptable substitute. Freeze/assert its actual window classifications before using it as an acceptance regression. The strong edit must produce credible cross-frame evidence. If the intended construction does not produce those facts, fix the fixture construction rather than loosening expected outcomes.

**Predeclared outcome gates.**

| Observation | Required disposition |
| --- | --- |
| Clean zero/known-delay control has a bounded frame bin different from its continuous oracle away from an exact rounding boundary, or bounded extraction alone changes credible/qualified classification | An extraction/scoring discrepancy is demonstrated. Block P4 rollout on that supported path; follow P5's extraction decision branch. Do not blame the original incident or hide it with filtering. |
| Bounded/oracle raw lags differ only within the existing quantization/refinement allowance and still produce the same expected frame bin and eligibility | Preserve the extraction and correction radius. Record the variance; do not widen the radius merely to make samples identical. |
| Exact/near half-frame cases disagree | Preserve distinct bins and the existing rounding convention; investigate measured grid uncertainty separately. Do not merge bins. No general rational-rounding rewrite is authorized here. |
| Fixed quality/coverage proposal passes every mandatory clean zero/nonzero control and every incident-shaped weak-dissent control, while all wrong-stream, credible-edit, drift, silence/repetition and one-success/four-failure negatives remain unapplied | Approve P4 implementation of that exact proposal. P4 must rerun the same cases through its actual production service. |
| A negative control is automatically accepted under the proposal, or the required weak-dissent positive still fails despite adequate independent support | Do not ship the new acceptance policy and do not tune numeric floors on the holdout set. Keep P1–P2 and record the failing evidence for a new narrowly scoped policy decision. |

For clean lossless controls at the requested rate, require origin-grid agreement within one output sample and the correct integer frame result. For fallback paths, compare measured error against the existing `ceil(requested_rate / analysis_rate)` correction allowance and require the correct frame result; anything outside the allowance is a discrepancy, not an automatic recommendation for a wider allowance. Record waveform/score deltas for lossy controls rather than demanding byte-identical AAC output. Correct frame bins and the predeclared eligibility/negative-control results remain mandatory. Exact half-frame tests explicitly assert the current ties behavior instead of using a broad tolerance.

Evaluate the fixed quality/coverage proposal against captured real estimator evidence using a test-only specification evaluator; it is not production proof until P4 executes the same matrix. Require the negative suite to contain at least four deterministic holdout seeds per stochastic family, every five-window edit/dissent position, both signs, and both FPS values. Record the finite matrix size and measured results; zero false accepts in this matrix is not a population-level error-rate claim.

For additional real-media confidence, document at least a constant-zero pair, a known-constant-nonzero pair, and a mismatched mix/cut/track pair, with visual checks at early, middle and late positions and near any disputed interval. A single visual match is insufficient. If suitable local media or a supported runtime is unavailable, keep that portion outstanding and do not claim it passed.

**Contracts/invariants.** Original trace remains immutable; the oracle is independent of production seeking; no production whole-track decode; no cache reuse during fixture measurement; all temporary processes/files have deterministic cleanup/timeouts. Full source identities stay in local test evidence only.

**Dependencies.** P1 trace/stream evidence; P2 is not necessary to construct oracles, but its candidate UI can aid real-media review. Do not parallelize writes to shared fixture owners without an explicit disjoint boundary.

**Focused automated tests.** Oracle slicing/origin sign/count validation; matching and asymmetric extraction; generated finite weak dissent; strong edit/drift/wrong stream negatives; all duration/support boundaries; packetization/resampling; score-stage attribution; resource bounds and cleanup. Existing real FFmpeg integrations must actually run, not skip.

**Runtime/integration/manual proof.** Run on the pinned-supported Docker/Linux FFmpeg and native Windows portable FFmpeg, recording both executable version lines and runtime fingerprints. Use the canonical Docker verifier in addition to the focused alignment tests. Windows comparison results and real-media checks remain separately required. Missing codecs/runtime are explicit blocked cells, not silently dropped dimensions.

**Documentation.** Add an execution-results subsection here with fixtures, hashes, version identities, pass/fail tables, maximum observed grid variance and the exact P4 go/no-go. Change current behavior docs only if correcting a false statement, not to describe the proposal as deployed.

**Acceptance criteria.** A reproducible scalar evidence bundle supports every matrix cell, including holdouts; the P4 gate has a definite pass or stop result; primary clean signed controls match expected frame relationships; no original-incident causation is asserted.

**Rollback.** Remove an invalid fixture/helper or revert test-only work without changing production or caches. Preserve failing scalar evidence when revising a fixture. Do not delete contradictory results just because a positive suite passes.

**Stop and replan.** Oracle shares the suspected extraction path, fixture labels cannot be established independently, a supported runtime behaves differently in a trust-relevant way, or the fixed proposal fails a predeclared gate. Additional arbitrary parameter sweeps are outside this package.

### [ ] P4 — Quality-qualified voting, temporal quorum and contradiction veto

**Outcome.** Close both demonstrated voting pathologies under a deliberate estimator version: weak estimates abstain, failed windows cannot leave a long source trusted by one survivor, and credible edits remain unapplied.

**Owner seams / likely files.** `alignment_consensus.py`, `alignment_audio.py` for default short/medium planning and budget-compatible counts, `alignment_correlation.py` for the policy identity, relevant service/config DTO documentation and cache identity tests. Preserve config schema fields and valid ranges; do not add switches or change the default ratio.

**Public behavior.** Implement §5.4–5.5, the policy notice and semantic migration in §6.3. More conservative acceptance is expected for thin coverage and weak-only evidence; qualified unanimous distributed support can now pass despite weak abstentions. Medium-duration default planning changes as specified. Warm old-policy shared results miss, including human-confirmed entries under the current key design.

**Contracts/invariants.** Use base-credible windows for the contradiction veto and configured-qualified windows for votes/support. Never lower explicit user thresholds, minimum or ratio. Retain every abstention in diagnostics. Independent interval selection uses actual useful support and is deterministic. Default ratio remains 1.0, zero voters are not unanimous, and no retry/oracle artifact contributes authority. Stable classifications remain diagnostic-only.

**Dependencies.** P1; P3 passing oracle/policy gate on the supported paths; P2 before public release. Any demonstrated primary extraction discrepancy must first be resolved through P5's bounded extraction branch or this package stays blocked. No policy bump is required merely to prototype the evaluator in tests, but it is mandatory before production acceptance changes.

**Focused automated tests.** Four strong `+0f` windows plus one finite weak cross-frame dissent accepts only with adequate independent support; repeat with the weak interval at all five positions. Four strong zeros plus a credible shifted edit stays provisional even for configured ratio 0.8. A stricter configured threshold that excludes the dissent from voting must not remove a base-credible contradiction. One success/four failures remains provisional on long sources; all unusable is unavailable; same-frame jitter accepts without modifying raw samples. Test ties, all failed gates, explicit minimum five, configured threshold 0.995, explicit ambiguity above the floor, budgets, short/medium/long boundaries around 30/90 seconds, overlapping custom windows, and two independent short-source intervals. Verify both cache origins miss on the new policy and unchanged schema v2 serialization.

**Runtime/integration/manual proof.** Rerun the P3 labeled matrix through the actual updated `align_clips_from_request` path without cache. Require the same zero-false-accept negative result and all mandatory positives. Run full Python and Docker gates, supported Windows FFmpeg tests and real-media checks. Compare primary extraction counts/total FFT/scoring budgets with the recorded baseline; no unbounded extra search is permitted.

**Documentation.** Same-pass CLI/config semantics, guide examples, architecture policy ownership/default duration behavior, release notes and estimator migration warning. Describe both the improvement and intentional thin-evidence conservatism. Record the actual policy token in this plan.

**Acceptance criteria.** All specified primary/negative controls have their intended state; candidate preservation and manual-zero provenance still pass. Actual configured values and denominator are visible. No old-policy cache entry bypasses the new safeguards. Required runtime cells are executed, not skipped, and caps are enforced at all supported requested rates.

**Rollback.** Revert the policy/planning change as a unit while retaining P1–P2 observability. Assign a **new** estimator identity for a behavioral rollback so results from the withdrawn policy cannot be reused under the restored code. Leave schema v2 intact; do not rewrite reusable cache records. Clearly state that the legacy one-survivor acceptance limitation returns if the old acceptance policy is restored.

**Stop and replan.** Any credible edit/wrong-stream negative is accepted, the holdout improvement requires lowered thresholds or weighted voting, configuration meaning cannot be disclosed, coverage depends on fabricated decoded origins, or primary work budgets must increase. Do not mask these failures with retry-to-majority logic.

### [ ] P5 — Evidence-gated extraction repair and bounded local diagnostics

**Outcome.** Repair a specifically demonstrated extraction-grid defect at its smallest owner, if one exists. Add only those short diagnostic rechecks that the experiments show provide useful explanations. Do not use local rechecks to promote a rejected constant offset.

**Owner seams / likely files.** `alignment_audio.py`, `alignment_correlation.py`, `alignment_consensus.py`, diagnostic serializers/adapters and the focused runtime/oracle tests. No CLI/config flags and no general retry scheduler.

**Dependencies.** P1–P3. The extraction-repair subpart precedes P4 rollout when P3 found a trust-relevant primary-path discrepancy. Diagnostic-only rechecks can follow P4 and are not required to ship P1–P2. Record `deferred — no demonstrated benefit` rather than installing dormant retry branches if the gate below fails.

**Production extraction decision tree.** Execute this ordered experiment, not a collection of unresolved implementation alternatives:

1. If P3 found no trust-relevant discrepancy, retain current seeking, resampling and refinement exactly. Do not increase preroll “for safety.”
2. If P3 reproduced a discrepancy, repeat the same controlled cases with a fixed ten-second preroll, keeping all other operations unchanged. If this alone eliminates every reproduced discrepancy on both supported runtimes and introduces none in holdouts, adopt that smallest bounded repair. Keep FFT/output/scoring caps and timeouts unchanged; document the new maximum preroll/decode-work estimate and bump estimator identity.
3. If ten seconds does not fix the discrepancy, do not ship it. Test one bounded grid-preserving extraction design that keeps decoded preroll through resampling and crops against an independently observed/validated output-sample origin. Adopt it only if origin/count/frame and negative-control gates all pass with the same bounded resource contracts. Do not label requested positions as measured origins to make the test pass.
4. If neither bounded design satisfies the oracle gates, retain the existing production path and block claims/new acceptance rollout on the affected supported path. Record the failing codec/runtime/timing cases and stop for a focused extraction design. No whole-track fallback, container-start correction, or larger unconstrained refinement radius is authorized.

The third step permits local implementation judgment about the exact filter/PTS plumbing; its origin semantics, boundedness, experiment and acceptance are fixed. Audio-to-video frame-zero mapping changes, alternative correlation/preprocessing defaults, adaptive stream/channel search, exact-rational rounding conversion and widened requested-rate correction radii are **not** bundled into this repair. They need their own demonstrated failure and decision/proof, even when the oracle has exposed a nearby problem.

**Disputed-window recheck decision.** Implement one diagnostic recheck only if P3 demonstrates a recoverable window failure or seek/grid-related discrepancy for which a bounded re-extraction supplies additional, reproducible evidence. The runtime experiment must distinguish the new facts from merely returning the majority's desired answer. If there is no demonstrated benefit, do not implement this production branch.

For an already provisional primary result, choose the earliest credible nonwinning interval; otherwise the earliest failed interval; otherwise the earliest weak/ambiguous interval. Break ties by logical ID. Recheck the central **two seconds** of that interval, clipped deterministically to its actual selected-stream bounds. Retain the parent ID and both original and recheck facts. Use the P3-validated bounded extraction recipe; do not vary recipes repeatedly until one agrees. A successful short subsection is not a replacement for the original full interval.

**Explicit zero-frame diagnostic decision.** Implement only for an existing provisional `+0f` candidate, and only after P3's silence/repetition/nonzero negative controls prove the diagnostic distinguishes useful zero-bin support from lack of signal. Use the same disputed interval selection; if none exists, use the earliest primary interval supporting the candidate. Analyze one central two-second subsection. Compare the best zero-**frame-bin** hypothesis with the strongest nonzero-bin alternative under the existing bounded search range, then score those at the requested rate. Do not constrain the search to zero and announce success because no alternative was evaluated. Exact sample zero is not the hypothesis; use the existing sample-to-frame mapping, including its boundary convention.

Local outcomes are `zero_supported_locally`, `alternative_supported_locally`, or `inconclusive`. Zero is locally supported only when its requested-rate score passes the effective configured/base quality threshold and its peak dominance over the nonzero alternative passes the effective peak threshold with meaningful signal/overlap. An alternative meeting those conditions wins locally; other cases are inconclusive. Show `Local zero-frame check supports +0f; automatic alignment is still not accepted.` rather than “zero verified.” These outcomes never change the primary audio decision or application authority.

**Fixed auxiliary budget.** After the primary trace fixes eligibility and target intervals, construct and reserve one deterministic auxiliary plan before any auxiliary IO. Examine at most the two eligible operations in order (disputed recheck, then zero check); include an operation only when its complete worst-case cost fits the remaining primary-plus-auxiliary caps, otherwise record `auxiliary_budget_unavailable` for that operation. Do not spend failed/skipped decoding's unused allowance opportunistically: charge the reserved primary work. The zero check may fit when a recheck was ineligible; neither operation retries admission after seeing the other's result. Do not remove/shorten primary windows, widen offset search, change configured sample rates, or exceed existing caps:

- At most **two auxiliary analysis checks** per pair: one disputed recheck and one zero check.
- Each uses at most **two seconds** of reference content plus the existing comparison search margin.
- At most **three extra requested-rate scoring pairs**: one for the recheck and two for zero-versus-alternative.
- All primary and auxiliary FFT work shares the **16,777,216-point total** and **2,097,152-point peak** caps. Reuse a bounded correlation workspace for the zero/nonzero-bin peak comparison; count every actual correlation invocation, not just the eventual candidate.
- At most **16 analysis-check invocations in total**. A primary plan using all 16 gets no auxiliaries. Retries are not free slots.
- All separately decoded scoring pairs share the existing **15,000,000-sample total** and **3,000,000-sample per-pair** caps. Existing primary accounting remains intact; new auxiliary scoring is always charged.
- Retain finite per-process timeouts, sequential extraction, one decoded pair/workspace at a time and deterministic release on failure. No retry of a retry.

At the demanding default fallback/scoring case of five 30-second pairs at 48 kHz:

```text
primary scoring = 5 × 2 streams × 30 s × 48,000 samples/s = 14,400,000 samples
auxiliary scoring = 3 pairs × 2 streams × 2 s × 48,000 samples/s = 576,000 samples
combined = 14,976,000 samples < 15,000,000 samples
headroom = 24,000 samples
```

That calculation covers nominal scoring samples, not the separately charged search/FFT work, and is not permission to ignore rounded endpoints. Reserve exact integer counts, overlap rounding and required padding; if they exhaust the headroom or FFT/check capacity, omit that complete auxiliary operation under the admission rule above. Never shrink primary evidence to make a diagnostic fit. Priority is disputed recheck, then zero check. The total number and duration of operations remain determined by the reserved primary plan and frozen trace, not wall-clock opportunity.

**Public behavior.** Details/verbose output may contain the local recheck and zero-test outcomes; normal output remains the primary decision with at most one short relevant note. A credible primary contradiction still forces review even when a child recheck favors zero. A changed extraction recipe is a documented estimator change and invalidates affected shared identities; pure diagnostic checks do not.

**Contracts/invariants.** Primary decision/support are frozen before auxiliary checks. Construct the complete immutable audio attempt once primary and admitted auxiliary work settles, then snapshot it before manual review; do not mutate a frozen attempt or its digest later. Neither child may add a vote, meet an independent-support minimum, erase a failed/disputed parent, alter the selected stream, or make a candidate newly authoritative. Retain both local hypothesis scores/rates in a bounded child record for the zero check. Rechecks never run to invent a zero when no candidate exists. New fatal subprocess failures retain typed external-boundary behavior; they are not converted into successful verification or a vote.

**Focused automated tests.** Deterministic target selection; zero-bin boundaries and a stronger nonzero alternative; silence/repetition inconclusive; 14,976,000-sample planning arithmetic with rounding headroom; max-rate/custom-budget/max-16-window skips; no shortened primary plan; no extra vote; contradictory parent survives favorable child; recheck failure cleanup and abort semantics; evidence/DTO byte bounds; identical inputs yield identical auxiliary plan. Verify no estimator bump for truly diagnostic-only checks, and a mandatory new token for an actual extraction repair.

**Runtime/integration/manual proof.** Execute before/after P3 oracle cases on both supported FFmpeg runtimes; demonstrate each shipped auxiliary branch's concrete benefit, correct local labels, unchanged primary trust, bounded commands and peak lifetimes. Run Docker/full Python gates and native Windows review of a child result. Record real decode work and latency; excessive latency without diagnostic value is a no-ship outcome, not justification for more switches.

**Documentation.** CLI/architecture/guide budget and diagnostic-only explanation; record the selected extraction branch or explicit no-change outcome, actual policy identities and measured results here. No claim of global zero confirmation.

**Acceptance criteria.** A shipped extraction repair eliminates the reproduced discrepancy without breaking holdouts or resource caps. Every shipped diagnostic branch adds demonstrable truthful local information while leaving automatic authority identical. Unjustified branches are absent, not hidden behind unused config.

**Rollback.** Remove diagnostic-only branches without invalidating accepted caches. For extraction behavior rollback, issue a new estimator identity and rerun oracle/negative controls. Keep original evidence and report the withdrawn recipe. Never substitute a favorable child for the frozen primary record.

**Stop and replan.** A repair requires unbounded prefix decode, measured origins cannot be established, runtime results disagree, a recheck changes automatic trust, zero verification avoids evaluating alternatives, the fixed budget does not fit the proposed operation, or added latency is not justified by observable diagnostic benefit.

### [ ] P6 — Cross-boundary acceptance, migration rehearsal and release handoff

**Outcome.** Prove the integrated trust/persistence/UI behavior on the actual release candidate and clearly distinguish delivered observability from any estimator work still blocked.

**Owner seams / likely files.** Tests and active authority docs across the preceding owners; native verification fixtures; this plan and release notes. No unrelated cleanup or new release machinery.

**Public behavior.** No additional product features. Publish the final documented state, cache miss expectations, session regeneration requirement, diagnostic privacy/retention and accepted/provisional/unavailable terminology.

**Contracts/invariants.** Revalidate end-to-end authority flow after integration: raw attempt → snapshot/terminal → metadata v2 → manual/keep-current result v1 → final result/provenance → cache v2 → trim calculation. No stage may substitute a candidate into authority. Verify every warning and preserved attempt after manual zero and after mixed-set keep-current.

**Dependencies.** P1–P2 for an observability-only release; P3–P4 and any required P5 extraction repair for a release claiming estimator robustness. Optional P5 diagnostic branches must either pass their gate or be explicitly recorded as not implemented. Do not mark an unexecuted package complete to close the plan.

**Focused automated tests.** Whole-service multi-comparison scenario containing accepted `+0f`, provisional `+0f`, unavailable, and a nonzero trusted/manual value. Test no-save, keep-current, manual confirmation, malformed result and artifact write failure; final trimming must use only authorized values and the normal shared-source-set normalization. Rehearse old cache/schema handling, both cache origins across a policy bump, old sessions, and existing run-local override precedence. Parse JSON stdout independently of all stderr messages.

**Runtime/integration/manual proof.** Run all §8 mandatory gates against the integrated candidate. Physical Windows evidence includes visible text, marker positions, keyboard/tab navigation, focus after saving, scrolling/detailed evidence, no accidental candidate prefill, all input bases, mixed comparisons, close-without-save, and invalid-result refusal. Record the exact tested source/bundle SHA. Hosted/offscreen proof is not a visible desktop pass.

**Documentation.** Finish same-pass authority updates, add only genuine current screenshots, complete the execution/proof ledger and release notes. When the agreed workstream is complete, mark the tracked plan historical under the runbook. If estimator work remains blocked after a P1–P2 release, keep the workstream active and state the outstanding gate.

**Acceptance criteria.** All required gates have inspected output at the candidate SHA; every skipped/unsupported cell is identified; no release-blocking Windows, runtime, trust or persistence proof is outstanding for the claimed scope. The release description does not claim the original incident was reproduced or fixed by a known cause.

**Rollback.** Use the coherent rollback boundary of the package being withdrawn. Preserve inert diagnostics, never reuse old session files as migration, and invalidate withdrawn acceptance behavior with a fresh policy identity. No force reset or automatic deletion of user media/generated history.

**Stop and replan.** A final path promotes an untrusted candidate, current docs contradict code, cache/session migration bypasses validation, release packaging excludes tested changes, or physical Windows acceptance exposes unusable/misleading review behavior.

## 8. Verification matrix and canonical commands

All rows are **pending** at plan delivery. Prior report probes and this source inspection are not new execution results. Tests should target exported behavior and boundary effects, using typed/local fixtures; avoid reproducing implementation branches in mocks. [R13]

### 8.1 Required proof surfaces

| Surface | Expected proof / final disposition | Packages | Environment |
| --- | --- | --- | --- |
| Four strong zero windows + finite weak cross-frame dissent | P1 retains provisional zero under v5; P4 accepts only qualified support with independent coverage. A finite weak estimate is mandatory, not an injected silence exception | P1, P3, P4 | Unit + real FFmpeg on Linux/Windows |
| Four strong zeros + strong localized shifted edit | Candidate remains visible but automatic result stays unapplied, including ratio 0.8 and a raised user threshold that excludes the dissent from voting | P1, P3, P4 | Unit + real negative fixture |
| One success + four recoverable extraction failures | P1 records all failures and preserves legacy outcome; P4 rejects long-source trust and retains a provisional candidate if qualified | P1, P4 | Unit + service integration |
| All windows unusable | Unavailable; no zero candidate/marker/authority; cause counts survive | P1, P2, P4 | Unit + silent/invalid-signal FFmpeg fixture |
| Same-frame raw-sample jitter | Same integer bin, observed median, raw values unchanged | P1, P4 | Unit + packetized real fixture |
| Stream mismatch / explicit override | Actual selected ordinals, metadata rationale and unknown/mismatch facts retained; matching override changes analyzed stream, not labels alone | P1, P3, P4 | Unit + multi-track FFmpeg |
| Selected duration missing | Preanalysis unavailable, zero work, exact stream/reason retained, no container fallback | P1, P2 | Planner/service/UI |
| Early/late/asymmetric bounded extraction vs full oracle | Independent output-grid/count/frame/quality comparison; supported-runtime agreement or blocked policy rollout | P3, P5 | Local FFmpeg + Docker/runtime + Windows FFmpeg |
| Packetization/resampling/priming | 960/1001-sample PCM packets; 44.1/48 kHz; direct/fallback; AAC; both FPS values and offset signs | P3–P5 | Real supported runtimes |
| Short media / overlapping windows | Full-window short policy; two medium independent intervals; long three-interval rule; custom shapes cannot inflate support | P3, P4 | Unit + short/medium FFmpeg |
| Accepted +0f / provisional +0f / no candidate | Distinct typed states, exact copy and markers, no truthiness collapse, no implicit confirmation | P1, P2 | Unit + offscreen + visible Windows |
| Manual zero after rejection | Original attempt/digest preserved; final authority manual; rejected computed result not written as reusable computed evidence | P1, P2, P6 | Service/persistence + native UI |
| Warm cache without rich history | Honest historical absence; no fabricated stream choice/counts; no fresh analysis solely for display | P1, P2, P6 | Cache/service/UI |
| Multi-comparison mixed states | One ordered whole-set action; per-pair authority and saved labels; unresolved pairs do not authorize source-set trims | P2, P6 | Service + native Windows |
| Normal/verbose/quiet/no-color/non-TTY/JSON | Prelaunch explanation, bounded verbose table, no blocking non-TTY read, no ANSI/markup injection, JSON-only stdout and unchanged public shape | P1, P2, P4, P6 | CLI tests, redirected console smoke |
| Metadata versions / old sessions | v2 accepted; v1/unknown/mixed/malformed rejected; ordinary sessions inert; result v1 still strictly session/bounds/topology validated | P2, P6 | Contract + native package round-trip |
| Diagnostic artifact safety | Bounded bytes, atomic last-valid snapshot, privacy/path/symlink/IO failures, never cache/trim authority | P1, P6 | Unit/filesystem, Windows path tests |
| Retry / zero diagnostic | Fixed budget and target, parent preserved, no vote or authority, local zero compared with alternative | P5 | Unit + supported FFmpeg + native details |
| Native Windows visible acceptance | Accurate text/markers/focus/buttons, actual result round-trip, mixed-set behavior and manual provenance at candidate SHA | P2, P6 | **Physical Windows desktop** |

### 8.2 Command canon

Bootstrap exactly as the runbook specifies:

```bash
uv sync --group dev --frozen
```

Focused selections (adjust a selection only after inspecting the actual local test layout; do not silently replace real integrations with mocks):

```bash
uv run --no-sync pytest -q tests/services -k alignment
uv run --no-sync pytest -q tests/vsview
uv run --no-sync pytest -q tests/orchestration -k alignment
uv run --no-sync pytest -q tests/cli tests/test_cli_contract_docs.py
uv run --no-sync pytest -q tests/integration/test_alignment_runtime.py -rs
# Include the new oracle module once P3 creates it; this selection also reports skips.
uv run --no-sync pytest -q tests/integration -k alignment -rs
```

Full Verification, required for product behavior/authority changes in these service/UI/CLI seams:

```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
```

Record the exact real tools used by the oracle:

```bash
ffmpeg -version
ffprobe -version
```

Canonical Docker/runtime gate, required for changed FFmpeg execution or real runtime integration contracts:

```bash
bash tools/verify_docker_integration.sh
```

This gate does not prove VSView. A compatible Linux X11 host can additionally execute:

```bash
bash tools/verify_docker_gui.sh
```

That is separate host-dependent GUI/offscreen proof; it does not replace visible Windows acceptance. Do not claim native macOS Docker GUI support or widen X11 access to make a check pass.

Windows portable build/validation route:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/validate_update_public_key.ps1 -PublicKeyPath tools/windows_portable/update_public_key.xml
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir dist/frame-compare-portable-win-x64 -CacheDir .portable_cache
dist/frame-compare-portable-win-x64/frame-compare.ps1 doctor --json
```

Use an isolated generated fixture config with `audio_alignment.use_vsview = true` for optional review and the existing `--force-interactive-alignment` route for forced validation. Generate sessions through Frame Compare, not a hand-authored script that bypasses its expected source set. Run the visible scenarios in §8.1 and save evidence outside tracked product outputs unless intentionally added to documentation.

**Packaging caveat:** the pinned Windows builder packages application source and wheel metadata from committed `HEAD`, excluding uncommitted application changes. Record the packaged SHA and relevant worktree differences. A successful old-HEAD bundle does not verify an uncommitted candidate. Candidate commits/build dispatches require implementation/release authorization; this planning task does not grant it. Hosted matching-SHA packaging/offscreen success still leaves the physical Windows UI pass outstanding. [R13]

If P2 changes package inclusion or installed entry-point behavior, also run the runbook's Python distribution verification or observe the matching-SHA `package` job; existing entry-point tests are not a substitute. No native dependency or signing/updater change is planned, so do not expand this task into a media-runtime refresh.

Documentation/structural checks:

```bash
git diff --check
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync pytest -q tests/test_cli_contract_docs.py
```

Regenerate `docs/api.md` with the canonical generator if tracked API output changes. For a strict documentation-site build, use the runbook environment transition:

```bash
uv sync --only-group docs --locked
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
# Restore both environments before subsequent Python gates.
uv sync --group dev --group docs --locked
```

No test command, successful exit, or CI check may be reported as proving a cell that skipped or did not exercise its actual boundary. Reuse still-current observed proof; rerun affected checks when code, fixtures or runtime identity changes.

## 9. Migration and rollout strategy

**Stage A — diagnostic release (P1–P2).** Keep v5 automatic behavior and shared schema v2. Introduce diagnostic schema v1, metadata v2/result v1, original-attempt preservation and exact UI language. Old cache entries remain eligible under current identity; their detailed history is unavailable. Regenerate VSView sessions after upgrading. This release fixes diagnostic loss and manual-review ambiguity, not the acceptance policy's one-survivor safety limitation.

**Stage B — measured policy release (P3–P4).** Require the oracle and negative-control gate, fix any reproduced primary extraction defect first, then ship quality-qualified voting/coverage under a new estimator token. Keep the default ratio 1.0 and publish its new denominator/minimum-window semantics prominently. Expect fresh computation/review because the current cache key invalidates both old computed and human-confirmed shared entries. Preserve accepted-cache schema v2; no migration/backfill.

**Stage C — justified local diagnostics (P5).** Ship a recheck/zero diagnostic only when the fixed gate demonstrates benefit and its primary-decision invariance is proven. Otherwise record it as not implemented; no placeholder flags, unused types or hidden runtime switches. A standalone extraction repair must use its own changed policy identity and cannot be smuggled into a supposedly diagnostic-only rollout.

**Acceptance rehearsal (P6).** Start with a warm v2 cache lacking detailed history; open a fresh metadata-v2 session containing mixed states; manually confirm a rejected zero; reopen the resulting run diagnostic; verify its original attempt/digest; validate the final cache contains only eligible authority; then repeat under the new estimator token to prove misses for both old origins. Exercise rollback without deleting old artifacts or accepting stale session files.

Before local implementation, compare the working branch with the pinned source at the changed seams. Preserve unrelated work and record any rebase/integration differences. Only one active plan should govern this workstream; consolidate any overlapping active plan under the runbook rather than creating competing authorities.

## 10. Risks, rollback notes and explicit release blockers

| Risk | Mitigation / blocking condition |
| --- | --- |
| Candidate accidentally enters trusted-offset field or normalized trims | End-to-end authority tests are mandatory. Any occurrence blocks every rollout, including diagnostic-only releases. |
| Fixed quality floors reject useful legitimate mixes | Floors are a conservative proposal with required positives/holdouts; failed gate keeps P1–P2 only. Do not tune on the holdout set or claim score calibration. |
| Filtering hides a real edit | Base-credible contradiction veto, independent coverage and per-window trace. A raised configured threshold cannot hide a credible dissent. Any negative false acceptance blocks P4. |
| Five rows mistaken for independent observations | Non-overlap and first/last-third support checks; medium-source planning; custom-window failures remain explicit. |
| Bounded extraction has runtime-dependent sample origins | Independent continuous oracle on both supported runtimes; no assumed-as-measured timestamps or blind offset correction. A trust-relevant discrepancy blocks new acceptance on that supported path. |
| Manual confirmation launders an audio rejection into computed provenance | Immutable original attempt plus separate human outcome; accepted-only cache serialization. Manual zero regression is release-blocking. |
| Cached authority shown as fresh analysis | Historical availability state and separate manual/computed provenance; never fabricate windows or selected streams. |
| Audit files leak media paths or become a cache | Pathless bounded schema, documented sharing/retention, no engine read path, adversarial artifact tests. |
| Metadata/result version coupling or stale-session acceptance | Separate versions, coordinated producer/consumer rollout, explicit regeneration and unchanged result session/frame checks. |
| Auxiliary probes hide contradictions or consume unbounded work | At most two short checks/three scoring pairs within fixed caps; primary decision frozen; no retry loop or vote. |
| UI passes offscreen but is confusing on Windows | Visible physical-host acceptance with captures, keyboard and mixed-state checks. Connector/source review cannot clear this blocker. |
| Rollback reuses withdrawn-policy cache entries | New estimator identity for behavioral rollback; no in-place migration or re-adoption of an old token. |

**Release blockers for Stage A:** provisional-to-authority leakage; missing prelaunch explanation; manual attempt loss; JSON stdout drift; uncontained/unsafe writes; misleading historical claims; mixed-state/result-validation failures; metadata producer/consumer mismatch; required full/native tests not executed; visible Windows review not accepted.

**Additional Stage B blockers:** any mandatory oracle/policy control failure, any strong-edit/wrong-stream/drift false acceptance, one-survivor long-source acceptance, changed policy without cache invalidation, concealed config semantic change, or exceeded primary budgets. Stage A may still ship as diagnostic-only with those Stage B blockers explicitly open.

**Additional P5 blockers:** no demonstrated diagnostic benefit, a child alters authority/support, zero testing omits alternatives, fixed auxiliary reservation cannot cover actual work, or an extraction change lacks two-runtime oracle proof. Do not add a configuration switch to route around a failed gate.

No rollback may authorize untrusted offsets, weaken session validation, remove containment, default null to zero, restore whole-track production decoding, or delete user media. Retained diagnostic files are safe to leave behind because they are never authority.

## 11. First executable implementation handoff

**Execute P1 only after implementation is authorized.** Start from the named branch and compare its relevant owners to `326da610a1f6d9baee7ea58d509f05f59af0f004`; preserve local work. Read `AGENTS.md`, the runbook's planning/full-verification/persistence sections, current architecture/CLI sections, and the execution-plan, persistence, CLI, runtime, architecture and test-design skills. This plan settles product behavior; helper names, local test organization and routine source discovery remain implementation judgment.

The first slice is:

1. Add the minimal immutable attempt/decision/leaf contracts and tests proving that provisional `+0f` cannot be an applied offset.
2. Capture selected-stream facts and one bounded record per planned interval, including failure categories/counts, without changing FFmpeg argv or the current v5 acceptance gates.
3. Derive a rejected review candidate separately using the fixed display floor and unique-group rule; preserve raw estimates and legacy automatic results.
4. Carry the original attempt through `AlignmentResult`, current-run provenance, validated manual replacement and immutable orchestration state. Keep cache `computed_result` accepted-only.
5. Add the contained atomic diagnostic writer, pre-review snapshot, final human-outcome update and basic prelaunch explanation. Keep JSON stdout and shared schema/policy unchanged.
6. Run focused service/persistence/CLI regressions, then the full canonical Python gate and available relevant FFmpeg integration proof. Inspect the diff and artifact schema/size. Record any missing runtime proof honestly.

**P1 handback must include:** changed owner seams; observed before/after automatic-outcome equivalence; the four-strong/one-weak provisional-zero example; the manual-zero preserved-attempt example and digest; a warm-cache historical-absence example; actual diagnostic file location/size/privacy check; stdout/stderr assertions; exact tests executed/skipped; and unresolved native/runtime gates. Do not proceed to quality filtering, a ratio change, metadata v2, unbounded probes or extraction redesign while completing this first package.

**Completion ledger — populate during authorized implementation:**

| Package | Status | Candidate SHA / proof references | Outstanding blockers |
| --- | --- | --- | --- |
| P1 — evidence and persistence | Complete | `14d82237011da0e2efd518ed6c70e64e732d9a21`; execution record above | None; later-package native/oracle gates remain scoped to P2/P3/P6 |
| P2 — terminal/native UX | Implementation complete; native acceptance outstanding | `1d29ef131d6c307a1efa6f3b3512524ed8fd1d29`; execution record above | Physical-Windows visible VSView and portable bundle proof |
| P3 — oracle and policy gate | Not started | None | Supported runtime matrix and controls |
| P4 — acceptance policy | Blocked on P3 | None | Exact policy go/no-go |
| P5 — extraction/local checks | Evidence-gated | None | Demonstrated discrepancy/benefit only |
| P6 — integrated release proof | Not started | None | Scope-appropriate gates above |

## Source and authority record

Repository references below are pinned to the starting SHA. They establish the existing behavior and ownership, not successful execution of this plan. Numeric display/quality/coverage floors, duration tiers, artifact byte bounds and auxiliary reservations are **new design decisions in this plan**, subject to the explicit gates above where they affect automatic acceptance.

**R1 — Supplied investigation:** “Frame Compare audio-alignment false negatives and diagnostic UX,” supplied as `frame-compare-audio-alignment-investigation.md` (mounted upload name included `(1)`). The uploaded bytes have SHA-256 `16fcd933880be679946b931d9112139d07c3c671a2b732a129e7e9a2cf428838`. The report's isolated execution and commit analysis are prior evidence, not tests rerun here.

- **R2:** [Pinned consensus owner](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/src/frame_compare/services/alignment_consensus.py): all-successful voting, winner-level gates, skip behavior and evidence loss.
- **R3:** [Pinned alignment service](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/src/frame_compare/services/alignment.py): result projection, trusted-offset map, manual replacement and provenance sequencing.
- **R4:** [Pinned service types](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/src/frame_compare/services/types.py): existing result/provenance/config/stability contracts; [orchestration alignment phase](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/src/frame_compare/orchestration/phase_alignment.py): applied-result invariant, final warnings and trim inputs.
- **R5:** [Current CLI contract, audio alignment](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/docs/current-cli-contract.md#L1359-L1500): public defaults, exact sign convention, cache policy and fixed budgets.
- **R6:** [Pinned audio IO/selection owner](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/src/frame_compare/services/alignment_audio.py): typed timing, stream rankings, default planning and extraction facts.
- **R7:** [Pinned planner/extractor implementation](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/src/frame_compare/services/alignment_audio.py#L534-L840): budget accounting and early/late paths.
- **R8:** [Native review contract](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/src/frame_compare/vsview/alignment_review_contract.py): metadata/result v1 constants, exact topology, trusted paths and typed results.
- **R9:** [Native review panel](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/src/frame_compare/vsview/alignment_review_panel.py): draft readiness, marker behavior, manual inputs and whole-set keep/save actions.
- **R10:** [Shared alignment reuse cache](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/src/frame_compare/services/alignment_reuse_cache.py): schema v2, source-set identity and estimator token participation.
- **R11:** [Audio-alignment guide](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/docs/guides/audio-alignment.md): cache/manual versions, native workflow and visual verification limits.
- **R12:** [Current architecture](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/docs/current-architecture.md#L334-L470) and [import layers](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/importlinter.ini): managed paths, immutable alignment state, service/native boundaries and allowed direction.
- **R13:** [Engineering runbook](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/docs/ENGINEERING_RUNBOOK.md), [AGENTS.md](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/AGENTS.md), and [repo-local skills](https://github.com/TJZine/frame-compare/tree/326da610a1f6d9baee7ea58d509f05f59af0f004/.agents/skills): command canon, risk/verification, active-plan policy and simplicity/boundary guidance. Read for this plan: `execution-plan-authoring`, `persistence-boundaries`, `cli-contract-boundaries`, `runtime-integration-boundaries`, `architecture-boundaries`, `python-test-design`.
- **R14:** [Runtime alignment tests](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/tests/integration/test_alignment_runtime.py) and [native-review tests](https://github.com/TJZine/frame-compare/tree/326da610a1f6d9baee7ea58d509f05f59af0f004/tests/vsview): existing fixture/boundary test locations. Further exact test discovery belongs to implementation.
- **R15:** [Current CLI stream/mode contract](https://github.com/TJZine/frame-compare/blob/326da610a1f6d9baee7ea58d509f05f59af0f004/docs/current-cli-contract.md#L355-L505): JSON/VSView incompatibility, structured stderr versus human output, quiet success behavior and ASCII non-TTY presentation.
- **X1:** [Official FFmpeg filters: atrim](https://ffmpeg.org/ffmpeg-filters.html#atrim), checked September 14, 2026: timestamp-based and sample-count trimming have different semantics when timestamps are inexact or nonzero.
- **X2:** [Official FFmpeg command documentation](https://ffmpeg.org/ffmpeg.html), checked September 14, 2026: input seek/accurate-seek and timestamp behavior. This is supporting rationale for the oracle, not evidence that the repository's specific media incident was caused by seeking.
