---
search:
  exclude: true
---

# Frame Compare Code Quality Planning Handoff

- Date: 2026-10-15
- Recipient: Opus 5.5 planning agent, as requested by the maintainer
- Purpose: Plan the complete set of worthwhile changes established by this assessment
- Status: Planning input; implementation has not been requested in this handoff
- Repository: `/Users/tristan/Software/frame-compare`
- Verified source revision: `e036bc348431c948314019318d40f642c0923784`
- Observed branch: `v0.7.0`

This handoff now incorporates a repository-wide code-health review, expanded at the maintainer's request after the initial focused assessment. It identifies twenty supported correction or improvement groups. At the maintainer's request, two candidates needing further evidence (CQ7 and CQ14) are kept in a [separate investigation report](2026-10-15-code-quality-investigations.md). The most consequential added finding is a Windows source-install rebuild path that recursively deletes an existing user-populated bundle. Other confirmed issues concern config admission authority, malformed persisted input, actual tonemap disclosure, updater version support, diagnostic selection, and test-fixture isolation.

The architectural opportunities give related state one owner, preserve meaningful domain distinctions, and remove coordination that callers currently perform by hand. Plan all supported items below, including small corrections and test-support work; do not turn every item into a standalone large refactor. The proposed interfaces are design candidates, not prescribed class names or a completed implementation plan. The recipient should choose coherent package boundaries, account for full migration and deletion work, and produce an executable plan.

## Original request and subsequent instruction

The maintainer's original request was:

> Any large refactor opportunities or code quality issues/things we can do to improve our repo to better align with pstack skills etc? not in workflow but actual code quality and best modern coding practices? utilize subagents to help where appropriate but ensure theyre tasks are scoped explicitely based on your insight and ideas.

The maintainer then requested this handoff:

> Please write me a detailed report alongside reasoning as well as what my original request was for me to pass to a planning agent (opus 5.5) to plan ALL of the changes you think are worthwhile and lead to a healthy codebase. this report needs to be detailed to save opus as much time as possible during the planning process

The maintainer subsequently expanded the requested depth:

> and i just want to be sure this is all you will suggest for this? there is no deeper or further refactors that would be recommended after we are done with these? i want to address as many as possible/necessary

> yes use as many subagents as you need we want to exhaustively check the whole repo for our report

The maintainer then separated the two unverified candidates from this planning handoff:

> i think we should keep those findings to a second investigatory report then since we need to do some additional work to verify them

The assessment interpreted the reference to skills using the repository's supplied shared engineering skills, particularly `design-code`, `review-code`, and `verify-code`. It did not invent a separate definition or rule set for “pstack.” The intended outcome is healthier product code: clearer responsibility, fewer invalid or contradictory states, simpler callers, and useful evidence. Workflow maintenance, skill changes, agent/developer-tool configuration, executing or publishing releases, and cosmetic modernization are outside this request. Application build/install/update/tool source improvements and affected test support remain in scope.

The user is asking the recipient to plan the complete worthwhile scope. Do not reduce the end state to the easiest preliminary slices. Small slices are appropriate where independently useful, but the plan must identify what remains and how the complete outcome is reached.

## Source identity and scope

The initial assessment inspected HEAD `5d18886aa52260fdec18a20936d2742ebc605138` plus substantial uncommitted changes. Those changes were subsequently committed as `0a1026b5` and `e036bc34`. The report preparation rechecked the relevant source at the full revision recorded above. The working tree was clean before this report was added. Do not use the earlier dirty-state description as the current checkout state.

The initial three scoped investigations supplemented the controller's orchestration analysis:

- Alignment: authority, result/provenance coordination, manual confirmation, reuse, cache publication, and decision gates.
- Report viewer: source/mode transitions, pair offsets, persistence, and image-request lifetimes.
- Rendering: request/result structure, work units, resource ownership, cancellation, and native draining.

The expanded pass added explicit investigations of config/CLI acquisition, analysis/cache identity, native color/geometry policy, metadata/publishing, runtime security/reliability, Windows distribution/update safety, test/fixture quality, native review, and documentation/operations. The controller inspected supporting Docker/build/release code and calibrated the findings. Historical reports elsewhere in the repository remained hypotheses rather than current findings.

The source review uses a wide inventory and deep representative/high-risk traces across the whole repository. It is not a claim that every line of every test was read or that every runtime/environment was accepted. The coverage and limitations sections identify the exact reach of the evidence. No finite review can guarantee that implementation or later feature work will never reveal another useful improvement. The intended stopping condition is that the current supported scope is planned coherently, the separately tracked investigations do not turn into assumed refactors, and no supported ownership problem is left hidden behind a preliminary slice.

Use the current task revision for planning. If the source has advanced, refresh only the affected claims and test routes. Line anchors below describe the verified revision; symbols and call paths are the more durable locator.

For a cloud checkout, repository links beginning `/Users/tristan/Software/frame-compare/` refer to the same paths beneath that checkout's root; strip that prefix when opening files. The reports are `docs/reviews/2026-10-15-code-quality-planning-handoff.md` and `docs/reviews/2026-10-15-code-quality-investigations.md`. Absolute shared-skill links describe the review host and may not exist in the cloud environment. Follow applicable repository instructions and available equivalent guidance; do not assume host tools or native capabilities transfer with this report.

## Planning scope at a glance

| ID | Change | Evidence and priority | Relative scope | Planning disposition |
| --- | --- | --- | --- | --- |
| CQ1 | Own viewer selection, mode changes, and pair offsets as one transition | Reproduced saved-offset corruption | Medium | Plan the defect correction and removal of the repeated synchronization protocol |
| CQ2 | Represent each comparison's alignment resolution in one coherent value | High-confidence maintenance burden across computation, review, diagnostics, and persistence | Medium to large | Plan the full caller migration, with explicit authority and evidence distinctions |
| CQ3 | Preserve clip/frame structure throughout rendering | High-confidence parallel-collection and reconstruction burden | Medium to large | Plan structured requests/jobs/results and removal of superseded plumbing |
| CQ4 | Read current selection at phase execution and give related selection state a coherent owner | Confirmed hidden list-identity dependency; recovery state is a related design seam | Medium | Eliminate the identity dependency; choose a proportionate selection/recovery representation |
| CQ5 | Evaluate automatic-alignment acceptance gates once | Exact duplicate policy, with no present divergence found | Small | Plan a bounded independent cleanup preserving gate behavior and reason order |
| CQ6 | Separate selection failure kinds from diagnostic wording | Recovery currently branches on reason strings | Small to medium | Plan typed internal classification while preserving external diagnostics |
| CQ8 | Acquire effective run configuration once and delete duplicate preview override policy | Reproduced admission/runtime configuration divergence | Medium to large | Give admission, callbacks, preview, execution, and post-actions one run-settings authority |
| CQ9 | Keep the metric request intact and centralize required-cache acquisition | Repeated request reconstruction and failure classification | Medium | Preserve the two required reads while consolidating their policy; derive sampling identity from shared constants |
| CQ10 | Normalize malformed persisted-input failures at their owners | Reproduced unhashable enum, recursion, and integer-limit decode escapes | Small to medium | Preserve cache, optional-review, history, and configuration failure distinctions |
| CQ11 | Carry actual applied tonemap facts into artifacts and report identity | Reproduced fallback output graph disclosed as the requested curve | Medium | Distinguish requested settings from actual per-clip transforms and decide serialized migration |
| CQ12 | Remove dormant render active-picture inference | Sole application caller already passes authoritative supplied rectangles | Small to medium | Delete duplicate unreachable policy while retaining geometry projection and live orchestration inference |
| CQ13 | Carry collection-policy warnings into final run outcomes | Typed mismatch warning is logged but lost from summaries/history | Small | Propagate once without changing successful JSON schema |
| CQ15 | Preserve existing installations during Windows source rebuild | Confirmed recursive deletion of a supported populated output root | Medium | Separate disposable staging from installed/user-owned state; highest safety priority |
| CQ16 | Support the repository's stable and RC version grammar in the updater | Source-confirmed rejection of installed RC versions | Small to medium | Unify extraction, signed range semantics, ordering, and target verification |
| CQ17 | Make explicit rollback use a safe replacement transaction | Current delete-then-copy rollback can destroy a working tree on failure | Medium | Share replacement/recovery policy with apply while retaining archive authentication boundaries |
| CQ18 | Make config-dependent doctor checks use the installed selected config | Windows AppData fallback used by run is ignored by doctor | Small to medium | Share selection policy without adding competing fallback rules |
| CQ19 | Reject nonfinite operation timeouts | Four configured timeouts accept positive infinity | Small | Enforce finite bounds at configuration validation |
| CQ20 | Give each Node test fixture its own document | Reproduced first fixture focusing an element into a second fixture's document | Small | Fix fake DOM ownership and preserve real-browser obligations |
| CQ21 | Reduce test-support coordination and unnecessary fixture work | Concrete duplicate assertions, fixture ownership, cache identity, and spelling coupling | Several bounded seams | Preserve distinct behavioral proof; integrate changes with affected owners rather than rewrite the suite |
| CQ22 | Correct current public doctor and cache descriptions | Source/authority contradict the public reference and Windows acceptance text | Small | Fix the specific contract drift alongside relevant code work |

CQ7 and CQ14 retain their original IDs in the separate investigation report and are intentionally absent from the supported planning table. Their investigation does not block the supported corrections.

“Medium to large” describes migration reach and regression risk, not an estimate of engineer-days or a reason to split work arbitrarily. CQ2 and CQ3 earn their scope by deleting caller coordination and duplicate representations. File length alone is not part of their justification.

## Repository census and review coverage

The tracked inventory contains 673 files: 197 under production source, 278 under tests/support, 50 under tools, 69 under docs, and four under scripts, plus root/build/CI/instruction/configuration assets. Production source includes 36 orchestration files, 49 service files, 21 utilities, 16 VS files, 15 render files, 14 config files, 13 analysis files, 13 CLI files, and nine VSView files, with root modules and bundled assets completing the inventory. Counts are an inventory, not a quality score.

The composition roots are the installed CLI, synchronous runner, async run coordinator, doctor runner, native VSView plugin, and Windows installer/updater entry points. Persistence consists of configuration/preset TOML, shared probe/alignment/TMDB caches, fingerprinted metric JSON, run identity/outcome records, native metadata/result sidecars, screenshots, and offline reports. Network boundaries are slow.pics, TMDB, and an explicitly configured isolated HTTPS webhook.

The build map includes Hatchling wheel/sdist packaging, the locked Python dependency graph, Docker source/native provenance and staged images, Windows portable/update artifacts, signed update manifests, extracted-bundle verification, and release-contract validation. CI definitions were inspected as evidence of entry-point/verification wiring, not as permission to redesign the workflow or as proof that hosted jobs ran at this SHA.

Generated/build/cache/log directories, compiled binaries, third-party dependencies, and opaque media/image/font assets were excluded from qualitative line review. Their inclusion/provenance or artifact ownership was inspected where production/build behavior depends on them. Host/agent workflow configuration was inventoried but not reviewed for workflow redesign. No stale optional code index was used to narrow the source census.

The dimension coverage and no-finding notes later in this report distinguish a wide scan from deep source tracing. The approved writable outputs are this non-product handoff and the separate investigation report, including their subsequent documentation-only commit for cloud access. No product code, tests, configuration, dependencies, or release artifacts were modified.

## Repository obligations and design standards

Read the current agent entrypoint (`AGENTS.md`), project profile (`.agents/project.md`), [architecture](../current-architecture.md), and the relevant sections of the [CLI contract](../current-cli-contract.md) before finalizing the plan. These sources own repository obligations. This report supplies findings and planning inputs rather than a replacement instruction system.

The relevant shared guidance is design-code (`/Users/tristan/.agents/skills/design-code/SKILL.md` on the review host), especially its decision and migration guidance (`/Users/tristan/.agents/skills/design-code/references/decisions-and-migration.md` on the review host), review-code (`/Users/tristan/.agents/skills/review-code/SKILL.md` on the review host), and verify-code (`/Users/tristan/.agents/skills/verify-code/SKILL.md` on the review host). Use develop-code (`/Users/tristan/.agents/skills/develop-code/SKILL.md` on the review host) when implementation is subsequently authorized. These are responsibility-specific tools, not a requirement to run every stage for this planning handoff.

Frame Compare is a Python 3.13+ CLI-first packaged application for deterministic frame comparison, audio/video alignment, tonemapping, static offline reports, and optional publishing. Internal import paths are convenience surfaces unless explicitly supported; API documentation alone does not require keeping obsolete internal entry points.

The proposed changes must preserve the following obligations:

- Help and version work without eager native-media imports. JSON stdout remains machine-clean, diagnostics use the appropriate stream, and expected failures retain typed/sanitized error behavior.
- Fresh computed alignment remains a candidate until the audio/video decision owner authorizes it. Provisional or unavailable evidence cannot become trim authority or computed-cache authority. A valid zero offset remains different from no accepted offset.
- Original evidence survives manual confirmation. Fresh estimator time, frame offsets, manual time, and historical cache evidence retain their distinct meanings.
- Source freshness follows the documented path/size/mtime identity policy. Frozen records do not prove that external source files remain unchanged; checks at actual acceptance and publication boundaries remain necessary.
- Cache formats, report payloads, native metadata/results, run records, source-frame conventions, stable ordering, physical screenshot naming, and persistence boundaries remain explicit. Keep existing serialized formats unless a real migration requirement is established.
- Caller-owned injected loaders and HTTP clients stay caller-owned. Atomic writes, lock ownership, containment, cancellation admission, worker draining, and subprocess reaping retain their current guarantees.
- Analysis, render, and services remain independent sibling domains under the existing import contracts unless a deliberate design decision changes that contract. Do not put a shared convenience type in an unrelated layer merely to bypass import rules.
- Docker, Windows portable, native Python, Node harnesses, and browser acceptance establish different claims. A passing simulated/static check is not evidence for an unavailable target runtime.

Apply the shared design principles to concrete burdens:

1. Give an operation's policy to one owner so callers can express intent without sequencing internal mechanics.
2. Use types or records where they remove an actual invalid state, distinguish authority/units/lifetime, or simplify a caller. Do not wrap every primitive.
3. Pair values that must stay associated. Prefer an owned collection of coherent records over multiple mutable collections with matching indexes or keys.
4. Derive redundant state where practical. Keep transient editing state and independently meaningful observations separate.
5. Retain validation at external, native, persisted, IPC, and independently evolving boundaries. Internal location alone does not establish trust.
6. Plan caller migration and deletion together. Temporary compatibility layers need an actual consumer or rollout requirement and a removal condition.
7. Preserve distinct behavioral proof. Change implementation-coupled tests when necessary, but retain the failure obligations they were intended to establish.

## CQ1 Own report selection and pair offsets as one transition

### Current mechanism and reproduced failure

The source selectors in [viewer.js](/Users/tristan/Software/frame-compare/src/frame_compare/services/report/assets/viewer.js:982) coordinate the following sequence themselves:

1. Store the current pair's spatial offset.
2. Mutate the left or right source index.
3. Enforce the current mode's distinct-pair rule.
4. Load the destination pair's spatial offset.
5. Reconcile Blink's active source.
6. Render and persist.

`swapPairClips()` implements a similar protocol. [setMode()](/Users/tristan/Software/frame-compare/src/frame_compare/services/report/assets/viewer.js:1645) can also change the source pair through `ensureDistinctPairSelection(mode)`, but does not perform the pair-offset transition. [persistViewerState()](/Users/tristan/Software/frame-compare/src/frame_compare/services/report/assets/viewer.js:1092) calls `storeCurrentPairAlignment()`, which joins the newly selected pair with independently mutable current offset fields. [Viewport's store/load methods](/Users/tristan/Software/frame-compare/src/frame_compare/services/report/assets/viewport.js:534) therefore depend on the caller having kept those fields synchronized.

The resulting defect is reproducible for both Diff and Blink:

| Step | Pair | Current spatial offset | Stored offset for pair `0:1` |
| --- | --- | --- | --- |
| Set a manual offset for sources 0 and 1 | `0:1` | `(7,3)` | `(7,3)` |
| Enter Slider and select source 0 on both sides | `0:0` | `(0,0)` | `(7,3)` |
| Enter Diff or Blink | Pair repair restores `0:1` | Incorrectly remains `(0,0)` | Incorrectly overwritten with `(0,0)`, including persisted storage |

Expected behavior: changing to a mode requiring distinct sources restores the destination pair's existing `(7,3)` offset and preserves its stored value. A destination pair without a saved offset should receive the existing neutral default.

This concerns spatial pixel translation in the report viewer. It is distinct from temporal source-frame/audio alignment.

### Recommended responsibility and alternatives

Give pair selection, pair repair, directional offset selection, and active-source validity one transition owner. Candidate operations are `selectLeft`, `selectRight`, `swap`, `setMode`, and `setOffset`, with a read-only selection snapshot for presentation. Root viewer composition can still own events and DOM updates; Viewport can still own geometry and gesture mechanics.

Prefer deriving committed current alignment from the selected pair, or otherwise make loading/storing it an internal part of the transition. Callers should not need the store/mutate/repair/load protocol. Do not accidentally collapse `rawAlignX`/`rawAlignY` input drafts into committed offsets: transient editing state has its own meaning.

A credible smaller design is one explicit transition function in the existing owner, without a new module. Choose it if it removes the protocol from all callers as clearly as a new model. Merely adding a missing `loadCurrentPairAlignment()` call in `setMode()` fixes the immediate symptom but leaves the repeated maintenance obligation; the plan should address that obligation as well.

### Migration and deletion scope

Trace and migrate source selectors, swaps, keyboard shortcuts, default selection, persisted-state restoration, mode changes, pair reset/reset-all, and Blink active-source reconciliation. Remove caller-level pair-offset choreography. Remove redundant committed current-offset copies if the resulting interface is clearer; do not retain two mutable authorities behind compatibility getters.

Preserve directional offset semantics, valid same-source Slider selection, single-source behavior, existing storage key/schema, malformed-state normalization, restored width-fit compatibility, keyboard/focus behavior, Blink pause intent, Grid pan-unit conversion, and stale Diff-image commit rejection. This change does not authorize a visual redesign.

### Verification and completion criteria

Use the existing Node fixture and tests listed in the verification map below. Add or extend a behavioral regression for same-source Slider → Diff and Slider → Blink, with both a preexisting destination-pair offset and an unset destination-pair offset. Observe current state and persisted state. Preserve reverse-pair behavior and restore semantics.

The defect probe in Appendix A uses a fixture that substitutes `render` with production `applyAlignment()` and `persistViewerState()`. It establishes state/persistence corruption, not browser rendering. Use real-browser proof for the changed interaction; extend a relevant browser case if the existing smoke does not observe this transition.

Completion means that every selection-changing entry point uses the same owned transition, the reproduced overwrite is fixed, persisted compatibility is retained, and the old synchronization protocol is removed from callers.

## CQ2 Make each comparison alignment resolution one coherent value

### Current burden and source trace

[align_clips_from_request()](/Users/tristan/Software/frame-compare/src/frame_compare/services/alignment.py:1206) creates parallel `results_map` and `provenances` dictionaries. [AlignmentProvenance](/Users/tristan/Software/frame-compare/src/frame_compare/services/types.py:86) contains another `result`, plus computed fallback and evidence-availability fields. Computation, cached reuse, manual overrides, presentation, diagnostics, and persistence must coordinate these representations.

The manual-review path makes the sequencing requirement particularly clear. [_apply_confirmed_vsview_offsets()](/Users/tristan/Software/frame-compare/src/frame_compare/services/alignment.py:211) changes the current result; [_record_interactive_provenance()](/Users/tristan/Software/frame-compare/src/frame_compare/services/alignment.py:1095) subsequently updates provenance. The latter deliberately reads the old provenance result to preserve the computed fallback. [The caller must invoke them in the right order](/Users/tristan/Software/frame-compare/src/frame_compare/services/alignment.py:1338).

This is a high-confidence maintenance burden. No reachable current authority bypass was established. Existing constructors and decision checks are useful protections and should not be described as broken merely because their inputs are cumbersome.

### Recommended representation

Compare these two designs:

- **Smallest coherent option:** one map of the existing provenance records, derive the current result from each record, and replace separate result/provenance updates with complete immutable replacement operations.
- **Stronger domain option:** one comparison-resolution record distinguishing current accepted/unresolved authority, origin, original attempt, accepted computed fallback, and evidence availability. Introduce explicit accepted/unresolved variants only where they remove repeated `applied`/`None` checks or invalid combinations in real callers.

A representative conceptual value is:

```text
ComparisonResolution
    comparison identity
    current authority: accepted offset or unresolved
    origin: current computation, current confirmation, shared computed,
            shared previous, or existing override
    original current-run attempt, when one exists
    accepted computed fallback, when one exists
    evidence availability, preferably derived when unambiguous
```

Manual confirmation should be one pure operation returning the complete replacement. It must preserve the original attempt rather than rewriting it to match the manual result.

The following examples are design acceptance cases:

| Starting evidence | Human decision | Required resulting meaning |
| --- | --- | --- |
| Provisional `+12` frames | Confirm `0` frames | Applied manual zero; identical original attempt/digest; no accepted computed fallback |
| Trusted computed `+42` frames | Confirm `+47` frames | Current manual authority is `+47`; original trusted attempt still describes `+42`; accepted computed fallback remains `+42` |
| Shared computed offset with stability but no original attempt | Reuse | Historical accepted authority remains usable under existing policy; original-attempt details remain unavailable |
| Unavailable computation | Keep current/missing optional review | Retain current documented unresolved/accepted behavior; do not manufacture an offset or confirmation |

Fresh computed time includes the estimator's subframe meaning. Do not replace every computed time with `frame_offset / fps`. Manual confirmed time follows the existing reference-FPS conversion. Historical entries may have accepted offsets without fresh evidence.

### Cache candidate preparation belongs in this migration

The cache checks are complementary today:

- [shared_write_is_service_eligible()](/Users/tristan/Software/frame-compare/src/frame_compare/services/alignment_previous_offsets.py:204) owns operation-level policy: complete requested set, applied results, allowed origins, and at least one current-run acceptance.
- [_is_write_eligible()](/Users/tristan/Software/frame-compare/src/frame_compare/services/alignment_reuse_cache.py:472) checks per-entry authority/serializability: trusted fresh attempt and stability, historical computed stability, or a valid optional computed fallback for interactive authority.
- [save_reusable_offsets()](/Users/tristan/Software/frame-compare/src/frame_compare/services/alignment_reuse_cache.py:545) also checks requested-set completeness and owns source-currentness, locking, merge, serialization, and atomic publication.

Do not delete these as interchangeable duplicate checks. Within the resolution redesign, consider one `prepare_reusable_source_set(request, resolutions)` operation that returns an eligible complete source set or no candidate. It can own the combined eligibility decision while persistence retains the checks and mechanics that protect changing files and publication.

Purely historical reuse must not refresh acceptance timestamps by becoming a new current-run acceptance. Manual overrides, confirmed previous offsets, fresh computed offsets, and shared computed offsets must keep their existing precedence and publication consequences. Keep cache schema v2 unless a real serialized change proves necessary.

### Migration and deletion scope

Migrate manual overrides, shared reuse, fresh computation, native confirmation, progress/presentation, diagnostics, cache candidate preparation, and final ordered phase results. Derive any existing external-facing result shape at the appropriate seam. Delete the parallel result map, separate post-confirmation provenance repair, and redundant internal eligibility choreography once the replacement owns their complete obligations.

Retain source-freshness checks around acceptance, early reuse returns, and locked publication. These protect an external resource changing over time; immutable records do not replace them. Retain strict native-result and persisted-evidence validation. The estimator, video-scoring algorithm, evidence schema, and native review UI are outside the necessary refactor scope.

### Evidence gaps and completion criteria

The test map below names existing proof. One important qualification: `test_align_clips_from_request_mixed_cached_computed_and_new_computed_write_back` patches the writer and asserts final result behavior without proving actual complete-source-set publication. Reconfirmation tests also inspect writer inputs rather than all on-disk semantics. Strengthen an appropriate existing case or add the missing behavioral observation so the migration proves both mixed historical/current publication and no publication for all-historical reuse. A promising test name is not proof of its implied behavior.

Completion means every per-comparison authority change is a complete replacement, original evidence/fallback semantics survive, ordered output and serialized formats remain compatible, and the cache publication decision is understandable without reading several callers' mutable maps.

## CQ3 Preserve clip and frame structure through rendering

### Current burden and caller trace

The product operation is a collection of selected screenshots for each clip, but its internal representation repeatedly loses and rebuilds that structure:

1. [Phase rendering](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/phase_render.py:57) constructs parallel `source_frames`, `comparison_frames`, and `selection_labels`, alongside expected-frame information.
2. [Batch expansion](/Users/tristan/Software/frame-compare/src/frame_compare/render/batch/expansion.py:98) returns flat render requests, label-to-range mappings, and clip-fact mappings.
3. [Work-unit construction](/Users/tristan/Software/frame-compare/src/frame_compare/render/batch/orchestrator.py:61) validates range continuity and coverage to reconstruct clip work units.
4. [Batch rendering](/Users/tristan/Software/frame-compare/src/frame_compare/render/batch/orchestrator.py:403) splits `RenderedFrameResult` records into separate path and fact mappings using those ranges.
5. [RenderedBatchResult](/Users/tristan/Software/frame-compare/src/frame_compare/render/types.py:90) and [RenderArtifacts](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/execution_types.py:34) independently validate matching labels and path/fact counts. [The phase copies the three mappings directly](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/phase_render.py:119).
6. [Report composition](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/phase_post_render.py:327) subsequently rejoins screenshots, frame facts, and clip facts by label.

The scheduler already treats each production clip job as an indivisible work unit while allowing different clips to overlap. The flatten/reconstruct protocol is therefore a representation burden rather than a required product abstraction.

### Recommended model and alternatives

Use coherent per-frame selections, ordered prepared clip jobs, and per-clip results. Candidate shapes are:

```text
SelectedScreenshot(source_frame, comparison_frame, selection_label)
PreparedClipRender(label, clip_facts, requests: tuple[RenderRequest, ...])
RenderedClip(label, clip_facts, frames: tuple[RenderedFrameResult, ...])
```

`RenderedFrameResult` already pairs a path with exact-frame facts. Preserve that pairing rather than decomposing it into independently mutable lists. The orchestration artifact can compose the render-owned collection with screenshot directory and warnings. Publishing/report serializers can derive the dictionaries their actual contracts need.

A smaller independently useful slice consolidates the duplicate result containers first. The complete worthwhile end state also addresses request-list synchronization and range reconstruction. Do not introduce cached mutable compatibility dictionaries that leave the original synchronization problem in place.

### Migration and deletion scope

Move request frame data into selected-frame records; have expansion return ordered prepared clip jobs after global output/collision planning; pass those jobs directly to scheduling; retain per-clip/per-frame results through orchestration; migrate report/publish consumers at their actual boundaries.

Once migrated, remove label-to-range plumbing, the result-by-label reconstruction helper, and duplicate internal cardinality validators made unnecessary by the representation. Audit actual callers before removing flat convenience APIs, including tests, plugin entry points, and supported surfaces. Internal location alone is not enough to prove that a consumer does not exist.

Preserve deterministic source/result/progress order, per-clip serialization, parallel overlap across clips, partial-completion semantics, lowest-request-index failure precedence, global collision refusal before native preparation, source-frame bounds, exact source-frame/fact association, and authoritative prepared-source presentation facts.

Native and injected backends remain trust boundaries. Keep validation that they returned the expected actual source-frame identity and count. A structured record does not prove that an encoder observed the right frame.

### Cancellation is a constraint rather than a rewrite target

The batch-owned `threading.Event`, main-thread polling, per-frame admission checks, and draining of admitted native work have concrete reasons and existing proof. Preserve that model while changing work-unit representation. The current real-SIGINT test observes a 150 ms admission bound, not a finite deadline for an uninterruptible native call to finish.

FFmpeg has bounded termination/reaping and staged promotion; an in-flight VapourSynth native frame request has different drain guarantees. Keep those distinctions. Neither a generalized async scheduler nor a generic resource manager was justified by this assessment.

Completion means the normal render path carries structured clip/frame data end to end, consumers no longer synchronize parallel maps/ranges, and the existing ordering/failure/cancellation/native-fact contracts still hold.

## CQ4 Remove phase dependence on selected frame list identity

### Confirmed dependency

[build_phases_before_align()](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/execution.py:214) passes `state.selected_frames` into a `partial` before phases execute. [The render phase is constructed similarly](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/execution.py:298). [apply_phase_output()](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/phase_output_application.py:23) uses slice assignment to mutate that exact list for frame-plan, analyze, and align outputs.

Today this works. The hidden invariant is that the list object must survive every phase. Replacing `state.selected_frames` with an equivalent new list would leave previously constructed phases reading stale selections. Other post-render closures already read current artifacts at execution time, demonstrating a straightforward local alternative.

Selected frames live in `ExecutionState`, while selection breakdown/details/metrics and prepared domain information live in [RunContext](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/context.py:129). Maintaining their relationship is spread across output application and recovery code.

### Recommended change and scope boundary

Have phase execution read the current selection rather than capturing a mutable list early. Then evaluate a coherent selection snapshot that carries selected frames and the metadata/domain needed to interpret them. Make the coordinate vocabulary explicit: selected comparison/reference-relative frames, reference source-frame details, and analysis-source metric coordinates are not interchangeable.

Do not convert every `RunContext` field to a universal immutable run-state hierarchy. Keep phase outputs as useful explicit boundaries. A smaller design can use execution-time adapters plus one focused selection value; a larger prepared-domain value is justified only if it removes real coordination from recovery/preparation callers.

[_apply_confirmed_override()](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/full_window_retry.py:188) already computes new configuration, refined clips, analysis source, window, and domain token before updating context. Its assignments are synchronous. No exposed partial-state/concurrency bug was established. The related opportunity is to represent and replace that coherent prepared selection domain explicitly, rather than treating seven fields as an undocumented group.

### Recovery and warning obligations

Retain authored versus effective config separation, explicit interactive consent, no retry offers for JSON/quiet/cache-only/disabled-analysis modes, exactly one accepted retry, fatal failure after accepted retry, active-rectangle refinement/recomputation, selection-domain/cache-key recomputation, and no uniform fallback after failed accepted recovery.

Preserve replacement of superseded frame-plan warnings, retention of unrelated warnings, and preflight active-rectangle warning updates. Avoid state bundles whose convenience silently conflates source-frame details with trimmed render-frame selection.

### Verification and completion criteria

An important behavioral regression constructs the phase plan before selection, then exercises frame-plan/analyze/align replacement and verifies that downstream alignment, rendering, and reporting receive the latest selection and matching metadata. Observe the consumed values rather than asserting that a particular list identity or slice assignment survives.

Retain existing cache-only failure behavior, cross-domain mapping, aligned reselection, and full-window recovery tests. Completion means replacing the current selection with a new coherent value cannot make later phases consume stale frames, and related metadata/domain ownership is explicit enough that callers do not repair it piecemeal.

## CQ5 Evaluate automatic alignment gates once

[v6_failure_reasons()](/Users/tristan/Software/frame-compare/src/frame_compare/services/alignment_decision.py:287) and [is_trusted_automatic()](/Users/tristan/Software/frame-compare/src/frame_compare/services/alignment_decision.py:326) encode the same five requirements separately:

1. Audio authority recount passes.
2. Video was observed and has a confirmed offset.
3. Every competing run is resolved.
4. Every credible disagreement is resolved.
5. No alternative target is confirmed.

[decide_after_video()](/Users/tristan/Software/frame-compare/src/frame_compare/services/alignment_decision.py:595) calls both. Adding or changing a gate therefore requires synchronized acceptance and explanatory changes. No present disagreement was found.

Evaluate ordered failures once, then derive trust from an empty failure tuple. Keep named, readable gate logic rather than introducing a generic policy engine. Remove the duplicate predicate if the caller audit confirms no real consumer; otherwise a trivial delegate is an acceptable temporary shape with a stated consumer.

Preserve exact primary-reason ordering, independent gate requirements, search-edge refusal, unavailable/inconclusive early returns, candidate construction, recount behavior, and A4b regrouping. Migrate tests of the removed predicate to the surviving semantic owner rather than deleting independent negative cases.

This can ship independently of CQ2. Completion means acceptance and explanations have one source of truth, with unchanged decision outcomes and reason ordering.

## CQ6 Separate selection failure classification from diagnostic wording

[SelectionError](/Users/tristan/Software/frame-compare/src/frame_compare/analysis/errors.py:6) stores a string `reason` used in its message and serialized details. Recovery policy matches exact strings in [_ELIGIBLE_REASONS](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/full_window_retry.py:47), as well as a separate exact empty-window reason. Producers include [metric selection](/Users/tristan/Software/frame-compare/src/frame_compare/analysis/selection.py:130), [window computation](/Users/tristan/Software/frame-compare/src/frame_compare/analysis/window.py:55), and initial frame planning.

Some strings look like stable machine identifiers and others are prose. Changing a message such as “insufficient random candidates after user frames” can silently alter eligibility for consent-gated recovery. This is a control-flow coupling, not a claim that current reasons misclassify observed failures.

Add a typed internal failure classification, using an enum or a small literal set as appropriate, and have recovery branch on that classification. Keep diagnostic reason text, requested/found counts, error code, hints, and existing serialized fields compatible. A type can be internal without adding a new field to public JSON.

Audit actual producers and consumers. Give unclassified/nonrecoverable failures explicit nonrecoverable behavior rather than a permissive default. Runtime failures wrapped after accepted recovery must remain fatal; exception type names need not become a sprawling global enum. Keep this scoped to selection/recovery, rather than rewriting the repository's error taxonomy.

CQ6 can precede CQ4 or be integrated with the selection-domain migration where file ownership makes that simpler. Completion means rewording a diagnostic cannot change recovery policy, existing qualifying failures retain consent/retry semantics, and nonqualifying failures remain nonrecoverable.

## CQ8 Give each execution one acquired configuration

**Classification:** confirmed admission/authority mismatch, S2 Medium, High confidence. The duplicate preview policy is a related maintainability burden.

[CLI admission](/Users/tristan/Software/frame-compare/src/frame_compare/cli/run_command.py:271) acquires effective settings, validates mode compatibility, configures logging, builds callback legality/visibility, and previews them. [RunRequest](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/types.py:24) carries the config path and overrides rather than that admitted value. [Runtime preparation](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/preparation.py:541) calls [preflight acquisition](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/preflight.py:410) again and reapplies overrides. The cached first config still controls callbacks and post-upload actions.

A bounded probe acquired/validated JSON execution with `audio_alignment.use_vsview=false`, changed a temporary config file to `true`, and called the actual preflight/effective-config owners. The observed values were admitted `false`, runtime `true`, cached CLI `false`. Rechecking the complete CLI contract against runtime settings raised `ConfigValidationError`; the actual preparation path does not perform that complete recheck. This proves differing real acquisitions and admission authority, not an observed GUI launch or damaged JSON stream. The trigger requires a change between reads.

Introduce one dependency-light acquired run-input value containing selected config identity, resolved root, effective settings, and necessary path facts. Admission, callback construction, preview, execution, logging, and post-actions should consume that run authority. Programmatic runner/preparation callers need the same acquisition owner once. Avoid an optional settings object alongside an optional path that creates contradictory authorities. A credible alternative is moving admission/preview/callback setup after runtime acquisition through a clean preparation interface; merely rechecking selected flags leaves competing snapshots.

Also delete preview's second override policy. [print_at_a_glance](/Users/tristan/Software/frame-compare/src/frame_compare/cli/output.py:192) receives already-effective config from its sole production caller, but redoes input path, frame counts/seed, overlay, upload, and interactive overrides. [Preview tonemap resolution](/Users/tristan/Software/frame-compare/src/frame_compare/cli/output.py:169) keeps another override dictionary and a preview-only branch in the render resolver. Preview should read effective config; the request should supply genuinely run-only controls. Remove `TonemapCliOverrides` and the resolver's second override branch once real consumers are migrated.

Migrate CLI request construction, admission/dependencies/preview/post-actions, orchestration request/preparation/preflight, runner/coordinator composition, [the alignment benchmark's direct preparation call](/Users/tristan/Software/frame-compare/tools/alignment_benchmark.py:266), and maintained request builders. Preserve runtime-free simple commands, dry-run side-effect boundaries, raw wizard edits, secret-safe persistence, source freshness, and containment checks at actual use boundaries.

The [post-run auto-open refresh](../current-cli-contract.md#report-auto-open-ownership) is intentional and tested; retain it as a separately named preference refresh. An execution snapshot does not freeze every future preference read.

Retain the request-config, dry-run, preview, logging precedence, preparation/cache/lifecycle/benchmark/import tests; in particular the [report-open suite](/Users/tristan/Software/frame-compare/tests/cli/test_run_report_open.py) and [color roundtrip suite](/Users/tristan/Software/frame-compare/tests/config/test_color_roundtrip.py). Add a changed-config-after-admission observation proving stable runtime policy and callbacks while the intentional post-run preference refresh still sees later edits.

Do not add an independent authored/resolved color hierarchy. `model_fields_set` already represents real explicit-versus-inherited semantics. Whole-config `exclude_unset=True` can discard a nested model mutated under an unset root field. A narrow removal of recursive explicit-field restoration is worth checking during this migration only if existing color/override/persistence tests prove equivalent behavior; it is not a prerequisite or another architecture campaign.

## CQ9 Keep metric requests intact through acquisition

**Classification:** subjective maintainability concern, S3 Low immediate impact, High confidence. Its migration reach is medium because cache identity and computation must stay synchronized.

[metric_cache_request_for_clip](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/active_rect.py:125) builds the existing analysis-owned `MetricCacheRequest` with source, range, FPS semantics, rectangle, and provenance. [Analyze](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/phase_selection.py:324) decomposes it into keyword arguments while sourcing path/FPS separately. [calculate_metrics](/Users/tristan/Software/frame-compare/src/frame_compare/analysis/metrics.py:168) reconstructs it, then metric construction flattens it again into metadata. Cache keying and request matching separately enumerate those identity fields. Adding a computation-affecting field requires synchronized edits across all these forwarding sites; defaults can conceal omissions.

Pass the existing request intact into analysis acquisition and metric construction. Analysis should own resolution of absent full-source range/FPS against the loaded source, and translation into serialized metadata. Preserve the difference between absent request information and concrete observed metadata: do not change fingerprint bytes merely by substituting resolved values. Migrate the production computation caller, the analysis-tier benchmark and any other audited direct tool/test callers; remove the parallel keywords/reconstruction. Preserve schema v8 and explicit persisted validation.

Consolidate required-cache acquisition as part of this seam. [Preparation's cache-mode check](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/preparation.py:275) and [Analyze's required-cache helper](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/phase_selection.py:366) duplicate fingerprint/loading/path selection and corrupted/version/missing classification. One analysis-owned required-read operation can return valid metrics or the existing typed failure. **Keep both reads:** preflight rejects before output reservation; execution reacquires and aborts if state changed. Do not memoize the first result or restore predictive reads for normal compute-or-hit acquisition.

As a small related policy correction, [metric algorithm identity](/Users/tristan/Software/frame-compare/src/frame_compare/analysis/metric_identity.py:79) hardcodes sampling `1/4` and maximum bursts `8`, while [execution](/Users/tristan/Software/frame-compare/src/frame_compare/analysis/sampling.py:8) uses constants. Derive those identity fields from the execution constants. Keep explicit semantic algorithm-version ownership and independent sampling-budget expectations. Current values agree; no stale-cache event was observed.

Use the [metric identity/cache tests](/Users/tristan/Software/frame-compare/tests/analysis), request-aware mismatch/range tests, effective-FPS/active-rect forwarding tests, and preparation/execution cache-mode tests. The distinguishing comparison is byte-identical cache keys and compatible v8 metadata for equivalent pre/post-migration requests, including absent versus explicit full-source range and explicit FPS equal to source FPS. Cache-only corruption must still fail before reservation and must not compute when the second read fails.

Do not merge probe and metric caches: aggregate locked TOML updates and immutable fingerprinted JSON entries have different lifetimes/failure contracts. Do not force sliced in-memory sparse metrics to equal a newly planned canonical sample map; aligned-overlap reselection legitimately slices them.

## CQ10 Preserve typed recovery for malformed persisted inputs

**Classification:** confirmed defects, S2 Medium for the metric enum failure and S3 Low for pathological decoder-depth/numeric inputs; High confidence from bounded probes. These share an input-boundary correction package, not a universal codec design.

[Metric active-rectangle source parsing](/Users/tristan/Software/frame-compare/src/frame_compare/analysis/cache_io.py:546) and detection-mode parsing test arbitrary decoded values for set membership before establishing string type. Lists/dictionaries raise `TypeError`, escaping `load_cached_metrics` instead of becoming `_CacheParseError` and a corrupted-cache result. A valid payload hit; an invalid string became `corrupted`; source `[]` and detection mode `{}` leaked `TypeError`. Normal acquisition therefore fails rather than recomputing, while cache-only paths miss their intended typed corruption failure.

Require the expected type at each enum decode boundary and normalize rejection locally. Do not solve this by broadly swallowing internal `TypeError`. Appendix B gives the actual-reader reproduction using a valid control and memory-backed filesystem delivery.

A sibling sweep found decode-stage exceptions that occur before semantic validation:

- [Metric JSON reading](/Users/tristan/Software/frame-compare/src/frame_compare/analysis/cache_io.py:212) and [native result JSON reading](/Users/tristan/Software/frame-compare/src/frame_compare/vsview/alignment_review_contract.py:283) leak `RecursionError` for approximately 20 KiB of nested arrays and plain `ValueError` for a 5,000-digit integer on the inspected interpreter.
- [TMDB TOML reading](/Users/tristan/Software/frame-compare/src/frame_compare/services/tmdb_cache.py:272) leaks analogous recursion and integer-limit exceptions from approximately 6 KiB of nested inline tables or a long integer.
- [Per-record history reading](/Users/tristan/Software/frame-compare/src/frame_compare/services/run_result_record.py:602) correctly isolates the integer-limit `ValueError`, but still leaks recursion instead of marking that entry unavailable.
- Shared alignment/manual/probe TOML readers have analogous narrow decode catches; inspect and test those owners as sibling cases before claiming their behavior is proved.

The safe probes used actual stdlib decoders and owning reader/error policy with filesystem delivery adapted to memory. No native process or network service ran. These are malformed local/generated-state recovery defects, not demonstrated exploits or arbitrary-code execution. [Python documents decoder resource considerations and interpreter limits](https://docs.python.org/3.13/library/json.html#implementation-limitations). Native embedded evidence already has a useful local pattern converting `(RecursionError, ValueError)` into the typed review-contract error.

Normalize decoder failures at each owner into its existing policy: recoverable cache miss/recompute, typed cache-only error, optional native-review rejection retaining authority, or isolated unavailable history entry. Invalid authored user config must remain an actionable typed failure rather than silently defaulting. Add bounds where the format's real valid capacity supports them; do not impose an arbitrary small metric-cache byte cap on duration-scaled arrays. Scope catches to decode/validation, preserving programmer and lifecycle failures.

Extend existing cache-validation, optional-review result, TMDB corruption, and history malformed-record cases through real temporary files. Cover valid control, ordinary corruption, wrong-shaped enum values, nested inputs, long integers, cache-only refusal, recomputation, optional retained offsets, and isolation of one bad history entry among good entries. Completion is correct owner-specific recovery, not merely absence of an exception.

## CQ11 Carry actual applied tonemap facts

**Classification:** confirmed policy/disclosure defect, S2 Medium, High confidence. Native pixel fidelity was not measured.

[Tonemap dispatch](/Users/tristan/Software/frame-compare/src/frame_compare/vs/tonemap.py:50) returns only a clip, losing which implementation succeeded. [Fallback](/Users/tristan/Software/frame-compare/src/frame_compare/vs/tonemap_fallback.py:37) always applies its peak-scaled rational/Reinhard-like expression regardless of requested `tone_curve`. [Preparation](/Users/tristan/Software/frame-compare/src/frame_compare/render/prepare.py:92) attaches the original requested settings as effective facts. [Overlay text](/Users/tristan/Software/frame-compare/src/frame_compare/render/overlay_text.py:136), [clip presentation](/Users/tristan/Software/frame-compare/src/frame_compare/services/report/payload.py:595), and global disclosure then identify the requested curve as applied.

A bounded diagnostic using existing clip/overlay/report fixtures, real preparation/dispatch/fallback/serializers, and unavailable-plugin discovery produced a fixed `x 3 * dup 1 + / 2 * 0 max 1 min` expression while the overlay said `Tonemap: Spline → 203 nits` and payload identified `spline`. This establishes the policy and disclosure loss; mocked native operations do not establish output-pixel accuracy.

Return an applied-transform result from dispatch: the clip plus immutable implementation/algorithm identity, meaningful effective controls, resolved source-peak facts, and fallback cause. Keep requested settings separately where useful. The fixed fallback should have its own truthful algorithm identity; setting `tone_curve=REINHARD` alone overstates equivalence with plugin Reinhard and still presents ignored controls as effective.

Migrate prepared source, render clip facts, overlay input, per-clip report presentation, and output-affecting report identity together. [Current report orchestration](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/phase_post_render.py:371) assumes one shared applied settings value; actual per-clip implementations may differ after runtime failure despite identical config. Make per-clip applied facts authoritative and derive a shared summary only when they match. Decide payload versioning, schema/consumer changes, identity semantics, and preservation of independently saved reports/review state explicitly. Do not silently add implementation-specific facts while pretending the old payload contract is unchanged.

The planner should consider whether an unavailable requested transform should fail or use a disclosed fallback. Current permitted runtime fallback is tested behavior; changing that policy needs an explicit product decision, not incidental removal. Preserve fatal configuration/signature errors, source-prop precedence, range-expansion restrictions, cancellation admission, and separate native-review preview defaults.

Retain [dispatch/fallback tests](/Users/tristan/Software/frame-compare/tests/vs/test_tonemap_apply.py), [extracted conversion/fallback cases](/Users/tristan/Software/frame-compare/tests/vs/test_tonemap_extracted_modules.py), [render wiring](/Users/tristan/Software/frame-compare/tests/render/test_tonemap_wiring.py), overlay disclosure, actual-preparation expansion, report-output, and report-identity tests. Add the missing joined observation: two clips requesting identical settings but receiving different actual implementations disclose independently and have an appropriate output identity. Obtain the applicable real-media proof for graph/output changes.

## CQ12 Delete dormant render active picture inference

**Classification:** subjective maintainability concern, S3 Low, High confidence from caller audit.

[Batch expansion](/Users/tristan/Software/frame-compare/src/frame_compare/render/batch/expansion.py:248) is the sole production caller of `plan_render_geometry` and always passes `active_rect_detection="provided"`. Every screenshot batch request requires canonical `ActivePictureFacts`. Other consumers of render's dimension/aspect inference are tests, and no registered public entry point requires that internal fallback.

Nevertheless, [render geometry](/Users/tristan/Software/frame-compare/src/frame_compare/render/geometry.py:285) retains dimension inference, aspect candidates/ranking, removal thresholds, and inference provenance, duplicating live [orchestration resolution](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/active_rect.py:299). The [architecture's direct-call inference claim](../current-architecture.md) is stale relative to the required request and actual caller.

Make render geometry consume dimensions plus resolved active-picture facts and own only native/full-frame projection, mod-safe crop, scale/canvas choice, padding, and overlay origins. Delete dormant detection modes/options, candidate helpers/constants, and unnecessary canonical-to-render-provenance-to-canonical translation. Retain orchestration inference/content propagation and its cache-identity consequences.

Map distinct old inference cases to retained orchestration proof before retiring tests. Preserve render crop/scale/pad, odd/mod-safe bounds, native preservation, backend application, and overlay placement. Use the active-rectangle, geometry, expansion-geometry, FFmpeg frame, and encoder suites. Completion is one live inference authority and a narrower render projection interface, not simply a smaller file.

## CQ13 Retain collection policy warnings in run outcomes

**Classification:** subjective maintainability/observability concern, S3 Low, High confidence. This is not a violation of the successful-JSON contract.

[Collection metadata policy](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/slowpics_metadata.py:68) produces an explicit/resolved TMDB mismatch as a typed `RunWarning`. [Publishing](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/phase_post_render.py:177) logs it, but `PublishPhaseOutput` carries only post-action warnings indirectly. Output application, final summaries, and completed records lose the original policy warning.

An in-memory joined probe used real policy, phase wiring, output application, result assembly, terminal formatting, and record construction; remote publication alone was replaced with a successful result and unexpected HTTP was rejected. It observed one mismatch log, zero result warnings, a `completed` record with warning count zero, no mismatch in the final summary, and the successful uploaded URL preserved. The documented promise to emit a sanitized warning is technically satisfied by the log; the improvement is making producer-owned warning semantics survive the whole run outcome.

Add a normal warnings collection to the publish output, forward the policy warnings, and accumulate them once. Retain diagnostic logging and existing post-action behavior. Verify one final warning in the result, terminal summary, and completed-record count, alongside successful publication and isolated explicit association/title policy. Keep successful JSON's existing omission of warning fields. A publishing state-machine rewrite or persisted-format migration is unnecessary.

## CQ15 Preserve user state during Windows source installation

**Classification:** confirmed destructive source-installer path, S1 High, High confidence from source and documented ownership. No destructive Windows reproduction was performed.

The repository's `install.cmd` invokes `install.ps1`, then [source installation](/Users/tristan/Software/frame-compare/tools/windows_portable/install-from-source.ps1:154), which defaults to `dist/frame-compare-portable-win-x64` and unconditionally invokes the builder. [Builder Main](/Users/tristan/Software/frame-compare/tools/windows_portable/build_portable.ps1:1140) recursively removes an existing output directory before reading the manifest or successfully building its replacement.

That output is also the supported installed bundle root. [The bundled README](/Users/tristan/Software/frame-compare/tools/windows_portable/README.txt:22) permits bundle-local `config/config.toml`, media under `comparison_videos`, and default generated output under `generated`, and directs source-build users to this directory. Repeating source installation can therefore delete user config, clips, and results; a malformed manifest or later build failure leaves the old bundle erased. An arbitrary output path also reaches the same deletion logic.

Counterpoints matter: complete reinstalls are documented to use fresh folders, and external generated storage is recommended for data that must survive replacement. The maintainer build recipe may deliberately remove a disposable candidate. Those constraints do not guard the normal fixed-directory source-installer rerun. This finding concerns source/bootstrap/build replacement, not the installed code-only updater's treatment of user data. [Microsoft documents recursive removal behavior](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/remove-item?view=powershell-7.5).

Separate disposable build staging from installed and user-owned state. Build and validate a fresh candidate; refuse an occupied/live target by default, or choose a fresh versioned target and change the installed pointer only after successful validation. Decide explicit user-data migration behavior where replacement is intended. Do not infer which existing files are disposable or overlay incompatible runtimes to preserve them. Validate manifest and output/root/ancestor relationships before destructive operations.

Migrate source installer, builder destination handling, and relevant extracted-artifact/source-install tests together. Preserve existing signed-build, committed-source, runtime fingerprint, hash, license, inventory, and native-panel checks. Test existing bundle-local config/media/generated sentinels and the installed-state pointer; inject manifest/build failure and assert the existing installation remains byte-identical or the operation refuses before mutation. Also test repeat invocation and unsafe destination relationships on Windows. Fix safety first; a generic PowerShell abstraction or workflow redesign is unnecessary.

## CQ16 Support stable and RC application versions consistently

**Classification:** confirmed supported-version admission mismatch by source, S2 Medium, High confidence; Windows transition execution outstanding.

[Release inputs](/Users/tristan/Software/frame-compare/.github/workflows/release.yml:10) explicitly support repository versions such as `0.1.0rc1` and RC tags. [Update-package generation](/Users/tristan/Software/frame-compare/tools/windows_portable/build_update.ps1:258) preserves the raw target application version. The installed updater's [command-output extraction](/Users/tristan/Software/frame-compare/tools/windows_portable/shim/frame-compare-update.ps1:583) accepts only numeric dotted versions; its Python fallback returns raw `__version__`. [Range admission](/Users/tristan/Software/frame-compare/tools/windows_portable/shim/frame-compare-update.ps1:564) passes that value into `System.Version.Parse`, catches failure, and rejects it.

Microsoft's [Version.Parse contract](https://learn.microsoft.com/en-us/dotnet/api/system.version.parse?view=net-10.0) accepts numeric components; it does not accept Python RC suffixes. A compatible stable installation can receive an RC target but that installed RC cannot subsequently pass admission for RC2 or stable code-only updates. Full RC bundles have the same installed-version problem. This is fail-closed availability behavior, not unsafe version acceptance or a signature bypass. Current stable numeric versions retain their happy path.

Own the repository's constrained stable/RC grammar and ordering consistently across extraction, signed range generation/admission, and exact target smoke verification. Do not merely strip suffixes; explicitly define RC ordering and stable/RC range semantics. Reuse existing version helpers if they can own that contract without a new runtime dependency. A general versioning framework is unnecessary.

Extend signed apply behavior tests beyond existing numeric `1.0.0`/`1.0.1` fixtures: RC→RC, RC→stable, chosen stable→RC policy, signed range boundaries, malformed values, and exact target verification. Preserve runtime/dependency compatibility checks and signature authority. Exercise supported Windows PowerShell 5.1 and PowerShell 7 updater paths. Full-bundle reinstall remains a recovery alternative, not a reason to leave the advertised code-update transition broken.

## CQ17 Use a safe source replacement transaction for rollback

**Classification:** inferred reliability risk, S2 Medium, High confidence in mechanism and Medium confidence in occurrence.

[Restore-FromBackup](/Users/tristan/Software/frame-compare/tools/windows_portable/shim/frame-compare-update.ps1:631) removes current application source and then copies the backup directly into the final target. [Explicit rollback](/Users/tristan/Software/frame-compare/tools/windows_portable/shim/frame-compare-update.ps1:638) checks backup presence/compatibility, obtains the update lock, rechecks, and calls that helper. It has no staged completeness check, preserved current tree, post-restore smoke validation, or recovery transaction.

An unreadable or incomplete compatible backup, copy failure, interruption, or partially failing deletion can leave a missing/mixed application tree. The backup itself remains outside the removed target; the finding does not claim every recovery copy is lost. Locks and compatibility identity meaningfully mitigate concurrent-update and wrong-runtime failures, but do not make copying transactional.

The adjacent apply path already stages `.new`, retains `.old`, promotes by rename, smoke-checks, and attempts recovery. Consolidate source-tree replacement/recovery policy inside the updater: stage/validate the candidate, retain current code until commit, verify postconditions, recover on failure, and preserve diagnosable recovery material. Keep signed archive authentication/extraction separate. Capture enough backup manifest/version information to recognize incomplete candidates. Remove delete-then-copy restoration once callers use the transaction.

Retain successful rollback, invalid/incompatible-backup refusal, lock ownership, and purge serialization. Add failure observations at backup read/copy, promotion, smoke, and interruption boundaries while comparing current-tree snapshots. Existing happy-path rollback tests do not establish those failure guarantees. Actual Windows filesystem/process proof is required; source tests cannot establish transactional behavior. No attacker-controlled signature bypass was found.

## CQ18 Align doctor with the installed selected configuration

**Classification:** confirmed diagnostic selection defect by source, S3 Low, High confidence; installed-Windows observation outstanding.

[Doctor's TMDB config lookup](/Users/tristan/Software/frame-compare/src/frame_compare/orchestration/doctor_checks.py:620) resolves only the workspace's `config/config.toml`, then defaults. The [installed shim](/Users/tristan/Software/frame-compare/tools/windows_portable/shim/frame-compare.ps1:28) injects the selected bundle/AppData fallback config for run/wizard/preset/history but excludes doctor, and launches from the bundle directory.

With no bundle-local config and a retained AppData config containing `[tmdb] enabled=false`, installed execution disables TMDB while doctor reports that its API key is missing. Invalid retained config can likewise be hidden. Runtime dependency checks remain useful; this concerns the config-dependent diagnostic, not the entire doctor result.

Give config-dependent doctor checks the same selected-config resolution as installed execution. CQ8 is an opportunity to share selection authority without copying another fallback rule. Doctor currently has no public root/config arguments, so do not assume run flags can simply be injected into it. Choose a clear internal settings-selection seam, or explicitly justify a supported CLI change if one is necessary.

Retain environment precedence, local-only/no-HTTP doctor behavior, exact portable fallback containment, and runtime-free simple CLI paths. Extend doctor network/config tests and installed-shim fallback behavior with only AppData config present, compare doctor versus run settings, and include disabled/enabled/invalid config cases. The distinguishing Windows observation is the real installed shim producing a TMDB diagnostic consistent with its selected execution config.

## CQ19 Require finite operation timeouts

**Classification:** confirmed validation gap, S3 Low, High confidence; downstream transport/platform consequences vary.

The timeout fields at [screenshots](/Users/tristan/Software/frame-compare/src/frame_compare/config/schema_models.py:209), [slow.pics general/image upload](/Users/tristan/Software/frame-compare/src/frame_compare/config/schema_models.py:273), and [TMDB](/Users/tristan/Software/frame-compare/src/frame_compare/config/schema_models.py:323) have lower bounds but accept positive infinity. A bounded model-construction probe confirmed acceptance for all four. TOML can express infinity; defaults remain finite and this requires explicit abnormal input.

[Abortable subprocess execution](/Users/tristan/Software/frame-compare/src/frame_compare/utils/subproc.py:197) computes deadline/remaining time from the configured value. With infinity, automatic expiration never occurs, although cancellation still works. HTTP callers pass the value into their transport; no actual network/platform hang was asserted.

Reject nonfinite operation timeouts during config validation, retaining current minimum values. Extend existing timeout-minimum tests with nonfinite constructor/TOML/environment inputs and typed CLI/config errors where relevant. Keep the documented distinction between bounded external operations and uninterruptible already-admitted native work. This is a local validation correction; no new timeout framework is needed.

## CQ20 Fix document ownership in Node test fixtures

**Classification:** confirmed test-support defect, S3 Low, High confidence; no production focus failure follows from it.

[The viewer harness](/Users/tristan/Software/frame-compare/tests/services/viewer_state_harness.js:30) stores mutable `activeDocument`. Its element factory passes `domMechanics(() => activeDocument)` to every element, then each `loadViewer()` replaces that global. Earlier fixtures' focus/removal/replacement methods consequently act on the latest fixture's document. The harness also starts asynchronous scenario groups together.

A bounded memory-only probe loaded two viewers, focused the first viewer's Inspector button, and observed `firstDocumentOwnsFocus=false` and `secondDocumentOwnsForeignFocus=true`. It used the actual fixture/DOM mechanics through the locked Node runtime, without a browser or files. This demonstrates incorrect fake-document ownership and the potential for cross-fixture false observations.

Make element construction belong to each fixture and close over that fixture's document. Retain useful shared DOM mechanics; do not build a universal browser emulator. Prove that focus, removal, and replacement in two coexisting fixtures affect only their owning documents. Retain existing focus restoration, detached/stale callback, modal, keyboard, and actual-browser interaction cases. Coordinate this with CQ1/CQ7 tests so their new regressions do not inherit a misleading fixture.

## CQ21 Reduce test support coordination while preserving proof

**Classification:** subjective maintainability concerns, S3 Low, High confidence in the mechanisms. Fixture preparation cost was not benchmarked. Plan bounded work at each affected seam, not a suite-wide rewrite or test-count target.

### Keep one authoritative assertion per Node obligation

[The viewer's Python bridge](/Users/tristan/Software/frame-compare/tests/services/test_report_viewer_state.py:14) runs a large JavaScript harness whose scenarios already make substantive assertions against production assets. [Directional cases](/Users/tristan/Software/frame-compare/tests/services/viewer_state_harness.js:1408) then package fixed values/success markers into JSON that Python reasserts. Similar summary mirrors exist for Lens, Grid, and review state.

Changing a scenario can require updating its JS assertion, summary construction, and Python expected dictionary. Fixed success flags add little fault sensitivity; the single large invocation also obstructs focused scenario execution. The real JS assertions are meaningful, so these cases are not test theater or broadly redundant.

Retain the locked runtime, timeout, exit checking, pytest bridge, and actual behavioral assertions. Add a small named-scenario/selector interface if it improves focused execution; let the bridge check execution/completion without restating all observations. First map summary fields to real assertions and retain any genuinely separate external observation. Prove focused execution and clear failure reporting with a controlled deliberate violation, then restore it.

### Give U4 media recipes a focused owner and identity

[U4 preparation](/Users/tristan/Software/frame-compare/tests/integration/test_alignment_u4_acceptance.py:444) eagerly builds the whole media matrix. Its [session cache](/Users/tristan/Software/frame-compare/tests/integration/test_alignment_u4_acceptance.py:580) hashes the entire test module plus FFmpeg version, so an assertion-only edit invalidates every scenario's cached assets and a focused selection still generates the full matrix when cold.

Extract the deterministic media recipe into focused support and key actual producer inputs/dependencies. Consider demand generation with explicit shared prerequisites, while retaining full-matrix generation for the complete acceptance gate. Preserve codec/runtime identity, session-held lock, atomic publication, pruning isolation, serialization, and the existing lock-overlap test. Measure creation counts/preparation duration for one focused case, an assertion-only edit, and a real recipe edit before claiming a speedup. Do not weaken freshness just to retain a warm cache.

### Separate reusable alignment scenarios from collected tests

[Native panel tests](/Users/tristan/Software/frame-compare/tests/vsview/test_alignment_review_panel.py:56) import builders from collected evidence/frozen-string test modules. [One producer fixture](/Users/tristan/Software/frame-compare/tests/services/test_alignment_frozen_strings.py:595) invokes several private video-classification helpers before reaching presentation. An estimator-private refactor can therefore break a UI fixture before the UI obligation is exercised.

Use the existing [alignment review test support](/Users/tristan/Software/frame-compare/tests/alignment_review_test_support.py) or similarly focused support to own reusable coherent scenarios. Separate explicit presentation fixtures from producer→projection integration cases. Retain producer execution where it is the obligation, along with literal actionable text, zero/unavailable authority, evidence identity, ordering, compact/full projection, and persistence proof. Frozen strings often protect real product contracts; length alone is no deletion rationale.

### Replace incidental Windows source spelling checks when touching their owners

[Builder tests](/Users/tristan/Software/frame-compare/tests/windows_portable/test_windows_portable_build_scripts.py:2436) still assert helper names, local variables, and exact invocation spelling alongside real packaging obligations. Equivalent helper refactors can fail while retained expected strings do not prove correct execution. Existing bounded process/inventory cases demonstrate a stronger seam.

For CQ15–CQ17 and related edits, replace only incidental spelling checks with bounded executable fixtures or existing artifact observations. Preserve structural checks that actually establish entry wiring, forbidden payloads, source/runtime provenance, signature policy, package contents, and platform-specific distinctions. Do not remove a structural test merely because it reads source, and do not require Windows execution to prove an ordinary independent pure calculation.

## CQ22 Correct specific public documentation drift

**Classification:** confirmed documentation defects, S3 Low, High confidence. These are corrections to actual product/acceptance claims, not workflow redesign.

[The public doctor reference](../reference/commands.md#doctor) still says an optional slow.pics check contacts the service. The current source and CLI contract explicitly perform no HTTP and no slow.pics reachability check. Correct the reference so users do not treat doctor success as publishing-connectivity evidence.

[The no-cache reference](../reference/commands.md#run-no-cache) says analysis cache is neither read nor written; [Windows acceptance text](../media-runtime-windows-validation.md#application-caches) similarly expects no reusable cache persistence. Actual help and canonical contract define scoped refresh: preparation removes the matching entry, computation proceeds, and the replacement persists. Align both descriptions with that intended behavior. Existing media cache E2E covers regeneration; documentation corrections alone do not require another media run.

Also correct the dormant direct-call geometry claim as part of CQ12, and update ownership/payload/disclosure documentation with CQ8–CQ11. Keep specific narrative corrections with the change they explain. Do not turn missed prose into a new mandatory documentation framework or agent workflow.

## Finding classification and triage

Severity describes immediate risk, not architectural ambition. A broad maintenance refactor can deserve planning while remaining S3 because no current production failure was established. Confidence refers to the stated mechanism and evidence; source-confirmed behavior is not a claim of target-runtime acceptance.

| ID | Type | Severity | Confidence | Suggested triage |
| --- | --- | --- | --- | --- |
| CQ1 | confirmed defect | S2 Medium | High | Correct saved-state loss and own the transition |
| CQ2 | subjective maintainability concern | S3 Low | High | Complete authority/evidence ownership migration with strong retained proof |
| CQ3 | subjective maintainability concern | S3 Low | High | Coordinate with actual-transform facts and consumer migration |
| CQ4 | subjective maintainability concern | S3 Low | High | Remove the hidden identity contract and clarify selection ownership |
| CQ5 | subjective maintainability concern | S3 Low | High | Bounded independent policy consolidation |
| CQ6 | subjective maintainability concern | S3 Low | High | Integrate with selection/recovery ownership |
| CQ8 | confirmed defect | S2 Medium | High | Correct execution authority and delete duplicate preview policy |
| CQ9 | subjective maintainability concern | S3 Low | High | Intact request and owned acquisition, preserving lifecycle reads |
| CQ10 | confirmed defect | S2 Medium overall | High | Fix ordinary wrong-shape recovery first; decoder-limit siblings are S3 |
| CQ11 | confirmed defect | S2 Medium | High | Plan applied facts/schema identity before dependent render migration |
| CQ12 | subjective maintainability concern | S3 Low | High | Subtract dormant inference with obligation-mapped proof |
| CQ13 | subjective maintainability concern | S3 Low | High | Small producer-warning handoff correction |
| CQ15 | confirmed defect | S1 High | High | First safety correction; preserve existing user-owned state |
| CQ16 | confirmed defect | S2 Medium | High | Repair advertised RC update transitions |
| CQ17 | inferred risk | S2 Medium | Medium | Protect working code during failed/interrupted rollback |
| CQ18 | confirmed defect | S3 Low | High | Align installed diagnostics with selected config |
| CQ19 | confirmed defect | S3 Low | High | Local finite-timeout validation |
| CQ20 | confirmed defect | S3 Low | High | Repair fixture isolation before relying on new focus/state cases |
| CQ21 | subjective maintainability concern | S3 Low | High | Bounded support/fixture/assertion work alongside affected seams |
| CQ22 | confirmed defect | S3 Low | High | Correct specific public and acceptance descriptions |

The top safety risk is the source rebuild's treatment of an existing bundle. No additional exploitable secret exposure, arbitrary-code execution, or signature-bypass finding was established in inspected application/Windows boundaries. Regression risk is concentrated in authority/persistence, source/frame identity, actual transform facts, and lifecycle replacement. Verification has strong existing surfaces, but this report does not establish a hosted release, physical Windows, real browser, or native-media acceptance result at the reviewed SHA.

## Dimension notes and reviewed surfaces

| Dimension | Wide scan and deep evidence | Outcome and limits |
| --- | --- | --- |
| Architecture and ownership | All production owners/entry points inventoried; deep CLI→run→selection→alignment→render→report/publish traces; native-review activation→save→accept; import contracts checked | CQ2–CQ6, CQ8–CQ9, CQ11–CQ12 address concrete coordination. Existing domain independence, strict native contract, and focused service boundaries remain useful. |
| Correctness and failure modes | Config admission, decode boundaries, authority/zero/manual/cache states, rendering facts, viewer transitions, Windows apply/rollback/install, diagnostic config | CQ1, CQ8, CQ10–CQ11, CQ15–CQ20 are supported by source/probes with stated runtime gaps; CQ14/CQ17 remain inferred rather than observed native failure. |
| Maintainability and technical debt | Caller burdens, parallel records/maps, duplicate policy, dormant geometry, test-only/internal consumers, native panel/projection/evidence | Promoted scope removes demonstrated coordination. No blanket module splitting, helper removal, type hierarchy, async rewrite, or generic framework justified. |
| Tests and verification | All 278 test/support files inventoried; deep large/high-risk Node, frozen-text, U4, E2E, native panel, browser, Windows, process, inventory, and CI routes | CQ20–CQ21; alignment publication gaps recorded under CQ2. Strong distinct numeric, trust-boundary, actual media, resource, and browser proof must remain. Most small tests were inventoried rather than read line by line. |
| Security and privacy | Filename-first searches across runtime-sensitive files; deep paths/atomic locks, subprocess children, config redaction, HTML/script-safe payloads, sidecars, upload/webhook/DNS, signed archives | No new material exploit/exposure established. Recoverable decoder failures and finite bounds remain concrete corrections. Native codec internals and external services were not audited or attacked. |
| Build, packaging, release, supply chain | Manifests/lock/build entries/CI inventoried; Docker staged native provenance, source checkout, wheel/sdist verifier, immutable release requests, Windows builder/inventory/update authentication | CQ15–CQ17. Existing exact hashes/sizes, frozen graph, committed source, signed manifest, contained extraction, and extracted runtime checks materially reduce risk. No artifacts downloaded/built/published or dependency audit service queried. |
| Configuration and observability | Loader/overrides/persistence, preview/dry-run, logging, typed warning flow, doctor/history, optional publication, installed fallback selection | CQ8, CQ13, CQ18–CQ19, CQ22. Authored color explicitness and intentional post-run preference refresh remain valid. Successful JSON warning omission is an explicit contract, not a newly asserted defect. |
| Performance and concurrency | Streaming queues/stores, worker cancellation/drain, upload bounds, TMDB aggregation, per-clip scheduling, probe/index lifetimes, U4 preparation/cache scope | No new measured runtime-performance regression established. CQ21 identifies unmeasured preparation-cost mechanisms; CQ19 fixes unbounded abnormal timeout input. Native drain limits remain documented. |
| Documentation and developer experience | Current setup/install/journey/reference/guide/authority routes inventoried; deep first/repeat runs, Docker/Windows/native setup, doctor, history, cache, report/HDR/publishing descriptions | CQ22 and same-pass ownership/disclosure updates. Historical review/plan archives and all asset/legal text were not comprehensively revalidated. No agent-workflow maintenance proposed. |

Supporting executable code reviewed by the controller included Docker image source/provenance/dependency installation and final targets, Compose ownership/mounts, canonical integration verifier reservation/cleanup/result proof, optional GPU/GUI verifier entry and cleanup paths, bounded source checkout and atomic no-clobber publication, distribution metadata/archive/RECORD validation, release version/SHA/note validation, signing-key migration's bounded/sanitized secret transport, Docker host-target containment, and benchmark acquisition/output helpers. No additional material refactor was established in those sampled paths beyond migrating the affected config/metric interfaces into tool callers.

The native-review investigator read all production VSView files, full shared evidence/projection sources, all native-review test bodies, and representative service acceptance paths. No current authority, IPC, callback-lifecycle, or resource-leak defect emerged there. The fixed topology, small draft records, strict complete-set result contract, public callbacks, original-evidence projection, and dedicated child cleanup earn their current boundaries.

## Calibration and proposals not promoted

Independent targeted calibration inspected the consequential source for CQ8, CQ11, and CQ15–CQ17 and retained their classifications. It specifically rejected overclaims of observed GUI/JSON corruption, native pixel fidelity, signature bypass, or universal loss of every rollback recovery copy. The controller validated mechanisms, relevant callers, test routes, and counterpoints for the other promoted findings; subagent confidence alone was not treated as evidence.

The following investigated ideas do not create additional necessary standalone work:

- **Native panel session-model rewrite:** rejected as required scope. Readiness/save completeness and three saved-state fields could be locally consolidated into prepared typed decisions and the successfully written result during a future substantive panel change. Fixed activation topology and strict zips mitigate positional drift; adding a separate model today would add synchronization. This is an optional local simplification, not a hidden unfinished part of CQ2.
- **Manual/provisional preview precedence defect:** not promoted. A source difference exists between preview and panel presentation, but the service applies preexisting manual overrides before estimation and creates interactive authority after the sole launch. The suspicious envelope combination was not established as currently launched by production. Synthetic validity is not reachability.
- **Global authored/resolved configuration hierarchy:** not justified. Current explicit color fields have real persistence/preset meaning; CQ8's narrow simplifications must preserve it.
- **All warnings must appear in successful JSON or stderr:** rejected as a contract defect. A real producer→serializer probe showed omitted dropped-frame warnings, but current success JSON intentionally omits warning fields and only permits logs on stderr. Changing that behavior is a separate product decision, not permission for unsolicited schema expansion. CQ13 concerns a typed warning lost even from normal final outcomes.
- **Merge all parsing, cache, HTTP, or resource owners:** rejected. Probe/metric/TMDB updates, isolated webhook credentials/DNS/TLS, native draining, and bounded subprocess reaping have different obligations. Consolidate actual repeated policy without removing their trust/time boundaries.
- **Broad frozen-text/test pruning or missing-CI claims:** rejected. Many strings protect authority and diagnostic contracts. Linux static/package/browser, Docker media/resource, and Windows artifact/native proof routes exist; absent hosted results are not absent jobs. CQ21 targets demonstrated support duplication and incidental spelling only.
- **Rewrite source/index behavior to match preview:** rejected. Parent-owned source-index recovery and cache-free preview retry intentionally have different mutation authority.

This is the intended boundary of the current recommendation set: complete the twenty supported corrections/improvement groups and preserve healthy modules. CQ7/CQ14 are separate investigation candidates, not assumed implementation scope. A final integrated review should confirm those end states and deletion/proof obligations. It is a completion check, not a prescheduled second campaign of speculative refactors.

## Existing verification map

The following tests were inspected as existing carriers of meaningful obligations. Except for the explicit baseline ledger later in this report, this table does not claim that all listed tests ran during report preparation.

### Viewer state and image behavior

All paths in this table are rooted at `/Users/tristan/Software/frame-compare/`.

| Existing test or suite | Obligation relevant to the plan |
| --- | --- |
| `tests/services/test_report_viewer_state.py::test_viewer_state_harness_exercises_pair_scoped_alignment` | Pair-scoped storage/restoration, malformed-state fallback, pair switching, directional offsets, single-mode alignment, keyboard behavior, Blink pause combinations, Grid mode boundary, stale Diff commits |
| `tests/services/test_report_viewer_viewport.py::test_viewport_harness_owns_coordinate_and_alignment_policy` | Zoom/pan/fit/reveal, pointer anchoring, Grid unit conversion, directional offsets, persistence delegation |
| `tests/services/test_report_grid_view_state.py::test_grid_view_harness_proves_layout_paging_and_mount_limits` | Ordered paging, mount bounds, generation rejection, retry/recovery, normalized mixed-aspect viewport, focus and reference cues |
| `tests/services/test_report_lens_state.py::test_lens_harness_proves_mapping_behavior_comparison_and_storage` | Lens context mapping, persistence, stale clone callbacks, preserved sample context |
| `tests/browser/test_report_browser_smoke.py::test_generated_report_initializes_observable_mode_and_aria_state` | Production-generated report, responsive modes/source visibility, ARIA, Grid/Inspector integration |
| `tests/browser/test_report_browser_smoke.py::test_saved_fit_mode_is_reflected_by_fit_radios_on_page_load` | Real-browser reflection of persisted fit state |
| `tests/browser/test_report_browser_smoke.py::test_report_omits_fit_width_keeps_restored_state_reachable_and_h_toggles_labels` | Stored width-fit compatibility and keyboard reachability |
| `tests/browser/test_report_browser_smoke.py::test_blink_keeps_failed_image_retry_focused_across_timer_tick` | Blink timers preserve the focused retry interaction |

The harness names such as `canonicalStateShared` sometimes express current internal shape. Preserve their underlying single-authority/no-divergence obligation, not the literal incidental structure if the redesign changes it.

### Alignment authority and persistence

All paths in this table are rooted at `/Users/tristan/Software/frame-compare/`.

| Existing test or suite | Obligation relevant to the plan |
| --- | --- |
| `tests/services/test_alignment_workflow_vsview.py::test_confirmed_native_pair_replaces_computed_offset_and_persists_override` | Manual authority and persisted override replace the computed result appropriately |
| Same file: `test_manual_zero_preserves_rejected_attempt_and_diagnostic_digest` | Manual zero preserves the rejected original evidence and digest |
| Same file: `test_optional_native_review_retains_computed_offset`, `test_forced_missing_result_stops_alignment` | Optional keep-current versus forced missing-result semantics |
| `tests/orchestration/test_phase_alignment_contract.py::test_rejected_audio_attempt_survives_without_alignment_or_trim_authority`, `test_provisional_audio_candidate_cannot_reach_trim_authority`, `test_tampered_diagnostic_cannot_authorize_provisional_alignment_or_trims` | Rejected/provisional evidence and diagnostic tampering cannot authorize trims |
| `tests/services/test_alignment_previous_offsets.py::test_align_clips_from_request_always_reuses_shared_offsets_skips_compute_and_allows_vsview`, `test_align_clips_from_request_prompt_mode_auto_reuses_computed_offsets_without_prompt` | Shared computed reuse and prompt-policy distinctions |
| Same file: `test_align_clips_from_request_reuses_confirmed_offsets_skips_vsview`, `test_align_clips_from_request_prompt_no_uses_computed_fallback_for_confirmed_entry` | Confirmed reuse and declined-confirmation fallback |
| Same file: `test_align_clips_from_request_reuses_shared_offsets_for_unresolved_only_after_manual_override`, `test_align_clips_from_request_reconfirmed_manual_override_becomes_write_eligible` | Override precedence and current reconfirmation eligibility |
| `tests/services/test_alignment_reuse_cache.py::test_shared_cache_persists_confirmed_entry_while_shared_computed_stays_computed`, `test_shared_reuse_cache_round_trips_interactive_entry_with_computed_fallback` | Mixed cache origins and preserved computed fallback on disk |
| Same file: `test_incomplete_requested_source_set_is_not_written_or_reused`, `test_computed_this_run_provisional_result_is_not_write_eligible`, `test_computed_this_run_without_trusted_attempt_is_not_write_eligible` | Complete source sets and fresh computed authority requirements |
| Same file: `test_shared_reuse_cache_does_not_write_computed_entry_without_stability`, `test_shared_reuse_cache_does_not_write_ineligible_provenance` | Stability and forbidden-origin publication checks |
| Same file: `test_alignment_result_rejects_incomplete_or_nonfinite_authority`, `test_computed_result_requires_matching_current_time_but_cached_evidence_is_historical` | Accepted-offset validity and fresh/historical time distinction |
| Same file: `test_frozen_source_drift_rejects_primed_cache_and_write`; previous-offset suite: `test_confirmed_cache_reuse_rechecks_sources_before_early_return`; phase-contract suite: `test_optional_alignment_source_drift_stops_downstream_phases` | Source identity remains current at authority-use and publication boundaries |
| `tests/services/test_alignment_diagnostics.py::test_diagnostic_is_bounded_pathless_and_preserves_original_digest`, `test_failed_final_replacement_preserves_last_valid_snapshot` | Immutable bounded diagnostics and safe publication failure |
| `tests/services/test_alignment_cancellation.py` | Outer/repeated cancellation waits for owned cleanup and blocks later work/publication; cleanup failure remains authoritative |
| `tests/services/test_alignment_decision.py::test_v6_trusted_predicate_requires_each_conjunct`, `test_v6_reason_ordering_uses_the_plan_order`, `test_v6_reason_ordering_covers_video_terminal_reasons` | Independent acceptance gates and exact explanation ordering |
| Same file: `test_a4b_boundary_run_drives_trusted_or_provisional_video_outcome`, `test_decide_after_video_trusts_the_recounted_authority` | Recount and boundary classification feed the actual decision |
| `tests/services/test_alignment_video.py::test_tied_alternative_frames_block_through_video_and_decision`, `test_real_scoring_run_with_one_winning_position_stays_unresolved` | Real scoring behavior reaches the decision owner |
| `tests/integration/test_alignment_u4_acceptance.py::test_real_phase_v6_cache_matrix` | Real audio/video → phase → cache acceptance |

### Rendering and orchestration

All paths in this table are rooted at `/Users/tristan/Software/frame-compare/`.

| Existing test or suite | Obligation relevant to the plan |
| --- | --- |
| `tests/render/test_orchestrator_batch_screenshots.py::test_render_screenshots_from_batch_detailed_preserves_fact_slices_and_clip_mapping` | Per-clip exact-frame facts remain associated correctly, including unequal clip counts |
| `tests/render/test_orchestrator.py::test_render_batch_parallelizes_clip_units_but_serializes_each_clip`, `test_render_batch_parallel_overlaps_ffmpeg_groups_and_preserves_order_and_progress` | Work-unit concurrency, stable results/progress, per-clip native serialization |
| Same file: `test_clip_unit_failure_preserves_partial_serialized_progress_and_admission`, `test_render_batch_parallel_reports_lowest_request_index_failure`, `test_clip_workers_stop_before_next_frame_and_preserve_first_failure` | Partial results, failure precedence, stop-admission behavior |
| Same file: `test_ffmpeg_batch_stop_reaps_child_without_publishing_partial_results`, `test_real_sigint_stops_frame_admission_within_150ms` | Real subprocess cleanup/publication refusal and bounded admission after interrupt |
| `tests/render/test_expansion.py` | Source/selection mapping, actual prepared facts, frame bounds, output-filesystem aliases/collisions before preparation, cancellation admission |
| `tests/orchestration/test_phase_output_integration.py::test_output_phases_use_reselected_metric_metadata_after_real_initial_selection` | Aligned reselection metadata reaches rendering/reporting |
| Same file: `test_unresolved_comparison_remains_in_render_report_and_slowpics_membership` | Unresolved comparisons retain documented membership without gaining authority |
| `tests/orchestration/test_execution_phase_plan.py::test_build_execution_phase_plan_preserves_align_boundary_and_progress_total`, `test_analyze_retry_replaces_superseded_frame_plan_warnings` | Reporting boundary and warning replacement behavior |
| `tests/orchestration/test_phase_tasks.py::test_run_analyze_phase_confirmed_full_window_retry_recomputes_cache_domain`, `test_run_analyze_phase_full_window_retry_failure_does_not_prompt_twice` | Effective-domain/cache recomputation and retry-once behavior |
| Same file: `test_run_analyze_phase_refused_or_failed_prompt_is_fatal_without_retry`, `test_full_window_retry_progress_failure_is_fatal_before_override`, `test_full_window_retry_active_rect_sampling_failure_is_fatal` | Consent/progress/refinement failure remains fatal at the right point |
| Same file: `test_run_analyze_phase_cache_only_exclusion_failure_does_not_offer_retry`, `test_run_analyze_phase_cache_only_invalid_cache_does_not_recompute`, `test_empty_exclusion_window_uses_authoritative_window_recovery_once` | Cache-only refusal and empty-window recovery policy |
| Same file: `test_run_analyze_phase_maps_analysis_metrics_into_reference_domain` | Analysis-source and reference selection coordinates remain distinct |
| `tests/orchestration/test_active_rect_content.py::test_full_window_retry_can_recompute_content_derived_rect`, `test_full_window_retry_clears_stale_content_rect_when_full_window_has_no_crop` | Full-window replacement recomputes/removes content-derived rectangles correctly |
| `tests/cli/test_help_and_import.py`, `tests/cli/test_run_json_errors.py` | Import-time and machine-output obligations when affected paths reach the CLI |

## Package dependencies and integration considerations

The planning agent should choose final packages, but the following relationships are already supported:

- CQ15 is the first safety priority because an ordinary rebuild can delete a user-populated bundle. CQ1 is an independently actionable interaction defect. Neither requires the broad alignment/render redesign.
- CQ5 is a bounded policy cleanup that can precede CQ2. It does not require the resolution redesign.
- CQ6 shares selection/recovery files with CQ4. Either land typed classification first or integrate them under one owner; do not schedule conflicting edits independently.
- CQ3 changes render results consumed by phase rendering/report composition. CQ4 changes selection inputs consumed by phase rendering/alignment. Agree on those seams before parallel implementation; keep one integration owner.
- CQ2 can preserve the phase-facing ordered alignment result shape initially, allowing its internal redesign to remain independent from CQ4. Any temporary projection should have a concrete boundary purpose and an explicit final disposition.
- CQ20 repairs the viewer fixture used for CQ1 proof and any later CQ7 investigation. Land or integrate it before trusting new multi-fixture focus observations. CQ21's assertion-summary cleanup can share that test-support package without weakening behavioral assertions.
- CQ8 owns acquired run settings; CQ18 should reuse the selected-config policy rather than inventing a separate doctor fallback. Delete the preview override branch within the same migration. Coordinate CLI admission, programmatic runner, tool callers, and intentional post-run preference refresh.
- CQ9's metric request/acquisition owner and CQ4's selected-domain owner meet at Analyze and full-window recovery. Agree on domain identity and reacquisition boundaries before parallel edits. CQ10's metric decode fixes can land independently.
- CQ11's actual applied-transform facts must survive CQ3's structured clip results. CQ12 deletes dormant inference without moving live orchestration policy into render. A later CQ14 decision can use these facts, but no backend-resampling rewrite is required by this handoff.
- CQ15 and CQ17 need safe staging/replacement primitives, but source-build installation and authenticated code update remain different operations. Share only the replacement mechanics that genuinely have the same contract. CQ16 can develop independently after its stable/RC ordering is agreed, then integrate with apply/rollback acceptance tests.
- CQ10 and CQ19 are bounded validation corrections that need not wait for architectural migrations. CQ13's warning propagation is similarly independent, with CQ22 documentation corrections accompanying the relevant behavior rather than creating a workflow project.
- CQ21 contains several separate test-support seams. Assign only the subpart that belongs to the affected implementation; do not create one large test-suite rewrite or block all product corrections on it.
- The Docker verifier uses shared media-cache/pruning state. Do not overlap verifier runs in one checkout.

Potential coherent deliverables include Windows preservation/replacement and version handling; viewer transitions and fixture ownership; acquired configuration and doctor selection; persisted-input/timeout validation; actual transform facts and geometry disposition; alignment resolution/cache candidates and V6 policy; selection/domain/failure ownership; structured rendering and dormant-policy deletion; warning propagation; and the affected test/documentation seams. These are suggested boundaries, not a mandatory serial pipeline or a fixed commit count. Keep changes together where splitting would preserve invalid intermediate ownership or force temporary synchronization.

For each package, define the completed behavior, owner/interface decision, caller migration, deletion list, proof obligations, dependencies, and rollback scope. For internal migrations, atomic caller replacement is usually preferable to maintaining duplicate compatibility models. Persisted or independently consumed formats need explicit compatibility handling.

## Verification strategy for implementation planning

The [engineering runbook](../ENGINEERING_RUNBOOK.md#verification-policy) remains the command and gate authority. The existing full-verification route applies to behavior/ownership changes in the affected hotspots. Use focused tests while iterating and reuse valid integrated evidence; do not rerun unchanged gates merely because the next package begins.

The current full native route is:

```sh
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q -n4 --dist loadgroup
uv run --no-sync lint-imports --config importlinter.ini
```

Viewer changes also use the focused report suites through the locked Node runtime and actual browser proof where the interaction/DOM obligation changes:

```sh
uv run --no-sync pytest -q tests/services/test_report_viewer_state.py tests/services/test_report_viewer_viewport.py tests/services/test_report_grid_view_state.py tests/services/test_report_lens_state.py
uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py
```

Inspect skips and actual test observations. `REPORT_BROWSER` can select an installed Chrome/Chromium executable. Node state proof, generated markup, and browser interaction proof establish different claims. Viewer work alone does not require native-media acceptance.

For changes that alter native runtime behavior or media-tier observations such as selected frames, screenshots, alignment/cache behavior, or report payloads, use the applicable complete [Docker/runtime procedure](../ENGINEERING_RUNBOOK.md#docker-runtime-verification). The canonical command is:

```sh
bash tools/verify_docker_integration.sh
```

Pure calculation/serialization changes whose native execution contract stays unchanged use the applicable Python gate; select this based on the final changed obligation, not directory name alone. CQ3's scheduling/data migration and CQ2/CQ4 changes reaching real alignment/selection/cache behavior should receive explicit media-gate treatment in the plan. A focused `--pytest-path` run is development evidence, not a substitute for a required full gate.

Only if the implementation changes whole-track memory bounds, maximum admitted lag, or streaming-collector cleanup, add the separately owned resource proof described in the runbook. The canonical Docker gate excludes that module. Those internals are not required redesign targets here.

If a chosen change affects native-review IPC, Qt behavior, Windows-specific execution, packaging, or distribution, load its full applicable runbook procedure. Do not impose every release/platform gate on a pure internal calculation change, and do not claim Windows/visible Qt acceptance from source checks or Linux-container proof.

Update the architecture document when ownership changes. Update the CLI contract only when a corresponding supported contract changes. Do not create unrelated documents or tests to satisfy ceremony.

## Evidence actually obtained

The following checks and observations were obtained during report preparation against product source at `e036bc348431c948314019318d40f642c0923784`. The report was the only added file; these checks did not validate an implementation of the proposed changes.

| Command or observation | Actual result | Scope of claim |
| --- | --- | --- |
| `uv run --no-sync ruff check src/frame_compare` | Passed | Production Python lint selection; not a full-repository formatting check |
| `uv run --no-sync pyright --warnings` | Zero errors, warnings, or informations | Configured source/test static type analysis |
| `uv run --no-sync lint-imports --config importlinter.ini` | Both contracts kept; 182 files and 781 dependencies analyzed | Declared layer and sibling-domain independence rules |
| Focused pytest command below | 46 passed in 2.80 seconds | Alignment decisions, execution phase plan, cross-phase outputs, viewer-state and viewport harnesses |
| Appendix A probe, rerun by the viewer investigator and then executed directly from this report by the controller | Reproduced corruption for Diff and Blink; controller checked both observed state changes | State/persistence failure through existing fixture; the printed behavior is defective despite successful probe execution |
| `uv run --no-sync ruff check .` | Passed | Full configured repository lint selection |
| `uv run --no-sync ruff format --check .` | Passed; 511 files already formatted | Configured Python formatting; not a JavaScript/PowerShell formatter |
| `uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium` | Passed the configured gate; zero medium/high findings, 27 low findings; 40,177 lines scanned | Static security heuristic, with seven issues suppressed by specific annotations; not proof of absence of vulnerabilities |
| CQ8 temporary-config acquisition probe | JSON admission passed with native review disabled; a subsequent real preparation read saw it enabled while the CLI snapshot remained false; revalidation against runtime settings rejected that combination | Two real config reads can disagree. No GUI launch or contaminated JSON was observed |
| CQ10 actual metric reader probe, Appendix B | Valid control hit; list/dict enum values escaped as `TypeError`; invalid string recovered as `corrupted` | Malformed valid JSON bypasses intended cache-recovery classification |
| CQ10 decoder-limit probe, Appendix C | Deep JSON/TOML escaped as `RecursionError`; overlong JSON/TMDB integers escaped as `ValueError`; history already recovered the integer error | Python 3.13.16 decoder behavior delivered through memory-backed filesystem seams; no file discovery/containment acceptance claim |
| CQ11 production policy with mocked native clip/plugin graph | Requested Spline fell back to the expression path while overlay/report settings still described Spline | Actual Python branch and fact propagation; no native pixel or image-fidelity measurement |
| CQ13 successful publish/output/history probe with mocked transport | One mismatch log, successful URL, zero final warnings, zero recorded warnings | Production warning propagation owners; no HTTP request or remote service acceptance |
| CQ19 configuration models, Appendix C | All four timeout fields accepted positive infinity | Configuration validation observation; no actual HTTP/subprocess hang was induced |
| CQ20 existing Node fixture, Appendix D | Focusing the first fixture's button changed the second fixture's active element | Test-support ownership defect; not a production browser focus defect |
| Windows source-build, version, and rollback traces, independently calibrated | CQ15/CQ16 source mechanisms confirmed; CQ17 failure mechanism retained as an inferred risk | No destructive installer/update/rollback operation was executed; no physical Windows acceptance |

The exact focused baseline command was:

```sh
uv run --no-sync pytest -o addopts='' -q tests/services/test_alignment_decision.py tests/orchestration/test_execution_phase_plan.py tests/orchestration/test_phase_output_integration.py tests/services/test_report_viewer_state.py tests/services/test_report_viewer_viewport.py
```

No full native suite, current real-browser acceptance, Docker media gate, Windows acceptance, or new performance benchmark was run for this report. The listed focused passes establish useful baseline behavior but do not close those implementation-time obligations.

## Sound designs and proposals to avoid

The assessment found useful designs worth preserving:

- The centralized automatic-alignment decision owner, evidence parser/projection, accepted-versus-unavailable offset checks, and immutable operation outcome already protect important invariants.
- Native/persisted input validation, source-currentness checks, atomic writers, and explicit persistence boundaries guard distinct risks. Their repetition at separate trust/time boundaries is not automatically duplicate policy.
- Main-task cancellation versus worker stop admission is intentional. Resource-specific native and subprocess lifetime handling is earned complexity.
- `DefaultVSLoader` is already a comprehensible resource owner. No loader rewrite was justified.
- Report `ReviewState` already has a bounded private model, report identity checks, copied records, revision-bound preview, and explicit transactional apply/persistence semantics. Use it as evidence that a focused state owner can work; do not route unrelated viewer state through it.
- `ViewerFormat` is a useful dependency-light formatting owner. Python report payload validation and identity shaping also have appropriate boundaries.

No evidence from this assessment supports a blanket TypeScript/framework migration, all-async rendering, a generic state machine/DI/plugin framework, a universal cache abstraction, a global error rewrite, indiscriminate dataclass conversion, new lint rules as the main remedy, file-size-driven splitting, test-count goals, broad comment deletion, or dependency upgrades for their own sake.

Do not reinterpret “all worthwhile changes” as permission to refactor every reviewed module. It means complete the twenty supported groups. Keep CQ7/CQ14 in the separate investigation handoff until distinguishing evidence supports a decision. Additional discoveries should carry their own caller trace, mechanism, benefit, and verification requirement before expanding the plan.

## Required output from the planning agent

Produce a complete implementation plan covering CQ1–CQ6, CQ8–CQ13, and CQ15–CQ22. Keep CQ7/CQ14 in their separate investigation report; do not assume either results in a refactor or make their completion a prerequisite for these supported changes. Include every CQ21 subpart, grouped with its affected owner where that avoids a separate project. For every item:

1. State the observed problem and intended final behavior or caller simplification.
2. Choose the owner/interface and explain the decisive tradeoff against the credible smaller alternative.
3. Name affected callers, data shapes, serialized contracts, and obsolete paths to delete.
4. Define coherent packages and real dependencies, with safe opportunities for parallel work and shared-resource constraints.
5. Map behavioral obligations to retained tests, strengthened observations, and any missing regression case.
6. Specify native/browser/platform evidence based on the actual changed contract, preserving unavailable acceptance as an explicit remaining obligation.
7. Identify rollback scope and compatibility requirements. Avoid unnecessary migration layers for internal callers that can change together.
8. Give measurable completion criteria such as removed synchronization protocols, one authoritative policy evaluation, preserved outputs, and observed failure-path behavior. Do not substitute line-count or test-count targets.

The remaining design questions are bounded: CQ1 transition function versus a focused model; CQ2 existing record consolidation versus useful accepted/unresolved variants and cache-candidate ownership; CQ3 grouping/serializer boundaries; CQ4 selection/domain bundle scope; CQ6 failure-kind representation; CQ8 acquisition location and direct-caller migration; CQ9 required-cache result/failure interface; CQ11 per-clip applied-transform facts and serialized identity compatibility; CQ15 occupied-destination behavior and user-data preservation; CQ16 constrained stable/RC grammar and ordering; CQ17 reusable replacement/recovery transaction; and the specific CQ21 fixture boundaries. Resolve these from the traced callers and constraints. Do not reopen healthy modules merely to make the plan larger.

The maintainer requested this report as planning input. Creating it does not request implementation, deployment, release, external communication, or a new Codex chat. Use the repository's current planning/handoff lifecycle if a durable active implementation plan is subsequently created.

## Appendix A Reproduce viewer pair offset corruption

Run from `/Users/tristan/Software/frame-compare` with the existing environment. This command reads the existing fixture and injects a bounded probe in memory; it does not modify the fixture or product source.

```sh
uv run --no-sync python - <<'PY'
import json
from pathlib import Path

from nodejs_wheel import node

harness = Path("tests/services/viewer_state_harness.js").resolve()
probe = r'''
for (const targetMode of ['diff', 'blink']) {
    const { viewer, storage, storageKey } = loadViewer({ clipCount: 2 });
    viewer.viewport.setManualAlignment(7, 3);
    viewer.setMode('slider');
    viewer.setRightClip(0);
    const before = {
        pair: viewer.viewport.currentPairAlignmentKey(),
        savedOriginal: {...viewer.state.pairAlignments['0:1']},
    };
    viewer.setMode(targetMode);
    console.log(JSON.stringify({
        targetMode,
        before,
        after: {
            pair: viewer.viewport.currentPairAlignmentKey(),
            current: [viewer.state.alignX, viewer.state.alignY],
            persistedOriginal: persisted(storage, storageKey).pairAlignments['0:1'],
        },
    }));
}
'''
source = harness.read_text().split("const summary = {};")[0] + probe
script = (
    "const Module=require('node:module');"
    f"const m=new Module({json.dumps(str(harness))});"
    f"m.filename={json.dumps(str(harness))};m.paths=module.paths;"
    f"m._compile({json.dumps(source)},m.filename);"
)
result = node(
    ["-e", script],
    return_completed_process=True,
    capture_output=True,
    encoding="utf-8",
    timeout=10,
)
print(result.stdout, end="")
print(result.stderr, end="")
raise SystemExit(result.returncode)
PY
```

At the verified revision, each target mode produces the following state change, with `targetMode` set to `diff` or `blink`:

```json
{
  "before": {
    "pair": "0:0",
    "savedOriginal": {"alignmentPreset": "custom", "alignX": 7, "alignY": 3}
  },
  "after": {
    "pair": "0:1",
    "current": [0, 0],
    "persistedOriginal": {"alignmentPreset": "none", "alignX": 0, "alignY": 0}
  }
}
```

For a durable regression, assert the expected restored `(7,3)` current and persisted offset through the repository's existing test route. This exploratory command deliberately prints the observed bug and exits successfully when the probe executes; its exit code is not a correctness assertion.

## Appendix B Reproduce malformed metric enum recovery failure

Run from the repository root. This uses the actual cache reader and an existing valid metadata builder, with memory-backed delivery replacing filesystem discovery/opening. It does not modify a cache or exercise filesystem containment. The assertions describe the observed defect at the reviewed revision; after the correction, the list/dict cases should recover as `corrupted` rather than escape.

```sh
.venv/bin/python -B - <<'PY'
import io
import json
from pathlib import Path
from unittest.mock import patch

from frame_compare.analysis import cache_io
from frame_compare.config.schema import AnalysisConfig
from tests.analysis._cache_io_test_helpers import valid_cache_metadata_payload

cases = [
    (None, None, 'hit'),
    ('active_rect_source', [], 'TypeError'),
    ('active_rect_detection_mode', {}, 'TypeError'),
    ('active_rect_source', 'invalid', 'corrupted'),
]
for field, value, expected in cases:
    metadata = valid_cache_metadata_payload(AnalysisConfig(), frame_count=1)
    if field is not None:
        metadata[field] = value
    payload = {
        'version': cache_io.CACHE_VERSION,
        'fingerprint': 'fp',
        'luminance': [0.1],
        'motion': [0.0],
        'sampled_source_frames': None,
        'metadata': metadata,
    }
    with (
        patch.object(cache_io, 'find_metrics_cache_file', return_value=Path('synthetic.compframes')),
        patch.object(Path, 'exists', return_value=True),
        patch.object(Path, 'open', return_value=io.StringIO(json.dumps(payload))),
    ):
        try:
            result = cache_io.load_cached_metrics(Path('.'), 'fp')
            observed = 'hit' if result.success else result.reason
        except TypeError as error:
            observed = type(error).__name__
        assert observed == expected, (field, observed, expected)
        print(f'{field or "valid control"}: {type(value).__name__} => {observed}')
PY
```

The valid control hits, both container-valued enum fields raise `TypeError`, and an invalid string returns `corrupted`. Durable proof should also follow the corrected result into ordinary recomputation and cache-only refusal, preserving their distinct contracts.

## Appendix C Observe decoder limits and nonfinite timeout admission

This bounded probe sends small pathological serialized values through the actual parsers while replacing filesystem delivery. It prints observations rather than asserting cross-version decoder internals. On Python 3.13.16 with integer limit 4,300, the deep JSON and TOML cases escaped as `RecursionError`; overlong JSON and TMDB integers escaped as `ValueError`. History recovered the integer failure as an unavailable entry but allowed the recursion failure to escape. The four model fields accepted `inf`.

No process/network timeout was exercised, and no optional-review GUI or persisted file was created. The unobserved sibling readers listed in CQ10 still need their own owner-specific cases; analogous catch clauses alone do not establish identical runtime behavior.

```sh
.venv/bin/python -B - <<'PY'
import io
import sys
from pathlib import Path
from unittest.mock import patch

from frame_compare.analysis import cache_io
from frame_compare.config.schema_models import ScreenshotsConfig, SlowpicsConfig, TmdbConfig
from frame_compare.services import run_result_record as history
from frame_compare.services.tmdb_cache import TmdbCache
from frame_compare.vsview import alignment_review_contract as ipc

print('Python', sys.version.split()[0], 'integer limit', sys.get_int_max_str_digits())
session = ipc.AlignmentReviewSession(
    Path('/unused/script.py'), Path('/unused'),
    '12345678123456781234567812345678', Path('/unused/result.json'),
)
for name, raw in [
    ('deep', '[' * 10000 + '0' + ']' * 10000),
    ('large_int', '1' * 5000),
]:
    with patch.object(ipc, '_validate_session_paths'), patch.object(Path, 'read_text', return_value=raw):
        try:
            ipc.read_alignment_review_result(session, ())
            result = 'accepted'
        except Exception as error:
            result = type(error).__name__
        print('VSView', name, result)
    with (
        patch.object(cache_io, 'find_metrics_cache_file', return_value=Path('/unused/cache.compframes')),
        patch.object(Path, 'exists', return_value=True),
        patch.object(Path, 'open', return_value=io.StringIO(raw)),
    ):
        try:
            result = cache_io.load_cached_metrics(Path('/unused'), 'a' * 40).reason
        except Exception as error:
            result = type(error).__name__
        print('metrics', name, result)
for name, raw in [
    ('deep', 'entries = ' + '{a=' * 1500 + '0' + '}' * 1500),
    ('large_int', 'value = ' + '1' * 5000),
]:
    with patch.object(Path, 'open', return_value=io.BytesIO(raw.encode())):
        try:
            result = TmdbCache(Path('/unused/tmdb.toml')).get_search(
                'https://api.example.test/search/movie', {},
            )
        except Exception as error:
            result = type(error).__name__
        print('TMDB', name, result)
    with (
        patch.object(Path, 'lstat'),
        patch.object(history, '_contained_regular_file', side_effect=lambda path, _: path),
        patch.object(Path, 'open', return_value=io.BytesIO(raw.encode())),
    ):
        try:
            entry = history._history_entry(Path('/unused/run'))
            result = None if entry is None else entry.status
        except Exception as error:
            result = type(error).__name__
        print('history', name, result)
for model, field in [
    (ScreenshotsConfig, 'ffmpeg_timeout_seconds'),
    (SlowpicsConfig, 'timeout_seconds'),
    (SlowpicsConfig, 'image_upload_timeout_seconds'),
    (TmdbConfig, 'timeout_seconds'),
]:
    value = model(**{field: float('inf')})
    print(f'{model.__name__}.{field} accepted:', getattr(value, field))
PY
```

The broad exception handlers here belong only to an exploratory observation command. They are not a proposed product error policy. Product normalization should occur at the narrow decoder owner and preserve each caller's typed recovery/failure behavior.

## Appendix D Reproduce Node fixture document contamination

This loads the existing fixture twice and focuses a button belonging to the first instance. The command compiles a memory-only prefix of the harness; it neither changes the harness nor loads a real browser.

```sh
uv run --no-sync python - <<'PY'
import json
from pathlib import Path

from nodejs_wheel import node

harness = Path('tests/services/viewer_state_harness.js').resolve()
probe = r'''
const first = loadViewer({clipCount: 2});
const second = loadViewer({clipCount: 2});
first.viewer.dom.btnInspector.focus();
const observed = {
    firstDocumentOwnsFocus: first.document.activeElement === first.viewer.dom.btnInspector,
    secondDocumentOwnsForeignFocus: second.document.activeElement === first.viewer.dom.btnInspector,
};
assert.equal(observed.firstDocumentOwnsFocus, false);
assert.equal(observed.secondDocumentOwnsForeignFocus, true);
console.log(JSON.stringify(observed));
'''
source = harness.read_text().split('const summary = {};')[0] + probe
script = (
    "const Module=require('node:module');"
    f'const m=new Module({json.dumps(str(harness))});'
    f'm.filename={json.dumps(str(harness))};m.paths=module.paths;'
    f'm._compile({json.dumps(source)},m.filename);'
)
result = node(
    ['-e', script],
    return_completed_process=True,
    capture_output=True,
    encoding='utf-8',
    timeout=10,
)
print(result.stdout, end='')
print(result.stderr, end='')
raise SystemExit(result.returncode)
PY
```

Observed output is `{"firstDocumentOwnsFocus":false,"secondDocumentOwnsForeignFocus":true}`. A durable regression must assert the corrected isolation instead of retaining these defect assertions. Real-browser focus behavior remains a separate obligation.
