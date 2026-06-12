# Architecture Repair Goal Prompt

Status: Reference
Scope: Reusable kickoff prompt for a reviewed Frame Compare architecture repair program
Owner: Maintainer

This is a reusable goal prompt, not an active plan. Paste the prompt below into a
fresh Codex session when starting the workstream. The session must create or
update an active plan under `docs/plans/` only after it has gathered current
evidence and confirmed that durable handoff memory is needed.

## Prompt

You are Codex working in `/Users/tristan/Software/frame-compare`.

Goal: execute a full production architecture repair program for Frame Compare,
covering all material architecture pressure areas identified by evidence, not
just one hotspot.

Use the current repo authority docs as durable goal context:

- `AGENTS.md`
- `docs/ENGINEERING_RUNBOOK.md`
- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- `importlinter.ini`
- `pyproject.toml`

Follow `AGENTS.md` and `docs/ENGINEERING_RUNBOOK.md`. Treat this as high-risk
architecture and hotspot work. Keep live state in `update_plan`.

Start by reading:

- `AGENTS.md`
- `docs/ENGINEERING_RUNBOOK.md`
- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- `importlinter.ini`
- `pyproject.toml`
- The repo-local skills that match the work, at minimum:
  - `architecture-boundaries`
  - `execution-plan-authoring`
  - `verification-strategy`
  - `review-request`
  - `review-adjudication`
  - `closeout-verification`
  - Any implicated boundary skills, such as `cli-contract-boundaries`,
    `persistence-boundaries`, `python-quality-boundaries`,
    `python-test-design`, `report-output-patterns`, or
    `runtime-integration-boundaries`

Produce an evidence-first architecture inventory across the current hotspots
listed in `docs/current-architecture.md`, including:

- `src/frame_compare/orchestration/coordinator.py`
- Neighboring orchestration owners: `types.py`, `preparation.py`, and
  `execution.py`
- `src/frame_compare/errors.py`
- `src/frame_compare/services/report/**`
- `src/frame_compare/cli/entry.py`
- `src/frame_compare/services/alignment.py`
- Focused audio-alignment owners:
  `alignment_audio.py`, `alignment_correlation.py`,
  `alignment_consensus.py`, and `alignment_vspreview.py`
- `src/frame_compare/render/batch/orchestrator.py`
- `src/frame_compare/orchestration/doctor.py`
- `src/frame_compare/vspreview/adapter.py`
- Any additional pressure areas discovered from call sites, tests, import-layer
  constraints, public CLI/config contracts, Docker/runtime seams, or Windows
  portable/release surfaces

For each hotspot, cite docs, source files, tests, and call sites, then identify:

- current owner responsibility
- public CLI/config/release/import-layer exposure
- filesystem, subprocess, HTTP, browser, clipboard, Docker, Windows, or
  VapourSynth boundary concerns
- state transition, partial failure, cleanup, cancellation, or stale-result risk
- validation and error-handling ownership
- current tests protecting the seam
- import-layer constraints from `importlinter.ini`
- likely safe extraction or ownership seams
- reason to touch or not touch it in the first repair package

Create a reviewed architecture repair program with ordered repair packages.
Each package must have:

- owner seams
- files in scope and explicitly out of scope
- public contracts preserved or intentionally changed
- invariants
- acceptance criteria
- verification classification and exact commands
- rollback notes
- stop/replan triggers
- review gate before implementation

Rank candidate packages by:

1. production safety risk
2. likelihood of blocking upcoming features or runtime work
3. ability to preserve current behavior with strong proof
4. ability to stabilize or shrink a hotspot without inventing architecture
5. reviewability as a bounded unit

Do not implement until the plan has read-only adversarial review and findings are
adjudicated. Then implement package by package, verifying and reviewing each one
before moving to the next. Commit only if explicitly asked.

Non-goals:

- no new product features
- no broad cleanup or line-count-only rewrites
- no behavior changes without proof through public seams, contract tests,
  integration tests, or documented manual proof
- no public CLI/config/release/import-layer compatibility expansion unless
  explicitly scoped and documented
- no compatibility shims, legacy bridges, fallback API variants, or no-value
  forwarding owners without maintainer approval
- no eager VapourSynth imports from CLI help or simple command paths
- no ad hoc config/env reads outside the documented owners
- no filesystem persistence outside existing persistence owners
- no Docker, Windows portable, dependency, lockfile, build, or packaging changes
  without reviewed approval and the required verification path

Close only when all material hotspot packages are repaired or explicitly
deferred by reviewed replan with owner, risk, and revisit trigger. Update
`docs/current-architecture.md`, `docs/current-cli-contract.md`,
`docs/ENGINEERING_RUNBOOK.md`, generated docs, or active plan files in the same
pass when ownership truth, public contracts, verification policy, or workflow
authority changes. Run required verification and report exact observed results.

## Expected Deliverables

- Evidence inventory across current hotspots and newly discovered pressure areas.
- Prioritized architecture repair program covering all material hotspots.
- Rejected alternatives and explicit deferrals.
- Active tracked plan only if durable cross-session handoff memory is needed.
- Read-only adversarial plan review and adjudication before implementation.
- Package-by-package implementation only after the package is approved.
- Package verification summaries with exact observed commands.
- Package review/adjudication summaries before moving to the next package.
- Same-pass authority doc updates when architecture or public contract truth
  changes.
- Final net architecture audit, residual risk list, completed package list, and
  deferred package list.

## Stop Or Replan Triggers

- Evidence contradicts current authority docs and cannot be safely corrected in
  the same pass.
- Owner seam is undecided.
- Public CLI/config/release behavior would change implicitly.
- Import-layer changes are required but not scoped.
- A package grows a hotspot without a better reviewed decomposition.
- Behavior must change without stable proof.
- Docker, Windows, VapourSynth, FFmpeg, browser, clipboard, HTTP, or filesystem
  proof is required but no environment path is named.
- Dependency, lockfile, build, packaging, or release-path changes become
  necessary.
- Tests fail for unrelated reasons.
- User changes overlap planned files.
- Review finds material architecture, correctness, security, public-contract, or
  verification blockers.
