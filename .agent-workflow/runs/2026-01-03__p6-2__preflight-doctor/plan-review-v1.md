---
RUN_ID: 2026-01-03__p6-2__preflight-doctor
VERSION: v1
TARGET: Phase 6 → Item 6.2
INPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/001-language-runtime.md
  - src/frame_compare/errors.py
  - pyproject.toml
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v1.md
---

# Plan Review Report: Preflight & Doctor

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** `.agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v1.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | FAIL | Introduces `WorkspacePaths` as an orchestration type with a shape that conflicts with utils SSOT (`utils-module.md` §3.1). |
| 2 | Dependencies | FAIL | Plan asserts `frame_compare.utils.progress` and “utils module” are completed, but `src/frame_compare/utils/types.py` (SSOT location of `WorkspacePaths`) is missing; plan also assumes error codes/signatures that conflict with SSOT and current `src/frame_compare/errors.py`. |
| 3 | File List | FAIL | Missing required files to align with SSOT: `src/frame_compare/utils/types.py` (+ likely `src/frame_compare/utils/__init__.py`) and (if using SSOT) updates to `src/frame_compare/errors.py` for `NoVideosFoundError(..., patterns=...)`. |
| 4 | Contract Impact | PASS | Canonical contracts are not planned to change; keep it NO if only code+tests+docs change. |
| 5 | Types Complete | FAIL | `WorkspacePaths` definition and ownership are incorrect vs SSOT; `NoVideosFoundError` code usage conflicts (plan claims FC-3002). |
| 6 | Tests Complete | FAIL | Several tests assert unspecified behavior (deprecated-config warnings), ambiguous semantics (`all_passed could be True` on optional failure), and non-deterministic setup (home expansion without a deterministic HOME fixture). |
| 7 | Verification Complete | FAIL | Commands deviate from command canon (scoped pyright/ruff/pytest); must include the exact canon commands. |
| 8 | Decision-Minimizing | FAIL | Leaves multiple design decisions to the Coding Agent (WorkspacePaths location/shape, Python version threshold, DoctorReport semantics, config sentinel path name). |
| 9 | Determinism Defined | FAIL | Preflight input discovery determinism (stable sorting + patterns) is referenced but not anchored to SSOT `orchestration-module.md` §4.3.6, and tests don’t specify deterministic setup for filesystem and env expansion. |

## Additional Quality Checks

- Error Codes: **Issue** — plan states `NoVideosFoundError (FC-3002)`; SSOT + code define `NoVideosFoundError` as **FC-3001** and `VideoOpenError` as FC-3002.
- Failure Modes: **Issue** — “VapourSynth missing” doctor behavior is described, but the exact `DoctorReport` semantics (`all_passed`, `critical_failures` contents) are not pinned.
- Derived Outputs: OK (no derived contract views intended).
- Rollback Guidance: OK (plan includes “mock external deps” guidance, but needs stronger STOP rules once SSOT conflicts are resolved).
- SSOT Update Audit (if SSOT changed this loop): N/A (this is plan-v1), but SSOT conflicts exist and must be fixed before coding.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Where `WorkspacePaths` lives and its exact field set (SSOT says `frame_compare.utils.types.WorkspacePaths` with specific fields/properties).
2. Which FC code `NoVideosFoundError` uses (SSOT conflict inside orchestration spec vs errors specs/code).
3. Python version threshold for doctor (repo/ADR says Python 3.13+; plan says 3.12).
4. Doctor semantics: whether `DoctorReport.all_passed` is false on any failure vs only “critical failures”; what strings populate `critical_failures` (names vs categories vs messages).
5. Config sentinel path for workspace discovery (`config/config.toml` vs `config.toml`).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Fix SSOT mismatch: NoVideosFoundError code in orchestration spec**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
   - Under heading: `#### 4.3.6 Input Discovery Rules`
   - Problem: Mentions `NoVideosFoundError (FC-3002)` but SSOT error specs + `src/frame_compare/errors.py` define `NoVideosFoundError` as FC-3001.
   - Required Change (SSOT): Update that snippet to `NoVideosFoundError (FC-3001)` (and reserve FC-3002 for video open failures).

2. **Use SSOT `WorkspacePaths` from utils (do not invent orchestration-owned shape)**
   - Section: `Files to Create/Modify`
   - Problem: Plan creates `src/frame_compare/orchestration/types.py` with a conflicting `WorkspacePaths` shape.
   - Required Change (plan): Remove `src/frame_compare/orchestration/types.py`. Create/modify `src/frame_compare/utils/types.py` per `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md` §3.1 (and re-export from `src/frame_compare/utils/__init__.py` if SSOT requires).
   - Required Change (plan): Update `resolve_paths(...) -> WorkspacePaths` to build fields from `ConfigSchema.paths` (`input_dir`, `screenshots_dir`, `generated_dir`, `config_dir`) per `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md` §2.2.

3. **Align error constructors to SSOT (or explicitly scope to existing signatures)**
   - Section: `Preflight` implementation + tests
   - Problem: SSOT `errors-module.md` defines `NoVideosFoundError(path: Path, patterns: list[str] | None = None)`; current `src/frame_compare/errors.py` accepts only `(directory: Path)`. Plan must not force the Coding Agent to choose between SSOT and code.
   - Required Change (plan): Either (preferred) include `src/frame_compare/errors.py` update in file list to match SSOT signature for `NoVideosFoundError` (optional `patterns`), OR narrow plan to calling the existing constructor and update SSOT error spec accordingly (disallowed unless you also update the SSOT docs).

4. **Make Doctor semantics unambiguous**
   - Section: `doctor.py` + `tests/orchestration/test_doctor.py`
   - Problem: Test description says “optional failure not critical → all_passed could be True” which is ambiguous.
   - Required Change (plan): Specify exact rules:
     - `DoctorReport.all_passed` is `True` only if **all** checks passed.
     - `DoctorReport.critical_failures` contains the `DoctorCheck.name` values for **failed core** checks only.
   - Required Change (plan): Specify reporter call expectations (total = number of checks; call sequence minimum set to assert).

5. **Pin Python version requirement**
   - Section: `doctor.py` checks + tests + Spec Anchors
   - Problem: Plan uses “>= 3.12” without SSOT anchor; repo SSOT is Python 3.13+.
   - Required Change (plan): Require Python 3.13+ and add spec anchor to `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/001-language-runtime.md` → `## Decision`.

6. **Fix preflight workspace discovery sentinel path and tests**
   - Section: `resolve_workspace` tests
   - Problem: Tests reference `config.toml`, but SSOT config path is `config/config.toml`.
   - Required Change (plan): Update tests and implementation to use `config/config.toml` consistently (also adjust upward-search fixture layout).

7. **Verification commands must include exact command canon**
   - Section: `Verification Commands`
   - Problem: Plan uses scoped checks (`pyright --warnings src/...`, `pytest -v ...`) instead of canon.
   - Required Change (plan): Include these exact commands (optionally followed by scoped runs):
     - `.venv/bin/pyright --warnings`
     - `.venv/bin/ruff check .`
     - `.venv/bin/pytest -q`
     - `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`

## Ready for Implementation

Return to Planning Agent for SSOT correction + plan revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-03__p6-2__preflight-doctor

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
- Under heading: "#### 4.3.6 Input Discovery Rules" add/change:
  - Change `NoVideosFoundError (FC-3002)` to `NoVideosFoundError (FC-3001)` (FC-3002 remains reserved for video open errors).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v1.md
Write file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
