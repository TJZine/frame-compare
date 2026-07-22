# Repo Review Context

Schema-Version: 1
Profile-Status: explicit
Last-Updated: 2026-07-22
Repo-Name: frame-compare
Default-Branch: main
Profile-Scope: suggestion-review and pr-commit-review
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
- `.codex/review-context.md` for `suggestion-review` and `pr-commit-review`
- `.codex/config.toml`
- `.codex/agents/*.toml`
- `.agents/skills/**`
- `.agents/rules/general-guidelines.md` only as an Antigravity shim that defers to AGENTS/runbook

Historical/reference only:
- `docs/DECISIONS.md` for historical exceptions/decisions
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
- `src/frame_compare/cli/entry.py`
- `src/frame_compare/config/**`
- `src/frame_compare/orchestration/**`
- `src/frame_compare/orchestration/coordinator.py`
- `src/frame_compare/errors.py`
- `src/frame_compare/render/**`
- `src/frame_compare/vs/**`
- `src/frame_compare/services/report/**`
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
uv run --no-sync ruff check .
# plus targeted pytest when touched module has direct tests
```

Logic verification:
```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
```

Full verification:
```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
```

Docs/API verification:
```bash
uv run --no-sync python scripts/generate_api_docs.py --check
```

Regenerate API docs:
```bash
uv run --no-sync python scripts/generate_api_docs.py
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

Preferred roles:
- `explorer`: read-only source discovery
- `reviewer`: packet-focused correctness, architecture, maintainability, security, or workflow review
- `worker`: bounded implementation
- `worker_sol_low`: bounded implementation with frozen ownership and contracts that still needs local code judgment
- `worker_luna`: lower-cost execution of a low-ambiguity, decision-complete Sol-planned unit
- `planner`: separate planning only when justified
- `docs_researcher`: official-source checks
- `monitor`: long waits and status checks

Preserve read-only reviewer/research roles versus write-capable planner/worker boundaries.

## Model Policy

- Use configured role defaults. Use `worker_sol_low` only for bounded work with
  frozen ownership and contracts. Use `worker_luna` only for an explicitly eligible,
  low-ambiguity, directly verifiable unit planned by the Sol planner. Change model
  or reasoning effort only from current representative evidence.

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
- raw Pydantic `ValidationError` escaping user-facing CLI handlers instead of
  mapping to typed config errors and documented exit codes
- hidden runtime import of VS-heavy modules at CLI import time
- weak path/subprocess/network safety
- unbounded subprocess/PowerShell invocations in Windows portable, release-path,
  or runtime-boundary tests
- deterministic naming/output changes without contract tests
- malformed frame props, metadata, or config values suppressing deterministic
  fallback behavior just because a key is present
- hotspot signatures broadened from named result/union types to `object`/`Any`
  without an owner-boundary reason
- tests that freeze incidental log/call/YAML/PowerShell formatting while missing
  the behavior or command semantics they meant to protect
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

Mandatory high-risk probes for costly PR commit reviews:
- CLI/config groups: inspect invalid-input tests, error mapping, exit codes,
  stdout/stderr separation, JSON cleanliness, no traceback leakage, and TOML
  serialization helpers that may drop sections or preserve `None`.
- `src/frame_compare/vs/**` groups: inspect missing/unspecified/malformed frame
  props such as `_Matrix`, parseable byte/string values, deterministic fallback
  branches, and lazy optional-runtime imports.
- Windows portable/release groups: inspect every direct `subprocess.run()` and
  PowerShell invocation for explicit timeouts; prefer semantic workflow/script
  assertions over exact line formatting.
- Orchestration hotspot groups: inspect typed result/union seams for broadening
  to `object`, `Any`, casts, or ad hoc dictionaries that weaken static signal.
- Test-heavy groups: scan for exact log/call-shape assertions, brittle parser
  regexes, duplicate helpers, stale file-level pyright pragmas, hidden external
  dependencies, broad fixtures, and skipped runtime tests being treated as proof.
