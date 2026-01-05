---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v8
TARGET: Meta → Phase 5 Quality Gate Fixes (Docker-first)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md (UPDATED THIS RUN)
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v7.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v8.md
  - docs/legacy_tonemap_info.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v8.md
---

# Implementation Plan: Phase 5 Quality Gate Fixes (Docker-first)

## Changes Since plan-v7

- **Added explicit parity gap documentation** (per plan-review-v8):
  - `enable_tonemap` config key is unused — deferred to follow-up RUN_ID
  - `use_vspreview` config key is unused — deferred to follow-up RUN_ID
  - Missing E2E tests claimed in traceability docs — deferred to follow-up RUN_ID
- **Clarified scope boundaries** with explicit "Out of Scope" section

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
- [ ] Fix 6: Convert to RGB48 before `core.placebo.Tonemap()` (per SSOT 5.2)
- [ ] Fix 7: Enable Vulkan in Dockerfile with Mesa lavapipe software ICD
- [ ] Fix 8: Implement runtime fallback when libplacebo fails (per SSOT 5.3)
- [ ] Expand Docker test coverage to run ALL tests/vs/ tests

---

## Out of Scope (Follow-up RUN_IDs Required)

> [!IMPORTANT]
> The following parity gaps were identified during this run but are **explicitly deferred** to separate follow-up RUN_IDs to avoid scope creep. Create these after the Docker gate passes.

### Follow-up RUN_ID: `YYYY-MM-DD__feat__auto-tonemap-wiring`

**Issue:** `config.color.enable_tonemap` exists but is unused in runtime code.

**What needs to happen:**

- Wire `enable_tonemap` config key into render/orchestration pipeline
- Gate by `SourceInfo.is_hdr` + `config.color.enable_tonemap`
- Apply tonemap preset/target settings from config/CLI

### Follow-up RUN_ID: `YYYY-MM-DD__feat__vspreview-integration`

**Issue:** `config.audio_alignment.use_vspreview` exists but is unused in runtime code.

**What needs to happen:**

- Implement VSPreview integration for manual audio alignment
- Wire config key into alignment service

### Follow-up RUN_ID: `YYYY-MM-DD__docs__traceability-audit`

**Issue:** `requirements-traceability.md` references "Full pipeline" E2E tests that do not exist in `tests/` today.

**What needs to happen:**

- Audit traceability matrix against actual tests
- Either create missing E2E tests or correct traceability claims

---

## Contract Impact

**Contracts touched:** NO

**SSOT updated this run (by Planning Agent):**

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md` — VapourSynth Availability Guards
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section "3.3 Tonemapping": Core acquisition rule (`vs.core`)
  - Section "5.2 libplacebo Integration": RGB48 input rule + `_apply_libplacebo` signature
  - Section "5.3 Fallback Handling": Fallback trigger conditions

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md`:
  - Section: "2.4 VapourSynth Tests"
  - Section: "3.1 Pytest Configuration"
  - Section: "3.2 Conftest Organization"
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "3.3 Tonemapping"
  - Section: "5.2 libplacebo Integration"
  - Section: "5.3 Fallback Handling"

---

## Public API (signatures)

Per updated SSOT `vs-module.md`:

- `apply_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
- `_apply_libplacebo(clip: vs.VideoNode, settings: TonemapSettings, core: vs.Core, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode | None`
- `_fallback_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None) -> vs.VideoNode`

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

**Additional changes required in builder stage (add after existing apt packages, around line 36):**

```dockerfile
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

#### Change 1: Update `_apply_libplacebo` signature (per SSOT 5.2)

**Current signature:**

```python
def _apply_libplacebo(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    core: vs.Core,
) -> vs.VideoNode:
```

**Change to (per SSOT):**

```python
def _apply_libplacebo(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    core: vs.Core,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode | None:
```

#### Change 2: Update input conversion to RGB48 (per SSOT 5.2)

**Current:**

```python
if clip.format.id != vs.RGBS:
    clip = clip.resize.Bicubic(format=vs.RGBS, matrix_in_s="709")
```

**Change to:**

```python
# libplacebo Input Format Rule (SSOT 5.2 — legacy-aligned)
try:
    if clip.format.bits_per_sample != 16 or clip.format.color_family != vs.RGB:
        clip = clip.resize.Bicubic(format=vs.RGB48, matrix_in_s="709")
except Exception as e:
    from frame_compare.errors import TonemapError
    raise TonemapError(f"Failed to convert to RGB48: {e}") from e
```

#### Change 3: Add post-tonemap RGBS conversion + runtime failure handling (per SSOT 5.2)

**Replace `core.placebo.Tonemap()` call block with:**

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

# Convert libplacebo output back to RGBS for post-processing (SSOT 5.2)
clip = clip.resize.Point(format=vs.RGBS)
```

#### Change 4: Update `apply_tonemap` to handle fallback trigger (per SSOT 5.3)

**Current:**

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

**Purpose:** Add fallback trigger test

**Add test:**

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
    mock_fallback.return_value = MagicMock()

    mock_clip = MagicMock()
    settings = TonemapSettings(enabled=True)

    result = apply_tonemap(mock_clip, settings)

    mock_libplacebo.assert_called_once()
    mock_fallback.assert_called_once()
    assert result is mock_fallback.return_value
```

---

### 4. `tools/verify_docker_integration.sh` (MODIFY)

**Purpose:** Remove marker filter; run ALL tests with zero skips

**Current (line 91):**

```bash
python -m pytest -v -m "integration or vs_required" tests/integration/ tests/vs/
```

**Change to:**

```bash
python -m pytest -v tests/integration/ tests/vs/
```

---

### 5. `docs/DECISIONS.md` (MODIFY)

**Entry:**

```markdown
### 2026-01-02__meta__p5-quality-gate

**Scope:** Phase 5 Quality Gate fixes (contract freshness, PIL deprecation, VS test collection, Docker libplacebo compatibility)

**SSOT Edits:**
- `testing-strategy.md` Section 3.2: Added VapourSynth Availability Guards
- `vs-module.md` Section 3.3: Changed core access to `vs.core`
- `vs-module.md` Section 5.2: Added libplacebo RGB48 input rule, updated `_apply_libplacebo` signature
- `vs-module.md` Section 5.3: Added fallback trigger conditions

**Key Decisions:**
1. libplacebo requires 16-bit input (RGB48), not 32-bit float (RGBS)
2. Dockerfile enables Vulkan via Mesa lavapipe for headless libplacebo
3. Runtime fallback is mandatory: if libplacebo fails at runtime, `_apply_libplacebo` returns `None`

**Deferred Parity Gaps (separate follow-up RUN_IDs):**
- `enable_tonemap` config wiring
- `use_vspreview` integration
- Traceability audit for missing E2E tests

**Artifacts:** plan-v1 through plan-v8, impl-v1, impl-v2, verify-v1 through verify-v3
```

---

### 6. `CHANGELOG.md` (MODIFY)

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

- [ ] GIVEN Docker build WHEN `docker compose build` THEN libplacebo has Vulkan support
- [ ] GIVEN tonemap code WHEN libplacebo available THEN input converted to RGB48
- [ ] GIVEN libplacebo runtime failure WHEN tonemapping THEN `_apply_libplacebo` returns `None`
- [ ] GIVEN Docker integration WHEN `verify_docker_integration.sh` THEN all tests pass, zero skips
- [ ] GIVEN unit test WHEN simulating libplacebo runtime failure THEN fallback exercised

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

**Pass criteria:** Exit 0, zero skipped, zero failed, `test_vs_integration_smoke` passes.

---

## Notes for Coding Agent

1. **SSOT already updated** — vs-module.md sections 3.3, 5.2, 5.3 updated by Planning Agent
2. **RGB48 conversion is mandatory** — libplacebo rejects 32-bit float
3. **Return None on failure** — `_apply_libplacebo` returns `None` to signal fallback
4. **Use vs.core** — not `clip.std.core`
5. **Signature must match SSOT** — `_apply_libplacebo(..., hdr_metadata=None) -> vs.VideoNode | None`
6. **Remove marker filter** — Docker tests run `tests/integration/` + `tests/vs/` without markers
7. **Rebuild Docker after changes** — `docker compose build frame-compare-test`

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__meta__p5-quality-gate

## Plan to Review

Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v8.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
3. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v8.md
4. Read file: Dockerfile

## SSOT Update Audit Required

Planning Agent updated SSOT this loop:

- File: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- Section 5.2: `_apply_libplacebo` signature includes `hdr_metadata` param and `-> vs.VideoNode | None`

Verify SSOT updates are sound and plan signatures match exactly.

## Your Task

Validate plan using 9-point checklist. Include SSOT Update Audit. Produce Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v9.md
