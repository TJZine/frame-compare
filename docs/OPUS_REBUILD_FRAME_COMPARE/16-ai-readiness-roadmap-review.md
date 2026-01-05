# Frame Compare 2.0 — AI Readiness Roadmap Review Report

**Date:** 2025-12-21
**Reviewer:** Codex (Principal Engineer / Test Architect)
**Model:** GPT-5.2
**Overall Assessment:** NEEDS REVISION

> [!IMPORTANT]
> This is a **historical** review report from `2025-12-21`. The current, authoritative readiness status is `AI_READINESS_ROADMAP.md`.
>
> **Update (2025-12-26 03:56 UTC):** All three readiness gates are GREEN:
> - Contract freshness: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check` → `OK: All derived files are up-to-date`
> - Scaffold Tier‑A: `(cd docs/OPUS_REBUILD_FRAME_COMPARE/scaffold && .venv/bin/pytest -q -m tier_a)` → `86 passed, 58 deselected`
> - Traceability: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check` → `✅ All traceability references valid`

---

## Executive Summary

`AI_READINESS_ROADMAP.md` is currently **stale/inaccurate** relative to the FC‑2.0 contract enforcement scaffolding and the actual verification gates. Two “must-pass” readiness checks are red today: the scaffold Tier‑A suite and traceability validation. Until those are green and the roadmap/workflow docs are aligned to the real gates, the project is not 10/10 ready for autonomous AI implementation.

---

## Top Risks (Blocking / High Impact)

> [!CAUTION]
> - Tier‑A security invariants are failing because the scaffold is missing required APIs (`frame_compare.utils.paths.resolve_safe_path`, `frame_compare.utils.subproc.validate_subprocess_arg`) and the corresponding error classes (`docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/security/test_path_containment.py:20`, `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/security/test_subprocess_sanitization.py:22`).
> - Traceability enforcement currently fails with 38 missing test references; this breaks the “AI can implement without guessing” promise (`scripts/validate_traceability.py:2`, `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md:10`).
> - The roadmap cites non-canonical contract paths and an outdated score, which will misdirect AI agents toward already-resolved or incorrectly-scoped work (`AI_READINESS_ROADMAP.md:3`, `AI_READINESS_ROADMAP.md:29`).
> - CLI spec type hints/defaults drift from the canonical CLI contract (e.g., `--root` default and Optional typing), increasing implementation ambiguity and breaking parity guarantees (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md:61`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md:16`).
> - The agent workflow’s “verification suite” omits contract freshness and traceability gates, so agents can regress contracts without being caught (`docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md:136`).

---

## Strengths

- Canonical contract system exists and is well-scoped: `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/README.md:39`.
- Generator uses stable sentinels and supports `--check` freshness verification: `scripts/generate_contract_views.py:67`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md:14`, `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md:245`.
- Deterministic screenshots-only frame planning is specified and implemented in scaffold (`FramePlan` + locked reference outputs): `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/analysis/frame_plan.py:1`.
- VapourSynth plugin detection is pinned to a baseline and explicitly warns about namespace variance: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md:79`.

---

## Critical Issues (Block Implementation)

### 1. Tier‑A Security Suite Not Green (Paths + Subprocess Sanitization)

| Attribute | Value |
|:----------|:------|
| Location | `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/security/test_path_containment.py:20` |
| Issue | Tests require `frame_compare.utils.paths.resolve_safe_path`, but the module is missing from the scaffold package. |
| Impact | Tier‑A suite fails; AI agents cannot trust security invariants or use the scaffold as a runnable starting point. |
| Fix | Implement `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/utils/paths.py` and wire it to FC‑3009 errors from `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml:158`. |

Also:

| Attribute | Value |
|:----------|:------|
| Location | `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/security/test_subprocess_sanitization.py:22` |
| Issue | Tests require `frame_compare.utils.subproc.validate_subprocess_arg`, but scaffold exports `sanitize_arg` and defines custom exceptions not aligned to the error taxonomy expected by tests and contracts. |
| Impact | Tier‑A suite fails; subprocess hardening is ambiguous (what’s the canonical API? what exception types are raised?). |
| Fix | Standardize on a single public API: `validate_subprocess_arg(arg: str | Path) -> str`, raising error classes in `frame_compare.errors` for FC‑3010/FC‑3011 (`docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml:164`). |

**Minimal suggested diff (design intent, not applied here):**

```diff
*** Add File: docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/utils/paths.py
+from __future__ import annotations
+from pathlib import Path
+from frame_compare.errors import InvalidPathError, PathEscapesRootError
+def resolve_safe_path(path: str, root: Path) -> Path: ...

*** Update File: docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/utils/subproc.py
@@
-def sanitize_arg(arg: str) -> str:
+def validate_subprocess_arg(arg: str | Path) -> str:
+    ...
+def sanitize_arg(arg: str) -> str:
+    return validate_subprocess_arg(arg)
```

**Contract note:** The contract registry includes FC‑3009/3010/3011 (`docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml:158`), but the scaffold error hierarchy currently does not expose the specific error classes required by the security tests (`docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/security/test_subprocess_sanitization.py:23`, `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/security/test_path_containment.py:43`). That is a blocker for “security coverage 10/10”.

---

### 2. Traceability Enforcement Fails (Drift Between Matrix and Scaffold Tests)

| Attribute | Value |
|:----------|:------|
| Location | `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md:10` |
| Issue | The traceability matrix references tests that do not exist in the scaffold (e.g., `test_load_mkv`, `test_tmdb_lookup`, etc.). |
| Impact | AI agents cannot rely on traceability to decide what “done” means; CI-style enforcement via `scripts/validate_traceability.py` is currently red. |
| Fix | Choose one policy and enforce it: (A) create stub tests with those names (skipped, but present), or (B) update the traceability matrix to reference the real stub suite and adjust the validator to check file/section anchors instead of function names. |

Evidence:

- Validator expects referenced tests to exist: `scripts/validate_traceability.py:49`
- Current E2E suite is a stub with different names and uses an unregistered marker: `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/e2e/test_pipeline_modes.py:23`

---

### 3. AI_READINESS_ROADMAP.md Is Not a Reliable “Single Pane of Glass”

| Attribute | Value |
|:----------|:------|
| Location | `AI_READINESS_ROADMAP.md:3` |
| Issue | The roadmap reports “8/10” and references non-canonical contract locations (`contracts/cli_flags.yaml`) and outdated deltas. |
| Impact | AI agents and humans will chase the wrong work items and/or assume gates are green when they are not. |
| Fix | Make the roadmap “gate-driven”: list the required verification commands and record their last known pass/fail status; link directly to canonical paths under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`. |

---

### 4. CLI Spec Drifts From Canonical Flag Contract (Types + Defaults)

| Attribute | Value |
|:----------|:------|
| Location | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md:61` |
| Issue | Option typing and defaults don’t match the canonical CLI contract. Example: `--root` is `Path` with default `.` in the canonical flag table, but the spec uses `root: Path = typer.Option(None, ...)`. |
| Impact | An implementation agent must guess whether `None` is valid and how to resolve the workspace root, risking parity regressions. |
| Fix | Align the spec signature and defaults to `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml` and keep Optional types explicit per Typer conventions. |

Canonical reference:

- `--root` default is `.`: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md:16`

Typer guidance (official docs):

- Optionality is driven by defaults; if the default is `None`, the type should be Optional for correctness in static analysis: source:https://github.com/fastapi/typer/blob/master/docs/tutorial/arguments/default.md (retrieved 2025-12-21 via Context7).

---

### 5. Agent Workflow Missing Contract + Traceability Gates

| Attribute | Value |
|:----------|:------|
| Location | `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md:136` |
| Issue | The “Run Full Verification Suite” omits two repo-critical gates: contract freshness (`scripts/generate_contract_views.py --check`) and traceability validation (`scripts/validate_traceability.py --check`). |
| Impact | Agents can “green” a task while silently regressing canonical contracts/derived views or leaving traceability broken. |
| Fix | Add those commands to the Verification Agent template and the human orchestrator workflow, and declare them required for “ready for implementation”. |

---

## Moderate Issues (Should Fix)

### 1. Unknown pytest mark in E2E stubs

- **Location:** `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/e2e/test_pipeline_modes.py:23`
- **Issue:** Uses `pytest.mark.tier_b`, but only `tier_a`, `vs_required`, `slow`, and `e2e` are registered (`docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/conftest.py:12`).
- **Fix:** Register `tier_b` in `conftest.py` or switch to the existing `e2e` marker.

### 2. Subprocess hardening contract naming inconsistency

- **Location:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/security-invariants.md:69`
- **Issue:** Doc specifies `sanitize_subprocess_arg`, scaffold uses `sanitize_arg`, tests require `validate_subprocess_arg`.
- **Fix:** Pick one name for the public utility API and use it everywhere (docs/spec/tests/scaffold).

---

## Minor Issues / Suggestions

1. Several docs use `python ...` commands, but `python` may not be on PATH in some environments; prefer `uv run python ...` or `.venv/bin/python ...` consistently (`docs/OPUS_REBUILD_FRAME_COMPARE/contracts/README.md:25`, `scripts/validate_traceability.py:1`).
2. Generated CLI contract output uses `Any` in the generated dict type (`scripts/generate_contract_views.py:154`); consider a `TypedDict` (P2) if strict type surfaces are required.

---

## Feature Parity & Traceability

| Feature (v0.0.14) | Spec Reference | Test Plan | Error Codes |
|:------------------|:---------------|:----------|:------------|
| Video Loading | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md:203` | ❌ (traceability references missing tests) | FC-3002/FC-4015/FC-2003 |
| Frame Selection | `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/analysis/frame_plan.py:50` | ✅ contract test exists (`test_frame_plan.py`) | FC-3004/FC-4012 |
| Screenshot Render | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md` | ❌ (traceability references missing tests) | FC-4004/FC-2005 |
| slow.pics Upload | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md` | ✅ policy test exists (`test_upload_policy.py`) | FC-5010/FC-5011 |

**Unmapped Features:** Many traceability entries currently point to non-existent test functions and therefore are not verifiable (`docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md:10`).

---

## Scalability Findings

| Smell | Location | Why It’s Churny | Lower-Churn Alternative |
|:------|:---------|:----------------|:------------------------|
| Test references as free-text strings | `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md:10` | Renames cause mass churn; validator is brittle to naming. | Validate file existence + anchored section IDs; allow stub tests but require stable filenames/markers. |
| Multiple names for one security function | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/security-invariants.md:69` | Refactors break tests/docs unexpectedly. | Standardize one public API name and re-export it. |

### Refactor Pressure Test Results

| Change | Estimated Edits | Verdict |
|:-------|:---------------|:--------|
| Add CLI flag | 1 canonical YAML + regen derived views | ✅ (contract-driven) |
| Add config field | 1 JSON schema + regen derived views | ✅ (contract-driven) |
| Rename/move internal module | Several imports + import-linter updates | ⚠️ (needs stable re-exports) |
| Add new upload target | New service module + new contract tests | ⚠️ (acceptable, but needs a target registry contract) |

---

## Mode Matrix (Modularity / Skippability)

| Mode | Enabled Phases | Required Deps | Outputs | Skip Rules | Error Codes |
|:-----|:---------------|:--------------|:--------|:-----------|:------------|
| Screenshots-only | FramePlan → Render | VS or FFmpeg | PNGs | Analysis skipped; deterministic uniform seeded selection | FC-200x/FC-4004 |
| Upload-enabled | Render → Publish | Network | URL | SSRF allowlist enforced | FC-5010/FC-5011 |

**Screenshots-Only Viable:** ✅ (algorithm + contract tests exist: `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/analysis/frame_plan.py:50`)
**Skip Semantics Explicit:** ⚠️ (full pipeline mode matrix still requires E2E acceptance tests; current E2E suite is skipped stubs: `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/e2e/test_pipeline_modes.py:37`)

---

## VapourSynth Toolchain Findings

| Plugin | Required For | Detection | Fallback | Error Code | Status |
|:-------|:-------------|:----------|:---------|:-----------|:-------|
| lsmas (`lsmas`) | Source loading | `core.lsmas.LWLibavSource` | FFmpeg | FC-2003 | ✅ spec’d |
| libplacebo | Tonemapping | `core.placebo.Tonemap` | basic | FC-2003/FC-2004 | ✅ spec’d |

Status is “spec’d”, but still needs a smoke-test in the pinned baseline to be 10/10 ready.

---

## Contract Alignment Matrix

| Domain | Canonical | Derived | Generator | Freshness Test | Status |
|:-------|:----------|:--------|:----------|:---------------|:-------|
| CLI Flags | `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml` | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md` | `scripts/generate_contract_views.py` | `test_derived_views_fresh.py` | ✅ |
| Error Codes | `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml` | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` | `scripts/generate_contract_views.py` | `test_derived_views_fresh.py` | ✅ |
| Config | `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/config_schema.json` | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md` | `scripts/generate_contract_views.py` | `test_derived_views_fresh.py` | ✅ |
| Layers | `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/pyproject.toml` | `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md` | `scripts/generate_contract_views.py` | `test_derived_views_fresh.py` | ✅ |
| Error Output | `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_output_schema.json` | — | — | `test_json_error_shape.py` | ✅ |
| Traceability | `docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/requirements-traceability.md` | — | `scripts/validate_traceability.py` | `scripts/validate_traceability.py --check` | ❌ |

---

## Best Practices Audit (Selective)

| Area | Status | Notes |
|:-----|:------:|:------|
| Pydantic Settings sources | ⚠️ | Ensure spec explicitly fixes source precedence and documents `settings_customise_sources` (pydantic-settings docs). |
| httpx lifecycle | ⚠️ | Specs should require `async with httpx.AsyncClient()` and explicit timeouts (httpx docs). |
| Typer option typing | ⚠️ | Align Optional types with defaults; avoid `Path` with default `None`. |

---

## Security & Reliability Audit

| Invariant | Error Code | Tested | Status |
|:----------|:-----------|:-------|:-------|
| Path containment | FC-3009 | ✅ (Tier‑A test) | ❌ (missing implementation + error types) |
| Subprocess safety | FC-3010/3011 | ✅ (Tier‑A test) | ❌ (missing API + error types) |
| SSRF prevention | FC-5010/5011 | ✅ (Tier‑A test) | ✅ |
| Secrets redaction | — | ✅ (Tier‑A test exists) | ✅ |
| Ctrl+C cleanup | Exit 130 | ❌ | ⚠️ (spec’d in docs, needs tests) |

---

## AI Agent Readiness Score

**Overall Score:** 6/10

| Dimension | Score | Justification |
|:----------|:-----:|:--------------|
| Spec precision | 7/10 | Contracts and phase ordering exist; key security APIs still inconsistent. |
| Code samples accuracy | 6/10 | Several module specs still use placeholders; optional typing drift exists. |
| Done criteria clarity | 5/10 | Traceability validator is red; “done” can’t be enforced. |
| Error recovery guidance | 6/10 | Good contracts; cancellation/cleanup needs tests. |
| Contract enforcement | 7/10 | Generator + sentinels + freshness test exist; but workflow docs omit the gates. |
| Anti-churn scalability | 7/10 | Canonical contracts reduce churn; traceability naming is brittle. |
| Modularity / skippability | 8/10 | `--skip-analysis` deterministic planning exists; full E2E mode suite is stubbed. |
| VapourSynth correctness | 8/10 | Baseline pinned + detection patterns spec’d; needs baseline smoke-test. |
| Security coverage | 4/10 | Two core invariants are red in Tier‑A. |

---

## Action Plan

### Priority 1 (Blocks Implementation)

1. Make Tier‑A security invariants green by implementing `utils.paths.resolve_safe_path`, standardizing `utils.subproc.validate_subprocess_arg`, and adding the missing error classes (FC‑3009/3010/3011) in `frame_compare.errors`.
2. Repair traceability enforcement: either create stub tests matching the traceability matrix or update the matrix + validator to match the real stub suite.
3. Update `AI_READINESS_ROADMAP.md` to be gate-driven with real verification commands and canonical paths.

### Priority 2 (Should Fix Before Implementation)

1. Align CLI spec types/defaults with the canonical `cli_flags.yaml` contract (especially `--root` default and Optional typing).
2. Add contract freshness + traceability checks to agent workflow verification steps.

### Priority 3 (Nice to Have)

1. Replace `Any` usage in generated CLI flag dict with a `TypedDict` for stricter surfaces.
2. Add a pinned baseline VS smoke test command and document expected “doctor” output fields.

---

## Appendix: Verification Commands (Historical Snapshot)

> This appendix reflects the verification command set discussed during the original `2025-12-21` review.
> The current SSOT for readiness gate commands is:
> - `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`
> - Rendered in `AI_READINESS_ROADMAP.md`

- Contract views freshness: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
- Scaffold Tier‑A suite: `(cd docs/OPUS_REBUILD_FRAME_COMPARE/scaffold && .venv/bin/pytest -q -m tier_a)`
- Traceability validation: `UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
