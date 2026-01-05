---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v6
TARGET: Meta → Phase 5 Quality Gate Fixes (Docker-first)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md (UPDATED THIS RUN)
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v6.md
  - docs/legacy_tonemap_info.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v6.md
---

# Implementation Plan: Phase 5 Quality Gate Fixes (Docker-first)

## Changes Since plan-v5

- **Expanded scope** to include Docker libplacebo compatibility (new blockers from verify-v3)
- **Updated SSOT first** (per plan-review-v6):
  - `vs-module.md` Section 3.3: Changed core access from `clip.std.core` to `vs.core`
  - `vs-module.md` Section 5.2: Added libplacebo 16-bit RGB48 input rule (legacy-aligned)
  - `vs-module.md` Section 5.3: Added runtime fallback trigger conditions
- **Mandated approach** (no alternatives for Coding Agent):
  - Dockerfile Vulkan enablement via Mesa lavapipe
  - tonemap.py 16-bit input conversion
  - Runtime fallback when libplacebo fails

## Context

**Phase:** Meta (Pre-Phase 6 checkpoint)
**Purpose:** Fix all Phase 5 Quality Gate blockers including Docker libplacebo compatibility
**Dependency:** Phase 6 (CLI & Orchestration) cannot start until Phase 5 Quality Gate passes

### All Blockers (Original + New)

| # | Issue | Severity | Root Cause | Status |
|---|-------|----------|------------|--------|
| 1 | Contract freshness | BLOCKER | Stale files | ✅ FIXED (impl-v1) |
| 2 | PIL deprecation | BLOCKER | `Image.getdata()` deprecated | ✅ FIXED (impl-v1) |
| 3 | find_spec ValueError | MEDIUM | macOS partial VS install | ✅ FIXED (impl-v1) |
| 4 | VS tests not in Docker | MEDIUM | Marker filter excluded tests/vs/ | ✅ FIXED (impl-v1) |
| 5 | vs.core access | BLOCKER | `clip.std.core` invalid | ✅ FIXED (impl-v2) |
| 6 | **libplacebo 16-bit input** | BLOCKER | Code sends RGBS (32-bit), plugin needs RGB48 | 🔴 NEW |
| 7 | **No Vulkan in Docker** | BLOCKER | libplacebo built with `-Dvulkan=disabled` | 🔴 NEW |
| 8 | **No runtime fallback** | MEDIUM | Code raises TonemapError instead of falling back | 🔴 NEW |

## Scope

This plan covers:

- [x] Fixes 1-5: Already implemented in impl-v1/impl-v2
- [ ] Fix 6: Convert to RGB48 before `core.placebo.Tonemap()` (per updated SSOT 5.2)
- [ ] Fix 7: Enable Vulkan in Dockerfile with Mesa lavapipe software ICD
- [ ] Fix 8: Implement runtime fallback when libplacebo fails (per updated SSOT 5.3)
- [ ] Expand Docker test coverage to run ALL tests/vs/ tests (not just vs_required marker)

This plan does NOT cover:

- Phase 6 implementation
- Adding new tonemapping presets

## Contract Impact

**Contracts touched:** NO

**SSOT updated this run (by Planning Agent):**

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md` — VapourSynth Availability Guards
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section 3.3: Core acquisition rule (`vs.core`)
  - Section 5.2: libplacebo Input Format Rule (RGB48)
  - Section 5.3: Fallback Trigger Conditions

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "2.4 VapourSynth Tests"
  - Section: "3.1 Pytest Configuration"
  - Section: "3.2 Conftest Organization"
  - Section: "VapourSynth Availability Guards"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "3.3 Tonemapping" (Behavioral Requirements)
  - Section: "5.2 libplacebo Integration"
  - Section: "5.3 Fallback Handling"

---

## Functions to Implement/Modify

Per updated SSOT sections 5.2 and 5.3:

- `_apply_libplacebo(clip, settings, core) -> vs.VideoNode | None` — Updated to:
  1. Convert to RGB48 before `core.placebo.Tonemap()`
  2. Convert back to RGBS after tonemap
  3. Return `None` on runtime failure (signal fallback)

- `apply_tonemap(clip, settings, hdr_metadata) -> vs.VideoNode` — Updated to:
  1. Use `vs.core` instead of `clip.std.core`
  2. Call fallback if `_apply_libplacebo` returns `None`

---

## Files to Create/Modify

### 1. `Dockerfile` (MODIFY)

**Purpose:** Enable Vulkan backend for libplacebo with Mesa lavapipe software ICD

**Current (lines 105-112):**

```dockerfile
meson setup build \
    -Dvulkan=disabled \
    -Dopengl=disabled \
    -Dshaderc=disabled \
    -Ddemos=false && \
```

**Change to:**

```dockerfile
meson setup build \
    -Dvulkan=enabled \
    -Dshaderc=disabled \
    -Ddemos=false && \
```

**Additional changes required in builder stage (add after line 43):**

```dockerfile
# Vulkan software ICD for headless libplacebo
libvulkan-dev \
glslang-tools \
```

**Additional changes required in runtime stage (line 141-150):**

```dockerfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        libxxhash0 \
        libvulkan1 \
        mesa-vulkan-drivers \
        procps \
        wget \
        which \
        && \
    rm -rf /var/lib/apt/lists/*
```

**Add environment variable for lavapipe (after line 174):**

```dockerfile
# Force Mesa lavapipe software Vulkan
ENV VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.x86_64.json
```

---

### 2. `src/frame_compare/vs/tonemap.py` (MODIFY)

**Purpose:** Implement 16-bit input conversion and runtime fallback per updated SSOT

#### Change 1: Update `_apply_libplacebo` to use RGB48 input (per SSOT 5.2)

**Current (approx line 155-170):**

```python
# RGBS Conversion Rule (old)
if clip.format.id != vs.RGBS:
    clip = clip.resize.Bicubic(format=vs.RGBS, matrix_in_s="709")
```

**Change to:**

```python
# libplacebo Input Format Rule (SSOT 5.2 — legacy-aligned)
# libplacebo requires 16-bit integer input
try:
    if clip.format.bits_per_sample != 16 or clip.format.color_family != vs.RGB:
        clip = clip.resize.Bicubic(format=vs.RGB48, matrix_in_s="709")
except Exception as e:
    from frame_compare.errors import TonemapError
    raise TonemapError(f"Failed to convert to RGB48: {e}") from e
```

#### Change 2: Add post-tonemap RGBS conversion (per SSOT 5.2)

**After `core.placebo.Tonemap()` call, add:**

```python
# Convert libplacebo output back to RGBS for post-processing (SSOT 5.2)
clip = clip.resize.Point(format=vs.RGBS)
```

#### Change 3: Update `_apply_libplacebo` to return None on runtime failure (per SSOT 5.3)

**Wrap `core.placebo.Tonemap()` call:**

```python
try:
    clip = core.placebo.Tonemap(
        clip,
        tone_mapping_function=tone_curve_map[settings.tone_curve],
        dst_max=settings.target_nits,
        src_max=src_max,
        dst_csp=0,  # SDR
    )
except Exception as e:
    # Runtime failure (Vulkan/context/bit-depth) — signal fallback
    import logging
    logging.getLogger(__name__).debug(f"libplacebo runtime failure, falling back: {e}")
    return None
```

#### Change 4: Update `apply_tonemap` to handle fallback trigger (per SSOT 5.3)

**Current logic:**

```python
if detect_plugins(core).get("libplacebo"):
    return _apply_libplacebo(clip, settings, core)
else:
    return _fallback_tonemap(clip, settings, hdr_metadata)
```

**Change to:**

```python
if detect_plugins(core).get("libplacebo"):
    result = _apply_libplacebo(clip, settings, core, hdr_metadata)
    if result is not None:
        return result
    # libplacebo failed at runtime, fall through to fallback
return _fallback_tonemap(clip, settings, hdr_metadata)
```

---

### 3. `tests/vs/test_tonemap.py` (MODIFY)

**Purpose:** Update mocks to patch `vapoursynth.core` and add fallback trigger test

#### Change 1: Update mock patches

**All patches of `clip.std.core` must change to `vapoursynth.core`:**

```python
# BEFORE
mock_clip.std.core = mock_core

# AFTER
# Patch at module level
@patch("frame_compare.vs.tonemap.vs.core", new_callable=MagicMock)
def test_...(mock_vs_core):
    ...
```

#### Change 2: Add unit test for runtime fallback (NEW)

**Test name:** `test_apply_tonemap_falls_back_on_libplacebo_runtime_failure`

**Test spec:**

```python
@patch("frame_compare.vs.tonemap.detect_plugins")
@patch("frame_compare.vs.tonemap._apply_libplacebo")
@patch("frame_compare.vs.tonemap._fallback_tonemap")
def test_apply_tonemap_falls_back_on_libplacebo_runtime_failure(
    mock_fallback, mock_libplacebo, mock_detect
):
    """Verify runtime failure in libplacebo triggers fallback."""
    mock_detect.return_value = {"libplacebo": True}
    mock_libplacebo.return_value = None  # Signals runtime failure
    mock_fallback.return_value = MagicMock()  # Fallback result

    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=True)

    result = apply_tonemap(mock_clip, settings)

    mock_libplacebo.assert_called_once()
    mock_fallback.assert_called_once()
    assert result is mock_fallback.return_value
```

---

### 4. `tests/vs/test_integration.py` (NO CHANGE)

The test already uses `vs.RGBS` which will be converted to RGB48 by the updated tonemap code. No test changes required — the code fix handles the conversion.

---

### 5. `tools/verify_docker_integration.sh` (MODIFY)

**Purpose:** Remove marker filter to run ALL tests/integration/ and tests/vs/ tests

**Current (line 91):**

```bash
python -m pytest -v -m "integration or vs_required" tests/integration/ tests/vs/
```

**Change to:**

```bash
python -m pytest -v tests/integration/ tests/vs/
```

**Rationale:** The marker filter excluded most unit tests in `tests/vs/`. Running all tests ensures comprehensive Docker verification.

---

### 6. `docs/DECISIONS.md` (MODIFY)

**Purpose:** Append run decision entry

**Entry:**

```markdown
### 2026-01-02__meta__p5-quality-gate

**Scope:** Phase 5 Quality Gate fixes (contract freshness, PIL deprecation, VS test collection, Docker libplacebo compatibility)

**SSOT Edits:**
- `testing-strategy.md` Section 3.2: Added VapourSynth Availability Guards
- `vs-module.md` Section 3.3: Changed core access to `vs.core`
- `vs-module.md` Section 5.2: Added libplacebo RGB48 input rule
- `vs-module.md` Section 5.3: Added fallback trigger conditions

**Key Decisions:**
1. libplacebo requires 16-bit input (RGB48), not 32-bit float (RGBS)
2. Dockerfile enables Vulkan via Mesa lavapipe for headless libplacebo
3. Runtime fallback is mandatory: if libplacebo fails at runtime, use _fallback_tonemap

**Artifacts:** plan-v1 through plan-v6, impl-v1, impl-v2, verify-v1 through verify-v3
```

---

### 7. `CHANGELOG.md` (MODIFY)

**Purpose:** Record infrastructure improvements

**Entry:**

```markdown
### Fixed
- Docker integration tests now include VS-required tests from `tests/vs/`
- Fixed PIL deprecation warning causing test failure in Docker
- Fixed test collection failure on macOS with partial VapourSynth install
- Fixed libplacebo tonemapping in Docker (16-bit input conversion)
- Fixed `vs.core` access pattern in tonemap module
- Enabled Vulkan in Docker image for libplacebo (Mesa lavapipe)
- Added runtime fallback when libplacebo fails due to Vulkan/context issues
```

---

## Acceptance Criteria

- [ ] GIVEN Docker build WHEN running `docker compose build` THEN libplacebo has Vulkan support
- [ ] GIVEN tonemap code WHEN libplacebo available THEN input is converted to RGB48 before `core.placebo.Tonemap()`
- [ ] GIVEN libplacebo runtime failure WHEN tonemapping THEN fallback is used silently (no TonemapError)
- [ ] GIVEN Docker integration WHEN running `verify_docker_integration.sh` THEN all tests pass with zero skips
- [ ] GIVEN unit test WHEN simulating libplacebo runtime failure THEN fallback path is exercised

---

## Verification Commands

### 1. Static Analysis

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

**Pass criteria:** All exit 0.

### 2. Local Test Suite

```bash
.venv/bin/pytest -v --cov=src/frame_compare --cov-report=term-missing --cov-fail-under=80
```

**Pass criteria:** Exit 0, coverage ≥ 80%, includes new fallback test.

### 3. Docker Build

```bash
docker compose build frame-compare-test
```

**Pass criteria:** Exit 0, no build errors.

### 4. Docker Integration (Primary Gate)

```bash
bash tools/verify_docker_integration.sh
```

**Pass criteria:**

- Exit 0
- Zero skipped tests
- Zero failed tests
- `test_vs_integration_smoke` passes (libplacebo or fallback succeeds)

---

## Notes for Coding Agent

1. **SSOT already updated** — Planning Agent updated vs-module.md sections 3.3, 5.2, 5.3
2. **RGB48 conversion is mandatory** — libplacebo rejects 32-bit float; use exact pattern from SSOT 5.2
3. **Return None on failure** — `_apply_libplacebo` must return `None` to signal fallback, not raise
4. **Use vs.core** — Per SSOT 3.3, use `vs.core` (module singleton), not `clip.std.core`
5. **Dockerfile changes are precise** — Change exactly the lines specified; don't modify other build flags
6. **Remove marker filter** — The `-m "integration or vs_required"` filter is too restrictive
7. **Test after Docker build** — The Docker image must be rebuilt before running integration tests

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__meta__p5-quality-gate

## Plan to Review

Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v6.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
3. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v6.md
4. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md
5. Read file: Dockerfile

## SSOT Update Audit Required

Planning Agent updated SSOT this loop:

- File: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- Sections updated: 3.3 (core access), 5.2 (libplacebo RGB48 rule), 5.3 (fallback triggers)

Verify the SSOT updates are sound and the plan correctly implements them.

## Your Task

Validate the plan using the 9-point checklist. Include SSOT Update Audit. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v7.md
