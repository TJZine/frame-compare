# Repo Review Context

Schema-Version: 1
Profile-Status: explicit
Last-Updated: 2026-05-20
Repo-Name: frame-compare
Default-Branch: main
Profile-Scope: review-suggestion-adjudication and pr-commit-review
Profile-Basis: stage1 branch inspection; main branch is sparse and stage1 contains active app/workflow implementation

## Precedence

This file is the primary repo profile for:
- `suggestion-review`
- `pr-commit-review`

Current code, current diff, config, CI, and successfully executed commands outrank stale profile content.
Generated cache files under `.codex/cache/` are optional aids only and must not outrank this profile.

## Technical Stack

- Language: Python 3.13+
- Product type: deterministic video frame comparison CLI/package
- Runtime/platform: CLI-first Python app with optional VapourSynth and FFmpeg runtime paths; Windows portable/release paths exist
- Package/build: `uv`, hatchling, `pyproject.toml`, `uv.lock`
- CLI framework: Typer, Rich
- Data/modeling: Pydantic, pydantic-settings
- Media/runtime: NumPy, Pillow, FFmpeg, optional VapourSynth/vspreview, video metadata/parsing libraries
- HTTP/integration: httpx; optional publishing integrations
- Type/lint/test: Pyright strict, Ruff, pytest, import-linter, coverage

## Product / Domain

- Product type: deterministic video comparison pipeline: frame selection, HDR→SDR tonemapping, overlays/reports, publishable outputs
- Data sensitivity: Low to Medium normally; path traversal, subprocess hardening, SSRF/network publishing paths elevate risk
- Operational criticality: User-facing CLI/release tool; deterministic outputs and release artifacts matter
- Public surfaces: CLI commands/flags/exit behavior, documented config behavior, generated release artifacts, installer/update commands, deterministic reports/metadata
- Compliance/security notes: path containment, subprocess arguments, network publishing/SSRF, release signing/update paths, filesystem persistence, and deterministic output contracts are elevated risk

## Authority Surfaces

Current truth:
- `AGENTS.md`
- `docs/ENGINEERING_RUNBOOK.md`
- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- `importlinter.ini`
- `pyproject.toml`
- `.codex/config.toml`
- `.codex/agents/*.toml`
- `.agents/skills/**`
- `.agents/rules/general-guidelines.md` only as an Antigravity shim that defers to AGENTS/runbook

Historical/reference only:
- `docs/DECISIONS.md` for historical exceptions/decisions
- `docs/archive/**`
- `docs/plans/**` unless the file starts with `Status: Active`
- `.codex/cache/**` local cache only

## Control-Plane / Config Paths

Do not treat these as pure docs/assets:
- `AGENTS.md`
- `CODEX.md`
- `.agents/rules/general-guidelines.md`
- `.agents/skills/**`
- `.codex/config.toml`
- `.codex/agents/**`
- `docs/ENGINEERING_RUNBOOK.md`
- `docs/current-architecture.md`
- `docs/current-cli-contract.md`
- `docs/api.md` when generated-reference drift matters
- `importlinter.ini`
- `pyproject.toml`
- `.github/workflows/**`
- `.coderabbit.yaml`
- Docker/Windows portable/release tooling docs and config

## High-Risk Paths

Trigger architecture/deep review:
- `src/frame_compare/cli_entry.py`
- `src/frame_compare/config/**`
- `src/frame_compare/orchestration/**`
- `src/frame_compare/orchestration/coordinator.py`
- `src/frame_compare/errors.py`
- `src/frame_compare/render/**`
- `src/frame_compare/vs/**`
- `src/frame_compare/services/report.py`
- `src/frame_compare/services/metadata.py`
- `src/frame_compare/services/publishers.py`
- `src/frame_compare/utils/subproc.py`
- `src/frame_compare/utils/atomic_write.py`
- `tools/windows_portable/**`
- `.github/workflows/windows-portable.yml`
- `Dockerfile`
- `docker-compose.yml`
- `tools/verify_docker_integration.sh`
- `scripts/generate_api_docs.py`
- `scripts/validate_traceability.py`
- workflow/authority docs listed above

## High-Risk Domains

- CLI/config contract drift
- deterministic output, stable naming, generated reports/metadata
- frame selection, alignment, metrics, and HDR/SDR tonemapping behavior
- FFmpeg/VapourSynth runtime behavior and fallbacks
- subprocess argument safety
- filesystem path containment, atomic writes, cache/config persistence
- HTTP publishing integrations and SSRF/network behavior
- Docker/runtime environment
- Windows portable installer/update/signing/release paths
- import boundaries and lazy imports that avoid VS-heavy imports at CLI import time
- architecture/workflow/authority doc drift

## Verification Commands

Bootstrap:
```bash
uv sync --group dev --frozen
```

Fast/local sanity:
```bash
.venv/bin/ruff check .
# plus targeted pytest when touched module has direct tests
```

Logic verification:
```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Full verification:
```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Docs/API verification:
```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py --check
```

Regenerate API docs:
```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_api_docs.py
```

Docker/runtime verification:
```bash
bash tools/verify_docker_integration.sh
```

Windows portable/release verification:
```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/validate_update_public_key.ps1 -PublicKeyPath tools/windows_portable/update_public_key.xml
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir dist/frame-compare-portable-win-x64 -CacheDir .portable_cache
dist/frame-compare-portable-win-x64/frame-compare.ps1 doctor --json
```

Windows update packaging/signing path:
```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_update.ps1 -BundleDir .\dist\frame-compare-portable-win-x64 -OutFile .\dist\frame-compare-update-win-x64-<version>.zip
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/sign_update.ps1 -UpdateZip .\dist\frame-compare-update-win-x64-<version>.zip
```

If Windows or Docker paths cannot run locally, record them as documented-only and require CI/maintainer confirmation before claiming full verification.

## Subagent Roles

Preferred roles when available:
- reviewer: normal correctness/regression/security/test review
- maintainability_reviewer: code-health, strict typing, brittle tests, file shape, unnecessary indirection, harmful duplication
- architecture_reviewer: CLI/config contracts, runtime/render/VS boundaries, release/Docker/Windows paths, import boundaries, persistence/subprocess/network risk
- worker_54_high: exact, bounded, testable fixes with no unresolved owner/product/architecture decision
- worker: ambiguous or high-risk implementation/fix work
- docs_researcher: official docs/API/tooling/runtime behavior checks

Fallback rule:
- If a named role is unavailable, use the closest available default subagent and pass the intended role instructions explicitly.
- Preserve read-only reviewer vs write-capable worker boundaries.
- Frame Compare stage1 currently has `.codex` roles for explorer, reviewer, docs_researcher, planner, worker, monitor, but may not yet have specialized reviewer/worker variants; use explicit fallback packets when missing.

## Model Policy

- Use cost-effective bounded roles for exact local fixes.
- Use maintainability review for strict typing/test/code-health concerns.
- Use deep architecture review for CLI/config contract, runtime/render/VS, Docker, Windows portable/release, subprocess/network/persistence, and authority-doc changes.
- Do not default every review subagent to GPT-5.5 high.

## Pure Docs / Assets Exclusion Rule

Only exclude commits from adversarial subagent review when they change docs/assets with no effect on runtime behavior, public CLI/config/API contracts, CI/release/deployment behavior, architecture/workflow/control-plane policy, tests, generated outputs, security, persistence, or data handling.

Never auto-exclude authority docs, generated API docs, workflow/control-plane docs, CI/release docs, Docker/Windows docs, or docs that define CLI/config/runtime behavior.

## Suggestion Review Calibration

Priority bumps:
- +2 for path traversal, subprocess, SSRF/network publishing, signing/update/release, or deterministic output corruption risks
- +1/+2 for CLI/config public contract drift
- +1/+2 for `orchestration/`, `render/`, `vs/`, Docker, Windows portable, or hotspot files
- +1 for import-boundary violations or lazy import regressions
- +1 for tests that weaken public seam or deterministic behavior proof

Priority reductions:
- style-only comments that do not affect clarity or behavior
- private importable-module polish when public CLI/config surface is unaffected
- pre-existing debt not worsened by the diff

Common false-positive patterns:
- treating generated `docs/api.md` as a stability promise by itself
- requesting broad compatibility shims without maintainer approval
- over-weighting importable module APIs that are not documented public contracts
- generic Python-style suggestions that break repo determinism or CLI contracts

Common true-positive patterns:
- CLI flag/config/env behavior drift without doc/test updates
- hidden runtime import of VS-heavy modules at CLI import time
- weak path/subprocess/network safety
- deterministic naming/output changes without contract tests
- missing Docker/Windows verification for touched release/runtime paths

## PR Commit Review Calibration

Grouping hints:
- Group commits by CLI/config contract, analysis/selection, render/VS/runtime, orchestration, services/reporting, Docker/Windows/release, docs/control-plane, or tests.
- Group later fix commits with the earlier commit they amend when they address the same logical issue.
- Use architecture review for CLI/config, orchestration/render/VS, Docker/Windows/release, subprocess/network/persistence, and authority-doc groups.
- Use maintainability review for strict typing, test design, code-health, large refactors, and generated-doc/tooling groups.

Final net-diff sanity check priorities:
- public CLI/config contract consistency
- deterministic output/report/naming drift
- import-boundary regressions
- missing authority doc updates
- incomplete Docker/Windows/runtime verification
- accidental local cache/run artifacts committed
