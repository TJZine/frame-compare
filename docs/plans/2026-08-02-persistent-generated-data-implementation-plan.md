---
search:
  exclude: true
---

Status: Active
Scope: Clean-cut implementation of the approved persistent generated-data root, unconditional run folders, canonical run-root reports, guided adoption, and Docker/Windows portable preservation proof
Owner: Controller and maintainer; bounded implementation sessions execute packages, while the controller integrates and verifies them

# Persistent Generated Data Implementation Plan

## Goal And Authority

Implement the frozen contract in the
[persistent generated-data specification](2026-08-02-persistent-generated-data-spec.md)
as a clean pre-release cutover. `paths.generated_dir` becomes the sole persistent
generated-data location; every real run receives a fresh run folder; screenshots,
the canonical local report, run records, run-local generated state, and shared caches
all follow that root; and guided Windows portable and Docker workflows preserve the
same contract.

Authority order during implementation is:

1. `AGENTS.md` and `docs/ENGINEERING_RUNBOOK.md` for workflow and verification;
2. the approved specification above for frozen product behavior;
3. `docs/current-architecture.md`, `docs/current-cli-contract.md`, and
   `importlinter.ini` for current owners and public/import contracts; and
4. current source and passing tests for the implementation impact surface.

If current source contradicts the specification or exposes an unresolved product,
ownership, compatibility, or proof decision, stop under the conditions below. Do not
rewrite the specification in an implementation package.

## Scope And Non-Goals

In scope:

- remove `report.output_dir`, `paths.use_run_folders`, and
  `paths.screenshots_dir` from supported config, generated config, presets,
  examples, runtime branches, tests, and current product documentation;
- support workspace-relative, environment-expanded, and explicit absolute
  `paths.generated_dir` values without changing the authored value during config,
  preset, or wizard persistence;
- resolve one generated-data root, enforce descendant containment, reserve one
  real immediate-child run folder for every real run, and derive the run's
  `screenshots/` and `generated/` directories;
- place the sole report at `<run-folder>/report.html`, retain report-relative
  screenshot references, and change the single V1 result record directly to
  run-folder-relative artifact paths;
- make history, CLI path presentation, shared analysis/alignment/probe caches,
  slow.pics report confirmation/cleanup, and shortcut placement consume the same
  resolved contract;
- add wizard adoption, Windows portable defaults/preservation proof, one Docker
  generated-data mount, and matching authority/user documentation; and
- update tests that currently use flat-output configuration only as fixture
  convenience so they construct canonical run-scoped paths instead.

Explicit non-goals for every package:

- migration, compatibility parsing, bespoke old-key errors, a second record version,
  dual readers/writers, report copies, redirects, shortcuts, or downgrade support;
- a database, server, archive index, multiple roots, history merging, backup/sync,
  NAS credential or mount management, or generated-data discovery outside the
  configured root;
- screenshot retention, latest-only output, pruning, quotas, recompression, or
  cleanup policy beyond the existing report-safe slow.pics behavior;
- new dependencies, speculative interfaces, generic storage abstractions, or changes
  to screenshot/run-folder naming, report viewer behavior, JSON key allowlists,
  history ordering/statuses, or slow.pics publishing semantics; and
- destructive cleanup of a user's local config, run folders, caches, or external
  generated-data directory.

## Risk, Ownership, And Execution Controls

This is high risk because it changes public config and filesystem behavior, report
and history contracts, report hotspots, Docker mounts, and Windows portable paths.
Execute packages in the listed order. Default to one writer at a time because the
path carrier and authority docs are shared integration surfaces. Parallel dispatch is
allowed only if the controller first proves disjoint production, test, and doc write
boundaries; otherwise remain serial.

At dispatch, use the configured `worker_luna` role from
`.codex/agents/worker-luna.toml` for each bounded package while its outcome, owner
seam, contracts, acceptance criteria, proof, and stop conditions remain unchanged.
Do not pin model or reasoning settings in this plan. Escalate a settled package to
the configured `worker` role only if repository evidence makes material
cross-boundary design judgment, complex diagnosis, or proof interpretation
unavoidable. Return unresolved product, ownership, architecture, compatibility, or
proof questions to planning.

The controller owns package dispatch, collision avoidance, integration, diff review,
authority synchronization, and rerunning checkpoint/final proof. A worker may discover
the exact cohesive files and routine helper/test organization inside its allowed owner
seam, but it must not cross the package boundary or invent policy.

Architecture attention applies during implementation. `orchestration/preparation.py`
and `services/run_result_record.py` are above 500 physical production lines;
`cli/run_command.py` is above 800; and `services/report/**` is a named hotspot. For
each touched owner above the threshold, the implementing handoff must record:

```text
Owner | Existing responsibility | New behavior
Decision: cohesive growth | extract
Evidence
```

Extraction is allowed only for a distinct present-day responsibility, never solely
for line count or test convenience. The final independent reviewer must adjudicate
these dispositions and reject both responsibility accumulation and thin forwarding
layers.

## Fresh Impact-Scan Evidence

The planning scan used `git status`, `rg --files`, focused `rg -n`/`rg -l` queries,
and direct reads of the owners, tests, and docs below.

- The only production `paths.use_run_folders` branches are in
  `config/schema_models.py`, `orchestration/preparation.py`, `cli/dry_run.py`, and
  `cli/output.py`. Other matches are tests or current documentation. No required
  production workflow was found that depends on flat output.
- `PathsConfig` currently owns `screenshots_dir`, `generated_dir`, and
  `use_run_folders`; `ReportConfig` owns `output_dir`; loader/persistence/preset
  owners serialize the schema generically. Preflight currently contains all
  configured output under the workspace, so it is the owner that must distinguish
  an allowed external generated root from still-contained config paths.
- `WorkspacePaths.with_run_dir()` already derives `<run>/screenshots` and
  `<run>/generated` and preserves shared cache paths. Preparation already reserves a
  folder, writes `run_info.toml` before heavy runtime work, captures the reservation,
  and writes run-local plus shared probe snapshots. The flat branch can be deleted
  without changing reservation naming/collision policy.
- Render output already consumes `WorkspacePaths.screenshots_dir`. Report generation
  currently chooses configured/fallback placement, while its payload owner already
  computes image references relative to an explicit report directory. The existing
  browser smoke test opens `file://` but embeds its image, so it does not yet prove
  the required sibling `screenshots/` load.
- `run_result_record.py` currently serializes report/screenshot paths relative to the
  workspace and history resolves them from the workspace before checking the
  generated root. Its existing parser and history tests already cover traversal,
  absolute/drive paths, symlinked runs/records/reports, deterministic output, malformed
  isolation, and exact-name opening; the ownership seam can change directly to
  run-relative V1 paths.
- Shared analysis and alignment caches already use explicit stable cache paths;
  shared probe cache is derived from the shared analysis cache root. They need to
  remain anchored to the immutable generated-data root after the current-run
  directories switch into a run folder.
- CLI output currently prints configured screenshot/generated base paths and the
  run-folder mode; `--diagnose-paths` currently maps `output` to screenshots and
  `cache` to generated. Successful run JSON already carries concrete
  `screenshots_dir` and `report_path` without needing key changes.
- The wizard already preserves raw authored TOML, strips non-persistable secrets,
  validates through config/preflight owners, and atomically writes only after
  confirmation. It currently prompts only for input/reference/frame-selection and
  has no generated-data location UX.
- `docker-compose.yml` has separate `/workspace/screenshots` and
  `/workspace/generated` mounts for runtime services. The host-open helper and
  onboarding tests/docs explicitly allow both roots; these are the complete default
  Compose translation surfaces found by the scan.
- The installed Windows shim state `config.toml` is preserved by uninstall/reinstall,
  and code-only updater ownership is limited to the bundle. The installer fallback
  config still writes `screenshots_dir`; current portable tests already exercise shim
  config injection, update/rollback, reinstall, uninstall, and user-file
  preservation, providing seams for explicit external-data sentinel proof.
- Stale authored examples were found in `config/benchmark.config.toml`,
  `docs/current-architecture.md`, `docs/current-cli-contract.md`, `README.md`,
  `docs/getting-started/docker.md`, `docs/docker-environments.md`,
  `docs/windows-portable.md`, and related setup/troubleshooting prose. Planning files
  may continue naming removed fields only to state the clean-cut decision.

## Part 1: Core Persistence And Report Contract

Complete the general Python/config/filesystem contract and leave it directly usable
through authored config and existing CLI commands. Part 1 must end with one report
location, one result-record meaning, and no flat-output runtime branch.

### Part 1 Sequencing Note

Packages 1.1–1.3 are green internal implementation checkpoints, not independently
released contracts. Package 1.1 introduces generated-root ownership,
`WorkspacePaths.generated_root`, dependency-light descendant containment, and exact
authored `generated_dir` persistence while leaving the three old schema fields
unchanged only in the in-progress worktree. Package 1.2 removes runtime consumption
of `paths.use_run_folders` and `paths.screenshots_dir`; Package 1.3 removes runtime
consumption of `report.output_dir`. Package 1.4 then deletes all three fields
atomically from schema, preflight, generated persistence/examples, tests, and current
docs. This temporary physical ordering is neither released compatibility behavior nor
authorization for a parser, alias, deprecation, fallback, or dual contract.

### Package 1.1 — Generated-Root Configuration And Path Authority

**Outcome:** Establish the future sole generated-output root by resolving
`paths.generated_dir` once, adding required `WorkspacePaths.generated_root`, exposing
dependency-light managed-descendant containment, and preserving the exact authored
generated-dir value. Keep the three old schema fields physically unchanged at this
internal checkpoint so their still-present downstream consumers and tests remain
green until Packages 1.2–1.4 remove them in dependency order.

**Owner seam and allowed write boundary:** Config schema/loading/persistence/presets
and preflight retain sole ownership of interpreting `paths.generated_dir`, accepted
forms, environment expansion, workspace-relative resolution, and typed selection
errors. The dependency-light utils layer owns `WorkspacePaths` plus one focused
managed-descendant containment primitive that services/history can consume without
importing orchestration; exact helper/module names are left to implementation. This
package may update those owners and their focused config/preflight/utils/persistence
tests. It must add `WorkspacePaths.generated_root` without deleting or changing the
three old schema fields or their current normalization at this checkpoint. Do not
modify run orchestration, report/history behavior, Docker, or Windows portable
scripts.

**Public contracts and invariants:**

- Preserve `report.output_dir`, `paths.use_run_folders`, and
  `paths.screenshots_dir` unchanged only for this in-progress green checkpoint. Do
  not add aliases, new parsing, deprecation, fallback, or documentation that treats
  their temporary physical presence as supported future behavior; Package 1.4 owns
  their atomic clean-cut deletion after consumers are gone.
- Keep the authored `paths.generated_dir` string unchanged through
  `run --write-config`, preset save/apply, and config serialization. Runtime expansion
  and resolution must not leak an incidental absolute path back into persisted TOML.
- Resolve a relative value from the selected workspace root. Accept an
  environment-expanded absolute normal directory, another mounted drive, or a root
  reached through an intentional symlink/junction. Keep config/config-dir containment
  and unrestricted read-only media-input rules unchanged.
- Keep all generated-root interpretation and acceptance policy in config/preflight.
  The dependency-light containment primitive receives already-resolved owner and
  descendant paths, enforces that managed descendants remain beneath their resolved
  owner, and contains no TOML, environment, CLI, history, or orchestration policy.
  Services and history must import that utility boundary rather than importing
  orchestration or reimplementing containment.
- Reject a filesystem root, Windows drive root, or bare UNC share root as the selected
  generated-data directory. Path resolution and config-only commands remain free of
  output side effects. A real run may later create a missing ordinary leaf and parent
  directories through the run-reservation owner; an unavailable drive/share/mount,
  permission failure, or read-only destination must raise a typed actionable error
  naming the selected location and suggesting reconnect, permissions repair, or
  another location.
- Never fall back to workspace `generated`, the portable bundle, or another root after
  an explicit generated root fails.
- Make required `WorkspacePaths.generated_root` the stable resolved root, distinct
  from the current run folder and its run-local generated directory. Use the focused
  dependency-light containment primitive for later run, cache, report, and history
  owners; do not create a general storage abstraction or move generated-root
  interpretation out of config/preflight.

**Explicit non-goals:** No deletion or reinterpretation of the three old schema
fields in this package; no run-folder lifecycle, report/result/history rewrite,
wizard prompt, platform script, compatibility handling, dependency, or generic
filesystem repository.

**Acceptance criteria:**

- `WorkspacePaths.generated_root` is required, absolute, stable across run-folder
  transitions, and distinct from the current run-local generated directory.
- Default and environment-expanded relative values resolve beneath the workspace;
  absolute same-drive and mounted-drive directories resolve to themselves; a root
  symlink/junction resolves to its intentional final target.
- Root/drive/share roots and invalid descendant paths fail through the typed CLI error
  adapter. Resolution performs no output creation; later failed writes to unavailable
  or read-only explicit roots create nothing elsewhere.
- Generated config and presets preserve the user's relative/absolute authored
  `generated_dir` value, remain deterministic and secret-safe, and do not gain a new
  persistence branch. The three old schema fields and existing consumer tests remain
  unchanged and green solely as internal sequencing state.
- Existing external-media behavior and the exact installed portable config-file
  exception remain unchanged.

**Focused verification:** Run focused config schema/loader/preset, preflight,
dependency-light utils, write-config, and preset command tests. Add public-seam cases
for relative, absolute, env-expanded, intentional root symlink, root/drive/share
rejection, side-effect-free resolution, authored-value persistence, and the
already-resolved managed-descendant containment primitive. Prove services/history can
consume that primitive without an orchestration import. Also prove existing schema,
generated-config, preset, preflight, and downstream tests remain green with the three
old fields unchanged. Use `tmp_path`, isolated environments, and platform-aware
Windows cases; do not make tests depend on unisolated generated state.

**Integration checkpoint:** The controller confirms every `WorkspacePaths` instance
receives one stable `generated_root`, config/preset/CLI persistence round-trips the
authored `generated_dir`, the dependency-light containment seam is import-safe, and
the existing suite remains green with all three old schema fields unchanged. This is
an internal dependency checkpoint, not a releasable public contract. Run `pyright`,
`ruff`, and `lint-imports` if the path carrier or imports changed.

**Stop conditions:** Stop if required `WorkspacePaths.generated_root` cannot be added
without prematurely changing/removing an old-field consumer, if the temporary
physical schema state would require new compatibility/fallback behavior, or for a new
dependency, unclear generated-root ownership, weakened descendant containment,
unsafe typed failure, or any evidence that an explicit external root must fall back.

**Likely role eligibility at dispatch:** `worker_luna` eligible. Escalate only if the
settled contract unexpectedly requires material cross-layer type/ownership redesign;
do not let a worker invent that redesign.

### Package 1.2 — Unconditional Run Layout And Shared Cache Placement

**Outcome:** Remove runtime consumption of `paths.use_run_folders` and
`paths.screenshots_dir`, delete flat-output execution, and make every real run reserve
one canonical run folder whose derived screenshot/run-local paths coexist with shared
caches under `WorkspacePaths.generated_root`. Physical schema deletion remains
deferred to Package 1.4.

**Owner seam and allowed write boundary:** Preparation and run-folder lifecycle;
`WorkspacePaths` consumption; render destination routing; slow.pics shortcut directory
selection; shared analysis/alignment/probe cache path consumption; and adjacent
orchestration/service tests and fixture helpers. Package 1.1 owns path interpretation;
this package must consume, not duplicate, it.

**Public contracts and invariants:**

- Every normal or cache-only run that proceeds far enough reserves a fresh real
  immediate-child directory beneath the resolved generated root. Preserve the current
  title-first name, 64-character cap, deterministic collision suffixes, and atomic
  reservation.
- Preserve cache-only prevalidation ordering: a missing/invalid required cache fails
  before metadata prefetch and run-folder reservation. A run that proceeds never
  reuses an existing run folder to satisfy a cache hit.
- Write root-level `run_info.toml` immediately after reservation and before probing or
  rendering. Preserve its current atomic write and best-effort empty-reservation
  cleanup behavior.
- Derive the current run's screenshots as `<run>/screenshots/` and run-local generated
  state as `<run>/generated/`; no caller reconstructs or configures those paths.
- Keep shared analysis cache at `<root>/cache/analysis`, shared alignment reuse at
  `<root>/cache/alignment`, and shared probe cache at `<root>/clip_probe.toml` after
  the workspace switches into a run folder. Keep run-local probe snapshots and manual
  overrides/VSPreview state under `<run>/generated/`.
- A configured generated root may itself resolve through a link/junction, but a run
  directory or managed descendant must not resolve outside it. Validate before use and
  fail rather than redirecting output.
- Because a run folder is now unconditional, a successful slow.pics shortcut belongs
  to that run folder. Preserve upload-plan membership and report-safe
  delete-after-upload semantics; do not retain the old no-run-folder common-parent
  policy.

**Explicit non-goals:** No report placement/result/history semantics yet, no naming
change, no cache schema/identity change, no cleanup/retention feature, no new phase,
and no platform-specific UI or mount work.

**Acceptance criteria:**

- Default, custom-relative, and external-root runs all create the same internal run
  layout and never write run state beside external media. A first real run may create
  its missing ordinary generated-root leaf/parents during reservation, while
  unavailable drive/share/mount and read-only failures stay typed and never fall back.
- Screenshot rendering, slow.pics upload inputs/cleanup, manual overrides, VSPreview
  artifacts, and shortcut output use the derived current-run paths.
- Shared caches remain siblings of run folders and survive repeated runs; the cache
  schemas, keys, `--no-cache`, and `--from-cache-only` meanings do not change.
- Symlinked run-directory candidates or any escaped screenshot, run-local generated,
  cache, run-info, or run-result target are rejected before managed use.
- Tests formerly setting `use_run_folders = false` for convenience construct an
  isolated canonical run workspace instead; no test-only production branch replaces
  flat mode.

**Focused verification:** Run focused run-folder, preparation/cache, cache-mode,
render-output, probe-cache, alignment-cache, slow.pics shortcut/cleanup, and failure
cleanup tests. Include fresh-run-on-hit, prevalidation-before-reservation,
external-media/external-output separation, shared-versus-run-local cache placement,
creation of a missing ordinary generated-root leaf and parents during real run
reservation, typed unavailable/read-only reservation failure with no fallback,
collision, atomic `run_info.toml`, and link-escape cases.

**Integration checkpoint:** The controller performs a default-root and temporary
external-root preparation/render smoke and inspects the resulting layout before
Package 1.3. Confirm the root contains only shared cache/probe state plus real run
directories, and each run carries derived screenshots/generated state.

**Stop conditions:** Stop if any production workflow requires flat output, cache-only
semantics would need to reserve or reuse folders differently, a cache owner cannot use
the stable generated root without an import-layer violation, or containment would
need to be weakened.

**Likely role eligibility at dispatch:** `worker_luna` eligible as a bounded runtime
path-consumption package. Escalate only for unexpected material orchestration redesign.

### Package 1.3 — Canonical Report, Run-Relative V1 Record, And History

**Outcome:** Remove runtime consumption of `report.output_dir`, create exactly one
canonical run-root report, record its artifacts relative to the run folder in the
existing V1 schema, and make history validate and open that portable run artifact.
Physical `ReportConfig.output_dir` schema deletion remains deferred to Package 1.4.

**Owner seam and allowed write boundary:** Report generation/payload owners;
post-render report routing; run-result record and lifecycle owners; history service and
CLI routing; browser/report/history tests. Package 1.2 supplies canonical run paths;
this package must not reinterpret config or output policy.

**Public contracts and invariants:**

- For every report-enabled run, pass the explicit canonical
  `<run-folder>/report.html` path to the report owner. Remove configured/fallback
  report-path selection. The report owner continues to own payload/HTML and atomic
  write mechanics, not orchestration policy.
- For non-embedded reports, payload image sources must be run-portable POSIX-relative
  paths such as `screenshots/<image>.png`. Embedded-image behavior remains supported.
- Change the one supported V1 record directly: `report_path` is normally
  `report.html` and `screenshot_dir` is normally `screenshots`, both relative to the
  record's own run folder. Keep version `1`; add no legacy reader, version branch,
  migration, or fallback resolution.
- Record paths must be non-empty POSIX relative paths with no `.`, `..`, drive, UNC,
  or absolute form. Serialization remains deterministic, atomic, null-free, and
  secret-safe for both completed and failed outcomes.
- History discovers only real immediate-child run directories, resolves records and
  artifacts from each owning run folder, and rejects escaped symlink/junction targets.
  Preserve exact-name matching, ordering, statuses, warning isolation, streams, and
  the exact history JSON key allowlist.
- A contained canonical `report.html` remains available even when referenced
  screenshots are missing. A missing, malformed, redirected, or escaped report keeps
  the existing typed history failure behavior and never reaches browser-open.
- Human/auto-open/report-confirmed slow.pics flows and successful JSON all consume the
  same canonical absolute runtime report path. Do not change slow.pics confirmation,
  upload, cleanup, or browser precedence beyond replacing the path source.

**Explicit non-goals:** No old-record recognition, schema V2, report archive/copy,
viewer redesign, annotation persistence, screenshot retention, or slow.pics semantic
change.

**Acceptance criteria:**

- A default or external-root report-enabled run has one `report.html` at the run root,
  sibling `screenshots/`, root-level `run_info.toml`/`run_result.toml`, and no report
  under `screenshots/` or a configured report directory.
- Moving a complete run folder beneath another generated root leaves its V1 record
  valid and `history list/open` resolves the contained report without source media.
- Completed and failed record writers emit only valid run-relative artifact paths;
  parser tests reject traversal, absolute, drive, UNC, and empty/dot forms, while
  record/history owner-boundary tests reject symlink/junction escapes.
- Successful human output, JSON values, report auto-open, report-confirmed slow.pics,
  and history identify the same report without changing JSON key sets or stream
  placement.
- A real supported Chrome/Chromium process opens the run-root report over `file://`
  with `embed_images = false` and proves that relative sibling screenshots load, not
  merely that HTML initializes or contains an `img` tag.

**Focused verification:** Run focused report entry/payload/viewer tests,
`tests/browser/test_report_browser_smoke.py`, run-result service/lifecycle tests, and
CLI history/report-open/report-confirmation tests. Exercise both completed and failed
records, moved run folders, malformed isolation, missing screenshots, escaped
symlinks, atomic failure, and separate stdout/stderr/JSON parsing through public seams.

**Integration checkpoint:** The controller creates a minimal run-layout fixture under
both a workspace-relative and temporary external root, opens `report.html` by
`file://` in the real-browser smoke, moves the complete run folder, and proves history
still lists/opens it. Package 1.4 cannot declare the public output contract until this
passes.

**Stop conditions:** Stop if relative screenshot references cannot load from a
run-root report, if V1 cannot change cleanly without compatibility, if safe history
resolution requires workspace-relative records or weakened containment, or if report
placement needs a second owner/path.

**Likely role eligibility at dispatch:** `worker_luna` eligible because the artifact
contract and proof are fully settled. Escalate only for unexpected material
cross-boundary diagnosis or report-hotspot design judgment.

### Package 1.4 — CLI Contract, Core Authorities, And Clean-Cutover Audit

**Outcome:** Perform the atomic clean cut by deleting `report.output_dir`,
`paths.use_run_folders`, and `paths.screenshots_dir` from schema, preflight, generated
config/presets, examples, tests, and current docs after Packages 1.2–1.3 remove their
consumers. Project the completed filesystem contract through CLI human/JSON surfaces
and close Part 1 as one coherent directly usable product checkpoint.

**Owner seam and allowed write boundary:** Config schema, config persistence/presets,
preflight's obsolete field handling, CLI output/run diagnostics/dry-run projection,
all remaining fixtures/tests/examples that physically carry the three old fields,
`config/benchmark.config.toml`, `docs/current-cli-contract.md`,
`docs/current-architecture.md`, and directly related core report/first-comparison
guidance. Packages 1.1–1.3 must already have removed production consumers; this
package owns the single coordinated deletion and current-authority synchronization.
Do not edit portable/Docker adoption surfaces reserved for Part 2.

**Public contracts and invariants:**

- Delete all three old fields in one coordinated change. Owned nested config tables
  reject them through ordinary unknown-field validation, with no custom migration
  error, alias, deprecation, ignored-value path, compatibility reader, or retained
  generated/default value.
- Keep `run --diagnose-paths` keys exactly `cache`, `config`, `input`, `output`, and
  `root`; set `output` to the resolved generated-data root and `cache` to
  `<generated-data-root>/cache`.
- Remove the at-a-glance configured screenshot-root and run-folder-mode rows. Show the
  resolved generated-data root. Completed human output still shows the concrete
  run-scoped screenshots and report paths.
- Keep successful `run --json` and history JSON key sets, compact single-document
  stdout, error shapes, stream placement, quiet behavior, and exit codes unchanged;
  only artifact path values reflect the new root/layout.
- Dry run keeps its current JSON key shape. Its existing `run_folders` fact is always
  true and run-folder name remains runtime-unknown; it must not imply a configurable
  flat mode or perform output side effects.
- `run --write-config`, preset save/apply, and authored examples contain no removed
  keys and preserve authored `paths.generated_dir` values.
- Update current architecture and CLI authority in the same package to describe the
  implemented Part 1 state, including owner/path flow, V1 run-relative records,
  canonical report, history containment, cache placement, and unchanged JSON shapes.

**Explicit non-goals:** No new CLI flag/subcommand/JSON key, wizard UX, Windows
portable script, Docker mount, release note, or broad documentation rewrite.

**Acceptance criteria:**

- Schema defaults, generated config, presets, examples, test fixtures, and current
  product docs contain no supported `report.output_dir`, `paths.use_run_folders`, or
  `paths.screenshots_dir`; direct attempts to load them receive ordinary owned-table
  unknown-field rejection.
- Focused CLI tests parse and compare exact JSON key allowlists, assert separate
  stdout/stderr, and verify semantic human path rows for default and external roots.
- `--diagnose-paths`, normal run output, auto-open, report confirmation, and both
  history commands agree on the resolved root and canonical report.
- Production code, current config/examples, and current product docs contain no live
  behavior for removed fields. Frozen planning/specification prose may name them only
  to document deletion.
- `docs/current-architecture.md` and `docs/current-cli-contract.md` match observed
  Part 1 behavior and `tests/test_cli_contract_docs.py` protects the updated contract.

**Focused verification:** First run a stale-consumer search and stop if production
still reads any of the three fields. Then run focused config loader/schema/generated
persistence/preset/write-config tests, including ordinary unknown-field rejection;
CLI output/run/dry-run/JSON/report-open/history tests; all fixtures converted from the
old fields; and CLI contract-doc tests. Search production, generated examples, tests,
and current docs for residual live behavior, excluding frozen planning prose that
states deletion. Use semantic assertions rather than whole-output snapshots. Run
generated API drift and strict documentation build checks after authority edits.

**Integration checkpoint:** This is the atomic clean-cut and Part 1 gate. Before
deleting schema fields, the controller confirms Packages 1.2–1.3 removed every
runtime consumer; after deletion, no intermediate old/new schema combination may be
handed off or released. The controller must:

1. inspect the integrated diff and threshold dispositions;
2. run the focused cross-owner tests from Packages 1.1–1.4;
3. run the real-browser `file://` non-embedded screenshot proof;
4. run the runbook's Full Verification commands;
5. run `lint-imports` as part of Full Verification and inspect `importlinter.ini` if
   any owner/import seam changed; and
6. perform isolated default-relative and external-root CLI smoke cases covering
   diagnose, run artifacts, result record, history list/open, and an unavailable
   explicit root with no fallback.

Part 1 is complete only when there is one runtime report path, one V1 record meaning,
unconditional run folders, no supported removed fields, and directly usable authored
config/CLI behavior. Do not begin Part 2 on a temporary dual contract.

**Stop conditions:** Stop if any runtime consumer of an old field remains, if deleting
the three fields cannot be one green coordinated change, or if the internal sequencing
state would need to become released compatibility behavior. Also stop for any
JSON/stream/exit-code expansion, compatibility or flat-output mode, authority/source
disagreement, unjustified import-contract change, or inability to run the Part 1
checkpoint concretely.

**Likely role eligibility at dispatch:** `worker_luna` eligible for the bounded
projection and authority synchronization. The controller, not the worker, owns the
Part 1 integration gate.

## Part 2: Guided Adoption And Runtime Proof

Consume the finished Part 1 contract without redesign. Add the user-facing wizard,
Windows portable preservation boundaries, one Docker mount, setup documentation, and
platform-honest end-to-end proof.

### Package 2.1 — Wizard Generated-Data Location UX

**Outcome:** Let interactive users choose and persist the sole generated-data location
in ordinary product language, including a normal external Windows directory, through
the existing secret-safe atomic wizard owner.

**Owner seam and allowed write boundary:** Wizard command/policy and prompt adapters,
wizard-focused tests, and the wizard section of the current CLI contract. Consume
Package 1.1 validation/persistence; do not add a second path parser or portable-only
Python branch.

**Public contracts and invariants:**

- Prompt for `Generated data location` (or equally clear reports/screenshots/cache
  wording) after input location and before reference/frame-selection choices. Explain
  that the directory contains durable comparison folders and reusable caches.
- Default to the authored current value or `generated` on first use. Accept relative,
  environment-expanded, and normal absolute values according to Package 1.1 and
  persist exactly the user's authored string after confirmation.
- Include the generated-data selection in semantic review when new/changed. A true
  no-op remains byte-for-byte and prompt cancellation/error behavior, TTY rules,
  secret stripping, raw unknown-root preservation, and one atomic write remain
  unchanged.
- Structurally validate the complete candidate through the shared config/preflight
  policy before write, including filesystem/drive/bare-share roots and applicable
  containment rules. Saving config must not probe, create, or require the selected
  generated path to exist or be writable. Do not silently substitute a
  bundle/workspace default for an invalid selection.

**Explicit non-goals:** No directory picker dependency, NAS-specific UI, retention or
backup prompt, extra root, media probing, automatic migration, or portable-only
config serializer.

**Acceptance criteria:**

- First use and edits show clear location/capacity language and persist relative and
  absolute values through the ordinary config owner.
- An installed portable fallback config can be wizard-edited to an external normal
  directory without manual TOML editing; later run/history commands read the same
  authored value.
- Filesystem roots, Windows drive roots, bare UNC share roots, and structural
  containment failures preserve existing config bytes and use typed errors. A missing
  ordinary relative or absolute generated path may be persisted without being
  created; availability and writability are runtime-reservation concerns owned and
  proved by Package 1.2.
- Cancellation, EOF, and atomic config-write failure preserve existing config bytes.
- Environment-only values remain neither disclosed nor persisted; generated secrets
  remain stripped exactly as before.

**Focused verification:** Run wizard command/policy tests for first-use, existing
config, no-op, cancellation at every new prompt boundary, semantic review, raw TOML
preservation, relative/absolute authored path persistence, persistence of a missing
ordinary path without filesystem creation, structural root/drive/bare-share and
containment rejection, exact portable config exception, secret stripping, and atomic
failure. Assert no availability/writability probe occurs and use public output
fragments and streams rather than whole help/review snapshots. Do not duplicate the
Package 1.2 runtime unavailable/read-only proof here.

**Integration checkpoint:** The controller invokes the real wizard in an isolated
TTY-capable local workspace, chooses an ordinary external path that does not yet
exist, confirms the exact stored text, and proves the wizard created neither that path
nor any output beneath it before Package 2.2.

**Stop conditions:** Stop if portable fallback config cannot retain the external
value independently of the bundle, if wizard validation needs a second path policy,
if a new dependency is required, or if cancellation/no-op atomicity cannot be
preserved.

**Likely role eligibility at dispatch:** `worker_luna` eligible; the UX wording,
prompt placement, persistence contract, and proof are bounded here.

### Package 2.2 — Windows Portable Defaults And External-Data Preservation

**Outcome:** Make installed portable defaults/config routing consume the sole
generated root and prove that update, rollback, reinstall, and uninstall do not own a
user-selected external generated-data directory.

**Owner seam and allowed write boundary:** `tools/windows_portable/**`, the existing
portable shim/install/update/uninstall tests and Windows workflows when needed, and
Windows portable user documentation. Do not modify core Python path semantics settled
in Part 1.

**Public contracts and invariants:**

- Portable default config includes `paths.generated_dir = "generated"` and omits the
  removed path fields. A top-level bundle `screenshots/` directory is not a runtime
  output root.
- Preserve the installed LocalAppData state `config.toml` across reinstall/uninstall
  under the existing user-file policy. When that fallback config is selected, wizard,
  run, preset, and history injection must address the same exact file.
- A user-selected external generated root is user data outside the portable bundle
  and shim state. Code-only update, rollback, full bundle replacement/reinstall, and
  uninstall must not create, read as managed install state, move, rewrite, back up,
  or delete it.
- Preserve existing signed-update trust, bundle inventory, launcher, and release
  asset contracts. Source clips moved with a bundle may change cache identity; docs
  state this honestly without weakening validation.

**Explicit non-goals:** No data migration/backup, installer-managed external folder,
new updater manifest field, new signing behavior, Windows shell shortcut to a report,
or network-share credentials.

**Acceptance criteria:**

- A compatible Windows host proves the installed shim/wizard persists a normal
  external directory in the fallback config and that run/diagnose/history resolve it.
- Same-drive and another mounted-drive external roots produce the canonical layout;
  a local junction to a dedicated directory is accepted; drive roots and bare UNC
  share roots are rejected.
- Tests place sentinel run/report/screenshot/cache data in the configured external
  root and prove byte-for-byte/path preservation across code-only update, rollback,
  reinstall/bundle replacement, and uninstall. Managed bundle/shim files still change
  or disappear as their existing contracts require.
- Portable default/config/shim/docs tests contain no supported removed fields and no
  output fallback to the bundle.

**Focused verification:** Run focused Windows portable build, shim-config,
install/uninstall, update/apply/rollback, workflow, and docs tests with explicit
subprocess timeouts. The external sentinel must be outside all install, bundle, state,
backup, and temporary directories so the proof is meaningful.

**Integration checkpoint:** On a compatible Windows host, run the runbook's canonical
public-key validation, portable build, and bundled `doctor --json`; run the
code-only-update build/sign path when updater or release-package logic changed. Also
run the external-root/junction and update/rollback/reinstall/uninstall sentinel E2E.
If signing credentials or a Windows runner are unavailable, record each unavailable
path as documented-only and require maintainer/Windows-runner confirmation; source
inspection is not verification.

**Stop conditions:** Stop if the external root must live under the replaceable bundle,
if the shim cannot consistently select the persisted fallback config, if preservation
requires updater/schema redesign beyond this plan, if a real Windows proof cannot be
specified, or if release signing/trust behavior would change.

**Likely role eligibility at dispatch:** `worker_luna` eligible within the settled
portable script/test/doc seam. Escalate only for unexpected material updater or
release-proof diagnosis; do not redesign release policy.

### Package 2.3 — Docker Single-Mount Adoption, User Docs, And Final Integration

**Outcome:** Persist all Docker-created run artifacts and shared caches through the
generated-data mount only, update host-opening/setup guidance, and close the full
two-part workstream with platform-honest verification and review.

**Owner seam and allowed write boundary:** Default Compose services, Docker host-open
helper and canonical integration gate, Docker/workflow contract tests, README and
Docker/onboarding/troubleshooting docs, plus final cross-surface authority cleanup.
Optional GPU/GUI profile semantics remain unchanged unless their inherited mount
reference requires a direct correction.

**Public contracts and invariants:**

- Remove the standalone `./screenshots:/workspace/screenshots` mount. Mount
  `./generated:/workspace/generated` as the only generated-data persistence path for
  runtime and wizard setup where the selected location must be validated/writable.
  Keep config and media permissions/read-only posture unchanged.
- Container removal must leave the run folder, report, screenshots, run records,
  run-local generated state, and shared analysis/alignment/probe caches on the host
  generated-data mount.
- Restrict the host-open helper's local path translation to
  `/workspace/generated -> ./generated`; remove screenshots-root acceptance and retain
  canonical-path/symlink-escape rejection plus explicit slow.pics URL handling.
- Update quick starts to create/mount `config`, `comparison_videos`, and `generated`
  only. Document that a custom container path is durable only when explicitly mapped
  to a host-owned directory.
- Keep default Docker headless software-Vulkan behavior and optional NVIDIA/X11
  capability claims unchanged. No GUI/GPU path is inferred verified by this work.

**Explicit non-goals:** No Docker volume manager, arbitrary host path translator,
desktop browser forwarding, GPU/GUI expansion, config-write expansion for run
services, or change to native Windows runtime behavior.

**Acceptance criteria:**

- Compose and onboarding contract tests expose one generated-output mount and no
  `/workspace/screenshots` output mapping.
- The host helper opens/translates a canonical report under
  `/workspace/generated/<run>/report.html`, rejects the removed screenshots root,
  rejects traversal/symlink escapes and protected workspace roots, and keeps slow.pics
  URL validation unchanged.
- A default Docker run using only the generated-data host mount leaves report,
  screenshots, `run_info.toml`, `run_result.toml`, run-local state, and shared cache
  sentinels readable after container removal.
- README, Docker guides, Windows guide, first-comparison/report guidance, current
  authorities, and troubleshooting describe one generated-data location and contain
  no live removed-field or standalone-screenshot-mount behavior.

**Focused verification:** Run Docker host-helper/onboarding/workflow contract tests,
strict docs validation, and the canonical `bash tools/verify_docker_integration.sh`
gate. Add an integration assertion that verifies durable host files after container
removal rather than only inspecting Compose YAML.

**Integration checkpoint:** This is the Part 2 and final gate. The controller must:

1. rerun the default/external-root CLI, moved-run history, no-fallback, and real-browser
   `file://` relative-screenshot proof from Part 1;
2. run the runbook's Full Verification commands;
3. run `bash tools/verify_docker_integration.sh` on a Docker-capable host;
4. collect Package 2.2 Windows portable/release-path and external-data preservation
   results from a compatible Windows host, explicitly separating executed proof from
   documented-only proof;
5. run generated API drift and strict Zensical documentation validation;
6. inspect `git diff --check`, the complete diff, stale-field searches, authority
   synchronization, import-layer results, and all architecture dispositions; and
7. dispatch one fresh independent configured `reviewer` with the frozen spec, full
   diff, verification record, platform evidence, owner dispositions, and risk packet
   but without the implementation transcript. Resolve material findings and rerun
   affected focused/full/platform proof before closeout.

**Stop conditions:** Stop if one generated mount cannot retain every required artifact,
if Docker proof needs a second output root, if host-helper safety would be weakened,
if Windows or Docker paths are claimed verified without execution, if final authority
docs conflict with observed behavior, or if independent review finds an unresolved
product/containment/data-loss issue.

**Likely role eligibility at dispatch:** `worker_luna` eligible for the bounded
Docker/helper/doc package. The controller owns final integration and the independent
`reviewer` gate; neither is delegated as an implementation package.

## Verification Record And Platform Distinctions

```text
VERIFICATION_RECORD
RISK: high
PRIMARY_MODE: contract + integration + manual
RATIONALE: Public config, filesystem containment, run records/history, report output,
Docker mounts, Windows portable preservation, and report hotspots all change.
TEST_DECISION: update existing contract/integration coverage and add missing
external-root, run-relative record, no-fallback, platform-preservation, and real-browser
proof through public seams.
COMMANDS_AND_EXPECTED_OUTCOMES:
- Package-focused pytest commands listed above pass before each package handoff.
- Runbook Full Verification passes at the Part 1 checkpoint and final integration.
- `bash tools/verify_docker_integration.sh` passes after the Compose mount change.
- The runbook Windows portable/release-path commands and external-data sentinel E2E
  pass on a compatible Windows host.
- `uv run --no-sync python scripts/generate_api_docs.py --check` reports no drift.
- `uv run --no-sync zensical build --clean --strict` succeeds.
- `git diff --check` and final stale-contract searches return clean.
UNAVAILABLE_OR_DOCUMENTED_ONLY_PROOF:
- Windows drive/junction/portable/update/signing proof is documented-only on non-Windows
  hosts and remains a closeout gate for a compatible runner/maintainer.
- Docker integration is documented-only when Docker is unavailable and remains a
  closeout gate for the Docker workflow/compatible host.
- Optional Linux NVIDIA GPU and X11 GUI profiles are unchanged and remain separately
  documented-only unless their dedicated host-dependent gates are actually run.
```

Canonical Full Verification (do not omit or substitute commands):

```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
```

Canonical documentation validation after authored docs change:

```bash
uv sync --only-group docs --locked
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
uv sync --group dev --group docs --locked
```

Canonical Docker gate:

```bash
bash tools/verify_docker_integration.sh
```

Canonical Windows portable/release-path baseline on Windows:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/validate_update_public_key.ps1 -PublicKeyPath tools/windows_portable/update_public_key.xml
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir dist/frame-compare-portable-win-x64 -CacheDir .portable_cache
dist/frame-compare-portable-win-x64/frame-compare.ps1 doctor --json
```

When updater or release-package logic changes, also run the runbook's update zip build
and signing commands and require valid signing evidence. Do not treat source inspection,
macOS PowerShell parsing, a skipped test, or a Docker YAML assertion as substitute
proof for the real platform boundary.

## Rollback

- Roll back package commits in reverse dependency order, keeping config/schema,
  runtime paths, report/record/history, CLI/docs, and platform surfaces internally
  consistent at every rollback checkpoint. Do not selectively restore one removed
  field or one old record/report meaning.
- Source rollback carries no data migration promise. Revert code and recreate local
  pre-release config, run folders, or caches manually only when explicitly desired;
  older builds are not required to read the changed config or V1 records.
- Never delete or mutate a user-selected external generated-data root as part of code,
  Docker, installer, updater, uninstall, test cleanup, or rollback. Tests may remove
  only their explicit isolated temporary roots.
- If Part 2 must be reverted while Part 1 remains, restore only the wizard/portable/
  Docker adoption changes to a Part 1-compatible state; do not reintroduce flat output,
  a second report path, or a screenshots mount that contradicts the core contract.
- A Docker rollback restores Compose, host-helper tests, and docs together. A Windows
  rollback restores managed scripts/config defaults only and leaves external user data
  untouched.

## Global Stop Conditions

Stop and return to the maintainer/planning authority rather than improvising if any
package discovers:

- a currently required production workflow that depends on flat output;
- an unavoidable need for old config or old result-record compatibility;
- a report-relative screenshot that cannot load from the canonical run-root
  `report.html` under `file://`;
- safe external-root support that requires weakening descendant containment or
  allowing filesystem/drive/share roots;
- an unavailable explicit root that would require fallback or split history;
- portable config that cannot retain an external root independently of the bundle, or
  update/reinstall/uninstall logic that must own that data;
- a two-part boundary that cannot end in the coherent Part 1 and Part 2 checkpoints
  above;
- an import/owner seam that conflicts with `importlinter.ini` or current architecture
  and cannot be resolved within the named owner;
- proof depth that cannot be stated or executed on the required platform; or
- a new dependency, database, server, archive index, migration, cleanup policy,
  screenshot-retention feature, or other scope expansion.

Close the workstream only after all accepted packages, both integration checkpoints,
required platform gates, final independent review, authority synchronization, and
diff inspection are complete. Then mark this plan historical in the same pass; the
approved specification remains product-history authority rather than an active plan.
