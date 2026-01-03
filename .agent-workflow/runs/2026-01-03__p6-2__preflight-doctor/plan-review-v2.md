---
RUN_ID: 2026-01-03__p6-2__preflight-doctor
VERSION: v2
TARGET: Phase 6 → Item 6.2
INPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/001-language-runtime.md
  - src/frame_compare/errors.py
  - src/frame_compare/config/loader.py
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v2.md
---

# Plan Review Report: Preflight & Doctor

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** `.agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v2.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Scope matches checklist 6.2 (preflight + doctor) and includes required utils type (`WorkspacePaths`). |
| 2 | Dependencies | FAIL | Plan depends on SSOT sections that currently conflict (`orchestration-module.md` §5.1 refers to `config.toml`, but plan implements `config/config.toml`). |
| 3 | File List | FAIL | Missing required code file to reconcile SSOT vs implementation: `src/frame_compare/errors.py` must be updated (or SSOT error signature must be changed) because plan anchors to error-handling SSOT that includes `NoVideosFoundError(..., patterns=...)` but instructs “do not add patterns”. |
| 4 | Contract Impact | PASS | No canonical contracts touched; contract freshness checks are included (acceptable). |
| 5 | Types Complete | FAIL | Public APIs are listed, but required behavior details remain underspecified (config discovery behavior for `config_path=None`, path expansion rules, and video patterns source). |
| 6 | Tests Complete | FAIL | Missing tests/negative cases for required plugin check (`lsmas`) and for missing input directory; “minimal valid TOML” content is unspecified (test fixture decision). |
| 7 | Verification Complete | PASS | Uses exact command canon (plus spec-anchor validation). |
| 8 | Decision-Minimizing | FAIL | Leaves coding decisions: config path selection rules, whether to update errors signature vs diverge from SSOT, and how to validate `lsmas` presence. |
| 9 | Determinism Defined | FAIL | Input discovery patterns and stable ordering are not anchored (`orchestration-module.md` §4.3.6) and path expansion behavior is not explicitly specified/tested. |

## Additional Quality Checks

- Error Codes: OK for FC-3001 usage in acceptance criteria; remaining mismatch is constructor signature vs SSOT.
- Failure Modes: Issue — missing-input-directory behavior not specified (should raise `DirectoryNotFoundError` per existing `src/frame_compare/errors.py`).
- Derived Outputs: OK (no derived contract views edited).
- Rollback Guidance: OK (plan includes deterministic test guidance; add STOP triggers once SSOT conflicts are resolved).
- SSOT Update Audit (if SSOT changed this loop): OK — `orchestration-module.md` §4.3.6 now references `NoVideosFoundError (FC-3001)` which matches error SSOT and `src/frame_compare/errors.py`.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. `resolve_workspace` sentinel path: SSOT §5.1 currently says `config.toml`; plan uses `config/config.toml`.
2. `NoVideosFoundError` signature: SSOT docs include optional `patterns`; current code does not; plan forbids adding `patterns`.
3. `prepare_preflight` config discovery behavior when `config_path is None` (exact rule not specified).
4. Doctor plugin check (`lsmas`) detection method and corresponding unit tests.
5. Missing input directory behavior (which exception, and whether preflight creates output dirs or only validates).

## Concrete Edits Required (if CHANGES REQUIRED)

1. **Update SSOT: path-resolution sentinel must match repo layout**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
   - Under heading: `"### 5.1 Path Resolution"`
   - Problem: The `resolve_workspace` docstring uses `config.toml`, but the repo’s config location is `config/config.toml` (also used in `ConfigSchema.model_config` and in the plan).
   - Required Change (SSOT): Replace the sentinel references so the priority list reads:
     - “Current working directory if `config/config.toml` exists”
     - “Search upward for `config/config.toml`”

2. **Align `NoVideosFoundError` constructor with SSOT (preferred: update code)**
   - Section: `Files to Create/Modify` + `Notes for Coding Agent`
   - Problem: Plan anchors to SSOT (`error-handling.md` / `errors-module.md`) that define `NoVideosFoundError(path, patterns=...)` but plan instructs to use existing `NoVideosFoundError(directory)` and forbids adding `patterns`.
   - Required Change (plan): Include `src/frame_compare/errors.py` in the file list and update `NoVideosFoundError` to accept `patterns: list[str] | None = None` (matching SSOT), including `details={"directory": ..., "patterns": ...}` (or SSOT-equivalent keys). Then update preflight to pass the patterns list used for discovery.

3. **Make `prepare_preflight` config discovery unambiguous**
   - Section: `src/frame_compare/orchestration/preflight.py` → `prepare_preflight`
   - Problem: The plan does not state exactly how `config_path=None` is handled (which path is tried and in what order).
   - Required Change (plan): Specify:
     - If `config_path` is provided: load that file (raise `ConfigNotFoundError` if missing).
     - Else: resolve `root = resolve_workspace(root)` then use `root / "config" / "config.toml"` as the config file path (raise `ConfigNotFoundError` if missing).

4. **Anchor and specify input discovery patterns**
   - Section: `Spec Anchors (SSOT)` and preflight “video discovery”
   - Problem: Plan references “patterns” but does not define them or anchor to the SSOT pattern list / stable ordering.
   - Required Change (plan): Add spec anchor to `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md` → `"#### 4.3.6 Input Discovery Rules"`, and explicitly state that the patterns list is `["*.mkv", "*.mp4", "*.avi", "*.m2ts", "*.ts"]` and ordering is stable (case-insensitive lexicographic).

5. **Complete doctor checks + tests for required plugins and missing input directory**
   - Section: `tests/orchestration/test_doctor.py` and `tests/orchestration/test_preflight.py`
   - Problem: Core plugin requirement (`lsmas`) is listed but has no tests; missing input directory behavior is not covered.
   - Required Change (plan): Add tests:
     - `test_check_lsmas_plugin_fails_when_missing` (core) and `test_check_lsmas_plugin_passes_when_available`.
     - `test_prepare_preflight_missing_input_dir_raises_directory_not_found` (use existing `DirectoryNotFoundError`).

6. **Specify deterministic “minimal valid TOML”**
   - Section: `tests/orchestration/test_preflight.py` fixture setup
   - Problem: “minimal valid TOML” is unspecified.
   - Required Change (plan): Specify exact file contents (e.g., empty file, or an explicit `[paths]` block with defaults) to avoid test fixture decisions.

7. **Add missing Spec Anchor for TMDB env var name**
   - Section: `Spec Anchors (SSOT)` and doctor network checks
   - Problem: Plan hardcodes `TMDB_API_KEY` without an anchor.
   - Required Change (plan): Add spec anchor to `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md` → `"### 3.3 Special Environment Variables"` and keep the check as “presence only” (no network).

## Ready for Implementation

Return to Planning Agent for SSOT update + plan revision. Next version: `plan-v3.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-03__p6-2__preflight-doctor

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
- Under heading: "### 5.1 Path Resolution" add/change:
  - Update the sentinel path references from `config.toml` to `config/config.toml` in steps (2) and (3).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v2.md
Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v2.md
Write file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v3.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
