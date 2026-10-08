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
  FFmpeg render, natively and on Windows portable (U1). Include Windows console
  prompts, exact handler restoration and EOF behavior; measure native drain
  latency under the controller-confirmed exception. A killable indexing child
  remains a separately authorized follow-up if that latency is unacceptable.
- O-10: physical gestures, reduced motion, and the native file picker in the report (U7).
- O-11: native libplacebo capability probe from a hostile cwd (U2), plus the
  GPU/X11 items when a host is available.
- O-13 and O-14: hosted CI selection for U5, and the Windows artifact, signing,
  and release items, when separately authorized.

O-04 to O-08 stay parked as hypotheses; this plan does not address them.

## Execution record

### Baseline and dispatch

Baseline: `58e50a6d48c0004b63f60b9b3ba53c1ac4b31537` on
`agent/e2e-test-strategy`. Initial porcelain status contained only untracked
`docs/prompts/`, `docs/reviews/`, and this plan. Initial docs commit:
`a7dffd6e` — `docs(reviews): record comprehensive review and remediation plan`.

Orchestrator: `01a11caa-f929-7cb1-a7c1-cbeebe42a44b`, host `local`.
Human authorization: turn `01a11cab-03d8-7303-afd6-7da36c16adac`, user message
`01a11cab-0774-76e3-8b8a-1277452564a8` in that chat. Each child must retrieve
and cite that authorization before its terminal callback. All children use the
same local checkout, disjoint ownership, and no Git mutations.

| Unit | Chat ID | Preset | Explicit model / effort | Status |
| --- | --- | --- | --- | --- |
| U1 | `01a11cac-44cd-7c93-b71d-892fb0313d1b` | worker | gpt-6.1-sol / medium | Integrated `ec2fc6ca`; wave A review complete |
| U2 | `01a11cac-4d5d-7192-9f2d-dd94c22eae4d` | worker_luna | gpt-5.6-luna / xhigh | `01fc3af5`; controller-directed R-A01 correction `f8dcc3b8` |
| U3 | `01a11cac-553a-7262-952f-dcdd9e4fb429` | worker_luna | gpt-5.6-luna / xhigh | Integrated `ca432635` |
| U4 | `01a11cac-5eab-7a01-8ce9-b67a09d1677a` | worker_luna | gpt-5.6-luna / xhigh | Integrated `fbc59eb3` |
| U5 | `01a11cac-699d-76f2-ac02-972093943961` | worker_luna | gpt-5.6-luna / xhigh | Integrated `e49cb87d` |
| U6 | `01a11cac-735c-7731-8bc6-6f12ff7edde9` | worker | gpt-6.1-sol / medium | Integrated `2350cf48` |
| U7 | `01a11cac-7d6e-7920-a020-daad3bf50043` | worker | gpt-6.1-sol / medium | Integrated `25b15ae8` |
| U8 | `01a11cac-8813-7f92-979a-64534fcb4c27` | worker_luna | gpt-5.6-luna / xhigh | Integrated `ee1d674f` |
| U9 | Orchestrator directly | Direct option permitted by plan | Parent model; no child preset override | Integrated `05adff41` |
| U10 | `01a11cf6-2e2c-7ef3-bf8b-553b6f039d4e` | worker | gpt-6.1-sol / medium | Integrated `12b2eee1`; wave B review complete |
| U11 | `01a11d39-822d-72f2-b67d-ccdec2195b67` | worker_luna | gpt-5.6-luna / xhigh | Documentation integrated; wave C review pending |

Models and efforts above are the explicit creation settings; terminal reports
will reconcile actual execution. Preset aliases were resolved from their TOML
`name` fields (`worker-luna.toml`, `deep-reviewer.toml` use hyphenated filenames).

U1 design challenge: `01a11cae-94b3-7573-9eb3-df4f5366bea7`,
`deep_reviewer` / `gpt-6.1-sol` / `xhigh`. U1 production work is paused pending
the human's controller decision on the main-task checkpoint alternative and
ownership transfers; this challenge supplies evidence and does not replace
wave A's independent review. The human clarified that design checkpoints and
consequential decisions must be routed through them to their controller;
Luna chats may not settle these decisions. That steering was sent to all wave A
children and the design challenger. No U1 production design was approved.

### Integration evidence (in progress)

- U9: the original assertion failed at the full-path check with basetemp
  `.tmp/remediation-2026-10-08/U9/deep/review/controller/representative-long-checkout-and-temporary-output-directory/native/native-tmp`.
  Fixed full path fixtures replace irrelevant filesystem temp paths. The full
  alignment-report file passes (20 cases), including narrow-width controls;
  the same target test passes under short and deep basetemps. Scratch copies
  with a wrong expected path and wrong expected source frame both fail their
  intended assertions. Product width is unchanged. The first deep invocation
  had a missing-parent setup error; corrected setup preceded the genuine failure.
- U8: inspected removal and consumer audit; regenerated `docs/api.md`. Retained
  props, tonemap conversion, runtime-free imports, and all encoder tests pass
  together (87 cases). The child had run 86 with one deselected; integration
  runs the complete selection.
- U2: integration caught a native-only false capability assertion in the new
  hostile-module test. The child corrected it to compare the clean real-child
  capability with cwd, PYTHONPATH, and combined hostile inputs. All 36 selected
  tests pass in its report; real managed libplacebo proof remains an end gate.
- Initial whole-tree cheap checks during concurrent edits: pyright 0 errors /
  warnings, bandit medium/high pass (22 low findings), both import contracts
  kept. Ruff/format found unfinished changes in other active units; these
  transient runs do not establish final integration passes.
- Ready-unit integration batch: 174 passed across U2/U5/U8/U9 selections
  (approximately 10 seconds); U3's 266 selected cases pass again (8.13 seconds);
  U7's six harness drivers pass (9 cases, 0.84 test seconds); U6's changed-test
  selection passes (36 cases, 32 platform/PowerShell skips, 0.17 test seconds).
  CLI-contract documentation guards pass (3 cases, 0.12 test seconds).
- Final ready-unit cheap gates: whole-tree pyright has 0 errors/warnings;
  Ruff check passes and format reports 518 formatted files; bandit medium/high
  passes (22 low findings, 1.62 seconds), and both import contracts pass
  (0.10 seconds). U1's intentional failing regression is excluded from these
  focused behavioral selections while its design is pending.
- All seven configured pre-commit hooks passed against explicit ready-unit
  paths (1.37 seconds). Per-command `core.hooksPath=/dev/null` is used for the
  subsequent commits to prevent the hook runner temporarily stashing concurrent
  unstaged work; the identical checks ran beforehand and repository hook
  configuration is unchanged. No stash, reset, branch change, or broad staging
  was used. U2/U3/U5/U6/U7/U8 each have one local commit (dispatch table above).
- U6's source/platform contract evidence is supporting only. The child's full
  Windows selection had 114 passes and 83 skips; the integration selection is
  36 passes / 32 skips. O-01/O-02/O-03 remain physical Windows acceptance.
- U7 architecture wording now records effective Blink pause ownership and
  selected-candidate preview/apply ownership. The actual Chrome smoke and O-10
  remain outstanding. Heavy gates have not started.

Wave A review chat: `01a11cb4-9d57-7a11-8b34-94df0d21a2b1`, `reviewer` / `gpt-6.1-sol` /
`high`. Its first bounded review covers `a7dffd6e..05adff41` (seven integrated
units); U1 and U4 will be sent to the same reviewer after their commits. This
early review does not establish completion of wave A. U1 awaits the human's
controller decision. U4's clarification established six pre-change failures in
the new oversized history/cache regressions and added real oversized-cache
cache-only refusal without invoking a loader. Integration ran the complete
seven-test-file selection: 141 passed in 2.27 test seconds (2.85 wall seconds).
Whole-tree pyright, Ruff check/format, bandit medium/high, both import contracts,
scoped diff, and all applicable explicit-path pre-commit hooks passed. One local
commit, `fbc59eb3` — `fix(cache): recover oversized persisted numeric entries`, includes only
U4's two parsers and six focused test files. The same wave reviewer receives
that commit; U1's writer overlap remains paused until controller confirmation.
No heavy gates have started.

### Bounded wave A review adjudication

Reviewer inspected `a7dffd6e..fbc59eb3` (eight integrated units), excluding the
dirty plan and U1 regression-only work. Fresh focused evidence: 540 passed,
32 Windows/PowerShell skips, plus one deliberately failing scratch regression.
No other material correctness or maintenance finding was established. This
does not finish wave A or approve U1's design.

R-A01 (P2/S2, accepted): U2's isolation excludes Docker's legitimate packaged
user site. Dockerfile installs VapourSynth/vs-placebo with `pip --user` under
`/home/framecompare/.local/lib/python3.13/site-packages`; `-I`,
`PYTHONNOUSERSITE=1`, and stripped `PYTHONUSERBASE` hide those dependencies.
Preserving native-loader variables does not restore Python import paths.
The clean-versus-hostile control can return false twice and miss this regression;
the require-libplacebo override bypasses the probe and cannot prove preservation.
Orchestrator reran the review's real-child positive-layout control: baseline
capability true, current capability false with `ModuleNotFoundError`, one
expected failure in 0.19 test seconds. This is import-boundary fixture evidence
plus Docker-layout source evidence, not an actual container/native-frame run.

U2 correction needs an explicitly trusted installed-dependency route while
retaining cwd/inherited-PYTHONPATH/user-site isolation. Arbitrary caller paths
must not be restored, and Docker/runtime-layout changes remain out of owner
scope. Per human steering, the import-policy decision is routed through the
human to their controller. U2's Luna worker was told to make no production
changes or policy choice until that decision arrives. U2's original commit
already exists; correction commit allocation must respect the one-unit-commit
instruction and prohibition on amendment.

Review deviations retained with evidence: explicit-path manual hooks avoid
forbidden stashing while preserving all hooks; early bounded review finds
defects before heavy gates and will be reused for the remaining range. U7's
private candidate/revision protection serves exact preview/apply and stale-state
obligations; U5's fake-Docker success protocol is necessary for its real verifier
success path. No material shim, redundant harness, orphan consumer, upward
import, or ownership violation was found in settled units. Static ignore/path
and skipped Windows controls remain supporting evidence. Real Docker sentinel,
capability, browser, native, docs, and physical gates remain outstanding.

### Provisional controller decision for U1 (2026-10-08)

The human relayed the controller's provisional decision. Production edits resume
only after deep-review evidence is relayed to the controller and confirmed.
U1 remains paused. This later human instruction governs the checkpoint decision;
the ownership transfers below do not yet permit production implementation.

Direction: keep main-task checkpoints; no pipeline rewrite. Blanket thread
offload lacks established VapourSynth-environment and terminal-input contracts;
an all-sync or process-isolated pipeline would widen implementation and platform
acceptance. Use one lowest-layer primitive based on the current asyncio task's
`cancelling()` count, no per-owner flags or new run-state field, and no effect
when no task is running. `raise_if_cancelling()` raises `CancelledError` so the
existing failure-record path and Runner exit-130 behavior remain authoritative.

Check phase admission, executor return before output application, completed
record admission, render-unit admission, and the actual durable-write owners.
Main-thread blocking waits use bounded polling (at most about 250 ms), including
render futures and VSView wait. Stop unstarted render futures, drain admitted
work, and preserve an earlier real failure. VSView retains its bounded
terminate/kill/reap and rejects post-interrupt sidecars. Native calls already
blocking the main thread observe cancellation when they return; latency remains
O-09. Native indexing/probing process isolation is a follow-up candidate only if
physical acceptance finds the latency unacceptable.

The proposed silent first-interrupt prompt limitation is not accepted. One
interrupt-aware helper in `utils/terminal.py` covers upload confirmation,
full-window retry confirmation, and alignment-reuse `stdin.readline()`. On the
main thread with a TTY, temporarily install `signal.default_int_handler` during
input; on `KeyboardInterrupt` or its Click `Abort`, invoke the saved Runner
handler and raise `CancelledError`; always restore the saved handler. Interrupt
must not become an answer, decline, or warn-only ordinary exception. Only if the
deep reviewer establishes unsafe handler swapping may the controller accept the
post-return checkpoint fallback, discarded answer, unchanged second-interrupt
behavior, and explicit contract wording.

Conditional U1 ownership transfers, limited to checkpoints/polling/prompts:

- `utils/terminal.py` or one new utils module;
- `services/alignment_previous_offsets.py`, `alignment_reuse_cache.py`,
  `alignment_manual_overrides.py`, `alignment_vsview.py`;
- `services/alignment_reuse_prompt.py`, `cli/run_command.py`;
- `orchestration/phase_alignment.py` before U10;
- `analysis/cache_io.py` writers only after U4's parser commit.

Proof includes the pre-change real-runner regression; no later phase/unit,
failed record, reaped child, exit 130; pending-cancellation tests at each
persistence owner; a real PTY prompt interruption/restoration test; unchanged
audio/webhook/VSView reaping obligations; final native and Docker gates.
Return evidence to the controller if a scoped main-thread wait cannot poll,
handler swapping misbehaves on Windows/Python 3.13, or scoped persistence runs
on a worker thread where the current-task primitive cannot observe the run.

Deep review returned three unresolved gaps, relayed to the human for confirmation:

1. Direct synchronous `CancelledError` leaves Runner's queued task cancellation
   available to interrupt a later awaited cleanup. Local CPython 3.13.16 plus
   actual HTTPX and simulated delayed-close transport probes observed close
   start without completion, even with HTTPcore's shield. This establishes a
   scheduling mechanism, not a leaked real socket. Deliver pending cancellation
   at the async boundary or own a bounded shielded drain; preserve cancellation
   authority, caller-owned clients, and earliest failures.
2. Writer-entry checkpoints precede lock waits, merging, serialization, fsync,
   and atomic replacement. The last logical publication boundary must be
   explicit, with temporary-file cleanup on `BaseException`. Failure-record
   persistence must bypass success/cache rejection while the task is cancelling.
   Minimal additional atomic/probe/diagnostic owner transfers require controller
   confirmation; an OS operation already admitted cannot be rolled back by a
   checkpoint.
3. Native VS `get_frame()` and some writes have no established finite deadline;
   executor shutdown waits for running threads. Scheduler polling does not
   establish a finite native drain. The controller must reconcile its accepted
   native-call limitation with the original strict bound, or authorize a proven
   narrower lifetime design. No native hang was observed.

The same `deep_reviewer` is supplying a read-only supplement on the proposed
prompt-handler swap, remaining owner files, and these conditions. No production
code or design approval followed either evidence package.

U1 worker independently reproduced queued cancellation interrupting actual
HTTPX delayed-close transport cleanup (local no-network probe): close started,
but close completion was absent. It also identified `utils/file_lock.py`'s
existing 50 ms polling without run-cancellation checks, the shared success/failure
record writer, audio-worker admission and diagnostic writes in
`services/alignment.py`, and preparation's run-local/shared probe-cache writes
after native source loading. Those additional owners need controller routing;
no ownership expansion or exclusion of probe-cache persistence was approved.

### U1 focused controller-evidence supplement

The deep reviewer verified the human's attachment authorization (turn
`01a11cb5-a194-7533-a647-285fe0e58403`, user message
`01a11cb5-a7c5-7fe1-9be2-f38554a1993c`) and returned evidence only. Production
remains paused until human/controller confirmation.

- Prompt prototype: seven bounded actual-PTY cases on macOS / CPython 3.13.16
  completed in 1.77 seconds. Real alignment-reuse, Typer/Click upload input,
  and retry-confirmation input produced first-interrupt cancellation count 1,
  restored the exact saved Runner handler and final default handler, and exited
  130. Answer/EOF/ordinary-error controls preserved zero cancellation and
  restoration. A second-signal control observed Runner count 2 and exit 130.
  No fixed sleeps, production edits, or network requests were used. This is
  prototype/input-path evidence, not landed helper or Windows-console acceptance.
- Prompt conditions: restore the same handler object within synchronous input
  scope, before async cleanup. Click `Abort` wraps both EOF and Ctrl+C; inspect
  its hidden exception context so EOF is not counted as an interrupt. Check
  pending cancellation before input and after successful reads. Do not assume
  foreign handlers/non-TTY/no-loop execution use the callable Runner handler.
  Invoking Runner then manually raising still leaves queued cancellation for
  the next await; owned cleanup needs the previously reported solution.
- Native exception needs precise controller wording: already-admitted native
  operations, including render/audio worker native calls, have no guaranteed
  finite drain deadline. Default FFmpeg extraction retains its timeout. Native
  indexing caches and artifacts produced by admitted work can finish with that
  work; current-task checkpoints cannot stop those worker writes. No renderer
  isolation/rewrite was selected or authorized.
- Minimum additional owners beyond original U1 and the provisional list:
  `utils/atomic_write.py`, `orchestration/preparation.py`,
  `services/alignment.py`, `services/alignment_diagnostics.py`,
  `orchestration/probing/probe_cache.py`; also `utils/file_lock.py` for run
  cancellation during its existing 50 ms lock polling. Original U1 already owns
  coordinator cleanup and run-record writers after U4. No evidence requires
  adding `analysis/metrics.py` solely for cache publication or
  `full_window_retry.py` solely for prompt conversion.
- New explicit return-to-controller trigger: `TmdbCache.store_search` and
  `store_alternative_titles` dispatch `_store` via `asyncio.to_thread`. Metadata
  preparation and post-render metadata can reach this shared response cache.
  `_store` locks, merges, serializes, then atomically publishes on the worker.
  A no-network actual-store/Runner probe with a simulated handshake lock and
  publication observed worker_has_task=False, main_task_cancelling=1, and
  publication_after_interrupt=True. This is a scheduling/publication mechanism
  with simulated lock/publication, not a live request or real persisted cache.
  If the prohibition includes shared TMDB responses, the controller must settle
  task-owned publication versus an explicit cross-thread cancellation contract,
  with narrow `services/tmdb_cache.py` ownership. If excluded, record the precise
  exception. Neither option was chosen here.

Still required after confirmation: queued-cancellation-safe awaited close,
last-publication checks with BaseException temp cleanup, early reservation
capture, diagnostic/probe-cache coverage, bounded polling including VSView
startup-readiness wait if covered, result-acceptance gates, failure progress
status, failure-record bypass, and the TMDB-worker decision. U1's worker and all
Luna chats retain the human/controller decision boundary.

### Confirmed controller decisions (2026-10-08)

The human relayed the final controller decisions in turn
`01a11cd3-d2f2-7151-8968-4fc50e0c8e4a`, user message
`01a11cd3-d31b-7862-a990-9bcf404b6bec`, and explicitly stated maintainer approval.
They supersede provisional decisions and the original U1/U2 specification where
amended; remaining constraints stay in force. U1 may resume production work.
U2 receives one newly authorized correction commit without amendment. Its
correction integrates before U1 changes the adapter; the sibling investigation
is read-only. The exact controller decision follows.

**Controller decisions: U1 confirmed with amendments; U2 import policy (2026-10-08).** The maintainer has approved these decisions, including the TMDB exception and the VSView sibling check. Record them in the execution record. U1 production work may resume under these terms. The return-to-controller conditions from the provisional decision still apply.

## U1: run cancellation (confirmed)

The direction is unchanged: main-task checkpoints, bounded polling, no pipeline rewrite. The deep-review evidence amends four details.

**1. Prompt helper: approved.** The deep reviewer's conditions are requirements:

- Act only on the main thread, with a TTY, when the current SIGINT handler is the callable asyncio Runner handler. Otherwise do nothing and leave foreign handlers untouched.
- Check for a pending interrupt before reading input and again after a successful read.
- Restore the exact saved handler object inside the synchronous input scope, before any async cleanup.
- Treat click's `Abort` as an interrupt only when its exception context is a KeyboardInterrupt. EOF stays EOF, with an interrupt count of zero.
- On a real interrupt, call the saved Runner handler, so the interrupt is counted and the main task cancelled. Then raise the private interrupt marker from point 2, not `CancelledError`.

The seven macOS PTY cases are accepted as prototype evidence. Add Windows console behavior to physical acceptance item O-09.

**2. Queued cancellation during cleanup: deliver it at the async boundary.**

When synchronous code raises `CancelledError`, the Runner's cancellation stays queued and fires at the first `await` inside cleanup. The rule has two levels:

- **Async checkpoints** (phase admission, executor return, and completed-record admission in `execution.py`, `phases.py` and `coordinator.py`) take the queued cancellation with an `await`, using the primitive's async form (`await asyncio.sleep(0)`). The real `CancelledError` arrives there and is consumed before any cleanup await.
- **Synchronous checkpoints and the prompt helper** raise one private `BaseException` subclass meaning "run interrupt requested". It must not subclass `Exception`, or `warn_only` phases would swallow it.
  - Every place where async code calls into synchronous owners converts the marker by awaiting the async checkpoint, which delivers the real `CancelledError`. At minimum that means the phase-executor wrapper and the coordinator's preparation call.
  - The marker never escapes the run.
  - With no running task, the primitive does nothing, so the marker is never raised.
- Keep the existing shields and bounds on owned cleanup. Add no new shields elsewhere.
- **Proof:** turn the HTTPX delayed-close transport probe into a regression where close completes after the first interrupt. It must fail on the current code first.

**3. Publication boundary and generic utilities.** Generic utilities never consult the ambient task; their owners decide.

- `utils/atomic_write.py`:
  - add an optional `publish_guard` callable, invoked immediately before the atomic replace, after locking, merging, serialization and fsync;
  - remove the temporary file on any `BaseException`.
- `utils/file_lock.py`: add an optional abort check, called on each iteration of the existing 50 ms poll.
- Result, cache, probe-cache and diagnostic owners pass the run's synchronous checkpoint as the guard.
- **Failure-record and failure-progress paths pass no guard**, so they still persist while the task is cancelling.
- A replace that has already started cannot be rolled back. This is accepted.

**Ownership transfers approved**, for checkpoint, guard, polling and early-reservation placement only:

- `utils/atomic_write.py` and `utils/file_lock.py`;
- `orchestration/preparation.py` (early reservation capture, and probe-cache writes after native source loading);
- `services/alignment.py` (audio-worker admission) and `services/alignment_diagnostics.py`;
- `orchestration/probing/probe_cache.py`.

These add to the provisional list. `analysis/metrics.py` and `orchestration/full_window_retry.py` are not transferred. The bounded-polling rule covers VSView's startup-readiness wait inside the already-owned `vsview/adapter.py`.

**4. Native limit: exception confirmed.** Use this exact wording for the contract:

> After the first Ctrl+C, Frame Compare starts no new phase, render unit or audio work, and publishes no new result, cache or diagnostic entry except the failure record. Native operations already admitted (VapourSynth frame requests, render and audio worker native calls, and native index or cache files those calls write) run to completion. They have no guaranteed finite drain deadline. FFmpeg frame extraction keeps its existing timeout. A second Ctrl+C keeps its existing behavior.

Physical acceptance item O-09 measures the real latency. If it proves unacceptable, the targeted follow-up is to move L-SMASH indexing (and possibly probing) into a killable child process. That is not part of U1.

O-09 also includes Windows console behavior of the interrupt-aware prompt helper,
as required by this confirmed controller decision.

**5. TMDB response cache: exception, no new ownership.**

When a response is already in flight, `TmdbCache` may finish publishing it on its `asyncio.to_thread` worker after the first Ctrl+C. It is excluded from the no-publication rule because:

- it records a validated upstream response keyed by a privacy-safe request identity;
- it carries no run, selection, alignment or cache authority;
- its writer is locked and atomic;
- the CLI drains the executor before exit.

No new TMDB request may start after the interrupt. The metadata phase's admission checkpoint and the cancellation of in-flight HTTP awaits must guarantee that; add one test asserting it. `services/tmdb_cache.py` is not transferred.

**Proof additions**, beyond the provisional list:

- the HTTPX close regression (point 2);
- `atomic_write` removes its temporary file on `BaseException`, and the guard fires after serialization but before the replace;
- a lock-wait abort test;
- the failure record persists while the task is cancelling;
- preparation's probe-cache writes and the alignment diagnostic writes are skipped after the interrupt;
- no new TMDB request after the interrupt;
- a `warn_only` phase does not swallow the interrupt marker.

## U2: trusted-dependency import policy

R-A01 is accepted. The probe launches its child Python with `-I` and `PYTHONNOUSERSITE`, which hide Docker's `pip --user` packages, so the probe wrongly reports libplacebo as unavailable.

Policy: the capability child trusts exactly the import locations the parent interpreter's installation trusts. It never trusts the working directory, the script directory, or an inherited `PYTHONPATH` or `PYTHONSTARTUP`.

- Do not use `-I`. Use safe-path mode (`-P` or `PYTHONSAFEPATH=1`) and strip the injection variables.
- The child's user site follows the parent's:
  - If the parent runs with user site enabled (`site.ENABLE_USER_SITE` is true and `sys.flags.no_user_site` is not set), keep it, along with the parent's `PYTHONUSERBASE`.
  - If the parent runs without it, launch the child with `-s`.
  - The parent already imports itself and its dependencies from that location, so the child gains no new trust.
- Keep the native-loader variables.
- No hard-coded Docker paths, no restoring arbitrary caller paths, and no changes to the Docker or runtime layout.
- Put the policy in one helper in `utils/subproc.py`, which U2 owns.
- **Proof:**
  - the reviewer's real-child positive-layout control passes: a dependency installed in user site is visible to the child;
  - the hostile cwd and hostile `PYTHONPATH` markers are still never imported;
  - when the parent runs without user site, so does the child;
  - the end-of-run Docker gate supplies the real packaged capability proof.
- Make a new commit, not an amend, for example `fix(vs): keep trusted user-site dependencies in the tonemap probe`.

**VSView sibling check, before U1 edits `vsview/adapter.py`.** `_build_vsview_child_env` applies the same `PYTHONNOUSERSITE=1` policy, and the `gui-linux` image installs VSView with `pip --user`. Yet the 2026-10-07 GUI proof passed.

- Determine from `tools/verify_docker_gui.sh` and its inside-container route how the adapter's child found VSView.
- If the adapter's policy would hide user-site packages, U1 adopts U2's shared helper in `_build_vsview_child_env`, with a positive-layout control.
- If it would not, record why. Do not change the adapter's import policy without that evidence.
- Sequence: U2's correction lands before U1 touches the adapter.

Dispatch after confirmation: existing U1 and U2 chats received the complete
controller decision and explicit scope/sequence. U1 may implement its confirmed
owners while leaving the adapter untouched until U2 integrates. U2 implements
the decided shared helper and investigates the GUI sibling without editing it.
The exact native-limit wording and shared-TMDB exception were added to the CLI
contract as an orchestrator delta; its three documentation guards pass.

End-gate preparation: a scratch-only Compose override sets both test and
production verifier containers to `network_mode: none`, preventing the default
doctor health check from contacting a live service while retaining the canonical
verifier command. Resolved Compose configuration confirms both services are
network-isolated. No runtime gate has run yet, and no Docker/Compose source
configuration or dependency was changed.

### U2 controller-directed correction integrated

Corrective commit `f8dcc3b82576ff42ed0d4f83c749e55dc8911e13` —
`fix(vs): keep trusted user-site dependencies in the tonemap probe` — changes
only the shared process helper, tonemap probe and their two existing test files.
The shared helper uses safe-path mode and strips Python injection variables;
user-site availability follows the parent exactly. No Docker/runtime layout or
native-loader configuration changes. A real user-site positive dependency
control now passes, hostile cwd/PYTHONPATH controls remain intact, and the
disabled-site proof starts a real parent with `-s` rather than assuming the
ambient venv's site policy. Integration: 54 passed in 0.90 test seconds; scoped
pyright has zero errors/warnings; all applicable explicit-path hooks pass.
Whole-tree bandit medium/high and both import contracts pass. Whole-tree
pyright/Ruff/format also ran, but encountered unfinished U1 source and test
edits; those transient failures are not claimed as final passes. They will be
rerun on settled wave A code.

Sibling evidence: `gui-linux` installs VSView and dependencies with `pip --user`.
The historical verifier imports availability in the parent, runs direct
`python -m vsview --help`, then generates a session with
`VSViewConfig(enabled=False)` (`tools/verify_docker_gui.sh`). It never exercises
the adapter's isolated startup probe or enabled launcher. Its prior success
therefore does not prove that `PYTHONNOUSERSITE=1` can find those dependencies.
Under the controller's explicit conditional authorization, U1 now adopts the
landed shared helper for both adapter child commands and adds a positive-layout
control. Adapter ownership is released only after the corrective commit above.
R-A01 awaits the same independent wave reviewer and the final real packaged
capability gate; the extra corrective commit was explicitly controller-approved.

Independent corrective review of `fbc59eb3..f8dcc3b8`: R-A01 is resolved at
import-boundary fixture level, with no new material finding. Reviewer reran
29 cases (0.74 seconds, no skips), scoped pyright/Ruff/format and range
diff-check successfully. The unchanged enabled-user-site positive control fails
against the previous committed probe with `ModuleNotFoundError: vapoursynth`
(one expected failure, 0.21 seconds), then passes against the correction. Its
minimal fake native interface proves real parent/child import behavior, not
native plugin acceptance. Separate enabled-site, disabled-site and hostile-path
proofs have distinct obligations; no material redundant harness, shim or
ownership issue was found. The controller-approved helper placement and extra
corrective commit are retained. The reviewer independently confirms the GUI
sibling explanation in source. Actual Docker/libplacebo proof remains open,
and active U1 code was excluded; this does not complete wave A.

### U1 integration under the confirmed amendments

Inspected all changed owners against the approved transfer list. No executor
thread migration, new run-state flag, generic ambient-task policy, new shield,
TMDB-cache ownership change or dependency change was introduced. The private
marker is converted at async boundaries before cleanup; queued cancellation no
longer interrupts the first HTTPX close await. Atomic guards run after fsync and
before replace, clean temporary files on `BaseException`, and exempt failed
records. Render polls at 100 ms, stops new units, cancels unstarted futures,
drains admitted workers and preserves a previously observed real failure.
VSView readiness and review waits use the shared import helper, poll at most
100 ms, and retain bounded terminate/kill/reap ownership. Preparation captures
the reservation before publication, blocks later source/probe admission, and
guards run/shared probe caches. Alignment blocks audio admission and guards
manual/reuse/diagnostic publication. The approved native and TMDB exceptions
remain explicit in the CLI contract and O-09 handoff.

Before-change evidence is retained in the child's ignored U1 scratch logs:
real SIGINT VSView/render regressions persisted `completed_with_warnings`;
the HTTPX delayed-close regression did not complete close; all three real PTY
prompts timed out on first SIGINT. Integration reran the complete focused
23-file selection: **435 passed, no skips, 22.22 test seconds**. It includes
unchanged audio/webhook repeated-cancellation, owned adapter reaping, failure
precedence, real contended-lock abort, fsync-triggered guarded publishers,
failed-record publication while cancelling, preparation probe admission,
warning-only marker propagation and zero/new-in-flight TMDB admission proofs.
CLI documentation guards: 3 passed in 0.08 seconds. Whole-tree pyright:
0 errors/warnings; Ruff check and format: pass (519 files); bandit medium/high:
pass (22 low findings); both import contracts: kept (180 files, 738 dependencies).
API regeneration produced no diff because the changed utility signatures are
outside its locked module list. Physical Windows console and actual native
drain latency remain unverified. Audio collector cleanup was unchanged, so the
conditional streaming-resource heavy proof is not required by this unit.

### Final wave A review and adjudication

Same reviewer reconciled the final net range `a7dffd6e..ec2fc6ca`, including U1's
new range `f8dcc3b8..ec2fc6ca`, with its earlier eight-unit and U2 corrective
reviews. No new material finding and no unresolved wave A finding. R-A01 is
closed at import-boundary level; packaged native acceptance remains an end
gate. Fresh final review: 271 passed, no skips, 14.12 seconds over 15 selected
files; net diff-check passed. Earlier 540-pass/32-skip and 29-pass selections
overlap, so their counts are not summed. Checkout remained clean during review.

Adjudication: retain the explicit-path hook workaround, early bounded review
followed by final net reconciliation, and deterministic U9 non-I/O paths as
strictly better execution/proof choices with the evidence above. The controller's
main-task cancellation amendments, native/TMDB exceptions, additional writer
owners, parent-trust import rule and extra corrective commit are explicit
authorizations, not unresolved deviations. No additional design approval is
inferred from this review. Source/test over-engineering hunt found no material
shim, redundant harness, broad framework, orphan consumer or ownership violation
requiring removal. U1's synchronous marker and async delivery have different
obligations; its publisher, lock, HTTPX, PTY and real-failure cases are distinct.
The final source review preserves runtime-free help/version, typed errors,
machine-clean JSON, zero/alignment authority, downward imports and owned cleanup.

Representative wave A test map (supporting cases remain where obligations differ):

| Finding | Meaningful proof |
| --- | --- |
| F-001 | `test_first_sigint_stops_admission_and_records_failure` (startup/review/render/HTTPX); separate PTY, publisher and prior-real-failure controls |
| F-002 / R-A01 | `test_libplacebo_probe_does_not_import_hostile_vapoursynth`; real enabled-parent positive and disabled-parent controls |
| F-003 | Installed CLI invalid-UTF8 config and preset-apply controls in `tests/e2e/test_cli_errors.py` and `test_cli_config.py` |
| F-004 | `test_cli_rejects_nul_paths_as_typed_config_errors` |
| F-005 | `test_cli_rejects_nonfinite_exclusions_as_typed_config_errors` |
| F-006 | `test_cli_history_list_json_isolates_oversized_record`; real written cache recomputation and cache-only refusal |
| F-007 | `test_verifier_preserves_previous_artifacts_and_owns_fresh_invocation_directory` success/failure and symlink controls |
| F-008 | `test_workflow_path_filter_has_positive_and_negative_controls` |
| F-009 | `test_dockerignore_excludes_local_residue_without_excluding_image_inputs`; real image sentinel still pending |
| F-010 | PS5 non-ASCII state/command process cases; Windows runtime skips remain open |
| F-011 / D-01 | `test_root_source_installer_prerequisite_at_process_boundary` and cmd refusal controls |
| D-03 | `test_windows_rollback_checks_backup_identity_without_mutating_on_refusal` and malformed/missing/mismatch controls |
| F-012 | Production viewer/viewport handler harness driven by `test_report_viewer_state.py`, all 30 combinations |
| F-013 | Review-state/controller harnesses driven by `test_report_review_state.py`: exact selected delta, stale/forged refusal, File path and atomic rejection |
| F-016 | Consumer audit plus retained active encoder/range/tonemap/import coverage; deleted orphan mocks are not claimed as proof |
| F-021 | `test_emit_frame_alignment_report_verbose_retains_row_zero_frames_and_paths`, deep/short and wrong-path/row negative controls |

Independent review does not claim Docker/native plugins, actual Chrome, Windows
console/portable runtime, native cancellation latency, physical gestures/picker,
hosted CI or artifact/signing acceptance. Wave B is released for its design
checkpoint; production migration still requires a controller decision relayed
through the human under their later steering.

U10 dispatch: existing preset responsibility text, full-plan/findings routes,
settled `ec2fc6ca` dependency baseline, complete constraints and verified parent
callback authorization supplied to a new local `worker` chat with explicit
`gpt-6.1-sol` / `medium`. Assignment is read-only design tracing/reproduction:
return owner, fields, complete producer/carrier inventory, exact public-string
projection, proof strategy and unresolved decisions. No migration or test edits
are authorized until the human relays their controller's checkpoint decision.

### U10 design checkpoint — awaiting human/controller decision

Design-only child returned at `ec2fc6ca`, with no production/test/doc edit.
Configured `worker` / `gpt-6.1-sol` / `medium`; actual sampler settings are not
independently exposed. It verified the original human callback authorization
and later controller-routing steering. The following is a proposal, not approval.

**A — Shared record and direct producer semantics.** Proposed owner:
`src/frame_compare/utils/warnings.py`, standard-library-only frozen, slotted
`RunWarning` dataclass:

```python
source: str
severity: Literal["warning", "skipped"]
message: str
detail: str | None = None
```

Read-only `text` returns `message` when detail is absent, otherwise
`f"{message} {detail}"`. Producers choose exact portions of their existing
text; no stripping/normalization, raw-text field, implicit string conversion,
string subclass, parser, registry, compatibility shim or persisted record.
Producers author source/severity directly, with stable sources `alignment`,
`frame selection`, `render`, `sources`, `analysis`, `active-rect auto detection`,
`analysis source`, `slow.pics`, `cleanup`, `history`; generic timed failures use
an explicit phase-to-source map. Only genuinely skipped branches use `skipped`
(too-few active-rect samples and report-unavailable upload); other warnings use
`warning`. Source headings must no longer accidentally include filenames or
exception fragments. CLI may retain its local presentation row's action kind,
which has a real row-suppression consumer. Exact `.text` matching preserves
post-upload association; field-tuple display dedup, cap, headline counts,
verbose expansion and stable text sorting remain. No import-contract change.

**B — Related retry text-policy seam.** `full_window_retry.py` currently removes
old active-rect warnings with `startswith("active-rect auto detection ")`.
Proposal: select by `source == "active-rect auto detection"` during the same
carrier migration. This preserves the intended producer membership while
removing another text-policy dependency. Retry/selection authority is unchanged.
Controller concurrence requested rather than silently widening the checkpoint.

**C — Exact existing public/persisted behavior.** Source inspection confirms
successful `run --json` has **no warning field** (`cli/run_command.py`,
`handle_json_output`), and run-result V1 stores only capped repetitions of
`"A run warning was reported."`, with the full original warning count
(`services/run_result_record.py`, `_warning_summaries`). Proposal: preserve those
schemas and exact bytes, not introduce a public warning field or persist
producer text. Completed/failed facts become typed in-memory inputs; persisted
summary fields, parser/history read diagnostics and unrelated diagnostic/log
strings remain strings. The orchestrator independently inspected these owners.

Migration inventory: warning producers in `services/alignment.py`,
`slowpics_shortcut.py`, `slowpics_webhook.py`, `slowpics_post_upload.py`,
`cli/run_command.py`, and orchestration's `phase_alignment.py`,
`phase_selection.py`, `phase_render.py`, `selection_domain.py`,
`active_rect_content.py`, `full_window_retry.py`, `execution.py`,
`phase_post_render.py`, `slowpics_metadata.py`, `analysis_source.py`,
`run_result_lifecycle.py`. Carriers/consumers additionally include
`utils/post_upload_actions.py`, orchestration `types.py`, `execution_types.py`,
`context.py`, `preflight.py`, `preparation.py`, `coordinator.py`,
`phase_output_application.py`, `alignment_report.py`, service run-result input
facts, and `cli/output.py`. Preserve log-only metadata and diagnostic-only
analysis-source routing rather than inflating final run counts. `runner.py`
only forwards the result and needs no change. Both applied-summary owners
(`phase_alignment.py`, `services/alignment_presentation.py`) change only
`audio applied` to `alignment applied`; review counts and unavailable/needs-
confirmation language remain.

Evidence before migration: production-path probe reproduces F-014 — identical
unapplied result with neutral label yields warning, adversarial label containing
`skipped`, colon and `because` yields skipped with truncated message/detail.
Genuine upload skip remains skipped. Both real summary owners currently say
`audio applied` for manual zero/nonzero and computed/cached presentation DTOs;
review-count control stays intact. Eleven existing focused warning/frozen-string/
generic-summary cases pass (0.68 wall seconds, no skips). These are baseline
observations, not new regression red/green or native authority evidence. Two
initial probe setup mistakes were corrected before the observations.

After approval, extend existing phase/output/frozen-string/run-record tests:
adversarial-label semantic invariance, genuine skip, exact text and action
dedup/cap/headline, pinned JSON omission and record bytes/count/cap, all applied
summary origins, existing retained success lines, active-rect/source/producer
branches and failure lifecycle. No new general harness or media gate for text
alone. Exact shared architecture/CLI/CHANGELOG deltas were proposed to the
orchestrator, who owns those files. No migration has begun; A/B/C require the
human's controller response before dependent work proceeds.


### U10 controller decision received (2026-10-08)

Human turn `01a11d1f-ab94-7733-9c60-8412ba982f66`, user message
`01a11d1f-abe3-7233-ac11-aeaf1dba8a88`, supplied the following exact decision in
`/Users/tristan/.codex/attachments/96217696-e11a-49d4-995b-a9ad5d06fe7f/Pasted text.txt`.
It approves A/B/C with explicit amendments and supersedes the earlier proposal:

Here's the U10 decision to pass back. It approves A, B and C, with three amendments to A.

---

**Controller decision: U10 typed warnings (2026-10-08). Approved with amendments.** Record it in the execution record. U10 migration may begin on top of `ec2fc6ca`.

**A. Shared warning record: approved, with three amendments.**

1. **Module name.** Use `src/frame_compare/utils/run_warnings.py`, not `utils/warnings.py`, so it doesn't share the standard library `warnings` module's name. That module is already relevant through pytest's `filterwarnings = error`. Keep the record frozen, slotted and standard-library-only, with the fields as proposed.
2. **Typed source.** Make `source` a `Literal` type alias (`WarningSource`) listing the stable sources the worker inventoried:
   - `alignment`, `frame selection`, `render`, `sources`, `analysis`;
   - `active-rect auto detection`, `analysis source`, `slow.pics`, `cleanup`, `history`.

   The phase-to-source map for generic timed failures returns that type. A misspelled source then fails pyright instead of quietly creating a new heading. No enum, registry or runtime validation is needed.
3. **Post-upload association by record, not text.** Post-upload action results carry the `RunWarning` itself. Match action rows to warnings and dedupe by record equality (frozen dataclass equality), not by `.text` lookup. That removes the last text-matching step. Keep `.text` only where a string is actually emitted: human output, logs and the alignment report.

Further requirements for A:
- Carriers are `list[RunWarning]` only. No `str | RunWarning` unions, implicit conversion, adapters, or parsing fallbacks.
- Delete `_warning_presentation_from_string`, `_normalize_warning_source`, the `" because "` and `":"` splitting, and the coordinator's `startswith("align:")` filter. Alignment warnings are selected by `source == "alignment"`, including the list handed to the alignment report.
- Producers write their message and detail as the exact text portions shown today, so human output stays identical except where F-014 is being fixed.
- The CLI's local presentation row keeps its action kind, and the field-tuple dedup, cap, headline counts, verbose expansion and stable sorting stay as they are.

**B. Retry filtering: approved.** In `full_window_retry.py`, select earlier active-rect warnings by `source == "active-rect auto detection"` instead of the text prefix, as part of the same migration. Retry and selection authority are unchanged. The ownership transfer is approved for this change only.

**C. Contract preservation: approved.** Successful `run --json` keeps having no warning field, and run-result V1 keeps its generic summaries, original count and cap, with byte-identical output. No new public warning field and no producer text in persisted records. This supersedes the plan's wording about projecting records to strings for JSON and run records. Persisted summary fields, history read diagnostics, and unrelated diagnostic or log strings stay strings. Log-only metadata and diagnostic-only analysis-source routing stay out of the final run count.

**F-015: approved as proposed.** Both summary owners change only `audio applied` to `alignment applied`. Review counts and the unavailable and needs-confirmation wording are unchanged.

**Ownership:** U10 owns the producer and carrier inventory listed in the checkpoint, plus `utils/run_warnings.py` and `orchestration/full_window_retry.py`. Shared architecture, CLI-contract and CHANGELOG text still go to the orchestrator as deltas. `lint-imports` must stay clean; `utils` is the lowest layer, so no contract change should be needed.

**Proof**, extending the existing phase, output, frozen-string and run-record tests:

- The F-014 production-path probe becomes a regression that fails before the migration. An identical unapplied result with a neutral label and with a label containing `skipped`, `:` and ` because ` renders with identical severity, source, message and detail.
- A genuine skip (the upload when the report is unavailable, and too few active-rect samples) still renders as skipped.
- Post-upload association and dedup work through record equality; cap and headline counts are unchanged.
- Successful JSON is pinned as having no warning field. Run-record bytes, count and cap are pinned.
- "alignment applied" appears for manual zero and nonzero, computed, cached and reviewed origins, and existing success lines are unchanged.
- Active-rect retry selection uses source, and the failure-lifecycle warnings still work.

No new harness and no media gate are needed for text-only behavior. The full native suite at the end covers integration.

**Return to the controller** if a producer can't produce today's exact text from the message/detail split without changing visible output beyond F-014. The same applies if any consumer outside the inventory needs the warning text or a new source value.

---

Two notes on why I amended A rather than approving it unchanged:

- **Text matching:** the worker's post-upload association still matched warnings by text. That is the same kind of text policy this unit exists to remove, and switching to record equality costs nothing.
- **Free-string source:** a free-form `source` string would let a typo create a new heading silently, and a `Literal` type catches that in pyright.

Orchestrator proof-wording check: migration remains paused on one internal
conflict in the decision. Its proof requires identical `message` for neutral
and adversarial labels, while the producer's existing exact message includes
`comparison_label` and the decision requires preserving today's text portions.
Both cannot hold literally. Recommended clarification: source, severity and
reason/detail remain identical; each message retains its respective label and
otherwise has identical wording and structure. This matches the original plan's
F-014 obligation without losing source-identifying context. No producer text or
implementation has changed. The approved module name, `WarningSource` Literal,
record-equality association, list-only carriers, retry selection, persisted/JSON
preservation and F-015 scope remain recorded; only the human/controller may
settle the conflicting proof wording before migration proceeds.

### U10 F-014 controller clarification (2026-10-08)

The human supplied the following controller clarification directly in this chat.
It resolves the proof conflict above; all other approvals remain in force.

**Controller clarification: U10 F-014 proof (2026-10-08).** The worker's reading is approved. Record it in the execution record. Migration may resume.

For the same unapplied result rendered once with the neutral label and once with the adversarial label (containing `skipped`, `:` and `because`), the regression asserts:

- `source`, `severity` and `detail` are identical between the two renderings.
- The adversarial `message` equals the neutral `message` with the neutral label replaced by the full adversarial label. Compute the expected string from the neutral rendering and compare for exact equality, so the wording is otherwise identical.
- The adversarial label appears whole and untruncated in `message`, and no part of it leaks into `source` or `detail`. This is the truncation and splitting F-014 reported.
- The rendered human line follows the same rule: the same glyph, styling and source heading, with only the label text differing.

The test must fail before the migration and pass after it. All other U10 approvals stand.

Orchestrator disposition: resume the same U10 implementation chat on `ec2fc6ca`
under the recorded module/source/record-equality/list-carrier amendments, approved
retry ownership and exact JSON/persisted behavior. The clarified regression must
fail before migration and pass afterward. No independent design approval or
expansion of the producer/carrier inventory is inferred.

### U10 integration evidence

Inspected the 28 production and 24 existing-test paths against the approved
inventory. `utils/run_warnings.py` is frozen/slotted/standard-library-only with
the ten-value `WarningSource` Literal; all runtime warning collections use
typed records, with no string unions, fallback parsers or adapters. CLI source/
severity/detail parsing and post-upload prefix slicing are deleted; action
association uses record equality. Alignment-report and retry selection use
source. JSON output function and persisted warning-summary/count/cap schema are
unchanged; log-only/diagnostic-only warnings retain their routing. Both short
applied-summary owners change only the approved phrase, preserving counts,
confirmation wording, durations, retention and authority. U1 cancellation and
U4 numeric recovery remain intact.

The clarified production formatter-to-CLI F-014 regression failed before any
production migration (wrong skipped severity and corrupted detail; log
`.tmp/remediation-2026-10-08/U10/f014-before.txt`), then passes with exact complete-
label substitution in message and ANSI-rendered line, invariant source/severity/
detail and no label leakage. Distinct controls prove both genuine skips, record
equality versus same emitted text, action row dedup/cap/headline, active-rect
source selection despite misleading prefix text, applied manual zero/nonzero/
computed/cached/reviewed summaries, pinned JSON bytes and exact completed/failed
V1 count/cap/sanitized bytes captured from `ec2fc6ca`. No new harness or skip.

Child final selections: 535 passed in 12.97 seconds and 34 runtime-free controls
in 0.62 seconds, no skips. Integration combined selection: **569 passed, no
skips, 13.53 test seconds**. Whole-tree pyright: zero errors/warnings; Ruff
check/format: pass (520 files); bandit medium/high: pass (22 low findings);
import contracts: 2 kept (181 files, 763 dependencies). API regeneration
produced no diff. Architecture and CLI deltas applied by the orchestrator;
CHANGELOG remains the required post-heavy-gate step. Child's configured
`worker` / `gpt-6.1-sol` / `medium` agrees with explicit creation settings;
actual sampler settings are not independently observable. Intermediate fixture
and collection errors were repaired without weakening production obligations;
only final clean selections are acceptance evidence.

U10 local commit: `12b2eee1f3ed9b823b9fc73d63a864aeec72203a` —
`refactor(warnings): carry producer semantics through run output`. Explicitly
staged 52 implementation/test paths (including new `run_warnings.py`) and the
three orchestrator-owned shared docs; applicable hooks passed. CLI-doc guards
also pass (3 cases, 0.13 seconds). Checkout was clean after commit.

Wave B reviewer: `01a11d32-e96a-72f2-8d98-c30253ef8730`, preset `reviewer`,
explicit `gpt-6.1-sol` / `high`. Self-contained read-only assignment covers
`ec2fc6ca..12b2eee1`, every approved amendment and clarification, deviations,
source/test over-engineering hunt, F-014/F-015 test map, ownership/contracts and
the remaining acceptance limits. No heavy gate, new design authority or
recursive dispatch is granted. Actual sampler settings remain unobservable.

### Wave B review and adjudication

Independent reviewer inspected `ec2fc6ca..12b2eee1`, all 28 production and 24
test deltas and affected callers. No validated material correctness or
maintainability finding; no new consequential decision or scope expansion.
Fresh focused evidence: **421 passed, no skips, 11.42 seconds** over 15 files;
scoped pyright zero errors/warnings, Ruff/format all 52 paths, committed
diff-check pass. An isolated disposable-process replay of exact baseline
production function bodies produces six expected failures (F-014 and five
F-015 origins, 0.48 seconds); those unchanged regressions pass against current
code. Baseline and current run-record owners independently produce identical
completed/failed V1 bytes for warning counts 2 and 10. This is supplemental
body-replay evidence, not a complete baseline checkout or native acceptance.

Adjudication: no correction required. Controller amendments remain explicit
authorizations; no additional U10 deviation was found. The earlier manual-hook
workaround remains bounded and justified. Over-engineering hunt found no
parser residue, text-matched action policy, union carrier, shim, registry,
unnecessary provenance DTO, new harness, skip or weakened assertion. Two local
stable-sort key expressions reconstruct identical prior lexical order; no
helper framework is justified. Literal sources and exact-record action
association remain owned at the shared utility and CLI consumers; no import
contract, JSON or persisted-schema expansion. U1 cancellation/failure capture
and U4 parsers remain intact. Shared architecture/CLI deltas are accurate.

Wave B test map:

| Obligation | Representative proving test |
| --- | --- |
| F-014 | `test_unapplied_alignment_warning_preserves_adversarial_label_and_semantics` (whole-label and ANSI substitution, invariant semantic fields) |
| F-015 | `test_align_pre_review_summary_uses_frozen_fragments` (manual zero/nonzero, computed, cached, reviewed; both owners) |
| Genuine skip | `test_report_confirmed_report_failure_skips_prompt_and_publish`; `test_auto_refinement_too_few_samples_remains_a_skipped_warning` |
| Record association | `test_post_upload_association_requires_record_equality`; equality-copy shortcut/webhook row dedup |
| Presentation cap/count | `test_result_summary_warning_headline_cap_and_verbose_expansion` |
| JSON omission/bytes | `test_run_json_is_machine_only_and_omits_post_upload_actions`; `test_json_review_diagnostics_stay_on_stderr_and_run_stdout_is_pinned` |
| V1 bytes/count/cap/privacy | `test_warning_record_bytes_preserve_count_cap_and_sanitization` |
| Retry source selection | `test_run_analyze_phase_confirmed_full_window_retry_recomputes_cache_domain`; superseded frame-plan replacement |
| Failure warning sink | `test_reserved_warning_sink_survives_prep_failure`; real interrupt failure-record/client-close controls; completed-write degradation |

Counts overlap integration and are not summed. Heavy gates and all recorded
physical/platform acceptance remain open. Wave C documentation is released
against the final reviewed code at `12b2eee1`.

U11 dispatch uses the current `worker-luna.toml` responsibility text and explicit
`gpt-5.6-luna` / `xhigh`. Self-contained handoff covers full-plan/findings routes,
F-017–F-020 and approved D-02, final code baseline, unit-only document ownership,
exact shared-doc deltas returned to the orchestrator, historical versus current
platform evidence, bounded checks and original human callback authorization.
No feature, platform-proof, design or consequential decision authority is granted
to the Luna chat. It must return such a question through the human/controller.

### U11 integration evidence

Seven unit-owned guides reconcile wizard scope/default publishing, report-local
date/time with exact ISO metadata, metrics-conditional fastest/cache-only
guidance, approved symlinked preset writes and historical offscreen evidence.
Orchestrator applied the corresponding CLI-contract and architecture deltas.
Historical 2026-10-07 handoff explicitly reports the Linux-container offscreen
three-source session, panel, frame-0 outputs, sidecar and cleanup on macOS Docker
Desktop; no current GUI run or independently authenticated raw log is claimed.
Current X11 wrapper, visible desktop and physical native acceptance stay open.
The runbook's bounded historical evidence already agrees and needed no edit.
No runtime, platform posture, preset containment or wizard feature change.

Focused checks repeated at integration: CLI docs (3), generated timestamp (4),
fastest preparation (4), preset save (8), first-use wizard (1), and metrics-
required fastest/cache-only dry-run refusal (1): **21 passed, no skips**.
Source inspection confirms ISO `datetime`/tooltip preservation and existing
preset-directory-link filesystem behavior. Whole-tree pyright zero errors/
warnings, Ruff check/format pass (520 files), bandit medium/high pass (22 low),
and both import contracts kept. Diff-check passes. No new test/harness or
media/browser/Docker/site run was introduced for prose-only changes. Exact
runtime/platform and strict-site acceptance remains for the final serial gates.
Configured `worker_luna` / `gpt-5.6-luna` / `xhigh` matches creation; actual
sampler settings cannot be independently observed.
