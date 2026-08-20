---
search:
  exclude: true
---

Status: Implemented historical specification; current behavior is documented in the present-state architecture and CLI contract
Scope: Persistent generated-data location, canonical run layout, and run-root local reports
Owner: Maintainer and implementing sessions

# Persistent Generated Data And Run-Root Report Specification

## Document Role

This document freezes the product and filesystem contract for a future two-part
implementation plan. It is a specification, not implementation authorization and
not an execution sequence. The later plan must preserve the decisions, invariants,
acceptance criteria, and stop conditions below.

The specification replaces the idea of a separately configured report archive with
one persistent generated-data root. That root owns run history, local reports,
screenshots, shared caches, and run-local generated state together.

## Goal

Make Frame Compare outputs durable, predictable, and easy to review regardless of
whether the application runs from a source checkout, Docker workspace, installed
Windows portable bundle, or a user-selected external storage location.

A user must be able to:

1. choose one generated-data location;
2. find each comparison in one clearly named run folder;
3. double-click `report.html` at the top of that run folder;
4. retain the run folder and shared caches independently of a replaceable portable
   application bundle; and
5. use the existing history commands against the same generated-data location.

## Product Decisions

### One Location Authority

`paths.generated_dir` is the sole configuration authority for persistent generated
data. It continues to default to `generated`, resolved relative to the workspace
root, and may also be configured as an environment-expanded absolute path outside
the workspace.

The setting owns all of the following:

- immediate-child run folders;
- run identity and outcome records;
- run screenshots and local HTML reports;
- run-local probe snapshots, alignment overrides, and VSPreview state;
- shared analysis metrics;
- shared alignment reuse state; and
- the shared clip-probe cache.

No second archive root, report root, or implicit portable-bundle fallback is added.

### Remove `report.output_dir`

`report.output_dir` is removed from the configuration schema, generated config,
presets, tests, documentation, and runtime path validation. No compatibility code or
bespoke error remains; an old local config is simply not a supported input.

### Canonical Run-Folder Report

Every report-enabled run writes exactly one canonical local report at:

```text
<resolved paths.generated_dir>/<run-folder>/report.html
```

The report is never placed under the run's `screenshots/` directory and is never
redirected by another report-path setting. CLI presentation, browser auto-open,
slow.pics report confirmation, successful JSON output, and `run_result.toml` all
refer to this canonical path.

The report uses relative references such as `screenshots/<image>.png` when
`report.embed_images = false`. Moving or copying the complete run folder therefore
preserves ordinary offline viewing. `report.embed_images = true` remains supported
and continues to produce a larger single-file report.

### Run Folders Are Unconditional

`paths.use_run_folders` is removed from the configuration schema and runtime. Every
run that proceeds far enough to reserve output uses a fresh run folder. There is no
flat-output, overwrite-latest, or non-archival execution mode.

`paths.screenshots_dir` is also removed from configuration because screenshots have
one derived location: `<run-folder>/screenshots/`. The runtime may continue carrying
the resolved current screenshot directory, but users do not configure it separately.

Removed `paths.use_run_folders` and `paths.screenshots_dir` values receive no
compatibility parser, bespoke error, or retained documentation. Old local configs
are not supported inputs.

## Canonical Filesystem Layout

The layout is identical for a default workspace-relative generated root and a
configured external generated root:

```text
<generated-data-root>/
├── cache/
│   ├── analysis/
│   │   └── <label>__<fingerprint>.compframes
│   └── alignment/
│       └── alignment_reuse.toml
├── clip_probe.toml
└── Movie Name (Year)/
    ├── report.html
    ├── run_info.toml
    ├── run_result.toml
    ├── screenshots/
    │   └── <rendered images>.png
    └── generated/
        ├── clip_probe.toml
        ├── manual_overrides.toml
        └── <other run-local generated state>
```

The exact current title-first naming policy, 64-character limit, deterministic
collision suffixes, and atomic folder reservation remain unchanged.

The shared `cache/` directory and shared `clip_probe.toml` are not history entries.
They remain siblings of run folders so cache reuse spans multiple comparisons.

## External Generated-Data Root Contract

### Accepted Forms

`paths.generated_dir` accepts:

- a relative path resolved against the selected workspace root;
- an absolute local path on the current drive;
- an absolute path on another mounted drive;
- an environment-expanded path; and
- any other directory path the host operating system exposes through normal
  filesystem APIs.

There is no NAS-specific implementation. The application does not manage network
credentials, mounting, reconnects, offline files, synchronization conflicts, or
remote availability.

The configured location must name a dedicated directory, not a filesystem root,
Windows drive root, or bare UNC share root. Ordinary directories on the same drive
require no additional setup.

### Resolution And Containment

The configured generated-data root is resolved once to its final filesystem target.
The root itself may be reached through a symbolic link or Windows junction; this
permits an intentional link to another mounted location.

After resolution, every Frame Compare-owned descendant must remain beneath that
resolved root. In particular:

- run folders must be real immediate-child directories, not symlinked aliases;
- `run_info.toml`, `run_result.toml`, and `report.html` must resolve to regular files
  inside their run folder;
- screenshot and run-local generated paths must remain inside their run folder;
- shared cache paths must remain inside the generated-data root; and
- history must reject a report or record whose symlink/junction target escapes the
  selected root.

This rule protects normal users from broken redirections and prevents a path that
looks archived from reading or writing an unrelated location. Windows `.lnk`
shortcut files are ordinary files and are not part of this filesystem rule.

### Availability And Failure

Frame Compare must never silently fall back to the workspace or portable bundle when
an explicitly configured generated-data root is missing, disconnected, read-only,
or otherwise unavailable.

Expected path and permission failures must use typed, actionable errors without raw
tracebacks. The error identifies the selected generated-data location and advises
the user to reconnect it, correct permissions, or choose another location.

For a first run, Frame Compare may create the selected leaf directory and missing
ordinary parent directories after configuration validation. It must not treat an
unavailable drive, share, or mount as an empty history.

Run-folder reservation, `run_info.toml`, `run_result.toml`, cache writes, and
`report.html` retain the repository's atomic-write and best-effort-cleanup policies.
No failure may redirect output to a second location.

## Runtime Path Ownership

`WorkspacePaths` remains the resolved runtime path carrier. It must distinguish:

- the workspace root used for config and relative-path interpretation;
- the resolved generated-data root used for shared state and run discovery;
- the current run folder;
- the current run's `screenshots/` directory;
- the current run's `generated/` directory; and
- shared analysis and alignment cache directories beneath the generated-data root.

Path construction belongs to preflight, `WorkspacePaths`, run-folder ownership, and
the relevant persistence services. Report generation receives an explicit canonical
run-root output path; it does not interpret configuration or choose archive policy.

CLI commands, renderers, cache owners, publishers, and report assets must consume
resolved paths rather than independently reconstructing them.

## Run-Result Record Contract

### Record Format

Run outcomes keep one supported V1 `run_result.toml` schema. Because there is no
released compatibility obligation, the current schema changes directly to
run-folder-relative paths without a version bump or dual reader.

For the single supported schema:

- `report_path` is run-folder-relative and normally equals `report.html`;
- `screenshot_dir` is run-folder-relative and normally equals `screenshots`;
- paths use POSIX separators in TOML;
- paths must be non-empty, relative, free of `.` and `..` segments, and free of
  drive, UNC, or absolute forms;
- resolving either path must remain within the record's own run folder; and
- serialization remains deterministic, atomic, secret-safe, and null-free.

Run-relative records make a complete run folder independently portable
between configured generated-data roots without embedding machine-specific absolute
paths.

Folders without a supported result record are not compatibility history. No record
or run directory is rewritten, migrated, or heuristically interpreted.

## History Contract

`history list`, `history list --json`, and `history open RUN_NAME` continue to use
the configured generated-data root and do not require source media to remain
available.

Existing command names, exact-name matching, ordering, status values, stdout/stderr
separation, and JSON key allowlist remain unchanged.

For result records:

- history discovers only real immediate-child run directories;
- report availability is evaluated against `<run-folder>/report.html` after strict
  record and containment validation;
- `history open` opens only the contained canonical report;
- missing screenshots do not make the HTML file nonexistent, but the report may
  render missing images honestly; and
- a missing, redirected, malformed, or escaped report produces the existing typed
  history failure behavior rather than a browser-open attempt.

Changing `paths.generated_dir` changes the single history root. Frame Compare does
not merge history from multiple roots.

## Cache Contract

Shared caches follow the configured generated-data root:

```text
<generated-data-root>/cache/analysis/
<generated-data-root>/cache/alignment/
<generated-data-root>/clip_probe.toml
```

Existing cache schemas, deterministic identities, cache-only semantics, corruption
handling, and `--no-cache` scope remain unchanged.

Persisting cache files does not guarantee a hit after source media is moved,
renamed, or modified. Source paths, fingerprints, selection domains, effective FPS,
analysis policy, active rectangles, and alignment settings continue to determine
cache compatibility.

Changing the generated-data root does not search, merge, copy, or migrate caches
from the previous root.

## Configuration And CLI Contract

### Configuration

- `paths.generated_dir` remains a string and the only generated-data location field.
- Relative values remain portable and resolve from `--root`.
- Absolute and environment-expanded external values become supported.
- `report.output_dir`, `paths.use_run_folders`, and `paths.screenshots_dir` are
  removed outright.
- `report.enable`, `report.embed_images`, `report.auto_open`, viewer defaults, and
  filmstrip settings remain unchanged.
- Secret-safe generated-config and preset persistence remain unchanged.

`run --write-config`, preset save/apply, and wizard output preserve the user's
authored relative or absolute generated-directory value rather than replacing it
with an incidental runtime-resolved path.

### CLI

No new run flag or history subcommand is required by this specification.

The following existing surfaces must reflect the resolved external location without
changing their JSON shapes or stream contracts:

- at-a-glance workspace paths;
- `run --diagnose-paths`;
- successful human artifact summaries;
- successful `run --json` path values;
- report auto-open;
- report-confirmed slow.pics upload; and
- `history list` and `history open`.

`run --diagnose-paths` keeps its existing keys. `output` becomes the resolved
generated-data root, and `cache` becomes `<generated-data-root>/cache`. Human
at-a-glance output removes the now-constant run-folder mode row and the obsolete
configured screenshot-root row, and shows the generated-data root instead. Completed
run output continues to show the concrete run-scoped screenshot and report paths.

## Wizard And Portable Contract

The wizard exposes the generated-data location in user-facing language such as
“Generated data location” or “Reports, screenshots, and cache location.” It must
make clear that the location contains both durable comparison folders and reusable
caches.

The default remains the workspace-relative `generated` directory. Windows portable
users must be able to select and persist a normal folder outside the replaceable
bundle without manually editing TOML. The selected value is stored through the
existing secret-safe config persistence owner, including the installed portable
fallback config under LocalAppData when that is the selected config.

The code-only portable updater, rollback tooling, reinstall flow, and uninstaller
must not create, delete, move, rewrite, or back up the configured external
generated-data root. A full portable-bundle replacement must leave external data
untouched.

Generated portable default config omits `paths.use_run_folders` and
`paths.screenshots_dir`. A top-level portable `screenshots/` directory is not a
runtime output root.

If a portable bundle is moved while source clips remain inside the bundle, cache
identity may change because source paths changed. The product must document this
without weakening cache validation.

Docker persists all reports, screenshots, run state, and caches through the
generated-data mount. The obsolete standalone screenshots mount and host-directory
setup are removed. An external container path is not durable unless mapped to a
host-owned location.

## Report And Review Portability

The canonical `report.html` and its sibling `screenshots/` directory form the local
review artifact. The report must initialize under `file://` from its run-folder root
on supported desktop browsers.

Screenshots are retained by default and this change adds no screenshot-retention
configuration. A non-embedded report requires the screenshot files. Embedding the
same compressed images as base64 and deleting the originals is normally larger, not
a disk-space optimization. Existing report-safe slow.pics post-upload deletion
semantics remain unchanged, but they are not generalized into a local archive
retention feature.

If measured storage use later justifies pruning, recompression, or whole-run
retention controls, that work requires a separate evidence-based specification. It
must not add a speculative boolean to this contract.

Browser-local viewer preferences and review notes remain browser storage scoped to
the report ID. Moving the run folder or changing browser profiles may not carry that
state. Existing review JSON export/import remains the portability mechanism for
review annotations; persisting browser review state into the run folder is outside
this specification.

## Clean Cutover

This pre-user change makes a clean cut with no migration surface:

1. `paths.generated_dir = "generated"` remains the default location.
2. Every run uses a run folder and the root-level `report.html` layout.
3. The single V1 result schema uses run-folder-relative artifact paths.
4. Removed configuration fields are deleted from code, tests, examples, and authored
   documentation without bespoke errors or compatibility parsing.
5. Existing local test data may be deleted and recreated; the application does not
   copy, migrate, or interpret it.

No release-note migration guide, compatibility writer, central report copy, or old
history reader is added.

## Invariants

1. One configured generated-data root owns both history and shared caches.
2. Every run has one canonical `<run-folder>/report.html`.
3. No report-specific output-directory setting exists.
4. A complete run folder is locally viewable without the application.
5. External generated-data roots never weaken descendant containment.
6. An unavailable configured root never causes silent fallback or split history.
7. Cache reuse remains identity-validated; persistence alone never forces a hit.
8. History remains read-only and exact-name based.
9. Config, JSON, TOML, CLI, and report outputs remain deterministic and secret-safe.
10. The portable updater and uninstaller never own user-selected external data.
11. Run folders and their derived screenshot directories have no configuration
    branches.

## Acceptance Criteria

### Default Location

- A default run creates `<workspace>/generated/<run>/report.html`.
- Its screenshots live under `<run>/screenshots/` and render correctly from the
  root-level report under `file://`.
- `run_info.toml` and `run_result.toml` remain at the run root.
- Shared analysis, alignment, and probe caches remain at the generated root.
- Human output, JSON output, auto-open, and history identify the same report.

### External Local Location

- An absolute normal folder on the same drive works without special setup.
- An absolute folder on another mounted drive produces the identical internal
  layout.
- Relative config continues to resolve beneath the workspace.
- `--diagnose-paths`, run execution, and both history commands agree on the resolved
  generated-data root.
- Replacing or moving the portable application bundle does not affect that external
  data.

### Link And Containment Safety

- A configured root that resolves through an intentional symlink or Windows junction
  is accepted when writable.
- A symlinked run directory is not treated as history.
- A report, record, screenshot directory, run-local generated directory, or cache
  path that resolves outside the selected root is rejected before use.
- A filesystem root, drive root, or bare share root is rejected as the configured
  generated-data location.

### Failure Behavior

- Missing or read-only local destinations produce typed actionable errors.
- Disconnected or inaccessible network destinations produce typed actionable errors.
- No failure writes to the old/default generated directory as a fallback.
- A run-result write failure preserves the existing completed-run warning and
  failed-run exception semantics.

### Clean Contract

- Result records reject absolute, traversal, drive, UNC, and symlink-escaping artifact
  paths.
- Production code, authored documentation, and current-config tests contain no
  `report.output_dir`, `paths.use_run_folders`, or `paths.screenshots_dir` behavior.
- No migration helper, compatibility fixture, version branch, or dual-path report
  logic remains.
- Successful JSON key sets and history JSON key sets do not change.
- Every successful run reports a run-scoped screenshot directory and canonical
  run-root report path.

### Portable And Docker

- The installed Windows portable wizard can persist an external generated-data
  location through its fallback config.
- Code-only update, rollback, reinstall, and uninstall verification demonstrate that
  external generated data is untouched.
- A Docker run with only the host-mounted generated-data output path retains reports,
  screenshots, run state, and caches after container removal.

## Verification Requirements For The Future Plan

The implementation is a high-risk public config/persistence and Windows-portable
change. The future plan must require:

- focused schema, loader, persistence, preflight, path-containment, and wizard tests;
- focused `WorkspacePaths`, run-folder, cache-location, report-generation,
  run-result, and history tests;
- focused CLI human/JSON/stream/help and `--diagnose-paths` contract tests;
- real-browser smoke verification of a root-level report with relative screenshots;
- the runbook's Full Verification gate;
- import-boundary verification if imports or owner seams change;
- the runbook's Windows portable/release-path verification on Windows;
- Docker integration verification if container mounts, Compose files, or Docker
  documentation behavior changes; and
- one independent review because report ownership, public config, history, and
  portable behavior are high-risk surfaces.

Network storage receives no dedicated proof requirement. A normal external Windows
directory and a local junction must be proved on Windows; host-exposed remote paths
inherit ordinary filesystem behavior.

## Rollback Constraints

Rollback means reverting the code and deleting/recreating local pre-release config,
run folders, and caches as needed. Older builds are not required to read the changed
config or records. The implementation must not add downgrade writers, duplicate
records, duplicate reports, or migration tooling to make source rollback seamless.

## Non-Goals

- A generated HTML archive index or report library page.
- A local history web server.
- Search, pagination, rename, delete, retention, or pruning commands.
- A latest-report copy, redirect, shortcut, or platform-specific launcher.
- Multiple simultaneous generated-data roots or merged history.
- Migration, copying, synchronization, or backup of old local data.
- Network authentication, mounting, offline synchronization, or conflict resolution.
- Separating cache and run-history roots in this change.
- Guaranteeing cache hits after source media paths or identities change.
- A screenshot-retention, latest-only, pruning, or disk-quota setting.
- Persisting browser-local review state directly into the run folder.
- Changing screenshot naming, run-folder naming, report viewer behavior, or slow.pics
  publishing semantics beyond use of the canonical report path.

## Recommended Two-Part Planning Boundary

The later implementation plan should preserve this ownership split:

### Part 1: Core Persistence And Report Contract

Own external generated-root resolution and containment, removal of
`report.output_dir`, `paths.use_run_folders`, and `paths.screenshots_dir`; resolved
workspace paths; unconditional run-folder reservation; canonical run-root report
placement; the single run-result record schema; history resolution; cache placement;
CLI contract updates; and core documentation.

Part 1 must leave all core behavior directly usable through authored config and the
existing CLI, independent of portable-specific UI.

### Part 2: Guided Adoption And Runtime Proof

Own wizard UX and persistence, installed Windows portable behavior, update/reinstall/
uninstall preservation proof, Docker guidance or mounts if affected, user
documentation, and end-to-end verification across default and external paths.

Part 2 must not redesign the core path or record contract established by Part 1.

Exact files, helper names, test organization, and commit boundaries belong in the
future implementation plan after a fresh impact scan.

## Stop Conditions

Stop and return to product or architecture planning if implementation discovery
shows any of the following:

- safe external-root support requires weakening descendant containment;
- the report cannot remain self-contained at the run root with relative screenshot
  references;
- portable config persistence cannot retain a user-selected external root without
  coupling user data to the bundle;
- the two implementation parts cannot be separated without an incomplete or unsafe
  public contract;
- removing flat-output mode reveals a current production workflow that cannot use
  run folders; or
- verification cannot prove normal external Windows storage and the portable
  update/reinstall preservation boundary.
