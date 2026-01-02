---
RUN_ID: 2026-01-02__p5-2__metadata-service
VERSION: v1
TARGET: Phase 5 → Item 5.2
INPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/verify-v1.md
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/impl-v1.md
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__p5-2__metadata-service/review-v1.md
  - .agent-workflow/index.md (updated)
---

# Review Report: Metadata Service

## Verdict: DESIGN ISSUE

## Review Summary
**Reviewer:** Review Agent
**Date:** 2026-01-02
**Files Reviewed:** 11
**Commit Subject:** `feat(services): add metadata parsing and TMDB lookup`

> [!NOTE]
> The commit subject must summarize the entire checklist item, not just the review phase.

## Process Gates
- [x] Plan was approved by Plan Review Agent
- [x] Verification handoff complete
- [x] All verification gate outputs included
- [x] Run index updated with final verdict

## Quality Check Results

```text
$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md
OK: Spec Anchors valid for .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md

$ .venv/bin/pyright --warnings
0 errors, 0 warnings, 0 informations

$ .venv/bin/ruff check .
All checks passed!

$ .venv/bin/pytest --cov -q --ignore tests/vs/
302 passed, 1 skipped
Required test coverage of 80.0% reached. Total coverage: 82.90%

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
Contracts: 2 kept, 0 broken.

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
OK: All derived files are up-to-date

$ UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
✅ All traceability references valid
```

## Files Reviewed
- .agent-workflow/runs/2026-01-02__p5-2__metadata-service/verify-v1.md
- .agent-workflow/runs/2026-01-02__p5-2__metadata-service/impl-v1.md
- .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md
- .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-review-v4.md
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
- src/frame_compare/services/metadata.py
- src/frame_compare/services/types.py
- src/frame_compare/services/__init__.py
- tests/services/test_metadata.py
- pyproject.toml
- docs/DECISIONS.md

## Checklist Results

### Correctness

- [x] Implements most acceptance criteria
- [ ] Issue: parse_filename can raise exceptions despite SSOT promise
- [ ] Issue: SSOT expects source normalization to "BluRay" but parser returns "Blu-ray"; intended behavior needs SSOT update

### Type Safety

- [x] Type hints complete
- [x] Pyright passes

### Error Handling

- [x] Error hierarchy used
- [x] Errors have codes and hints

### Testing

- [x] Unit tests cover parsing and TMDB flows
- [x] Coverage gate passed

### Documentation

- [x] Decisions recorded for parser strategy and _search_tmdb helper

### Security

- [x] No issues found

### Performance

- [x] No concerns

## Issues Found

### Critical (Must Fix)

1. **SSOT update required for source normalization (spec mismatch)**
   - Location: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` and `.agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md`
   - Issue: The plan/test expectation requires `source == "BluRay"`, but the underlying parser returns "Blu-ray". This is an intended behavior decision, so SSOT must be updated to declare the canonical format rather than normalizing to satisfy a test.
   - Fix: Update SSOT to define the canonical `source` representation for parser outputs (accept "Blu-ray"), then revise the plan/tests to match. This is a design/spec change and requires Planning + Plan Review.

2. **parse_filename does not honor “never raises” contract**
   - Location: `src/frame_compare/services/metadata.py:57` and `src/frame_compare/services/metadata.py:61`
   - Issue: Both GuessIt and Anitopy calls are unguarded. If either library raises (malformed input, internal error), `parse_filename` will propagate, violating the SSOT contract “always returns, never raises.”
   - Fix: Wrap parser calls in try/except and return `{}` on exceptions (or guard each parser invocation in the loop) so `parse_filename` always returns a `ParsedMetadata`.

### Suggestions (Nice to Have)

None.

## Acceptance Criteria Verification

- [x] GIVEN a western movie filename WHEN `parse_filename` is called THEN returns `ParsedMetadata` with normalized title — ✓ Verified
- [ ] GIVEN an anime filename starting with `[` WHEN `parse_filename` is called THEN Anitopy is used first — ⚠️ Not fully verified due to missing parser error guards
- [x] GIVEN `api_key=None` WHEN `lookup_tmdb` is called THEN returns `None` without HTTP request — ✓ Verified
- [x] GIVEN invalid API key format WHEN `lookup_tmdb` is called THEN raises `TmdbError` — ✓ Verified
- [x] GIVEN multiple TMDB results and no callback WHEN `resolve_metadata` is called THEN returns first result — ✓ Verified
- [x] GIVEN invalid callback index WHEN `resolve_metadata` is called THEN raises `MetadataError` — ✓ Verified

## Next Steps

### If DESIGN ISSUE

- Planning Agent: Revise the plan after updating SSOT to define the canonical `source` output (accept "Blu-ray"), then re-run Plan Review.
- Coding Agent: After plan approval, implement guardrails so `parse_filename` never raises.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__p5-2__metadata-service

## Design Issue Identified
Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/review-v1.md
See "Issues Found > Critical" section for the design problem description.

## Previous Plan
Read file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v4.md

## Affected Contracts/Specs
- docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md

## Your Task
Revise the implementation plan to define the canonical `source` output (accept "Blu-ray") and align tests accordingly.
If contracts need updating, include the contract changes in the plan.

## Output
Write file: .agent-workflow/runs/2026-01-02__p5-2__metadata-service/plan-v5.md
