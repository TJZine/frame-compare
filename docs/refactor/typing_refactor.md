# Typing Refactor Plan (High-Level)

This document outlines a future initiative to ship first-class type hints for Frame Compare’s programmatic surfaces (runner helpers, VSPreview helpers, CLI shims). The plan is intentionally high-level; we will refine each phase once the current modularization backlog is fully addressed.

## Goals

- Publish a stable, typed runner API so Pyright/VSCode users never need to import `src.frame_compare.*`.
- Provide `.pyi` stubs (or inline annotations + `py.typed`) for the curated surface, covering runner helpers, VSPreview helpers, and any supported CLI shims.
- Align packaging/docs so downstream consumers know which symbols are officially supported and typed.

### Current Status & Prerequisites

- API hardening and modularization are largely in place:
  - `docs/refactor/api_hardening.md` defines the curated public surface (`run_cli`, `main`, `RunRequest`, `RunResult`, `CLIAppError`, `ScreenshotError`, TMDB helpers, preflight helpers, doctor helpers, `vs_core`).
  - `docs/refactor/mod_refactor.md` and `docs/refactor/runner_service_split.md` have completed the main CLI/core/runner modularization phases.
  - `src/frame_compare/compat.py` now centralises legacy/compat exports via `COMPAT_EXPORTS` and `apply_compat_exports`, including doctor shims (`collect_doctor_checks`, `emit_doctor_results`) and CLI helpers (`_cli_override_value`, `_cli_flag_value`).
- CLI architecture refactor is planned and tracked separately:
  - `docs/refactor/frame_compare_cli_refactor.md` describes how CLI wiring and helpers are split into `cli_entry` and `cli_utils` with `frame_compare.py` as a thin shim.
- **Prerequisite for starting this typing refactor**:
  - Complete the runner cleanup (`docs/refactor/refactor_cleanup.md`) and the CLI refactor (`docs/refactor/frame_compare_cli_refactor.md`) so that:
    - Legacy runner toggles and temporary scaffolding are removed or clearly isolated.
    - Compat shims reflect the final public surface you intend to keep typed and supported.

## Phase 0 – Discovery & Contract Definition
- Audit existing exports (`frame_compare.__all__`, `_COMPAT_EXPORTS`, README references) to decide which helpers become part of the public runner API.
- Inventory every helper currently imported from `src.frame_compare.*` by tests or downstream scripts (`RunResult`, `RunRequest`, VSPreview helpers, CLI runtime utilities).
- Produce a “candidate API list” and document open questions (e.g., which shims remain temporary, whether fixtures should be public).
- Deliverable: short report in this doc naming the proposed stable surface plus risks.

## Phase 1 – Export Stabilization
- Update `frame_compare/__init__.py` and related modules to expose the curated helper list via explicit exports (no wildcards).
- Deprecate or internalize helpers that shouldn’t be public; document the remaining exports in README.
- Add regression tests ensuring the curated exports stay intact (e.g., verifying `dir(frame_compare)` contains the expected names).
- Deliverable: stable export surface ready for typing.

## Phase 2 – Stub Generation & Packaging
- Generate `.pyi` files (or inline `Protocol` annotations) for:
  - Runner helpers (`RunRequest`, `RunResult`, reporter interfaces).
  - VSPreview helpers (`render_script`, `launch`, manual-offset helpers).
  - CLI runtime utilities that stay public (e.g., `CliOutputManager`, `JsonTail`).
- Wire stubs into packaging:
  - Include them in `pyproject.toml`/`MANIFEST.in`.
  - Add or update `py.typed`.
  - Document the typed API in README’s “Programmatic Usage” section.
- Deliverable: package ships with first-class typing information.

## Phase 3 – Verification & Consumer Testing
- Re-run Pyright locally.
- Install the package into a fresh environment (`uv pip install .`) and run Pyright against sample consumer scripts to confirm no `src.*` imports are required.
- Update docs/tests to use the new public imports exclusively.
- Deliverable: verified typed API, updated docs/tests, Pyright clean in both repo and consumer contexts.

## Phase 4 – Follow-up & Maintenance
- Document maintenance steps (how to update stubs when adding new helpers).
- Track any remaining TODOs (e.g., wizard/doctor helpers) in this file for future phases.
- Ensure CHANGELOG captures the new typed surface for end users.

### Notes
- Expect the overall effort to span 1–2 focused Codex sessions per phase.
- Inline annotations alone will not meet the goal; we must commit to a curated, supported export surface.
- Revisit this plan after:
  - The CLI/core modularization and service split plans are fully applied (`docs/refactor/mod_refactor.md`, `docs/refactor/runner_service_split.md`),
  - The CLI refactor is complete (`docs/refactor/frame_compare_cli_refactor.md`),
  - And the runner cleanup has retired legacy toggles/shims (`docs/refactor/refactor_cleanup.md`),
  so that the curated public API and compat exports reflect the long-term surface before you generate and ship stubs.
