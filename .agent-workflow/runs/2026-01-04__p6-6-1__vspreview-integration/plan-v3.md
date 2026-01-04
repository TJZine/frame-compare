---
RUN_ID: 2026-01-04__p6-6-1__vspreview-integration
VERSION: v3
TARGET: Phase 6 → Item 6.6 (VSPreview Integration)
INPUTS:
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v2.md
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-review-v2.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v3.md
---

# Implementation Plan: VSPreview Integration (Module + Manual Overrides)

## Changes Since plan-v2

- Corrected `importlinter.ini` update to reflect import-linter layer semantics:
  - `|` denotes **independent** siblings within a layer (no imports between siblings), so placing `frame_compare.vspreview` in the same `analysis | render | services` layer would forbid the required `services -> vspreview` import.
  - Plan now places `frame_compare.vspreview` on its own layer immediately below the domain layer, and leaves `domain-independence` unchanged (does not include `vspreview`).

## Context
**Phase:** 6
**Module:** `frame_compare.vspreview`
**Spec Reference:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md`
**Dependencies:**
- Existing alignment implementation in `src/frame_compare/services/alignment.py`
- Existing doctor implementation in `src/frame_compare/orchestration/doctor.py`
- Error hierarchy in `src/frame_compare/errors.py`
- Layering gate in `importlinter.ini`

## Scope
This plan covers:
- [ ] Implement `frame_compare.vspreview` module (availability check, script generation, launch wrapper, override persistence)
- [ ] Apply manual override precedence over computed/cached offsets in `frame_compare.services.alignment.align_clips`
- [ ] Update `src/frame_compare/orchestration/doctor.py` to report VSPreview availability via `frame_compare.vspreview.is_vspreview_available()`
- [ ] Add unit tests (no GUI / no external binaries / no VSPreview required) per vspreview spec §8.1, with deterministic mocking
- [ ] Update `importlinter.ini` to add `frame_compare.vspreview` as a separate layer below domain modules so `frame_compare.services` may import it

This plan does NOT cover:
- Runner/orchestration pipeline wiring (`src/frame_compare/runner.py`, `RunRequest`, phase orchestration) — see Phase 6.7
- Interactive CLI prompt workflow after VSPreview exits (confirm/adjust offsets) — requires Runner/CLI implementation per specs
- JSON output payload shaping for `vspreview_offer` (vspreview spec §3.2.3) — deferred to CLI/Runner work
- Integration tests requiring display / VSPreview / VapourSynth / FFmpeg (must remain skipped/marker-gated)

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
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md`:
  - Section: "3.2 Dependency Errors (FC-2xxx) — Exit Code 3"
  - Section: "3.4 Processing Errors (FC-4xxx) — Exit Code 5"
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
    - Return `True` if `shutil.which("vspreview")` is non-None, OR
    - `importlib.util.find_spec("vspreview")` is non-None AND (`find_spec("PySide6")` OR `find_spec("PyQt5")`) is non-None.
- `launch_alignment_verification_session(reference: Path, comparisons: list[Path], suggested_offsets_by_key: dict[str, int], cache_dir: Path, config: VSPreviewConfig) -> Path`
  - Deterministic behavior per vspreview spec §3.2 / §3.2.2:
    - Always generate and persist the script under `{cache_dir}/vspreview_sessions/` (created if missing).
    - Filename timestamp format MUST match vspreview spec §3.2.2 (`YYYYMMDDTHHMMSSZ` UTC, seconds precision) and MUST NOT be embedded in script content.
  - `config.enabled` behavior per vspreview spec §3.2:
    - If `config.enabled` is `False`, return the generated script path without resolving or launching VSPreview and without raising.
  - Launch telemetry ownership (to satisfy vspreview spec §3.2.3 in the absence of Runner/CLI wiring):
    - `launch_alignment_verification_session` MUST print (to stdout) the generated script path and the resolved copy/paste launch command before attempting launch.
    - The resolved command MUST follow vspreview spec §6.3 priority:
      1) if `vspreview` executable exists in PATH: `vspreview {script_path}`
      2) else: `{sys.executable} -m vspreview {script_path}` (only after `vspreview` is importable and a Qt backend is importable)
  - TTY gating per vspreview spec §3.2.3:
    - If `stdin` is not a TTY, do not launch; return the generated script path.
  - Error surface per vspreview spec §9:
    - If `config.enabled` is `True` and a launch is attempted but VSPreview is not available, raise `VSPreviewNotFoundError`.
    - If launch is attempted and fails (subprocess failure / non-zero exit), raise `VSPreviewError` with details that include return code and stderr/stdout snippets.

### 4. `src/frame_compare/errors.py`
**Purpose:** Add VSPreview error types required by vspreview spec §9 and errors-module SSOT.

**Types to define (spec-anchored):**
- `VSPreviewNotFoundError` — FC-2008 (DependencyError), `ErrorContext.name="VSPREVIEW_NOT_FOUND"`
- `VSPreviewError` — FC-4019 (ProcessingError), `ErrorContext.name="VSPREVIEW_ERROR"`

### 5. `src/frame_compare/orchestration/doctor.py` (MODIFY)
**Purpose:** Ensure doctor reporting for VSPreview matches vspreview spec §6.1 and avoids direct `__import__("vspreview")` probing.

**Changes required (spec-anchored):**
- Update `_check_vspreview()` to call `frame_compare.vspreview.is_vspreview_available()`.
- When VSPreview is missing, return a non-failing optional check result consistent with vspreview spec §6.1 (passed=True, message indicates optional missing, hint gives install guidance).

### 6. `src/frame_compare/services/alignment.py`
**Purpose:** Apply manual override precedence and preserve cache separation.

**Changes required (spec-anchored):**
- Load `{cache_dir}/manual_overrides.toml` via `frame_compare.vspreview.load_manual_overrides()` and apply precedence from services spec §2.4.
- Manual overrides MUST take precedence over cache and computed results.
- Manual overrides MUST NOT be written to `audio_offsets.toml` (cache separation per services spec §2.4).

**Behavioral details (deterministic):**
- When a manual override exists for `{reference.stem}:{comparison.stem}`, construct `AlignmentResult` per services spec §2.4 (including `method="manual"`, `correlation_score=1.0`, and `time_offset_seconds` derived from reference FPS).
- Manual override short-circuits audio extraction for that comparison (no FFmpeg call for overridden entries).

### 7. `tests/vspreview/test_overrides.py`
**Purpose:** Unit tests for vspreview module (no GUI required).

**Tests required (spec-anchored, vspreview spec §8.1):**
- `test_is_vspreview_available_returns_true_when_importable`
  - Patch `shutil.which` to return `None`
  - Patch `importlib.util.find_spec` to return non-None for `vspreview` and for one backend (`PySide6` or `PyQt5`)
- `test_is_vspreview_available_returns_false_when_missing`
  - Patch BOTH `shutil.which` to return `None` AND `importlib.util.find_spec` to return `None` for `vspreview`
- `test_load_manual_overrides_parses_valid_toml`
- `test_load_manual_overrides_returns_empty_dict_on_missing_file`
- `test_load_manual_overrides_returns_empty_dict_on_parse_error`
- `test_load_manual_overrides_returns_empty_dict_on_version_mismatch`
- `test_save_manual_override_creates_file_if_missing`
- `test_save_manual_override_merges_with_existing`
- `test_save_manual_override_overwrites_same_key`
- `test_manual_override_takes_precedence_over_computed`
  - Patch `frame_compare.vspreview.load_manual_overrides` to return an override for one comparison key.
  - Patch `frame_compare.services.alignment.load_cached_offsets` to return a cached computed result for the same key.
  - Patch `frame_compare.services.alignment._extract_audio` to raise if called (proves FFmpeg is not invoked).
  - Patch `frame_compare.services.alignment._probe_fps` to a known `Fraction` and assert it is called at most once.
  - Assert returned `AlignmentResult.method == "manual"` and `frame_offset` equals override value.

### 8. `importlinter.ini` (MODIFY)
**Purpose:** Keep `lint-imports` deterministic while allowing `frame_compare.services` to import `frame_compare.vspreview`.

**Change:**
- Add `frame_compare.vspreview` as its own layer below domain modules:
  - Keep domain layer as: `frame_compare.analysis | frame_compare.render | frame_compare.services`
  - Add a new layer line: `frame_compare.vspreview`
- Do NOT add `frame_compare.vspreview` to `domain-independence`.

## Acceptance Criteria

- [ ] GIVEN VSPreview is missing WHEN calling `is_vspreview_available()` THEN it returns `False` without raising
- [ ] GIVEN valid `manual_overrides.toml` WHEN calling `load_manual_overrides()` THEN it returns the expected key→ManualOverride mapping
- [ ] GIVEN missing/corrupt/version-mismatched `manual_overrides.toml` WHEN calling `load_manual_overrides()` THEN it returns `{}` (warn-only)
- [ ] GIVEN an existing override for a clip pair WHEN calling `save_manual_override()` THEN the stored entry is overwritten deterministically
- [ ] GIVEN computed/cached offsets exist WHEN a manual override exists THEN `align_clips()` returns manual override results for those keys and does not call audio extraction for overridden entries
- [ ] GIVEN manual overrides exist THEN `audio_offsets.toml` is not modified with manual entries
- [ ] GIVEN `frame-compare doctor` runs WHEN VSPreview is missing THEN the VSPreview check reports optional missing without causing a critical failure
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

- Keep this slice unit-test-only: do not invoke VSPreview, VapourSynth, FFmpeg, or any network calls from tests.
- Ensure `is_vspreview_available()` is robust across machines where `vspreview` may exist on PATH: tests must explicitly patch `shutil.which` and `importlib.util.find_spec`.
- Treat `manual_overrides.toml` as warn-only on parse/version errors (empty mapping fallback).
- Keep the VSPreview script generator deterministic (stable content; timestamp in filename only; timestamp format per SSOT).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-01-04__p6-6-1__vspreview-integration

## Plan to Review
Read file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-v3.md

## Context Files to Read
1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vspreview-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md
4. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md
5. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## Your Task
Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output
Write file: .agent-workflow/runs/2026-01-04__p6-6-1__vspreview-integration/plan-review-v3.md
