---
search:
  exclude: true
---

Status: Active
Scope: Implement the accepted findings of the 2026-10-08 comprehensive review.
The maintainer authorizes separate Codex implementation chats, local commits on
the current branch, and the decisions recorded below. Pushes, PRs, releases,
signing, dependency changes, and live-service calls remain out of scope.
Source: `agent/e2e-test-strategy` at `58e50a6d48c0004b63f60b9b3ba53c1ac4b31537`.

# Review remediation

## Inputs and authority

- Findings: `docs/reviews/comprehensive-review-2026-10-08/REPORT.md` (F-001–F-021,
  probe index P-01–P-16). The finding text is the defect specification. Each unit
  reads, in full, the findings it owns and the matching package in that folder's
  `REMEDIATION.md`.
- `REMEDIATION.md` is the draft this plan supersedes. Where they differ, this plan
  wins: it records the maintainer's decisions, merges packages into units, and
  sets ownership and order. Its package text still supplies scope, out-of-scope
  lists, and risks.
- `NEEDS-OBSERVATION.md` lists the physical and live acceptance that stays open
  after implementation (see "Acceptance handoff").
- Repository rules: `AGENTS.md`, `.agents/project.md`, `docs/ENGINEERING_RUNBOOK.md`,
  `docs/current-architecture.md`, `docs/current-cli-contract.md`, `importlinter.ini`.
  Use the shared `develop-code`, `design-code`, `review-code`, and `verify-code`
  skills for their responsibilities and `orchestrate-implementation-chats` for
  dispatch.

## Maintainer decisions (2026-10-08)

| ID | Decision | Effect |
| --- | --- | --- |
| D-01 | Source builds require PowerShell 7. Published-bundle install, launch, and update keep Windows PowerShell 5.1 support. | U6: early, precise PS7 prerequisite refusal on the source route before any bootstrap, sync, or output mutation. |
| D-02 | User-authored symlinked preset directories stay permitted. | U11: document that `preset save` writes to the resolved target; no code change, no containment claim for presets. |
| D-03 | A full portable reinstall installs into a fresh directory, preserving user config and data. In-place overlay of a full ZIP is not supported. | U6: document the route; backups record the runtime identity of the bundle that created them; `list-backups` and `rollback` refuse identity-less or mismatched backups before any file changes. |
| W-1 | Warnings become typed records. | U10: producers emit structured warnings (source, severity, message, detail); the CLI renders from fields; the text parser and the coordinator's `"align:"` prefix filter are deleted; JSON and run-record warning strings stay byte-identical. |

Adjudications of the review made when planning:

- F-007 is lower impact than its S2 rating: the verifier deletes only its own
  conventional output folder. The fix is still cheap and is kept (U5).
- F-009: exclude all local, ignored residue that no image needs, not only `.tmp`
  (U5).
- F-016: delete the orphan color policy outright; no shim (total-replacement stance).

## Constraints copied into every unit

1. Work in `/Users/tristan/Software/frame-compare` on `agent/e2e-test-strategy`.
   Never switch branches, push, open PRs, rebase, amend, reset, stash, or create
   worktrees. Children never stage or commit; the orchestrator owns Git.
2. Edit only the files your unit owns (unit table). Before editing anything
   else, ask the orchestrator for an ownership transfer. Never touch `.codex/`,
   `.handoff/`, `tools/old_corr.py`, `tools/old_consensus.py`, `docs/TODO.md`, or
   `docs/reviews/`.
3. Shared documents belong to the orchestrator: `docs/current-cli-contract.md`,
   `docs/current-architecture.md`, `docs/ENGINEERING_RUNBOOK.md`, `docs/api.md`,
   `CHANGELOG.md`, and this plan. Return any needed wording as exact proposed
   text in your report instead of editing them. Unit-specific user docs listed in
   the unit table are yours to edit.
4. Preserve the product obligations in `AGENTS.md`: runtime-free help and version,
   typed sanitized errors and exit codes, machine-clean JSON stdout, deterministic
   artifacts, owned cleanup and caller-owned injected resources, explicit
   persistence and atomic writes, audio/video authority, a valid zero offset
   distinct from absent evidence, manual provenance, isolated webhook transport,
   and separate Docker and Windows proof.
5. Total replacement: delete superseded paths. Add no compatibility readers,
   shims, re-exports, migrations, or kept-alive fields without a real consumer.
   Simple must still mean good ownership and structure; improve module layout
   when your change makes the better structure clear.
6. Tests: first reproduce the finding's failure (the probe command in REPORT.md is
   the reference) and record that the new regression fails before your change.
   Prefer the real path: the installed CLI through the existing `tests/e2e`
   harness, or real children, files, and the production modules. Use focused unit
   tests only for numeric, lifecycle, or boundary behavior that is cheaper and
   more sensitive there. Extend existing test files and harnesses; do not build a
   new harness. Never loosen an assertion or add a skip to pass.
7. Cheap checks only in child chats: focused pytest selections without `-n`,
   `pyright` on touched paths, `ruff check`/`ruff format --check` on touched
   paths, and small probes under `.tmp/remediation-2026-10-08/<unit>/` (gitignored).
   Never run the full native suite, Docker, the browser smoke, media E2E, or
   `zensical`; the orchestrator runs those. Never run `uv sync`/`uv lock` or
   change dependencies. Never contact a live service.
8. Stop and report `blocked` if a fix would need: a change to a persisted format or
   public JSON/CLI contract beyond this plan, a new dependency, a decision listed
   as open, another unit's files, or an assertion loosened to pass.

## Units

Presets come from `.codex/agents/*.toml`. Read the TOML and pass its `model` and
`model_reasoning_effort` explicitly to `create_thread`. Put its
`developer_instructions` at the top of the child prompt, and report each child's
actual model and effort. The orchestrator may swap `worker_luna` for `worker` when
a unit turns out to need deeper judgment; record why.

| Unit | Findings | Preset | Owned files (plus their focused tests) | Wave |
| --- | --- | --- | --- | --- |
| U1 Run cancellation | F-001 | `worker`, design checkpoint | `runner.py`; `orchestration/execution.py`, `phases.py`, `coordinator.py`, `run_result_lifecycle.py`; `render/batch/orchestrator.py`; `vsview/adapter.py`; `services/run_result_record.py` writer paths only after U4 is integrated | A |
| U2 Tonemap probe isolation | F-002 | `worker_luna` | `vs/tonemap_runtime.py` and its probe launch; `utils/subproc.py` only if the policy belongs there | A |
| U3 Config input boundaries | F-003, F-004, F-005 | `worker_luna` | `config/schema_sources.py`, `loader.py`, `presets.py`, `schema_models.py`, `errors.py`; `orchestration/preflight.py` path normalization | A |
| U4 Persisted numeric recovery | F-006 | `worker_luna` | `services/run_result_record.py` parsers; `analysis/cache_io.py` | A |
| U5 Docker verifier, context, CI | F-007, F-008, F-009 | `worker_luna` | `tools/verify_docker_integration.sh`, `.dockerignore`, `.github/workflows/docker-integration.yml`, `tests/workflows/` | A |
| U6 Windows install and update | F-010, F-011, D-01, D-03 | `worker` | `tools/windows_portable/**`, root `install.cmd`/`install.ps1`, `docs/windows-portable.md`, `INSTALL-WINDOWS.md`, `tests/windows_portable/` | A |
| U7 Report viewer state | F-012, F-013 | `worker` | `services/report/assets/viewer.js` (Blink and the review import controller), `viewport.js`, `review_state.js`; `tests/services/*_harness.js` and their Python drivers | A |
| U8 Orphan color policy | F-016 | `worker_luna` | `vs/color.py`, the unused `ColorProps` in `vs/types.py`, `vs/__init__.py` exports, `tests/vs/test_color.py` | A |
| U9 Portable path assertion | F-021 | `worker_luna` (or the orchestrator directly) | `tests/orchestration/test_alignment_report.py` | A |
| U10 Typed warnings and truthful summaries | F-014, F-015, W-1 | `worker` | warning producers and carriers, `cli/output.py`, `orchestration/phase_alignment.py`, `services/alignment.py` warning text, `services/alignment_presentation.py` | B (after U1 and U4) |
| U11 Documentation reconciliation | F-017–F-020, D-02 | `worker_luna` | `docs/guides/*.md`, `docs/getting-started/*.md`, `docs/reference/*.md`; contract text returned to the orchestrator | C (after all code units) |

Wave A units run in parallel; their owned files are disjoint. If a unit needs a
file another unit owns, the orchestrator serializes the two. Wave B starts after
U1 and U4 are integrated and committed, because U10 changes the execution state
and run-result paths they touch. Wave C documents the final behavior.

### U1 — Observe the first Ctrl+C at every admission and commit point

Specification: F-001 and REMEDIATION P1. Mechanism verified at planning:
`execute_phases` awaits `phase.execute`, but synchronous executors never yield, so
asyncio.run's first-SIGINT task cancellation is not delivered until the next real
`await`. Later phases, render-unit admission, output application, and
`record_completed_run_result` can still run.

Required behavior after the first SIGINT:

- No new phase starts, no further phase output is applied, and no new render unit
  or alignment work is admitted.
- No review, manual-override, or cache result is persisted after the interrupt.
- The run record goes through the existing failure path (not `completed`), and
  the process exits 130.
- In-flight work stops cooperatively where its owner supports that (the VSView
  wait terminates and reaps its child; the render pool cancels unstarted units and
  lets running units finish within a bound) and drains before exit.
- The earliest real failure still wins, a second SIGINT keeps its current
  behavior, and injected resources stay caller-owned.

Design checkpoint (mandatory): before writing production code, trace every
synchronous executor and return a short design note to the orchestrator, then
wait for approval. Preferred direction: one run-scoped, thread-safe stop signal
owned by the run. Each synchronous phase executor runs off the event loop with
that signal, the async wrapper sets it on `CancelledError` and awaits a bounded,
shielded drain, and owners check it at admission points. This lets the loop
receive cancellation without abandoning work. The note must settle whether
VapourSynth core/environment, Rich progress, and interactive prompts are safe off
the main thread. If they are not, propose the alternative: checkpoints on
`asyncio.current_task().cancelling()` between phases, output application, and
commit, plus owner-level stop hooks for the blocking waits. The orchestrator may
ask a `deep_reviewer` chat to challenge the note. Do not build a general process
framework.

Proof: turn P-02's real runner/SIGINT/child/coordinator probe into a regression in
the existing lifecycle tests (it must fail before the change). Assert: no later
phase or unit, a failure record, the child reaped, exit 130. Keep the existing
audio and webhook repeated-cancellation tests and the VSView reaping tests passing
as distinct obligations. Contract-doc delta: the interrupt outcome, if the contract
describes it.

### U2 — Isolate the tonemap capability child

F-002, REMEDIATION P2. Launch the probe so that the current working directory and
inherited `PYTHONPATH`/user site cannot shadow installed modules, while keeping the
runtime and plugin variables native loading needs. Reuse the existing isolation
policy if one owner already fits; no upward `vs`→`vsview` import. Proof: real child
with a hostile `vapoursynth.py` in cwd and a hostile `PYTHONPATH` entry: the marker
is never imported. Probe result and fallback behavior are unchanged for a clean
environment. Native libplacebo is absent on this Mac; the orchestrator's Docker
gate supplies the real capability proof.

### U3 — Typed errors for invalid config input

F-003, F-004, F-005, REMEDIATION P3. At the file and schema owners:

- invalid UTF-8 in config and presets becomes the existing sanitized config or
  preset error;
- NUL and other filesystem-unrepresentable path values are rejected at the path
  boundary before reservation or writes;
- non-finite lead/trail exclusions are rejected by the schema.

Proof through the installed CLI in `tests/e2e` (`test_cli_errors.py`,
`test_cli_config.py`): JSON mode keeps stdout machine-readable with exit 2,
human mode prints the typed error, and the config bytes are unchanged; plus
`preset apply` with invalid bytes. Keep finite, short, and empty window behavior.
No global `Exception` catch; no broad `ValueError` conversion that could hide
invariant bugs.

### U4 — Persisted numerics recover at their parsers

F-006, REMEDIATION P4. Convert numbers safely inside the run-record and analysis
cache parsers. An oversized value makes that one entry unavailable: history keeps
valid siblings and `history open` returns the typed unavailable result; normal
analysis treats the entry as a corrupt cache miss and recomputes; cache-only mode
gets its typed refusal. Proof: the `10**400` cases from P-03 through `history list
--json` and the real acquisition path, with valid controls. Do not coerce booleans
or weaken cache identity.

### U5 — Docker verifier owns its output; context and CI match real inputs

F-007, F-008, F-009, REMEDIATION P5 and P6.

- The verifier writes each run's E2E artifacts to a fresh invocation directory
  under `generated/e2e/`, prints that path, and never deletes earlier runs. The
  workflow artifact upload keeps working on a fresh CI checkout.
- `.dockerignore` excludes local ignored residue that no image needs: `.tmp`,
  `.handoff`, `.codanna`, `.desloppify`, `.agent`, `.hypothesis`, `.uv_cache`,
  `site`, `tools/old_*.py`. Confirm that nothing the Dockerfile copies is excluded.
- The Docker workflow path filter adds `tools/checkout_source_commit.sh` and
  `.dockerignore`, keeping the docs-only exclusion and the all-base-branch policy.

Proof: the existing workflow-contract tests extended with positive and negative
selection controls; a sentinel test that the verifier leaves a previous artifact
directory intact on success and early failure (fake Docker, as in P-04). The
orchestrator's canonical Docker gate checks the image sentinel: the same harmless
`.tmp` file must be absent from the production image.

### U6 — Windows install, source prerequisite, and backup identity

F-010, F-011, D-01, D-03, REMEDIATION P7 and P8.

- Both published shims read the install-state file explicitly as UTF-8 in a form
  that Windows PowerShell 5.1 supports. The state writer is unchanged.
- The root `install.cmd` source route and the source installer detect PowerShell 7
  first and refuse with a precise prerequisite message before any uv, bootstrap,
  or output mutation. The published bundle keeps its 5.1 fallback. Update the
  Windows docs to state PS7 for source builds.
- Each update backup records the runtime/requirements identity of the bundle that
  created it. `list-backups` marks, and `rollback` refuses, backups whose identity
  is missing or differs from the current bundle, before changing any file.
  Identity-less legacy backups are refused, not migrated.
- Docs: a full runtime reinstall goes into a fresh, empty folder; user config and
  data are preserved; overlaying a full ZIP onto an existing root is unsupported.

Proof on this Mac: the existing `tests/windows_portable/` contract tests extended
for each behavior (PowerShell-dependent cases will skip here; report them as
skips). Physical Windows acceptance is O-01, O-02, and O-03 in the handoff below;
do not claim it.

### U7 — Report viewer: Blink pause intent and import preview

F-012, F-013, REMEDIATION P9 and P10.

- Blink: separate the user's pause intent (explicit or reduced-motion) from
  temporary gesture suspension. Derive the effective timer and control state at the
  Blink owner, migrate the direct boolean writes, and delete the shared flag.
  Pan, pinch, and Lens completion or cancellation must not clear the user's pause.
- Review import: compute the selected candidate once per conflict policy; the
  preview counts come from local→candidate, and apply uses that same candidate.
  Fix `tests/services/review_state_harness.js:87`, which currently pins the
  mismatch.

Proof: the existing Node viewer and review-state harnesses, exercising the
production handlers and timer (P-07 is the reference). Cover initially running vs
paused, reduced motion, each gesture's completion and cancel, and each conflict
choice with preview equal to the applied delta. Keep validation, quota, and
atomic-rollback proofs. The orchestrator runs the real-Chrome browser smoke.

### U8 — Delete the orphan color policy

F-016, REMEDIATION P13. First prove there is no real consumer: production
imports, plugin entry points, persisted data, scripts, and tools. Then delete
`vs/color.py`, the unused `ColorProps`, its `vs/__init__.py` exports, and the
mock-only tests. Keep the active encoder, `tonemap_conversion`, and `props` range
proof. If a real consumer turns up, stop and report it. The orchestrator
regenerates `docs/api.md`.

### U9 — Portable terminal path assertion

F-021, REMEDIATION P15. Keep the row-zero and full-path obligation while making
the assertion independent of checkout depth and Rich wrapping. Proof: the test
passes with both the deep basetemp that failed and a short one, and still fails if
the path or row is wrong. Do not change product output width.

### U10 — Typed warnings and truthful applied summaries (wave B)

F-014, F-015, W-1, REMEDIATION P11 and P12.

- Introduce one typed warning record (source, severity, message, optional
  detail) owned at the lowest layer that producers and the CLI can share under
  `importlinter.ini`. Producers construct it directly. Severity and source are
  never inferred from message text.
- Migrate every `warnings: list[str]` carrier (about 25 sites) to the record.
  JSON output, run records, and post-upload deduplication project the record to
  the exact strings emitted today; prove byte-identical output for the existing
  JSON and record fixtures.
- Delete `_warning_presentation_from_string`, the `" because "` and `":"`
  splitting, and the coordinator's `startswith("align:")` filter; select alignment
  warnings by source.
- F-015: both applied-summary owners say "alignment applied" for any applied
  result. Review counts and unavailable/needs-confirmation wording stay unchanged.

Design checkpoint: return the record's owner module, its fields, and the list of
producers to the orchestrator before migrating. Proof: an identical unapplied
result with a neutral label and with a label containing "skipped", ":", and
" because " renders with identical severity, source, and detail; a genuinely
skipped warning still renders as skipped. Manual zero and nonzero, computed,
cached, and reviewed summaries. The architecture doc's ownership text is an
orchestrator delta.

### U11 — Documentation reconciliation (wave C)

F-017–F-020, D-02, REMEDIATION P14. Remove the nonexistent wizard upload toggle,
describe the report header's localized date and time, make the offscreen-evidence
tier consistent (historical Linux-container offscreen proof versus the unverified
X11 wrapper and visible desktop), and add the metrics condition to the
fastest/cache-only guidance. Document D-02's preset-symlink behavior. Return
contract-file text to the orchestrator. Proof: `tests/test_cli_contract_docs.py`;
the orchestrator runs the strict site build.

## Orchestrator procedure

1. Baseline: record HEAD and `git status --porcelain`. The tree should contain only
   the untracked `docs/prompts/`, `docs/reviews/`, and this plan. Commit those
   first as one docs commit, for example
   `docs(reviews): record comprehensive review and remediation plan`.
2. Resolve this chat's real thread and host IDs and the human turn that
   authorized this plan. Dispatch wave A per `orchestrate-implementation-chats`,
   using self-contained handoffs: unit section, constraints, findings and REPORT.md
   paths, owned files, preset settings, and the callback route. Record a dispatch
   map in the execution record below. When nothing useful remains, end the turn;
   callbacks resume you. Do not poll.
3. Handle the U1 and U10 design checkpoints yourself; use `deep_reviewer` for U1
   if the thread-affinity question is not clear-cut.
4. On each completion: check the actual diff against the unit's owned files and
   plan clauses; run the cheap static gates (`pyright --warnings`, `ruff check .`,
   `ruff format --check .`, `bandit -c pyproject.toml -r src --severity-level medium`,
   `lint-imports --config importlinter.ini`) and the unit's focused tests; apply
   returned doc deltas and regenerate `docs/api.md` if signatures changed. Then make
   one Conventional Commit for the unit, staging paths explicitly (never
   `git add -A`). Reuse the same child for corrections.
5. After each wave, send the wave's commit range to one `reviewer` chat (Sol,
   high). It reviews against this plan, and its report must include:
   - a deviations register (keep a deviation only when it is strictly better,
     with evidence);
   - an over-engineering hunt in source and tests (shims, fix-series residue,
     redundant or mock-heavy tests);
   - a test map with one proving test per finding;
   - a structure and ownership check.
   Adjudicate its findings with evidence before acting; send accepted fixes back to
   the owning child.
6. Heavy gates, once, at the end, serially, never overlapping:
   - full native suite `uv run --no-sync pytest -q -n4 --dist loadgroup`;
   - real-Chrome browser smoke (U7);
   - `bash tools/verify_docker_integration.sh`, then the production-image `.tmp`
     sentinel check (U1, U2, U4, U5);
   - `uv run --no-sync python scripts/generate_api_docs.py --check`;
   - `uv run --no-sync zensical build --clean --strict` if the docs group is
     installed;
   - the streaming-resource proof only if U1 changed audio collector cleanup.
   Rerun after any fix that invalidates a result. Record commands, durations,
   counts, and every skip reason.
7. Add the user-facing changes to `CHANGELOG.md` under Unreleased (config
   validation errors, viewer fixes, Windows PS7 source prerequisite and
   backup-identity refusal, Ctrl+C behavior).
8. Write the execution record and the acceptance handoff below, set this plan's
   status line to state that implementation is complete and physical acceptance
   is open, and stop. Final message: commits (SHA and subject), units with their
   preset and actual model/effort, gate results, deviations, and open acceptance.

## Acceptance handoff (after implementation)

These items need the maintainer or a physical host. They are not claimed by any
gate above. Use the exact steps in `NEEDS-OBSERVATION.md`.

- O-01: Windows PowerShell 5.1, non-ASCII bundle path, `version` and `list-backups` (U6).
- O-02: root `install.cmd` source route without PS7 refuses early; with PS7, it
  builds (U6).
- O-03 (reframed by D-03): a fresh-directory reinstall; an old identity-less or
  mismatched backup is refused by `rollback` before any change (U6).
- O-09: real first and repeated Ctrl+C during native review, VS render, and
  FFmpeg render, natively and on Windows portable (U1).
- O-10: physical gestures, reduced motion, and the native file picker in the report (U7).
- O-11: native libplacebo capability probe from a hostile cwd (U2), plus the
  GPU/X11 items when a host is available.
- O-13 and O-14: hosted CI selection for U5, and the Windows artifact, signing,
  and release items, when separately authorized.

O-04 to O-08 stay parked as hypotheses; this plan does not address them.

## Execution record

(Orchestrator: dispatch map, commits, review adjudications, gate results,
deviations, and open items.)
