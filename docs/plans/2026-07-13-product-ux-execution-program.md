Status: Active
Scope: Approved CLI ergonomics, diagnostics, run history and safe rerun, guided setup, and generated-report review UX
Owner: Frame Compare maintainer and executing Codex sessions
Updated: 2026-07-13

# Product and UX execution program

## 1. Executive decision

Deliver the approved product improvements as a sequence of independently releasable
packages, not as one long-lived feature branch or a broad UI rewrite. Each package
must have one clear owner seam, its own public-contract update, targeted tests, the
repository full-verification gate, diff inspection, and an independent final review
when it changes a high-risk surface.

The sequence is intentionally ordered from low-coupling CLI improvements through
new persisted state and only then into interactive report work:

1. CLI discoverability and `inputs open`.
2. Side-effect-free `run --dry-run`.
3. Focused diagnostics and final-selection output improvements.
4. Run outcome persistence and read-only history commands.
5. Safe rerun, only after its feasibility gate passes.
6. Goal-oriented wizard redesign, after its prompt/profile contract is approved.
7. Report interaction design gate.
8. Magnifier and pixel inspection.
9. Grid comparison.
10. Local review state with versioned export/import.
11. Blind A/B, only after an identity-leak audit proves it can be honest.

This program preserves `comparison_videos` as the default folder-first input
workflow. It does not add positional source-file arguments or require users to type
long media paths.

## 2. Goals and non-goals

### Goals

1. Make the existing CLI workflow easier to discover and safer to operate without
   changing the folder-first mental model.
2. Let users understand what a run would do before media probing, rendering,
   persistence, network activity, or browser launch.
3. Make failures and successful selections easier to understand using existing
   typed diagnostic and orchestration facts.
4. Add a small, durable, versioned run-history foundation with deterministic,
   atomic filesystem behavior.
5. Support a guarded "repeat these saved settings against these verified inputs"
   workflow without claiming bit-for-bit reproducibility.
6. Improve guided setup without inventing a second configuration or preset system.
7. Turn the generated report into a stronger inspection workspace while preserving
   its static, offline, report-first architecture.
8. Keep implementation slices small enough to review, revert, and release
   independently.

### Non-goals

- No positional media-file mode; `comparison_videos` remains the default input seam.
- No visual frame-plan or timeline-selection visualization.
- No motion-sample generation, objective quality metrics, or generic resume of an
  interrupted run.
- No server, database, account system, report backend, or background daemon.
- No full-screen application shell or wholesale report visual redesign.
- No framework migration for the static HTML report.
- No `doctor --fix`, automatic package installation, or silent environment mutation.
- No feature-flag framework solely for these changes.
- No abstract repository layer, generic command bus, plugin system, or generalized
  persistence framework.
- No promise that reruns are bit-identical across Frame Compare, FFmpeg,
  VapourSynth, model, or operating-system versions.
- No blind mode that merely hides labels while filenames, baked overlays, metadata,
  or ordering still reveal source identity.

## 3. Program-wide invariants

Every package must preserve these invariants:

- `frame_compare.cli.entry` remains a thin, lazy composition root. Command behavior
  belongs in focused `cli/*_command.py` owners.
- Orchestration phases coordinate existing owners; they do not absorb CLI rendering,
  persistence parsing, browser policy, or report interaction logic.
- Services remain side-effect owners with typed inputs and outputs. Cross-layer
  imports continue to satisfy `importlinter.ini`.
- Human output uses stderr where required by the current CLI contract. JSON stdout
  remains exactly one JSON document with no progress, Rich markup, browser noise,
  or diagnostic text.
- New public CLI, config, JSON, persistence, and report behavior is documented in
  `docs/current-cli-contract.md` in the same package that changes it.
- Persisted files are versioned, deterministic, atomically replaced, and contained
  beneath the configured workspace root. Readers fail closed on malformed or
  unsupported data.
- Secrets, API keys, webhook headers, tokens, environment values, tracebacks, and
  absolute paths outside the workspace are never written to history or replay
  records.
- A convenience command never invokes a shell string. External processes receive
  argument arrays through the existing subprocess boundary.
- Existing user configuration and legacy run folders are never rewritten as an
  implicit migration.
- Report state stays offline and local to the browser unless the user explicitly
  exports a JSON file.
- Accessibility is part of the report interaction contract: keyboard access,
  visible focus, semantic controls, reduced-motion behavior, readable contrast,
  and touch/pointer parity are not follow-up work.
- New behavior reuses current owners and data when they are already sufficient.
  Duplicate summaries, parallel configuration models, and compatibility shims are
  out of scope.

## 4. Ownership map

| Concern | Primary owner | Composition seam | Explicitly kept out |
| --- | --- | --- | --- |
| CLI registration and lazy imports | `src/frame_compare/cli/entry.py` | Typer registration only | Business logic, persistence, platform subprocess policy |
| Input-folder open command | New focused `src/frame_compare/cli/inputs_command.py` | Registered by `entry.py`; reuses configured path resolution | Orchestration and report code |
| Dry-run planning and rendering | New focused `src/frame_compare/cli/dry_run.py` plus `run_command.py` dispatch | Runs before `Runner.run` | `RunRequest`, orchestration phases, media probing, persistence |
| Doctor remediation facts | `src/frame_compare/orchestration/doctor_checks.py` | Existing `DoctorReport` and CLI renderers | New repair engine or platform mutation |
| Selection summary | New focused `src/frame_compare/orchestration/selection_report.py` | Called after final aligned selection is known | `RunResult` growth solely for live human output |
| Run creation identity | Existing `src/frame_compare/services/run_info.py` | Existing preparation flow | Outcome mutation or replay settings |
| Run outcomes | New `src/frame_compare/services/run_result_record.py` | Minimal lifecycle calls from orchestration | CLI history rendering and config reconstruction |
| Replay settings and input manifest | New `src/frame_compare/services/run_replay.py` | Written after run reservation; read by history CLI | Secrets, publishing authorization, source discovery policy |
| History CLI | New `src/frame_compare/cli/history_command.py` | Uses run-record service APIs | Direct TOML parsing and arbitrary path opening |
| Guided wizard | Existing `src/frame_compare/cli/wizard_command.py`, split only if measured size/cohesion requires it | Existing config load/write and preset owners | New profile engine or runtime imports |
| Report payload and markup | Existing `src/frame_compare/services/report/*` owners | Renderer and payload contracts | Browser persistence policy and orchestration logic |
| Viewer interactions and state | `src/frame_compare/services/report/assets/viewer.js` and `viewer.css` | Existing embedded payload | New web framework, server, or Python callback layer |

Adding a new module in this map is justified only where it gives a new public or
persistence behavior one owner. Do not pre-create empty abstractions for later
packages.

## 5. Release and branch workflow

Each numbered package below is its own branch/PR or equivalent reviewable commit
series. Integrate packages in dependency order and start each package from the
latest integrated base. Do not keep the entire program open in one implementation
branch.

For every package:

1. Restate the package scope and stop conditions in the task before editing.
2. Load one process skill and only the boundary skills required by that package.
3. Inspect the named owner seams and current tests; do not begin with a broad repo
   refactor.
4. Add or update contract tests before or with production behavior.
5. Update the relevant authority docs in the same change.
6. Run targeted verification while iterating, then the full gate before handoff.
7. Inspect `git diff`, `git status`, generated/untracked files, and unrelated user
   changes.
8. Obtain one independent final review for high-risk CLI, config, persistence,
   orchestration, services, browser-open, or report packages; adjudicate findings
   against evidence before changing code.
9. Merge/release only when the package is independently useful and revertable.

Use conventional commits. Avoid drive-by cleanup; record discovered unrelated debt
separately rather than expanding a package.

Use the copy/paste session packets in
[`docs/product-ux-package-handoffs.md`](../product-ux-package-handoffs.md). That
companion contains workflow instructions only; this active plan remains the sole
authority for product behavior, package scope, and stop conditions.

### Authorized persistent-controller mode

The maintainer authorized a single persistent main controller to execute this
program through depth-one subagents instead of requiring a fresh manually prompted
main session for every unit. This changes execution topology only; it does not relax
any package contract, dependency, proof, review, approval, or stop condition.

In this mode:

- the main task is the sole authoritative controller and owns scope, integration,
  user communication, conflict resolution, verification, review adjudication,
  remediation, staging, commits, and ledger state;
- one fresh bounded implementation worker may write the current unit; it receives a
  decision-complete packet and may not delegate, broaden scope, or use git;
- the controller inspects the worker's actual diff and reruns required proof;
- one separate fresh read-only reviewer receives no implementation transcript and
  may not edit, delegate, or use git;
- the controller adjudicates every review finding, fixes accepted/modified issues
  itself, reruns affected proof, and requests closure review only after a material
  fix;
- only one writer is active at a time, dependent units are never parallelized, and
  the controller continues automatically after a successful checkpoint;
- the controller pauses for Unit 6A approval; Unit 7 approval; a maintainer decision
  required by Unit 5 or Unit 11; any named package stop condition; an unplanned
  public, architecture, or authority contract; overlapping unrelated user changes;
  missing environment bootstrap that requires installation authority; a failed
  required proof after bounded remediation; branch/push/PR or external coordination;
  dependency installation; or any other material scope/permission expansion.

The maintainer authorizes the persistent controller to stage exact task-owned files
and create local conventional commits for the workflow bootstrap, each reviewed
unit, and each mechanical ledger checkpoint. This authorization does not include
creating/switching branches, pushing, opening pull requests, installing dependencies,
or changing unrelated/external state.

Because a commit cannot contain its own hash, checkpointed closeout uses two local
commits:

1. the reviewed implementation/design commit, including same-pass authority docs,
   or a reviewed durable-evidence commit for a blocked feasibility outcome;
2. a docs-only ledger checkpoint that records the first commit's immutable hash and
   promotes the row to `Completed`, `Awaiting approval`, or `Blocked` as appropriate.

A `Blocked` feasibility outcome must not commit partial production code, disposable
experiments, or an incomplete feature. After reviewing the evidence, the controller
first restores the task-owned production/test surface to the integrated base through
safe explicit edits without touching unrelated changes, then may commit only the
durable evidence/design record. The ledger checkpoint records that evidence commit
and keeps dependent work stopped.
If the controller cannot separate task-owned partial work from unrelated changes, it
pauses instead of committing.

The ledger-only checkpoint may run `git diff --check`, exact row inspection, and
repository-status inspection instead of repeating the product full gate or
independent review. Approval or accepted-deferral transitions use another docs-only
checkpoint after the maintainer decision. Stage exact files only; never use
`git add .`.

### Execution ledger

Update one row at package closeout using these exact state meanings:

- `Ready`: dependency gates are satisfied and work may start.
- `Pending <dependency>`: the named dependency has not reached a promoting state;
  work may not start.
- `In progress`: one main session owns the unit.
- `Verified / awaiting integration`: implementation, proof, and review are complete,
  but the change is not yet represented by an immutable integrated reference.
- `Awaiting approval`: a reviewed decision/design artifact exists but the maintainer
  has not approved it.
- `Completed`: the accepted implementation or decision artifact is present on the
  current base and the row names its immutable commit/merge reference.
- `Approved`: a decision gate is maintainer-approved, integrated, and the row names
  both its durable contract location and immutable reference.
- `Deferred / accepted`: the maintainer accepted a reviewed deferral; the row names
  the evidence, acceptance record, and reevaluation trigger.
- `Blocked`: the unit cannot proceed and dependent work must not start.

A dependent package may begin only after the preceding row is `Completed`,
`Approved`, or `Deferred / accepted`. `Verified / awaiting integration`,
`Awaiting approval`, and `Blocked` do not promote the next row. Package sessions do
not invent an integrated reference: without explicit git authorization they stop at
`Verified / awaiting integration`, and a later authorized integration/acceptance
step advances the ledger.

| Unit | Status | Integrated reference | Verification/review | Next action |
| --- | --- | --- | --- | --- |
| 1. CLI discoverability and input open | Deferred / accepted | Deferral evidence and acceptance record in `972a34d` under [Deferred outcome (accepted 2026-07-14)](#deferred-outcome-accepted-2026-07-14) | Candidate full gate passed; independent review accepted U1-001/U1-002; clean rollback verified | Reevaluate only with approved Windows/Linux opener contract and host-proof plan |
| 2. Side-effect-free dry run | Completed | `9af60bd` | Focused CLI/contract proof and full gate passed; independent review U2-001/U2-002/U2-003 accepted, fixed, and reverified; deterministic case-fold tie gap fixed | Continue to Unit 3A |
| 3A. Doctor-hint audit | Completed | `c20c0e5` | 84 focused doctor/VSPreview/CLI tests and full gate passed; independent review U3A-001/U3A-002/U3A-003 accepted, fixed, and reverified | Continue to Unit 3B |
| 3B. Final-selection summary | Completed | `1402634` | 29 focused selection-report/lifecycle/contract tests and full gate passed; independent review found no actionable issues | Continue to Unit 4 |
| 4. Run outcomes and history | Completed | `78d1adb` | Focused persistence/lifecycle/CLI/Windows proof and full gate passed; independent review U4-001 through U4-007 accepted, fixed, closed, and reverified | Continue to Unit 5 feasibility |
| 5. Guarded safe rerun | Deferred / accepted | Deferral evidence and acceptance record in `fbbf173` under [Reviewed feasibility outcome (accepted 2026-07-14)](#reviewed-feasibility-outcome-accepted-2026-07-14) | Full feasibility gate and independent review accepted U5F-001 through U5F-005; clean rollback verified | Reevaluate only with an approved internal config-injection contract and revised proof |
| 6A. Wizard product-contract gate | Approved | Approved specification in `be32476` under [Unit 6A wizard interaction specification](#unit-6a-wizard-interaction-specification) | Plan-only structural proof passed; independent review U6A-001 through U6A-007 accepted, revised, closed, and returned APPROVABLE; maintainer approved 2026-07-14 | Continue to Unit 6B |
| 6B. Wizard implementation | Completed | `484ae6f` | Expanded focused wizard/config/source/atomic/CLI/Windows proof and full gate passed; independent review U6B-001 through U6B-003 plus controller finding U6B-C001 accepted, fixed, closure-confirmed, and returned APPROVABLE | Continue to Unit 7 design gate |
| 7. Report interaction design gate | Approved | `43c8341` | Reviewed contract at [`2026-07-14-report-interaction-design-contract.md`](2026-07-14-report-interaction-design-contract.md); U7-002 through U7-007 closed; maintainer approved 2026-07-14 with U7-001 manual browser proof deferred to final-program validation | Continue to Unit 8 |
| 8. Magnifier and pixel inspector | Completed | `d24f094` | 100 focused report tests and the canonical full gate passed; U8-R001 through U8-R007 plus controller async findings accepted/modified, fixed, closure-reviewed, and returned APPROVABLE; manual browser matrix remains deferred final-program validation debt | Continue to Unit 9 |
| 9. Multi-clip grid | Completed | `d6c5fb0` | Focused Grid/Pixel/viewer harnesses and 104 focused report tests passed; canonical pyright/Ruff/Bandit/full-pytest/import-linter gate passed after fixes; U9-R001 through U9-R004 accepted, fixed, closure-reviewed, and returned APPROVABLE; manual browser matrix remains deferred final-program validation debt | Continue to Unit 10 |
| 10. Local review state/export | Ready | — | Dependency promoted by completed Unit 9 implementation `d6c5fb0`; approved interaction contract `43c8341` | Claim Unit 10 implementation |
| 11. Blind A/B feasibility/implementation | Pending Unit 10 | — | — | Wait |

## 6. Package 1: CLI discoverability and input-folder opening

### User contract

- Add `frame-compare inputs open`.
- Resolve the input directory through the same root/config rules as `run`.
- Open that directory using the supported host mechanism: `open` on macOS,
  `xdg-open` on Linux, and the native non-shell Windows path.
- If the directory is absent, fail with the existing typed path/config error style;
  do not silently create it.
- If graphical opening is unavailable or the environment is headless/containerized,
  return a typed dependency/platform error that includes the resolved path and a
  concrete manual-open hint. Do not claim that the host folder opened.
- Keep `comparison_videos` as the documented default workflow.
- Improve command and option help with accepted choices, defaults, and a small
  number of copyable examples. Help must remain skimmable and must not become a
  second manual.

### Expected files in scope

- `src/frame_compare/cli/entry.py`
- new `src/frame_compare/cli/inputs_command.py`
- `src/frame_compare/cli/run_command.py` only for option help text
- `src/frame_compare/cli/wizard_command.py` only for help text if needed
- `tests/cli/test_help_and_import.py`
- new `tests/cli/test_inputs_command.py`
- `docs/current-cli-contract.md`
- `README.md` or the current user-facing quick-start owner, if it exposes command
  examples

### Guardrails

- Pass paths as process arguments; no `shell=True`, interpolated command, or
  shell-dependent quoting.
- Mock the platform process boundary in unit tests. Record real native verification
  only on the host platforms actually exercised.
- If the command cannot reuse the existing safe open/process seams and Typer entry
  point without packaging or runtime-architecture changes, stop and defer it. The
  approved feature is intentionally a small convenience, not a new platform layer.

### Verification and rollback

- Contract tests cover root/config resolution, paths containing spaces, missing
  directories, unsupported openers, opener failure, JSON/output cleanliness where
  applicable, and lazy `--help` imports.
- Run the repository full-verification gate.
- Rollback is removal of the subgroup and its focused owner; no persisted state is
  involved.

### Deferred outcome (accepted 2026-07-14)

Unit 1 is deferred in full. No `inputs` subgroup, opener implementation, help
change, public-contract change, or test from the candidate is shipped. The
controller explicitly removed every partial production, test, README, and CLI
authority change before recording this outcome.

The candidate passed 31 focused CLI/contract tests and the complete repository gate
(`pyright --warnings`, Ruff, Bandit at medium severity, full pytest, and both
import-linter contracts) before independent review. A fresh read-only unconfigured
reviewer fallback then identified two P1 findings:

- **U1-001 — accepted:** the installed Windows
  [`frame-compare.ps1`](../../tools/windows_portable/shim/frame-compare.ps1) shim
  injects its persisted state config for `run`, `wizard`, and `preset`, but not for
  `inputs open`. Fixing the discrepancy requires expanding the package into the
  Windows portable/release surface and its verification contract.
- **U1-002 — accepted:** documented
  [`xdg-open`](https://man.archlinux.org/man/xdg-open.1) semantics permit a successfully
  launched desktop application to remain attached for a long time. The candidate's
  ten-second synchronous timeout could therefore open a folder and still report a
  false failure. A correct replacement needs an approved launch-acceptance,
  detachment, process-lifetime, and failure-reporting contract.

The maintainer accepted deferral in the persistent controller task on 2026-07-14.
Reevaluate Unit 1 only when a new approved package explicitly includes both Windows
portable config injection and Linux opener lifetime semantics, with the matching
Windows/Linux host-proof plan. Do not revive only the cosmetic help or label portion
without reopening the complete user contract.

## 7. Package 2: side-effect-free `run --dry-run`

### Frozen behavior

`frame-compare run --dry-run` performs only:

1. root/config/preset loading and validation;
2. CLI option compatibility validation;
3. configured input-directory validation and supported-file discovery;
4. pure resolution of the planned selection strategy and declared outputs;
5. rendering a typed dry-run plan.

It does not:

- construct or call the orchestration runner;
- import or initialize VapourSynth;
- run FFmpeg, ffprobe, doctor checks, media probing, analysis, or alignment;
- read or write analysis/probe/alignment caches;
- reserve a run folder or write run metadata;
- perform TMDB, slow.pics, webhook, or other network activity;
- open a browser, copy to the clipboard, or launch VSPreview.

Human output and `--json` render the same typed DTO. JSON contains a stable,
allowlisted summary of the input directory, discovered source filenames, reference
selector, selection strategy, declared output/publishing intentions, and an
explicit `checks_not_performed` list. It never dumps the complete effective config.

The output must distinguish facts that are known without probing from facts that
cannot be known yet. For example, it may say that report generation is enabled but
must not invent the final run-folder name, selected frame numbers, clip metadata,
or output dimensions.

### Expected files in scope

- `src/frame_compare/cli/entry.py`
- `src/frame_compare/cli/run_command.py`
- new `src/frame_compare/cli/dry_run.py`
- `src/frame_compare/cli/output.py` only if the shared JSON writer is reused
- `tests/cli/test_run_command.py`
- new `tests/cli/test_run_dry_run.py`
- `tests/cli/test_run_json_errors.py`
- `docs/current-cli-contract.md`

### Architectural decision

Dry run is CLI-owned and exits before `RunRequest` construction. Do not add a
`dry_run` flag to `RunRequest`, the phase plan, or the runner; doing so would force
every runtime owner to defend against accidental side effects.

### Stop conditions

- If current input discovery cannot be called without runtime initialization or
  writes, extract only its pure filename-discovery policy into a focused owner.
- Stop rather than simulate media-derived values or build a parallel orchestration
  graph.

### Verification and rollback

- Tests use sentinels that fail if runner construction, subprocesses, network,
  cache access, run-folder writes, browser open, or clipboard access occurs.
- Test invalid config, no inputs, incompatible options, human output, and exact JSON
  shape/stream discipline.
- Run the repository full-verification gate.
- Rollback removes the option and DTO; no migrations are required.

## 8. Package 3A: doctor-hint quality audit

The current doctor model already owns `CheckResult.hint`, exposes it as
`install_hint` in JSON, and renders it in human output. Improve the facts, not the
framework.

### Scope

- Audit each failing/warning check for a deterministic, platform-appropriate next
  action.
- Distinguish missing executable, unusable version, unavailable optional feature,
  bundle corruption, network failure, and configuration failure where the check
  can prove that distinction.
- Keep hints short and directly actionable. Include an exact command only when it
  is safe and correct for the detected platform/install mode.
- Preserve existing status, exit-code, and JSON field names.

### Non-goals and stop conditions

- No automated repair, package-manager detection matrix, shell execution, or broad
  environment recommendation engine.
- Do not guess an install command when the application cannot identify the install
  mode. Prefer a precise diagnostic and documentation pointer.

### Expected files and proof

- `src/frame_compare/orchestration/doctor_checks.py`
- `src/frame_compare/orchestration/doctor_types.py` only if a proven missing typed
  fact is required
- `tests/orchestration/test_doctor*.py`
- `tests/cli/test_doctor_command.py`
- `docs/current-cli-contract.md`
- Run targeted doctor tests, then the full-verification gate.

## 9. Package 3B: final-selection summary

The existing `Clip Overview` already reports per-clip resolution, frame rate, frame
count, HDR state, and path after sources load. Preserve it and remove or correct any
stale TODO that says clip metadata is missing.

Add one verbose human summary after alignment has produced the final selection. It
reports the final frame count and the counts/ranges attributable to available
selection categories such as user, dark, bright, motion, and random. It must use the
existing `SelectionBreakdown`; it does not recalculate selection or add data solely
for presentation.

### Owner and contract

- Put formatting/emission in a focused
  `src/frame_compare/orchestration/selection_report.py`, parallel to
  `fps_report.py`.
- Invoke it at the phase boundary where the final aligned selection and breakdown
  are both known.
- Emit only for verbose human runs. Keep quiet mode quiet and JSON stdout unchanged.
- Do not enlarge `RunResult` solely to route live console output.

### Expected proof

- New focused selection-report tests.
- Phase integration tests prove it uses the post-alignment selection, stays absent
  in normal/quiet/JSON modes, and handles user-only or unavailable breakdowns.
- Update CLI authority prose and run the full-verification gate.

## 10. Package 4: run outcomes and read-only history (Stage 1)

### Persistence contract

Keep `run_info.toml` as immutable creation identity. Add a separate, versioned,
atomically written `run_result.toml` under each reserved run folder.

The initial schema contains only durable facts needed for history:

- schema version;
- `completed`, `completed_with_warnings`, or `failed` status;
- start/completion timestamps and elapsed duration;
- paths to the report and screenshot directory relative to the workspace root;
- clip count and final selected-frame count;
- existing phase-timing/cache summary facts where available;
- sanitized warning summaries;
- slow.pics outcome and URL when one exists;
- for failure, a stable error code/category and sanitized message, never traceback or
  exception representation.

Do not duplicate configuration or replay settings in this file. That belongs to
the separate Stage 2 replay record.

### Lifecycle behavior

- Write the final result after post-run outputs have settled.
- On a run failure after folder reservation, make one best-effort failure-record
  write and then preserve the original error and exit code.
- A result-record write failure must not turn completed media work into a failed
  comparison. Surface a structured warning; the folder appears as `unknown` in
  history if no valid record exists.
- Failures before run-folder reservation create no history entry.
- Legacy folders with no `run_result.toml` remain readable as `unknown`; never
  migrate them implicitly.

### CLI contract

- `frame-compare history list` lists run folders newest first with deterministic
  tie-breaking and concise status/time/report availability.
- `frame-compare history open RUN_NAME` accepts an exact run-folder name, validates
  that the stored relative report path resolves beneath the configured generated
  root, and reuses existing browser-open policy.
- Malformed/unsupported records are displayed as unavailable with an actionable
  warning; one bad folder does not hide valid history.
- No delete, rename, search, pagination, database, or fuzzy matching in Stage 1.
- Provide a stable allowlisted `history list --json` shape and keep stdout clean.

### Expected files in scope

- new `src/frame_compare/services/run_result_record.py`
- minimal lifecycle calls in `src/frame_compare/orchestration/coordinator.py` or a
  focused lifecycle helper selected after inspection
- new `src/frame_compare/cli/history_command.py`
- `src/frame_compare/cli/entry.py`
- service, orchestration lifecycle, and CLI contract tests
- `docs/current-cli-contract.md`
- `docs/current-architecture.md` if the new persistence owner changes the durable
  architecture map

### Verification and rollback

- Round-trip, schema-version, malformed-file, atomic-write, containment, legacy
  folder, partial-failure, and deterministic-order tests are required.
- Verify report opening cannot escape the generated root through `..`, absolute
  paths, or symlinks according to the repository's current containment policy.
- Run the full-verification gate.
- Rollback can leave `run_result.toml` files in old runs; older versions ignore
  them. Never require destructive cleanup.

## 11. Package 5: guarded safe rerun (Stage 2)

### Feasibility gate

Do not implement this package until a focused spike proves all of the following
without changing the runner-wide configuration contract:

1. a redacted effective configuration can round-trip with all semantically relevant
   Pydantic explicit-field state preserved;
2. current input names and existing stat-based fingerprints can be compared before
   a new run starts;
3. replay construction can reuse existing config override and source-discovery
   owners rather than introduce a second config loader or source-selection path;
4. publishing can be disabled by default independently of saved settings.

The spike is test code or a disposable local experiment, not a shipped abstraction.
If any point requires a broad `ConfigSchema`, `RunRequest`, or orchestration refactor,
defer rerun and keep Stage 1 history. That is the main downside boundary.

### Reviewed feasibility outcome (accepted 2026-07-14)

Unit 5 cannot clear its frozen feasibility gate on the current runtime seams. No
`history rerun` command, replay writer, production change, or feasibility test is
shipped. The controller explicitly removed the disposable test-owned spike before
recording this evidence.

The candidate spike passed 10 focused tests, 275 adjacent config/source/history
tests, Ruff, strict Pyright, Bandit at medium severity, the full pytest suite, and
both import-linter contracts. A fresh read-only adversarial reviewer then rejected
the feasibility claim. The controller accepted every finding from source evidence:

- **U5F-001 — accepted, blocking:** the spike reconstructed configuration only in
  test helpers. The real preparation path still reloads configuration from
  `RunRequest.config_path` in `orchestration/preparation.py`; there is no existing
  owner-compatible seam that can deliver reconstructed values plus recursive
  Pydantic explicit-field state to the runner. Proceeding requires an approved,
  narrowly owned internal configuration-injection contract across the request,
  preflight, and preparation boundary. A temporary parallel loader or config path
  would violate the package constraints.
- **U5F-002 — accepted:** the isolated proofs did not exercise reconstruct, force
  `no_upload=True`, then run as one sequence. The canonical override rebuild loses
  `model_fields_set` inside mappings of `SourceOverrideConfig`, changing explicit
  `None` versus omitted state. Any approved implementation must restore the complete
  saved recursive state after applying the forced publishing override or narrowly
  repair that owner.
- **U5F-003 — accepted:** `ConfigSchema.model_validate()` can rehydrate omitted
  slow.pics/TMDB settings and secrets from current settings sources. Default-off
  publishing must be proved after reconstruction under hostile current publishing
  configuration, not only against an ambient secretless environment.
- **U5F-004 — accepted:** the spike used JSON even though the required artifact is
  TOML. Explicit `None` is not directly TOML-serializable, so a versioned tagged or
  omission-plus-explicit-state encoding must be proved for `None`, `Fraction`, enum,
  and color-preset semantics before the target persistence format is feasible.
- **U5F-005 — accepted:** the section-wide audio-alignment projection retained
  `use_vspreview`, `force_interactive`, `cache_results`, and `previous_offsets`,
  contrary to the rule against replaying presentation/runtime and cache-only policy.
  A reviewed field-level semantic classification is required.

The accepted names plus size/`mtime_ns` manifest remains intentionally
non-cryptographic and has a validation-to-run race; those are documented residual
limitations, not the blocker. The maintainer accepted Unit 5 deferral in the
persistent controller task on 2026-07-14. Reevaluate rerun only when a new approved
package includes the internal configuration-injection contract and a revised
feasibility proof covering all five findings.

### Replay persistence contract

On normal runs, atomically write a separate versioned `run_replay.toml` after source
identity is available but before analysis, rendering, or external publishing. It
contains:

- redacted effective config values required by runtime behavior;
- recursively captured explicit-field state needed to reproduce Pydantic semantics;
- semantic CLI overrides that affect comparison behavior;
- input-directory identity plus ordered input-relative source names and the same
  size/mtime source fingerprints already owned by current probe/cache identity;
- Frame Compare version and relevant runtime identity facts.

It never contains secrets, tokens, webhook headers, presentation-only flags, or an
authorization to republish.

### Rerun contract

- Add `frame-compare history rerun RUN_NAME`.
- Revalidate the stored schema, path containment, and complete source manifest.
- The current discovered source set must match recorded names and fingerprints
  exactly. Added, removed, renamed, or changed inputs fail closed with a diff-style
  explanation. Do not add an alternate explicit-file runtime path just for rerun.
- Document that stat-based fingerprints detect ordinary source changes but are not
  cryptographic proof of identical media bytes. Do not impose full-file hashing on
  multi-gigabyte videos without a separate measured performance decision.
- Always create a new run folder; never mutate or resume the old one.
- Restore comparison-semantic settings. Do not restore `--json`, `--quiet`,
  `--no-color`, browser-open state, clipboard behavior, or cache-only policy.
- Disable slow.pics, webhook, and other publishing by default. A separate explicit
  `--with-publishing` opt-in uses current secrets and current safety validation.
- Treat this as "repeat saved settings with verified current inputs," not as
  bit-for-bit reproducibility. Warn on version drift and fail on unsupported replay
  schema versions.

### Required tests

- Secret-redaction tests with sentinel values.
- Recursive config/explicit-field round trips, including color/tonemap behavior.
- Changed/added/removed/renamed input rejection.
- Path traversal and symlink containment.
- New-folder guarantee and old-folder immutability.
- Publishing disabled by default and explicitly enabled only through the new flag.
- Version drift, malformed record, legacy history, JSON/output, and original error
  preservation.
- Full-verification gate and independent final review.

### Rollback

Remove the rerun command and replay writer. Existing `run_replay.toml` files are
ignored by older code and remain harmless. Do not delete user run folders.

## 12. Package 6: goal-oriented wizard redesign

### Product-contract gate

Before editing production prompts, write a short wizard interaction spec and obtain
maintainer approval for:

- the exact goal choices and names;
- the exact config fields each choice changes;
- whether choices are code-owned guided defaults or saved user presets;
- behavior when a config already exists;
- source/reference confirmation behavior when files are already present;
- final review/confirmation copy.

Record the complete reviewed specification in this active plan (or in a tracked
supporting document linked from this section) before requesting approval. The Unit
6A ledger row must name that durable location. Record maintainer approval and its
immutable integrated reference in the row before Unit 6B begins; chat-only approval
or an untracked artifact is not a sufficient cross-session contract.

Do not ship vague labels such as "best" or "high quality" without showing their
concrete consequences. Do not invent built-in presets that silently diverge from
the existing preset merge contract.

### Unit 6A wizard interaction specification

Status: approved by the maintainer on 2026-07-14. Immutable design reference:
`be32476`. Any change to a frozen goal, patch, consequence, prompt order, stream, or
exit contract requires renewed durable approval before implementation continues.

Review record (2026-07-14): U6A-001 through U6A-007 were accepted, resolved in the
durable contract, and confirmed closed by the same read-only reviewer after material
revision. Closure review found no directly introduced issue and returned
`APPROVABLE`. Residual TTY, hostile-environment, Windows portable, raw-TOML,
redaction, and atomic-failure proof belongs to Unit 6B.

#### Intent and ownership

`wizard` becomes a goal-oriented editor for frame-selection configuration. It does
not run comparisons, probe media, create a second preset system, or ask users to
choose an unexplained quality tier. Guided goals are code-owned, typed, partial
patches with one wizard owner. They are not saved presets and never appear in
`preset list`; user-created presets remain exclusively owned by the existing
`config.presets` merge/save contract.

Unit 6B adds no command, option, or `ConfigSchema` field. The selected config path,
path-containment rules, exact Windows portable state-config exception, human output
streams, and standard typed-error adapter remain authoritative. The wizard uses the
existing defaults, config validation/deep-merge, atomic text writer, deterministic
input discovery, and source-selection owners. A lightweight owner may be extracted
only if needed to reuse filename discovery without importing a runtime-heavy module;
it must not duplicate extension, ordering, or selector policy.

The redesign intentionally removes the current slow.pics visibility/deletion and
TMDB-key prompts. First use explicitly writes `slowpics.auto_upload = false` as a
file-level safety baseline. Environment settings have higher precedence and can
still enable publishing when a later run starts, so the wizard states that caveat
rather than promising effective publishing is disabled. Existing publishing values
and secrets are preserved but never displayed. Publishing setup remains available
through the documented config/environment and preset surfaces; Unit 6B updates the
current CLI authority and README in the same pass so this removal is not silent.

The wizard command owns a typed `InputError` with code `FC-3017` for its interactive-
terminal precondition, either beside the wizard or in the existing cohesive CLI
error owner. It uses the standard error adapter; Unit 6B does not create a parallel
plain-text error path. The existing config-loader owner is extended with the
smallest raw-payload validation seam needed by this workflow. That seam redacts all
Pydantic `input` values before constructing an `FC-1003` error so invalid secret-
bearing config cannot be echoed by the wizard.

#### Guided goal contract

The prompt is `What do you want to compare?` and shows consequences before input.
The numbered choices and exact partial patches are:

| Choice | Exact `analysis` patch | Consequence shown before selection |
| --- | --- | --- |
| `1. Random spot check` | `user_frames = []`, `random_frame_count = 10`, `dark_frame_count = 0`, `bright_frame_count = 0`, `motion_frame_count = 0` | Select 10 deterministic random frames using the configured seed. This does not run the luminance/motion metrics scan. |
| `2. Dark, bright, and motion coverage` | `user_frames = []`, `random_frame_count = 4`, `dark_frame_count = 2`, `bright_frame_count = 2`, `motion_frame_count = 2`, `performance_mode = "quality"` | Request 10 frames: 4 random, 2 dark, 2 bright, and 2 high-motion. This overrides `performance` mode, scans full-resolution luma for every eligible frame, can choose different frames than the 25%-sampled performance mode, and can take substantially longer. |
| `3. Specific frame numbers` | `user_frames = <validated list>`, all four automatic counts `= 0` | Use only the listed zero-based frame numbers. This does not run the luminance/motion metrics scan. |

When an existing config is loaded, prepend `0. Keep current frame selection`. It is
a true no-op: every `analysis` field remains unchanged. It is the default existing-
config choice. First use defaults to `Random spot check`; it does not show the no-op
choice because there is no prior user selection to preserve.

`Specific frame numbers` accepts one comma-separated list of 1–100 base-10,
non-negative integers, for example `0, 24, 120`. Empty entries, signs other than an
optional leading `+`, non-integers, negative values, and duplicates are rejected with
a concise inline explanation and the same prompt is repeated. Persist the accepted
values in ascending order. Validation does not probe clip length; out-of-range frame
handling remains the existing run-time selection contract and is stated in the
prompt as `Frame availability is checked when the comparison runs.`

Every goal patch leaves `random_seed`, ignore windows, quantiles, and all config
sections outside the listed fields unchanged. The coverage goal deliberately sets
`performance_mode = "quality"`; the other two goals preserve the current performance
mode because they do not request metric selectors.

#### Startup, config preservation, and candidate construction

The operation order is fixed:

1. Resolve and contain the selected config destination before reading config or
   prompting. Preserve the exact installed Windows portable exception.
2. Require interactive stdin and stdout. If either is not a TTY, fail before config
   load, prompts, or writes with input exit code 4 and stdout empty. Standard-adapter
   stderr must contain the stable semantic fragments
   `[FC-3017]`, `Wizard requires an interactive terminal.`, and
   `Run frame-compare wizard from a terminal; edit the selected TOML file directly`
   ` for automation.` Styling, the standard `✗` marker, indentation, and color follow
   the shared adapter and are not separate literal-copy contracts.
3. If the selected file exists, parse and validate it before prompting. TOML,
   schema, or contained-path failure uses the current typed config/input error and
   leaves the file byte-for-byte unchanged. Wizard validation retains error code,
   locations, types, messages, hint, stream, and exit behavior but replaces every
   raw Pydantic `input` detail with `<redacted>`. If the file does not exist, start
   from repository `ConfigSchema` defaults without reading the repository template
   as a second defaults source, and add the explicit file patch
   `slowpics.auto_upload = false`.
4. Keep the parsed existing TOML payload as the persistence base. Apply only the
   confirmed partial patches to that payload, then validate the effective candidate
   against defaults plus the complete payload. This prevents environment-only
   values or secrets from being materialized on disk, preserves unrelated supported
   and unknown TOML keys, and avoids serializing a duplicate full defaults document.
   Existing comments, whitespace, quoting style, and key order need not be preserved.
   Every unedited parsed TOML value, type, explicit key presence, table/array
   membership, date/time value, and unknown-root entry must be preserved. The current
   `prepare_toml_payload` sanitizer must not process an existing raw payload because
   it drops explicit empty strings and unsupported-but-valid raw structures.

No prompt mutates the file. Candidate state remains in memory until the final
confirmation. Environment-provided secrets may influence a later `run`, but the
wizard neither displays nor persists values absent from the selected file.

#### Input directory and reference flow

Prompt `Input directory` with the current configured value, or the repository
default on first use. Resolve relative values against `--root`; external media
directories remain allowed. A missing or non-directory value prints
`Input directory does not exist or is not a directory.` and repeats the prompt.

After a valid directory is chosen, perform filename-only discovery with the current
supported extensions and deterministic case-fold/exact-name ordering. Do not probe,
open, hash, or read media contents.

- Canonical `NoVideosFoundError`/`FC-3001` is caught only at this wizard boundary and
  converted to the zero-file branch; discovery semantics are not reimplemented.
- Zero supported files: print `No supported video files found; reference selection`
  ` is unchanged.` Preserve an existing `sources.reference`; omit it on first use.
- One supported file: list its relative filename. First use offers `Automatic`
  (default, no explicit reference) and that filename. Existing config offers `Keep`
  (default), `Automatic`, and the filename.
- Two or more supported files: list every relative filename in discovery order.
  First use offers `Automatic (first discovered: <name>)` as the default plus every
  filename. Existing config first offers `Keep current: <selector>` as the default,
  then `Automatic (first discovered: <name>)` and every filename.

For a non-empty set, invoke canonical `resolve_source_selection` once with automatic
reference before presenting the reference menu. A `DuplicateSourceStemError` fails
through its existing typed input contract before the reference prompt or write;
the wizard does not invent a second duplicate policy. `Keep` is a no-op even when
the current selector does not match a presently discovered file, but the menu and
final review warn `Current reference does not match the discovered files; a run may`
` fail until the files or selector change.` `Automatic` removes the explicit
`sources.reference` key. A filename choice stores its input-relative POSIX name and
is revalidated through canonical source selection before review. Invalid menu input
repeats without changing candidate state. Other discovery/selection failures use
their existing typed input errors and leave the config unchanged.

#### Review, confirmation, cancellation, and writes

Before confirmation, validate the full candidate and print this stable semantic
review to stdout:

```text
Review configuration changes
  Config: <resolved selected config path>
  Input directory: <old or default> -> <new>          # only when changed/new
  Reference: <old or automatic> -> <new>              # only when changed/new
  Frame selection: <old summary> -> <goal summary>     # only when changed/new
  Metric scan: disabled|quality|performance
  Publishing settings: file default disabled|preserved; environment may override at run time
  Other settings: preserved
  Sensitive values: preserved and hidden              # existing secret keys only
Write these changes? [y/N]:
```

The goal summary names the exact counts or explicit frame list; it never says only
`fast`, `best`, or `high quality`. The review includes only changed/new fields plus
the two preservation statements. Secret values, lengths, prefixes, URLs, and
environment presence are never printed. If nothing changed, print
`No configuration changes. Configuration was not written.` to stderr and exit 0
without asking for write confirmation.

Final confirmation defaults to `No`. A `No` response prints
`Canceled; configuration unchanged.` to stderr and exits 0. Ctrl-C, Typer abort, or
EOF at every prompt boundary prints exactly `Canceled; configuration unchanged.` to
stderr and exits 130. Validation errors caused by a single prompt value repeat that
prompt. A candidate-wide invariant failure uses the typed config error, exits 2,
redacts every raw input detail, and does not write.

Only `Yes` calls the existing atomic text writer once. Success prints
`Configuration written: <resolved path>` to stderr and exits 0. Serialization,
directory creation, permission, replacement, or fsync failure uses the existing
`ConfigWriteError`/exit-2 contract. Write, flush, file-fsync, mode-preservation, and
replacement failures before a successful `os.replace` leave an existing target
byte-for-byte unchanged. Temporary-file cleanup is best effort: cleanup failure may
leave the hidden sibling temp file and is attached as a note to the original error.
The contract does not claim parent-directory fsync or rollback after a successful
replace.

#### Representative terminal transcripts

First use with multiple clips:

```text
$ frame-compare wizard
Input directory [comparison_videos]:
Found 3 video files: Encode-A.mkv, Encode-B.mkv, Reference.mkv
Reference:
  1. Automatic (first discovered: Encode-A.mkv)
  2. Encode-A.mkv
  3. Encode-B.mkv
  4. Reference.mkv
Select [1]: 4
What do you want to compare?
  1. Random spot check — 10 deterministic random frames; no metrics scan
  2. Dark, bright, and motion coverage — 4 random + 2 dark + 2 bright + 2 motion; full-resolution quality scan of every eligible frame (overrides 25%-sampled performance mode and can take substantially longer)
  3. Specific frame numbers — only the zero-based frames you enter; no metrics scan
Select [1]: 2
Review configuration changes
  Config: <root>/config/config.toml
  Input directory: <not configured> -> comparison_videos
  Reference: automatic -> Reference.mkv
  Frame selection: <default> -> 4 random + 2 dark + 2 bright + 2 motion
  Metric scan: quality
  Publishing settings: file default disabled; environment may override at run time
  Other settings: preserved
Write these changes? [y/N]: y
Configuration written: <root>/config/config.toml
```

Existing config with a secret and specific frames:

```text
$ frame-compare wizard
Input directory [comparison_videos]:
Found 2 video files: Encode.mkv, Reference.mkv
Reference [Keep current: Reference.mkv]:
What do you want to compare?
  0. Keep current frame selection
  1. Random spot check — 10 deterministic random frames; no metrics scan
  2. Dark, bright, and motion coverage — 4 random + 2 dark + 2 bright + 2 motion; full-resolution quality scan of every eligible frame (overrides 25%-sampled performance mode and can take substantially longer)
  3. Specific frame numbers — only the zero-based frames you enter; no metrics scan
Select [0]: 3
Frame numbers (comma-separated): 0, 24, 120
Frame availability is checked when the comparison runs.
Review configuration changes
  Config: <root>/config/config.toml
  Frame selection: 10 random -> frames 0, 24, 120
  Metric scan: disabled
  Publishing settings: preserved; environment may override at run time
  Other settings: preserved
  Sensitive values: preserved and hidden
Write these changes? [y/N]: n
Canceled; configuration unchanged.
```

Non-interactive use:

```text
$ printf '\n' | frame-compare wizard
✗ Error [FC-3017]: Wizard requires an interactive terminal.
  Hint: Run frame-compare wizard from a terminal; edit the selected TOML file directly for automation.
# exit 4; stdout empty; no file read or written
```

#### Unit 6B behavior-first test matrix

| Area | Required public/integration proof |
| --- | --- |
| Goal patches | Each numbered choice yields exactly its listed partial patch and consequence summary; existing no-op preserves every analysis field; specific frames cover retry, sorting, duplicates, negatives, empty entries, and 100/101 bounds. |
| First use | Missing selected config starts from schema defaults, supports zero/one/many discovered files, writes only the confirmed minimal payload including explicit `slowpics.auto_upload = false`, never claims to override the environment, and proves effective environment precedence with a hostile sentinel. |
| Existing config | Every unrelated parsed value/type/key, unknown TOML section, empty string, date/time, array-of-tables, dotted/nested table, relative path, explicit value, and sentinel secret survives; environment-only sentinels are neither shown nor persisted; invalid existing TOML/schema/path redacts all raw validation inputs and fails before prompts. |
| Source flow | Canonical extension/order/selector owners are reused; FC-3001-only empty adaptation, zero/one/many, case-fold ties, duplicate-stem rejection before reference prompting, nested relative names if supported by the owner, stale-current warning, automatic removal, explicit reference, discovery error, and external input directory are covered without probe calls. |
| Review/privacy | Semantic diff contains only changes and preservation summaries; no secret value/length/prefix/URL/environment fact appears in stdout, stderr, exception text, or snapshots. |
| Cancellation | Final `No`, Ctrl-C/abort, and EOF at each prompt boundary emit the exact cancellation line, never call the writer, and preserve existing bytes; no-op exits 0 without confirmation/write. |
| Terminal/errors | stdin and stdout TTY combinations, `NO_COLOR`, wizard-owned FC-3017/exit 4 through standard-adapter semantic fragments, redacted typed parse/validation/path errors, separate stdout/stderr, and absence of unsupported `--verbose` advice are asserted. |
| Persistence | Exactly one atomic write occurs after `Yes`; success, parent creation, serialization, permission, pre-replace file-fsync/replace failure, old-target preservation, successful-replace boundary, best-effort temp cleanup, and cleanup-failure note are covered without claiming parent-directory durability. |
| Platform/architecture | Explicit contained config, rejected escaping config, exact Windows portable state path, command help/lazy-import sentinels, no media probe/runtime-heavy import, preset isolation, CLI authority/README transcript drift, full gate, and import contracts pass. |

Tests assert semantic prompt fragments and parsed TOML, not complete Rich/terminal
snapshots. CliRunner remains sequential; subprocess/entrypoint tests use explicit
timeouts and controlled TTYs.

#### Files, non-goals, rollback, and stops

Expected Unit 6B owners are the existing wizard command/entry wiring and wizard-
owned FC-3017 type, the smallest extension of the existing config loader/merge/write
owner needed to preserve raw values and redact invalid inputs without persisting
environment values, focused wizard/config/atomic-boundary tests, and the current
CLI/README authority. Split `wizard_command.py` only if measured cohesion requires
it. Do not change the global error formatter, preset semantics, schema fields, run
flags, runtime orchestration, media probing, report UX, or comparison algorithms.

Rollback restores the prior wizard implementation and its authority text; because
the new flow writes ordinary valid config through the existing atomic owner, no
migration or user-file deletion is required.

Stop Unit 6B before coding or integration if preserving an existing file requires
persisting environment-only values, secrets cannot be redacted from every review or
error path, canonical filename/reference reuse requires a runtime-heavy import or a
second selector policy, atomic replacement cannot preserve old bytes, the Windows
portable exception would diverge, or implementation requires a new command, flag,
schema field, preset engine, dependency, or media probe. Any changed goal name,
field patch, consequence, prompt ordering, or stream/exit behavior requires renewed
maintainer approval in the durable Unit 6A contract.

### Recommended implementation contract

- Keep the wizard a guided editor of `ConfigSchema`, not a second runtime path.
- Load and preserve an existing valid config, including unrelated supported fields
  and secrets, unless the user explicitly changes them.
- For first use, begin from repository defaults.
- Detect filenames in the configured input folder without probing media or importing
  runtime-heavy modules. Let the user confirm the reference selector when useful.
- Present a final concise review of changes and write once, atomically, only after
  confirmation. Cancellation and validation failure leave the old config intact.
- Continue using the existing preset owner for actual user presets. If guided goals
  are approved, represent them as small typed config patches with one owner and
  contract tests; do not duplicate full TOML defaults.

### UX and verification

- Use `cli-contract-boundaries`, `python-test-design`, and `verification-strategy`.
  The web interface-design skill is not the design owner for terminal prompts.
- Test first-run, existing-config edit, cancellation at each destructive boundary,
  secret preservation, invalid input recovery, non-interactive failure, no-TTY
  behavior, and atomic write failure.
- Record representative prompt transcripts in tests or authority docs; avoid broad
  snapshots that fail on harmless Rich formatting.
- Run the full-verification gate.

## 13. Package 7: report interaction design gate

No report feature code begins until this gate is approved. At the start of the
package, explicitly load and apply `interface-design`, `report-output-patterns`,
`python-test-design`, and `verification-strategy`.

### Required design foundation

Document before prototyping:

- **Intent:** a precise inspection workstation for finding and recording visible
  differences, not a generic dashboard.
- **Palette:** preserve the existing cinema-black/charcoal technical surface with a
  restrained reference cyan and warning/annotation amber; verify contrast rather
  than broadening the palette.
- **Depth:** preserve the report's current restrained depth model; use layering only
  where the magnifier or docked inspector requires it.
- **Surfaces:** define toolbar, image stage, comparison grid, docked inspector,
  floating lens, and review panel hierarchy.
- **Typography:** retain the current readable UI stack and numeric treatment unless
  evidence demonstrates a problem.
- **Spacing:** define a compact base unit and responsive density rules appropriate
  to image inspection.

The signature interaction is the coordinate-linked magnifier/pixel inspector, not
decorative dashboard chrome.

### Prototype matrix

Build a disposable, non-production prototype using representative generated report
data for:

- two, three, four, and more-than-four clips;
- 16:9, ultrawide, portrait, and very large source images;
- long labels and paths;
- reports with and without analysis categories or slow.pics;
- desktop mouse, keyboard-only, touch-sized viewport, reduced motion, and browser
  zoom;
- loading/error/missing-image/import-conflict states.

Prototype artifacts stay ignored or outside `src/`. Inspect them in the in-app
browser at multiple viewport sizes. Capture screenshots for the task review, not as
permanent generated repo assets unless the maintainer approves them.

### Decisions that must be frozen

- magnifier default presentation and lens/dock relationship;
- zoom levels, sampling behavior, coordinate display, and ROI lock semantics;
- linked pan/zoom behavior and responsive grid layout;
- keyboard model and touch fallback;
- bookmark/tag/note information model and local-storage scope;
- versioned export/import schema and report-identity mismatch policy;
- identity-leak definition for blind A/B.

Record the complete reviewed interaction contract in this active plan (or in a
tracked supporting document linked from this section). The Unit 7 ledger row must
name that durable location plus the maintainer approval and immutable integrated
reference. Disposable prototypes and screenshots are supporting evidence, not the
cross-session contract consumed by Units 8 through 11.

Approval of this design gate permits the following implementation packages; it does
not authorize a broad report rewrite.

### Unit 7 reviewed design outcome (manual proof deferred 2026-07-14)

The reviewed contract is
[`2026-07-14-report-interaction-design-contract.md`](2026-07-14-report-interaction-design-contract.md).
Its independent adversarial review accepted U7-002 through U7-007, covering the closed
export/import domain, deterministic per-mode coordinate anchors and gesture arbitration,
the presentation-blind threat boundary, memory-only import transactions, standard
inspector-tab keyboard behavior, and faithful prototype closed/open plus ROI interaction
states. Controller fixes were closure-reviewed; the reviewer returned `APPROVABLE EXCEPT
FOR U7-001` before the maintainer decision below.

U7-001 identified missing in-app-browser visual and interaction proof. On 2026-07-14 the
maintainer explicitly chose to run that manual proof after Units 8–11 are implemented so
the complete report experience can be tested and any issues fixed in the same pass. This
changes proof timing only. It does not count as a pass or waive the required desktop,
constrained/touch-width, 200% zoom, reduced-motion, keyboard traversal, inspector
open/closed, 2/3/4/6-clip, failure-state, and current-viewer continuity matrix. Program
closeout remains blocked until that evidence is recorded and accepted.

Fresh design-unit proof passed `node --check` for the disposable prototype, required
contract/scenario marker checks, `git diff --check`, and the untracked-file diff check.
No production Python changed, so production test/type/lint/security/import gates are not
claimed for this design-only unit. The reviewed contract is integrated as `43c8341`.
The maintainer explicitly approved Unit 7 on 2026-07-14. This approval promotes Unit 8
without changing the deferred final-program manual-validation obligation above.

## 14. Package 8: magnifier, locked ROI, and pixel inspector

### Interaction contract

- Provide a small docked inspector that remains useful while the main images are
  zoomed out.
- Allow an optional floating lens over the active image.
- Support an explicitly locked region of interest so the same source coordinates
  are inspected across clips and comparison modes.
- Provide a small, approved zoom set such as 2x/4x/8x, source coordinates, active
  clip/mode, and pixel values only when they can be sampled accurately.
- Reuse existing image layers and transform math. Do not introduce canvas rendering
  unless the approved design or accurate sampling proves it necessary.
- If browser color management or cross-origin restrictions make a value approximate,
  label it honestly; do not present false measurement precision.

### Architecture and proof

- Keep behavior in viewer assets and small existing report renderer/payload seams.
- Do not add orchestration data unless source-coordinate mapping truly requires it.
- Add semantic markup assertions, focused JavaScript state-harness tests, CSS
  contract tests, and manual browser visual QA at the approved matrix.
- Verify keyboard focus, escape/unlock behavior, pointer capture, high-DPI scaling,
  resize, reduced motion, and no regression to slider/overlay/diff modes.
- Run the full-verification gate and independent final review.

### Stop condition

If accurate coordinate linking cannot be derived from current payload dimensions and
viewer transforms, stop and define the smallest payload addition before coding. Do
not scatter coordinate conversions across event handlers.

## 15. Package 9: multi-clip grid comparison

### Initial contract

- Add a viewer-only grid mode; do not expand the public report `default_mode` config
  enum in the first slice.
- Use a deterministic responsive layout: two clips side by side, three with one
  larger/selected cell only if approved by the prototype, four in 2x2, and a clearly
  specified overflow policy for more than four.
- Link pan/zoom/ROI coordinates across visible cells by default.
- Keep labels and the active/reference state visible without covering comparison
  content.
- Preserve all current modes and local viewer-state behavior.

### Scope controls

- No virtualized gallery framework, detachable windows, arbitrary drag-layout
  system, or saved dashboard layouts.
- Do not add grid to persisted config until real use demonstrates a need to make it
  the generated-report default.

### Proof

- Test 2/3/4/N layouts, image load failures, long labels, synchronized transforms,
  mode switching, state persistence, responsive breakpoints, and keyboard order.
- Perform browser visual QA at the design matrix and run the full-verification gate.

## 16. Package 10: local review state and export/import

### Review model

Add only the approved local review facts:

- frame bookmark;
- optional tag from a small controlled set or explicitly approved freeform model;
- note;
- optional preferred/winning clip for that frame.

Persist them in browser `localStorage`, scoped by stable report identity and schema
version. Do not write back into the generated HTML or run directory from browser
JavaScript.

### Export/import contract

- Export a versioned JSON document through an explicit user action.
- Include report identity, clip identities, frame references, annotations, and
  export timestamp; exclude image data, secrets, absolute paths, and unrelated
  viewer preferences.
- Import validates structure, size bounds, types, tag/note length, report identity,
  clip identities, and frame bounds before changing current state.
- Reject report-identity mismatches by default. A future explicit remapping workflow
  is outside this slice.
- Apply a valid import atomically in memory/local storage; malformed or partial data
  leaves current review state unchanged.
- Treat all imported strings as text, never HTML.

### Proof and rollback

- Test storage unavailable/quota failure, corrupt stored state, schema mismatch,
  malicious strings, oversized import, duplicate bookmarks, atomic replacement,
  and export round trip.
- Add accessible empty, dirty, saved/exported, import-error, and conflict states.
- Full-verification gate, browser visual QA, and independent final review.
- Rollback removes UI and readers; local browser data remains harmless and can be
  ignored by earlier report versions.

## 17. Package 11: blind A/B feasibility and implementation

Start with an identity-leak audit across:

- clip labels and ordering;
- filenames, paths, alt text, titles, tooltips, and accessible names;
- baked image overlays and frame labels;
- report metadata and downloadable/exported review data;
- slow.pics labels/links and browser state;
- keyboard order or styling that distinguishes the reference.

Implement blind A/B only if the report can conceal those facts for the comparison
session without creating a misleading claim. Randomize labels through a stored
per-session mapping, keep reveal explicit, and record the reveal state separately
from the vote.

If baked screenshots or payload data expose identity and fixing that requires clean
alternate renders, config changes, or a new report format, stop and create a
separate decision-complete plan. Do not ship cosmetic label hiding as "blind."

## 18. Verification matrix

Every implementation package that changes Python or product behavior runs the
repository full gate:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Use focused tests during development. Also apply these package-specific proofs:

| Surface | Additional proof |
| --- | --- |
| CLI help/open/dry-run/history/wizard | Typer runner tests, subprocess sentinels, stdout/stderr/exit-code assertions, lazy import tests |
| Persistence | deterministic round trip, atomic replacement, malformed/old/new schema, containment, permission/partial-write failure |
| Rerun | config semantic round trip, manifest mismatch, redaction, side-effect opt-in, new-run immutability |
| Report viewer | JavaScript state harness, semantic markup/CSS contracts, in-app browser interaction and multi-viewport screenshots |
| Platform folder open | mocked macOS/Linux/Windows boundaries; real checks only on available hosts, others recorded as documented-only |
| Windows portable/release files, if actually touched | the runbook Windows portable/release-path gate |
| Render/VS/Docker files, if unexpectedly required | `bash tools/verify_docker_integration.sh` plus the relevant runtime proof |

For plan-only edits, run `git diff --check` and inspect the plan and repository
status. Do not run the full product suite solely for this planning document.

## 19. Architecture and debt control checklist

Before accepting each package, answer yes to all applicable questions:

- Does one existing or newly justified focused module own the behavior?
- Did `entry.py`, `coordinator.py`, `phase_tasks.py`, `viewer.js`, or another hotspot
  receive only composition-level changes, or is any growth explicitly justified?
- Is there exactly one config/persistence/report representation of each new fact?
- Can invalid external or persisted input fail before expensive or irreversible work?
- Are secrets and absolute external paths excluded by construction, not by cleanup?
- Does rollback leave existing user runs/config/reports readable or safely ignored?
- Are platform limitations honest and tested at the boundary?
- Did the change avoid speculative interfaces, compatibility aliases, and generic
  helpers with only one caller?
- Did the tests assert behavior at the owner boundary rather than mirror internal
  implementation?
- Are authority docs and generated docs consistent with the code in the same diff?
- Is the package independently useful, releasable, and reviewable?

If a package cannot meet these checks without widening scope, stop and amend this
plan or create a separate active plan for the newly discovered workstream.

## 20. Completion and handoff

This program is complete only when every implemented package has passed its proof
surface, all explicitly deferred packages are recorded as deferred rather than
silently omitted, authority documentation reflects the shipped state, and no
active work remains under this scope.

At completion:

1. update this file from `Status: Active` to `Status: Historical`;
2. record the final shipped/deferred package matrix and any documented-only platform
   verification;
3. inspect the final repository status without altering unrelated user files;
4. hand off exact verification commands and results.

Only one active plan should own this workstream. Smaller package tasks may use
inline plans that link back here; they must not create competing active roadmap
documents.
