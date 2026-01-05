---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v8
TARGET: Meta → Phase 5 Quality Gate (Docker-first) + Parity Gap Triage
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v6.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v7.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md
  - docs/legacy_tonemap_info.md
  - docs/legacy_project_dissection.md
  - Dockerfile
  - tools/verify_docker_integration.sh
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v8.md
---

# Plan Review Report: Phase 5 Quality Gate (Docker-First) — Tonemap + Feature Parity Gaps

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Plan Reference:** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md

This RUN_ID is blocked by a new Docker-only failure (`verify-v3.md`): libplacebo tonemapping fails (bit-depth requirement + Vulkan context creation). The approved plan (`plan-v5.md`) does not cover this.

Separately, a parity gap was identified: the legacy “auto-tonemap screenshots when HDR and config enables it” feature is **not wired into the runtime pipeline** (config key exists but is unused), and VSPreview integration is also unimplemented (config key exists but is unused). These parity items are important, but must be planned as **separate follow-up RUN_IDs** to avoid expanding an already-iterated quality-gate run into a multi-week scope change.

## Verdict Rationale (Single Path Forward)

**Mandated path (no alternatives):**

1. Fix Docker so libplacebo/vs-placebo can actually create a headless device (Docker is the real baseline).
2. Align `src/frame_compare/vs/tonemap.py` with the SSOT libplacebo rules (RGB48/16-bit input) and the SSOT runtime-failure fallback behavior.
3. Expand the Docker gate to run the full intended suite (`tests/integration/` + `tests/vs/`) with zero skips.
4. After the Docker gate is green, open separate parity/spec runs for auto-tonemap wiring and VSPreview integration (do not piggyback onto this RUN_ID).

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | FAIL | plan-v5 does not include the Docker libplacebo failure; parity wiring must be split into new follow-up runs. |
| 2 | Dependencies | FAIL | Docker fix spans Docker build/runtime + tonemap implementation + Docker gate test selection. |
| 3 | File List | FAIL | No file list exists for the Docker libplacebo fix in plan-v5. |
| 4 | Contract Impact | PASS | No canonical contract edits required for the Docker tonemap fix. |
| 5 | Types Complete | FAIL | The next plan must explicitly anchor the runtime-failure fallback behavior (already in `vs-module.md`) and list any new/changed helper behavior in backticked one-line signatures. |
| 6 | Tests Complete | FAIL | Missing explicit tests for “libplacebo present-but-raises → fallback used” and for expanded Docker gate coverage. |
| 7 | Verification Complete | FAIL | Docker gate must run the intended suites and enforce “0 skipped”; plan-v5 verification does not cover the new failure. |
| 8 | Decision-Minimizing | FAIL | The plan must not offer “fix test vs fix code vs skip”; it must mandate the approach above. |
| 9 | Determinism Defined | PASS | Determinism rules exist; the issue is enforcement via Docker gate + wiring coverage. |

## Key Evidence (What’s Actually Broken)

### Docker libplacebo failure (blocking)
- Source: `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md`
- Error: `placebo.Tonemap: Input must be 16 bits per sample!`
- Error: `libplacebo compiled without Vulkan support! Failed creating vulkan context`

### Dockerfile proves the Vulkan failure is expected today
- Source: `Dockerfile`
- libplacebo is built with:
  - `-Dvulkan=disabled`
  - `-Dopengl=disabled`
  - `-Dshaderc=disabled`
- Therefore, vs-placebo/libplacebo cannot create a Vulkan context in the current image; the integration failure is consistent with the build flags.

### SSOT already defines the required tonemap behavior (implementation drift, not spec gap)
- Source: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
  - `### 5.2 libplacebo Integration`: mandates RGB48 (16-bit) input conversion for libplacebo.
  - `### 5.3 Fallback Handling`: mandates fallback when libplacebo is present but fails at runtime (Vulkan/context/bit-depth).
- Current implementation (`src/frame_compare/vs/tonemap.py`) still forces RGBS and raises `TonemapError` on libplacebo runtime failure, which conflicts with SSOT.

### Parity gaps (not part of this RUN_ID; require new follow-up runs)
- `enable_tonemap` exists in config but is unused in runtime code.
- `use_vspreview` exists in config but is unused in runtime code.
- `requirements-traceability.md` references “Full pipeline” E2E tests that do not exist in `tests/` today; this is traceability drift that should be corrected as part of a parity/spec cleanup run.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

Decisions that must be removed by the revised plan:
- Docker policy: Docker must support a working libplacebo backend (headless Vulkan software path) and still have deterministic fallback if runtime creation fails.
- Docker gate policy: must run `pytest -v tests/integration/ tests/vs/` (no marker filter) and still enforce “0 skipped”.

## Concrete Edits Required (CHANGES REQUIRED)

1) **Write a revised plan for this RUN_ID**
   - Write file: `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v6.md`
   - Plan must include `## Spec Anchors (SSOT)` referencing exact headings in:
     - `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
       - `### 5.2 libplacebo Integration`
       - `### 5.3 Fallback Handling`
   - Plan must mandate the file list (minimum):
     - `Dockerfile` (enable Vulkan backend for libplacebo build + required runtime packages)
     - `src/frame_compare/vs/tonemap.py` (RGB48 conversion + runtime failure fallback)
     - `tests/vs/test_tonemap.py` (unit test for “libplacebo present-but-raises → fallback used”)
     - `tests/vs/test_integration.py` (Docker integration smoke should pass deterministically)
     - `tools/verify_docker_integration.sh` (remove marker filter; run `tests/integration/` + `tests/vs/`)
     - `docker-compose.yml` only if explicit Vulkan environment variables are required

2) **Docker build/runtime must be explicit and reproducible**
   - The plan must specify:
     - The exact `meson` flags to enable libplacebo Vulkan support (remove `-Dvulkan=disabled`).
     - The exact runtime packages required for a headless Vulkan software path (e.g., Vulkan loader + software ICD).
     - Any required env wiring (if needed) and where it lives (`Dockerfile` vs `docker-compose.yml`).

3) **Docker gate expansion is required**
   - The plan must update `tools/verify_docker_integration.sh` to run:
     - `python -m pytest -v tests/integration/ tests/vs/`
   - The plan must keep the “zero skips” requirement.

4) **Create separate parity/spec follow-up RUN_IDs (do not expand this run)**
   - Follow-up runs must cover:
     - Auto-tonemap wiring into the actual render/orchestration pipeline, gated by:
       - `SourceInfo.is_hdr`
       - `config.color.enable_tonemap`
       - tonemap preset/target settings from config/CLI
     - VSPreview integration for manual alignment (`config.audio_alignment.use_vspreview`)
     - Parity/traceability audit updates so docs do not claim nonexistent E2E tests

## Ready for Implementation

Not ready. Requires a revised plan (`plan-v6.md`) that fixes Docker libplacebo viability, aligns tonemap implementation to SSOT, and expands the Docker gate. Parity wiring (auto-tonemap + VSPreview) must be split into separate follow-up runs.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Revision Required (Docker tonemap gate)
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v8.md
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v6.md

## Hard Rules
- Mandate exactly one approach: Docker is the real baseline; enable a headless Vulkan software path for libplacebo, and still implement deterministic runtime fallback per SSOT.
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
- Do not expand this RUN_ID to include pipeline wiring or VSPreview; create separate follow-up RUN_ID(s) for those parity/spec tasks after Docker gate passes.
