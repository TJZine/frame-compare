# Test Suite Cleanup Closure Ledger

Controller-owned live ledger for the cleanup based on the refreshed audit at
`2ed0cf3`. Baseline: 2,197 tests collected on 2026-07-10.

Allowed terminal statuses: `implemented`, `already implemented`,
`superseded by current architecture`, `keep: production contract`,
`deferred with explicit audit authority`, `blocked`.

## Current audit

| Entry | Scope | Status |
| --- | --- | --- |
| NEW-001 | Empty placeholder modules | implemented |
| NEW-002 | Report entry duplication | implemented |
| NEW-003 | Report filmstrip/assets/mode duplication | implemented |
| NEW-004 | CLI output duplication | implemented |
| NEW-005 | Report-open policy duplication | implemented |
| NEW-006 | VSPreview availability duplication | implemented |
| NEW-007 | DTO/protocol smoke tests | implemented |
| NEW-008 | Duplicate metrics cache-key tests | implemented |
| NEW-009 | Best-effort cache-save choreography | implemented |
| NEW-010 | Metrics import-boundary proof | implemented |
| NEW-011 | FPS diagnostics and benchmark progress prose | implemented |
| NEW-012 | Phase task/output owner split | implemented |
| NEW-013 | Preparation owner split | implemented |
| NEW-014 | Render expansion responsibility split | implemented |
| NEW-015 | Metrics strategy/orchestration split | implemented |
| NEW-016 | Alignment workflow owner split | implemented |
| NEW-017 | Cache I/O contract split | implemented |
| NEW-018 | Execute-run run-folder owner split | implemented |
| NEW-019 | Benchmark tooling split | implemented |
| NEW-020 | Run command owner split | implemented |
| NEW-021 | CLI contract docs split | implemented |
| NEW-022 | Viewer state harness split | deferred with explicit audit authority |

## Cleanup packages and waves

| Entry | Scope | Status |
| --- | --- | --- |
| Package A | NEW-002, NEW-003 | implemented |
| Package B | NEW-004, NEW-005, NEW-020 | implemented |
| Package C | NEW-008 through NEW-011, NEW-015, NEW-019 | implemented |
| Package D | NEW-001, NEW-007 | implemented |
| Package E | NEW-006 | implemented |
| Structural wave 1 | NEW-012 through NEW-015 | implemented |
| Structural wave 2 | NEW-016 through NEW-019 | implemented |
| Structural wave 3 | NEW-018, NEW-021, NEW-022, old-audit reconciliation | deferred with explicit audit authority |

## Superseded audit

| Entry | Historical subject | Status |
| --- | --- | --- |
| TSO-001 | API docs CLI drift output | keep: production contract |
| TSO-002 | API docs rendering/order | keep: production contract |
| TSO-003 | Rich literal-bracket error rendering | keep: production contract |
| TSO-004 | Traceability exact-def behavior/dead scaffold constant | implemented |
| TSO-005 | Execute-run skipped phase timings | already implemented |
| TSO-006 | Progress selection force_tty default | already implemented |
| TSO-007 | Alignment request owner seam | keep: production contract |
| TSO-008 | Alignment report Rich prose | keep: production contract |
| TSO-009 | FPS report exhaustive log payload | implemented |
| TSO-010 | Alignment workflow progress choreography | already implemented |
| TSO-011 | Alignment reuse prompt glyph/width | already implemented |
| TSO-012 | Alignment VSPreview prompt wording | already implemented |
| TSO-013 | Viewer JS source-order contracts | deferred with explicit audit authority |
| TSO-014 | Viewer persisted-state field duplication | keep: production contract |
| TSO-015 | Viewer harness aggregate summary | deferred with explicit audit authority |
| TSO-016 | Decorative viewer CSS assertions | implemented |
| TSO-017 | Metadata parser call ordering | already implemented |
| TSO-018 | TMDB bounded concurrency | keep: production contract |
| TSO-019 | VSPreview path escaping | keep: production contract |
| TSO-020 | VSPreview overlay warning source snapshot | already implemented |
| TSO-021 | VSPreview stream helper source snapshot | already implemented |
| TSO-022 | VSPreview lsmas/lw source ordering | already implemented |
| TSO-023 | VSPreview output prose/order snapshots | already implemented |
| TSO-024 | VSPreview bootstrap/section snapshots | implemented |
| TSO-025 | VSPreview atomic write/collision | keep: production contract |
| TSO-026 | Windows update/release script contracts | keep: production contract |
| TSO-027 | Windows shim precedence/dot-sourcing | keep: production contract |
| TSO-028 | Windows install-path positional order | already implemented |
| TSO-029 | Windows absolute PowerShell fallbacks | keep: production contract |
| TSO-030 | Opt-in live slow.pics canary | keep: production contract |
| TSO-031 | Progress reporter private-state tests | superseded by current architecture |
| TSO-032 | Report renderer markup snapshots | already implemented |
| TSO-033 | Duplicate report clip-option HTML | already implemented |
| TSO-034 | Output-phase helper/log exactness | implemented |
| TSO-035 | Duplicate stale report-path clearing | already implemented |
| TSO-036 | Render geometry/encoder internals | superseded by current architecture |

## Former Package R1 and named residuals

| Entry | Scope | Status |
| --- | --- | --- |
| R1-FPS | Required-key subset for internal FPS diagnostic rows | implemented |
| R1-BENCH | Relax benchmark progress prose; preserve counts/completion | implemented |
| RES-SCAFFOLD | Remove unused `scripts/validate_traceability.py::SCAFFOLD_TESTS_DIR` | implemented |
| RES-CSS | Remove decorative filmstrip `linear-gradient` assertion if still non-contractual | implemented |
| RES-VSPREVIEW | Remove stale `test_build_script_content_assert_by_section` snapshot | implemented |
| RES-THEME | Treat historical `docs/DECISIONS.md` theme value as historical | superseded by current architecture |

## Verification record

- Primary mode: `refactor-invariance`.
- Classification: existing focused coverage is sufficient for deletions,
  consolidation, and moves; add/replace tests only for a real owner/public
  contract.
- Baseline collection: `.venv/bin/pytest -o addopts='' --collect-only -q` ->
  2,197 tests collected.
- Final collection: 2,155 tests (raw baseline delta: -42; cleanup-attributable
  delta: -61, offset by 19 tests from independently landed commit `556e8993`).
- `.venv/bin/pyright --warnings`: 0 errors, 0 warnings.
- `.venv/bin/ruff check .`: passed.
- `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`:
  2 contracts kept, 0 broken.
- `.venv/bin/bandit -c pyproject.toml -r src --severity-level medium`:
  no medium/high issues.
- `.venv/bin/pytest -q`: 2,136 passed, 19 honest environment skips.
- `git diff --check`: passed.
- Reviewer: no blocking/high or code findings. Accepted the ledger-only medium
  correction for TSO-013, TSO-015, and TSO-031.
