---
RUN_ID: 2026-02-03__p6-7-12__consolidated-fps-report-5-4
VERSION: v1
TARGET: Phase 6 → Item 6.7
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/plan-v1.md
---

# Implementation Plan: Consolidated FPS Report (§5.4) + Unit Tests (ClipState + Probe Cache)

## Context

**Phase:** 6
**Module:** `frame_compare.orchestration`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` → Section 5.4
**Dependencies:** Orchestration module slice exists (`context.py`, `coordinator.py`, `probe_cache.py`, existing unit tests)

## Scope

This plan covers (bundled under Phase 6 → Item 6.7):

- [ ] Implement a consolidated, operator-facing FPS report per orchestration spec §5.4
- [ ] Emit the report exactly twice per run: after LoadSources and after Align (even when Align is skipped)
- [ ] Ensure JSON-mode produces a structured FPS block (log event) and non-JSON mode prints a human-readable report
- [ ] Unit test coverage:
  - [ ] FPS report divergence flagging (source != effective)
  - [ ] ClipState trim/effective frame count invariants remain covered
  - [ ] Probe cache keying + deterministic I/O behavior (including missing-version behavior and deterministic ordering)

This plan does NOT cover:

- Any changes to how `effective_fps` is computed (forced/inherited fps policy is deferred)
- Any VS / FFmpeg integration behavior (no external deps in unit tests)
- CLI surface / `frame-compare run` output plumbing (CLI is still stubbed)

## Contract Impact

**Contracts touched:** NO

No canonical contract files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` are modified by this slice.

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`:
  - Section: "5.4 FPS Diagnostics (Operator-Facing, Consolidated)"
  - Section: "4.4.4 Phase Ordering (SSOT)"
  - Section: "3.5 Runtime Context Types (SSOT)"
  - Section: "3.5.1 Probe Cache I/O Helpers (SSOT)"
  - Section: "7.1 Unit Tests"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "1.3 Deterministic Test Vector Policy (SSOT)"

## Files to Create/Modify

### 1. [NEW] `src/frame_compare/orchestration/fps_report.py`

**Purpose:** Build and emit the consolidated FPS report described in orchestration spec §5.4.

**Types to define:**

- `FpsReportClip` — immutable per-clip FPS diagnostics entry (source/effective/divergence + optional note)

**Functions to implement (spec-anchored):**

- `build_consolidated_fps_report(reference: ClipState, comparisons: Sequence[ClipState]) -> tuple[FpsReportClip, ...]`
- `emit_consolidated_fps_report(*, stage: str, clips: Sequence[FpsReportClip], json_output: bool, quiet: bool) -> None`

**Behavior requirements:**

- Clip ordering is deterministic:
  - Reference first, then comparisons in input order.
- `fps_divergent` is True iff `effective_fps != source_fps` for that clip.
- JSON-mode behavior:
  - Emit a single structlog event named `fps_report` with fields:
    - `stage`: `"after_load_sources"` or `"after_align"`
    - `clips`: list of dicts containing (at minimum) the four spec-required fields:
      - `source_fps_num`, `source_fps_den`
      - `effective_fps_num`, `effective_fps_den`
      - `fps_divergent`
      - `note` (omit or set null when absent)
    - Include `label` and `path` as additional, operator-helpful fields.
  - Do not log anything when `quiet=True`.
- Non-JSON behavior:
  - Print a single, human-readable multi-line report to stderr (one line per clip).
  - Do not print anything when `quiet=True`.

---

### 2. [MODIFY] `src/frame_compare/orchestration/coordinator.py`

**Purpose:** Emit the consolidated FPS report after LoadSources and after Align, per spec §5.4.

**Change details (no public signature changes):**

- Import the new helpers from `frame_compare.orchestration.fps_report`.
- After LoadSources completes (immediately after `RunContext` is constructed), emit the consolidated report with:
  - `stage="after_load_sources"`
  - `json_output=request.json_output`
  - `quiet=request.quiet`
- Ensure a second emission occurs after the Align phase boundary:
  - Execute phases up to Align (inclusive), then emit:
    - `stage="after_align"`
    - `json_output=request.json_output`
    - `quiet=request.quiet`
  - This emission must occur even if Align is skipped by config.
- Keep `RunResult` shape unchanged (no new fields added).

---

### 3. [NEW] `tests/orchestration/test_fps_report.py`

**Purpose:** Unit tests for FPS report building/emission helpers (pure + deterministic; no VS required).

**Tests required:**

| Test Name | Scenario | Expected |
|-----------|----------|----------|
| `test_build_consolidated_fps_report_orders_reference_then_comparisons` | reference + 2 comparisons | tuple order is reference, comp1, comp2 |
| `test_build_consolidated_fps_report_flags_divergence_when_effective_fps_differs` | clip with `source_fps != effective_fps` | `fps_divergent` True |
| `test_emit_consolidated_fps_report_noop_when_quiet` | `quiet=True` | no print and no log emission (use monkeypatch) |

---

### 4. [MODIFY] `tests/orchestration/test_execute_run.py`

**Purpose:** Verify orchestration emits FPS report at the correct boundaries (after LoadSources and after Align).

**Tests required:**

| Test Name | Scenario | Expected |
|-----------|----------|----------|
| `test_execute_run_emits_fps_report_after_load_sources_and_after_align` | minimal valid run, Align disabled in config | emitter called twice with stages `after_load_sources` then `after_align` |

**Implementation note:** Use `monkeypatch` to replace the emitter in `frame_compare.orchestration.coordinator` (not structlog capture) and record calls deterministically.

---

### 5. [MODIFY] `tests/orchestration/test_probe_cache.py`

**Purpose:** Complete SSOT-required probe cache unit coverage for missing-version handling and deterministic write ordering.

**Tests required (additions):**

| Test Name | Scenario | Expected |
|-----------|----------|----------|
| `test_load_clip_probe_cache_returns_empty_dict_on_missing_version` | TOML without top-level `version` | empty dict |
| `test_save_clip_probe_cache_writes_version_first_and_keys_sorted` | two entries with out-of-order keys | file text has `version = \"1\"` before any table; tables appear in lexicographic key order |

## Acceptance Criteria

- [ ] GIVEN a run with ≥1 clip WHEN LoadSources completes THEN a consolidated FPS report is emitted with stage `after_load_sources`
- [ ] GIVEN any run WHEN the Align phase boundary is passed (executed or skipped) THEN a consolidated FPS report is emitted with stage `after_align`
- [ ] GIVEN any clip WHEN `effective_fps != source_fps` THEN the report marks `fps_divergent=True` for that clip
- [ ] GIVEN `json_output=True` THEN the FPS report is emitted as a single structured log event `fps_report` containing per-clip required fields
- [ ] GIVEN `quiet=True` THEN no FPS report is emitted/printed
- [ ] GIVEN probe cache TOML missing `version` THEN `load_clip_probe_cache` returns empty dict (warn-only)
- [ ] GIVEN probe cache is saved THEN key ordering is deterministic (sorted) and `version = "1"` is first

## Verification Commands

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/plan-v1.md
.venv/bin/pyright --warnings src/frame_compare/orchestration/
.venv/bin/ruff check src/frame_compare/orchestration/
.venv/bin/pytest -v tests/orchestration/
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

1. Keep the FPS report logic pure and unit-testable; tests should not depend on structlog renderer configuration.
2. JSON output must avoid non-serializable values (no `Fraction` / `Path` objects in the emitted payload).
3. Do not change public signatures of `execute_run`, `RunRequest`, or `RunResult` in this slice.
4. Probe cache ordering test should assert only stable, non-brittle properties (version first + table key ordering).

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-02-03__p6-7-12__consolidated-fps-report-5-4

## Plan to Review

Read file: .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-02-03__p6-7-12__consolidated-fps-report-5-4/plan-review-v1.md
