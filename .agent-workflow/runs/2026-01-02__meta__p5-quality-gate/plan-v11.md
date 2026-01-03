---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v11
TARGET: Meta → Phase 5 Quality Gate Fixes (Docker-first)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v11.md
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md
---

# Implementation Plan: Phase 5 Quality Gate Fixes (Docker-first)

## Changes Since plan-v10

- **Fixed `TonemapError` constructor** (per plan-review-v11):
  - Changed to `TonemapError(reason=...)` per actual error API
- **Fixed undefined identifier** (per plan-review-v11):
  - Changed `tone_curve_map` to `_TONE_CURVE_MAP` (existing constant)
- **Removed `dst_csp=0` kwarg** (per plan-review-v11):
  - Not specified in SSOT; must not introduce new kwargs

## Context

**Phase:** Meta (Pre-Phase 6 checkpoint)
**Purpose:** Fix all Phase 5 Quality Gate blockers including Docker libplacebo compatibility
**Dependency:** Phase 6 cannot start until Phase 5 Quality Gate passes

### Blockers Summary

| # | Issue | Status |
|---|-------|--------|
| 1-5 | Original blockers | ✅ FIXED |
| 6 | libplacebo 16-bit input | 🔴 NEW |
| 7 | No Vulkan in Docker | 🔴 NEW |
| 8 | No runtime fallback | 🔴 NEW |

## Scope

- [x] Fixes 1-5: Already implemented
- [ ] Fix 6-8: Docker libplacebo compatibility

---

## Out of Scope (Follow-up RUN_IDs)

- `enable_tonemap` config wiring
- `use_vspreview` integration
- Traceability audit

---

## Contract Impact

**Contracts touched:** NO

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

Per SSOT `vs-module.md`:

- `apply_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
- `_apply_libplacebo(clip: vs.VideoNode, settings: TonemapSettings, core: vs.Core, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode | None`
- `_fallback_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None) -> vs.VideoNode`

---

## Files to Create/Modify

### 1. `Dockerfile` (MODIFY)

**Purpose:** Enable Vulkan backend for libplacebo with Mesa lavapipe

#### Builder stage — libplacebo meson flags

```dockerfile
meson setup build \
    -Dvulkan=enabled \
    -Dopengl=disabled \
    -Dshaderc=disabled \
    -Ddemos=false && \
```

#### Builder stage — add glslang-tools

```dockerfile
glslang-tools \
```

#### Runtime stage — add Vulkan packages

```dockerfile
libvulkan1 \
mesa-vulkan-drivers \
```

> [!IMPORTANT]
> Do NOT set `VK_ICD_FILENAMES`. Mesa auto-discovers for architecture portability.

---

### 2. `src/frame_compare/vs/tonemap.py` (MODIFY)

#### Change 1: Update `_apply_libplacebo` signature

```python
def _apply_libplacebo(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    core: vs.Core,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode | None:
```

#### Change 2: Update input conversion to RGB48 (FIXED)

```python
    # Exact conversion call for libplacebo path
    try:
        if clip.format.bits_per_sample != 16 or clip.format.color_family != vs.RGB:
            clip = clip.resize.Bicubic(format=vs.RGB48, matrix_in_s="709")
    except Exception as e:
        raise TonemapError(reason=f"Failed to convert to RGB48: {e}") from e
```

> [!NOTE]
> Uses `TonemapError(reason=...)` per actual error API in `src/frame_compare/errors.py`.

#### Change 3: Post-tonemap RGBS conversion + runtime failure handling (FIXED)

```python
try:
    clip = core.placebo.Tonemap(
        clip,
        tone_mapping_function=_TONE_CURVE_MAP[settings.tone_curve],
        dst_max=settings.target_nits,
        src_max=src_max,
    )
except Exception as e:
    # Runtime failure (Vulkan/context/bit-depth) — signal fallback
    import logging
    logging.getLogger(__name__).debug(f"libplacebo runtime failure, falling back: {e}")
    return None

# Convert libplacebo output back to RGBS for post-processing (runs on SUCCESS only)
clip = clip.resize.Point(format=vs.RGBS)
```

> [!NOTE]
>
> - Uses `_TONE_CURVE_MAP` (existing constant in tonemap.py)
> - Removed `dst_csp=0` (not in SSOT)
> - RGBS conversion is **outside** the except block

#### Change 4: Update `apply_tonemap` to handle fallback

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

**Add unit test for runtime fallback:**

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

### 4. `tests/vs/test_integration.py` (MODIFY)

**Add Docker-only test that proves libplacebo Tonemap succeeds:**

```python
@pytest.mark.vs_required
def test_libplacebo_tonemap_succeeds_in_docker():
    """Ensure libplacebo Tonemap actually works in Docker (Vulkan backend).

    This test verifies that `_apply_libplacebo` returns a vs.VideoNode (not None),
    proving the Vulkan/lavapipe backend is functional.
    """
    import vapoursynth as vs
    from frame_compare.vs.tonemap import _apply_libplacebo, detect_plugins
    from frame_compare.vs import TonemapSettings, HDRMetadata

    core = vs.core

    # Skip if libplacebo not available
    if not detect_plugins(core).get("libplacebo"):
        pytest.skip("libplacebo not available")

    # Create a minimal HDR test clip (RGBS, 1920x1080, 1 frame)
    clip = core.std.BlankClip(
        width=1920,
        height=1080,
        format=vs.RGBS,
        length=1,
        color=[0.5, 0.5, 0.5],
    )

    settings = TonemapSettings(
        enabled=True,
        preset="reference",
        tone_curve="bt2390",
        target_nits=203,
    )

    hdr_metadata = HDRMetadata(
        mastering_display=None,
        max_cll=1000,
        max_fall=400,
        color_primaries=9,
        transfer=16,
        matrix=9,
    )

    # Call _apply_libplacebo directly and assert it succeeds
    result = _apply_libplacebo(clip, settings, core, hdr_metadata)

    # If result is None, libplacebo failed (Vulkan backend broken)
    assert result is not None, (
        "_apply_libplacebo returned None — libplacebo Vulkan backend failed."
    )
    assert isinstance(result, vs.VideoNode)
```

---

### 5. `tools/verify_docker_integration.sh` (MODIFY)

**Remove marker filter:**

```bash
python -m pytest -v tests/integration/ tests/vs/
```

---

### 6. `docs/DECISIONS.md` (MODIFY)

```markdown
### 2026-01-02__meta__p5-quality-gate

**Key Decisions:**
1. libplacebo requires 16-bit input (RGB48)
2. Dockerfile enables Vulkan via Mesa lavapipe
3. Keep `-Dopengl=disabled` for headless libplacebo
4. Runtime fallback: `_apply_libplacebo` returns `None` on failure
5. Docker gate must prove libplacebo succeeds (test `test_libplacebo_tonemap_succeeds_in_docker`)
```

---

### 7. `CHANGELOG.md` (MODIFY)

```markdown
### Fixed
- Docker integration tests now include VS-required tests from `tests/vs/`
- Fixed PIL deprecation warning causing test failure in Docker
- Fixed test collection failure on macOS with partial VapourSynth install
- Fixed libplacebo tonemapping in Docker (16-bit input conversion)
- Fixed `vs.core` access pattern in tonemap module
- Enabled Vulkan in Docker image for libplacebo (Mesa lavapipe)
- Added runtime fallback when libplacebo fails
- Added explicit test to verify libplacebo Vulkan backend works in Docker
```

---

## Acceptance Criteria

- [ ] GIVEN Docker build THEN libplacebo compiles with Vulkan
- [ ] GIVEN tonemap code THEN input converted to RGB48 before libplacebo
- [ ] GIVEN libplacebo runtime failure THEN `_apply_libplacebo` returns `None`
- [ ] GIVEN Docker integration THEN `test_libplacebo_tonemap_succeeds_in_docker` passes (proves Vulkan works)
- [ ] GIVEN Docker integration THEN zero skips, zero failed

---

## Verification Commands

### 1. Spec Anchor Validation

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md
```

### 2. Static Analysis

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

### 3. Local Test Suite

```bash
.venv/bin/pytest -v --cov=src/frame_compare --cov-report=term-missing --cov-fail-under=80
```

### 4. Docker Build

```bash
docker compose build frame-compare-test
```

### 5. Docker Integration (Primary Gate)

```bash
bash tools/verify_docker_integration.sh
```

**Pass criteria:** Exit 0, zero skipped, zero failed, `test_libplacebo_tonemap_succeeds_in_docker` passes.

---

## Notes for Coding Agent

1. **Use `TonemapError(reason=...)`** — not positional arg
2. **Use `_TONE_CURVE_MAP`** — existing constant, not `tone_curve_map`
3. **No `dst_csp` kwarg** — not in SSOT, don't add it
4. **RGBS conversion is OUTSIDE except block**
5. **New test is critical** — `test_libplacebo_tonemap_succeeds_in_docker` must pass
6. **Rebuild Docker after changes**

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2026-01-02__meta__p5-quality-gate

## Plan to Review

Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
3. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v11.md
4. Read file: src/frame_compare/errors.py

## Spec Anchor STOP Gate Required

Run: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md`

## Your Task

Validate plan using 9-point checklist. Verify:

- `TonemapError(reason=...)` constructor usage is correct
- `_TONE_CURVE_MAP` is referenced (not `tone_curve_map`)
- No `dst_csp` kwarg is present

Produce Plan Review Report.

## Output

Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v12.md
