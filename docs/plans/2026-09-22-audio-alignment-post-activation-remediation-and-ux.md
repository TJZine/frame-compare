---
search:
  exclude: true
---

Status: Active
Scope: Repair post-activation audio alignment findings AA-01–AA-06 and clarify terminal and VSView review UX without changing authority or wire schemas.
Owner: Audio alignment remediation orchestrator; sequential user-visible Codex tasks, controller-owned integration and plan records.

# Audio alignment post-activation remediation and UX

## Baseline and authority

Use the saved `frame-compare` project and its Local/current checkout at
`dev/v0.6.0-review-remediation`. No worktrees or branch changes.
The handoff expected local and pushed `13330e31e1a22f525d13da95f6f5be45370fd356`.
Initial inspection found clean local `51ef0132fa89d8ed36c6114c63157e2c13630085`,
one commit ahead, while `git ls-remote` confirmed the expected pushed head.
The extra commit changes only `AGENTS.md` and the engineering runbook. The user
explicitly approved this local baseline on September 22, 2026 before edits.
Required ancestors `326da610`, `0df9c369`, `3739ac6d`, and `2a6afbb0` are present.

Read repository-root `AGENTS.md`, the [runbook](../ENGINEERING_RUNBOOK.md),
[architecture](../current-architecture.md), [CLI contract](../current-cli-contract.md),
[command reference](../reference/commands-and-configuration.md),
`importlinter.ini`, `pyproject.toml`, and `.codex/config.toml` as the authorities.
The [original audio plan](2026-09-14-audio-alignment-trust-and-diagnostics.md)
is Historical: preserve its chronology and evidence. The separate
[screenshot plan](2026-08-17-documentation-v2-screenshot-remediation.md) remains
Active and outside this workstream. Preserve it byte-for-byte; initial Git blob
`c2ea06026cc65d5fc7b089ac01e4cc5a83432ad6`.

Use Ponytail full mode with the user's readability, complete-scope, and meaningful
verification preferences. The inspected installed skill is
`/Users/tristan/.codex/plugins/cache/ponytail/ponytail/4.10.0/skills/ponytail/SKILL.md`.
Use `execution-plan-authoring`, `model-selection`, `verification-strategy`, and
`closeout-verification` for their respective decisions, plus only boundary skills
needed by each package. Apply `interface-design` within the accepted existing UI.
The runbook's referenced `large-task-orchestration` skill was not found in the
available personal skill roots; this plan uses the user's complete explicit
orchestration contract and the available execution-plan skill instead. No missing
workflow machinery needs to be invented. `.venv/bin/python` exists; no bootstrap
sync was needed. Bootstrap only if required executables are absent.

## Problem and current state

The v12 mono activation and physical-Windows feasibility/acceptance are complete.
This work repairs concrete post-activation defects, led by the release-blocking
raw/base-trim composition error, and makes the review decision easier to understand.
It does not repeat the earlier feasibility program or redesign audio alignment.

Current shipped policy is
`continuous-origin-qualified-channel-corroboration-2097152-v12`.
Qualified mono evidence may become trusted automatic authority and reach application,
trims, and accepted-cache reuse. Channel evidence is permanently provisional: never
automatically applied, trimmed, cached as computed authority, or promoted by a trusted
peer. A candidate at `+0f` is distinct from no candidate. Manual confirmation is
separate authority and retains the original immutable attempt.

Public/raw offset `O` is reference source frame minus comparison source frame.
Positive offsets trim the reference; negative offsets trim the comparison in the
zero-base case. Existing base trims require the application conversion below.
One child process at a time, sequential PCM lifetimes, bounded retention, and cleanup
of children/readers/workers before cancellation is rethrown remain mandatory.
Failures and partial outputs never create authority; diagnostics never authorize.
Keep cache v2, diagnostics v3, VSView metadata v4, result v1, and manual v1.
This remains a sampled constant-offset estimator, not an edit matcher or drift corrector.

Previous evidence remains scoped: `3739ac6d` activated v12; `89584237` recorded the
checkpoint; `2a6afbb0` proved physical Windows zero/+5/-5 mono application without
base trims, current-v12 reuse, v11 misses, silence/different-segment rejection, the
natural trusted-zero/provisional-zero pair, visible ASCII-safe markers, and cleanup.
The original plan closed at `13330e31`. Native Windows resource-suite skips were
honest platform gaps supplemented by direct Win32 evidence, not suite passes.

## Non-goals and execution restrictions

No new dependencies, public flags/configuration, schemas, thresholds, best-channel
heuristics, channel automatic authority, retry frameworks, compatibility readers,
whole-track PCM buffering, cache identity redesign, or broad orchestration/UI rewrite.
No screenshot-remediation work, unrelated edits, push, amend, rebase, reset, branch
change, publishing, release, or signing. Do not globally disable mono authority for
AA-01. Preserve unrelated non-overlapping changes; stop for an overlapping conflict.
Transient Docker build cache, stopped containers, and obsolete build images may be
cleared if necessary; never remove persistent volumes or unrelated user data.

## Accepted findings and fixed decisions

| ID | Severity and accepted defect | Required disposition |
| --- | --- | --- |
| AA-01 | High, release blocker. Raw offsets passed directly to the trim calculator are then composed with unequal base trims, producing wrong raw-source relationships, including raw zero. Existing legacy normalization coverage asserts the wrong relationship. | At the orchestration application boundary only, pass `Q_i = O_i - B_R + B_C_i`. Preserve raw `O_i` in public/cache/manual/diagnostic/evidence fields. Replace the mistaken expectation with final-source invariants. For `B_R=3`, `B_C=[7,11,13]`, `O=[10,-5,0]`, calculator inputs are `[14,3,10]` and final reference-minus-comparison source starts are `[10,-5,0]`. |
| AA-02 | Medium. Default medium-duration planning rounds odd endpoint lengths into a one-sample overlap. `248003/8000` seconds currently produces `[0,124002)` and `[124001,248003)`. | Plan disjoint integer-domain endpoints for odd/even counts, retaining independence rules and direct/discovery/verification paths. |
| AA-03 | Medium. Credible named-channel dissent in another temporal window can escape the aggregate veto: weak mono and internally corroborated channel frames `0,0,+1,0,0` can yield a misleading provisional zero. No automatic-authority breach was observed. | Veto the aggregate channel hint for any relevant base-credible named-channel observation supporting another frame, even if individual windows have no contradiction flag. Weak/non-credible noise must not veto. |
| AA-04 | Low. The final `AudioWindow` loop local survives into the next channel loader. | Release each view's arrays before the next loader on normal and exceptional paths; prove lifetime with weak references or equivalent. No numeric/policy identity change. |
| AA-05 | Low. Current docs describe declined confirmed reuse as non-applied computed fallback, retain a global-hold assertion, and label generated VSView metadata v2. The old-version rejection list also omits rejected v3. | Document active mono authority/reuse, metadata v4 with prior versions rejected, and F2 cache consequences. Preserve historical evidence. |
| AA-06 | Medium-low, accepted with modification. Docker resource proof is opt-in but workflow filters omit narrow alignment service/orchestration owners. | Add concrete alignment/resource-affecting owner and test paths with workflow-contract tests, not broad `services/**` or `orchestration/**` globs. Ordinary pytest and opt-in resource proof stay distinct. Hosted execution remains pending until pushed. |

### Estimator/cache identity

The user clarified after F2 dispatch that this is a refinement of audio alignment v2,
not a new product version. The originally proposed v13 label is superseded. F2 combines
AA-02 and AA-03 under one fresh opaque cache-policy token:
`continuous-origin-qualified-channel-corroboration-2097152-v2-temporal-invariants-20260922`.
The dated suffix distinguishes evidence policy; it is not a user-facing release label
and does not change any schema version. Do not add version badges to the UI.
The user's subsequent clarification supersedes the original historical-cache matrix:
there is one user, old results need not be preserved, and backward compatibility is
out of scope. Support only the current format and policy. Existing policy-key mismatch
may ignore stale entries and recompute; no migration, compatibility reader, legacy
preservation, special old-version handling, or cache-cleanup subsystem is required.
No other planned package changes identity. Verify current-policy behavior/reuse and
one focused stale-policy miss/rejection; do not build an exhaustive old computed,
embedded, or confirmed-entry matrix. Existing meaningful tests may be reused.
Old shared confirmations may be lost without migration. Current run-local explicit
manual overrides retain their existing precedence. Do not delete unrelated user data.

## Frozen UX state and copy matrix

Use existing Rich and native Qt owners, fonts, spacing, focus behavior, and controls.
Retain source/comparison identities. The hierarchy is outcome/status, action guidance,
then collapsed evidence details. No new design system or broad layout changes.
All `{offset}` substitutions are signed integer frames including `+0f`.
These are presentation labels, not new enum values or wire fields.

### Terminal

At the moment an admitted channel fallback actually begins, emit exactly one human
activity transition per comparison, preserving the existing `ALIGN | Comparison N |
<prepared presentation>` identity, with this text:

> Checking individual audio channels for a review hint. Any hint will need visual confirmation.

Do not emit it for ineligible fallback, sufficient mono, or once per view/window.
No percentage, ETA, new nested phase, or worker-thread UI access. Reuse the current
event-loop/progress handoff. Preserve existing structured JSON progress contracts.

| State | Normal decision-first copy | Action / qualification |
| --- | --- | --- |
| Trusted mono, applied | `Audio alignment accepted: {offset} - APPLIED` | `No additional confirmation needed.` Applied zero is still applied authority, not absence. |
| Reused computed authority | `Accepted audio alignment reused: {offset} - APPLIED` | `No additional confirmation needed.` Do not fabricate current evidence. |
| Manual/confirmed authority | `Manually confirmed alignment: {offset} - APPLIED` | `No additional confirmation needed.` Label reuse when applicable using the existing provenance. |
| Provisional with no current authority | `Provisional audio candidate: {offset} - NOT APPLIED` | `Visual confirmation required to use this hint. Align manually or keep the current alignment.` |
| Unavailable/rejected with no candidate or authority | `No usable audio candidate - NOT APPLIED` | `Align manually or keep the current alignment.` Never substitute zero. |
| Manual authority plus original provisional/unavailable attempt | Lead with the current manual authority above; original hint remains explicitly `NOT APPLIED` if shown. | Original evidence is history and cannot replace the current decision. |

Move reason identifiers, estimator tokens, raw/qualified/independent counts, thresholds,
stream internals, and evidence topology to existing verbose/details output. Keep
truthful actionable failures and successful diagnostic-file location behavior.
Do not lose machine diagnostic facts. Quiet suppresses routine activity/acceptance
but retains existing actionable rejection/write warnings. Non-TTY is static, no-color
retains literal status, narrow output wraps without losing sign/status/identity.
JSON stdout/schemas and existing structured stderr contracts are unchanged.

### VSView before saving

The existing callback-derived draft is the captured position: no new capture button,
hidden-playhead access, synchronization mutation, or authority inference. Show the
active viewing position separately from each stored draft. Inactive sources have
only their last captured position; do not invent a live viewing frame for them.

| Surface/state | Frozen copy |
| --- | --- |
| Complete viewer positions | `{n}/{total} positions captured — ready to confirm` |
| Incomplete viewer positions | `{n}/{total} positions captured` |
| Manual source-frame basis | `{n}/{total} source frames entered` plus ` — ready to confirm` only when complete and valid |
| Known-offset basis | `{n}/{total} offsets entered` plus ` — ready to confirm` only when complete and valid |
| Active output | `Viewing: frame {frame}` |
| Captured viewer draft | `Captured position: frame {frame}` |
| Missing viewer draft | `Captured position: not captured` |
| Manual source draft | `Entered source frame: {frame}` |
| Invalid draft | `Needs attention — {existing validation message}` |
| Trusted mono | `Accepted audio alignment: {offset} — APPLIED` / `No additional confirmation needed.` |
| Reused trusted mono | `Accepted audio alignment reused: {offset} — APPLIED` |
| Manual authority | `Manually confirmed alignment: {offset} — APPLIED` |
| Provisional without authority | `Provisional audio candidate: {offset} — NOT APPLIED` / `Visual confirmation required to use this hint.` |
| Unavailable without authority | `Unresolved comparison — no usable audio candidate` |
| Reference | `Reference anchor — no offset` |
| Evidence disclosure | `Audio evidence details — Comparison {ordinal}`; collapsed by default |
| Viewer-position guidance | `To confirm a new alignment, unlink the playheads and position each source on the same visible moment. Or keep the current alignment.` |
| Known-offset guidance | `Enter the signed reference-minus-comparison offsets, then confirm. Or keep the current alignment.` |
| Primary actions | Preserve `Confirm these aligned positions` and `Confirm these known offsets` by basis. |
| Secondary action | Preserve `Keep current alignment`. Help: `Keeps existing alignment. Provisional candidates are not confirmed; unresolved comparisons remain unresolved.` |

Use current authority first when a manual result coexists with historical evidence.
Keep original accepted/provisional/unavailable audio classification in details; never
relabel provisional as rejected solely because the user confirms manually.
Retain meaningful trim previews but do not describe raw zero as literally untrimmed
when base trims exist. No candidate prefill, playhead movement, visited-state update,
readiness increment, marker authority, or confirmation enablement from evidence alone.

### VSView after either saved action

Prominent heading: `Alignment choices saved`.
Prominent next action: `Close VSView to resume Frame Compare.`
Replace pre-save unlink/position/entry guidance. Hide or replace stale action help;
retain the existing save-once/disabled-action behavior and accessible focus handling.
Show a per-comparison outcome near its identity, above optional original evidence.

| Saved outcome | Frozen copy |
| --- | --- |
| Keep current, accepted computed authority | `Accepted alignment retained: {offset}` |
| Keep current, manual authority | `Current alignment retained: {offset} — manually confirmed` |
| Keep current, provisional and no authority | `Current alignment retained. Provisional candidate {offset} not confirmed — NOT APPLIED. Comparison unresolved.` |
| Keep current, unavailable and no authority | `Current alignment retained. Comparison unresolved — no accepted alignment.` |
| Confirm positions/offsets, any original state | `Alignment confirmed: {offset} — manually confirmed` |

Confirmation establishes manual authority but does not rewrite original audio evidence.
An original accepted audio attempt remains accepted in details; an original provisional
hint remains historical provisional evidence. A keep-current action never silently
confirms it. Use the existing ASCII-safe in-video marker separator (` - `), including
`Provisional +0f - NOT APPLIED`; native panel Unicode must render without mojibake.
Preserve keyboard navigation, focus, enlarged fonts, narrow viewports, manual entry,
close-without-save, strict validation, schemas, and authority semantics.

## Package sequence, boundaries, and acceptance

Execute strictly `C0 -> F1 -> F2 -> F3 -> F4 -> F5 -> U1 -> U2 -> A1 -> W1 -> closeout`.
Every arrow includes controller acceptance and a separate plan-record commit before
the next writer. Current-authority documentation directly affected by a behavior change
belongs to that package; F4 reconciles remaining stale text, not delayed truth updates.
Exact test-file discovery is routine within the stated owner boundary.

### C0 — complete review coverage (read-only)

Inspect complete local ranges `326da610...13330e31` and `0df9c369...13330e31`,
their ancestry, activation commit, and final effective behavior. Close externally
omitted coverage, check AA-01–AA-06 against source/tests, and assess CI-equivalence
assumptions from checked-in workflows. Do not assume ordinary pytest executes the
opt-in resource gate. Identify only materially new consequential findings; no broad
audit, architecture reopening, files changed, or commit. Return file/line/commit
evidence, coverage inventory, proofs and limitations. If the external review artifact
is unavailable, treat the handoff as its claim set and explicitly limit attribution.
Controller checks cited source/ranges and adjudicates contradictions before F1.
Plan record: `docs(plan): record post-activation review closure`.

### F1 — raw/base-trim composition

Write `src/frame_compare/orchestration/phase_alignment.py`, focused orchestration/
production-path integration tests, and directly governing current-contract prose.
Adjacent service/estimator/cache owners are read-only. Implement only normalized
calculator input `Q`, keeping raw `O` everywhere else. Cover equal/unequal base trims,
raw zero/both signs, multiple comparisons, accepted and provisional/rejected siblings,
computed/cache-reused/manual/interactive paths where applicable, source index/selection
mapping, and bounds. Include at least one production audio-to-final-source-frame
integration. Assert final reference source start minus comparison source start equals
raw `O`; do not merely assert calculator calls. No identity change.
Proof: focused phase/selection/production integration plus Full Verification.
Commit: `fix(alignment): compose raw offsets with existing source trims`.

### F2 — temporal evidence invariants

Write `services/alignment_audio.py`, `alignment_consensus.py`, policy identity in
`alignment_correlation.py`, their focused unit/integration/cache tests, and current
identity/behavior docs. Combine AA-02/03; preserve independent-support geometry.
Test odd/even endpoint counts and one-sample boundaries around 30/60/90 seconds at
direct and discovery/verification rates. Test credible named-channel dissent with
both signs at every relevant temporal position, including internally agreeing windows;
weak/noisy dissent does not veto. Channels remain provisional with fail-on-call or
equivalent proof against application/trims/cache/promotion. Test the single policy refresh,
current-policy behavior/reuse, and one stale-policy rejection as specified above.
Proof: focused planner/channel/cache/production integration, Full Verification,
native alignment integration, current docs, and fresh Docker candidate proof.
Commit: `fix(alignment): enforce temporal evidence invariants`.

### F3 — channel PCM lifetime

Write only channel lifetime seam in `services/alignment_consensus.py` and focused
tests. Release arrays before the next channel loader, including the lingering loop
local; prove normal and exception/cancellation cleanup with weak references or
equivalent. Retain one active child and identical numerical/policy behavior and token.
Proof: focused lifetime/channel/cancellation tests, Full Verification, opt-in native
resource suite and relevant Docker resource proof. No new resource framework.
Commit: `fix(alignment): release channel buffers between views`.

### F4 — current documentation reconciliation

Write current CLI contract, command reference, and current audio guide/architecture
only for AA-05 and accepted F2 consequences. Confirm source truth for declined reuse,
active mono authority, metadata v4, and current-policy-only reuse. Historical plans
and immutable evidence are read-only. Proof: CLI contract-doc tests, generated API
check, strict documentation build, link/diff inspection; no product change.
Commit: `docs(alignment): reconcile authority and metadata contracts`.

### F5 — CI resource trigger coverage

Write only `.github/workflows/docker-integration.yml` and focused workflow-contract
tests. Include narrow alignment calculation/collection/lifetime owners and resource-
affecting orchestration/test seams found by tracing the suite, plus workflow self-
coverage if necessary. Existing `tests/integration/**` already matches its suite.
No blanket service/orchestration globs; assert positive owner matches and unrelated
negative matches. Preserve opt-in command and ordinary pytest separation.
Proof: YAML parse, workflow contracts, Full Verification and canonical Docker gate
under runbook requirements. Hosted trigger behavior pending push, not locally proven.
Commit: `ci(alignment): run resource proof for alignment changes`.

### U1 — terminal UX

Write existing presentation/progress seams in `services/alignment.py`, their current
progress/presentation callers only where the activity transition requires them, focused
terminal/progress tests, and governing current CLI/audio-guide prose. No general
progress redesign. Implement the frozen terminal matrix with one actual-fallback
transition and decision-first normal output. Keep diagnostic facts and JSON contracts.
Test sufficient-mono/no-fallback, repeated views, zero/both signs, manual plus original
attempt, quiet, non-TTY, no-color, narrow layout, and current/absent history. Verify
event-loop delivery and cancellation. Proof: focused rendering/progress/JSON/CLI
contracts, Full Verification, docs checks, and rendered terminal inspection.
Commit: `feat(alignment): clarify analysis progress and review decisions`.

### U2 — VSView UX

After U1, write existing `vsview/alignment_review_panel.py`, `session_script.py`
presentation if necessary, focused native panel/session tests, and directly governing
current docs. Contract/service authority owners remain read-only. Implement the frozen
pre/post-save matrix using existing controls; outcome first, concise guidance second,
collapsed details third. Distinguish viewing/captured/manual positions and evidence
state. No schema/authority or callback observation semantics change. Cover mixed
accepted/provisional/unresolved and historical/manual evidence; confirmation and
keep-current; absence versus zero; no stale guidance after saving; no mojibake.
Proof: focused panel/session/metadata contracts, Full Verification, docs, fresh
distribution proof for changed bundled assets, and real Qt rendering at normal/narrow
sizes and enlarged font with keyboard/focus/manual-entry checks. Offscreen proof is
explicitly distinct from physical-Windows visual acceptance in W1.
Commit: `feat(vsview): clarify captured positions and retained outcomes`.

### A1 — controller integration verification

Run directly in the orchestrator; no writer or monitoring task without a concrete
repair. Run all canonical checks below on the integrated candidate, inspecting full
output and every skip. Record exact source/image/artifact identities. Repair only
concrete task-caused failures via a bounded new task, then rerun invalidated proof.
Commit the plan-only acceptance record after a clean candidate is established.

### W1 — physical Windows acceptance and handoff

After clean committed Mac acceptance, stop implementation and give the user a complete
copy-paste prompt for a brand-new physical-Windows Codex task. No remote push is
authorized to transfer it: report exact candidate and required ancestor SHAs and let
the user supply that checkout. Task writes only sanitized canonical evidence at
`tests/fixtures/alignment_oracle/streaming-production-results.json`; private media,
screenshots, raw logs and package outputs remain ignored/untracked. No production or
plan edits, signing, publishing, dependency refresh, or runtime redesign.

| Windows gate | Required evidence |
| --- | --- |
| Identity/package | Exact clean controller candidate, required production and baseline ancestors; package from committed source under runbook or verify exact supplied production candidate. Record controller/production/package/bundle/inventory/runtime identities and any plan-only delta. Validate provenance, hashes, sizes, layout, licenses, launcher/doctor and extracted package. |
| Raw composition | Unequal/equal base trims with raw zero/positive/negative, multi-comparison and mixed authority. Independently demonstrate final raw-source start differences equal raw `O`, not `Q`. |
| Temporal policy | Odd-duration endpoints, direct/verification paths; cross-window credible channel dissent suppresses the hint, weak dissent preserves valid provisional evidence. |
| Real controls | Retained-real zero/+5/-5 controls; natural three-file trusted mono zero plus provisional channel zero. Keep true different-segment/silence negatives. No forced remix tuning. |
| Cache | Current v2-refinement policy write/reuse and one stale-policy miss/rejection; explicit current manual precedence and no channel authority/promotion. Old results need not survive. |
| Resources/lifetime | Same-timestamp combined RSS, bounds, handle plateau, one active child, reader/worker cleanup, cancellation and partial/nonzero failure. Run resource suite and report native Windows sampler skips honestly; direct Win32 evidence fills platform proof, not a false suite pass. |
| Visible terminal | One actual channel activity transition, signed accepted/applied/provisional/unavailable decisions, manual/quiet/non-TTY/no-color behavior as applicable. |
| Visible VSView | Captured versus viewing positions; accepted/provisional/unresolved states; collapsed details; confirm and keep-current; prominent truthful saved summaries; close-to-resume guidance without stale instructions; Unicode/ASCII overlay rendering; narrow view/enlarged fonts; keyboard/focus; both manual bases; close without saving. |
| Fail closed | Missing/malformed/contradictory results, no partial authority/cache/trims, unchanged session/result/manual schemas. |
| Evidence hygiene | JSON/policy/hash/privacy validation, complete actual outputs, exact commands and limitations, ignored private captures, sanitized canonical evidence only and clean worktree. |

Suggested evidence commit: `test(alignment): verify Windows remediation candidate`.
Require the same one-attempt callback contract below. Controller reviews every evidence
line and reruns locally available oracle-policy/JSON/privacy/hash/diff/docs checks.
Contradictory Windows evidence blocks closeout and triggers a replan.

## Verification commands and evidence rules

Risk is high for the overall program: orchestration, authority-adjacent policy,
native lifetime, public presentation, and Docker are affected. Plan-only activation
is nonbehavioral and uses structural/preamble/reference/diff and strict-doc proof.
Package regressions establish the concrete defect; full gates do not replace them.
Workers retain complete output in ignored task evidence with paths returned to the
controller. Test count alone is not an acceptance claim. Inspect skips individually;
unavailable native/UI/Windows/hosted proof stays pending. Do not poll tasks.

Full Verification and A1 mandatory commands:

```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
bash tools/verify_docker_integration.sh
docker compose run --rm --no-deps \
  -e FRAME_COMPARE_CONTINUOUS_ALIGNMENT_RESOURCES=1 \
  --entrypoint python frame-compare-test \
  -m pytest -o cache_dir=/tmp/frame-compare-resource-pytest-cache \
  tests/integration/test_alignment_streaming_resources.py -rsx -s
git diff --check
git status --short
git log --oneline --decorate -n 20
```

Use the checked-in workflow/runbook if an exact command changes. Confirm resource
proof uses the current verified image/source, not a stale tag. Default Docker proves
headless media/runtime, not visible VSView. Native opted-in resource command is
`FRAME_COMPARE_CONTINUOUS_ALIGNMENT_RESOURCES=1 uv run --no-sync pytest -q tests/integration/test_alignment_streaming_resources.py -rsx`.
For docs run `uv run --no-sync pytest -q tests/test_cli_contract_docs.py` as applicable.
Use runbook distribution proof with a fresh `mktemp -d` directory and fresh install
when packaging/installed assets change or candidate proof requires it; inspect exact
wheel/sdist and installed behavior. Windows follows the runbook unsigned portable
build/extracted verification route; signing remains forbidden for this task.
Before every commit inspect every changed line, stage intended paths only, and run
`git diff --cached --check` plus scope/status checks. Record observed command output,
failures/repairs, skips, identities, and worker versus controller proof separately.

## Orchestration and callback contract

Only one implementation writer at a time, using user-visible Codex new tasks on the
saved project/current Local checkout. No implementation subagents. Before each
dispatch inspect `.codex/config.toml` and resolve current role policy. Select the
standalone model and reasoning at dispatch based on settled boundaries and actual
risk; do not permanently bind package models here. Record actual settings below.
The user's standalone task settings govern, not the subagent profile's reasoning.

Every package prompt must contain exact headings `UNIT`, `STARTING SHA`, `OBJECTIVE`,
`OWNER/WRITE BOUNDARY`, `DEPENDENCIES`, `INVARIANTS`, `ACCEPTANCE`, `VERIFICATION`,
`EXPECTED RETURN`, `STOP CONDITIONS`, and `CONVENTIONAL COMMIT`.
Give an exact starting SHA, this plan, package commit subject and write scope.
Tell each task not to spawn subagents, broaden scope, push, amend, rebase, reset,
change branches, publish, release, sign, or modify unrelated work. It must inspect
every changed line, meet acceptance honestly, verify, commit conventionally, and
send the callback. If acceptance cannot be met, stop without committing. C0 is the
explicit read-only/no-commit exception.

Every child prompt includes verbatim:

> At completion, use Codex task messaging to send your complete structured result to the task titled exactly `Audio alignment remediation orchestrator`. Resolve that task once through the task list, make one delivery attempt, and report whether it succeeded. Do not retry, poll, or monitor the orchestrator. If direct delivery is unavailable, leave the full structured result as your final response so the user can paste it back.

Return `RESULT`, `CALLBACK_SENT`, `START SHA`, `END SHA`, `FILES CHANGED`, `COMMIT`,
`PROOF EXECUTED`, `PROOF NOT EXECUTED`, `ASSUMPTIONS`, `BLOCKERS`, `REMAINING RISKS`.
After dispatch the controller ends the turn and waits for that callback; no task
polling, repeated inspection, or progress-monitor tasks. This explicit user workflow
overrides the app's generic post-creation waiting recommendation.

On each callback confirm SHAs/ancestry, inspect commit and every changed line, read
complete proof output, verify scope and otherwise clean checkout, and run independent
risk-matched controller verification. Repair only concrete findings through new tasks.
No habitual reviewer pass: another read-only review needs materially new consequential
risk. After acceptance update this execution record and commit it separately before
dispatching the next dependency-ready package. Report implementation/plan commits,
controller proof, remaining risks, and next package. Continue automatically until
Windows, a declared replan gate, or a genuine unresolved product decision.

## Stop/replan gates, risks, and rollback

Stop for an unapproved checkout/branch/revision discrepancy, overlapping user edits,
an invariant that cannot be preserved, a required public config/dependency/schema/
channel-authority change, a new high-severity architectural conflict from C0, cache
architecture changes beyond accepted prior-policy misses, UX requiring material redesign,
regressions outside the authorized unit, contradictory Windows evidence, or a
consequential product ambiguity unresolved by this plan. Routine fixture, helper,
file-discovery and implementation choices are not user decision gates.

| Risk | Control / remaining limitation |
| --- | --- |
| Wrong coordinate or sign, especially zero and mixed siblings | F1 final-source invariant and production integration, repeated on Windows; AA-01 remains a release blocker until accepted. |
| Credibility/support regression | F2 boundary and dissent-position/sign matrix; fixed floors and independent support remain unchanged. Sampling cannot detect every edit. |
| Old results discarded | Accepted by the sole user; current-policy-only support, no backward compatibility, migration or identity split. |
| Retained PCM/process resources | F3 lifetime assertions plus native/Docker/Win32 proof; sampled memory cannot exclude every between-sample transient. |
| UI implies authority or confuses saved state | Frozen state matrix, strict schemas, fail-closed tests and physical visual acceptance. |
| CI absent or skipped | Narrow filter contracts, explicit opt-in Docker run; hosted CI remains pending until user push. |
| Platform/evidence limitations | Mac/offscreen results cannot substitute for physical Windows; private real-media lineage remains limited. |

Rollback is prospective guidance, not permission for forbidden Git operations.
Use a focused forward repair or an explicitly approved revert of a cohesive package;
never amend/reset/rebase or restore an old policy token to resurrect cache authority.
Any rollback changing estimator semantics requires a fresh identity and controller
replan. Withdraw a failed candidate from release consideration while preserving
manual authority, immutable history and accepted earlier evidence. Do not globally
disable automatic authority for AA-01 alone. No rollback deletes user data/volumes.

## Execution record and closeout

Each accepted row must include actual start/end SHA, task/model/reasoning, write scope,
implementation/evidence commit, worker output/proof, independent controller proof,
separate plan-record commit, and risks/stop notes. A record may name its own commit by
the unique subject and Git history rather than a self-referential hash; backfill hashes
at the next checkpoint. Pending rows are not proof.

| Unit | State | Start / end SHA | Task / actual model / effort | Write scope and commit | Worker proof / evidence | Controller proof | Plan record / risks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Activation | Complete | `51ef0132fa89d8ed36c6114c63157e2c13630085` / `edb10ef6f3e0b7c413a414374e26c8e4959080f4` | Current orchestrator; GPT-6, effort not exposed | This plan only; `edb10ef6` | Not applicable | Baseline/ancestry/authority, preamble/package/link checks, API drift, strict Zensical (no issues), staged diff and hooks passed. Initial site-link failure repaired before commit. | User approved extra workflow commit; no product edits |
| C0 | Accepted | `edb10ef6f3e0b7c413a414374e26c8e4959080f4` / same | `01a0c7bd-430a-7590-86da-f91ffb5699fc`; `gpt-5.6-sol`, medium | Read-only; no implementation commit | Complete structured callback received; 69/53 commits, 86/66 historical touched paths; four reproductions; 11 focused tests passed | Independent source/workflow/range audit; AA-01/02 reproduced; same 11 tests passed, no skips; clean status | `docs(plan): record post-activation review closure`; details below |
| F1 | Accepted locally and in Docker; Windows remains W1 | `cdd0fce3643dd57b6307ef43ae725975e539f633` / `5e75900ca572038105dc9e700ec5ee3759ac98bd` | `01a0c7cd-4fe7-7232-a1ee-dd892721fbdb`; `gpt-5.6-sol`, medium | Six authorized phase/test/current-doc files; `5e75900c` | Red/green regression, focused/full/static/docs and targeted canonical Docker passed; ignored logs `task-evidence/f1` | Every changed line inspected; focused phase/cache/manual/native integration passed; image source/lock hashes match | `docs(plan): record raw offset composition acceptance`; Windows still required |
| F2 | Accepted locally and in Docker after F2-R; Windows remains W1 | `e55615b6ea3f73f6e4e4c9e7ac5075a802bc240d` / `c5554ea784921d65fe9a748ba133854a3d67d956` | `01a0c7dd-8e98-7230-9c66-2f22bd822e02`; `gpt-5.6-luna`, xhigh | Twelve planner/channel/policy/test/current-doc files; `c5554ea7` | Full/static/docs pass with documented skips; targeted Docker and opt-in channel proof reported | Focused planner/channel/cache/authority/native-contract tests passed, no skips; documentation overstates midpoint split above 60 seconds | F2-R accepted at `8aa733aa`; F3 next |
| F3 | Accepted locally and in Docker; Windows remains W1 | `137267b1f3573c69d40c7d79b8d473b29b35cccb` / `b9919607c9395b168a79633c5a2234f83ea5b977` | `01a0c7fd-c427-7f42-9553-f2bb3690cb42`; Luna xhigh | Consensus lifetime and focused tests; `b9919607` | Full/static/docs, native and Docker resource/channel proof passed within recorded limits | Every changed line inspected; focused tests and five native resource tests passed; image hashes match | F4 next; no numerical or identity change |
| F4 | Accepted | `1133b11fd2b4ec46fc9e6cb695d700cb883116de` / `c15d230c638a0c33299fbddf7321e148cd8c62f0` | `01a0c80b-bf75-72a0-88ae-72b374fe7074`; Luna xhigh | Current CLI contract and command reference; `c15d230c` | Contract-doc/API/isolated strict docs and hooks passed | Every changed line and source facts inspected; contract-doc/API checks passed; tracked strict docs passed | F5 next; unrelated untracked site-link warning preserved |
| F5 | Accepted trigger coverage; hosted gate pending | `dff31ed101bc8f5b78dc72f62b7ff0495f49e870` / `d4b571db466156db6fa42929fe28378b7b1509bf` | `01a0c816-6b9e-7751-9a45-734b5be9a236`; Luna xhigh | Workflow path filter and contract tests; `d4b571db` | Full/static/docs, Docker resources passed; broad guard remains non-pass | Every changed line checked; 21 independent workflow tests passed | U1 next; no hosted pass claim |
| U1 | Accepted after U1-R; Windows remains W1 | `e9e70d8891c7c65264d650b2fbd759ca808d86fe` / `e07699581cc3a171230d19f6c99e16539dbaeab3` | `01a0c828-7d7d-7270-9d9e-4fda3f1be796`; Luna xhigh | Alignment presentation/callback, tests and current docs; `e0769958` | Focused/full/static checks reported; normal/narrow render captured | Complete diff inspected; focused tests passed; two concrete contract gaps reproduced | U1-R `6ea7e67a` accepted; U2 next |
| U2 | Accepted after U2-R; physical Windows remains W1 | `5afe857c788481073053f67f74a97e35b86d070b` / `ecfdc90d1f83e021d087e5941f06791d35137639` | `01a0c854-688e-74d1-ae5b-83257c98e199`; Luna xhigh | Panel/tests/current docs; `ecfdc90d` | Full/static/docs/package and offscreen screenshots reported | Code and screenshots inspected; three UI regressions reproduced in Qt | U2-R `c0fb947d` accepted; A1-R Docker gate repair next |
| A1 | Pending U2 | Pending | Controller | Integration proof and plan record | Not applicable | Pending | No monitor delegation |
| W1 | Pending A1 and physical host | Pending | Pending | Canonical sanitized evidence only | Pending | Pending | Mandatory before closeout |
| Closeout | Pending all acceptance | Pending | Controller | Plan only | Not applicable | Complete range audit pending | Hosted status and limitations required |

### C0 acceptance — September 22, 2026

The task delivered one complete callback to this orchestrator. No polling or secondary
review was used. Start/end remained `edb10ef6`; the worker changed no files and made
no commit. All AA-01–AA-06 findings are confirmed; no materially new consequential
finding or architectural replan gate was found. The adjacent v3 omission is folded
into AA-05/F4. External review text was not supplied, so closure checks the handoff's
claims against the complete local history rather than inventing external attribution.

Coverage inventories in the callback contain every historical touched path and all
69 commits in `326da610..13330e31`, grouped into foundations, rejected experiments,
R0–R5, release/CI evidence, channel support, and activation/closeout. The narrower
`0df9c369..13330e31` contains 53 commits. Controller independently confirmed 86/66
historical touched paths (not net-diff file counts) and that the only post-activation
changes through `13330e31` are the old plan and canonical Windows evidence JSON.
The approved `51ef0132` workflow-only commit and this new plan do not alter production.

Worker evidence: inline AA-01 calculator/final-source reproduction, AA-02 planner
reproduction, AA-03 production-service cross-window dissent reproduction, and AA-04
weak-reference reproduction. AA-03 retained a provisional zero with all per-window
contradiction flags false, while applied remained false and public authority absent.
AA-04 retained the preceding final window array at each next loader, then released
all on function return; this is not proof of concurrent processes or permanent leaks.
These last two executions are worker-observed; controller directly reviewed the
responsible nested-loop and aggregate-veto source but did not rerun those reproductions.

Controller independently reproduced AA-01 with bases `3/[7,11,13]`: raw calculator
inputs give final differences `[6,-13,-10]`, whereas `Q=[14,3,10]` gives `[10,-5,0]`.
AA-02 directly produced `[0,124002)` and `[124001,248003)` at 8000 Hz. Source review
confirmed AA-05's active latch/embedded reuse versus stale documentation and AA-06's
missing narrow filters, ordinary-pytest opt-in skips, canonical default exclusion,
and separate resource invocation in the same preceding-built test service.

Both worker and controller ran:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -p no:cacheprovider -o addopts='' \
  tests/orchestration/test_phase_tasks_alignment.py::test_run_align_phase_legacy_normalizes_positive_negative_and_zero_offsets_with_base_trims \
  tests/workflows/test_docker_integration_contract.py \
  tests/services/test_alignment_authority_hold.py \
  -k 'legacy_normalizes or docker or r7' -rsx
```

Complete controller output: 24 collected, 13 deselected, 11 selected; all 11 passed
in 2.23 seconds with no skips. Worker reported 11 passed in 1.99 seconds. The passing
legacy trim test currently asserts the wrong relationship; it does not negate AA-01.
No new full product, Docker, resource, package, Windows, or visible-UI proof was
claimed for this read-only unit. Hosted CI remains unobserved. C0 needs no further
review; F1 is next and must replace the wrong test expectation with source-frame proof.

### F1 acceptance — September 22, 2026

Implementation commit `5e75900ca572038105dc9e700ec5ee3759ac98bd` converts only
authorized raw offsets to calculator coordinates in `orchestration/phase_alignment.py`.
Stored raw values and `None` authority remain unchanged. Existing trim composition
retains bounds and common-domain handling. The corrected signed multi-comparison
regression proves raw differences `[10,-5,0]` with bases `3/[7,11,13]`; mixed siblings
retain provisional non-authority. Real FFmpeg plus production service/orchestration
proves raw zero with bases 3/7 becomes final starts 7/7 and correct selected frames.
No estimator/schema/authority change; v12 remains current until F2.

The task initially stopped without committing because user-owned tooling edits changed
workflow expectations during full pytest. The user explicitly identified those edits
as theirs and instructed F1 to ignore that issue and continue. They landed separately
as `6e5e47cd6f1ef701a3b80c7d2270df56147dc022`; verification was rerun afterward.
The separately staged R80 handoff became `7a661bed05aed2d10746780820626c97f04def32`
after F1. Both commits are unrelated user-owned work, preserved and excluded from
this workstream's implementation diff. No rebase/reset was needed or performed.
The original interrupted/mixed-state full-suite failure is not acceptance evidence.

Worker logs are ignored local files under `.codex/cache/task-evidence/f1/`.
Logs 01–19 retain red/green tests, fixture corrections and the interrupted run;
20–31 record final verification. The controller read final full pytest and all gate
outputs, reviewed all six committed files, and confirmed commit scope/ancestry.
Final worker proof: focused 38-test acceptance, full pytest, changed-file formatting,
Pyright (zero errors/warnings), Ruff, Bandit (zero medium/high), both import contracts,
API drift, five CLI-doc tests and strict Zensical passed. Ordinary-suite opt-in,
unavailable native plugin, live-service and Windows/PowerShell skips remain explicit.

Broad canonical Docker built fresh source images and ran 339 passing tests with one
intentional channel-calibration opt-in skip; its zero-skip guard correctly failed.
The subsequent supported targeted verifier ran the new production integration with
zero skips and the complete runtime/application probes, including non-root execution,
VapourSynth R79/API 4.2, L-SMASH/FFMS2, RGB48 placebo, Debian FFmpeg/ffprobe
`7:7.1.5-0+deb13u1`, software Vulkan, linkage/provenance/doctor, generated fixtures,
real rendering and generated application artifacts. Only this targeted route is
accepted as the completed F1 Docker gate; the broad invocation is not called passed.
Images: test `sha256:eab17d4e70955b540d6460b004ec952e26024bf2db1c58fa7b56cf3b0d76d0e7`,
runtime `sha256:9a9e14b582cad5eb3a5543fe8dd96a5ce690e20b9993020933d7247cf1b22e58`.
Controller confirmed both tags and exact image/local SHA-256 matches for the changed
production owner, new integration test, `pyproject.toml`, and `uv.lock`.

Independent controller command passed without skips:

```bash
uv run --no-sync pytest -q \
  tests/orchestration/test_phase_tasks_alignment.py \
  tests/orchestration/test_phase_alignment_contract.py \
  tests/integration/test_alignment_continuous_pipeline.py::test_real_audio_alignment_preserves_raw_zero_offset_through_unequal_base_trims \
  tests/services/test_alignment_previous_offsets.py \
  tests/services/test_alignment_manual_overrides.py -rsx
```

`git show --check`, clean status, screenshot-plan hash, and the plan-record diff were
checked. Reuse the inspected full/static/Docker evidence because no subsequent product
change invalidated it; the later R80 handoff is plan-only. Physical Windows remains W1.
At A1 the broad Docker opt-in skip still needs explicit handling through the supported
test selection/opt-in route; do not weaken zero-skip enforcement. F2 is next.

### F2 controller checkpoint — bounded documentation repair

The controller inspected the F2 diff and independently ran distributed planning,
channel corroboration, reuse-cache, authority-hold, and VSView alignment-review
contract tests. All passed without skips. The complete full-suite log shows expected
runtime/platform/opt-in skips; these are not resource or Windows acceptance. Static
and strict-doc logs pass. The broad Docker run still fails its zero-skip guard on the
channel opt-in test; targeted Docker proof is distinct and final A1 remains required.

One concrete correction is required before acceptance: all three changed current
docs describe the entire default 30–90-second tier as midpoint halves. The actual
planner splits integer halves only through 60 seconds; above 60 and below 90 it
retains two capped 30-second endpoint windows with a gap. This is the intended bounded
behavior, so repair prose only and preserve larger configured minimum-window behavior.
F2-R may edit only those three current docs, verify against source and existing
boundary tests, run API-doc and strict documentation checks, and commit separately.

The callback's starting SHA was mistyped and its model description was inconclusive.
The ledger uses the exact dispatch SHA and explicit tool model/reasoning instead.
Intervening controller plan clarifications and the user's independent runtime-plan
commit are expected. The unrelated untracked CLI/report UX plan is preserved.
Audio alignment remains a v2 refinement; old results remain disposable, without
compatibility readers, migrations, or preservation requirements.

Checkpoint API-doc validation passed. Controller strict-doc validation was blocked
solely by the unrelated untracked CLI/report UX plan's root `AGENTS.md` site link
(line 65); that file is preserved. This is not an F2 regression or a strict-doc pass.

Activation commit: `docs(plan): activate audio alignment remediation and UX plan`.
After all implementation, controller, and Windows gates pass, inspect every commit
and complete net diff since the approved baseline; confirm no unrelated changes and
clean worktree, complete all ledger/evidence fields, and preserve screenshot-plan hash.
Then mark this plan `Status: Historical`, record final evidence, hosted-CI status,
remaining limitations and user-only transfer/push follow-up, and commit only this plan:
`docs(plan): close audio alignment remediation and UX plan`.
Report all implementation/evidence and plan-record commits, local/Docker/Windows
proof, residual risks and whether user action remains. Do not claim completion before
W1. Do not push, publish, release, sign, amend, rebase, or reset at closeout.


### F2 and F2-R acceptance

F2-R task `01a0c7f5-c9a3-74a2-a8de-3ac0e5849f5e` ran on Luna xhigh,
from `0cf03a275edeac469102c2f99a52c98d7a453bcc` to
`8aa733aa92c6eb2ba8d4f066bae3c30649e295e4`. Its three-doc-only commit
`docs(alignment): clarify bounded endpoint planning` corrects the midpoint claim;
no production or test behavior changed. Controller inspected every changed line and
confirmed source geometry and configured-minimum behavior. Worker boundary tests,
API check, copied-doc strict build, and commit hooks passed.

Controller reran distributed planning and CLI contract-doc tests successfully without
skips, plus API-doc validation. An independent strict build of a temporary copy of
all tracked docs and the current Zensical config passed with no issues. This isolates
the known unrelated untracked UX-plan link warning without altering user files.
Both unrelated untracked UX plans remain preserved.

Controller read the F2 full-suite and Docker logs, preserving their explicit skip
limitations. Targeted production Docker runtime/application proof passed with zero
skips, and opted-in channel tests passed. Controller independently compared the
three F2 production owners plus pyproject/lock hashes against test image
`sha256:d55f6f842cc7383666ee14979258e489fab522634e05ae752546b268b29ec0ae`;
all match. Production image was
`sha256:df6e0e4f0b3203ef889d6673dc5a5e1e4a52946af38d132ebfc494780e96c375`.
F2/F2-R are accepted within these local/Docker bounds. Resource proof belongs to F3
and A1; physical Windows remains W1; hosted CI is pending push. F3 is next.


### F3 acceptance — channel PCM lifetime

Implementation `b9919607` wraps existing per-view scoring in `try/finally` and clears
both `phase` and the lingering `window` local. The whitespace-insensitive diff confirms
no scoring/qualification calculation changed. Weak-reference tests cover release before
the next loader on normal and handled correlation-error paths, and release during
cancellation rethrow at the post-load cancellation check. These prove this owner's
references, not arbitrary references retained by external exception traceback frames.

Controller independently passed channel corroboration, distributed planning and
mono-authority tests without skips, plus all five opted-in native streaming resource
tests. Worker logs under `.codex/cache/task-evidence/f3` show full pytest and static
checks passing with explicit platform/live/opt-in skips, API checks passing, and strict
tracked-docs proof passing. Live site validation remains blocked by the unrelated
untracked UX plan's root-AGENTS link. Both unrelated untracked plans are preserved.

Native and Docker channel matrices each completed 36 decodes, preserving zero and
signed positive controls and rejecting negative controls. Native and Docker resource
suites each passed five tests; Docker reports one maximum active child, bounded sampled
RSS, and no active children after cancellation. Sampling is bounded evidence, not an
exhaustive allocation trace. Targeted Docker production runtime/application proof passed
with zero skips. The broad wrapper remains a non-pass (339 passed, one channel opt-in
skip), and final A1 must honor its zero-skip rule.

Controller verified the consensus implementation, focused test, pyproject and lock hashes
against test image `sha256:a011be25adb099b99d57ded3deb9f9c712db9c22267cf769a1bec58ac1e7bdc9`.
Production image: `sha256:9ffc6ae4448ba59d87f5ab480be551021b59bd004cfc35ee384fe04366dbd9f2`.
No package/schema/identity/authority change. Windows semantics remain W1 and hosted CI
remains pending push. F4 current-documentation reconciliation is dependency-ready.


### F4 acceptance — current authority and metadata documentation

Commit `c15d230c` corrects four factual statements in two authorized current docs:
qualified-mono fallback after declining confirmed reuse, active automatic authority,
metadata v4, and explicit rejection of metadata v1/v2/v3. Controller inspected the
complete diff and confirmed the inactive hold latch and current computed-reuse path.
No runtime, cache policy, schema, historical plan or unrelated file changed.
Controller independently passed five contract-doc tests and API-doc validation;
strict tracked-doc validation passed. Worker complete logs are in
`.codex/cache/task-evidence/f4`. Live strict docs still encounters the unrelated
untracked UX-plan site link; copied tracked-doc proof isolates that known issue.
F5 is next. Physical Windows and hosted CI remain pending as before.


### F5 acceptance — resource workflow trigger coverage

Commit `d4b571db` adds only the controller-selected narrow owner paths and alignment
test patterns plus workflow self-trigger. Contract coverage checks exact inclusion,
representative matches, unrelated negative cases, unchanged resource command ordering,
and the zero-skip guard. Controller inspected every changed line and independently
passed all 21 Docker/workflow contract tests. No runtime, job command, permission,
branch filter or dependency changed.

Complete worker logs in `.codex/cache/task-evidence/f5` show full/static/API/tracked-doc
checks passing with stated platform/opt-in skips. Reused F3 image hashes match resource
owners/test/dependencies; five opted-in Docker resource tests passed. Broad canonical
Docker returned exit 3 with 339 passing and one channel opt-in skip. This acceptance
covers triggers only: the pre-existing skip still blocks the sequential hosted job
before its resource step and must be resolved or explicitly gated during A1. It is
not a hosted resource pass. User files remain preserved; Windows remains W1.

### U1 controller implementation decisions

Use a private optional channel-fallback callback through the existing computation
call chain in `services/alignment.py`. Invoke it once when the channel plan is admitted,
before the first channel loader, not per window/view. Marshal human progress through
the existing `loop.call_soon_threadsafe` seam. Suppress this new human activity in
quiet/JSON modes; retain existing machine events unchanged. No new progress protocol,
wire field, enum, worker UI access, task nesting or event framework.

Choose the normal heading from current applied result and its provenance first;
historical attempt state cannot override manual authority. Keep original evidence
truthful in verbose/details, including explicit NOT APPLIED for original provisional
hints. Reuse existing normal/verbose formatting owners; move internal detail lines
rather than discard diagnostic facts. The frozen terminal copy above is authoritative.


### U1 controller checkpoint — structured events and reuse label repair

Controller inspected all seven changed files and normal/narrow no-color Rich captures.
Focused workflow, previous-offset, channel, native-review and cancellation tests passed.
Two concrete gaps prevent acceptance:

1. `_present_alignment_evidence` changed the predicate used by JSON structured warnings
   from unapplied OR historical attempt not trusted to only unapplied. An applied manual
   result with a provisional historical attempt now emits no event where the prior
   contract emitted `audio_alignment_requires_review`. Preserve the prior JSON predicate
   and fields exactly; use current-authority-first behavior for human output separately.
2. `shared_previous_offsets` now prints the same manual heading as a new confirmation.
   Restore the required reuse label using this frozen line:
   `Manually confirmed alignment reused: {offset} - APPLIED`.
   Keep `Manually confirmed alignment: {offset} - APPLIED` for current-run confirmation.

U1-R is limited to alignment.py presentation predicates/copy, focused workflow/reuse
regressions and the two directly governing current docs. Add explicit tests for the
JSON historical-attempt case and current versus reused manual headings. Do not alter
wire fields or the historical JSON event as an unsolicited cleanup. Complete the
missing tracked-doc strict proof and relevant real production integration proof, then
return a separate conventional repair commit. Existing hold-latch rollback behavior
is unrelated to old-result compatibility and need not be redesigned.


### U1 and U1-R acceptance

Repair task `01a0c840-223f-7f03-b199-1b66c0c6ee15` ran Luna xhigh from
`d80e9f3b9e908f9f373fd319973fa0a9312f4241` to
`6ea7e67a5af9e76ad08608dc85582f6c57e9caa0`. Controller inspected every line of
its five-file diff. JSON retains its prior historical-attempt event predicate and
unchanged fields; human output remains current-authority-first. Shared confirmed
reuse has the frozen distinct manual reuse label. Regression tests assert exact
structured events and production reuse presentation.

Controller independently passed workflow/reuse/native-review/cancellation/CLI-doc
checks and actual production channel integration, without skips. Worker full pytest,
static checks, API-doc and isolated strict docs passed; full-suite platform/live/opt-in
skips remain explicitly unproven. Complete logs/commands are in
`.codex/cache/task-evidence/u1-r/COMMANDS.md`. Original normal/narrow no-color Rich
captures were inspected. Controller tracked-doc strict check passed. U1 is accepted;
Windows visible UX remains W1 and fresh integrated Docker proof remains A1.

### U2 controller implementation decisions

Retain existing Qt widgets and scalar draft state. Put the existing status label before
action guidance, with per-source outcomes before captured-position detail. Reuse
checkable evidence groups, collapsed initially; no new capture control or playhead
observation. The active source may show Viewing and Captured position as separate
lines from known callback-derived facts; inactive sources show only captured position.
Use current manual-entry mode and draft origin to distinguish entered-source-frame
wording from captured viewer positions. No readiness from hints or authority alone.

After either saved action, the existing status label says Alignment choices saved and
the guidance says Close VSView to resume Frame Compare. Hide stale keep-current help;
retain disabled actions and saved-result focus behavior. Show the exact frozen saved
outcomes in existing per-source outcome labels. Original evidence remains in collapsed
details with its original classification, including provisional rather than rejected.
Use relative/native font emphasis and wrapping, no fixed-size design or new theme.


### U2 controller checkpoint — saved state and active input basis

Controller inspected production changes and three offscreen screenshots. Direct Qt
reproductions found:

- After confirming a provisional comparison, its unchanged audio summary still says
  Visual confirmation required to use this hint. After confirming a different offset,
  the unchanged accepted summary can still look like current applied authority.
- Saved drafts stop receiving viewer callbacks, but the active source still displays
  Viewing: frame 108 after the actual current frame changes to 150.
- Entering an invalid source frame, switching to Known offsets and entering valid +5
  produces ready-to-confirm while showing the inactive frame error in both source
  status and error label.

U2-R decisions: after save, hide the pre-save audio summary labels; retain original
classification/facts in collapsed evidence details and saved outcomes in source lineup.
Do not mutate the original attempt or authority payload. Stop displaying Viewing after
save; frozen captured/entered positions remain available. Only active-basis validation
may drive displayed errors, matching existing readiness/save validation; preserve the
inactive drafts for switching back. Restore exact Entered source frame: {frame} copy
without a second literal frame. Regressions must cover confirm and keep-current with
mixed states, post-save viewer movement, invalid-frame to valid-offset basis switching
and switching back. Capture mixed-state saved screenshots (the original keep-current
capture used four identical reused authorities and did not exercise the full matrix).
No result/schema/callback observation change or layout redesign. A1 remains pending.


### U2 and U2-R acceptance

Repair task `01a0c873-4f36-7433-95e6-34d4d6a97fb1` ran Luna xhigh from
`2e6e836cffab34d969ae49265893003f9327b218` to
`c0fb947d49302a34587490cb885b45b5835ac03a`. Controller inspected every changed
line, mixed-state normal/narrow/enlarged saved screenshots, and full/static/native
proof logs. The repair hides stale pre-save summaries, retains immutable details,
removes frozen Viewing claims, scopes displayed errors to active input basis and
restores exact manual-entry copy. Controller independently passed all VSView tests
and CLI-doc tests without skips. Worker fresh distribution/isolated vsview install,
version/help and shipped-panel import passed. Evidence is indexed under
`.codex/cache/task-evidence/u2-r/COMMANDS.md`. Tracked-doc strict validation passed;
unrelated untracked plan links remain preserved. No physical-Windows claim.

### A1-R — repair known canonical Docker opt-in mismatch

Before final A1, a bounded writer will edit only `tools/verify_docker_integration.sh`
and its workflow-contract test. The existing broad verifier includes the opt-in
channel matrix but does not enable it, deterministically failing its zero-skip guard
and preventing the following hosted resource step. This defect was observed repeatedly
in F1–F5 and is now a concrete integration repair, not a new architecture decision.

Controller decision: pass the existing `FRAME_COMPARE_CHANNEL_CORROBORATION=1` into
the test container for canonical verifier invocations via the existing docker env-args
array. No new flag, dependency, opt-in framework or test exclusion. Keep streaming
resources excluded from the ordinary broad command and run them separately as before.
Keep the global zero-skip guard and exact process failure propagation. Contract tests
must prove the environment reaches Docker and retained guards still fail on skips.
Run a fresh-image full canonical verifier (not a focused substitute), require all
included tests to pass with zero skips, then run the exact opted-in resource suite.
Record source/image identities and complete logs. Separate repair commit:
`ci(alignment): enable channel proof in canonical Docker gate`.
Controller A1 full integration remains required after repair acceptance.
