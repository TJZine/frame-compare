---
RUN_ID: 2026-02-02__p6-7-7__rundependencies
VERSION: v1
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement RunDependencies for dependency injection
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-v1.md
---

# Implementation Plan: RunDependencies (Dependency Injection)

## Context
**Phase:** 6 (CLI & Orchestration)
**Checklist slice:** Phase 6 → Item 6.7 — Runner & Phase Orchestration
**Goal in this slice:** Implement the `RunDependencies` dependency injection container used by `run(...)` / `execute_run(...)` to enable testability and deterministic unit tests without real external tools.

## Scope
This plan covers:
- [ ] Implement `RunDependencies` per `cli-module.md` (fields + default-provider helpers).
- [ ] Define the DI protocol surface used by `RunDependencies` for FFmpeg access (protocol + default implementation stub/adapter).
- [ ] Re-export `RunDependencies` via `frame_compare.orchestration` (public surface until `frame_compare.runner` exists).
- [ ] Add unit tests for `RunDependencies` defaults and injected override behavior (no external tools).

This plan does NOT cover:
- Creating `src/frame_compare/runner.py` or implementing the public `run(request, dependencies=None) -> RunResult` entry point (separate checklist item under 6.7).
- Implementing `async execute_run(request, deps=None) -> RunResult` or any phase orchestration (`orchestration-module.md` §4.4.3/§4.4.4).
- Any behavior that requires real external dependencies (FFmpeg/FFprobe, VapourSynth, network calls).

## Contract Impact
**Contracts touched:** NO

No changes to canonical contract files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md`:
  - Section: “6.7 Runner & Phase Orchestration”
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: “1.2 Module Structure”
  - Section: “3.3 Dependency Injection Protocols”
  - Section: “3.4 RunDependencies”
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: “4.4.3 Execute Function”
- `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md`:
  - Section: “3.4 Dependency Injection”
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: “4.3 Dependency Injection Testing”

## Files to Create/Modify

### 1. `src/frame_compare/orchestration/coordinator.py` (MODIFY)
**Purpose:** Add the `RunDependencies` dataclass and its related DI protocol surface in a location that is already the home for run coordination types (`RunRequest`, `RunResult`).

**Implementation notes:**
- Keep imports side-effect free (no eager FFmpeg/VapourSynth invocation).
- `vs_loader` default MUST be lazy (construct default loader only when requested).
- `http_client` lifecycle remains caller-owned when injected (runner/execute_run will manage the default client lifecycle later; this slice only stores it).
- `clock` MUST be injectable and default to `datetime.now` (per spec).

### 2. `src/frame_compare/orchestration/__init__.py` (MODIFY)
**Purpose:** Re-export `RunDependencies` as part of the current public orchestration surface (consistent with `RunRequest`/`RunResult` re-exports), until `frame_compare.runner` exists.

### 3. `tests/orchestration/test_run_dependencies.py` (ADD)
**Purpose:** Unit tests for dependency injection behavior without requiring external dependencies.

**Tests required (names are suggestions; exact names can vary):**
- Verify `RunDependencies` is importable via both `frame_compare.orchestration` and `frame_compare.orchestration.coordinator`.
- Verify injected `vs_loader` and `ffmpeg_runner` are returned unchanged by the getter helpers.
- Verify default `vs_loader` is constructed lazily when none is provided.
- Verify `clock` is callable and returns a `datetime`.

### 4. `docs/DECISIONS.md` (MODIFY)
**Purpose:** Append a short decision log entry capturing the DI surface and the temporary export location (until `frame_compare.runner` is created).

### 5. `CHANGELOG.md` (MODIFY)
**Purpose:** Note that `RunDependencies` has been added for dependency injection/testability.

## Functions to implement

- `RunDependencies.get_vs_loader(self) -> VSLoader`
- `RunDependencies.get_ffmpeg_runner(self) -> FFmpegRunner`
- `DefaultFFmpegRunner.extract_frame(self, video: Path, frame_num: int, output: Path) -> None`
- `DefaultFFmpegRunner.probe_hdr(self, video: Path) -> HDRMetadata | None`

## Acceptance Criteria

- [ ] `RunDependencies` exists with the fields described in `cli-module.md` §3.4 (including optional injection + default clock).
- [ ] `frame_compare.orchestration` publicly exports `RunDependencies`.
- [ ] Unit tests validate default-provider behavior and injected overrides without invoking external tools.

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → Command Canon.

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Recommended targeted test during development:

```bash
.venv/bin/pytest -q tests/orchestration/test_run_dependencies.py
```

## Notes for Coding Agent

- Keep this slice narrowly focused on the DI container surface; do not introduce `frame_compare.runner` yet.
- Avoid adding unit tests that require FFmpeg, VapourSynth, or network access; keep tests pure and deterministic.
- Prefer adding new DI protocol types in a way that does not force immediate implementation of external-tool logic; the pipeline wiring will land in later 6.7 items.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-02-02__p6-7-7__rundependencies

## Plan to Review
Read file: .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-v1.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates/checklist only)
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
5. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
6. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-review-v1.md
