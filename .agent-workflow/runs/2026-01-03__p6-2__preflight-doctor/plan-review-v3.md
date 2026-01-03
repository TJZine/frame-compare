---
RUN_ID: 2026-01-03__p6-2__preflight-doctor
VERSION: v3
TARGET: Phase 6 → Item 6.2
INPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v3.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/utils-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/001-language-runtime.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-handling.md
  - src/frame_compare/vs/env.py
OUTPUTS:
  - .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v3.md
---

# Plan Review Report: Preflight & Doctor

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** `.agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v3.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Scope matches checklist 6.2 and remains bounded. |
| 2 | Dependencies | PASS | Uses `config`, `errors`, `utils.progress`, and (for plugin detection) `vs.env` which exists. |
| 3 | File List | PASS | Files are explicitly listed, including required `errors.py` signature alignment and `utils/types.py`. |
| 4 | Contract Impact | PASS | Canonical contracts untouched; contract freshness gates included (acceptable). |
| 5 | Types Complete | FAIL | `NoVideosFoundError` alignment is incomplete vs SSOT (missing required instance attributes per SSOT snippet), and doctor check names/order are not fully pinned (coding agent would choose). |
| 6 | Tests Complete | FAIL | Missing deterministic tests for (a) path/env expansion in `resolve_paths`, (b) stable case-insensitive input ordering, and (c) slow.pics reachability URL/timeout behavior. |
| 7 | Verification Complete | PASS | Exact command canon is present; spec-anchor validation included. |
| 8 | Decision-Minimizing | FAIL | Leaves several behavioral choices to Coding Agent (slow.pics URL, exact doctor check list/names/order, exact expansion semantics verification). |
| 9 | Determinism Defined | FAIL | Input discovery determinism is described but not tested (ordering), and path expansion behavior is required by SSOT but not specified/tested deterministically. |

## Additional Quality Checks

- Error Codes: OK (FC-3001 used consistently; SSOT `orchestration-module.md` §4.3.6 updated correctly).
- Failure Modes: OK (missing input dir → `DirectoryNotFoundError` is now specified).
- Derived Outputs: OK (no derived contract views edited).
- Rollback Guidance: OK (STOP trigger included).
- SSOT Update Audit (this loop): OK — `orchestration-module.md` §5.1 now references `config/config.toml`, consistent with repo config layout.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. The exact slow.pics reachability URL to probe and how to treat non-200 responses.
2. The exact set of `DoctorCheck.name` strings and their ordering (needed for deterministic `critical_failures` and stable reporting/tests).
3. How `resolve_paths` implements and verifies path expansion rules from SSOT (env vars + `~`) without platform-dependent tests.
4. Whether `NoVideosFoundError` exposes `self.path`/`self.patterns` attributes per SSOT error snippets (plan currently does not require them).

## Concrete Edits Required (plan-v4.md)

1. **Complete `NoVideosFoundError` SSOT alignment**
   - Section: `Files to Create/Modify` → `src/frame_compare/errors.py`
   - Problem: Plan aligns signature and `details` keys but does not require the SSOT-described instance attributes.
   - Required Change: Add explicit requirements (mirroring `errors-module.md` example) to set:
     - `self.path = path`
     - `self.patterns = patterns or []` (or document why this attribute is intentionally omitted, but omission would require SSOT update—avoid).

2. **Pin doctor check names + ordering**
   - Section: `src/frame_compare/orchestration/doctor.py` (add a short “Check List (deterministic)” subsection)
   - Problem: Names are implied by tests but not specified as a complete list; ordering is unspecified.
   - Required Change: Specify the exact list and order returned by `collect_checks()` including `name` and `category`, e.g.:
     - core: `python_version`, `vapoursynth`, `lsmas`
     - optional: `ffmpeg`, `dovi_tool`, `vspreview`
     - network: `slowpics`, `tmdb_api_key`

3. **Make slow.pics probe deterministic**
   - Section: `doctor.py` network checks + `tests/orchestration/test_doctor.py`
   - Problem: Plan specifies HEAD+timeout but not the URL or response handling.
   - Required Change: Specify:
     - URL: `https://slow.pics/` (exact string)
     - Timeout: 5.0 seconds
     - Pass criteria: request succeeds with status < 400 (or specify exact accepted statuses)
     - Failure criteria: exception or status >= 400 sets `passed=False` with a non-empty hint.
   - Add a unit test asserting the request call parameters (mock `httpx.Client.head`) and that failure populates `CheckResult.passed=False`.

4. **Add deterministic tests for required preflight behaviors**
   - Section: `tests/orchestration/test_preflight.py`
   - Problem: SSOT requires path expansion and stable ordering; plan doesn’t include tests.
   - Required Change: Add tests:
     - `test_resolve_paths_expands_env_vars` — write config with `[paths] input_dir="$TEST_ROOT/in"` and set `TEST_ROOT` via `monkeypatch.setenv`; assert resolved `workspace.input_dir` matches expanded path.
     - `test_prepare_preflight_discovers_inputs_sorted_case_insensitive` — create files `b.mkv` and `A.mkv`; assert the discovered list ordering is case-insensitive lexicographic (as specified in SSOT §4.3.6).

## Ready for Implementation

Return to Planning Agent for a small, plan-only revision. Next version: `plan-v4.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-03__p6-2__preflight-doctor

## Revision Required
Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-review-v3.md
Read file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v3.md
Write file: .agent-workflow/runs/2026-01-03__p6-2__preflight-doctor/plan-v4.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
