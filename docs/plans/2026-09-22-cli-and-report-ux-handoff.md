---
search:
  exclude: true
---

Status: Reference
Scope: Copy-paste controller handoff for the active CLI and report UX implementation plan.
Owner: Maintainer-directed implementation controller.

# Implementation handoff

Paste the prompt below into the implementation controller session. This is an
execution handoff, not a second active plan. It preserves one authoritative
controller, one implementation writer at a time, controller-owned integration and
commits, risk-matched verification, and durable execution records. The runtime
mechanics below are the current Claude Code mapping; they are execution details,
not product requirements, and do not change shared agent defaults.

---

Act as the implementation controller for:

`/Users/tristan/Software/frame-compare/docs/plans/2026-09-22-cli-and-report-ux-improvements.md`

Repository: `/Users/tristan/Software/frame-compare`

Controller session name: `Implement CLI and report UX improvements`

Implement the complete active plan, verify the results, and maintain its execution
record. Use the current local checkout and one implementation writer at a time. Do
not create or switch branches or worktrees.

Dispatch each bounded implementation unit to the repository's configured Claude
subagent (`.claude/agents/<role>.md`) through the Agent tool in the foreground so
its structured result returns directly to the controller. The controller makes no
competing writes while a writer runs. Do not use Agent Teams, parallel Desktop
worktree sessions, polling, monitors, or callback messaging to wait for a worker.
A same-checkout peer-session mechanism may substitute only if it provably shares
this checkout, keeps one writer, returns results to the controller, keeps Git
controller-owned, and costs no more; otherwise use subagents.

## Inspect once, then execute

Read the full plan, applicable AGENTS.md instructions, the engineering runbook,
relevant current CLI/report authority sections, and the smallest applicable skill
set, including the manual-only `large-task-orchestration` skill. Inspect
`.claude/agents/`, `.claude/settings.json`, and relevant `.claude/skills/` entries
with their canonical `.agents/skills/` bodies before dispatch. Inspect branch,
HEAD, status, staged state, tracking state, and relevant commits. Treat any recorded
SHA as investigation context, not a required starting point.

Preserve unrelated work. Investigate drift and continue when safe; do not require
the user to reconfirm an explained commit advance or unrelated change. Pause only
the affected unit if overlapping work cannot be safely separated. Do not change
branches, create worktrees, reset, rebase, amend, clean, or discard existing changes.

## Frozen product decisions

- **Remove Fit width (↔), retain the orientation switch and every other floating
  control.** Keep their current placement and mode-dependent availability. Do not
  hide the remaining controls in a new menu. Retain internal width-fit calculations
  and supported saved width-fit state as specified by P4.
- Preserve the established charcoal/brass design and image-first layout.
- Implement P1–P6 completely, including copy, help, setup handoff, Inspector cleanup,
  browser-storage explanation, spatial-offset naming, and visual/accessibility proof.
- Preserve the plan's CLI, JSON, report, review-state, and persistence invariants.
- The active audio remediation plan owns terminal temporal-alignment and native
  VSView UX. Inspect its U1/U2/W1 evidence for P5; do not dispatch duplicate work or
  claim those dependencies complete without evidence.
- Coordinate published image recapture through the existing screenshot plan.
  Synthetic previews and historical images are not current visual acceptance proof.

## Worker roles and model selection

Keep the controller on its current model and effort. Workers use the checked-in
role definitions without overrides; inspect them before dispatch because they are
authoritative. At the time of writing:

- `worker_luna` (Sonnet, max effort): default for bounded P1–P4 implementation with
  settled outcomes and contracts.
- `worker` (Opus, medium effort): only when a unit needs material cross-owner
  judgment, difficult diagnosis, or proof interpretation.
- `reviewer` (Opus, high effort, read-only): only when independent review is
  justified under the runbook or requested by the user.

If a configured role or model is unavailable, report the exact limitation rather
than substituting silently. Do not edit shared role files for this run. Record each
worker's role and configured model/effort in the execution record. The controller
performs P5 reconciliation and P6 integration directly; add a read-only sidecar only
for clearly bounded independent evidence.

## Execution loop

1. Select the next dependency-ready unit: P1 → P2 → P3 → P4, P5 according to the
   actual upstream audio-plan status, then integrated P6.
2. Record HEAD, `git status --short`, staged files, and unrelated changes. Prepare
   the compact packet below.
3. Dispatch one foreground writer subagent. No nested agents.
4. On return, verify its start state, inspect every changed line, relevant callers
   and contracts, and actual proof output. A worker result is evidence, not
   acceptance. Run missing or invalidated checks.
5. Repair concrete findings by resuming the same subagent when the fix is adjacent
   and its context is current, otherwise with a fresh same-role worker given only
   the fresh baseline, finding, boundary, invariants, proof, and stop conditions.
6. The controller chooses the conventional commit message before staging, stages
   only task-owned files, and creates the implementation commit. Workers never
   stage, commit, or otherwise mutate Git.
7. Record acceptance and executed evidence in the plan and commit that record
   separately as `docs(plan): ...`. Never record intended proof as executed.
8. Continue through integration and closeout. Missing native/browser/upstream proof
   remains pending; do not mark the plan complete or Historical prematurely.

The implementation invocation authorizes scoped local conventional commits by the
controller. It does not authorize push, PR creation, release, publication, signing,
new dependencies, or changes to shared agent settings.

## Compact worker packet

- **UNIT / ROLE:** package ID/name, active plan section, and configured subagent.
- **STARTING SHA / STATUS:** exact HEAD and known worktree/staged changes; verify
  before editing.
- **OBJECTIVE:** one complete implementation outcome.
- **OWNER/WRITE BOUNDARY:** allowed production, test, and documentation owners;
  read-only inspection elsewhere is allowed. Controller owns plan records and Git.
- **DEPENDENCIES / INVARIANTS:** accepted commits, settled decisions, public
  contracts, preservation requirements, and non-goals.
- **SKILLS / AUTHORITIES:** smallest canonical skill set; the worker reads
  `AGENTS.md` itself.
- **ACCEPTANCE / VERIFICATION:** concrete behavior, edge cases, and focused proof
  the worker must run; proof reserved for the controller or P6.
- **STOP CONDITIONS:** unsafe baseline/overlap, consequential decision outside the
  unit, unmet acceptance within the boundary, or materially blocking unavailable
  proof. Repair ordinary task-caused failures within scope.
- **INTENDED COMMIT:** the message the controller will use; the worker does not
  commit.

Workers return `RESULT`, `ROLE`, `CONFIGURED MODEL / EFFORT`, `START SHA`,
`END SHA`, `FILES CHANGED`, `DIFF SUMMARY`, `PROOF EXECUTED`, `PROOF NOT EXECUTED`,
`SKIPS / LIMITATIONS`, `ASSUMPTIONS`, `BLOCKERS`, and `REMAINING RISKS`, with exact
commands and observed results rather than only "tests passed".

## Verification and completion

Follow the plan and repository command canon. Workers run focused proof; the controller
owns the current integrated Full Verification, real-browser checks, and documentation
build. This division does not waive an applicable per-unit gate. Reuse still-current
evidence; repeat only when changes, failures, or uncovered interactions invalidate it.

Inspect test skips and actual logs. Use the locked Node harnesses through repository
pytest. Layout, browser initialization, keyboard/focus behavior, narrow views, 200%
zoom, natural-image usability, and native VSView each need the proof specified by
P5/P6; a syntax check or adapted conversation preview cannot substitute for them.
Respect tool access denials; do not work around a rejected browser/security action.
Complete independent work and give a precise compatible-host handoff for unavailable
required proof. Do not wait indefinitely for another active workstream.

Do not add an automatic review loop. Request one fresh read-only `reviewer` only
if a concrete consequential risk remains after direct inspection and proof. Adjudicate
findings against current code, fix accepted issues, and rerun only affected proof.

Before finishing, inspect the task-owned diff and worktree, reconcile every P1–P6
acceptance item, update the execution record, and mark the plan Historical only if
the complete scope is accepted. Use conventional commits throughout.

Return: completed units and user-visible changes; local commit SHAs; executed checks
and inspected skips; browser/native evidence; upstream dependency status; actual
worker roles and configured models/efforts; and any outstanding blockers with an
exact next step. Do not claim full completion while required acceptance is pending.
