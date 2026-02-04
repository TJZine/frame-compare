---
RUN_ID: 2026-02-04__p6-8-3__preset
VERSION: v2
TARGET: Phase 6 → Item 6.8 (Bundled) — CLI Commands — Complete `preset` subcommands (list, apply, save) — Bundled 2 tasks
INPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v2.md
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v1.md
OUTPUTS:
  - .agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v2.md
---

# Plan Review Report: CLI `preset` subcommands + api-design option completeness

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-02-04
**Plan Reference:** `.agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v2.md`

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | FAIL | Plan still contains underspecified/incorrect behaviors for `--no-cache` / `--from-cache-only` relative to SSOT and the canonical flag meaning (“cached metrics”). |
| 2 | Dependencies | PASS | Uses existing `config`, `errors`, `preflight`, `orchestration` surfaces. |
| 3 | File List | FAIL | Plan’s global-option actions include `--no-color` reporter behavior and `--verbose` logging configuration but do not pin exact implementation wiring and may require additional file touches beyond the current file list. |
| 4 | Contract Impact | PASS | No contract edits planned. |
| 5 | Types Complete | PASS | Proposed changes are compatible with repo typing constraints. |
| 6 | Tests Complete | FAIL | Added tests cover preset + write-config/diagnose-paths/--json mappings, but cache-flag tests target probe cache rather than “cached metrics”, and `--verbose`/`--no-color` tests are not concretely defined/grounded. |
| 7 | Verification Complete | PASS | Quality gate commands listed. |
| 8 | Decision-Minimizing | FAIL | “Use an existing error type already in repo” for cache-only failures is a remaining decision point; plan must specify the exact error class and where raised. |
| 9 | Determinism Defined | PASS | `--diagnose-paths` and `--json` schemas are pinned and deterministic. |

## Additional Quality Checks

- Error Codes: **Issue** — Cache-only failure mode does not specify which existing `FrameCompareError` subtype/code is used (and therefore which exit code).
- Failure Modes: **Issue** — `--from-cache-only` semantics are not aligned to the canonical definition (“cached snapshot/metrics”) and conflict with SSOT cache interaction guidance.
- Derived Outputs: **OK** — None planned.
- Rollback Guidance: **OK** — Localized changes; revert touched modules/tests if needed.
- SSOT Update Audit (if SSOT changed this loop): **N/A** — No SSOT edits proposed.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

1. Which existing `FrameCompareError` subclass is raised for `--from-cache-only` cache-miss (and for which cache), and at what boundary (preflight vs LoadSources vs Analyze vs Align)?
2. What is the authoritative scope of “cached metrics” for `--no-cache` in this slice: analysis metrics cache (`analysis/cache_io.py`), alignment cache (`services/alignment.py`), probe cache (`orchestration/probe_cache.py`), or a subset per SSOT?
3. How exactly should `--no-color` affect progress reporter selection (Rich vs Log) without conflating “no color” with “non-interactive”?
4. Which concrete logging configuration call implements `--verbose` “debug output” (e.g., `frame_compare.utils.logging.configure_logging(level=...)`), and what is the interaction with `--json`?

## Concrete Edits Required (to approve)

1. **Align `--no-cache` / `--from-cache-only` semantics with SSOT + canonical flag meaning**
   - Section: `## CLI Option Coverage (api-design audit)` + `## Normative rules`
   - Problem: Plan defines these flags in terms of `clip_probe.toml`, but canonical `cli-flags-canonical.md` defines `--no-cache` as “Ignore cached metrics”, and SSOT orchestration cache interactions treat `clip_probe.toml` separately from metrics caches.
   - Required Change:
     - Define `--no-cache` behavior explicitly in terms of *metrics* caches that exist in code today (minimum: analysis metrics cache `cache.compframes` under `analysis/cache_io.py`; and if alignment cache `audio_offsets.toml` is in-scope, specify it too).
     - Define `--from-cache-only` behavior explicitly for those same caches: what must be present, what is forbidden to compute, and what error is raised when caches are missing.
     - If `clip_probe.toml` is included in “cached snapshot” semantics, justify with SSOT anchors and reconcile with the orchestration cache interaction table; otherwise remove probe-cache-specific semantics/tests from this slice.

2. **Pin the exact error type and exit-code behavior for cache-only failures**
   - Section: `## Normative rules` and coordinator implementation notes
   - Problem: “Use an existing error type already in repo” leaves Coding Agent with a high-impact decision (JSON error schema + exit code).
   - Required Change:
     - Specify the exact exception class(es) to raise for cache-only violations (e.g., a specific existing `ProcessingError` subtype) and where it is raised.
     - Confirm the resulting exit code via `frame_compare.errors.get_exit_code`.

3. **Make `--no-color` and `--verbose` implementation wiring concrete and consistent with file list**
   - Section: `## Normative rules` + `## Files to Create/Modify`
   - Problem: Plan promises behavior that likely requires changing reporter selection/logging config, but does not pin how or ensure the needed files are included.
   - Required Change:
     - `--verbose`: specify the exact call site and mechanism (e.g., `frame_compare.utils.logging.configure_logging(level="DEBUG", format=...)`) and define interaction with `--json`.
     - `--no-color`: specify whether it (a) disables color in Rich console error output only, (b) forces non-rich progress reporter selection, or (c) both; then list the exact functions/files that will be modified to enforce it.

4. **Update tests to match the corrected cache-flag semantics**
   - Section: `tests/orchestration/test_execute_run.py` (and/or other test files)
   - Problem: Planned tests target probe-cache behavior; they will not validate “cached metrics” semantics.
   - Required Change:
     - Replace or supplement the probe-cache tests with tests that assert `--no-cache` bypasses analysis metrics cache reads (and `--from-cache-only` fails on missing metrics cache) using monkeypatching to avoid VS/FFmpeg.
     - If alignment caching is included, add a corresponding test asserting `--no-cache` bypasses `audio_offsets.toml` reads/writes.

## Ready for Implementation

Return to Planning Agent for revision (`plan-v3.md`). Coding Agent must not proceed until verdict is APPROVED and Implementation Agent Decision Points Remaining is NONE.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Coding Agent for Frame Compare 2.0.

## RUN_ID
2026-02-04__p6-8-3__preset

## Precondition
Read file: `.agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v2.md`
Confirm: Verdict is APPROVED and Implementation Agent Decision Points Remaining is NONE.
If not, STOP and request a revised plan + plan review.

## Files to Read
1. `.agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-v2.md`
2. `.agent-workflow/runs/2026-02-04__p6-8-3__preset/plan-review-v2.md`

## Output
Write file: `.agent-workflow/runs/2026-02-04__p6-8-3__preset/impl-v1.md`

## STOP CONDITIONS (Hard)
- If verdict != APPROVED or Implementation Agent Decision Points Remaining != NONE, do not proceed.
