---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v12
TARGET: Meta → Phase 5 → Docker Gate Fixes (verify-v4 blockers)
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v11.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v12.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/impl-v3.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v4.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - src/frame_compare/errors.py
  - Dockerfile
  - tools/verify_docker_integration.sh
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v12.md
---

# Implementation Plan: Phase 5 Docker Gate Fixes (verify-v4 blockers)

## Changes Since plan-v11

- Add missing Docker test dependency (`pytest-mock`) to unblock `mocker` fixture in Docker.
- Fix RGB→RGB resize conversion rules (remove invalid `matrix_in_s` usage for RGB inputs) per Docker failure.
- Make Vulkan device selection deterministic in Docker by forcing lavapipe ICD selection at test runtime (without hardcoding arch-specific paths in `Dockerfile`).
- Update SSOT `vs-module.md` Section 5.2 conversion snippets to match the corrected RGB/YUV conversion rules.

## Context

`verify-v4.md` reports Docker-only blockers after implementing plan-v11:

1. Docker tests error: `fixture 'mocker' not found` (pytest-mock missing in image).
2. VapourSynth resize error: `RGB color family cannot have YUV matrix coefficients` due to `matrix_in_s="709"` used on RGB input during RGB48 conversion.
3. libplacebo Vulkan failure: `Found no suitable device, giving up.` despite Vulkan packages installed.

## Scope

This plan fixes ONLY the verify-v4 Docker blockers:

- [ ] Install `pytest-mock` inside the Docker runtime image.
- [ ] Fix RGB48 conversion logic so RGB inputs do not pass `matrix_in_s`.
- [ ] Force lavapipe selection deterministically for Docker test runs.

Out of scope:

- Any feature work (auto-tonemap wiring, VSPreview integration, traceability audit).

## Contract Impact

**Contracts touched:** NO

## SSOT Update (Required for Fix 2)

SSOT must match the corrected behavior (RGB clips must not pass YUV matrix coefficients).

- File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
  - Section: `### 5.2 libplacebo Integration`
  - Change: RGB48 and RGBS conversion snippets are conditional:
    - RGB input: omit `matrix_in_s`
    - non-RGB input (YUV): include `matrix_in_s="709"`

## Spec Anchors (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`:
  - Section: "3.3 Tonemapping"
  - Section: "5.2 libplacebo Integration"
  - Section: "5.3 Fallback Handling"

## Public API (signatures)

- `apply_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode`
- `_apply_libplacebo(clip: vs.VideoNode, settings: TonemapSettings, core: vs.Core, hdr_metadata: HDRMetadata | None = None) -> vs.VideoNode | None`
- `_fallback_tonemap(clip: vs.VideoNode, settings: TonemapSettings, hdr_metadata: HDRMetadata | None) -> vs.VideoNode`

## Files to Modify

### 1. `Dockerfile` (MODIFY)

**Goal:** Ensure Docker has the same pytest plugin support as local runs.

**Change:** Install `pytest-mock` in runtime stage alongside pytest.

Current:

```dockerfile
RUN pip install --no-cache-dir --user -e . && \
    pip install --no-cache-dir --user "pytest>=8.3.0"
```

Change to:

```dockerfile
RUN pip install --no-cache-dir --user -e . && \
    pip install --no-cache-dir --user "pytest>=8.3.0" "pytest-mock>=3.14.0"
```

### 2. `src/frame_compare/vs/tonemap.py` (MODIFY)

**Goal:** Never pass `matrix_in_s` for RGB inputs when converting between RGB formats.

**Change A (libplacebo RGB48 conversion):** Replace the unconditional RGB48 conversion call:

```python
clip = clip.resize.Bicubic(format=vs.RGB48, matrix_in_s="709")
```

With the conditional conversion:

```python
if clip.format.color_family == vs.RGB:
    clip = clip.resize.Bicubic(format=vs.RGB48)
else:
    clip = clip.resize.Bicubic(format=vs.RGB48, matrix_in_s="709")
```

**Change B (`_to_rgbs` RGBS conversion):** Ensure `_to_rgbs` omits `matrix_in_s` for RGB inputs when converting to RGBS:

```python
if clip.format.color_family == vs.RGB:
    clip = clip.resize.Bicubic(format=vs.RGBS)
else:
    clip = clip.resize.Bicubic(format=vs.RGBS, matrix_in_s="709")
```

**Error handling:** Preserve existing `TonemapError(reason=..., hint=...)` behavior (FC-4003), using the actual constructor from `src/frame_compare/errors.py`.

### 3. `tools/verify_docker_integration.sh` (MODIFY)

**Goal:** Make the Docker gate deterministic for Vulkan device selection in headless environments.

**Change:** Prepend environment exports inside `container_cmd` before running pytest:

1. Always set software rendering:

```bash
export LIBGL_ALWAYS_SOFTWARE=1
```

2. If a lavapipe ICD JSON exists, force Vulkan loader to use it:

```bash
icd="$(ls /usr/share/vulkan/icd.d/lvp_icd.*.json 2>/dev/null | head -n 1 || true)"
if [[ -n "$icd" ]]; then
  export VK_ICD_FILENAMES="$icd"
fi
```

**Notes:**

- This avoids hardcoding architecture-specific ICD paths in `Dockerfile` (amd64 vs arm64).
- This change applies only to the Docker test gate command path, and does not change non-Docker behavior.

## Acceptance Criteria

- [ ] GIVEN `bash tools/verify_docker_integration.sh` THEN exit 0 with zero failed and zero skipped.
- [ ] GIVEN Docker tests THEN `tests/vs/test_env.py` no longer errors with missing `mocker` fixture.
- [ ] GIVEN `tests/vs/test_integration.py::test_vs_integration_smoke` THEN no `Resize error 1026` occurs.
- [ ] GIVEN `tests/vs/test_integration.py::test_libplacebo_tonemap_succeeds_in_docker` THEN `_apply_libplacebo` returns non-None (Vulkan device usable via lavapipe).

## Verification Commands

### 1. Spec Anchor STOP Gate

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_spec_anchors.py .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v12.md
```

**Pass criteria:** Exit 0.

### 2. Local Gates (sanity)

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
```

**Pass criteria:** All exit 0.

### 3. Docker Gate (primary)

```bash
bash tools/verify_docker_integration.sh
```

**Pass criteria:** Exit 0, zero failed, zero skipped.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Plan to Review
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v12.md

## Context Files to Read
1. Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v4.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
3. Read file: src/frame_compare/errors.py

## Output
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v13.md
