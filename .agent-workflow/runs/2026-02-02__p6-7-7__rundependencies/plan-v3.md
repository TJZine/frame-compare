---
RUN_ID: 2026-02-02__p6-7-7__rundependencies
VERSION: v3
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement RunDependencies for dependency injection
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-v2.md
  - .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/api-design.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-v3.md
---

# Implementation Plan: RunDependencies (Dependency Injection)

## Context
**Phase:** 6 (CLI & Orchestration)
**Checklist slice:** Phase 6 → Item 6.7 — Runner & Phase Orchestration
**Goal in this slice:** Implement the `RunDependencies` dependency injection container used by `run(...)` / `execute_run(...)` to enable testability and deterministic unit tests without real external tools.

## Changes Since plan-v2

- Resolved Plan Review decision points by explicitly choosing a stub-only `DefaultFFmpegRunner` for this slice (non-functional; raises `NotImplementedError`).
- Clarified where the DI surface lives (coordinator types) and how to interpret SSOT examples that reference `frame_compare.types`.
- Tightened unit test requirements to cover default `get_ffmpeg_runner()` behavior (not only injected overrides).

## Scope
This plan covers:
- [ ] Implement `RunDependencies` per `cli-module.md` (fields + default-provider helpers).
- [ ] Define the DI protocol surface used by `RunDependencies` for FFmpeg access (protocol + default implementation stub).
- [ ] Re-export `RunDependencies` via `frame_compare.orchestration` (public surface until `frame_compare.runner` exists).
- [ ] Add unit tests for `RunDependencies` defaults and injected override behavior (no external tools).

This plan does NOT cover:
- Creating `src/frame_compare/runner.py` or implementing the public `run(request, dependencies=None) -> RunResult` entry point (separate checklist item under 6.7).
- Implementing `async execute_run(request, deps=None) -> RunResult` or any phase orchestration (`orchestration-module.md` §4.4.3/§4.4.4).
- Implementing real FFmpeg subprocess behavior; the default FFmpeg runner is intentionally a stub in this slice.
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

**Ownership clarifications (this slice):**
- `FFmpegRunner` (Protocol) lives in this file.
- `DefaultFFmpegRunner` lives in this file and is a stub implementation in this slice.
- `RunDependencies` lives in this file and provides default-provider helpers.

**Signature intent (informational; not a planned-signature list):**

```python
class FFmpegRunner(Protocol):
    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None: ...
    def probe_hdr(self, video: Path) -> HDRMetadata | None: ...

class DefaultFFmpegRunner:
    def extract_frame(self, video: Path, frame_num: int, output: Path) -> None: ...
    def probe_hdr(self, video: Path) -> HDRMetadata | None: ...

@dataclass
class RunDependencies:
    vs_loader: VSLoader | None = None
    ffmpeg_runner: FFmpegRunner | None = None
    http_client: httpx.AsyncClient | None = None
    progress: ProgressReporter | None = None
    clock: Callable[[], datetime] = field(default=datetime.now)
    def get_vs_loader(self) -> VSLoader: ...
    def get_ffmpeg_runner(self) -> FFmpegRunner: ...
```

**Implementation notes:**
- Keep imports side-effect free (no eager FFmpeg/VapourSynth invocation).
- `vs_loader` default MUST be lazy (construct default loader only when requested).
- `ffmpeg_runner` default MUST be lazy (construct default runner only when requested).
- `DefaultFFmpegRunner` methods MUST raise `NotImplementedError` in this slice (explicit stub decision).
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
- Verify default `ffmpeg_runner` is constructed lazily when none is provided.
- Verify `clock` is callable and returns a `datetime`.

### 4. `docs/DECISIONS.md` (MODIFY)
**Purpose:** Append a short decision log entry capturing:
- The stub-only decision for `DefaultFFmpegRunner` in this slice.
- The temporary export location of `RunDependencies` via `frame_compare.orchestration` (until `frame_compare.runner` exists).

### 5. `CHANGELOG.md` (MODIFY)
**Purpose:** Note that `RunDependencies` has been added for dependency injection/testability.

## SSOT Example Mismatch Handling (Plan Clarification)

Some SSOT docs/examples reference `from frame_compare.types import RunDependencies`. In the current repo state, `frame_compare.types` is not present.

For this slice, treat the canonical import as:
- `from frame_compare.orchestration import RunDependencies`

This plan explicitly does NOT introduce a new `frame_compare.types` module; that decision is deferred until the `frame_compare.runner` package-root API is implemented and stabilized.

## Functions to implement

- `get_vs_loader(self) -> VSLoader`
- `get_ffmpeg_runner(self) -> FFmpegRunner`
- `extract_frame(self, video: Path, frame_num: int, output: Path) -> None`
- `probe_hdr(self, video: Path) -> HDRMetadata | None`

## Acceptance Criteria

- [ ] `RunDependencies` exists with the fields described in `cli-module.md` §3.4 (including optional injection + default clock).
- [ ] `get_vs_loader()` returns the injected loader if present; otherwise returns a lazily-created default loader.
- [ ] `get_ffmpeg_runner()` returns the injected runner if present; otherwise returns a lazily-created `DefaultFFmpegRunner` stub.
- [ ] `DefaultFFmpegRunner` methods raise `NotImplementedError` in this slice (explicit stub decision; real FFmpeg execution deferred).
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
- Implement `DefaultFFmpegRunner` as an explicit stub in this slice (raise `NotImplementedError`), and ensure tests only validate DI wiring (construction + return values), not subprocess execution.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-02-02__p6-7-7__rundependencies

## Plan to Review
Read file: .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-v3.md

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
Write file: .agent-workflow/runs/2026-02-02__p6-7-7__rundependencies/plan-review-v3.md
