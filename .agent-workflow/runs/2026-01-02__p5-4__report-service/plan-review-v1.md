---
RUN_ID: 2026-01-02__p5-4__report-service
VERSION: v1
TARGET: Phase 5 → Item 5.4 (Report Generator)
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-review-v1.md
---

# Plan Review Report: Report Generator Service

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-02
**Plan Reference:** .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v1.md

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | PASS | Single slice: `frame_compare.services.report` report generation. |
| 2 | Dependencies | PASS | Dependencies and import targets are explicit and match module specs. |
| 3 | File List | PASS | File set is explicit (service, exports, tests, DECISIONS, CHANGELOG). |
| 4 | Contract Impact | PASS | Contracts not touched; plan includes `lint-imports` gate. |
| 5 | Types Complete | FAIL | Public function signature is present but not listed as required one-line backticked signature(s) for mechanical coverage checks. |
| 6 | Tests Complete | FAIL | Test count is inconsistent, and failure-path coverage is missing for SSOT-listed errors (missing screenshot, encode/read failure, write failure) plus deterministic ordering / JSON payload assertions. |
| 7 | Verification Complete | PASS | Commands + pass criteria are explicit. |
| 8 | Decision-Minimizing | FAIL | Determinism/ordering guidance conflicts with SSOT (sorting is a new decision) and output-path fallback selection is underspecified. |
| 9 | Determinism Defined | FAIL | Ordering rules and deterministic “first screenshot” selection aren’t fully specified/tested. |

## Additional Quality Checks

- Error Codes: OK (uses existing `ReportError` / FC-4017; no new errors introduced)
- Failure Modes: Issue (SSOT + plan do not fully specify behavior for screenshot mapping/length invariants and output-path fallback when screenshots are malformed)
- Derived Outputs: OK (no generated contract views involved)
- Rollback Guidance: OK (no risky migrations/contracts; plan revision is sufficient)
- SSOT Update Audit (this loop): Issue (new SSOT doc is implementable overall, but needs clarifications below; additionally, it currently conflicts with `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/data-contracts.md` report sections)

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Whether to sort clips/screenshots vs preserve SSOT iteration order (affects UI ordering and reproducibility).
2. Exactly which screenshot is considered “first screenshot” for determining default output directory.
3. How to handle malformed `ReportData.screenshots` shapes (missing clip keys / empty lists / length mismatch) without raising raw `KeyError`/`IndexError`.
4. Which SSOT governs report filename/version/JSON schema (`report-viewer-spec.md` vs `data-contracts.md`), and which must be updated to remove conflicts.

## Concrete Edits Required (CHANGES REQUIRED)

1. **Clarify SSOT validation + output-path fallback (blocking)**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md` → `### 9.1 Generation Errors`, `## 11. Generation Algorithm`
   - Problem: SSOT defines some errors, but leaves malformed screenshot-mapping invariants and “first screenshot” selection ambiguous, forcing implementation decisions.
   - Required Change:
     - Add explicit validation requirements for:
       - `len(data.frames) == 0` (must raise `ReportError("no screenshots provided")`)
       - Screenshot mapping missing/empty/mismatched length (must raise `ReportError("no screenshots provided")`)
     - Make output-path fallback deterministic by specifying the exact screenshot used for parent directory selection (e.g., first clip in `data.clips` and first frame index).

2. **Make public API mechanically checkable**
   - Section: Plan → `## Spec Anchors (SSOT)` (or a nearby “Public API” subsection)
   - Problem: Plan does not list public function signatures in the required one-line, backticked form.
   - Required Change: Add:
     - `- \`generate_report(data: ReportData, config: ReportConfig, output_path: Path | None = None) -> Path\``

3. **Fill test gaps and remove inconsistencies**
   - Section: Plan → `tests/services/test_report.py` test matrix
   - Problem: Table says “22 total” but lists more; missing tests for SSOT error conditions and JSON payload determinism/shape.
   - Required Change:
     - Fix the stated test count to match the listed tests (and the revised set).
     - Add explicit unit tests (names + assertions) for:
       - Missing screenshot file → `ReportError("screenshot not found: {path}")`
       - Image read/encode failure when `embed_images=True` → `ReportError("failed to encode image: {path}")` (use `monkeypatch` to raise from `Path.read_bytes`)
       - Write failure → `ReportError("failed to write report: {reason}")` (use `monkeypatch` to raise from `Path.write_text`)
       - Embedded JSON payload contains required keys (`version`, `generated_at`, `default_mode`, `clips`, `frames`) and preserves deterministic ordering (clips order from `data.clips`, frames order from `data.frames`, per-frame images order aligned to clips)

4. **Remove/replace sorting directive**
   - Section: Plan → “Notes for Coding Agent” item 10
   - Problem: “Sort clips and screenshots” is not specified in SSOT and changes semantics (UI order).
   - Required Change: Replace with SSOT-aligned determinism rule: preserve `data.clips` and `data.frames` ordering and do not iterate dict order (use `data.clips` to index into `data.screenshots`).

5. **Resolve SSOT conflict with Data Contracts (blocking)**
   - Section: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/data-contracts.md` → `## 3. Report HTML Structure`, `## 4. Report JSON Payload`
   - Problem: `data-contracts.md` specifies `{output_dir}/comparison_report.html`, schema version `"2.0"`, and a different JSON payload shape than `report-viewer-spec.md` (`report.html`, version `"1.0"`, `EmbeddedData`).
   - Required Change (no alternatives): Mark these v2 sections as **future / not implemented in Phase 5.4**, and explicitly state that **Phase 5.4 is governed by** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md` (HTML + embedded JSON). This must remove any ambiguity about what the Coding Agent should implement.

## Ready for Implementation

Return to Planning Agent for SSOT clarification + plan revision. Next version: `plan-v2.md`.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-4__report-service

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md
- Under heading: "### 9.1 Generation Errors" add/change:
  - Add condition: `len(data.frames) == 0` → `ReportError("no screenshots provided")`
  - Add condition: screenshots mapping invalid (missing clip key, any screenshot list empty, or any list length != `len(data.frames)`) → `ReportError("no screenshots provided")`
- Under heading: "## 11. Generation Algorithm" add/change:
  - Step 1 (VALIDATE INPUT): include the same frames/screenshots mapping validation as above
  - Step 2c (DETERMINE OUTPUT PATH): replace “first screenshot's parent” with a deterministic selection rule (first clip in `data.clips` and first frame index)

Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/data-contracts.md
- Under heading: "## 3. Report HTML Structure" add/change:
  - Add an explicit note that this v2 contract is **future / not implemented in Phase 5.4**, and that Phase 5.4’s report HTML structure is defined in `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md`.
- Under heading: "## 4. Report JSON Payload" add/change:
  - Add an explicit note that this v2 contract is **future / not implemented in Phase 5.4**, and that Phase 5.4’s embedded JSON payload shape is defined in `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/report-viewer-spec.md` (EmbeddedData).

## Then Revise the Plan (do not fix in-plan)
Read file: .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-review-v1.md
Read file: .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v1.md
Write file: .agent-workflow/runs/2026-01-02__p5-4__report-service/plan-v2.md

## Hard Rules
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not add missing SSOT requirements into the plan; update SSOT and re-anchor.
