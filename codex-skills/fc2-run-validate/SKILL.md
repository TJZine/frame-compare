---
name: fc2-run-validate
description: Use when validating a Frame Compare 2.0 run directory after an agent writes an artifact (RUN_ID format + artifact hygiene + NEXT block placeholder rules).
---

# FC-2.0 Run Validation Skill

## Canonical Rules

- Run directory + artifact rules live in:
  - `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`
  - `.agent-workflow/runs/README.md`
- Validators:
  - `scripts/validate_run_id.py`
  - `scripts/validate_run_artifacts.py`

## Quick Commands (Command Canon)

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists <RUN_ID>
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/<RUN_ID>
```

## Convenience Wrapper (optional)

If you want a single command (uses `sys.executable` to avoid PATH issues):

```bash
python3 codex-skills/fc2-run-validate/scripts/validate_run.py <RUN_ID>
```

## What “good” looks like

- Exit code 0
- Ends with: `OK: Run artifacts valid for <RUN_ID>`
