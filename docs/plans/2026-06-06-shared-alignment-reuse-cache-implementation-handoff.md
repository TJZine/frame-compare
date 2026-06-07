Status: Historical
Historical Scope: Archived record of the shared alignment reuse cache implementation orchestration
Historical Owner: Completed Codex implementation orchestrator

# Shared Alignment Reuse Cache Implementation Handoff

Historical status note: this handoff records the completed shared-alignment
implementation workflow and is not an active implementation launcher. For
legacy alignment persistence cleanup, including `previous_offsets = "disabled"`
shared-cache write behavior, legacy `audio_offsets.toml` precedence, and
`check_alignment_cached()` lifetime, defer to
`docs/plans/2026-06-07-alignment-persistence-convergence-plan.md`.

The preserved content below is retained for historical record only.

## 1. Source Plan

Implement this approved plan:

```text
docs/plans/2026-06-06-shared-alignment-reuse-cache-plan.md
```

The plan review loop is complete. The final adversarial
`frame-compare-feature-review` pass returned:

```text
Clean review: no blocking findings and no required changes.
```

Do not re-plan the feature unless implementation evidence hits a stop-and-replan
trigger in the source plan.

## 2. Orchestrator Contract

The orchestrator owns:

- reading `AGENTS.md`, `docs/ENGINEERING_RUNBOOK.md`, the source plan,
  `docs/current-architecture.md`, `docs/current-cli-contract.md`, and relevant
  boundary skills before work starts
- maintaining the live `update_plan` checklist
- cutting implementation into the slices below
- dispatching exactly one implementation worker per active slice
- integrating worker output
- running local verification for the slice
- requesting adversarial review for the slice
- adjudicating reviewer findings
- creating one commit per accepted slice
- continuing through all slices until the full feature is complete

Do not stop after one slice unless blocked by a source-plan stop condition,
failed verification that cannot be fixed in-scope, merge conflicts that require
human choice, or missing local tooling that prevents meaningful progress.

## 3. Agent Settings

Implementation worker agents:

```text
agent_type = default
model = gpt-5.5
reasoning_effort = low
```

Reviewer agents:

```text
agent_type = default
model = gpt-5.5
reasoning_effort = low
```

Use fresh reviewer agents for review passes. Keep reviewers read-only. Close
completed agents once their result has been adjudicated.

## 4. Per-Slice Loop

Run this loop for every slice.

1. Confirm the slice has disjoint write scope from any active worker.
2. Spawn one implementation worker with the exact slice contract:
   - task
   - files in scope
   - files out of scope
   - invariants
   - required tests
   - expected final report
3. Worker edits only its slice files and reports changed files plus commands run.
4. Orchestrator inspects the worker output and local diff.
5. Orchestrator runs the slice's targeted verification locally.
6. If targeted verification fails, send the failure back to the same worker to
   fix within the slice. Repeat until targeted verification passes or a stop
   condition is hit.
7. Spawn one fresh read-only reviewer for the slice with the diff, files changed,
   verification output, and source-plan invariants.
8. If the reviewer finds issues, adjudicate them. Accepted or modified findings
   go back to the same slice worker for best-practice fixes.
9. After fixes, rerun targeted verification locally.
10. If the first reviewer surfaced any issues, run up to two more fresh
    read-only reviewers against the revised slice before committing.
    - Maximum review passes per slice: three total.
    - Do not exceed this cap for usage control.
    - If review pass 2 or 3 finds a real blocker, fix it with the same worker,
      rerun targeted verification, and continue only until the three-pass cap is
      reached.
11. Before committing, run `git diff --check` and inspect `git diff --stat` plus
    the changed slice files.
12. Commit the slice with a conventional commit message.
13. Continue immediately to the next slice.

If the third reviewer still reports a blocker after fixes, do not create that
slice commit. Stop and report the blocker, the attempted fixes, and the
verification state.

## 5. Review Request Template

Use this shape for every slice reviewer:

```text
REVIEW_REQUEST
TASK:
Adversarially review implementation slice <slice id/name> for the shared
alignment reuse cache feature.

TASK_FAMILY:
Feature implementation review.

RISK_TIER:
Use the source plan risk tier. Escalate attention for CLI/config, persistence,
or runtime slices.

REVIEW_TARGET:
Current local diff for this slice only.

PLAN_OR_ARTIFACT:
docs/plans/2026-06-06-shared-alignment-reuse-cache-plan.md

FILES_IN_SCOPE:
<exact changed files for this slice>

FILES_OUT_OF_SCOPE:
Unrelated dirty files and future slices.

KEY_INVARIANTS:
<slice invariants plus relevant source-plan invariants>

VERIFICATION_RUN:
<commands run by orchestrator and exact pass/fail summary>

KNOWN_RISKS:
<slice-specific risks>

WHAT_TO_PRIORITIZE:
Correctness, public contract drift, filesystem/cache safety, import layers,
runtime regressions, missing tests, brittle tests, and docs drift.

OUTPUT_EXPECTATION:
Lead with findings ordered by severity and cite file/line references. Separate
blockers from optional improvements. Say explicitly when no blocking findings
are found.
```

## 6. Slice Order

### Slice 1: Config Surface And Effective Validation

Files in scope:

- `src/frame_compare/config/schema_models.py`
- `src/frame_compare/config/defaults.py`
- `src/frame_compare/services/types.py`
- `src/frame_compare/cli/run_command.py`
- `tests/config/test_schema.py`
- `tests/config/test_overrides.py`
- `tests/cli/test_run_json_errors.py`
- `tests/cli/test_run_command.py`
- `tests/cli/test_run_request_config.py`

Implement:

- `audio_alignment.previous_offsets = "disabled" | "prompt" | "always"`
- default config template entry
- typed service-side policy field
- runtime validation for prompt/json and prompt/quiet
- effective-config validation for:
  - `force_interactive = true` with `previous_offsets = "prompt" | "always"`
  - `cache_results = false` with `previous_offsets = "prompt" | "always"`
- `run --write-config` and `run --write-config --json` pre-write rejection
- no CLI flag and no override-map entry

Targeted verification:

```bash
.venv/bin/pytest -q tests/config/test_schema.py tests/config/test_overrides.py tests/cli/test_run_json_errors.py tests/cli/test_run_command.py tests/cli/test_run_request_config.py
.venv/bin/pyright --warnings
```

Commit message:

```text
feat: add previous offset reuse config policy
```

### Slice 2: Workspace Path And Layer-Neutral Request DTOs

Files in scope:

- `src/frame_compare/utils/types.py`
- `src/frame_compare/orchestration/preflight.py`
- `src/frame_compare/orchestration/phase_tasks.py`
- `tests/orchestration/test_preflight.py`
- `tests/orchestration/test_preparation.py`
- `tests/orchestration/test_phase_tasks_alignment.py`
- `tests/orchestration/test_execute_run_phase_integration.py`
- `tests/orchestration/test_phase_tasks_outputs.py`

Implement:

- optional-backed `WorkspacePaths.shared_alignment_cache_dir`
- run-folder preservation of workspace-level shared alignment cache path
- layer-neutral alignment request/cache-identity DTOs in `utils.types`
- orchestration construction of the typed alignment request
- no service import of orchestration/analysis-owned identity types
- preserve existing phase output behavior and monkeypatch seams

Targeted verification:

```bash
.venv/bin/pytest -q tests/orchestration/test_preflight.py tests/orchestration/test_preparation.py tests/orchestration/test_phase_tasks_alignment.py tests/orchestration/test_execute_run_phase_integration.py tests/orchestration/test_phase_tasks_outputs.py
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
.venv/bin/pyright --warnings
```

Commit message:

```text
feat: add shared alignment reuse request plumbing
```

### Slice 3: Shared Alignment Reuse Cache Owner

Files in scope:

- `src/frame_compare/services/alignment_reuse_cache.py`
- `src/frame_compare/services/types.py`
- `tests/services/test_alignment_reuse_cache.py`
- `tests/services/test_alignment_cache.py`

Implement:

- versioned TOML shared cache owner under `shared_alignment_cache_dir`
- stable source-set/cache identity using typed request facts
- freshness validation for path, size, mtime, trims, FPS, reference relation,
  selected streams, and audio-alignment settings
- complete source-set all-or-nothing load
- atomic deterministic writes
- provenance schema with `origin = "computed" | "vspreview_confirmed"`
- per-entry `accepted_at`
- computed score replay and confirmed score `1.0`
- corrupt/version-mismatch read fallback with warning
- write failure warning without failing the run
- no promotion of legacy `audio_offsets.toml`, preexisting manual overrides, or
  shared reuse

Targeted verification:

```bash
.venv/bin/pytest -q tests/services/test_alignment_reuse_cache.py tests/services/test_alignment_cache.py
.venv/bin/pyright --warnings
```

Commit message:

```text
feat: add shared alignment reuse cache
```

### Slice 4: Prompt Boundary And Human Output

Files in scope:

- `src/frame_compare/services/alignment_reuse_prompt.py`
- `src/frame_compare/services/alignment.py`
- `src/frame_compare/services/alignment_vspreview.py` only if needed for a
  narrow progress/interaction hook
- `tests/services/test_alignment_reuse_prompt.py`
- `tests/services/test_alignment_vspreview.py`
- `tests/cli/test_run_output.py`

Implement:

- Rich stderr table for previous offsets
- Rich-safe labels, stems, filenames, and paths
- yes/no prompt with default No
- no blocking read unless stdin and stderr are both TTYs
- deterministic fallback line when stderr is visible and prompt cannot complete
- no human diagnostic when stderr is non-TTY
- `--no-color` behavior
- progress suspend/resume around prompt/table

Targeted verification:

```bash
.venv/bin/pytest -q tests/services/test_alignment_reuse_prompt.py tests/services/test_alignment_vspreview.py tests/cli/test_run_output.py
.venv/bin/pyright --warnings
```

Commit message:

```text
feat: add alignment reuse prompt output
```

### Slice 5: Alignment Coordinator Reuse And Persistence

Files in scope:

- `src/frame_compare/services/alignment.py`
- `src/frame_compare/services/types.py`
- `tests/services/test_alignment_core.py`
- `tests/services/test_alignment_workflow.py`
- `tests/services/test_alignment_workflow_vspreview.py`
- `tests/integration/test_alignment_runtime.py`

Implement:

- precedence:
  1. current-run manual overrides
  2. accepted shared previous-offset reuse
  3. current-run `audio_offsets.toml`
  4. computed correlation
  5. optional VSPreview confirmation
- disabled mode performs no shared read/write
- always mode reuses complete valid previous offsets and skips compute/VSPreview
- prompt yes/no branching with VSPreview fallback on no
- service protection for invalid policy combinations
- write-source provenance carrier
- shared writes only when the entire source set is write-eligible
- reuse-only runs do not refresh `accepted_at`
- preserve `align_clips(...)` wrapper current behavior only
- preserve `check_alignment_cached()` current-run-only behavior
- preserve duplicate stem fail-fast behavior

Targeted verification:

```bash
.venv/bin/pytest -q tests/services/test_alignment_core.py tests/services/test_alignment_workflow.py tests/services/test_alignment_workflow_vspreview.py tests/integration/test_alignment_runtime.py
.venv/bin/pyright --warnings
```

Commit message:

```text
feat: reuse previous alignment offsets
```

### Slice 6: CLI Preview And Authority Docs

Files in scope:

- `src/frame_compare/cli/output.py`
- `docs/current-cli-contract.md`
- `docs/current-architecture.md`
- `tests/cli/test_cli_output.py`
- `tests/test_cli_contract_docs.py`
- `tests/cli/test_run_command.py` only for diagnose/no-cache doc-lock behavior

Implement:

- at-a-glance `previous offsets` row
- CLI contract documentation for config-only mode, JSON/quiet/write-config
  behavior, TTY fallback, no-color, cache path, `--no-cache`, and
  `--from-cache-only`
- architecture documentation for persistence owner, run-folder exception,
  request seam, prompt helper, and provenance carrier
- docs-lock assertions

Targeted verification:

```bash
.venv/bin/pytest -q tests/cli/test_cli_output.py tests/test_cli_contract_docs.py tests/cli/test_run_command.py
.venv/bin/pyright --warnings
```

Commit message:

```text
docs: document shared alignment reuse cache
```

### Slice 7: Final Integration And Full Gate

Files in scope:

- all files touched by slices 1-6
- no new behavior unless required to fix integration failures

Implement:

- resolve cross-slice integration failures
- remove dead helpers or duplicated test fixtures introduced during slices
- run full verification
- update the active plan status only if the repo's current plan policy expects
  completed plans to be marked after implementation

Required verification:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
bash tools/verify_docker_integration.sh
```

If Docker cannot run locally, record it as a documented-only gap and do not
claim Docker/runtime verification passed.

Commit message:

```text
test: verify shared alignment reuse integration
```

## 7. Commit Rules

- Create one commit per accepted slice.
- Use conventional commits.
- Stage only files in the completed slice.
- Never stage unrelated dirty files.
- Before each commit run:

```bash
git status --short
git diff --stat
git diff --check
git diff -- <slice files>
```

- After each successful commit, continue to the next slice.
- Do not squash during this loop.

## 8. Stop Conditions

Stop and report instead of committing if:

- a source-plan stop-and-replan trigger is hit
- the worker needs to invent a public contract or owner seam not in the source
  plan
- import-linter requires a boundary change beyond the planned owner seams
- targeted verification keeps failing after the same worker has attempted a
  reasonable fix
- the third reviewer for a slice still reports a real blocker
- unrelated workspace changes overlap the slice files and cannot be separated
  safely
- Docker/runtime verification cannot run during final integration and the
  maintainer requires local proof rather than documented-only status

## 9. Final Completion Criteria

The feature loop is complete only when:

- every slice above has either a committed implementation or a documented,
  maintainer-accepted reason for being unnecessary
- every implemented slice has passed targeted local verification
- every implemented slice has passed its capped adversarial review loop
- full verification has been run, or documented-only gaps are explicitly stated
- the final diff is clean except for unrelated pre-existing workspace files
- final report includes commit list, verification results, review status, and
  any documented-only gaps
