---
RUN_ID: 2026-01-04__p6-6-1__vspreview-integration
VERSION: v1
TARGET: Phase 6 → Item 6.6 (VSPreview Integration)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v3.md
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-review-v3.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/impl-v1.md
---

# Implementation Report: VSPreview Integration (Module + Manual Overrides)

## Summary

Implemented the `frame_compare.vspreview` module for optional interactive alignment verification using VSPreview. The module provides availability detection, session script generation/launch, and manual override persistence. Integrated manual override precedence in `align_clips()` and updated doctor diagnostics to use the new `is_vspreview_available()` function.

## Files Created/Modified

### Created

| File | Purpose |
|------|---------|
| `src/frame_compare/vspreview/__init__.py` | Public API exports: `ManualOverride`, `VSPreviewConfig`, `is_vspreview_available`, `launch_alignment_verification_session`, `load_manual_overrides`, `save_manual_override` |
| `src/frame_compare/vspreview/overrides.py` | `ManualOverride` dataclass, `load_manual_overrides()`, `save_manual_override()` with deterministic TOML writing |
| `src/frame_compare/vspreview/adapter.py` | `VSPreviewConfig` dataclass, `is_vspreview_available()`, `launch_alignment_verification_session()` with script generation and launch logic |
| `tests/vspreview/__init__.py` | Test package init |
| `tests/vspreview/test_overrides.py` | 13 unit tests covering availability, override loading/saving, and precedence |

### Modified

| File | Changes |
|------|---------|
| `src/frame_compare/errors.py` | Added `VSPreviewNotFoundError` (FC-2008) and `VSPreviewError` (FC-4019) |
| `src/frame_compare/services/alignment.py` | Added manual override precedence (manual > cached > computed), skip FFmpeg for overridden entries, exclude manual entries from cache |
| `src/frame_compare/orchestration/doctor.py` | Updated `_check_vspreview()` to use `is_vspreview_available()`, return `passed=True` even when missing (optional check) |
| `importlinter.ini` | Added `frame_compare.vspreview` as dedicated layer below domain modules |
| `docs/DECISIONS.md` | Added Phase 6.6 VSPreview Integration entry |
| `CHANGELOG.md` | Added VSPreview Integration entry under Unreleased |

## Implementation Details

### Error Types

```python
# FC-2008: DependencyError subclass
class VSPreviewNotFoundError(DependencyError):
    """VSPreview is not installed or available."""

# FC-4019: ProcessingError subclass
class VSPreviewError(ProcessingError):
    """VSPreview launch or runtime failure."""
```

### Availability Detection

`is_vspreview_available()` checks:

1. `shutil.which("vspreview")` returns non-None, OR
2. `importlib.util.find_spec("vspreview")` is non-None AND (`PySide6` OR `PyQt5`) is importable

### Manual Override Persistence

- File: `{cache_dir}/manual_overrides.toml`
- Version: `"1"`
- Schema: `version` key first, then sorted entry tables
- Graceful fallback: corrupt/missing/version-mismatch returns `{}` with warning

### Alignment Integration

Manual override precedence in `align_clips()`:

1. Load overrides via `load_manual_overrides(cache_dir)`
2. For each comparison with existing override: construct `AlignmentResult` with `method="manual"`, `correlation_score=1.0`
3. Skip FFmpeg audio extraction for overridden entries
4. Cache writes exclude `method="manual"` entries (cache separation)

### Import Linter Configuration

Per plan-v3, `frame_compare.vspreview` is placed on its own layer below the domain modules because import-linter's `|` separator denotes **independent siblings** that cannot import each other:

```ini
layers =
    frame_compare.cli_entry
    frame_compare.orchestration
    frame_compare.analysis | frame_compare.render | frame_compare.services
    frame_compare.vspreview   # ← Separate layer, allows services -> vspreview
    frame_compare.vs
    frame_compare.config
    frame_compare.utils
    frame_compare.errors
```

## Verification Results

| Gate | Result | Details |
|------|--------|---------|
| Pyright | ✅ PASS | 0 errors, 0 warnings, 0 informations |
| Ruff | ✅ PASS | All checks passed |
| Pytest | ✅ PASS | All tests pass (2 skipped: vs_required integration tests) |
| Import-linter | ✅ PASS | 2 contracts kept, 0 broken |

## Tests Added

| Test | Description |
|------|-------------|
| `test_is_vspreview_available_returns_true_when_executable_in_path` | vspreview in PATH → True |
| `test_is_vspreview_available_returns_true_when_importable` | vspreview + PySide6 importable → True |
| `test_is_vspreview_available_returns_true_with_pyqt5_backend` | vspreview + PyQt5 importable → True |
| `test_is_vspreview_available_returns_false_when_missing` | Nothing available → False |
| `test_is_vspreview_available_returns_false_when_no_qt_backend` | vspreview but no Qt → False |
| `test_load_manual_overrides_parses_valid_toml` | Valid TOML → dict[str, ManualOverride] |
| `test_load_manual_overrides_returns_empty_dict_on_missing_file` | No file → {} |
| `test_load_manual_overrides_returns_empty_dict_on_parse_error` | Corrupt TOML → {} |
| `test_load_manual_overrides_returns_empty_dict_on_version_mismatch` | Version mismatch → {} |
| `test_save_manual_override_creates_file_if_missing` | Creates dir/file |
| `test_save_manual_override_merges_with_existing` | Preserves other keys |
| `test_save_manual_override_overwrites_same_key` | Updates existing |
| `test_manual_override_takes_precedence_over_computed` | FFmpeg not called for overridden entries, result.method == "manual" |

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| VSPreview missing → `is_vspreview_available()` returns `False` without raising | ✅ |
| Valid `manual_overrides.toml` → correct key→ManualOverride mapping | ✅ |
| Missing/corrupt/version-mismatched file → returns `{}` (warn-only) | ✅ |
| Existing override → `save_manual_override()` overwrites deterministically | ✅ |
| Manual override exists → `align_clips()` uses override, skips FFmpeg | ✅ |
| Manual overrides not written to `audio_offsets.toml` | ✅ |
| `frame-compare doctor` → VSPreview check reports optional missing | ✅ |
| `lint-imports --config importlinter.ini` passes | ✅ |

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID

2026-01-04__p6-6-1__vspreview-integration

## Preconditions

1. Read file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-review-v3.md
   Confirm: Verdict is APPROVED.
2. Read file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/impl-v1.md

## Files to Review

1. Read file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v3.md

## Your Task

1. Confirm implementation matches plan exactly (files, types, functions, tests).
2. Run verification suite:
   - `python scripts/validate_spec_anchors.py` (if exists)
   - `.venv/bin/pyright --warnings`
   - `.venv/bin/ruff check .`
   - `.venv/bin/pytest -q`
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
   - `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
3. Update master checklist: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md` (mark Phase 6.6 items complete).
4. Update run index: `.agent-workflow/index.md` (append entry with status `PENDING_REVIEW`).

## Output

Write file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/verify-v1.md
