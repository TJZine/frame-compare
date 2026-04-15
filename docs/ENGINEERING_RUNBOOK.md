# Engineering Runbook

This is the canonical operating runbook for Frame Compare.

## Entrypoint

`AGENTS.md` owns the repo entrypoint map.

If you land in this document directly, use it as the operating policy, then consult
`docs/current-architecture.md`, `importlinter.ini`, and `pyproject.toml` as needed.
Use `docs/DECISIONS.md` only for historical context.

## Repo Stance

Frame Compare operates as a CLI-first packaged Python app with some importable modules.

Default public/stability policy:

- CLI commands, flags, exit behavior, and documented config behavior are the public surface.
- Generated release artifacts and installer/update commands are public surfaces.
- Importable package modules are convenience-only unless the repo explicitly documents a supported import contract.

If a task needs a broader compatibility promise, the maintainer must confirm it in the task or decision log before implementation.

## Authority Surfaces

- `AGENTS.md`: short entrypoint map only
- `docs/ENGINEERING_RUNBOOK.md`: workflow, verification, planning, review, handoff
- `docs/current-architecture.md`: present-day architecture truth
- `docs/DECISIONS.md`: decision log and historical exceptions
- `docs/api.md`: generated reference, not a stability promise by itself
- `README.md`: product overview, install, quickstart
- `CONTRIBUTING.md`: contributor onboarding and PR mechanics
- `docs/plans/**`: reference-only unless the file starts with `Status: Active`
- `docs/archive/**`: historical reference only, never current authority
- `.codex/cache/**`: local cache material only, never current authority

Do not create a second runbook or second architecture summary.

## Command Canon

Bootstrap:

```bash
uv sync --group dev --frozen
```

Core local gates:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Docker integration gate:

```bash
bash tools/verify_docker_integration.sh
```

Windows portable local packaging path:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/validate_update_public_key.ps1 -PublicKeyPath tools/windows_portable/update_public_key.xml
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir dist/frame-compare-portable-win-x64 -CacheDir .portable_cache
dist/frame-compare-portable-win-x64/frame-compare.ps1 doctor --json
```

Windows code-only update packaging path:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_update.ps1 -BundleDir .\dist\frame-compare-portable-win-x64 -OutFile .\dist\frame-compare-update-win-x64-<version>.zip
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/sign_update.ps1 -UpdateZip .\dist\frame-compare-update-win-x64-<version>.zip
```

The Windows commands require a Windows host with PowerShell and the expected toolchain. In non-Windows environments, treat them as documented-only unless a compatible runner is available.

## Verification Policy

### Fast Local Sanity

Use for docs-only changes and small internal refactors that do not touch runtime behavior.

- Run `ruff check .` when Python files changed.
- Run targeted `pytest` only when a touched module has direct tests.

### Logic Verification

Use for most code changes that do not affect packaging, Docker, Windows portable, or public CLI/config contracts.

- Run the touched tests or a focused `pytest` selection.
- Run `pyright --warnings`.
- Run `ruff check .`.
- Run `lint-imports` if imports or top-level module boundaries changed.

### Full Verification

Required for:

- CLI behavior changes
- config loading or env-var behavior changes
- changes in `orchestration/`, `render/`, `vs/`, `services/`
- changes to hot spots listed in the architecture doc
- changes to docs that redefine workflow or architecture authority

Run:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

### Docker / Runtime Verification

Required when changing:

- `Dockerfile`
- `docker-compose.yml`
- `tools/verify_docker_integration.sh`
- `src/frame_compare/render/**`
- `src/frame_compare/vs/**`
- integration tests that validate real VS/FFmpeg behavior

Canonical command:

```bash
bash tools/verify_docker_integration.sh
```

If this path cannot be run locally, record it as documented-only and rely on `.github/workflows/docker-integration.yml`.

### Windows Portable / Release-Path Verification

Required when changing:

- `.github/workflows/windows-portable.yml`
- anything under `tools/windows_portable/**`
- installer/update commands or release asset layout in docs
- bundle/update manifests and signing flow

Canonical verification path:

1. Validate the update public key.
2. Build the portable bundle.
3. Run bundle smoke checks.
4. Build the code-only update zip when updater logic changes.
5. Sign the update zip when updater or release-package logic changes.
6. Confirm the GitHub Actions Windows workflow still matches the documented local path.

Current CI ownership:

- `.github/workflows/windows-portable.yml` is the canonical CI path for the full portable bundle.
- The repo does not currently have a matching CI path for `build_update.ps1` plus `sign_update.ps1`.

When updater or release-package logic changes and the signed-update path cannot run locally, mark it as documented-only in the task handoff and require explicit maintainer or Windows-runner confirmation before treating the release path as fully verified.

## Risk Tiers

### Low Risk

- docs-only updates
- comments
- non-behavioral cleanup outside hotspots

No durable plan required. Use fast local sanity.

### Medium Risk

- targeted module changes
- new tests
- non-breaking internal refactors

Use a lightweight task plan in the current task or PR. Use logic verification.

### High Risk

- CLI or config behavior changes
- Docker/runtime changes
- Windows portable/release-path changes
- changes to hotspots
- changes to external integrations
- changes to architecture or workflow authority docs

Require:

- explicit task plan before editing
- same-pass updates to the relevant authority docs
- full verification, plus Docker or Windows verification if those surfaces changed

### Stop And Ask

Stop and get maintainer confirmation if any of these are unclear:

- product invariants
- deployment/runtime model
- security-sensitive boundaries
- conflicting workflow docs
- whether an import-level API should be treated as stable

## Discrepancy Handling

- `AGENTS.md` controls entrypoint order.
- Observed code, config, and successfully executed commands outrank stale prose in
  `docs/current-architecture.md`, `README.md`, `CONTRIBUTING.md`, `docs/DECISIONS.md`,
  historical plans, and cached review material.
- When a doc/code mismatch looks intentional, risky, or not safely resolvable in the
  same pass, stop and ask the maintainer instead of guessing.
- Correct stale active docs in the same pass once the current-state behavior is clear.

## Planning And Handoff

`docs/plans/` is inactive by default.

It becomes authoritative only when all of these are true:

1. The work is multi-session or high-risk.
2. A dated plan file is created or updated under `docs/plans/`.
3. The plan starts with a metadata block containing `Status: Active`.

Required active-plan metadata block:

```text
Status: Active
Scope: <task scope>
Owner: <person or session>
```

Rules:

- If no active-plan marker exists, treat `docs/plans/` as reference-only.
- Only one active plan should exist per workstream.
- When the work closes, change the marker to `Status: Historical` or move the document to historical/reference context in the same pass.

## Review Policy

Review should prioritize:

- behavioral regressions
- contract drift at the CLI/config/release-artifact surface
- layer violations
- filesystem ownership leaks
- undocumented authority drift

Changes in `orchestration/coordinator.py`, `errors.py`, `services/report.py`, or packaging workflows should receive extra scrutiny because they are current hotspots or blast-radius multipliers.

## Documentation Freshness Triggers

Update `docs/current-architecture.md` in the same pass when changing:

- composition roots
- runtime phase ordering
- module boundaries
- persistence ownership
- external integrations
- hotspot file structure in a meaningful way

Update this runbook in the same pass when changing:

- verification policy
- risk-tier routing
- plan activation rules
- public API stance
- release-path workflow

Update or remove stale references immediately. Do not leave half-live commands in active docs.

## Repo-Specific Anti-Debt Rules

- Keep config and env-var interpretation inside `config/*`, `cli_entry.py`, and preflight/bootstrap owners.
- Keep HTTP integrations inside `services.metadata`, `services.publishers`, or explicit diagnostics code.
- Use existing atomic-write owners for config and cache persistence paths.
- Preserve lazy CLI import boundaries that avoid importing VS-heavy modules at CLI import time.
- Avoid adding new behavior directly into the hotspot files when a smaller adjacent module can own it cleanly.
- Do not add compatibility shims or legacy bridges unless explicitly requested.
