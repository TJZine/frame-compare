---
RUN_ID: 2026-01-02__meta__p5-quality-gate
VERSION: v6
TARGET: Meta → Phase 5 Quality Gate Fixes (Docker-first)
INPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v5.md
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md
  - docs/legacy_tonemap_info.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md
  - Dockerfile
  - docker-compose.yml
  - tools/verify_docker_integration.sh
  - tests/vs/test_integration.py
  - src/frame_compare/vs/tonemap.py
OUTPUTS:
  - .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v6.md
---

# Plan Review Report: Phase 5 Quality Gate (Docker Integration Setback)

## Verdict: CHANGES REQUIRED

## Review Summary
**Reviewer:** Plan Review Agent
**Date:** 2026-01-03
**Reference Plan (last approved):** .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md

This run is currently blocked by a new Docker-only failure (`verify-v3.md`): libplacebo tonemapping fails with **16-bit requirement** and **no Vulkan support**. The approved plan does not cover this failure, and the SSOT for tonemapping is now inconsistent with observed runtime constraints.

## Checklist Results

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Scope | FAIL | Plan-v5 scope does not include the new Docker libplacebo failure; needs an explicit “Docker-first tonemap compatibility” slice. |
| 2 | Dependencies | FAIL | Fix requires aligning SSOT (`vs-module.md`) + code (`src/frame_compare/vs/tonemap.py`) + Docker gate selection (`tools/verify_docker_integration.sh`). |
| 3 | File List | FAIL | No file list exists for the new failure (tonemap code + SSOT + tests + docker script + Dockerfile/plugin build flags). |
| 4 | Contract Impact | PASS | No canonical contract changes implied. |
| 5 | Types Complete | FAIL | New/changed behavior requires SSOT-defined behavior and explicit public/semipublic function behavior (fallback on libplacebo runtime failure). |
| 6 | Tests Complete | FAIL | No planned tests/assertions exist for “libplacebo present but unusable → fallback works” in Docker. |
| 7 | Verification Complete | FAIL | The verification commands must be updated to reflect the expanded Docker gate (more than the current 4 selected tests, per stated goals). |
| 8 | Decision-Minimizing | FAIL | The prompt lists multiple options; the plan must mandate exactly one approach. |
| 9 | Determinism Defined | PASS | Not central to this slice. |

## What Changed Since Approval (Evidence)

- `.agent-workflow/runs/2026-01-02__meta__p5-quality-gate/verify-v3.md` reports:
  - `placebo.Tonemap: Input must be 16 bits per sample!`
  - `libplacebo compiled without Vulkan support! Failed creating vulkan context`
- `src/frame_compare/vs/tonemap.py` currently **forces RGBS (32-bit float)** before calling `core.placebo.Tonemap`, which directly conflicts with the plugin’s 16-bit requirement.
- `Dockerfile` currently builds libplacebo with `-Dvulkan=disabled` and `-Dopengl=disabled`, so **no Docker-only code change can make libplacebo work** until the image build enables a GPU backend (Vulkan via a software ICD is the intended headless path).
- `docs/legacy_tonemap_info.md` indicates the legacy pipeline tonemapped from **RGB48** (16-bit), which aligns with the libplacebo requirement and should inform the SSOT update.
- SSOT in `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` currently mandates an **RGBS Conversion Rule shared by libplacebo and fallback**, and references `clip.std.core` for core access; both are now inconsistent with verified behavior.

## Required Decision (Mandated by Plan Review)

**Mandated approach (single path): Fix Docker + fix code + keep deterministic runtime fallback.**

1. **Docker image must enable a libplacebo backend**: stop building libplacebo with Vulkan disabled; use a headless Vulkan software ICD (e.g., Mesa lavapipe) so vs-placebo can create a device in Docker.
2. **Code must satisfy libplacebo’s 16-bit input requirement**: ensure libplacebo is fed RGB48 (16-bit) input (legacy-aligned), and only then run `core.placebo.Tonemap`.
3. **Runtime fallback must be defined**: if libplacebo is present but still fails at runtime (device/context), fall back to `_fallback_tonemap` instead of raising `TonemapError`. This makes Docker and non-Docker behavior robust.

## SSOT Update Audit (Required)

Planning must update SSOT so implementation is not forced to guess:

- File: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
- Sections to update:
  - `### 5.2 libplacebo Integration`
  - `### 5.3 Fallback Handling`
- Audit finding: The new Docker failure proves the SSOT’s “RGBS Conversion Rule shared by libplacebo and fallback” is not universally valid; SSOT must specify a **libplacebo-specific input format rule** and a **runtime failure fallback rule**.

## Concrete Edits Required (CHANGES REQUIRED)

1. **Update SSOT for libplacebo bit depth + core access (blocking)**
   - Edit file: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
   - Under heading: `### 5.2 libplacebo Integration` add/change:
     - Replace the “shared RGBS conversion rule” with a **legacy-aligned libplacebo rule**:
       - Convert to RGB48 (16-bit) before `core.placebo.Tonemap`.
       - Define the canonical internal format returned from `apply_tonemap` (if RGBS remains canonical, define the post-libplacebo conversion back to RGBS and where post-processing runs).
     - Update any core access references to align with the verified fix (`vs.core`, not `clip.std.core`).
   - Under heading: `### 5.3 Fallback Handling` add/change:
     - Define that if libplacebo is present but `core.placebo.Tonemap` raises due to runtime constraints (e.g., Vulkan/context/bit depth), the implementation must **fall back** to `_fallback_tonemap` instead of raising `TonemapError`.

2. **Revise plan to include the new Docker failure (plan-v6)**
   - Add a new section for this slice with an explicit file list:
     - `src/frame_compare/vs/tonemap.py` (libplacebo input conversion + runtime fallback)
     - `tests/vs/test_integration.py` (keep tonemap enabled; assert it does not raise in Docker)
     - `tests/vs/test_tonemap.py` (add a unit test that simulates libplacebo present-but-failing and asserts fallback path is used)
     - `tools/verify_docker_integration.sh` (expand coverage to run the full `tests/vs/` suite, not only `vs_required`, to address “many integration tasks aren’t being run”)
     - `Dockerfile` (enable Vulkan backend for libplacebo build; ensure runtime has Vulkan loader + software ICD)
     - `docker-compose.yml` (if required, set env vars for Vulkan software ICD selection)

3. **Expand Docker test selection (scope expansion, required)**
   - Problem: Current Docker gate runs only `tests/integration/` plus a single `vs_required` test; most `tests/vs/` unit tests are excluded by the `-m "integration or vs_required"` filter.
   - Required change (no alternatives): Remove the marker filter for the Docker gate and run `pytest -v tests/integration/ tests/vs/` (still require zero skips).

4. **Update verification commands in the plan**
   - Add/confirm:
     - `bash tools/verify_docker_integration.sh`
     - A local non-Docker check that exercises the fallback logic deterministically (unit test), so Docker isn’t the only signal.

## Implementation Agent Decision Points Remaining

Implementation Agent Decision Points Remaining: NOT NONE

Decisions to remove in plan-v6:
- Exact SSOT-defined libplacebo input format and post-processing format.
- Dockerfile/Vulkan backend selection and env wiring (must be explicit in the plan).
- Whether to treat libplacebo runtime failure as “unavailable → fallback” vs “fatal error” (must be explicit in SSOT).

## Ready for Implementation

Not ready. Requires SSOT updates + a revised plan (`plan-v6.md`) that mandates the approach above and expands the Docker gate scope.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Planning Agent for Frame Compare 2.0.

## RUN_ID
2026-01-02__meta__p5-quality-gate

## Blocking SSOT Updates Required (Do this first)
Edit file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
- Under heading: "### 5.2 libplacebo Integration" add/change:
  - Specify a libplacebo-specific input format rule that guarantees 16-bit input (RGB48) before calling `core.placebo.Tonemap` (legacy-aligned; see `docs/legacy_tonemap_info.md`).
  - Specify whether/when to convert back to RGBS after the libplacebo call for post-processing and return value (must match tests and be deterministic).
  - Update core access references to `vs.core` (not `clip.std.core`).
- Under heading: "### 5.3 Fallback Handling" add/change:
  - Add rule: if libplacebo plugin is present but `core.placebo.Tonemap` fails due to runtime constraints (Vulkan/context/bit depth), treat it as unavailable and fall back to `_fallback_tonemap` (no raised `TonemapError`).

## Then Revise the Plan
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-review-v6.md
Read file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v5.md
Write file: .agent-workflow/runs/2026-01-02__meta__p5-quality-gate/plan-v6.md

## Hard Rules
- Plan must mandate: Dockerfile Vulkan enablement + 16-bit libplacebo input conversion + runtime fallback; no alternatives left to the Coding Agent.
- Spec Anchors must copy/paste exact SSOT headings (must pass `validate_spec_anchors.py`).
