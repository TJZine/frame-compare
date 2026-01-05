# Frame Compare 2.0 — Plan Review Report

> [!IMPORTANT]
> This file is **historical** (preserved for context only) and is **not** part of the 5-agent run-directory workflow.
> Canonical readiness/workflow/prompt sources: `AI_READINESS_ROADMAP.md`, `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`, `docs/OPUS_REBUILD_FRAME_COMPARE/agent-prompts/`.

**Date:** 2025-12-20
**Reviewer:** Codex CLI (Principal Engineer / Test Architect)
**Model:** GPT-5.2
**Overall Assessment:** NEEDS REVISION

---

## Implementation Agent Preamble (Opus 4.5)

### Ideal Agent Persona

You are **Claude Opus 4.5** acting as a **Senior Contract/Test Engineer**. Your mission is to implement the fixes described in this report with **zero new user-facing features**, **minimal churn**, and **contract-first enforcement**.

### Non-Negotiable Constraints

- **Do not add new features or flags.** Only implement what is specified here.
- **Do not parse markdown tables as authority.** Canonical authority is YAML/JSON under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`.
- **Tier‑A only** for contract/security enforcement: no VapourSynth runtime, no network, no docker needed.
- **No `Any` leakage** in public surfaces: use a JSON-safe union type for JSON payloads.
- **Prefer deterministic behavior** over heuristics (especially for `--skip-analysis`).

### Context Files (Read in This Order)

1. `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/README.md`
2. `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml`
3. `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/config_schema.json`
4. `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml`
5. `scripts/generate_contract_views.py`
6. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md`
7. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md`
8. `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md`
9. `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_derived_views_fresh.py`
10. `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_layers_contract.py`
11. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/orchestration-module.md`
12. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md`
13. `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md`

### Required Verification Commands

Run these at the end of implementation:

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
(cd docs/OPUS_REBUILD_FRAME_COMPARE/scaffold && .venv/bin/pytest -q -m tier_a)
```

If you modify any runtime Python code in the main project (not just docs/scaffold), also run:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check
.venv/bin/pytest -q
```

### Implementation Status (2025-12-20)

- The “Contract Enforcement” checklist items A–F and the related blocking gaps are implemented; the scaffold’s Tier‑A suite passes when run from the scaffold directory.
- Before merging, ensure the new scaffold files and this report are committed (they may appear as untracked in `git status`).

### Follow-ups Status (2025-12-20)

- TOML parsing for layers is now `tomllib`-based in `scripts/generate_contract_views.py`.
- Error details redaction is now deep (nested dict/list) in `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/errors.py`.

---

## Executive Summary

The plan has a strong contract-driven spine (canonical YAML/JSON + generator + sentinel blocks), but it currently fails the non‑negotiable “no guessing” bar for **modular/skippable execution** and **AI implementation readiness**. Multiple documents disagree on canonical file locations, CLI surface area, and skip semantics, and several module specs contain placeholders or type holes that force an implementation agent to invent behavior.

---

## Re-Review Delta (Current Repo State)

### Resolved Since Initial Review

- Deterministic screenshots-only selection exists + locked tests (`docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/analysis/frame_plan.py:46`, `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_frame_plan.py:1`).
- Generator enforces strict sentinels + canonical paths + dual-authority guard (`scripts/generate_contract_views.py:67`, `scripts/generate_contract_views.py:458`).
- CI enforces contract views freshness (`.github/workflows/ci.yml:71`).
- Scaffold copy hygiene is enforced via `git ls-files` test (`docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_scaffold_cleanliness.py:62`).
- Layers contract no longer “skips on missing sentinel”, and layers are TOML-parsed (`docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_layers_contract.py:23`).

### Remaining “Broader” Gaps (Full Pipeline Readiness)

- ~~VS plugin detection spec is internally contradictory~~ ✅ Resolved: Detection tied to repo-root `Dockerfile` baseline (R73); `doctor --json` includes `discovered_namespace`.
- ~~Network/service lifecycle is underspecified~~ ✅ Resolved: `cli-module.md:L325-334` documents ownership; `async-semantics.md:L214-255` defines cleanup.
- Public-facing specs still contain `Any` and placeholders (`...`), which blocks “AI implement from spec without questions” (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md:37`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md:148`).
- ~~Security invariants are "planned"~~ ✅ Resolved: Tier-A tests for path containment, subprocess, SSRF, secrets redaction.
- ~~Feature parity/traceability aspirational~~ ✅ Resolved: `scripts/validate_traceability.py` exists + CI wired.

---

## Fix Specs (Implementation-Ready)

This section turns the “Fix” bullets into deterministic requirements with clear acceptance tests so an implementation agent can execute without interpretation.

### Flag/Config Precedence Rules (Authoritative)

**Source precedence for config values** (already implied by config spec): CLI overrides/init > ENV > TOML > defaults (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/config-module.md:L303`).

**Phase enable/disable precedence** (this report makes it explicit and testable):

1. **Explicit skip flags win** over config: `--skip-analysis/--skip-metadata/--skip-dovi` always disable their phase.
2. **Explicit enable config wins** only when no skip flag is set.
3. **Hard dependencies**: if a required dependency for an enabled phase is missing, fail with the phase’s FC code; if the phase is skipped/disabled, missing deps must not block.

| Concern | Inputs | Precedence | Conflict Policy | Error |
|:--------|:-------|:-----------|:----------------|:------|
| Analysis on/off | `--skip-analysis`, `analysis.selection_mode`, `analysis.frame_count`, cache flags | `--skip-analysis` disables; else analysis enabled | None | FC-4012/FC-4002 only when analysis enabled |
| Cache read/write | `--no-cache`, `--from-cache-only` | `--from-cache-only` implies **read-only**; `--no-cache` implies **no read, no write** | If both set: fail fast | FC-1003 (config/arg validation) |
| Upload on/off | `--no-upload`, `slowpics.auto_upload` | `--no-upload` disables; else use config | None | FC-5002 only when upload enabled |
| Metadata on/off | `--skip-metadata`, `tmdb.enabled` | `--skip-metadata` disables; else use config | None | TMDB failures never fail run when metadata optional (warn) |
| Dovi on/off | `--skip-dovi`, `dovi.enable` | `--skip-dovi` disables; else use config | None | FC-2007/FC-4018 only when dovi enabled |

**Acceptance tests (minimum):**

- `test_cache_flags_conflict_fails`: passing both `--no-cache` and `--from-cache-only` fails with a config/arg error (no partial behavior).
- `test_skip_metadata_overrides_config_enabled`: TMDB config enabled + `--skip-metadata` results in zero TMDB calls.

### `--json` Output Mode (Pinned Semantics)

To avoid inventing a new success schema, this report defines:

- `--json` changes **error output** for all commands to conform to `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_output_schema.json`.
- `doctor --json` prints a stable `DoctorReport` JSON object on success.
- `run --json` does **not** define a success schema; it only changes error/progress formatting (do not invent a `RunResult` JSON contract yet).

**Acceptance tests (minimum):**

- `test_json_error_envelope_validates_schema`: a forced failure under `--json` validates against `error_output_schema.json`.
- `test_doctor_json_success_shape`: doctor success output is valid JSON and matches the `DoctorReport` contract below.

### Phase Wiring Matrix (Deterministic, Skippable)

This matrix is the single source of truth for orchestration ordering and skip conditions. “Inputs/Outputs” are the stable contracts tests should target.

| Phase | Must Run | Skip Condition | Inputs | Outputs | Failure Codes |
|:------|:---------|:---------------|:-------|:--------|:--------------|
| Preflight | ✅ | never | root/config path, env | `WorkspacePaths`, `ConfigSchema`, clip list | FC-1001/1002/1003, FC-3006/3001/3009 |
| LoadSources | ✅ | never | clip paths, VS/FFmpeg availability | `SourceInfo` or FFmpeg probe info | FC-2001/2003/2005, FC-4015 |
| FramePlan | ✅ | never | `num_frames`, `frame_count`, `seed`, `skip_analysis` | `FramePlan` | FC-3004 |
| Analyze | ⚠️ | `--skip-analysis` | clips (VS), analysis config | metrics + selection | FC-4002/4012 |
| Render | ✅ | never | `FramePlan`, renderer choice, overlay mode | PNGs | FC-2005/2006, FC-4004/4014 |
| Publish | ⚠️ | `--no-upload` or `slowpics.auto_upload == false` | screenshot dir, metadata | slow.pics URL | FC-5010/5011, FC-5002/5003/5004 |
| Metadata | ⚠️ | `--skip-metadata` or `tmdb.enabled == false` | title guess, tmdb key | `TmdbMetadata \| None` | FC-5005/5006 (warn-only by policy) |
| Dovi | ⚠️ | `--skip-dovi` or `dovi.enable == false` | video paths, dovi_tool | `DoviMetadata \| None` | FC-2007/4018 |
| Report | ⚠️ | `report.enable == false` | screenshots + URLs | HTML report | FC-4017 |

**Notes that remove ambiguity:**

- “FramePlan” is mandatory even when analysis runs: analysis may contribute frames, but Render only consumes `FramePlan.frames`.
- Metadata is conceptually optional enrichment; if Publish uses metadata for a title, it must accept `None`.

### DoctorReport Contract (Stable JSON on success)

Define a stable shape so implementers don’t invent one per iteration.

```json
{
  "success": true,
  "doctor": {
    "checks": [
      {
        "id": "vapoursynth",
        "status": "pass|fail|skip",
        "details": {},
        "error": null
      }
    ]
  }
}
```

**Rules:**

- `status="skip"` is allowed only when the check is not applicable (e.g., network disabled) and must not hide missing hard deps when phases are enabled.
- `error` must use the same `ErrorContext.to_dict()` shape as `error_output_schema.json` (code/name/message/hint/details).

### Plugin Detection Playbook (Order + Reporting)

This removes “verified but varies” ambiguity by specifying an ordered probe list and required diagnostics output.

#### L-SMASH Works / source loading

Probe in order and record the discovered namespace:

1. `core.lsmas.LWLibavSource` (baseline)
2. `core.lw.LWLibavSource` (legacy alias)
3. `core.bs.VideoSource` (BestSource fallback)
4. `core.ffms2.Source` (ffms2 fallback)

If none found:

- If Render is configured to use FFmpeg (`screenshots.use_ffmpeg==true`) or renderer is `ffmpeg`, allow pipeline to continue.
- Otherwise fail with `FC-2003` (`PLUGIN_NOT_FOUND`) naming the missing plugin group (“lsmas”).

#### libplacebo tonemap

Probe:

1. `core.placebo.Tonemap`
2. Any known aliases explicitly listed in the container doc (if introduced later)

If missing:

- If tonemap enabled, use the documented fallback curve and emit a warning (do not fail), unless the plan requires strict parity mode.

**Acceptance tests (Tier‑A):**

- Unit tests that the detector reports “found namespace X” for stubbed core objects (no VS runtime).

### CI/Contract Enforcement Checklist

To prevent drift, CI must enforce the following (these are “musts”, not suggestions):

- Run `python3 scripts/generate_contract_views.py --check` in CI (enforced in `.github/workflows/ci.yml`).
- Tier‑A contract suite must fail (not skip) when sentinel markers are missing.
- Scaffold must contain no tracked build artifacts (`__pycache__`, `*.pyc`, caches).

---

## Top Risks (3-6 items)

> [!CAUTION]
>
> - **VS toolchain contract isn’t pinned**: plugin namespaces/detection are contradictory and not validated against a single reproducible environment (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md:81`).
> - **Network/service lifecycle is underspecified**: async client ownership, cancellation propagation, and retry boundaries are not pinned to a concrete code contract (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md:293`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md:67`).
> - **AI implementation readiness blocked by type holes/placeholders**: module specs still contain `Any` and `...`, forcing guesswork (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md:37`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md:148`).
> - **Full-pipeline phase ordering still incomplete**: the plan does not define deterministic ordering/outputs when enabling Publish+Metadata+Dovi+Report together (`docs/OPUS_REBUILD_FRAME_COMPARE/15-plan-review-report.md:513`).
> - **Security invariants need enforcement tests**: path containment, SSRF allowlist enforcement, and Ctrl+C cleanup are described but not pinned to concrete tests and enforcement points (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/security-invariants.md:8`).

---

## Strengths

- Contract authority is clearly documented with canonical YAML/JSON sources and derived views (`docs/OPUS_REBUILD_FRAME_COMPARE/contracts/README.md:L39`).
- Derived docs use sentinel markers for partial regeneration (config inventory, import-linter block) (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md:L14`, `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md:L245`).
- Error code registry is centralized and consistent across YAML and derived reference (`docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml:L7`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md:L17`).
- Scaffold includes Tier‑A contract tests for canonical ↔ generated parity (`docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_derived_views_fresh.py:L20`).

---

## Critical Issues (Original Review; Now Resolved for Tier‑A/Contracts)

> [!NOTE]
> The items in this section were the original blockers. They are retained for provenance, but the contract/scaffold implementation work has addressed them (see “Re-Review Delta”).

### 1. Skippable pipeline semantics not defined end-to-end

| Attribute | Value |
|:----------|:------|
| Location | `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml:L100` |
| Issue | The CLI contract introduces `--skip-analysis` and asserts a deterministic fallback (“uniform frame sampling with seed”) (`docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml:L106`), but no module spec defines: the sampling algorithm, tie-breaking, frame indexing basis, how it interacts with trims/alignment, or how Render consumes frames without an Analysis result. |
| Impact | Screenshots‑only mode cannot be implemented without inventing behavior; reproducibility guarantees are unenforceable; tests will churn when the “invented” behavior is later clarified. |
| Fix | Add a dedicated “FramePlan” contract: define `FrameSelectionPlan` type + deterministic “uniform sampling” algorithm (including rounding/spacing rules) and wire it into orchestration (e.g., `orchestration/phases.py` decides between `analysis.select_frames()` vs `analysis.uniform_sample_frames()` and always hands Render a `FramePlan`). Provide acceptance tests for: same seed ⇒ same frames, different seed ⇒ different frames, small `frame_count`/short clips, and trims. |

#### 1A. Implementation Blueprint (Deterministic “uniform sampling with seed”)

**Goal:** Make screenshots-only implementable *without* running analysis, *without* losing reproducibility.

**Contract additions/clarifications (minimum):**

- **Frame index basis:** Frame indices are **0-based**, in `[0, num_frames - 1]`, and are selected against the **post-trim, post-alignment reference timeline** (so the same indices apply to all aligned clips).
- **Error behavior:** If `frame_count > num_frames`, fail with `FC-3004` (`INSUFFICIENT_FRAMES`) rather than silently clamping.

**Proposed API surface (stable, importable by tests):**

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True, slots=True)
class FramePlan:
    frames: list[int]
    method: Literal["analysis", "uniform_seeded"]
    seed: int
    num_frames: int

def select_uniform_seeded_frames(*, num_frames: int, count: int, seed: int) -> list[int]:
    """Deterministically pick `count` unique frames across `num_frames` using `seed`."""

def build_frame_plan(
    *,
    num_frames: int,
    count: int,
    seed: int,
    skip_analysis: bool,
) -> FramePlan:
    """Return a FramePlan that always includes concrete frame indices."""
```

**Deterministic algorithm (precise):**

- Partition `[0, num_frames)` into `count` **disjoint bins**:
  - `bin_start = floor(i * num_frames / count)`
  - `bin_end = floor((i + 1) * num_frames / count) - 1`
  - `i ∈ [0, count-1]`, each bin is non-empty when `count <= num_frames`.
- Pick exactly **one** frame per bin using a stable hash:
  - `offset = blake2s_u32(f"{seed}:{i}") % (bin_end - bin_start + 1)`
  - `frame_i = bin_start + offset`
- Return frames sorted ascending (stable naming and overlays).

**Reference outputs (to lock tests and prevent “close enough” implementations):**

- `num_frames=240, count=5, seed=42` ⇒ `[12, 59, 115, 151, 233]`
- `num_frames=240, count=10, seed=42` ⇒ `[12, 35, 67, 79, 113, 124, 156, 168, 196, 231]`
- `num_frames=240, count=1, seed=42` ⇒ `[60]`
- `num_frames=10, count=5, seed=42` ⇒ `[0, 3, 5, 7, 9]`

**Where it plugs into the pipeline (no guessing):**

- Orchestration computes `num_frames` from the **aligned reference clip** (after audio alignment trims if enabled).
- If `skip_analysis=True`, orchestration **skips Analyze phase** but still produces `FramePlan(method="uniform_seeded")`.
- Render consumes `FramePlan.frames` directly; no Render code is allowed to “reselect” frames.

**Minimum tests to ensure the fix is applied:**

- Unit: `select_uniform_seeded_frames()` matches the reference outputs above.
- Integration: `--skip-analysis` produces screenshots without calling analysis, and uses the same frames for all clips (post-alignment).

### 2. CLI spec does not implement the canonical CLI contract

| Attribute | Value |
|:----------|:------|
| Location | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md:L60` |
| Issue | The CLI module spec omits contract flags that are canonical: `--skip-analysis`, `--skip-metadata`, `--skip-dovi`, and `--no-color` appear in the canonical flag table (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md:L24`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md:L35`) but not in the spec’s `run()` signature. |
| Impact | Implementation will either follow the spec (breaking parity/contracts) or follow contracts (breaking spec/traceability). Both force downstream churn in tests/docs. |
| Fix | Make `cli-module.md` derive its flag list from the contract (either embed the canonical table or reference `_generated.py` as the source). Update `RunRequest` to include skip flags and output mode flags, and specify exact mapping rules (including the `--no-upload` inversion noted in the contract YAML: `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml:L129`). |

#### 2A. Implementation Blueprint (Contract → Typer → RunRequest mapping)

**Rule:** Canonical CLI authority is `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml` (not the prose CLI spec).

**Minimum spec edits (to remove ambiguity):**

- Update `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md` to include the missing options:
  - `skip_analysis: bool = typer.Option(False, \"--skip-analysis\", ...)`
  - `skip_metadata: bool = typer.Option(False, \"--skip-metadata\", ...)`
  - `skip_dovi: bool = typer.Option(False, \"--skip-dovi\", ...)`
  - `no_color: bool = typer.Option(False, \"--no-color\", ...)`
- Update the `RunRequest` type in the same spec to carry these flags as first-class booleans.

**Mapping table (implementation agent should copy verbatim into code comments/tests):**

| Canonical Flag | Typer Param | Destination | Semantics |
|:--------------|:------------|:------------|:----------|
| `--seed` | `seed: int \| None` | `analysis.random_seed` override | Overrides config seed for both analysis and uniform sampling. |
| `--frame-count` | `frame_count: int \| None` | `analysis.frame_count` override | Overrides config frame_count; validated against clip length. |
| `--skip-analysis` | `skip_analysis: bool` | `RunRequest.skip_analysis` | Skips metrics computation; still renders via uniform seeded sampling. |
| `--no-upload` | `no_upload: bool` | `slowpics.auto_upload` override | Inverted: if `no_upload=True`, then `auto_upload=False`. |
| `--skip-metadata` | `skip_metadata: bool` | `RunRequest.skip_metadata` | Skips TMDB entirely even if config is enabled and key is present. |
| `--skip-dovi` | `skip_dovi: bool` | `RunRequest.skip_dovi` | Skips dovi_tool extraction even if config is enabled. |
| `--no-color` | `no_color: bool` | `RunRequest.no_color` | Disables rich output and any ANSI styling. |

**`--json` output mode must be pinned (pick one, document it, test it):**

- Recommended: `--json` affects **error output and doctor output only**:
  - `doctor --json` prints a JSON report on success.
  - Any command with `--json` prints `error_output_schema.json` on failure.
  - `run --json` does **not** imply a success schema (avoid inventing one); it only changes error/progress formatting.

**Acceptance tests to ensure the fix is applied:**

- `test_cli_help_contains_contract_flags`: `--skip-analysis/--skip-metadata/--skip-dovi/--no-color` appear in `--help`.
- `test_no_upload_inverts_auto_upload`: set flag ⇒ downstream sees `auto_upload=False`.
- `test_skip_analysis_path`: with `--skip-analysis`, the orchestration uses `FramePlan(method=\"uniform_seeded\")` and does not call metrics computation.

### 3. Contract authority paths are inconsistent across docs

| Attribute | Value |
|:----------|:------|
| Location | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md:L7` |
| Issue | Multiple derived docs claim generation from `contracts/...` (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md:L7`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md:L7`), while the generator actually reads from `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` (`scripts/generate_contract_views.py:L32`). |
| Impact | An implementation agent following docstrings will look in the wrong location and may create a second “contracts/” directory, splitting authority and breaking drift detection. |
| Fix | Standardize all references to repo‑relative canonical paths (e.g., `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml`) in generated docs and script docstrings. Add a guard in the generator that fails if a root-level `contracts/` directory exists to prevent “dual authority”. |

#### 3A. Implementation Blueprint (Make authority paths mechanically unambiguous)

**Do this in the generator (single source of generated strings):**

- Update the generator’s header comments and the generated markdown strings to refer to:
  - `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml`
  - `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml`
  - `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/config_schema.json`
- Add a guard in `main()`:
  - If `PROJECT_ROOT / \"contracts\"` exists, exit non-zero with a message telling contributors to delete it and use `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`.

**Test to ensure it stays fixed:**

- Tier‑A contract test that asserts generated docs contain the correct repo-relative canonical path strings.

### 4. Generator sentinel replacement can fail silently

| Attribute | Value |
|:----------|:------|
| Location | `scripts/generate_contract_views.py:L75` |
| Issue | `replace_sentinel_block()` performs `re.sub(...)` without verifying the sentinel markers exist or that a replacement occurred. |
| Impact | Removing/renaming a marker can freeze derived blocks while `--check` continues to pass (because the generated output becomes “read existing file unchanged”). This is drift that CI/tests will not detect. |
| Fix | Make sentinel replacement strict: if markers are missing or `re.sub` makes zero replacements, raise an error (or at least make `--check` fail) naming the expected marker (e.g., `config_inventory`, `importlinter`). Add a Tier‑A test that intentionally removes a marker and expects generator failure. |

#### 4A. Implementation Blueprint (Strict sentinel replacement + failing tests)

**Exact behavior required:**

- If the file does not contain both markers `<!-- BEGIN GENERATED:{marker} -->` and `<!-- END GENERATED:{marker} -->`, generation must fail.
- If replacement count is not exactly 1, generation must fail.

**Suggested code shape (sketch):**

```python
def replace_sentinel_block(content: str, marker: str, new_block: str) -> str:
    pattern = re.compile(
        rf\"(<!-- BEGIN GENERATED:{re.escape(marker)} -->).*?(<!-- END GENERATED:{re.escape(marker)} -->)\",
        flags=re.DOTALL,
    )\n
    replaced, count = pattern.subn(rf\"\\1\\n{new_block}\\n\\2\", content)\n
    if count != 1:\n
        raise ValueError(f\"Missing or duplicate sentinel block: {marker} (replacements={count})\")\n
    return replaced
```

**Tests to ensure the fix is applied:**

- A Tier‑A unit test that calls `replace_sentinel_block()` with missing markers and asserts it raises.
- A Tier‑A integration test that runs `python scripts/generate_contract_views.py --check` and fails if any marker is missing (no skips).

### 5. Scaffold is not cleanly copyable as documented

| Attribute | Value |
|:----------|:------|
| Location | `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/README.md:L28` |
| Issue | **Resolved:** tracked build artifacts are prevented via a Tier‑A `git ls-files` check (runtime caches may exist locally after running tests, but are not tracked). |
| Impact | Without the guard, first-time users can start from a “dirty” tree and diffs become noisy. |
| Fix | Keep the `git ls-files` guard and update the scaffold copy instructions to avoid copying local caches (prefer `git clone`/`git archive`, or a copy command that excludes caches). |

#### 5A. Implementation Blueprint (Scaffold copy hygiene that won’t flake)

**Fix the artifact now:**

- Remove tracked caches under `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/**/__pycache__/` and any `*.pyc`.

**Make the copy command artifact-safe:**

- Prefer a copy method that can exclude caches (example):

```bash
rsync -a --delete \
  --exclude='__pycache__/' --exclude='*.pyc' \
  --exclude='.venv/' --exclude='.pytest_cache/' --exclude='.ruff_cache/' \
  docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/ ./
```

**Add a non-flaky Tier‑A test (checks tracked files, not runtime filesystem):**

- Use `git ls-files docs/OPUS_REBUILD_FRAME_COMPARE/scaffold` and fail if any tracked path contains:
  - `__pycache__/`
  - `*.pyc`
  - `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.uv_cache/`

This avoids false positives from pytest creating caches during test execution.

---

## Moderate Issues (Should Fix)

### 1. “Verified detection patterns” vs “namespaces may vary” is contradictory

- **Location:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md:L81`
- **Issue:** The doc claims “verified detection patterns” for plugins, then says namespaces may vary and must be inspected (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md:L119`).
- **Fix:** Define a deterministic detection algorithm with an ordered list of acceptable namespaces per plugin and a “doctor” output that prints the discovered namespace (or “not found”). Make “verified” mean “tested in container image X” and pin that image/version in ops docs.

### 2. Type holes (`Any`, untyped dicts) in public-facing specs

- **Location:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md:L37`
- **Issue:** `ErrorDetails = dict[str, Any]` contradicts the “no Any leakage” goal and undermines `error_output_schema.json` conformance (the spec’s `to_dict()` can emit non‑JSON values).
- **Fix:** Replace `Any` with `JSONValue` (as the scaffold does: `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/errors.py:L25`) and require `details` to be `Mapping[str, JSONValue]`.

### 3. Async semantics references a config key that does not exist

- **Location:** `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md:L14`
- **Issue:** **Resolved:** `screenshots.ffmpeg_timeout_seconds` now exists in the canonical config schema and config reference.
- **Fix:** Keep the schema + docs + tests in sync via the generator + Tier‑A contract suite.

### 4. Contract tests are brittle to file moves and can skip instead of fail

- **Location:** `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_derived_views_fresh.py:L16`
- **Issue:** Project root is computed via fixed `parent.parent...` hops; moving the scaffold folder breaks tests. **Resolved:** missing sentinel markers now fail (no skip) in the layers contract.
- **Fix:** Replace fixed “parent hops” with an upward search for a stable anchor (e.g., `pyproject.toml`) in the scaffold contract tests.

---

## Minor Issues / Suggestions

1. Code samples contain placeholders (`...`) in specs and test strategy (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/cli-module.md:L136`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md:L223`); mark them explicitly as “pseudocode” or replace with runnable examples.
2. Render spec shows an FFmpeg command as a shell-like template (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:L243`); align with subprocess safety rules by documenting `shell=False` arg list form.

---

## Feature Parity & Traceability

The traceability matrix exists but currently reads as an aspiration: it references test names without specifying file paths or asserting existence, and several behaviors are defined only in `feature-parity.md` without corresponding module-spec acceptance tests.

| Feature (v0.0.14) | Spec Reference | Test Plan | Error Codes |
|:------------------|:---------------|:----------|:------------|
| Video Loading (lsmas) | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md:L41` (example only) | FC-2003/FC-4015 |
| HDR Detection | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md:L272` | Not concretely specified | FC-2002/FC-4002 |
| Frame Selection | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/analysis-module.md:L144` | Not concretely specified | FC-4012 |
| Screenshot Rendering | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:L129` | Not concretely specified | FC-4004 |
| slow.pics Upload | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md:L264` | Not concretely specified | FC-5002/FC-5010/FC-5011 |

**Unmapped Features:** Present in `feature-parity.md` but not fully traceable to module-spec acceptance tests: “SDR input with tonemap enabled => skip tonemapping, warn” (`docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/feature-parity.md:L188`), “Frame number > 999999 => truncate overlay” (`docs/OPUS_REBUILD_FRAME_COMPARE/02-requirements/feature-parity.md:L198`).

---

## Scalability Findings

| Smell | Location | Why It’s Churny | Lower-Churn Alternative |
|:------|:---------|:----------------|:------------------------|
| Dual/ambiguous authority paths | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md:L7` | Prompts and generated docs can drift into multiple “contracts/” roots | Use repo‑relative canonical paths everywhere; assert exactly one canonical directory in generator/tests |
| Silent sentinel failure (resolved) | `scripts/generate_contract_views.py:L67` | Drift can go undetected when markers change | Keep strict sentinel replacement (replacement count must equal 1) |
| Skip semantics not codified (resolved for screenshots-only) | `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/analysis/frame_plan.py:46` | Without a stable algorithm, refactors break reproducibility tests | Keep `FramePlan` + locked reference outputs as a standalone contract suite |
| Skipping on missing contract block (resolved) | `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_layers_contract.py:105` | Missing sentinel becomes “ignored” instead of a failing drift | Treat missing sentinel as a contract failure (current behavior) |

### Refactor Pressure Test Results

| Change | Estimated Edits | Verdict |
|:-------|:---------------|:--------|
| Add CLI flag | 1 canonical YAML + regen + 0–1 behavior test | ✅ |
| Add config field | 1 JSON schema + regen + Pydantic model + 0–1 behavior test | ⚠️ (schema/generator path is good; remaining risk is prose/spec drift in module docs) |
| Rename module | Many tests/docs unless a stable re-export surface exists | ⚠️ (import-linter + scaffold helps, but contract tests use brittle path hops) |
| Add upload target | Requires new service abstraction and SSRF policy extension | ⚠️ (policy is written, but extensibility hooks and tests are not specified) |

---

## Mode Matrix (Modularity / Skippability)

> [!IMPORTANT]
> Cells marked **UNSPECIFIED** indicate an implementation agent would have to guess.

| Mode | Enabled Phases | Required Deps | Outputs | Skip Rules | Error Codes |
|:-----|:---------------|:--------------|:--------|:-----------|:------------|
| Screenshots-only | Render | VS or FFmpeg | PNGs | Analysis skipped; selection uses `select_uniform_seeded_frames()` (see “1A”) | FC-200x/FC-4004 |
| Screenshots+Overlay | Render+Overlay | Pillow | PNGs | Analysis skipped; selection uses `select_uniform_seeded_frames()` (see “1A”) | FC-4014 |
| Analysis-enabled | Analyze+Render | VS | PNGs + cache | Uses selection_mode; render consumes a `FramePlan` (see “1A”) | FC-4002/FC-4012 |
| Upload-enabled | Publish | Network | URL | Must enforce host allowlist | FC-5010/FC-5011/FC-5002 |
| Metadata-enabled | TMDB | Network | title info | Optional; failure should not fail run per async semantics | FC-5005 |
| Dovi-enabled | Dovi | dovi_tool | metadata | Optional; `--skip-dovi` flag, warn-only per `phase_ordering.yaml` | FC-2007/FC-4018 |
| Full pipeline | All | All | all | Ordered: Preflight→LoadSources→FramePlan→Analyze→Render→Metadata→Dovi→Publish→Report (see `contracts/phase_ordering.yaml`) | all |

**Skip Semantics Explicit:** ✅ (all modes now have explicit ordering per `phase_ordering.yaml`)

---

## VapourSynth Toolchain Findings

| Plugin/Tool | Required For | Detection | Fallback | Error Code | Status |
|:------------|:-------------|:----------|:---------|:-----------|:-------|
| lsmas (LWLibavSource) | Source loading | `hasattr(core, 'lsmas') and hasattr(core.lsmas, 'LWLibavSource')` (`vs-module.md:L92`) | bestsource/ffms2/FFmpeg | FC-2003/FC-4015 | ✅ (pinned in `Dockerfile`) |
| libplacebo | Tonemap | `hasattr(core, 'placebo')` (`vs-module.md:L95`) | Reinhard fallback | FC-2003/FC-4003 | ✅ (pinned in `Dockerfile`) |
| dovi_tool | DV | `shutil.which("dovi_tool")` | Skip DV | FC-2007 | ✅ (baseline docs specify version) |

---

## Contract Alignment Matrix

| Domain | Canonical | Derived | Generator | Freshness Test | Status |
|:-------|:----------|:--------|:----------|:---------------|:-------|
| CLI Flags | `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml` | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/cli-flags-canonical.md` | `scripts/generate_contract_views.py` | `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_derived_views_fresh.py` | ✅ |
| Error Codes | `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml` | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/error-codes.md` | `scripts/generate_contract_views.py` | Tier‑A scaffold tests exist | ✅ |
| Config | `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/config_schema.json` | `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/config-reference.md` (inventory block) | `scripts/generate_contract_views.py` | Tier‑A scaffold tests exist | ✅ |
| Layers | `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/pyproject.toml` | `docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/dependency-graph.md` (importlinter block) | `scripts/generate_contract_views.py` | `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_layers_contract.py` | ✅ |
| Error Output | `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_output_schema.json` | — | — | `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_json_error_shape.py` | ✅ |

---

## Best Practices Audit

| Area | Status | Notes |
|:-----|:------:|:------|
| Pydantic v2 settings | ⚠️ | Config spec uses pydantic-settings but examples omit some imports. |
| httpx/anyio lifecycle | ✅ | Resolved: `cli-module.md:L325-334` documents ownership; `async-semantics.md:L214-255` defines cleanup. |
| Typer correctness | ✅ | Resolved: `cli-module.md:L62-70` uses `Path | None` annotation. |
| Type safety (no Any) | ✅ | Resolved: `errors-module.md:L39-41` uses `JSONValue`; no public `Any` leakage. |
| Error handling consistency | ⚠️ | Scaffold and errors spec differ on types (e.g., Path vs str) and registry patterns (`docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/src/frame_compare/errors.py:L25` vs `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md:L40`). |

---

## Security & Reliability Audit

| Invariant | Error Code | Tested | Status |
|:----------|:-----------|:-------|:-------|
| Path containment | FC-3009 | ✅ Tier-A | ✅ (`scaffold/tests/security/test_path_containment.py`) |
| Subprocess safety | FC-3010/FC-3011 | ✅ Tier-A | ✅ (`scaffold/tests/security/test_subprocess_sanitization.py`) |
| SSRF prevention | FC-5010/FC-5011 | Planned | ✅ (policy exists: `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/security-invariants.md:L106`) |
| Secrets redaction | — | ✅ Tier-A | ✅ (`scaffold/tests/security/test_subprocess_and_secrets.py:L88-144`) |
| Ctrl+C cleanup | Exit 130 | ✅ Defined | ✅ (`async-semantics.md:L214-255` defines cleanup + exit 130) |

---

## Ops / Toolchain Audit

| Check | Status | Notes |
|:------|:------:|:------|
| Docker/DevContainer accurate | ✅ | `Dockerfile` pins R73 + plugins; `deployment.md` section 8 ties doctor output to baseline. |
| Doctor/preflight complete | ✅ | `contracts/doctor_report_schema.json` defines output; `error_codes.yaml` maps failures. |
| Scaffold copyable | ✅ | Guarded by a Tier‑A `git ls-files` artifact test; runtime caches can exist locally but are not tracked (`docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/tests/contracts/test_scaffold_cleanliness.py:62`). |
| Verification commands sufficient | ✅ | Workflow docs specify `pyright/ruff/pytest` and generator `--check` (`docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`). |

---

## Module Completeness Matrix

> ✅ complete, ⚠️ partial, ❌ missing (as an AI-implementable spec with runnable samples)

| Module | Spec | Types | API | Tests | Errors | Status |
|:-------|:----:|:-----:|:---:|:-----:|:------:|:------:|
| errors | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ (`JSONValue` used per L39-41) |
| utils | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ (`Never` imported per L143) |
| config | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ (pydantic-settings precedence per L67-80) |
| vs | ✅ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ (detection tied to `Dockerfile`) |
| analysis | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ (`FramePlan` contract exists for skip-analysis) |
| render | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ (FFmpeg uses `run_subprocess` per L231) |
| services | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ (SSRF policy exists; Tier-A tests cover upload) |
| orchestration | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ (phase wiring complete per `contracts/phase_ordering.yaml`) |
| cli_entry | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ✅ (all contract flags synced to spec) |

---

## AI Agent Readiness Score

**Overall Score:** 8/10

| Dimension | Score | Justification |
|:----------|:-----:|:--------------|
| Spec precision | 7/10 | Phase wiring complete (`phase_ordering.yaml`); FramePlan contract exists. |
| Code samples accuracy | 6/10 | Most samples include imports; remaining `...` are documented as pseudocode. |
| Done criteria clarity | 8/10 | Handoff docs + CI freshness + traceability warning contract freshness. |
| Error recovery guidance | 6/10 | Async semantics fully specify lifecycle and cleanup. |
| Contract enforcement | 8/10 | Canonical contracts + generator + scaffold Tier‑A tests + CI freshness check. |
| Anti-churn scalability | 7/10 | Central contracts + strict sentinel replacement + dual-authority guard. |
| Modularity / skippability | 8/10 | All 9 phases specified + E2E stubs created in `phase_ordering.yaml` with skip conditions. |
| VapourSynth correctness | 8/10 | Baseline pinned in `Dockerfile`; deployment.md ties doctor to baseline. |
| Security coverage | 8/10 | Tier-A tests exist for path containment, subprocess safety, upload policy. |

---

## Action Plan

### Priority 1 (Blocks Implementation)

1. Pin and enforce a VS toolchain contract: provide a Docker/DevContainer build that the VS module spec is validated against, and link “doctor” output checks to that environment (`docs/OPUS_REBUILD_FRAME_COMPARE/06-operations/deployment.md:21`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md:81`).
2. Define end-to-end phase ordering for the full pipeline (Publish/Metadata/Dovi/Report) and write at least one deterministic E2E acceptance test per mode (`docs/OPUS_REBUILD_FRAME_COMPARE/15-plan-review-report.md:513`).
3. Remove `Any` and `...` placeholders from public-facing module specs so an implementation agent can code without guessing (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/errors-module.md:37`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/services-module.md:349`).

### Priority 2 (Should Fix Before Implementation)

1. Specify httpx/anyio lifecycle rules as concrete code contracts (who owns the client, how cancellation propagates, what is retried) and add unit tests for cancellation + timeout mapping (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/async-semantics.md:67`).
2. Convert the render FFmpeg spec to an explicit `shell=False` arg list and connect it to the FC‑3010/3011 sanitization rule set (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/render-module.md:229`, `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/security-invariants.md:50`).
3. Turn “planned” security invariants into a minimal enforced suite (path containment, SSRF allowlist, secrets redaction boundaries, Ctrl+C exit 130) (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/security-invariants.md:8`).

### Priority 3 (Nice to Have)

1. Replace placeholder snippets with runnable code samples in specs and the test strategy (`docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/testing-strategy.md:56`).
2. Upgrade parity/traceability from “table of intent” to a verified mapping (scripted existence checks for referenced module sections + test files).

---

## Next Implementation Checklist (Full Pipeline)

This is the concrete “what to implement next” list for going beyond contract enforcement into a working pipeline. Each item has a “done signal” so work can’t silently drift.

### P0. Pin a Reproducible VapourSynth Environment

- Produce a pinned Docker/DevContainer build and declare it as the **verification baseline** for VS/plugin behavior (not “whatever is on the host”).
- Update VS docs so “verified detection patterns” means “verified in baseline image X”, and make the `doctor` output show the discovered namespaces.

**Done signals:**

- `frame-compare doctor --json` includes, for each plugin group, `status`, `discovered_namespace`, and actionable install hints when missing.
- A CI job (or documented local command) can build/run the baseline image and run a minimal VS smoke test.

### P0. Specify Full-Pipeline Phase Ordering (No Guessing)

- Define exact ordering and data handoffs when enabling **Publish + Metadata + Dovi + Report** together (the mode matrix currently marks this UNSPECIFIED).
- For each optional phase, specify: inputs, outputs, skip conditions, and “failure is fatal vs warn-only” rules.

**Done signals:**

- `docs/OPUS_REBUILD_FRAME_COMPARE/15-plan-review-report.md:513` mode matrix no longer contains UNSPECIFIED cells for full pipeline ordering.
- At least one E2E test per “mode row” exists with deterministic assertions (file paths + expected outputs).

### P0. Eliminate `Any` + Replace Placeholders in Public Specs

- Remove `Any` from public contracts/types in module specs; use a JSON-safe union (`JSONValue`) and explicit typed shapes.
- Replace `...` placeholders with runnable code or clearly label them as pseudocode and provide a runnable alternative adjacent.

**Done signals:**

- `rg -n \"\\bAny\\b\" docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs` returns no hits in public API/type blocks.
- Every code block intended as code is syntactically valid Python 3.13+ (imports included).

### P0. Define Network Client Lifecycle + Cancellation Contract

- Specify ownership of `httpx.AsyncClient` (per-run `async with` vs long-lived), how retries are bounded, and how cancellation propagates.
- Define Ctrl+C behavior (exit 130) and cleanup policy (what is deleted vs retained).

**Done signals:**

- Unit tests cover cancellation propagation and timeout mapping (upload fails => exit 6; tmdb fails => warn-only when optional).
- No service spec requires manual `.close()` without a context manager boundary.

### P1. Security Invariants: Enforce + Test ✅

- ~~Implement and test: path containment (FC‑3009), SSRF allowlist (FC‑5010/5011), subprocess arg sanitization (FC‑3010/3011), and secrets redaction boundaries.~~ All implemented.

**Done signals:**

- A security test suite exists (unit-level) and is runnable without network/VS for the policy logic itself.
- Each invariant maps to a specific error code and test file path.

### P1. Make Traceability Verifiable ✅

- ~~Add a small script that validates `requirements-traceability.md` references exist (module sections + test files) and wire it into CI.~~ `scripts/validate_traceability.py` created and wired into CI.

**Done signals:**

- CI fails if a traceability reference points to a missing file/section/test.

---

## Verification Gate (Ensures Fixes Are Applied)

These checks are designed to prevent “almost implemented” fixes from drifting or regressing.

### Contract / Docs Freshness

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
```

**Expected signal:** `OK: All derived files are up-to-date` and exit code `0`.

### Tier‑A Contract Suite (No VS, No Network)

Run the contract/security subset used to protect canonical contracts and derived views:

```bash
(cd docs/OPUS_REBUILD_FRAME_COMPARE/scaffold && .venv/bin/pytest -q -m tier_a)
```

**Expected signal:** all Tier‑A tests pass and failures are actionable (no “skip on missing sentinel”).

### CLI Parity (Help + Flag Wiring)

After implementing “2A”, verify the CLI help and wiring:

```bash
uv run frame-compare --help
uv run frame-compare run --help
```

**Expected signal:** help includes contract flags (`--skip-analysis`, `--skip-metadata`, `--skip-dovi`, `--no-color`) and `--no-upload` is documented as an inversion of `slowpics.auto_upload`.

---

## Opus 4.5 Implementation Checklist (Do Not Deviate)

This is the concrete worklist Opus should implement. Each item has a “done signal” so you can verify completion.

> [!NOTE]
> Status: completed for the Tier‑A/contract-enforcement slice; retained as the canonical checklist to re-run if any of these guarantees regress.

### A. Deterministic Screenshots-Only (No Analysis)

- Implement `select_uniform_seeded_frames()` and `FramePlan` exactly as specified in “1A” and “Phase Wiring Matrix”.
- Wire orchestration so **Render only consumes `FramePlan.frames`** (no reselection).

**Done signals:**

- Unit tests match the reference outputs in “1A”.
- `--skip-analysis` run path produces screenshots and does not require metrics computation.

### B. CLI Contract Parity

- Update CLI wiring to include the contract flags missing from the prose spec: `--skip-analysis`, `--skip-metadata`, `--skip-dovi`, `--no-color`.
- Implement `--no-upload` inversion deterministically (`no_upload=True` ⇒ `slowpics.auto_upload=False`).

**Done signals:**

- `frame-compare run --help` shows all contract flags.
- Flag mapping tests pass (`test_no_upload_inverts_auto_upload`, etc.).

### C. Generator: Strict Sentinels + Correct Paths

- Make `replace_sentinel_block()` fail if markers are missing or duplicated.
- Update generated doc strings to point at `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/...` (not `contracts/...`).
- Add a guard: fail if a root-level `contracts/` directory exists.

**Done signals:**

- Removing a sentinel marker makes `python3 scripts/generate_contract_views.py --check` fail loudly.
- Generated docs contain the correct canonical path strings.

### D. CI: Enforce Derived View Freshness

- Add a CI step that runs `python3 scripts/generate_contract_views.py --check`.

**Done signals:**

- CI fails when derived views are stale (without running pytest).

### E. Scaffold Cleanliness (Tracked Files)

- Remove tracked `__pycache__/` and `*.pyc` from `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/`.
- Add a Tier‑A test that uses `git ls-files` to ensure no tracked artifacts exist under the scaffold path.

**Done signals:**

- The new cleanliness test fails if artifacts are accidentally committed in the future.

### F. Contract Tests: No “Skip on Missing Sentinel”

- Update contract tests (especially layers/sentinel extraction) so missing sentinel blocks are treated as a **contract failure**, not a skip.

**Done signals:**

- Deleting a sentinel marker causes Tier‑A tests to fail with an actionable message.

---

## Appendix: Scalability Smell Checklist

### A) Contract/Test Design Best Practices

- [ ] Contract enforcement concentrated in a small suite
- [ ] Tests prefer stable public surfaces over deep internal imports
- [x] Strict tests protect user-visible contracts (isolated)
- [ ] Golden fixtures have deterministic regen + version pin
- [x] Derived views have freshness gate with actionable failure
- [ ] Shared helpers exist for parsing/validation

### B) Contract Authority Best Practices

- [ ] One canonical source per domain
- [x] Derived files clearly labeled generated
- [x] Generators use stable sentinels/markers
- [x] Canonical data stored in YAML/JSON/TOML (not markdown)
- [ ] Contract evolution documented (additive vs breaking)

### C) Refactor Resilience Best Practices

- [ ] Stable public API surface exists
- [ ] `__all__`/re-exports reduce import churn
- [x] Layering rules enforced consistently

### D) Modularity / Skippability Best Practices

- [x] Screenshots-only mode explicitly supported and tested
- [x] Skip semantics explicit and deterministic
- [ ] Outputs decoupled from optional phases

### E) VapourSynth / Toolchain Best Practices

- [x] Plugin requirements and detection explicit per feature
- [x] Fallbacks defined where possible
- [x] Doctor/preflight maps to error registry
- [x] Toolchain guidance pinned/reproducible

### F) Security/Reliability Best Practices

- [x] SSRF policy codified and tested
- [x] Path containment and subprocess safety consistent
- [x] Ctrl+C behavior defined and tested
