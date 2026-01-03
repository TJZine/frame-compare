---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v5
TARGET: Meta → Phase 5 Quality Gate Fixes
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v1.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v3.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v4.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v4.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md
---

# Implementation Plan: Phase 5 Quality Gate Fixes

## Changes Since plan-v4

- Mechanical Auto-Fix Mode: Fixed Spec Anchor heading string to match SSOT heading title text
  - From: `"#### VapourSynth Availability Guards"`
  - To: `"VapourSynth Availability Guards"`

## Context

**Phase:** Meta (Pre-Phase 6 checkpoint)
**Purpose:** Fix all Phase 5 Quality Gate blockers and ensure Docker-based testing before proceeding to Phase 6
**Dependency:** Phase 6 (CLI & Orchestration) cannot start until Phase 5 Quality Gate passes

### Blockers Identified (from verify-v1.md)

| # | Issue | Severity | Root Cause |
|---|-------|----------|------------|
| 1 | Contract freshness check failed | BLOCKER | 3 stale files need regeneration |
| 2 | Docker integration test failing | BLOCKER | PIL `Image.getdata()` deprecated, treated as error |
| 3 | Test collection errors on macOS | MEDIUM | `find_spec("vapoursynth")` raises `ValueError` instead of returning `None` |
| 4 | VS tests not in Docker verification | MEDIUM | `vs_required` tests only run locally, not in Docker container |

## Scope

This plan covers:

- [x] Fix 1: Regenerate stale contract views
- [x] Fix 2: Replace deprecated PIL `Image.getdata()` with compatible helper
- [x] Fix 3: Handle `ValueError` from `find_spec` in test collection guards
- [x] Fix 4: Ensure VS integration tests run in Docker verification suite

This plan does NOT cover:

- Phase 6 implementation
- Adding new VS tests beyond existing `@pytest.mark.vs_required` tests

## Contract Impact

**Contracts touched:** NO (regeneration only, no edits to canonical contracts)

**SSOT updated this run:**

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md` → added "VapourSynth Availability Guards" subsection under 3.2

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "2.4 VapourSynth Tests"
  - Section: "3.1 Pytest Configuration"
  - Section: "3.2 Conftest Organization"
  - Section: "VapourSynth Availability Guards"

---

## Functions to Implement

Helper functions (spec-anchored in "VapourSynth Availability Guards"):

- `_vs_needs_mock() -> bool` — Check if vapoursynth needs to be mocked for test collection (in `tests/conftest.py`)
- `_vs_spec_available() -> bool` — Check if vapoursynth module spec is available (in `tests/vs/test_exports.py`, `tests/vs/test_tonemap.py`)

---

## Files to Create/Modify

### 1. Contract Regeneration (Shell Command)

**Purpose:** Regenerate stale derived contract views

**Command:**

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py
```

**Stale files to regenerate:**

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/cli/_generated.py`

> [!NOTE]
> No manual edits to these files. The generator script produces deterministic output from canonical contracts.

---

### 2. `tests/integration/test_render_pipeline.py` (MODIFY)

**Purpose:** Fix deprecated PIL `Image.getdata()` call that causes Docker test failure

**Root cause:** `pyproject.toml` has `filterwarnings = ["error"]`, so `DeprecationWarning` becomes an error. PIL 14 deprecates `Image.getdata()`.

**Change at line 58:**

```python
# BEFORE
assert len(set(result.getdata())) > 1

# AFTER
# Use compatible approach that works with Pillow < 14 and >= 14
try:
    # Pillow >= 14 preferred method
    pixel_data = result.get_flattened_data()
except AttributeError:
    # Pillow < 14 fallback (getdata still works, suppress warning)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        pixel_data = list(result.getdata())
assert len(set(pixel_data)) > 1
```

---

### 3. `tests/conftest.py` (MODIFY)

**Purpose:** Handle `ValueError` from `find_spec("vapoursynth")` during test collection

**Function signature:** `_vs_needs_mock() -> bool` (per SSOT "VapourSynth Availability Guards")

**Change at lines 21-28:**

```python
# BEFORE
if "vapoursynth" not in sys.modules and importlib.util.find_spec("vapoursynth") is None:

# AFTER
def _vs_needs_mock() -> bool:
    """Check if vapoursynth needs to be mocked for test collection."""
    if "vapoursynth" in sys.modules:
        return False
    try:
        return importlib.util.find_spec("vapoursynth") is None
    except ValueError:
        # Raised when vapoursynth.__spec__ is not set (partial install)
        return True

if _vs_needs_mock():
```

---

### 4. `tests/vs/test_exports.py` (MODIFY)

**Purpose:** Handle `ValueError` from `find_spec("vapoursynth")` during test collection

**Function signature:** `_vs_spec_available() -> bool` (per SSOT "VapourSynth Availability Guards")

**Change at lines 7-12:**

```python
# BEFORE
if importlib.util.find_spec("vapoursynth") is None:

# AFTER
def _vs_spec_available() -> bool:
    try:
        return importlib.util.find_spec("vapoursynth") is not None
    except ValueError:
        return False

if not _vs_spec_available():
```

---

### 5. `tests/vs/test_tonemap.py` (MODIFY)

**Purpose:** Handle `ValueError` from `find_spec("vapoursynth")` during test collection

**Function signature:** `_vs_spec_available() -> bool` (per SSOT "VapourSynth Availability Guards")

**Change at lines 9-15:**

```python
# BEFORE
if importlib.util.find_spec("vapoursynth") is None:

# AFTER
def _vs_spec_available() -> bool:
    try:
        return importlib.util.find_spec("vapoursynth") is not None
    except ValueError:
        return False

if not _vs_spec_available():
```

---

### 6. `tools/verify_docker_integration.sh` (MODIFY)

**Purpose:** Ensure VS-required tests run in Docker container with zero skips

**Change (line 91):**

```bash
# BEFORE
python -m pytest -v -m "integration or vs_required" tests/integration/

# AFTER
python -m pytest -v -m "integration or vs_required" tests/integration/ tests/vs/
```

---

### 7. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry

**Required facts to record:**

- RUN_ID: `2026-01-02__meta__p5-quality-gate`
- Artifact versions: plan-v1 through plan-v4, verify-v1, impl-v1, verify-v2
- Scope: Fix Phase 5 Quality Gate blockers
- SSOT edits: Added "VapourSynth Availability Guards" to testing-strategy.md section 3.2
- Verification gates: pyright, ruff, lint-imports, contract freshness, Docker integration

---

### 8. `CHANGELOG.md` (MODIFY)

**Purpose:** Record infrastructure improvements

**Entry:**

```markdown
### Fixed
- Docker integration tests now include VS-required tests from `tests/vs/`
- Fixed PIL deprecation warning causing test failure in Docker
- Fixed test collection failure on macOS with partial VapourSynth install
```

---

## Acceptance Criteria

- [ ] GIVEN contract regeneration WHEN running `generate_contract_views.py --check` THEN exit 0
- [ ] GIVEN PIL compatibility fix WHEN running `test_overlay_application_adds_visible_content` in Docker THEN test passes
- [ ] GIVEN `find_spec` guard fix WHEN running `pytest --collect-only` on macOS THEN no collection errors
- [ ] GIVEN Docker integration script WHEN running THEN includes `tests/vs/` and exits 0 with zero skips
- [ ] GIVEN all fixes WHEN running full test suite THEN coverage ≥ 80% and all tests pass

---

## Verification Commands

### 1. Contract Freshness

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**Pass criteria:** Both exit 0.

### 2. Static Analysis

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All exit 0 with no errors.

### 3. Local Test Suite (with collection fix)

```bash
.venv/bin/pytest -v --cov=src/frame_compare --cov-report=term-missing --cov-fail-under=80
```

**Pass criteria:** Exit 0, no collection errors, coverage ≥ 80%.

### 4. Docker Integration (Primary Gate)

```bash
bash tools/verify_docker_integration.sh
```

**Pass criteria:**

- Exit 0
- Zero skipped tests
- Includes `test_vs_integration_smoke` from `tests/vs/test_integration.py`

---

## Notes for Coding Agent

1. **Contract regeneration first** — Run the generator command before any code changes
2. **PIL compatibility** — Use try/except pattern to support Pillow < 14 and >= 14; do NOT pin Pillow version
3. **find_spec helper** — Implement per SSOT "VapourSynth Availability Guards" section
4. **Docker script change is minimal** — Only add `tests/vs/` to the pytest path list
5. **Test after each fix** — Verify each blocker is resolved before moving to the next
6. **SSOT already updated** — The testing-strategy.md update was made by Planning Agent; Coding Agent implements in test files

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__meta__p5-quality-gate

## Plan to Review

Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
3. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v1.md
4. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v3.md
5. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md (for templates only)

## SSOT Update Audit Required

Planning Agent updated SSOT this loop:

- File: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
- Section added: "#### VapourSynth Availability Guards" under 3.2

Verify the SSOT update is sound and the plan correctly references it.

## Your Task

Validate the plan using the 9-point checklist. Include SSOT Update Audit. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v5.md
