# Product and UX package handoffs

This is the copy/paste handoff companion to the sole active authority:

- `docs/plans/2026-07-13-product-ux-execution-program.md`

This file does not introduce or override product decisions. If it conflicts with
the active plan, `AGENTS.md`, `docs/ENGINEERING_RUNBOOK.md`, observed source, or an
approved later plan amendment, stop and resolve the discrepancy before editing.

## How to use this pack

Two execution modes are supported:

- **Persistent controller mode (recommended):** pass the single master launch
  prompt below once. The main task dispatches bounded workers and reviewers, commits
  each accepted unit, updates the ledger, and continues until an approval or stop
  condition genuinely requires the maintainer.
- **Manual unit mode:** pass exactly one unit prompt to a fresh main Codex session
  after the preceding unit is integrated or otherwise accepted. That session is the
  controller and implementer for one unit and must not start the next.

Unit 6 is intentionally split into a product-contract gate and implementation.
Unit 7 is intentionally design-only. Unit 11 begins with a feasibility audit and
may correctly end in a documented deferral.

The active plan records the maintainer's narrow authorization for the persistent
controller to stage exact task-owned files and create local conventional commits.
Manual unit sessions do not inherit that authorization unless their user prompt
explicitly says so. Neither mode is authorized to create/switch branches, push,
open a PR, install dependencies, or change unrelated/external state.

## Shared controller contract for every unit

Every prompt below incorporates this contract by reference. The main session must:

1. Begin by reading, in order:
   1. `AGENTS.md`;
   2. `docs/ENGINEERING_RUNBOOK.md`;
   3. `docs/plans/2026-07-13-product-ux-execution-program.md`;
   4. this handoff file and the assigned unit prompt;
   5. `docs/current-architecture.md`;
   6. `docs/current-cli-contract.md` when the unit changes public behavior;
   7. `importlinter.ini`;
   8. only the process and boundary skills named by the unit.
2. Inspect `git status --short`, the latest integrated source, existing tests, and
   the unit's owner seams before editing. Preserve all unrelated user changes. Stop
   if the preceding ledger dependency is not complete or current code contradicts a
   frozen contract in a way that is risky to resolve locally.
3. Keep `update_plan` current for the assigned unit. Restate its goal, non-goals,
   public surfaces, owner seam, verification, rollback, and stop conditions before
   writing code.
4. In manual unit mode, act as the primary implementer. In persistent controller
   mode, dispatch exactly one bounded implementation worker for the current unit and
   retain integration ownership. Do not spawn an implementation swarm or delegate
   unresolved product/architecture choices. Use sidecars only for genuinely
   independent read-only evidence. No child may delegate again, edit overlapping
   files, choose a new product contract, or perform git operations.
5. Implement the smallest coherent solution inside existing owners. Protect
   architecture and maintainability as release requirements:
   - keep `cli/entry.py` a thin lazy composition root;
   - keep orchestration hotspots at composition level;
   - keep config, filesystem, subprocess, network, report, and browser policy behind
     their documented owners;
   - preserve `importlinter.ini` direction;
   - use typed immutable internal seams and existing error/atomic-write patterns;
   - preserve deterministic CLI/JSON/TOML/report contracts;
   - update authority docs in the same change as public or architectural behavior;
   - reject speculative abstractions, generic frameworks, compatibility shims,
     duplicate policy, dependencies without demonstrated need, and drive-by cleanup;
   - do not silence type/lint/test failures or weaken tests to accommodate the
     implementation.
6. Treat correctness, data safety, privacy, accessibility, performance, platform
   honesty, rollback, and failure behavior as part of the feature—not later polish.
   Validate external/persisted input before expensive or irreversible work. Never
   persist secrets, unsafe absolute paths, tracebacks, or untrusted HTML.
7. Add behavior-first tests at the owning boundary. Test negative paths, stream and
   exit-code behavior, malformed/legacy state, containment, partial failures, and
   side-effect absence wherever relevant. Avoid snapshots that merely mirror the
   implementation.
8. Run the unit's targeted proof while iterating, then the runbook full gate for
   every Python/product change:

   ```bash
   .venv/bin/pyright --warnings
   .venv/bin/ruff check .
   .venv/bin/bandit -c pyproject.toml -r src --severity-level medium
   .venv/bin/pytest -q
   UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
   ```

   Add Docker, runtime, Windows portable, or manual browser proof only when the
   changed surface requires it. If a required host proof is unavailable, label it
   documented-only; never claim it passed.
9. Inspect the complete task-owned diff and repository status before review. The
   implementation must be feature-complete for the assigned unit, with docs and
   fresh verification evidence, before requesting final review.
10. Spawn one fresh adversarial review subagent after verification. Use the
    configured `reviewer` role from `.codex/agents/reviewer.toml` when role routing
    is available and the launcher demonstrably applies that role. Otherwise spawn a
    fresh subagent with no inherited turns, explicitly require read-only behavior,
    and record it as an **unconfigured reviewer fallback**. Never claim that the
    fallback used the model, reasoning effort, sandbox, or developer instructions
    from `reviewer.toml`. The reviewer must not edit files, delegate, or perform git
    operations. Apply `model-selection` when choosing a configured role and require
    every reviewer to use `frame-compare-feature-review`, `review-request`, and only
    the boundary skills relevant to the reviewed unit.
11. Give the reviewer a bounded packet containing:
    - assigned unit and active-plan section;
    - task-owned diff and exact files changed;
    - public contracts and invariants;
    - non-goals and stop conditions;
    - targeted/full verification commands and observed results;
    - manual or platform proof gaps;
    - known risks and requested focus.

    Do not send the implementation transcript or ask for general impressions. Ask
    for concrete findings ordered by severity, with file/line evidence, user or
    production impact, and the smallest justified remedy. The reviewer must
    prioritize correctness, regressions, contract drift, data/security/privacy,
    architecture boundaries, maintainability/debt, performance/resource use,
    accessibility where applicable, and missing proof. Style-only comments are out
    unless they conceal a real risk.
12. Adjudicate every finding from the current source:
    - **accept:** evidence confirms it; fix it;
    - **modify:** the concern is real but scope/severity/remedy changes; implement the
      corrected remedy;
    - **reject:** only with stronger counter-evidence;
    - **defer:** only when non-blocking, with owner and concrete trigger recorded;
    - **validate:** name and run the exact missing proof before closure.

    Record identifier, severity, evidence, disposition, rationale, action, and
    verification. Fix all accepted/modified in-scope findings in the main session.
    No valid actionable issue may be left unfixed merely to finish the unit; a defer
    disposition requires a genuinely non-blocking rationale, owner, and trigger.
    Rerun affected targeted proof and the full gate when production code changed.
    Reuse the same reviewer for closure only if fixes materially changed the review
    surface or the accepted finding needs confirmation; do not demand duplicate
    clean reviews for an unchanged diff.
13. Run `closeout-verification`. In manual unit mode, update only the assigned row
    in the active plan's execution ledger. In persistent controller mode, follow the
    checkpoint protocol, which may also promote the next dependent row to `Ready`.
    Use the ledger's exact state definitions and record exact proof, review result,
    and next action. `Completed` and `Approved` require an immutable integrated
    reference. Without separate git/integration authorization, stop at `Verified /
    awaiting integration` or `Awaiting approval`. Do not mark the unit complete
    while a blocking finding, failed required proof, unapproved contract choice, or
    stop condition remains.
14. Report changed files, user-visible behavior, authority-doc changes, exact
    verification, reviewer findings/dispositions, remaining risks or documented-only
    proofs, and every subagent role used. For a configured role, read and report the
    actual `model` and `model_reasoning_effort` from its
    `.codex/agents/<role>.toml`. For an unconfigured fallback, report only launcher
    metadata actually exposed by the tool and state explicitly that no configured
    role/model attribution can be made.
15. In manual unit mode, do not stage, commit, push, open a PR, or begin the next
    unit unless the maintainer explicitly authorizes it. In persistent controller
    mode, follow the active plan's exact-file local commit/checkpoint authorization;
    never create/switch branches, push, open a PR, install dependencies, or broaden
    that authorization.

## Persistent master-controller protocol

The persistent controller applies `large-task-orchestration` and remains the only
authoritative task for the whole program. If a long-running goal mechanism is
available, the launch prompt explicitly authorizes creating one unbudgeted goal for
the active program; the controller must not mark it complete until every shipped or
maintainer-accepted deferred unit is closed and the active plan is ready for final
program closeout.

### Bootstrap checkpoint

Before Unit 1, the controller must:

1. inspect `git status --short` and preserve every unrelated change;
2. confirm the required `.venv/bin/*` tools exist. If they do not, stop and request
   explicit authority to run the `AGENTS.md` bootstrap command; persistent mode does
   not silently expand its dependency-installation permission;
3. confirm there is exactly one active plan for this workstream;
4. inspect this handoff pack and the active plan, including the prior adversarial
   review closure recorded below;
5. run plan-only structural proof and whitespace checks;
6. if these two workflow documents are not yet integrated, first inspect the index.
   If unrelated paths are already staged, pause rather than altering or committing
   the user's index. Otherwise stage exactly:
   - `docs/plans/2026-07-13-product-ux-execution-program.md`;
   - `docs/product-ux-package-handoffs.md`;
7. require `git diff --cached --name-only` to contain exactly those two paths, run
   `git diff --cached --check`, inspect the cached stat and complete cached diff, and
   stop on any unintended content;
8. create local commit `docs: add product UX execution workflow`;
9. reread the ledger from the committed base before dispatching Unit 1.

Do not stage the other pre-existing untracked plans, reviews, or user files visible
in the workspace.

### Unit execution loop

For the next ledger-eligible unit, the controller must:

1. set only that ledger row to `In progress` in the working tree and update its live
   `update_plan` state;
2. build the bounded worker packet from the active package section, the matching
   unit handoff, current source, and tests; extract its implementation/design
   contract rather than forwarding controller-only review, ledger, or git
   instructions to the worker; include the worker-safe skill set explicitly;
3. use the configured `worker` role from `.codex/agents/worker.toml` when the
   launcher demonstrably applies it; otherwise use a fresh no-inherited-turns
   subagent and record it as an unconfigured worker fallback without attributing the
   TOML model/effort;
4. permit exactly one writer for the unit. The controller performs no overlapping
   writes while the worker runs;
5. require the worker to return only `RESULT | FILES CHANGED | PROOF | ASSUMPTIONS |
   BLOCKERS`; the worker may run focused proof but may not update the ledger, review
   its own work, stage/commit, start another unit, or delegate;
6. inspect the actual files/diff rather than trusting the return summary. Stop on
   scope expansion, ownership conflict, unexpected public behavior, unrelated
   edits, or an unproved dependency;
7. complete any controller-owned integration, authority-doc update, and missing
   behavior-first tests inside the frozen unit scope;
8. run targeted proof and the complete runbook-required gate from fresh source;
9. dispatch the fresh independent reviewer using the shared review protocol and
   unit-specific focus; the implementation worker must never serve as reviewer;
10. adjudicate every finding. The controller—not the implementation worker—fixes all
    accepted/modified in-scope issues, then reruns affected targeted proof and the
    full gate when production code changed. Reuse the same reviewer only for
    material-fix closure;
11. branch closeout by outcome:
    - for a complete implementation or reviewed design awaiting approval, inspect
      the final task-owned diff/status, update the row to `Verified / awaiting
      integration`, confirm the index contains no unrelated pre-staged paths, stage
      exact unit files only, verify the cached path allowlist and cached diff/check,
      and create one conventional implementation/design commit;
    - for a blocked feasibility outcome, confirm and review the evidence, restore
      every task-owned partial production/test change to the integrated base without
      destructive git commands or touching unrelated changes, remove disposable
      experiments, prove the remaining diff contains only durable evidence/design
      records, confirm the index contains no unrelated pre-staged paths, then stage/
      inspect/commit only those records. If safe separation is impossible, pause
      without committing;
12. read the resulting implementation/design/evidence commit hash; change the
    current ledger row to `Completed`, `Awaiting approval`, or `Blocked`; when it is
    `Completed`, promote the next dependent row to `Ready`; record the hash plus
    exact verification and review result; run plan-only structural checks; verify
    the ledger-only cached diff; and create a separate mechanical commit such as
    `docs: record UX unit 2 checkpoint`;
13. if the row is `Completed`, continue automatically;
14. if the row is `Awaiting approval` or `Blocked`, stop dispatching, give the
    maintainer the durable contract/evidence and smallest required decision, and
    resume this same controller task after the answer;
15. after a maintainer approval or accepted deferral, update the row to `Approved`
    or `Deferred / accepted`, promote the next eligible row, run plan-only checks,
    create the mechanical decision checkpoint, and continue.

Do not issue a final completion response after an ordinary successful unit. Send a
concise progress update and continue the loop. Context compaction is expected; the
committed active plan, ledger, git history, and current `update_plan` are the recovery
state.

### Worker packet

Every implementation/design worker receives this exact shape:

```text
UNIT: <unit>
ROLE: configured worker/planner, or explicitly unconfigured fallback
WORKER SKILLS: frame-compare-feature-implement or the approved planning/design
process skill, plus only unit-relevant boundary/test/verification skills; explicitly
exclude large-task-orchestration, model-selection, review-request,
frame-compare-feature-review, closeout-verification, ledger, staging, and commit work
OBJECTIVE: <one bounded package outcome>
FILES: <expected owner files and tests; exact additions allowed by the plan>
DEPENDENCIES: <required ledger state and current integrated base>
INVARIANTS: <public contracts, owner boundaries, data/stream/persistence rules>
VERIFICATION: <focused commands the worker may run; controller reruns final proof>
OUTPUT: RESULT | FILES CHANGED | PROOF | ASSUMPTIONS | BLOCKERS
EFFORT BUDGET: one bounded implementation turn and at most one same-unit follow-up;
stop rather than broaden scope
STOP CONDITIONS: <package stops plus any source/plan discrepancy>

Do not delegate, perform git operations, edit the ledger, start another unit, or
choose a new public/architecture contract. Work directly in the shared workspace and
preserve unrelated changes.
```

Use the configured `planner` role only for Unit 6A when separate product-contract
planning is justified and the launcher demonstrably applies it. Use the normal
worker role for implementation and the Unit 7 design/prototype gate. Do not route
these units to `worker_luna`; they retain product, architecture, or UI judgment.

### Pause and terminal conditions

Routine successful checkpoints require no user intervention. Pause only when:

- Unit 6A's reviewed wizard contract awaits approval;
- Unit 7's reviewed report interaction contract awaits approval;
- Unit 5 cannot pass its rerun feasibility gate and needs accepted deferral;
- Unit 11 cannot provide honest blind behavior without a new render/report contract;
- a package hits its named stop condition;
- a required proof fails after bounded remediation;
- unrelated user changes overlap required files;
- the plan and current source disagree on product behavior or ownership;
- new authority, external coordination, branch/push/PR action, dependency
  installation, or other scope expansion is required.

After Unit 11 closes, the controller performs a program-wide ledger/diff/docs audit,
runs any final proof required by the accumulated surfaces, requests a final
program-level read-only review only if the combined integration surface materially
adds risk beyond the already reviewed units, and asks the maintainer before marking
the active plan `Historical`, pushing, or opening a PR.

## One-launch master prompt

Copy this prompt once into a fresh Codex task. It replaces repeated unit handoffs:

```text
Execute the complete Frame Compare product/UX program as its single persistent
authoritative controller. Create one unbudgeted long-running goal for this objective
if the goal mechanism is available. Do not stop after ordinary successful units.

Read and obey, in order:
1. AGENTS.md
2. docs/ENGINEERING_RUNBOOK.md
3. docs/plans/2026-07-13-product-ux-execution-program.md
4. docs/product-ux-package-handoffs.md, especially the Persistent
   master-controller protocol
5. docs/current-architecture.md
6. docs/current-cli-contract.md
7. importlinter.ini
8. the process/boundary skills named by the current unit

Use large-task-orchestration. Keep this main task as the sole controller. Execute
only the next ledger-eligible unit, dispatching one fresh bounded implementation or
design worker at a time with depth one and no git/delegation authority. Inspect the
actual shared-workspace diff and rerun all required proof yourself. Then dispatch a
separate fresh no-inherited-context read-only adversarial reviewer, adjudicate every
finding from source evidence, fix every accepted/modified in-scope issue in this main
controller, reverify, and integrate the unit.

You are authorized to stage exact task-owned files and create local conventional
commits for the workflow bootstrap, each reviewed unit, and mechanical ledger/
approval checkpoints exactly as defined in the active plan. Never use `git add .`.
You are not authorized to create/switch branches, push, open a PR, install
dependencies, or modify unrelated/external state.

Bootstrap the two workflow documents if they are not yet integrated, preserving all
other existing/untracked user files. If required `.venv/bin/*` tools are missing,
pause and ask for bootstrap/install authority before running `uv sync`; do not infer
that authority. Then run Units 1, 2, 3A, 3B, 4, 5, 6A, 6B, 7,
8, 9, 10, and 11 through the ledger state machine. Continue automatically after
each `Completed` checkpoint. Pause and ask me only at Unit 6A approval, Unit 7
approval, a Unit 5/11 feasibility decision, an explicit package stop condition,
overlapping user changes, failed required proof, or a genuinely new public/
architecture/authority decision. Resume this same task after my answer; do not ask
me to copy another package prompt.

For every unit, enforce production correctness, architecture ownership, strict
typing, deterministic public/persistence/report contracts, privacy/containment,
failure and rollback behavior, accessibility/performance where applicable,
behavior-first tests, same-pass authority docs, no hotspot dumping, no speculative
abstractions, no duplicate policy, no compatibility shims without requirement, no
drive-by cleanup, and no weakened quality gates. Update the durable ledger after
every integration. Report concise progress while working and provide a final
program closeout only when all units are shipped or explicitly accepted as deferred.
```

## Workflow review record

The manual-unit handoff pack received a fresh read-only adversarial review before
the persistent-controller addendum. Findings HND-001 through HND-004 covered durable
approval contracts, ledger state/integration semantics, canvas-policy drift, and
configured-role attribution; all were accepted, fixed, and confirmed closed. The
launcher did not demonstrate configured-role routing, so that review is recorded as
an unconfigured reviewer fallback with no TOML model/effort attribution.

The persistent-controller addendum then received a separate fresh read-only
adversarial review. Findings PC-001 through PC-005 covered blocked-outcome partial
work, pause authority, worker-safe skill routing, cached bootstrap proof, and missing
environment bootstrap authority. All were accepted, fixed, and confirmed closed.
That launcher likewise did not demonstrate configured-role routing, so the review is
recorded as an unconfigured reviewer fallback with no TOML model/effort attribution.

## Standard adversarial reviewer packet

The main session should adapt and send this after implementation and verification:

```text
Act as a fresh read-only adversarial production reviewer for Frame Compare. Do not
edit files, delegate, or perform git operations.

Review Unit <UNIT> from
docs/plans/2026-07-13-product-ux-execution-program.md. Read AGENTS.md,
docs/ENGINEERING_RUNBOOK.md, the assigned plan section,
docs/current-architecture.md, docs/current-cli-contract.md when relevant,
importlinter.ini, and the task-owned diff. Changed files: <FILES>.

Frozen contracts/invariants: <INVARIANTS>.
Non-goals/stop conditions: <NON_GOALS_AND_STOPS>.
Verification observed: <COMMANDS_AND_RESULTS>.
Known risks/manual gaps: <RISKS_AND_GAPS>.

Lead with concrete findings ordered by severity. For each finding provide a stable
identifier, priority, exact file/line evidence, failure scenario and impact, and the
smallest justified remedy. Prioritize behavioral regressions, public CLI/config/
JSON/TOML/report drift, data loss or disclosure, containment, import/layer violations,
hotspot growth, duplicated policy, speculative abstractions, performance/resource
cost, accessibility where applicable, and missing or weak tests. Do not report
style-only preferences. If no actionable findings remain, say so explicitly and
name any residual proof gap.
```

## Unit 1 handoff: CLI discoverability and input-folder opening

```text
Implement Unit 1 only from the active product/UX program. Read and obey the Shared
controller contract in docs/product-ux-package-handoffs.md and Package 1 in
docs/plans/2026-07-13-product-ux-execution-program.md. Use
frame-compare-feature-implement, cli-contract-boundaries,
runtime-integration-boundaries, architecture-boundaries, python-quality-boundaries,
python-test-design, verification-strategy, review-request, and
closeout-verification.

Goal: add the intentionally small `frame-compare inputs open` convenience and
improve CLI help/examples while preserving `comparison_videos` as the default
folder-first workflow. Reuse current root/config/path and safe platform-open seams;
keep entry.py to registration/lazy wiring. Use argument-safe native open behavior,
typed failures, and honest headless/container handling. Do not create missing input
directories, add positional media paths, change packaging, introduce a platform
framework, or broaden runtime behavior.

Required proof includes focused help/import and input-command tests covering path
spaces, missing folders, unsupported/failed openers, output/exit behavior, and
macOS/Linux/Windows boundary mocks, followed by the full runbook gate. If safe reuse
is not possible without packaging or architecture expansion, stop and defer the
open command rather than overengineer it.

After verification, spawn the fresh read-only adversarial reviewer required by the
Shared controller contract. Focus its packet on shell/process safety, platform
honesty, CLI/import contracts, hotspot growth, and whether this remained a genuinely
small feature. Adjudicate every finding, fix accepted issues, rerun proof, update the
Unit 1 ledger row, and stop without starting Unit 2.
```

## Unit 2 handoff: side-effect-free dry run

```text
Implement Unit 2 only after Unit 1 is complete. Read and obey the Shared controller
contract and Package 2 of the active program. Use frame-compare-feature-implement,
cli-contract-boundaries, architecture-boundaries, python-quality-boundaries,
python-test-design, verification-strategy, review-request, and
closeout-verification.

Goal: add `frame-compare run --dry-run` as a CLI-owned, typed, human/JSON planning
surface that validates config/options and discovers supported input filenames, then
exits before RunRequest construction. It must not initialize runtime dependencies,
probe media, run subprocesses or network calls, read/write caches, reserve/write run
folders, launch a browser/clipboard/VSPreview, or invent media-derived values. JSON
must be one stable allowlisted document and must not dump the effective config or
secrets. Preserve every existing normal-run contract.

Add sentinels proving forbidden owners cannot be reached, plus focused tests for
invalid config/options, no inputs, known versus unknown facts, human output,
JSON shape/streams, and lazy imports. Extract only a pure filename-discovery owner
if current discovery cannot be reused without side effects; stop instead of adding
dry-run branches throughout orchestration or simulating a second phase graph. Run
focused CLI tests and the full runbook gate.

Then spawn a fresh read-only adversarial reviewer. Focus review on hidden side
effects, import/runtime leakage, secret/config disclosure, JSON/public-contract
drift, duplicated planning logic, and false claims about unprobed facts. Adjudicate,
fix, reverify, update the Unit 2 ledger row, and stop.
```

## Unit 3A handoff: doctor-hint quality audit

```text
Implement Unit 3A only after Unit 2 is complete. Read and obey the Shared controller
contract and Package 3A of the active program. Use
frame-compare-feature-implement, cli-contract-boundaries,
runtime-integration-boundaries, python-quality-boundaries, python-test-design,
verification-strategy, review-request, and closeout-verification.

Goal: audit and improve the facts already carried by CheckResult.hint so failed or
warning checks give short, deterministic, platform/install-mode-appropriate next
actions. Preserve existing statuses, exit codes, human layout, and JSON field names.
Distinguish failure classes only when current checks can prove the distinction.

Do not add doctor --fix, execute repair commands, build a package-manager matrix,
guess unsafe install commands, or create a remediation framework. Prefer an honest
diagnostic/documentation pointer when install mode is unknown. Add focused doctor
owner and CLI rendering tests for each changed hint, escaping, JSON cleanliness, and
platform branches; then run the full gate.

Spawn a fresh read-only adversarial reviewer after verification. Focus on misleading
or unsafe instructions, platform/bundle drift, public JSON/exit regressions,
duplicated policy, and insufficient negative tests. Adjudicate, fix, reverify, update
the Unit 3A ledger row, and stop.
```

## Unit 3B handoff: final-selection summary

```text
Implement Unit 3B only after Unit 3A is complete. Read and obey the Shared controller
contract and Package 3B of the active program. Use
frame-compare-feature-implement, report-output-patterns, architecture-boundaries,
python-quality-boundaries, python-test-design, verification-strategy,
review-request, and closeout-verification.

Goal: add one concise verbose human summary of the final post-alignment frame
selection using the existing SelectionBreakdown. Preserve the existing Clip Overview
metadata output and correct any stale TODO claiming it is absent. Put formatting in
a focused owner parallel to fps_report.py and keep phase/coordinator changes at
composition level. Normal, quiet, and JSON behavior must remain unchanged.

Do not recalculate selection, create new runtime facts for presentation, grow
RunResult solely for live output, duplicate Clip Overview, or reorganize unrelated
CLI panels. Test post-alignment category counts/ranges, user-only and missing
breakdowns, output modes/streams, and phase placement; then run the full gate.

Spawn a fresh read-only adversarial reviewer. Focus on frame-domain correctness,
pre/post-alignment confusion, output-mode leakage, duplicate presentation policy,
hotspot growth, and weak edge coverage. Adjudicate, fix, reverify, update the Unit 3B
ledger row, and stop.
```

## Unit 4 handoff: run outcomes and read-only history

```text
Implement Unit 4 only after Unit 3B is complete. Read and obey the Shared controller
contract and Package 4 of the active program. Use frame-compare-feature-implement,
persistence-boundaries, cli-contract-boundaries, architecture-boundaries,
runtime-integration-boundaries, python-quality-boundaries, python-test-design,
verification-strategy, review-request, and closeout-verification.

Goal: preserve run_info.toml as immutable creation identity; add the minimal
versioned atomic run_result.toml outcome record and read-only `history list`,
`history list --json`, and exact-name `history open` commands. Records must be
deterministic, redacted, workspace-relative, containment-safe, tolerant of legacy
folders, and independently readable when another folder is malformed. Result-write
failure must not erase the original run outcome; failed-run recording is best
effort and must preserve the original exception/exit code.

Do not add replay settings yet, a database, migrations, delete/rename/search/fuzzy
matching, arbitrary path opening, or direct TOML parsing in CLI code. Keep lifecycle
changes minimal and service-owned. Cover schema/version round trips, atomic and
permission failure, success/warning/failure lifecycle, legacy/malformed folders,
ordering ties, exact JSON/streams, symlink/path traversal containment, report-open
failure, and no mutation of old runs. Update CLI and architecture authority docs as
required, then run the full gate.

Spawn a fresh read-only adversarial reviewer. Focus on data loss, partial writes,
error masking, secret/path leakage, symlink containment, deterministic ordering,
legacy behavior, JSON drift, lifecycle hotspot growth, and unnecessary persistence
abstraction. Adjudicate, fix, reverify, update Unit 4's ledger row, and stop.
```

## Unit 5 handoff: guarded safe rerun

```text
Implement Unit 5 only after Unit 4 is complete. Read and obey the Shared controller
contract and Package 5 of the active program. Use frame-compare-feature-implement,
persistence-boundaries, cli-contract-boundaries, architecture-boundaries,
runtime-integration-boundaries, python-quality-boundaries, python-test-design,
verification-strategy, review-request, and closeout-verification.

Begin with the required focused feasibility spike. Prove config plus recursive
explicit-field semantics can round-trip redacted; existing stat-based source
identities can be checked before a new run; current config/source owners can be
reused; and publishing can be disabled independently. The spike must be disposable
or test-owned. If this needs a broad ConfigSchema, RunRequest, source-selection, or
orchestration refactor, record evidence, run adversarial review of the deferral,
update the ledger as `Blocked`, and stop without shipping a partial rerun. Only a
later maintainer acceptance step may advance that row to `Deferred / accepted` and
promote Unit 6A.

If and only if the gate passes without a new product decision, add versioned atomic
run_replay.toml and `history rerun RUN_NAME`. Always create a new folder, validate
the complete current source set against recorded relative names/size/mtime, restore
only comparison-semantic settings, never persist secrets, and disable all publishing
unless the user explicitly supplies --with-publishing using current secrets and
safety checks. Do not replay presentation flags or cache-only policy. Clearly state
that stat identity is not a cryptographic byte guarantee and do not add full-video
hashing without separate measured approval.

Test redaction sentinels, explicit-field/tonemap semantics, all input mismatches,
path/symlink containment, old-run immutability, new-folder creation, publishing
default/opt-in, malformed/unsupported/version-drift records, legacy history,
streams/errors, and rollback behavior. Update authority docs and run the full gate.

Spawn a fresh read-only adversarial reviewer whether the outcome is implementation
or deferral. Focus on reproducibility claims, secrets, duplicate external side
effects, stale inputs, config semantic drift, source-manifest bypass, performance,
and architecture expansion. Adjudicate, fix/reverify when implemented, update the
Unit 5 ledger row accurately, and stop.
```

## Unit 6A handoff: wizard product-contract gate

```text
Complete Unit 6A only after Unit 5 reaches a ledger state that promotes dependent
work. This is a product/CLI interaction design
session, not production implementation. Read and obey the Shared controller contract
and Package 6's Product-contract gate. Use brainstorming,
execution-plan-authoring, cli-contract-boundaries, python-test-design,
verification-strategy, review-request, and closeout-verification.

Inspect the current wizard, defaults, config merge/write behavior, preset system,
existing tests, and comparison_videos workflow. Produce a decision-complete wizard
interaction specification covering exact goal names, exact field patches and shown
consequences, first-run versus existing-config behavior, preservation of unrelated
fields/secrets, input/reference confirmation, cancellation/validation, final review
copy, atomic write, non-TTY behavior, and whether guided goals are code-owned patches
or user presets. Include representative terminal transcripts and a test matrix.

Do not edit production code, invent vague quality labels, duplicate full defaults,
create a second preset/config engine, probe media, or import runtime-heavy owners.
Stop where a maintainer product choice is genuinely required and present the smallest
clear alternatives with tradeoffs.

Record the complete specification in the active plan or a tracked supporting
document linked from it. Run plan-only structural proof and spawn a fresh read-only
adversarial reviewer of that durable specification. Focus on UX friction, hidden
config mutation, ambiguous profile meaning, preservation/secrets, cancellation
safety, terminal accessibility, owner fit, and overengineering. Adjudicate and
revise the spec. Update the Unit 6A ledger row with the exact durable location and
`Awaiting approval`; it becomes `Approved` only after maintainer approval is
recorded with an immutable integrated reference. Then stop. Unit 6B must not start
from chat-only approval or an untracked artifact.
```

## Unit 6B handoff: wizard implementation

```text
Implement Unit 6B only when Unit 6A's exact interaction/profile specification is
recorded as maintainer-approved. Read and obey the Shared controller contract, the
approved Unit 6A spec, and Package 6 of the active program. Use
frame-compare-feature-implement, cli-contract-boundaries, persistence-boundaries,
architecture-boundaries, python-quality-boundaries, python-test-design,
verification-strategy, review-request, and closeout-verification.

Goal: implement exactly the approved guided ConfigSchema editor using existing
config load/merge/preset/atomic-write owners. Preserve valid unrelated settings and
secrets, begin first use from repository defaults, inspect filenames without probing,
show a final diff/review, and write once only after confirmation. Cancellation,
validation failure, no-TTY failure, and write failure must leave the old config
unchanged.

Do not change approved profile meanings, introduce another profile engine, duplicate
full TOML defaults, import runtime-heavy modules, expand into report UX, or perform
partial writes. Test every approved transcript path, first run, existing config,
secret preservation, cancellation boundaries, invalid recovery, non-interactive
behavior, and atomic failure without brittle full-screen snapshots. Update CLI docs
and run the full gate.

Spawn a fresh read-only adversarial reviewer. Focus on silent/destructive config
changes, profile drift from the approved matrix, secret loss/disclosure, cancellation
and TTY behavior, duplicate preset policy, lazy imports, maintainability, and test
fidelity. Adjudicate, fix, reverify, update Unit 6B's ledger row, and stop.
```

## Unit 7 handoff: report interaction design gate

```text
Complete Unit 7 only after Unit 6B is complete. This is a design/prototype gate, not
production report implementation. Read and obey the Shared controller contract and
Package 7 of the active program. Use interface-design, report-output-patterns,
browser:control-in-app-browser, python-test-design, verification-strategy,
review-request, and closeout-verification. Do not use frontend-design; this is an
interactive inspection tool, not a marketing surface.

Inspect the current generated report in the browser and document Intent, Palette,
Depth, Surfaces, Typography, and Spacing before prototyping. Preserve its restrained
cinema-black/charcoal technical identity with reference cyan and annotation amber
unless evidence supports a change. The signature interaction is the coordinate-
linked magnifier/pixel inspector. Build only disposable/ignored prototypes with
representative 2/3/4/N clips, varied aspect ratios, long labels, missing/error states,
desktop/keyboard/touch/reduced-motion/browser-zoom conditions.

Freeze magnifier dock/lens behavior, zoom/sampling honesty, ROI lock, linked pan/zoom,
grid layouts/overflow, keyboard and touch behavior, review data model, local-storage
scope, export/import identity rules, and the blind-mode leak definition. Provide
screenshots and interaction notes for maintainer approval. Do not edit production
viewer assets, add a framework, broaden the visual redesign, or treat attractive
mockups as accessibility/interaction proof.

Record the complete frozen interaction contract in the active plan or a tracked
supporting document linked from it; disposable prototypes/screenshots are evidence,
not the durable contract. After prototype validation, spawn a fresh read-only
adversarial reviewer of the durable contract and supporting artifacts. Focus on
inspection usefulness, information density, accessibility, responsive/touch
behavior, coordinate accuracy, state/error coverage, report architecture fit,
performance implications, and generic dashboard drift. Adjudicate/revise and update
Unit 7 with the exact durable location and `Awaiting approval`; it becomes `Approved`
only after maintainer approval is recorded with an immutable integrated reference.
Then stop. Unit 8 must not start from chat-only approval or disposable artifacts.
```

## Unit 8 handoff: magnifier, locked ROI, and pixel inspector

```text
Implement Unit 8 only after Unit 7's design contract is recorded as approved. Read
and obey the Shared controller contract, approved design artifacts, and Package 8 of
the active program. Use frame-compare-feature-implement, interface-design,
report-output-patterns, browser:control-in-app-browser, architecture-boundaries,
python-quality-boundaries, python-test-design, verification-strategy,
review-request, and closeout-verification.

Goal: implement exactly the approved docked inspector, optional floating lens,
locked source-coordinate ROI, approved zoom levels, and honest coordinate/pixel
presentation. Reuse existing image layers and centralize transform math. Keep report
and viewer owners focused; add payload facts only if current dimensions/transforms
cannot correctly supply them. Preserve slider/overlay/diff modes, static offline
operation, keyboard/touch access, focus, reduced motion, high-DPI/resize behavior,
and graceful image failures.

Do not introduce a web framework, orchestration coupling, false pixel precision,
scattered coordinate conversions, or unapproved visual redesign. Do not introduce
canvas unless the approved design or accurate sampling proves it necessary; require
a new maintainer decision only when canvas was not already approved. Add semantic markup,
JS state-harness, CSS contract, and interaction tests plus browser visual QA across
the approved matrix; then run the full gate.

Spawn a fresh read-only adversarial reviewer. Focus on coordinate/frame correctness,
transform drift, color/sampling claims, event/pointer leaks, memory/performance,
keyboard/touch/accessibility, mode regressions, payload growth, and viewer.js hotspot
debt. Adjudicate, fix, reverify including browser QA where affected, update Unit 8's
ledger row, and stop.
```

## Unit 9 handoff: multi-clip grid comparison

```text
Implement Unit 9 only after Unit 8 is complete. Read and obey the Shared controller
contract, approved Unit 7 design contract, and Package 9 of the active program. Use
frame-compare-feature-implement, interface-design, report-output-patterns,
browser:control-in-app-browser, architecture-boundaries, python-test-design,
verification-strategy, review-request, and closeout-verification.

Goal: add the approved viewer-only responsive grid with deterministic 2/3/4/N
layout/overflow and linked pan/zoom/ROI across visible cells. Preserve current modes,
report payload compatibility, local viewer state, visible reference/active labels,
keyboard order, touch behavior, and useful image area at constrained viewports.

Do not add grid to the public default_mode config in this slice, create virtualized
gallery/layout frameworks, detachable windows, arbitrary drag layouts, saved
dashboards, or duplicate transform state. Test every clip-count layout, long labels,
load failures, mode transitions, synchronized transforms, persistence, breakpoints,
keyboard/touch order, and magnifier interaction. Perform browser visual QA and run
the full gate.

Spawn a fresh read-only adversarial reviewer. Focus on N-source correctness,
responsive overflow, transform synchronization, performance/memory, accessibility,
state regressions, config/payload drift, and avoidable viewer hotspot complexity.
Adjudicate, fix, reverify, update Unit 9's ledger row, and stop.
```

## Unit 10 handoff: local review state and export/import

```text
Implement Unit 10 only after Unit 9 is complete. Read and obey the Shared controller
contract, approved Unit 7 design contract, and Package 10 of the active program. Use
frame-compare-feature-implement, interface-design, report-output-patterns,
persistence-boundaries, browser:control-in-app-browser, architecture-boundaries,
python-test-design, verification-strategy, review-request, and
closeout-verification.

Goal: implement the approved local-only bookmark/tag/note/preferred-clip model,
versioned report-scoped localStorage, and explicit versioned JSON export/import.
Validate complete imports before atomically replacing state; reject report/clip
identity mismatches by default; enforce type/size/frame/text bounds; render imported
content as text; keep current state intact on malformed, partial, unavailable-storage,
or quota failures. Exclude image data, secrets, external absolute paths, and
unrelated viewer preferences.

Do not add a backend, account/database, HTML writeback, implicit upload, report
identity remapping, generic persistence library, or unapproved freeform taxonomy.
Test corrupt/old/new schemas, malicious strings, oversized input, duplicates,
storage denial/quota, atomic replacement, export round trip, accessible empty/dirty/
saved/error states, and integration with grid/magnifier. Perform browser QA and run
the full gate.

Spawn a fresh read-only adversarial reviewer. Focus on data loss, injection,
identity confusion, privacy/path leakage, quota/partial failures, schema evolution,
accessibility, performance, and duplicated report state. Adjudicate, fix, reverify,
update Unit 10's ledger row, and stop.
```

## Unit 11 handoff: blind A/B feasibility and implementation

```text
Execute Unit 11 only after Unit 10 is complete. Read and obey the Shared controller
contract, approved Unit 7 blind-mode definition, and Package 11 of the active
program. Use frame-compare-feature-implement, interface-design,
report-output-patterns, browser:control-in-app-browser, architecture-boundaries,
runtime-integration-boundaries, python-test-design, verification-strategy,
review-request, and closeout-verification.

Begin with a complete identity-leak audit of visible labels/order, filenames/paths,
alt/accessibility text, tooltips, baked overlays, payload/report metadata,
downloads/exports, slow.pics links, local state, keyboard order, and styling. If true
concealment requires alternate clean renders, config/public payload changes, or a
new report format not already approved, stop and produce a decision-complete follow-
up plan. Do not ship cosmetic label hiding as blind A/B.

Only if the approved leak definition can be met with current artifacts should you
implement a per-session randomized neutral mapping, explicit reveal, separate vote
and reveal state, accessible neutral naming, and deterministic tests that prove no
identity appears before reveal. Preserve all non-blind report behavior and exported
review integrity. Test reload/session behavior, reveal/vote ordering, every metadata
and accessibility surface, grid/magnifier/review integration, and failure states;
perform browser QA and run all required gates, including Docker/runtime proof if
render or VS surfaces become in scope.

Spawn a fresh read-only adversarial reviewer whether the outcome is implementation
or principled deferral. Focus specifically on overlooked identity channels, false
blindness claims, randomization bias, accessibility leaks, persisted/exported state,
render/payload contract drift, and complexity disproportionate to value. Adjudicate,
fix/reverify if implemented, update Unit 11 accurately, and stop. Do not mark the
overall active program Historical; final program closeout remains a separate
maintainer-authorized task.
```
