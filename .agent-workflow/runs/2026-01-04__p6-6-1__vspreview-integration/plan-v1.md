---
RUN_ID: 2026-01-04__p6-6-1__vspreview-integration
VERSION: v1
TARGET: Phase 6 → Item 6.6 (VSPreview Integration)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v1.md
---

# Implementation Plan: VSPreview Integration (Module + Manual Overrides)

## Context
**Phase:** 6
**Module:** `frame_compare.vspreview`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md`
**Dependencies:**
- Existing alignment cache implementation in `src/frame_compare/services/alignment.py`
- Error hierarchy in `src/frame_compare/errors.py`
- Layering gate in `importlinter.ini`

## Scope
This plan covers:
- [ ] Implement `frame_compare.vspreview` module (availability check, script generation, launch wrapper)
- [ ] Implement manual override persistence (`manual_overrides.toml`) with failure-tolerant loading
- [ ] Apply manual override precedence over computed/cached offsets in `frame_compare.services.alignment.align_clips`
- [ ] Add unit tests (no GUI / no VSPreview required) per vspreview spec §8.1
- [ ] Update `importlinter.ini` to include `frame_compare.vspreview` in the layered architecture contract

This plan does NOT cover:
- Runner/orchestration pipeline wiring (`src/frame_compare/runner.py`, `RunRequest`, phase orchestration) — see Phase 6.7
- Interactive CLI prompt workflow after VSPreview exit (confirm/adjust offsets) — requires Runner/CLI implementation per specs
- Integration tests requiring display / VSPreview / VapourSynth (must remain skipped/marker-gated)

## Contract Impact
**Contracts touched:** NO

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md`:
  - Section: "3. Public API"
  - Section: "3.1 Availability Check"
  - Section: "3.2 Launch Session for Verification (All Comparisons)"
  - Section: "3.2.1 Overlay + Confirmation Contract (Required)"
  - Section: "3.2.2 Script Generation Requirements (Legacy-Proven)"
  - Section: "3.2.3 Launch + Telemetry Contract (Fragility Hardened)"
  - Section: "3.3 Override Persistence"
  - Section: "5. Cache Schema"
  - Section: "8. Testing Strategy"
  - Section: "9. Error Handling"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md`:
  - Section: "2.2 Public API"
  - Section: "2.4 VSPreview Integration and Manual Overrides (Deterministic Contract)"
  - Section: "2.5 Trim-First Normalization (Positive-Only Applied Trims) (SSOT)"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`:
  - Section: "2. CLI Entry Point"

## Files to Create/Modify

### 1. `src/frame_compare/vspreview/__init__.py`
**Purpose:** Public exports for the VSPreview integration module.

**Types to export:**
- `ManualOverride` — user-provided signed relative offset record
- `VSPreviewConfig` — adapter configuration for session launch behavior

**Functions to export (spec-anchored):**
- `is_vspreview_available() -> bool`
- `launch_alignment_verification_session(reference: Path, comparisons: list[Path], suggested_offsets_by_key: dict[str, int], cache_dir: Path, config: VSPreviewConfig) -> Path`
- `load_manual_overrides(cache_dir: Path) -> dict[str, ManualOverride]`
- `save_manual_override(cache_dir: Path, override: ManualOverride) -> None`

### 2. `src/frame_compare/vspreview/overrides.py`
**Purpose:** Manual override cache schema + persistence helpers for `{cache_dir}/manual_overrides.toml`.

**Types to define (spec-anchored):**
- `ManualOverride` — dataclass exactly as defined in vspreview spec §2.1

**Functions to implement (spec-anchored):**
- `load_manual_overrides(cache_dir: Path) -> dict[str, ManualOverride]`
  - Behavior per vspreview spec §3.3 / §5.2: return `{}` on missing file, TOML parse error, or version mismatch (warn-only).
- `save_manual_override(cache_dir: Path, override: ManualOverride) -> None`
  - Behavior per vspreview spec §3.3: create file if missing; merge; overwrite same key.

**Determinism requirement:**
- Writes must be stable: `version` first, then entry tables in sorted key order, with stable field ordering inside each table.

### 3. `src/frame_compare/vspreview/adapter.py`
**Purpose:** VSPreview availability detection and session script generation/launch wrapper.

**Types to define (spec-anchored):**
- `VSPreviewConfig` — dataclass as defined in vspreview spec §2.2

**Functions to implement (spec-anchored):**
- `is_vspreview_available() -> bool`
  - Availability rules per vspreview spec §3.1 / §6.3:
    - Return `True` if either:
      - `vspreview` executable is in `PATH`, OR
      - `vspreview` module is importable AND a Qt backend (`PySide6` or `PyQt5`) is importable.
- `launch_alignment_verification_session(reference: Path, comparisons: list[Path], suggested_offsets_by_key: dict[str, int], cache_dir: Path, config: VSPreviewConfig) -> Path`
  - Behavior per vspreview spec §3.2:
    - Always generate and persist the script under `{cache_dir}/vspreview_sessions/` and return the script path.
    - Implement script content requirements per §3.2.2:
      - self-contained (no arg parsing), stable dict literals, sys.path bootstrap, safe_print, UTF-8 stdout/stderr reconfigure best-effort.
      - slot layout: reference repeated on even slots; comparisons on odd.
      - FPS harmonization (preview-only): apply `AssumeFPS` (or equivalent) so comparisons scrub at reference FPS.
      - pairwise trim application per signed relative offset (for preview ergonomics):
        - `frame_offset > 0` → trim comparison start by `frame_offset` frames
        - `frame_offset < 0` → trim the paired reference start by `-frame_offset` frames (using per-comparison reference slot)
      - overlays best-effort per §3.2.1 / §3.2.2 (warn + continue if overlay plugin missing).
    - Launch behavior per §3.2.3 / §6.3:
      - Resolve command as either `vspreview {script}` (preferred) or `{sys.executable} -m vspreview {script}`.
      - If VSPreview is unavailable at invocation: raise `VSPreviewNotFoundError` (v1 error surface; see §9).
      - If `stdin` is not a TTY: do not launch; return script path only (orchestration will message/warn later).
      - If launch fails (non-zero exit or subprocess failure): raise `VSPreviewError` with actionable details.

### 4. `src/frame_compare/errors.py`
**Purpose:** Add VSPreview error types referenced by vspreview spec.

**Types to define (spec-anchored):**
- `VSPreviewNotFoundError` — FC-2008 (DependencyError)
- `VSPreviewError` — FC-4019 (ProcessingError)

**Spec anchor:** vspreview spec §9 defines class names + codes; implementation must follow existing `ErrorContext` patterns in `src/frame_compare/errors.py`.

### 5. `src/frame_compare/services/alignment.py`
**Purpose:** Apply manual override precedence and preserve cache separation.

**Changes required (spec-anchored):**
- Load `{cache_dir}/manual_overrides.toml` via `frame_compare.vspreview.overrides.load_manual_overrides()` and apply precedence from services spec §2.4.
- Manual overrides MUST take precedence over cache and computed results.
- Manual overrides MUST NOT be written to `audio_offsets.toml` (cache separation per services spec §2.4).

**Behavioral details (deterministic):**
- If a manual override exists for `{reference.stem}:{comparison.stem}`:
  - result uses `method="manual"`
  - `frame_offset` is the override’s signed relative offset
  - `time_offset_seconds` is derived from reference FPS (`frame_offset / fps`) with a single `_probe_fps(reference)` call for the run
- Cache results remain computed-only (`method="cross_correlation"`) and only computed results are written.

### 6. `tests/vspreview/test_overrides.py`
**Purpose:** Unit tests for vspreview module (no GUI required).

**Tests required (spec-anchored, vspreview spec §8.1):**
- `test_is_vspreview_available_returns_true_when_importable`
- `test_is_vspreview_available_returns_false_when_missing` (mock `find_spec` to return None)
- `test_load_manual_overrides_parses_valid_toml`
- `test_load_manual_overrides_returns_empty_dict_on_missing_file`
- `test_load_manual_overrides_returns_empty_dict_on_parse_error`
- `test_load_manual_overrides_returns_empty_dict_on_version_mismatch`
- `test_save_manual_override_creates_file_if_missing`
- `test_save_manual_override_merges_with_existing`
- `test_save_manual_override_overwrites_same_key`
- `test_manual_override_takes_precedence_over_computed`
  - Validate services spec §2.4 precedence by patching `frame_compare.services.alignment.load_cached_offsets` and
    ensuring `align_clips()` returns a manual-method `AlignmentResult` for overridden keys without calling audio extraction.

### 7. `importlinter.ini` (MODIFY)
**Purpose:** Keep `lint-imports` deterministic by placing `frame_compare.vspreview` into the layered architecture contract.

**Change:**
- Add `frame_compare.vspreview` to the domain layer line:
  - `frame_compare.analysis | frame_compare.render | frame_compare.services | frame_compare.vspreview`

## Acceptance Criteria

- [ ] GIVEN VSPreview is missing WHEN calling `is_vspreview_available()` THEN it returns `False` without raising
- [ ] GIVEN valid `manual_overrides.toml` WHEN calling `load_manual_overrides()` THEN it returns the expected key→ManualOverride mapping
- [ ] GIVEN missing/corrupt/version-mismatched `manual_overrides.toml` WHEN calling `load_manual_overrides()` THEN it returns `{}` (warn-only)
- [ ] GIVEN an existing override for a clip pair WHEN calling `save_manual_override()` THEN the stored entry is overwritten deterministically
- [ ] GIVEN computed/cached offsets exist WHEN a manual override exists THEN `align_clips()` returns manual override results for those keys
- [ ] GIVEN manual overrides exist THEN `audio_offsets.toml` is not modified with manual entries
- [ ] GIVEN the repo import gates run THEN `lint-imports --config importlinter.ini` passes with the new module present

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` → **Command Canon**.

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All commands exit 0 with no errors or warnings.

## Notes for Coding Agent

- Do not add any tests that require a display server, VapourSynth, FFmpeg, or VSPreview; keep this slice unit-test-only.
- Keep the VSPreview script generator deterministic (stable content; timestamp only in filename).
- Ensure cache separation: manual overrides live only in `manual_overrides.toml`; computed offsets remain in `audio_offsets.toml`.
- Use existing structlog patterns for warnings in cache loaders (warn-only behavior).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-6-1__vspreview-integration

## Plan to Review
Read file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v1.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-review-v1.md
