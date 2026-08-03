---
search:
  exclude: true
---

Status: Supporting handoff; not a second active plan
Authority: [Persistent generated-data spec](2026-08-02-persistent-generated-data-spec.md)
Owner: Planning agent and maintainer

# Persistent Generated Data Implementation-Planning Handoff

## Purpose

Use this handoff to produce the decision-complete two-part implementation plan for
the active persistent generated-data specification. This handoff authorizes planning
artifact edits only. It does not authorize production-code implementation, staging,
committing, pushing, release work, or destructive cleanup of local generated data.

Use the configured `planner` role from `.codex/agents/planner.toml`. Read exact role
and model settings from that file at dispatch; do not copy them into the durable
plan.

## Authority Order

Read these sources before planning:

1. `AGENTS.md`
2. `docs/ENGINEERING_RUNBOOK.md`
3. `docs/plans/2026-08-02-persistent-generated-data-spec.md`
4. `docs/current-architecture.md`
5. `docs/current-cli-contract.md`
6. `importlinter.ini`
7. `pyproject.toml` only where verification, packaging, or dependency ownership
   requires it

Load and follow the smallest relevant repo-local skill set, including:

- `execution-plan-authoring`
- `model-selection`
- `persistence-boundaries`
- `architecture-boundaries`
- `cli-contract-boundaries`
- `report-output-patterns`
- `runtime-integration-boundaries`
- `verification-strategy`

Use `python-test-design` only when the plan must settle a non-obvious proof seam.
Use `bounded-worker-execution` when shaping implementation units for delegated
execution.

The specification is product authority for this workstream. Current source and
tests remain authority for the implementation impact surface. If source evidence
contradicts the spec or exposes an unresolved product decision, stop and report the
conflict rather than rewriting the product contract during planning.

## Frozen Product Decisions

Do not reopen or soften these decisions:

- `paths.generated_dir` is the sole persistent generated-data location.
- Relative generated paths remain workspace-relative; explicit absolute and
  environment-expanded external paths are supported.
- `report.output_dir` is deleted outright with no compatibility parser, bespoke
  migration error, deprecation path, or retained product documentation.
- `paths.use_run_folders` is deleted; every real run uses a fresh run folder.
- `paths.screenshots_dir` is deleted; screenshots always use
  `<run-folder>/screenshots/`.
- The canonical report is `<run-folder>/report.html`.
- `run_result.toml` remains one V1 schema and changes directly to run-relative
  `report_path` and `screenshot_dir`; no old-record reader or version branch is
  retained.
- Existing local pre-release config, run folders, and caches may be deleted and
  recreated; no migration tooling is planned.
- Shared analysis, alignment, and probe caches follow `paths.generated_dir`.
- An explicit external generated root never silently falls back when unavailable.
- The configured root may resolve through an intentional symlink or Windows
  junction, but managed descendants may not escape the resolved root.
- Docker persists output through the generated-data mount only; the standalone
  screenshots mount is removed.
- The Windows portable wizard must let users persist a normal external data
  location, and portable update/reinstall/uninstall paths must not own that data.
- No screenshot-retention, latest-only, pruning, quota, archive-index, or migration
  feature is added.

Apply YAGNI throughout: prefer deletion, existing owners, existing standard-library
path behavior, and one contract over compatibility branches, new abstraction layers,
or speculative configuration.

## Required Planning Discovery

Perform a fresh read-only impact scan. At minimum, trace:

- `PathsConfig`, `ReportConfig`, config loading, config serialization, presets, and
  wizard persistence;
- preflight path normalization and containment;
- `WorkspacePaths` construction and run-folder transition;
- run-folder reservation and `run_info.toml` lifecycle;
- screenshot render destinations;
- report output-path selection and relative image payload generation;
- completed and failed `run_result.toml` writing, parsing, discovery, and report
  resolution;
- `history list` and `history open`;
- human output, successful JSON, `--diagnose-paths`, auto-open, and report-confirmed
  slow.pics behavior;
- shared analysis, alignment, and probe cache paths;
- slow.pics post-upload deletion and shortcut behavior only far enough to preserve
  the frozen report/screenshot contract;
- Docker Compose mounts and Docker-facing documentation;
- Windows portable default config, shim fallback config, wizard, update, reinstall,
  uninstall, and their contract tests;
- current test fixtures that use flat-output mode for convenience rather than
  product behavior; and
- current authority documentation that must change with the public contract.

Use `rg`/`rg --files` first. Inspect the working tree before planning and preserve
the existing untracked specification and this handoff.

## Planning Deliverable

Create:

```text
docs/plans/2026-08-02-persistent-generated-data-implementation-plan.md
```

The plan must use the runbook's active-plan preamble:

```text
---
search:
  exclude: true
---

Status: Active
Scope: <exact implementation scope>
Owner: <controller/maintainer ownership>
```

In the same planning-artifact change, replace the specification's `Status: Active`
with a non-active approved-specification marker that links to the new active plan.
This preserves one active plan for the workstream. Keep this handoff supporting and
non-active.

Do not edit production code while authoring the plan.

## Required Plan Shape

The plan must contain exactly two implementation parts matching the specification:

### Part 1: Core Persistence And Report Contract

Make the general Python/config/filesystem behavior complete and directly usable
without portable-specific UI. Cover configuration deletion, external generated-root
resolution and containment, unconditional run folders, derived screenshot paths,
run-root report placement, run-relative result records, history, cache placement,
CLI/public output changes, core docs, and direct proof.

Part 1 must end at a coherent product checkpoint. It must not leave two report paths,
two result-record meanings, or a temporary flat-output compatibility mode.

### Part 2: Guided Adoption And Runtime Proof

Cover wizard UX/persistence, Windows portable defaults and preservation boundaries,
Docker mount simplification, user-facing setup/docs, end-to-end default/external-path
proof, and final high-risk verification/review.

Part 2 must consume the Part 1 contract without redesigning it.

Within each part, define the smallest dependency-ordered work packages that can be
implemented and verified independently. Each package must include:

- outcome;
- owner seam and allowed write boundary;
- public contracts and invariants;
- explicit non-goals;
- acceptance criteria;
- focused verification;
- integration checkpoint;
- stop conditions; and
- likely role eligibility at dispatch.

Do not freeze helper names, speculative abstractions, exact test-file organization,
or exact file lists unless writer collision or a sensitive shared surface requires
it.

## Luna-First Execution Posture

Shape bounded implementation packages so `worker_luna` is the default eligible role
at dispatch under `.codex/agents/worker-luna.toml`.

A Luna-eligible package has:

- one coherent owner or disjoint write boundary;
- settled product and public-contract decisions;
- direct acceptance criteria and runnable proof;
- no unresolved compatibility or migration policy;
- no dependency addition;
- no need to redesign architecture; and
- explicit stop conditions for scope expansion or contradictory evidence.

Do not permanently pin a model or reasoning effort in the plan. At dispatch, the
controller selects the configured `worker_luna` role by default when the package
remains bounded. Escalate to configured `worker` only when the settled unit still
requires material cross-boundary design judgment, complex diagnosis, or proof
interpretation. Return unresolved product, architecture, ownership, or verification
questions to planning instead of asking either worker to invent policy.

Avoid concurrent writers unless the plan proves their file/owner boundaries are
disjoint. The controller owns integration, diff review, and rerunning the required
verification.

## Verification And Review Requirements

The plan must route verification through the runbook rather than inventing a second
command canon. It must include:

- focused proof for each package;
- a Part 1 integration checkpoint;
- a Part 2 Windows portable/runtime checkpoint;
- the runbook's Full Verification gate at final integration;
- Windows portable/release-path verification on a compatible Windows host;
- Docker integration verification because Compose output mounts change;
- real-browser proof that run-root `report.html` loads relative screenshots under
  `file://`;
- import-boundary proof when imports or owner seams change; and
- one independent final `reviewer` pass because the change touches public config,
  history, report output, Docker, Windows portable behavior, and report hotspots.

The plan must distinguish locally executable proof from Windows- or host-dependent
proof. It must not mark a platform path verified from source inspection alone.

## Planning Stop Conditions

Stop and ask the maintainer rather than completing the plan if discovery shows:

- a currently required production workflow depends on flat-output mode;
- an unavoidable need for old config or result-record compatibility;
- report-relative screenshot loading cannot support the run-root layout;
- safe external path support requires weakening descendant containment;
- portable config cannot retain an external root independently of the bundle;
- the two parts cannot end at coherent independently verifiable checkpoints;
- required proof depth cannot be stated concretely; or
- a new dependency, database, server, archive index, cleanup policy, or screenshot
  retention feature appears necessary.

## Expected Handoff Back

Return only after:

1. the active two-part implementation plan exists;
2. the specification status points to that plan and is no longer independently
   active;
3. this supporting handoff remains non-active;
4. strict documentation validation passes;
5. the planning diff contains no production-code changes; and
6. the final response links the plan and summarizes package boundaries, Luna
   eligibility, unresolved stop conditions, and validation performed.

## Paste-Ready Planner Prompt

```text
Use the configured planner role for Frame Compare. Read AGENTS.md, the engineering
runbook, and docs/plans/2026-08-02-persistent-generated-data-planning-handoff.md in
full, then follow that handoff exactly. Treat
docs/plans/2026-08-02-persistent-generated-data-spec.md as frozen product authority.
Perform a fresh read-only impact scan and create the required decision-complete,
two-part active implementation plan. Make work packages Luna-eligible wherever the
owner seam, contracts, acceptance criteria, proof, and stop conditions can be made
bounded. Do not implement production code. Preserve unrelated worktree changes and
run strict documentation validation before handing the plan back.
```
