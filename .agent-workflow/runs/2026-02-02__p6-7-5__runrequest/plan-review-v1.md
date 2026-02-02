---
RUN_ID: 2026-02-02__p6-7-5__runrequest
VERSION: v1
TARGET: Phase 6 → Item 6.7 — Runner & Phase Orchestration — Implement `RunRequest` dataclass per spec
INPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-review-v1.md
---

# Plan Review Report: `RunRequest` (Runner & Phase Orchestration)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-02
**Plan Reference:** `.agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v1.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice (Phase 6.7 `RunRequest` type only) with clear out-of-scope list. |
| 2 | Dependencies | PASS | No new runtime deps; type-only change scoped to `dataclasses` + `pathlib`. |
| 3 | File List | PASS | Minimal and explicit: new `coordinator.py`, modify `__init__.py`, add one test file. |
| 4 | Contract Impact | PASS | Plan explicitly states canonical contracts are not touched. |
| 5 | Types Complete | FAIL | Plan does not list the full public signature in a single backticked line (it uses an ellipsis) and does not explicitly pin the authoritative field order when SSOT definitions differ between orchestration/CLI specs. |
| 6 | Tests Complete | FAIL | Plan names tests but does not enumerate field-by-field assertions for defaults, and acceptance criteria includes public export but no test/explicit assertion covers it. |
| 7 | Verification Complete | PASS | Commands + pass criteria are explicit and align with command canon. |
| 8 | Decision-Minimizing | FAIL | Current plan text can cause a coding-time STOP due to SSOT drift wording (“field set identical across both SSOT specs”) without clarifying that order differences are non-semantic and which definition to implement in `coordinator.py`. |
| 9 | Determinism Defined | PASS | N/A (type-only slice; no algorithmic output). |

## Additional Quality Checks

- Error Codes: OK (no new errors introduced in this slice).
- Failure Modes: OK (not applicable; type-only).
- Derived Outputs: OK (no derived contract views involved).
- Rollback Guidance: OK (not required for a type-only slice).
- SSOT Update Audit (if SSOT changed this loop): Issue — SSOT sources referenced by the plan include two `RunRequest` definitions with differing field order; plan must explicitly state which ordering is implemented and why that is not a coding-time decision.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether `RunRequest` field order should follow `orchestration-module.md` §4.4.1 verbatim (recommended for `frame_compare.orchestration.coordinator`) when `cli-module.md` §3.1 shows a different order.
2. Whether to add an explicit test assertion that `RunRequest` is exported from `frame_compare.orchestration` (acceptance criteria implies it, but plan does not require a test).

## Concrete Edits Required (for plan-v2.md)

1. **Make the public signature fully explicit (no ellipsis)**
   - Section: `Files to Create/Modify` → `src/frame_compare/orchestration/coordinator.py`
   - Problem: The plan uses an ellipsis in the signature and does not provide a single one-line, backticked public signature as required by the workflow checklist.
   - Required Change: Add one backticked, single-line signature for `RunRequest(...)` listing all fields with types/defaults (matching SSOT), and explicitly state the field order to implement in `coordinator.py`.

2. **Resolve SSOT drift explicitly to avoid a coding-time STOP**
   - Section: `Spec Anchors (SSOT)` and/or `Key implementation notes`
   - Problem: `orchestration-module.md` §4.4.1 and `cli-module.md` §3.1 show different *field order* for `RunRequest`, while the plan instructs the Coding Agent to STOP on “drift”.
   - Required Change: Add a short “SSOT reconciliation” note that:
     - The authoritative implementation order for `frame_compare.orchestration.coordinator.RunRequest` is the code block in `orchestration-module.md` §4.4.1, and
     - The CLI spec must match *names/types/defaults* (order differences are non-semantic), so this is not a coding-time decision.

3. **Make tests fully explicit and cover the public export acceptance criterion**
   - Section: `tests/orchestration/test_run_request.py`
   - Problem: “assert default values for all optional/bool fields” is underspecified, and there is no explicit test/assertion for “importable from `frame_compare.orchestration`”.
   - Required Change: Update the plan to:
     - List the exact assertions for defaults (field-by-field, matching the final field list), and
     - Add a named test that asserts `from frame_compare.orchestration import RunRequest` works (or include that assertion explicitly in `test_run_request_defaults`).

## Ready for Implementation

Return to Planning Agent for revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-02-02__p6-7-5__runrequest

## Revision Required
Read file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-review-v1.md
Read file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v1.md
Write file: .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v2.md

## Hard Rules
- Add a single-line, backticked `RunRequest(...)` public signature with all fields (no ellipsis).
- Add an explicit SSOT reconciliation note: implement field order from `orchestration-module.md` §4.4.1; ensure names/types/defaults match `cli-module.md` §3.1 (order differences are non-semantic).
- Make tests explicit and include an assertion that `RunRequest` is publicly importable from `frame_compare.orchestration`.
- Spec Anchors must pass:
  `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-02-02__p6-7-5__runrequest/plan-v2.md`
