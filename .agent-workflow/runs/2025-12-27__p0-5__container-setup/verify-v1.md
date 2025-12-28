---
RUN_ID: 2025-12-27__p0-5__container-setup
VERSION: v1
TARGET: Phase 0 → Item 0.5 (Container Setup)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/impl-v2.md
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v4.md
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/verify-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md (updated)
  - .agent-workflow/index.md (appended)
---

# Verification Handoff: Container Setup

## Summary

**Date:** 2025-12-28
**Plan Reference:** .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v4.md
**Plan Review Report:** .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v4.md
**Implementation Report:** .agent-workflow/runs/2025-12-27__p0-5__container-setup/impl-v2.md

## Implementation Review

### Plan Review Gate

- [x] Plan Review Report exists
- [x] Verdict: APPROVED

### Plan Compliance

- [x] All files in plan were created
- [x] No extra files created beyond plan scope
- [x] Implementation matches plan exactly
- [x] Deviations documented in impl-v2.md:
  - Updated lsmas namespace verification guidance (prefer `lsmas` with `lw` fallback)
  - Various documentation updates for namespace order

### Documentation Check

- [x] Dockerfile has appropriate comments
- [x] docker-compose.yml documented
- [x] devcontainer.json has VS Code customizations
- [x] CHANGELOG.md updated
- [x] docs/DECISIONS.md updated

## Verification Results

### Quality Gates

```text
$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest --cov
..                                                               [100%]
2 passed in 0.03s
Required test coverage of 80.0% reached. Total coverage: 85.71%
```

### Contract Gates

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/2025-12-27__p0-5__container-setup
OK: Run artifacts valid for 2025-12-27__p0-5__container-setup
```

### Docker Verification

```text
$ docker --version
Docker version 29.1.3, build f52814d

$ docker images | grep frame-compare
frame-compare:builder   d9ad230f066b   936MB
frame-compare:dev       8ae407ccef79   653MB

$ docker run --rm frame-compare:dev --help
✓ CLI help displayed (exit 0)

$ docker run --rm --entrypoint python frame-compare:dev -c "import vapoursynth as vs; ..."
VS Version Number: 73
✓ VapourSynth R73 verified (exit 0)

$ docker run --rm --entrypoint python frame-compare:dev -c "..." (lsmas check)
lsmas: lsmas.LWLibavSource available
✓ lsmas plugin verified (exit 0)

$ docker run --rm --entrypoint python frame-compare:dev -c "..." (placebo check)
placebo: Tonemap callable
✓ placebo plugin verified (exit 0)

$ docker run --rm --entrypoint python frame-compare:dev -c "..." (ffms2 check)
ffms2: Source available
✓ ffms2 plugin verified (exit 0)
```

### Negative Test (Plugin Isolation)

```text
$ docker run --rm --entrypoint sh frame-compare:dev -c \
  "printf 'UserPluginDir=/nonexistent\nSystemPluginDir=/nonexistent\n' > /tmp/vs.conf && \
   VAPOURSYNTH_CONF_PATH=/tmp/vs.conf python -c \"...(lsmas check)...\"" \
  && echo "UNEXPECTED" || echo "EXPECTED: Assertion failed"
Autoloading the user plugin dir '/nonexistent' failed. Directory doesn't exist?
AssertionError: lsmas should be loaded
EXPECTED: Assertion failed (lsmas not found with isolated config)
✓ PASS: Plugin isolation works correctly with VAPOURSYNTH_CONF_PATH
```

> [!NOTE]
> The original plan used `VAPOURSYNTH_PLUGIN_PATH=/nonexistent` which does not disable autoloading. The impl-v2.md corrected this to use `VAPOURSYNTH_CONF_PATH` with a temp config, which correctly isolates plugin discovery. The lsmas-first positive check is correct (legacy `lw`-only checks fail in the baseline container).

## Checklist Updates

- [x] Marked complete: 0.5 Container Setup (6 of 7 items)
  - DevContainer VS Code verification left unchecked (manual user action)
- [x] Updated: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md

## Index Updates

- [x] Appended to: .agent-workflow/index.md

## Issues Found

None. All verification gates passed, including the corrected negative test using `VAPOURSYNTH_CONF_PATH`.

## Ready for Review

All verification gates passed. Docker verification passed. Handoff to Review Agent.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-27__p0-5__container-setup

## Files to Read

1. Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/verify-v1.md
2. Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/impl-v2.md
3. Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v4.md
4. Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v4.md

## Preconditions

- Plan Review Report shows Verdict: APPROVED
- All verification gates passed

## Your Task

Perform final quality review and issue verdict.

## Output

Write file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/review-v1.md
