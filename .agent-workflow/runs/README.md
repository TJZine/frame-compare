# Agent Workflow Run Directory

This directory contains versioned artifact directories for each checklist item run.

## Convention

### RUN_ID Format

```
RUN_ID = YYYY-MM-DD__p<phase>-<item>__<short_slug>
```

For meta runs (non-checklist / maintenance tasks):

```
RUN_ID = YYYY-MM-DD__meta__<short_slug>
```

**Examples:**

- `2025-12-25__p1-1-1__config-module`
- `2025-12-26__p2-3__frame-extraction`
- `2025-12-25__p0-1__error-types`
- `2025-12-26__meta__ai-readiness-audit`

### Directory Layout

Each run produces a directory with 5 stage artifacts (each stage may be revised as `v2`, `v3`, ...):

```
.agent-workflow/runs/<RUN_ID>/
├── plan-v1.md          # Planning Agent output
├── plan-v2.md          # (if revision required)
├── plan-review-v1.md   # Plan Review Agent output
├── plan-review-v2.md   # (if revision required)
├── impl-v1.md          # Coding Agent output
├── impl-v2.md          # (if revision required)
├── verify-v1.md        # Verification Agent output
├── verify-v2.md        # (if revision required)
├── review-v1.md        # Review Agent output
└── review-v2.md        # (if revision required)
```

### Versioning Rules

1. Start at `v1` for all artifacts
2. If Plan Review requires changes:
   - Planning Agent emits `plan-v(N+1).md`
   - Plan Review Agent emits `plan-review-v(N+1).md`
3. Downstream artifacts reference exact `vN` they consumed
4. If Review requires changes:
   - Coding Agent emits `impl-v(N+1).md`
   - Verification Agent emits `verify-v(N+1).md`
   - Review Agent emits `review-v(N+1).md`
5. If Review identifies a design issue:
   - Return to Planning + Plan Review for `plan-v(N+1).md` and `plan-review-v(N+1).md` (then Coding/Verification/Review repeat)

### Plan Size Guardrails (Required)

- Plans must include `## Spec Anchors (SSOT)` that point to exact SSOT doc headings for each planned file change.
- Plans list one-line public function signatures wrapped in backticks (e.g., `` `load_config(path: Path) -> AppConfig` ``) for every planned function.
- Target ≤ **350 lines** for `plan-vN.md`; if a plan exceeds this, split into smaller sub-slices instead of iterating endlessly.
- If a run reaches `plan-v4` or higher, treat it as a spec/scope problem (STOP and clarify SSOT or split the run).

### Required Headers

Every artifact file must begin with:

```yaml
---
RUN_ID: <RUN_ID>
VERSION: vN
TARGET: Phase X → Item Y
INPUTS:
  - [list of files consumed]
OUTPUTS:
  - [list of files produced]
---
```

### Validation (Required)

Validate a RUN_ID and the artifacts written for that run:

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists <RUN_ID>
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/<RUN_ID>
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/<RUN_ID>/plan-v<N>.md
```

> `validate_spec_anchors.py` is required for new plans and revised plans going forward; older runs may not contain Spec Anchors/signature bullets.

> [!IMPORTANT]
> `scripts/validate_run_artifacts.py` enforces that NEXT blocks contain **no placeholders** for the current run,
> including non-concrete version tokens like `impl-v[N+1].md` / `plan-v(N+1).md`. Use digits only (e.g., `impl-v2.md`).

If either command fails: **STOP** and fix the run directory artifacts before proceeding.

## See Also

- [Agent Workflow Documentation](../../docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md)
- [Run Index](../index.md)
