Status: Historical
Scope: Redesign VSPreview manual alignment around untrimmed source-frame matching and computed absolute offsets
Owner: Next Codex cleanup-loop session
Closed: 2026-05-30

# VSPreview Source-Frame Alignment Plan

Archived: historical context only. Do not treat this document as current
execution authority. Imperative language below is preserved only as historical
acceptance criteria for the completed workstream.

## Closeout Notes

- Implemented the approved option-3 flow.
- Full runbook verification passed on 2026-05-30.
- A non-interactive generated-session smoke loaded temporary FFmpeg clips through
  VapourSynth and confirmed the generated session reports untrimmed source
  outputs with audio hints only.
- Missing proof: a human-driven VSPreview GUI/manual alignment run was not
  performed in this session, so positive/negative real GUI confirmation remains
  a manual runtime proof gap.

## Purpose

This historical plan captured the intended `frame-compare-cleanup-loop`
workflow for redesigning the VSPreview manual alignment flow around option 3.

Historical handoff context: the original workflow expected the next session's
main agent to act as orchestrator, keep live state in `update_plan`, and
delegate planning validation, implementation, and review work through the
cleanup-loop workflow. That context is informational only now that the
workstream is closed.

## Task Family and Risk Tier

- Task family: high-risk cleanup/remediation of interactive VSPreview alignment
  behavior
- Runbook tier: High

Why high risk:

- The work changes runtime VSPreview behavior and manual alignment semantics.
- `src/frame_compare/services/alignment.py` is a current hotspot.
- The work touches a user-facing interactive flow that persists run-scoped
  manual override state.
- Correctness depends on preserving signed frame-offset semantics across
  audio estimation, VSPreview, manual confirmation, cache, and orchestration
  trim normalization.

## Current State

The present design is confusing because three domains are mixed in the user's
mental model:

1. VSPreview pre-applies trim normalization and suggestion-derived preview math.
   The generated session uses `calculate_alignment_trims()` and trims the
   reference/comparison clips before the user inspects them.
2. Terminal confirmation still expects the final signed absolute offset that
   will be saved to `manual_overrides.toml` and applied by the pipeline.
3. Observed preview deltas are therefore not obviously translatable into saved
   offsets. The user sees a preview that has already consumed the suggestion,
   then must enter a final offset in the unnormalized alignment contract.

The target is to remove that inversion. VSPreview should show base/untrimmed
source clips, the audio-derived offset should be a hint only, and the user
should identify matching source frames directly.

## Baselines To Preserve

Do not regress the already-landed fixes below while changing the manual flow:

- Exact FFmpeg frame extraction and average-FPS alignment baseline from
  `4bf97fc fix(alignment): extract exact frames and use average fps`.
- VSPreview parity fixes already landed, especially loader/bootstrap and
  pipeline-parity behavior from `4199996 fix(vspreview): normalize preview offsets against pipeline trims`.
- Audio stream selection and alignment cache hardening from
  `e799547 fix(alignment): select matching audio streams and harden cache`.
- Mixed-FPS fail-fast behavior from
  `155a208 fix(orchestration): reject mixed-fps runs during prep`.

The new design may intentionally replace suggestion-applied VSPreview trims, but
it must not undo the safer loader resolution, path bootstrapping, stream
selection, cache validation, or mixed-FPS rejection guarantees.

## Decision: Option 3 Over Option 2

Chosen: option 3, source-frame matching in an untrimmed VSPreview session.

Option 2 is treated as "keep a suggestion-normalized preview, then improve
terminal wording or offset adjustment around it." That would preserve most of
the current implementation but still requires users to reason across two
domains: preview-relative positions and final absolute offsets.

Option 3 is better for implementation and support because it creates one stable
contract:

- VSPreview displays untrimmed source-frame domains.
- The suggestion is only a hint.
- The user records the matching reference source frame and comparison source
  frame.
- Frame Compare computes the persisted offset as:

```text
final_frame_offset = reference_source_frame - comparison_source_frame
```

That formula matches the current signed convention: positive offsets trim the
reference, negative offsets trim the comparison. It also keeps the audio
estimator and downstream trim normalization as consumers of a final offset,
instead of making them owners of interactive preview semantics.
The persisted value remains the existing comparison-relative-to-reference
offset contract consumed by the downstream trim pipeline.

## Approved Scope

Implement the option-3 manual alignment flow:

1. Generate VSPreview scripts that load and display base/untrimmed source clips.
2. Remove suggestion-derived trim normalization from the generated VSPreview
   manual alignment session.
3. Present audio-derived offsets as hints only.
4. Ask the user for matching source-frame positions after VSPreview inspection.
5. Compute the final signed absolute offset from the source-frame pair using
   `reference_source_frame - comparison_source_frame`.
6. Persist and apply the computed final offset through the existing manual
   override and alignment result path.
7. Preserve public CLI/config behavior unless a stop-and-replan trigger fires.

## Explicit Non-Goals

Out of scope unless a stop-and-replan trigger fires and the maintainer approves:

- changing audio cross-correlation or stream-selection policy
- changing alignment cache file schema or compatibility policy
- changing `manual_overrides.toml` schema or version
- adding CLI flags, config knobs, or JSON output
- supporting mixed-FPS manual alignment by bypassing the new fail-fast behavior
- changing render/output frame-number semantics
- changing Windows portable, Docker, release packaging, or installer behavior
- general VSPreview UI feature work outside manual alignment verification
- general refactors of orchestration phase ordering

## Required Invariants

The implementation must preserve these invariants:

1. Existing signed offset semantics remain unchanged:
   `offset = reference_source_frame - comparison_source_frame`.
2. Existing downstream trim normalization remains the pipeline owner after a
   final offset is known.
3. `manual_overrides.toml` continues to store `frame_offset` as the final signed
   comparison-relative-to-reference frame offset.
4. Audio-derived offsets remain suggestions/hints for the manual flow. They must
   not be pre-applied to the VSPreview clips.
5. Optional VSPreview still degrades to computed/cached/manual offsets when it
   cannot launch. Forced interactive mode must keep fail-fast behavior when
   VSPreview or a terminal is unavailable.
6. Duplicate stem validation, cache hardening, selected audio stream matching,
   and mixed-FPS rejection remain intact.
7. CLI command names, flags, JSON mode behavior, config persistence, and public
   config schema remain unchanged.
8. Source-frame prompts must be explicit about the frame domain and sign
   convention. Do not rely on users mentally inverting preview-applied trims.
9. No new broad import dependency should be introduced across
   `services`, `vspreview`, `orchestration`, or `vs` layers.

## Owner Seams

Prefer existing owners. Do not create a new top-level package or cross-layer
facade for this work.

Primary owners likely in scope:

- `src/frame_compare/vspreview/session_script.py`
  - Owns generated VSPreview session behavior.
  - Should become the owner of untrimmed source-domain preview output and hint
    display text.
- `src/frame_compare/services/alignment_vspreview.py`
  - Owns launch policy, terminal confirmation, source-frame input validation,
    final offset computation, and manual override save calls.
- `src/frame_compare/services/alignment.py`
  - Owns integration of confirmed VSPreview offsets into `AlignmentResult`.
  - Keep this file narrow; do not move prompt or generated-script policy here.
- `src/frame_compare/services/alignment_math.py`
  - Optional owner for a tiny pure helper if centralizing the source-frame
    offset formula materially improves testability.
- `src/frame_compare/vspreview/overrides.py`
  - In scope only to preserve existing schema/read-write behavior or update
    tests around persisted values. Avoid schema changes.

Secondary owners only if required:

- `src/frame_compare/orchestration/phase_tasks.py`
  - Only if implementation discovers an existing orchestration handoff is
    misusing confirmed offsets. Do not use this as the primary owner.
- `docs/current-architecture.md`
  - Update only if owner seams or runtime ownership meaningfully change.
- `docs/current-cli-contract.md`
  - Update only if a stop-and-replan decision explicitly changes public
    CLI/config behavior.

Tests likely in scope:

- `tests/vspreview/test_adapter.py`
- `tests/services/test_alignment_vspreview.py`
- `tests/services/test_alignment_workflow_vspreview.py`
- `tests/services/test_alignment_workflow.py`
- `tests/vspreview/test_overrides_load.py`
- `tests/vspreview/test_overrides_save.py`
- `tests/vspreview/test_overrides_precedence.py`
- `tests/orchestration/test_phase_tasks_alignment.py`

## Files Out Of Scope By Default

- `src/frame_compare/services/alignment_audio.py`
- `src/frame_compare/services/alignment_cache.py`
- `src/frame_compare/render/**`
- `src/frame_compare/vs/**`
- `src/frame_compare/config/**`
- `src/frame_compare/cli/entry.py`
- `src/frame_compare/cli/output.py`
- `src/frame_compare/orchestration/preparation.py`
- `tools/windows_portable/**`
- `.github/workflows/**`
- `Dockerfile`
- `docker-compose.yml`

## Approved Behavioral Contract

### VSPreview Session

- Generated sessions must load the reference and comparison clips untrimmed.
- The generated session must not call `calculate_alignment_trims()` to align the
  preview outputs.
- The generated session must not use `OFFSET_MAP` edits as the primary manual
  alignment mechanism.
- Each comparison output should still include clear labels and the audio hint,
  for example the suggested signed offset and one example matching pair implied
  by the hint.
- Output ordering must remain predictable: reference/comparison pairs by sorted
  comparison stem unless the existing adapter contract says otherwise.
- Keep the safe text stream handling and `resolve_lwlibavsource()` fallback
  behavior.

### Terminal Confirmation

- Confirmation must collect matching source-frame positions for each comparison.
- The accepted data contract is two non-negative integer source frame indices:
  one reference frame and one comparison frame.
- The computed final offset is
  `reference_source_frame - comparison_source_frame`.
- `skip` or `s` must keep the current computed/cached/manual offsets and must not
  write a new manual override.
- A blank response must not silently persist the suggestion as a manual override
  unless the cleanup-loop session first stops and replans that behavior with
  explicit maintainer approval.
- Invalid frame-pair input must re-prompt with a concise explanation. Do not
  accept floats, booleans, negative frames, or partial pairs.

### Persistence and Application

- Persist only the computed final signed offset using the existing
  `ManualOverride.frame_offset` field.
- `align_clips()` should continue to return `AlignmentResult.source == "manual"`
  for confirmed VSPreview overrides.
- Do not change cache precedence: manual overrides first, then cached offsets,
  then computed offsets, with VSPreview confirmation able to replace the
  current result only after explicit source-frame confirmation.

## Execution Units

The cleanup-loop orchestrator should execute these units one at a time, with a
review/adjudication loop after each unit or paired low-risk unit.

### Unit 1: Validate Plan and Current Code

Target:

- Load this active plan, `AGENTS.md`, the runbook, current architecture, current
  CLI contract, `importlinter.ini`, and relevant boundary skills.
- Confirm the baseline commits and current tests still match this plan.

Must prove:

- The current generated script still pre-applies suggestion-derived trim
  normalization.
- The current prompt still accepts final signed offsets directly.
- No newer code has already implemented option 3.

### Unit 2: Redesign Generated VSPreview Session

Target:

- Change `session_script.py` so the alignment session displays untrimmed source
  clips and hint text only.
- Remove the preview-time dependency on pipeline trim normalization for manual
  alignment inspection.

Must prove:

- Generated script content no longer imports or calls
  `calculate_alignment_trims()` for the manual alignment session.
- Generated script execution in tests sets predictable outputs without slicing
  source clips by suggested offsets.
- Existing bootstrap, path escaping, stream reconfiguration, and loader fallback
  tests remain meaningful.

### Unit 3: Redesign Confirmation Prompt

Target:

- Replace direct final-offset entry with source-frame pair entry in
  `alignment_vspreview.py`.
- Compute the final offset from the source-frame pair.
- Preserve `skip` semantics and forced/optional launch behavior.

Must prove:

- Input pair `reference=120`, `comparison=108` persists/applies `+12`.
- Input pair `reference=108`, `comparison=120` persists/applies `-12`.
- Blank and malformed input do not accidentally save a manual override.
- Prompt text names source-frame domain and the signed formula.

### Unit 4: Preserve Alignment Integration

Target:

- Keep `alignment.py` as a consumer of confirmed final offsets.
- Avoid changing the estimator path except for adapting to a renamed/typed return
  value if the prompt owner needs one.

Must prove:

- Cached or computed suggestions still launch VSPreview as hints.
- Confirmed source-frame pairs override the current result as manual offsets.
- Optional VSPreview unavailable/launch-failed paths keep current degraded
  behavior.
- Forced interactive unavailable/no-TTY paths still fail fast.

### Unit 5: Verification and Documentation Closeout

Target:

- Run the focused and full verification below.
- Update authority docs only if a stop-and-replan-approved public or ownership
  change occurred.
- Mark this plan historical only when implementation and verification are
  complete.

Must prove:

- Public CLI/config behavior is unchanged.
- Runtime/manual proof gaps, if any, are recorded explicitly.

## Verification Strategy

Primary verification mode:

- `contract-first` for manual persisted offset semantics
- `integration-ops` for generated VSPreview/runtime behavior

Required plan classification:

- `new regression/contract test required`
- `broader integration/manual proof required`

Why this depth matches the risk:

- The core risk is semantic: a user-entered alignment must persist the same
  final signed offset that downstream trim normalization expects.
- Unit tests are needed for formula, prompt, persistence, and generated script
  content.
- Manual/runtime proof is needed because VSPreview usability depends on a real
  VapourSynth/VSPreview environment that unit tests can only approximate.

### Proof Surface Classification

| Surface | Classification | Required proof |
| --- | --- | --- |
| Source-frame offset formula | new regression/contract test required | Positive, negative, zero, invalid, and malformed source-frame pairs |
| Terminal prompt semantics | new regression/contract test required | `skip`, EOF/no input, blank, invalid, and valid pair behavior |
| Manual override persistence | new regression/contract test required | Existing schema stores computed final `frame_offset` |
| Generated VSPreview script behavior | new regression/contract test required | Script content and fake-runtime execution show untrimmed outputs and hint-only suggestions |
| Optional/forced launch policy | existing coverage sufficient plus targeted updates | Existing availability/no-TTY/launch-failure tests continue to pass after prompt contract update |
| Audio estimator and stream matching | existing coverage sufficient | Do not change `alignment_audio.py`; run existing alignment tests to guard regressions |
| Public CLI/config contract | existing coverage sufficient unless stop trigger fires | No flag/config/schema changes; run full verification before closeout |
| Real VSPreview usability | broader integration/manual proof required | Launch a generated session with sample clips when environment supports VSPreview |
| Docker/Windows packaging | no new automated test needed | Out of scope unless implementation touches runtime packaging files |

### Required Focused Commands

Run focused tests during implementation:

```bash
.venv/bin/pytest -q tests/vspreview/test_adapter.py tests/services/test_alignment_vspreview.py tests/services/test_alignment_workflow_vspreview.py tests/services/test_alignment_workflow.py tests/services/test_alignment.py tests/vspreview/test_overrides_load.py tests/vspreview/test_overrides_save.py tests/vspreview/test_overrides_precedence.py tests/orchestration/test_phase_tasks_alignment.py
```

Run static checks after code changes:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
```

Runbook full verification before closeout:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

### Required Manual Runtime Proof

If the environment has VSPreview, VapourSynth, and small media fixtures:

1. Run an interactive alignment session with a comparison known to be ahead of
   the reference and enter matching source frames that produce a positive
   offset.
2. Run an interactive alignment session with a comparison known to be behind the
   reference and enter matching source frames that produce a negative offset.
3. Confirm `manual_overrides.toml` stores the computed final signed offsets.
4. Confirm the subsequent pipeline trims align using those saved offsets.
5. Confirm the VSPreview session itself showed untrimmed source clips and did
   not pre-apply the suggestion.

If local runtime proof cannot run, record the exact missing dependency or
environment constraint and do not claim runtime proof passed.

## Rollback Surface

The rollback surface should stay narrow:

- Revert changes in `session_script.py`, `alignment_vspreview.py`, and any
  narrow integration changes in `alignment.py` or `alignment_math.py`.
- Revert corresponding focused tests.
- Do not delete or migrate existing `manual_overrides.toml` files.
- Do not roll back `e799547`, `155a208`, `4bf97fc`, `4199996`, or unrelated
  baseline fixes.
- If authority docs were updated because an approved stop/replan changed public
  behavior, revert those doc changes with the code rollback.

## Stop-And-Replan Triggers

Stop before coding further and ask the maintainer if any of these occur:

1. Implementing option 3 appears to require changing CLI flags, config schema,
   JSON output, or cache/manual override file schema.
2. VSPreview cannot present or communicate reliable source-frame indices in a
   way users can act on.
3. The correct source-frame domain is ambiguous because VSPreview displays
   one-based indices while pipeline internals use zero-based indices and no
   safe conversion contract is obvious.
4. Supporting the new flow would require changing audio estimator semantics,
   stream matching, or cache key policy.
5. The implementation needs mixed-FPS support instead of preserving fail-fast
   rejection.
6. The clean owner seam expands into orchestration phase ordering, render,
   packaging, Docker, or Windows portable files.
7. Import-layer changes to `importlinter.ini` appear necessary.
8. A proposed blank/default behavior would silently persist the suggestion as a
   manual override without explicit source-frame confirmation.
9. Existing tests reveal that downstream trim normalization uses a different
   sign convention than this plan's formula.

## Same-Pass Documentation Rules

- Update `docs/current-architecture.md` only if runtime ownership or module
  boundaries change materially.
- Update `docs/current-cli-contract.md` only if a stop-and-replan-approved
  public CLI/config behavior change occurs.
- Do not update `AGENTS.md` or the runbook for this work unless workflow policy
  itself changes, which is out of scope by default.

## Historical Cleanup-Loop Requirements

The original plan required this controller workflow:

1. Use `frame-compare-cleanup-loop`.
2. Keep authoritative live state in `update_plan`.
3. Load this plan with `frame-compare-cleanup-plan`.
4. Request `frame-compare-cleanup-review` before implementation.
5. Delegate each bounded implementation unit through
   `frame-compare-cleanup-implement`.
6. Review each implementation unit.
7. Use `review-adjudication` for findings.
8. Continue until the approved scope closes or a stop-and-replan trigger fires.
9. Use `closeout-verification` before claiming completion.

## MODEL_SUGGESTION

PLANNER: gpt-5.5 high
IMPLEMENTER: gpt-5.5 medium
REVIEWER: gpt-5.5 high
WHY: Score 4+. The work involves hotspot alignment code, runtime VSPreview
behavior, public CLI/config invariants, multiple boundary skills, and hidden
semantic coupling between preview, persistence, cache, and downstream trims.

## Historical Suggested Session Start Prompt

The prompt below is archived for context only and must not be used as current
execution guidance.

```text
Use frame-compare-cleanup-loop.

Load and follow the active tracked plan at docs/plans/2026-05-30-vspreview-source-frame-alignment-flow.md.

Task: implement the approved option-3 VSPreview manual alignment redesign. The main session agent is orchestrator only: keep live state in update_plan and delegate plan validation, implementation, and review through the cleanup-loop workflow.

Constraints:
- Follow AGENTS.md and docs/ENGINEERING_RUNBOOK.md.
- Preserve public CLI/config behavior unless a stop-and-replan trigger fires.
- Generate base/untrimmed VSPreview sessions.
- Treat audio offsets as hints only.
- Prompt users for matching source-frame positions.
- Compute final signed offsets as reference_source_frame - comparison_source_frame.
- Preserve e799547, 155a208, exact FFmpeg frame extraction, and already-landed VSPreview parity fixes.
- Bias changes toward VSPreview session behavior and confirmation flow, not the audio estimator.
- Run focused tests during implementation and full verification before closeout.
- Record any missing real VSPreview runtime proof explicitly.
```
