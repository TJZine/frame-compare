---
RUN_ID: 2026-02-04__p6-7-13__docker-real-deps-zero-skips
VERSION: v1
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Write integration tests (Docker, real deps; zero skips)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - tools/verify_docker_integration.sh
  - tests/integration/conftest.py
  - src/frame_compare/orchestration/coordinator.py
  - src/frame_compare/orchestration/preflight.py
  - src/frame_compare/orchestration/probe_cache.py
  - src/frame_compare/vs/source.py
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-7-13__docker-real-deps-zero-skips/plan-v1.md
---

# Implementation Plan: Docker Integration Tests for LoadSources Probe Cache (Real Deps, Zero Skips)

## Context

**Phase:** 6 (CLI & Orchestration)
**Checklist slice:** Phase 6 → Item 6.7 — Runner & Phase Orchestration
**Goal in this slice:** Add Docker-runnable integration tests that exercise the real VapourSynth + FFmpeg LoadSources path and verify probe cache file write + reuse behavior, with **zero skips** under `tools/verify_docker_integration.sh`.

## Contract Impact

**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "3.5.1 Probe Cache I/O Helpers (SSOT)"
  - Section: "4.4.3 Execute Function"
  - Section: "4.4.4 Phase Ordering (SSOT)"
  - Section: "4.4.7 Output Directory Layout"
  - Section: "7.2 Integration Tests"
  - Section: "7.3 Docker Integration Gate (Zero Skips)"

## Scope

This plan covers:

- [ ] Add `tests/integration/test_loadsources_probe_cache.py` implementing the two checklist-required integration tests:
  - write `generated/clip_probe.toml` during LoadSources when cache is empty
  - reuse `generated/clip_probe.toml` on a second run (no re-probe)
- [ ] Ensure tests are runnable under Docker with **real** VapourSynth + FFmpeg and result in **zero skips** when executed by `bash tools/verify_docker_integration.sh`.
- [ ] Keep tests deterministic (fixed tiny CFR inputs; stable filenames; no network).

This plan does NOT cover:

- Implementing non-stub behavior for later phases (FramePlan/Analyze/Align/Render/Publish/Report).
- Changing Docker image contents or the Docker integration gate script.
- CLI flag wiring beyond what is already present in `RunRequest`.

## Files to Create/Modify

### 1. [NEW] `tests/integration/test_loadsources_probe_cache.py`

**Purpose:** Real-deps integration coverage for LoadSources probe caching in Docker (Phase 6 → Item 6.7 checklist).

**Tests required (names are canonical per checklist):**

- `test_loadsources_writes_clip_probe_cache_file`
  - Arrange a temporary workspace root containing:
    - `config/config.toml` (minimal; may be empty)
    - `comparison_videos/` with at least two small deterministic CFR videos produced by FFmpeg (via existing integration fixtures).
  - Run `execute_run` with a real `DefaultVSLoader` and quiet progress.
  - Assert `{root}/generated/clip_probe.toml` exists and `load_clip_probe_cache(...)` returns entries for each discovered input video.
- `test_loadsources_reuses_clip_probe_cache_file`
  - Run `execute_run` once to populate `{root}/generated/clip_probe.toml`.
  - Capture the cache file contents (text) after the first run.
  - Run `execute_run` again with a VS loader that raises if `load(...)` is called.
  - Assert the second run succeeds, the cache file contents are unchanged, and the loader was not invoked.

**Key implementation notes:**

- Place the file under `tests/integration/` so it is executed by `bash tools/verify_docker_integration.sh` (which runs `pytest -v tests/integration/ tests/vs/`).
- Use the existing `tests/integration/conftest.py::mock_video_path` fixture so FFmpeg availability is enforced the same way as other integration tests.
- Gate test execution in non-Docker environments:
  - Skip at module import time when VapourSynth is absent or globally mocked by `tests/conftest.py`.
  - Skip when the `lsmas` plugin (LWLibavSource) is not available on the real core.
  - In Docker, these skips must not trigger (gate requires zero skips).

## Functions to implement (spec-anchored)

This slice is test-first, but the plan anchors the callable surfaces being exercised by the new integration tests (no production code changes expected unless the tests uncover a defect).

- `async def execute_run(request: RunRequest, deps: RunDependencies | None = None) -> RunResult` — LoadSources probes inputs, writes `generated/clip_probe.toml`, and reuses the cache on subsequent runs.
- `def load_clip_probe_cache(cache_path: Path) -> dict[str, ClipProbeSnapshot]` — Load probe cache from `{workspace.generated_dir}/clip_probe.toml` with SSOT semantics.
- `def save_clip_probe_cache(cache_path: Path, entries_by_key: Mapping[str, ClipProbeSnapshot]) -> None` — Persist probe cache deterministically to `{workspace.generated_dir}/clip_probe.toml`.

## Acceptance Criteria

- [ ] `tests/integration/test_loadsources_probe_cache.py` exists and implements both checklist-required tests.
- [ ] `tools/verify_docker_integration.sh` passes and reports **zero skips**.
- [ ] The “writes cache” test confirms `generated/clip_probe.toml` is created and readable via `load_clip_probe_cache(...)`.
- [ ] The “reuses cache” test confirms a second run does not call the video loader and does not change cache file contents.

## Verification Commands

```bash
# Run-focused checks (fast)
.venv/bin/pytest -q tests/integration/test_loadsources_probe_cache.py

# Full local gates
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini

# Docker real-deps gate (must be zero skips)
bash tools/verify_docker_integration.sh
```

## Notes for Coding Agent

- Prefer `RunRequest(root=workspace_root, quiet=True)` to avoid FPS report noise during integration tests.
- Keep the workspace setup minimal: create `config/config.toml` and rely on schema defaults for paths; use the default `comparison_videos/` + `generated/` structure per SSOT.
- Use stable filenames (e.g., `a_ref.mp4`, `b_comp.mp4`) to keep deterministic discovery ordering.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-02-04__p6-7-13__docker-real-deps-zero-skips

## Files to Read
1. Read file: .agent-workflow/runs/2026-02-04__p6-7-13__docker-real-deps-zero-skips/plan-v1.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
5. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md

## Your Task
Review the plan for completeness, SSOT alignment, and decision-minimization. Confirm the plan satisfies the Docker gate requirement (real deps, zero skips) and that Spec Anchors + signature coverage will pass `validate_spec_anchors.py`.

## Output
Write file: .agent-workflow/runs/2026-02-04__p6-7-13__docker-real-deps-zero-skips/plan-review-v1.md
