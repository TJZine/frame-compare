---
search:
  exclude: true
---

Status: Reference
Scope: Copy-paste controller handoff for the active CLI and report UX implementation plan.
Owner: Maintainer-directed implementation controller.

# Implementation handoff

Paste the prompt below into the implementation controller task. This is an execution
handoff, not a second active plan. It preserves the attached workflow's separate-task,
completion-callback execution model. Simplification removes repetition, not task
isolation, callback delivery, verification, or commit ownership. Its model settings
are the user's explicit choices for this run and do not change shared agent defaults.

---

Act as the implementation controller for:

`/Users/tristan/Software/frame-compare/docs/plans/2026-09-22-cli-and-report-ux-improvements.md`

Repository: `/Users/tristan/Software/frame-compare`

Exact controller task title: `Implement CLI and report UX improvements`

Implement the complete active plan, verify the results, and maintain its execution
record. Use the current local checkout and one implementation writer at a time.
Create a separate Codex task for each implementation unit using the app's new-task
tool (`create_thread`, also referred to as new_thread). Workers use the same saved
project and explicitly select its local/current checkout, not the default Git
worktree environment. Do not substitute in-turn collaboration subagents.

After dispatch, **end the controller turn**. The worker runs independently and sends
its result back through task messaging (`send_message_to_thread`). Resume on that
message. Do not poll, repeatedly inspect the worker, run a sleep/wait loop, create a
monitor, or keep the controller turn active waiting for completion. If callback
delivery is unavailable, leave the result in the worker's final response for the
user to forward; do not replace callbacks with monitoring.

## Inspect once, then execute

Read the full plan, applicable AGENTS.md instructions, the engineering runbook,
relevant current CLI/report authority sections, and the smallest applicable skill
set. Inspect `.codex/config.toml` and relevant agent configuration before dispatch.
Inspect branch, HEAD, status, locally recorded upstream state, and relevant commits.
Expand into adjacent code/configuration only when the unit needs it.

Handoff snapshot, to investigate rather than enforce blindly:

- Branch: `dev/v0.6.0-review-remediation`
- HEAD: `c5554ea784921d65fe9a748ba133854a3d67d956`
- Local tracking information: 11 commits ahead of origin; the live remote has not
  been verified. No push is requested.
- Before this handoff was written, the UX implementation plan was the only untracked
  file and there were no tracked modifications. Expect this handoff file too.
- The plan's older dirty audio-alignment baseline has since been committed. Inspect
  current state rather than assuming those changes still need preservation as edits.

Preserve unrelated work. Investigate drift and continue when safe; do not require
the user to reconfirm an explained commit advance or unrelated change. Pause only
the affected unit if overlapping work cannot be safely separated. Do not change
branches, create worktrees, reset, rebase, amend, or discard existing changes.

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

## Worker tasks and model selection

Use exactly these settings for delegated work:

- Bounded implementation, focused tests, straightforward docs, and narrow evidence
  collection: **`gpt-6-luna` with `xhigh` reasoning**.
- Other delegated work requiring material cross-owner judgment, difficult diagnosis,
  proof interpretation, or a justified independent review: **`gpt-6-sol` with
  `medium` reasoning**.

Keep the controller's current model. Set the worker task's `model` and `thinking`
explicitly at creation: Luna/xhigh or Sol/medium as above. Use the same explicit
settings for repair messages when needed; do not silently substitute another model
or effort. The repository's `worker_luna` role defaults to max, so its defaults do
not supply the requested task settings. Do not edit shared role files or switch to
in-turn subagents to resolve this. If requested settings are unavailable, report it
rather than silently changing them. Record each task's ID, role, model, and effort.

P1–P4 can normally start with Luna once their boundaries are confirmed. Choose Sol
only for a concrete need, not because a package spans several files. The controller
can perform P5 reconciliation and P6 integration directly. Do not add a planner,
monitor, reviewer, or further delegation without useful independent work to assign.

## Execution loop

1. Select the next dependency-ready unit: P1 → P2 → P3 → P4, P5 when its evidence is
   available, then integrated P6. Use one worker per cohesive unit; split only when
   a distinct outcome or proof boundary makes the work materially easier to verify.
2. Prepare the compact packet below. Record starting HEAD and existing
   task-owned/unrelated changes before dispatch so the worker can isolate its delta.
3. Create the worker as a separate task in the same local checkout. Give it the
   exact controller title and, when known, controller task ID for callback routing.
   State the dispatched unit/task in the final response and end the controller turn;
   defer further plan-file writes until its callback. Only the worker may write until
   it finishes or explicitly stops and returns control; no nested workers.
4. Resume on the worker's completion/blocker message. Confirm the returned unit,
   start/end SHA, changed files, commit, and proof. Read further worker output only
   when a concrete omission needs investigation after its response, not as polling.
5. Inspect every changed line, relevant callers/contracts, and actual verification
   output. A worker's success label is not acceptance. Reuse valid observed proof;
   run missing or invalidated checks and order focused repairs for real findings.
6. Resolve routine file-discovery and implementation questions locally. If a worker
   needs another file within the approved outcome, the controller can expand its
   boundary explicitly. Ask the user only for consequential decisions outside the
   accepted plan.
7. Workers create the exact requested conventional implementation commit only after
   meeting their acceptance/proof requirements. The controller validates that commit,
   records acceptance and evidence in the plan, and commits plan records separately.
   Stage only owned changes and preserve pre-existing staged/unrelated work. Send
   a focused repair to the worker task if needed, with a fresh baseline, boundary,
   proof, commit instruction, and callback. End the turn after that dispatch too.
8. Continue through integration and closeout. Missing native/browser/upstream proof
   remains pending; do not mark the full plan complete or Historical prematurely.

The implementation invocation authorizes scoped local conventional commits under
this loop. It does not authorize push, PR creation, release, publication, signing,
new dependencies, or changes to shared agent settings. The planning session that
prepared this handoff does not perform those implementation commits.

## Compact worker packet

Keep the original workflow's section names, with concise unit-specific contents:

- **UNIT:** package ID/name and active plan path/section.
- **STARTING SHA:** exact SHA and known worktree changes; verify before editing.
- **OBJECTIVE:** one complete implementation outcome.
- **OWNER/WRITE BOUNDARY:** allowed production, test, and documentation owners;
  read-only inspection elsewhere is allowed. Controller owns plan records.
- **DEPENDENCIES:** accepted preceding commits and relevant settled decisions.
- **INVARIANTS:** public contracts, preservation requirements, and non-goals.
- **ACCEPTANCE:** concrete behavior and edge cases required to accept this unit.
- **VERIFICATION:** exact commands, manual/browser proof, and controller-owned gates.
- **EXPECTED RETURN:** structured result and mandatory callback instruction below.
- **STOP CONDITIONS:** unsafe baseline/overlap, consequential boundary or contract
  expansion, unmet acceptance, or required proof unavailable. Stop without committing
  and send the blocker back. Repair ordinary task-caused failures within scope.
- **CONVENTIONAL COMMIT:** exact message for the single completed implementation
  commit; no amend. Read-only units explicitly say no commit.

Tell every worker: read applicable instructions; preserve unrelated work; implement
the smallest complete solution; reuse meaningful tests; inspect every changed line;
run specified proof and diff/status checks; never claim unexecuted proof. Commit only
the requested, verified, task-owned changes. Do not spawn agents, create tasks, push,
rebase, reset, change branches, publish, release, sign, add dependencies, or broaden
scope independently. Stop writes before sending a result or blocker to the controller.

## Mandatory completion callback

Include this instruction in every worker and repair prompt, with the actual
controller task ID filled in when available:

> At completion, use Codex task messaging to send your complete structured result
> to the task titled exactly `Implement CLI and report UX improvements`. Use the
> supplied controller task ID when available; otherwise resolve that exact title once
> through the task list. Make one delivery attempt and report whether it succeeded.
> Do not retry, poll, or monitor the controller. If direct delivery is unavailable or
> the title is ambiguous, leave the complete structured result in your final response
> so it can be forwarded manually. Send blockers through the same route after stopping
> edits. After sending your result, perform no further writes; end your turn.

Workers return these fields, including exact commands/results rather than only
“tests passed”:

`RESULT`, `CALLBACK_SENT`, `START SHA`, `END SHA`, `FILES CHANGED`, `COMMIT`,
`PROOF EXECUTED`, `PROOF NOT EXECUTED`, `ASSUMPTIONS`, `BLOCKERS`, `REMAINING RISKS`.

The worker's final response records the actual callback delivery result. The
controller uses the returned evidence to resume integration and dispatch the next
unit. Controller/worker back-and-forth stays in task messages, never a polling loop.

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

Do not add an automatic review loop. Request one independent Sol/medium review only
if a concrete consequential risk remains after direct inspection and proof. Adjudicate
findings against current code, fix accepted issues, and rerun only affected proof.

Before finishing, inspect the task-owned diff and worktree, reconcile every P1–P6
acceptance item, update the execution record, and mark the plan Historical only if
the complete scope is accepted. Use conventional commits throughout.

Return: completed units and user-visible changes; local commit SHAs; executed checks
and inspected skips; browser/native evidence; upstream dependency status; actual
worker task IDs/roles/models/efforts; and any outstanding blockers with an
exact next step. Do not claim full completion while required acceptance is pending.
