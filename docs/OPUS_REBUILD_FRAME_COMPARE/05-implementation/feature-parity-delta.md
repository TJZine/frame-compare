# Feature Parity Delta Report — Frame Compare 2.0

> **Purpose:** Explicit legacy → 2.0 feature mapping with implementation status
> **Last Updated:** 2026-01-03
> **Status:** Pre-Runner implementation phase

---

## 1. Executive Summary

This document identifies the feature parity gaps between legacy Frame Compare (v0.0.14) and the Frame Compare 2.0 rebuild. It serves as the central truth table driving SSOT spec updates and subsequent implementation work.

### Critical Gaps Requiring Spec Closure

| Gap ID | Feature | Status | Blocking Runner? |
|:-------|:--------|:-------|:-----------------|
| GAP-001 | Auto-Tonemap Wiring | **MISSING** | Yes |
| GAP-002 | Runner/Orchestration Package | **MISSING** | Yes |
| GAP-003 | VSPreview Manual Alignment | **MISSING** | No (optional) |
| GAP-004 | FramePlan Skip-Analysis | **MISSING** | Yes |
| GAP-005 | E2E Test Coverage | **MISSING** | No (verification) |

---

## 2. Feature Parity Matrix

### 2.1 Core Pipeline Features

| Feature ID | Legacy Feature | 2.0 Status | SSOT Anchor | Code Anchor | Test Anchor |
|:-----------|:---------------|:-----------|:------------|:------------|:------------|
| F-001 | Video Loading (lsmas) | ✅ Implemented | [vs-module.md §3.2](module-specs/vs-module.md#32-source-loading) | `vs/loader.py`, `vs/source.py` | `tests/vs/test_loader.py` |
| F-002 | HDR Detection | ✅ Implemented | [vs-module.md §5.1](module-specs/vs-module.md#51-hdr-detection) | `vs/props.py` | `tests/vs/test_props.py` |
| F-003 | PQ Tonemapping | ✅ Implemented | [vs-module.md §3.3](module-specs/vs-module.md#33-tonemapping) | `vs/tonemap.py` | `tests/vs/test_tonemap.py` |
| F-004 | HLG Tonemapping | ✅ Implemented | [vs-module.md §3.3](module-specs/vs-module.md#33-tonemapping) | `vs/tonemap.py` | `tests/vs/test_tonemap.py` |
| F-005 | Frame Selection (Analysis) | ✅ Implemented | [analysis-module.md §3.2](module-specs/analysis-module.md#32-frame-selection) | `analysis/selection.py` | `tests/analysis/test_selection.py` |
| F-006 | Screenshot Render | ✅ Implemented | [render-module.md §3.1](module-specs/render-module.md#31-frame-rendering) | `render/orchestrator.py` | `tests/render/test_orchestrator.py` |
| F-007 | Audio Alignment | ✅ Implemented | [services-module.md §2.2](module-specs/services-module.md#22-public-api) | `services/alignment.py` | `tests/services/test_alignment.py` |
| F-008 | slow.pics Upload | ✅ Implemented | [services-module.md §4.2](module-specs/services-module.md#42-public-api) | `services/publishers.py` | `tests/services/test_publishers.py` |
| F-009 | TMDB Metadata | ✅ Implemented | [services-module.md §3.2](module-specs/services-module.md#32-public-api) | `services/metadata.py` | `tests/services/test_metadata.py` |
| F-010 | HTML Report | ✅ Implemented | [services-module.md §6.2](module-specs/services-module.md#62-public-api) | `services/report.py` | `tests/services/test_report.py` |
| F-011 | Metrics Caching | ✅ Implemented | [analysis-module.md §5](module-specs/analysis-module.md#5-cache-strategy) | `analysis/cache_io.py` | `tests/analysis/test_cache_io.py` |
| F-012 | CLI Interface | ⚠️ Partial | [cli-module.md §2.1](module-specs/cli-module.md#21-command-structure) | `cli_entry.py` | `tests/cli/test_cli_commands.py` |
| F-013 | Config Loading | ✅ Implemented | [config-module.md §3](module-specs/config-module.md#3-public-api) | `config/loader.py` | `tests/config/test_loader.py` |

### 2.2 Missing Integration Features (GAP Details)

#### GAP-001: Auto-Tonemap Wiring (HDR → SDR in Render Pipeline)

| Aspect | Details |
|:-------|:--------|
| **Legacy Behavior** | `vs_core.process_clip_for_screenshot` applies tonemap before geometry, writes tonemapped clip to disk |
| **2.0 Current State** | `apply_tonemap()` exists in `vs/tonemap.py` but render pipeline (`render/orchestrator.py`) never calls it |
| **Config Key** | `config.color.enable_tonemap` exists in schema but is not consumed at runtime |
| **Blocking** | Runner phase — HDR sources will produce wrong screenshots |
| **Fix Required** | Spec render-module.md to add tonemap integration point, implement in orchestrator |

---

#### GAP-002: Runner/Orchestration Package

| Aspect | Details |
|:-------|:--------|
| **Legacy Behavior** | `orchestration/coordinator.py` + `phases/` directory manage full pipeline |
| **2.0 Current State** | `src/frame_compare/orchestration/` exists and implements preflight/doctor/progress; runner/phases execution remains incomplete |
| **SSOT State** | `orchestration-module.md` spec exists and includes `ClipState`/probe cache; remaining Phase 6.7–6.8 work is tracked in the master checklist |
| **CLI State** | `cli_entry.py` prints `"[stub] <command>: Not yet implemented"` for run/wizard/doctor/preset |
| **Blocking** | Cannot run end-to-end without orchestration layer |
| **Fix Required** | Complete orchestration-module.md spec with minimal API surface, then implement |

---

#### GAP-003: VSPreview Manual Alignment Override

| Aspect | Details |
|:-------|:--------|
| **Legacy Behavior** | Interactive `vspreview` mode lets user verify/adjust audio sync, manual offsets persist |
| **2.0 Current State** | `use_vspreview: bool` exists in config and `AlignmentConfig` but is not consumed |
| **SSOT State** | `vspreview-module.md` + `services-module.md` define the interaction contract; implementation remains pending |
| **Blocking** | Optional feature — can launch Runner without this |
| **Fix Required** | Create vspreview-module.md spec, update services-module.md with interaction contract |

---

#### GAP-004: FramePlan Skip-Analysis Path

| Aspect | Details |
|:-------|:--------|
| **Legacy Behavior** | `--skip-analysis` uses seeded uniform sampling for frame selection |
| **2.0 Current State** | FramePlan is specified but not implemented (`src/frame_compare/analysis/frame_plan.py` missing) |
| **SSOT State** | `frame-plan-module.md` exists with exact algorithm + tests |
| **Code State** | Scaffold references are non-authoritative; SSOT is `frame-plan-module.md` and target implementation path is `src/frame_compare/analysis/frame_plan.py`. |
| **Blocking** | Cannot implement `--skip-analysis` without deterministic algorithm spec |
| **Fix Required** | Create frame-plan-module.md with exact algorithm |

---

#### GAP-005: E2E Test Coverage

| Aspect | Details |
|:-------|:--------|
| **Legacy Behavior** | Full pipeline tests in `tests/` |
| **2.0 Current State** | E2E coverage exists but is minimal (e.g., CLI version); full pipeline E2E remains PLANNED. |
| **Traceability Claim** | requirements-traceability.md §4 lists test names that do not exist |
| **Blocking** | Verification only — not blocking implementation |
| **Fix Required** | Update requirements-traceability.md to mark tests as PLANNED |

---

#### GAP-006: Analysis Lead/Trailer Ignore Window

| Aspect | Details |
|:-------|:--------|
| **Legacy Behavior** | Frame selection can skip intro/outro via config (e.g., `ignore_lead_seconds`). |
| **2.0 Current State** | No corresponding config key or algorithm contract present in 2.0 SSOT for selection boundaries. |
| **Blocking** | Optional for Runner MVP; impacts parity and determinism for selection modes. |
| **Fix Required** | Mark as DEFERRED (define config keys + boundary rules) or DE-SCOPED (explicitly state not supported). |

---

#### GAP-007: Per-File Overrides (Trim/FPS)

| Aspect | Details |
|:-------|:--------|
| **Legacy Behavior** | Users can define per-file overrides for trim and FPS in `[overrides]`. |
| **2.0 Current State** | `ConfigSchema` does not define an `overrides` section; orchestration specs must not reference `config.overrides`. |
| **Blocking** | Optional for Runner MVP; current spec-to-code alignment requires correction. |
| **Fix Required** | Remove `config.overrides` references from specs and track overrides as DEFERRED with a planned schema/spec anchor. |

---

#### GAP-008: Tonemap QA/Strictness Policy

| Aspect | Details |
|:-------|:--------|
| **Legacy Behavior** | Tonemap flow includes verification/stamping; strict mode can abort on overlay/verification failures. |
| **2.0 Current State** | Tonemap wiring + VS-missing fail-fast policy is specified; strictness/verification/stamping parity is not defined. |
| **Blocking** | Optional for Runner MVP; must be explicitly DEFERRED/DE-SCOPED to avoid implementer guesses. |
| **Fix Required** | Add an explicit SSOT decision for strictness/verification (scope + module anchor). |

---

#### GAP-009: Run Snapshot / Last-Run State Artifact

| Aspect | Details |
|:-------|:--------|
| **Legacy Behavior** | Persists a last-run snapshot (e.g., `.frame_compare.run.json`). |
| **2.0 Current State** | No SSOT contract for a run snapshot artifact. |
| **Blocking** | Optional for Runner MVP; impacts reproducibility/debugging parity. |
| **Fix Required** | Mark as DEFERRED with planned artifact path + schema, or explicitly DE-SCOPED. |

---

## 3. Config Keys Without Runtime Consumers

| Config Key | Schema Location | Runtime Consumer | Status |
|:-----------|:----------------|:-----------------|:-------|
| `color.enable_tonemap` | `config/schema.py:117` | None | ❌ Not consumed |
| `audio_alignment.use_vspreview` | `config/schema.py:103` | None | ❌ Not consumed |
| `audio_alignment.use_vspreview` | `services/types.py:25` | None | ❌ Not consumed |

---

## 4. Spec-to-Code Drift

### 4.1 Orchestration Gap

- **Spec:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
- **Expected Code:** `src/frame_compare/orchestration/` (coordinator.py, phases.py, runner.py, doctor.py, preflight.py)
- **Actual:** Directory does not exist

### 4.2 FramePlan Gap

- **Spec Reference:** render-module.md §1.3 references `contracts/phase_ordering.yaml` and `scaffold/src/frame_compare/analysis/frame_plan.py`
- **Expected Spec:** `frame-plan-module.md`
- **Actual:** No frame-plan module spec exists

### 4.3 Tonemap Integration Gap

- **Spec:** vs-module.md defines `apply_tonemap()` signature
- **Required Caller:** `src/frame_compare/render/orchestrator.py::render_screenshots()` MUST apply tonemap once per clip (after load, before any frame extraction) when gated by HDR detection and `config.color.enable_tonemap`.
- **Actual:** `grep -r "apply_tonemap" src/frame_compare/render/` returns 0 results

---

## 5. Traceability Drift Summary

`requirements-traceability.md` now marks pipeline E2E tests as **PLANNED** with target file paths and marker policy.
No further traceability action is required in this parity-closure phase.

---

## 6. Recommended Spec Closure Order

1. **Task E (This Document)** — Establishes truth table
2. **Task A (Tonemap Wiring)** — Required for correct HDR screenshots
3. **Task D (FramePlan)** — Required for `--skip-analysis` path
4. **Task B (Orchestration)** — Required to wire everything together
5. **Task C (VSPreview)** — Optional, can defer past Runner MVP
