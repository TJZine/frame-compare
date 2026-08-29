# Engineering Runbook

This is the canonical operating runbook for Frame Compare.

## Entrypoint

`AGENTS.md` owns the repo entrypoint map.

If you land in this document directly, use it as the operating policy, then consult
`docs/current-architecture.md`, `docs/current-cli-contract.md`, `importlinter.ini`, and
`pyproject.toml` as needed.
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
- `.agents/rules/general-guidelines.md`: Antigravity-specific entrypoint shim only
- `docs/ENGINEERING_RUNBOOK.md`: workflow, verification, planning, review, handoff
- `docs/current-architecture.md`: present-day architecture truth
- `docs/current-cli-contract.md`: present-day CLI command, flag, and persistence contract
- `docs/supported-media-runtime.md`: supported media component matrix, provenance, licensing, and native-runtime update boundary
- `docs/DECISIONS.md`: decision log and historical exceptions
- `docs/api.md`: generated reference, not a stability promise by itself
- `.codex/review-context.md`: repo review profile for `suggestion-review`
  and `pr-commit-review`
- `README.md`: product overview, install, quickstart
- `CONTRIBUTING.md`: contributor onboarding and PR mechanics
- `docs/plans/**`: reference-only unless the file has the required search-exclusion
  front matter followed by `Status: Active`
- `.codex/cache/**`: local cache material only, never current authority

Do not create a second runbook, second architecture summary, or second current CLI contract.

## Command Canon

Bootstrap:

```bash
uv sync --group dev --frozen
```

Core local gates:

```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
```

API documentation regeneration and drift check:

```bash
# Regenerate docs/api.md
uv run --no-sync python scripts/generate_api_docs.py

# Check docs/api.md for drift (also run automatically as part of the pytest suite)
uv run --no-sync python scripts/generate_api_docs.py --check
```

Documentation site setup, strict build, and local preview:

```bash
# Install only the locked documentation toolchain
uv sync --only-group docs --locked

# Check generated API documentation before building the site
uv run --no-sync python scripts/generate_api_docs.py --check

# Build with link and configuration validation
uv run --no-sync zensical build --clean --strict

# Preview the site locally
uv run --no-sync zensical serve
```

`docs/**` owns authored site content, while root `zensical.toml` owns site structure,
navigation, and built-in presentation features. Generated output belongs in the ignored
`site/` directory. Restore the contributor environment together with the documentation
toolchain before running Python gates after a docs-only sync:

```bash
uv sync --group dev --group docs --locked
```

Docker integration gate:

```bash
bash tools/verify_docker_integration.sh
```

Default Docker posture:

- Docker is a first-class runtime surface, but the default path is headless and
  deterministic.
- The canonical default Docker verification path uses software Vulkan and CI-safe
  backend rendering rather than GPU passthrough or desktop GUI assumptions.
- The proof must report the exact Debian FFmpeg package and both executable version
  lines; import VapourSynth and verify the expected release/API; register
  L-SMASH-Works, FFMS2, and vs-placebo through deterministic plugin manifests;
  open a generated fixture through both source loaders; invoke `placebo.Tonemap`
  without reducing the result to 8-bit; run `doctor --json`; inspect native
  linkage for missing shared libraries; and execute as a non-root user.
- Optional Docker GPU or GUI profiles require compatible host setup and separate
  verification; do not treat them as covered by the default gate unless the task
  explicitly adds and proves them.

Windows portable local packaging path:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/validate_update_public_key.ps1 -PublicKeyPath tools/windows_portable/update_public_key.xml
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir dist/frame-compare-portable-win-x64 -CacheDir .portable_cache
dist/frame-compare-portable-win-x64/frame-compare.ps1 doctor --json
```

Windows code-only update packaging path:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_update.ps1 -BundleDir .\dist\frame-compare-portable-win-x64 -OutFile .\dist\frame-compare-update-win-x64-<version>.zip
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/sign_update.ps1 -UpdateZip .\dist\frame-compare-update-win-x64-<version>.zip -ExpectedPublicKeyPath .\tools\windows_portable\update_public_key.xml
```

The Windows commands require a Windows host with PowerShell and the expected
toolchain. In non-Windows environments, treat them as documented-only unless a
compatible runner is available. A code-only update does not carry native media
artifacts. `build_update.ps1` must copy the complete bundle's required
media-runtime fingerprint into the signed update manifest, and the installed
updater must refuse a missing, legacy, malformed, or different fingerprint before
any unsafe dependency override. Crossing a media-runtime fingerprint requires a
complete portable bundle reinstall.

Locked runtime dependency audit (PowerShell):

```powershell
$auditRequirements = Join-Path $env:TEMP "frame-compare-audit-requirements.txt"
uv export --frozen --no-dev --all-extras --no-emit-project --format requirements.txt --output-file $auditRequirements
uv run --no-sync pip-audit --strict --require-hashes --disable-pip --progress-spinner off --timeout 20 --vulnerability-service pypi --requirement $auditRequirements
Remove-Item -LiteralPath $auditRequirements
```

Run the audit on both Windows and Linux before a release. The PyPA advisory
database exposed by PyPI is the authority. Any known advisory or dependency
collection failure blocks the release. An exception must be explicit and
time-bounded in the active release plan with the advisory ID, affected package,
owner, rationale, expiry, and removal condition; do not add an unrecorded
`--ignore-vuln`.

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
- Run `bandit -c pyproject.toml -r src --severity-level medium`.
- Run `lint-imports` if imports or top-level module boundaries changed.

### Full Verification

Required for:

- CLI behavior changes
- config loading or env-var behavior changes
- changes in `orchestration/`, `render/`, `vs/`, `services/`
- changes to hot spots listed in the architecture doc
- architecture or CLI/config authority changes that can affect product behavior

Run:

```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
```

### Docker / Runtime Verification

Required when changing:

- `Dockerfile`
- `docker-compose*.yml`
- `tools/verify_docker_*.sh`
- `.github/workflows/docker-integration.yml`
- Docker workflow/contract tests that validate Docker/runtime script or profile semantics
- `src/frame_compare/render/**`
- `src/frame_compare/vs/**`
- integration tests that validate real VS/FFmpeg behavior

Canonical command:

```bash
bash tools/verify_docker_integration.sh
```

If this path cannot be run locally, record it as documented-only and rely on
`.github/workflows/docker-integration.yml`.

For a coordinated media-runtime change, the gate additionally owns immutable
source/wheel hashes and byte sizes, native SONAME/symlink preservation,
`manifest.vs` layout, source-index creation, generated SDR/HDR fixture coverage
where codecs are available, software-Vulkan initialization, vs-placebo filter
execution, runtime fingerprint agreement, and absence of build tooling from the
runtime stage. Do not replace Debian FFmpeg with a custom build without an
explicit security, ABI, licensing, image-size, and multiarchitecture decision.

Current capability contract:

| Environment | Default posture |
| --- | --- |
| macOS Docker Desktop | Supported for backend rendering, reports, and software tonemap only; Docker-based VSPreview GUI launch is unsupported beyond those backend features, and native GPU acceleration/native Qt desktop forwarding are not supported |
| Linux Docker, CPU/software Vulkan | Canonical default Docker path; headless, deterministic, and CI-safe |
| Linux Docker with NVIDIA GPU | Optional `gpu-nvidia` override/profile plus dedicated GPU proof path; documented-only/unverified unless separately proved on a compatible Linux NVIDIA host |
| Linux Docker with X11 GUI | Optional `gui-linux` override/profile plus dedicated GUI proof path; documented-only/unverified unless separately proved on a compatible Linux X11 desktop host |
| Native Windows portable | Separate first-class native runtime/release surface, not a Docker profile |

When documenting or reviewing optional Docker GPU/profile work, cite the official
Docker references in prose so the host/runtime assumptions stay explicit:
[Docker Engine GPU access](https://docs.docker.com/engine/containers/gpu/),
[Docker Desktop GPU support notes](https://docs.docker.com/desktop/features/gpu/),
[Compose profiles](https://docs.docker.com/compose/how-tos/profiles/), and the
[Compose `gpus` service attribute](https://docs.docker.com/reference/compose-file/services/#gpus).

Optional NVIDIA GPU proof command:

```bash
bash tools/verify_docker_gpu.sh
```

That command is not part of the default Docker gate. It is a separate, fail-closed
host-dependent proof for Linux NVIDIA systems only. If the local machine cannot run
it, record GPU support as documented-only/unverified rather than supported.

Optional Linux X11 GUI proof command:

```bash
bash tools/verify_docker_gui.sh
```

That command is not part of the default Docker gate. It is a separate,
host-dependent proof for Linux X11 desktop systems only. The minimal X11 contract
is explicit:

- host `DISPLAY`
- host `/tmp/.X11-unix` socket mount into the container
- optional host `XAUTHORITY` cookie file mount when the X server requires it
- container user/UID aligned to the host UID/GID for local-user X11 permissions

Docs and scripts must not use `xhost +`. If temporary X11 permission widening is
needed, use the narrower host-local form `xhost +si:localuser:<user>` and record
the cleanup command `xhost -si:localuser:<user>`. Real UI launch remains manual
only; the proof command should verify dependency availability and session-script
generation without requiring a visible desktop launch.

If the local machine cannot run the GUI proof command, record GUI support as
documented-only/unverified rather than supported.

### Windows Portable / Release-Path Verification

Required when changing:

- `.github/workflows/release.yml`
- `.github/workflows/release-please.yml`
- `.github/workflows/windows-portable.yml`
- `.github/workflows/windows-portable-build.yml`
- anything under `tools/windows_portable/**`
- installer/update commands or release asset layout in docs
- bundle/update manifests and signing flow

Canonical verification path:

1. Validate the update public key and manifest schemas.
2. Download every artifact with exact byte-size and SHA-256 verification.
3. Build the portable bundle and validate its deterministic ZIP layout, native
   plugin manifests, license inventory, source provenance, and runtime fingerprint.
4. Run the extracted bundle's `--help`, `version`, and `doctor --json` smoke checks;
   verify R79/API R4.2, L-SMASH-Works 1310, vs-placebo 2.0.4, Akarin 1.5.0, VSZip 22.1.0,
   and the selected LGPL-only FFmpeg artifact. FFMS2 must remain absent from the
   Windows baseline. In one
   required bundled Python process, preload the managed VapourSynth runtime before
   importing PyQt6 and VSPreview, then recheck the plugin environment, open the
   generated media through L-SMASH, and invoke the application tonemap path. Run the
   direct vs-placebo frame proof after Qt when Vulkan is usable; an exact
   `vulkan_runtime_unavailable` skip is permitted only on hosts without that runtime
   and does not replace the separate physical-Windows GPU proof.
5. Build the code-only update ZIP when updater logic changes and prove both a
   matching-runtime apply/rollback and a mismatched-runtime fail-closed refusal.
6. Sign the update ZIP when updater or release-package logic changes.
7. Confirm the GitHub Actions Windows workflow still matches the documented local path.

Current CI ownership:

- `.github/workflows/windows-portable.yml` is the existing default-branch
  PR/manual entrypoint. Its `release` operation calls
  `.github/workflows/release.yml` from the selected exact commit, which requires
  channel/version/tag/SHA inputs, rechecks stable against current `main`, rejects
  tag/release collisions, and publishes only after a complete draft asset proof.
  Keeping dispatch at this pre-existing path makes the pre-merge RC reachable
  without a preparatory commit on `main`.
- `.github/workflows/release-please.yml` runs only after the version currently
  recorded in `.release-please-manifest.json` has a matching published stable tag
  and release. This keeps it dormant while the guarded release entrypoint is
  publishing that manifest version, then resumes human-reviewed version/changelog
  PR behavior for later changes. GitHub-release creation remains disabled; the
  guarded entrypoint owns publication.
- `.github/workflows/windows-portable-build.yml` is the reusable full portable
  build/sign/verification boundary called by PR, manual verification, and the
  release orchestrator.
- `.github/workflows/windows-portable-build.yml` also builds and verifies a code-only
  update zip after the full bundle exists. Pull requests prove unsigned update
  zip creation and layout. Reusable release and manual runs require
  `WINDOWS_UPDATE_SIGNING_KEY_XML`; they fail before artifact publication when
  the secret is absent, does not match the committed public key, or signing
  verification fails. Every public Windows release includes the signed update zip
  and its checksum.

GitHub-hosted Windows proves packaging and generated-fixture behavior, not a
physical release workstation. A media-runtime refresh remains unmergeable until
the separate physical-Windows handoff records real GPU Vulkan initialization,
HDR10/Dolby Vision output, range/bit-depth preservation, real-media timing and
frame properties, old/new index and cache behavior, updater migration from the
previous bundle, and objective plus perceptual comparison evidence. Never describe
that handoff as complete based only on hosted CI.

### Staging and dependency-update flow

- `.github/workflows/sync-staging.yml` runs after each `main` push and can also be
  dispatched manually. It fast-forwards `staging` when possible, merges `main`
  when the branches have diverged, and never force-pushes. A concurrent update or
  merge conflict fails closed without changing the remote `staging` branch.
- If a ruleset protects `staging`, it must allow this non-force update (or provide
  an explicit bypass for the workflow actor); a required pull request or required
  status check that blocks the bot will make the sync fail closed. Keep branch
  deletion and force-push protections enabled.
- Normal Dependabot version-update entries in `.github/dependabot.yml` target the
  lowercase `staging` branch so dependency changes can be exercised before they
  reach `main`. GitHub security-update PRs remain governed by GitHub's default
  branch behavior and may still target `main`.
- CI, documentation, Docker, Windows, and PR-title checks remain available for
  `staging` pull requests. Because a `GITHUB_TOKEN` push does not start another
  push-triggered workflow, run the relevant checks manually on `staging` after
  validating an automatic sync and record the results in the PR or handoff.
- Changes to `.github/workflows/sync-staging.yml` require the Full Verification
  commands above plus this integration gate. Record evidence for the active
  `staging` ruleset's behavior for the bot's non-force update, a merge-conflict
  run failing with remote `staging` unchanged, a stale-`main` run refusing to
  push with `staging` unchanged, and a `GITHUB_TOKEN` push producing no second
  push-triggered workflow. If GitHub-only behavior cannot be exercised locally,
  mark it documented-only and require maintainer confirmation; this section is
  the authoritative record.

The first stable lifecycle is release-branch finalization, one squash merge into
`main`, then an exact-SHA guarded dispatch. Do not use a Release Please-generated
initial version-bump commit. Remove temporary `bootstrap-sha` and `release-as`
only during final stable preparation after RC acceptance; the stable validator
rejects them if they remain. Live RC/stable dispatches, production approval,
remote tag/release cleanup, and the final merge are maintainer-only.

When updater or release-package logic changes and the signed-update path cannot
run locally or in CI with `WINDOWS_UPDATE_SIGNING_KEY_XML`, mark signing as
documented-only in the task handoff and require explicit maintainer or
Windows-runner confirmation before treating the signed update release path as
fully verified.

### Workflow And Documentation Verification

For `AGENTS.md`, repo-local skills, role config, or workflow-only runbook changes,
use the smallest structural proof that covers the edited surface:

Always run `git diff --check`. Parse edited TOML or YAML with the repo's existing
tooling, and inspect changed skill, role, and launcher paths or references
directly. Run `uv run --no-sync pytest -q tests/test_cli_contract_docs.py` when
`AGENTS.md`, the current CLI authority links, or CLI contract documentation
changes.

Do not create a generalized workflow verifier unless repeated, measured failures
justify its maintenance cost. Do not run the full product suite solely because
workflow prose changed. Use full verification when the same change also modifies
product code, executable tooling, architecture, or a public CLI/config contract.

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
- architecture or CLI/config contract authority changes tied to product behavior

Require:

- explicit task plan before editing
- same-pass updates to the relevant authority docs
- full verification, plus Docker or Windows verification if those surfaces changed

For single-session work, including single-session high-risk work, the default plan can
live inline in the current task, review, or PR. Activate `docs/plans/` only when the
work needs a durable cross-session handoff or the maintainer explicitly asks for a
tracked plan file.

## Orchestration Policy

Use the lightest workflow that still protects the outcome:

- Low risk: one agent, focused proof, and a local diff audit.
- Medium risk: one agent plans and implements. Add one independent final review
  only when the change is novel, broad, weakly covered, or hard to validate.
- High risk: explicit plan, implementation, risk-matched verification, and one
  independent final review.
- Separate planner: only for ambiguous seams, cross-session work, or genuinely
  large multi-boundary changes.
- Repeated evaluator/reviewer loops: only after a material finding or measured
  evidence that another pass improves the result.

Delegate independent read-heavy exploration, documentation research, log analysis,
or long waits when useful. Parallel writes require disjoint write boundaries and an
approved integration plan; require exact file lists only when concurrent writers or
sensitive shared surfaces need collision protection. Use `worker_luna` by default
for bounded delegated implementation when the outcome, owner seam, contracts,
acceptance criteria, and direct proof are clear, including work that needs
repository comprehension, exact-file discovery, and routine local coding judgment.
Use `worker` when the same settled bounded unit needs material local design
judgment, cross-boundary comprehension, complex diagnosis, or proof interpretation.
Return unresolved product, ownership, public-contract, architecture, or proof
decisions to planning. Plans describe risk and constraints rather than permanently
binding a model; the controller selects the current role at dispatch, reviews the
diff, and reverifies the result. Keep delegation depth shallow.

For genuinely large multi-unit work, explicitly use the
`large-task-orchestration` skill. The main task remains the authoritative
controller and integrates checkpointed, decision-complete units. Reuse a completed
worker only for adjacent work with the same owner and contracts; use a fresh worker
when the seam or assumptions change, and a fresh read-only reviewer for required
independent final review. Give that reviewer a bounded task/diff/proof/risk packet
without the implementation transcript. Treat six threads as a cap rather than a
target and keep delegation depth at one.

## Production Quality Guardrails

Every non-trivial code change should be checked against these criteria before
closeout. Passing tests are required evidence, not the full definition of done.

- Correctness first: preserve documented CLI/config behavior, exit codes, generated
  output contracts, filesystem effects, and release/runtime behavior unless the task
  explicitly changes them.
- Architecture fit: keep behavior in the current owner when it shares the same
  invariants, state, lifecycle, and reason to change. Extract only a distinct
  present-day responsibility; respect `importlinter.ini`, and reject both hotspot
  accretion and line-count-driven pass-through abstractions.
- Boundary hygiene: keep config/env interpretation, filesystem persistence, HTTP
  integrations, subprocess/runtime details, report generation, and packaging policy
  behind their documented owners.
- Contract discipline: one public shape per operation, deterministic JSON/TOML/report
  output, no silent public-surface drift, and same-pass updates to authority docs when
  public behavior changes.
- Maintainability: prefer the simplest correct design that matches existing patterns;
  apply DRY where duplication is harmful, avoid premature abstractions, speculative
  options, dead code, debug leftovers, commented-out code, misleading names, and
  unnecessary indirection.
- YAGNI: every new abstraction, option, fallback, retry, cache, or edge-case branch
  must serve a current requirement, reachable input, observed failure, or real
  trust/runtime boundary. Do not encode hypothetical futures.
- Compatibility restraint: do not add legacy bridges, compatibility shims, fallback API
  variants, or broad migration paths unless the maintainer explicitly approves them.
- Test quality: prove behavior through public seams where practical, avoid brittle
  snapshots and private implementation probes, and add focused regression or contract
  coverage when existing tests do not protect the changed surface.
- Runtime and release honesty: Docker, FFmpeg/VapourSynth, browser-open, Windows
  portable, and updater/signing paths must be verified through the runbook commands
  when touched; if the local environment cannot run a required path, record it as
  documented-only and do not claim full verification.
- Exception records: intentional departures from these guardrails need an owner, a
  reason, verification evidence, and a removal or revisit trigger.

## Task Routing Matrix

Use this as the default routing shortcut before exploring deeper:

| Task family | Primary authority | Typical owner files | Default tier | Default verification |
| --- | --- | --- | --- | --- |
| CLI/config contract change | `docs/current-cli-contract.md` | `src/frame_compare/cli/entry.py`, `src/frame_compare/config/overrides.py`, focused `tests/cli/test_*.py`, `tests/config/test_overrides.py`, `tests/test_cli_contract_docs.py` | High | Full verification |
| Internal logic change outside hotspots/public CLI | `docs/current-architecture.md` | Existing owner module plus nearby tests | Medium | Logic verification |
| Hotspot or runtime pipeline change | `docs/current-architecture.md` | `orchestration/`, `render/`, `vs/`, hotspot files, adjacent tests | High | Full verification, plus Docker when listed under Docker/runtime verification |
| Docker/runtime environment change | this runbook + `docs/current-architecture.md` | `Dockerfile`, `docker-compose*.yml`, `tools/verify_docker_*.sh`, `.github/workflows/docker-integration.yml`, Docker workflow/contract tests, runtime integration tests | High | Full verification plus Docker/runtime verification |
| Windows portable or release-path change | this runbook | `tools/windows_portable/**`, `.github/workflows/windows-portable.yml`, release-path docs | High | Full verification plus Windows portable/release-path verification |
| Workflow-only authority change | this runbook | `AGENTS.md`, repo-local skills, `.codex/config.toml`, `.codex/agents/**`, workflow-only runbook sections | Medium | Workflow/documentation verification |
| Architecture or public contract authority change | affected authority doc | `docs/current-architecture.md`, `docs/current-cli-contract.md`, related product/tests | High | Full verification |

### Stop And Ask

Stop and get maintainer confirmation if any of these are unclear:

- product invariants
- deployment/runtime model
- security-sensitive boundaries
- conflicting workflow docs
- whether an import-level API should be treated as stable

## Discrepancy Handling

- `AGENTS.md` controls entrypoint order.
- `.agents/rules/general-guidelines.md` is an Antigravity shim and must defer to
  `AGENTS.md` plus this runbook when instructions conflict.
- Observed code, config, and successfully executed commands outrank stale prose in
  `docs/current-architecture.md`, `docs/current-cli-contract.md`, `README.md`,
  `CONTRIBUTING.md`, `docs/DECISIONS.md`, historical plans, and cached review material.
- When a doc/code mismatch looks intentional, risky, or not safely resolvable in the
  same pass, stop and ask the maintainer instead of guessing.
- Correct stale active docs in the same pass once the current-state behavior is clear.

## Planning And Handoff

`docs/plans/` is inactive by default.

It becomes authoritative only when all of these are true:

1. The work needs a durable cross-session handoff, or the maintainer explicitly asks for a tracked plan file.
2. A dated plan file is created or updated under `docs/plans/`.
3. The plan has the required Zensical search-exclusion front matter followed by an
   activation metadata block containing `Status: Active`.

Required active-plan preamble:

```text
---
search:
  exclude: true
---

Status: Active
Scope: <task scope>
Owner: <person or session>
```

Rules:

- If no active-plan marker exists, treat `docs/plans/` as reference-only.
- Keep `search.exclude: true` on every tracked plan so internal planning material
  cannot enter the user-documentation search index.
- For single-session work, keep the plan inline unless a durable handoff is needed.
- Only one active plan should exist per workstream.
- When the work closes, change the marker to `Status: Historical` or move the document to historical/reference context in the same pass.

## Review Policy

Review should prioritize:

- behavioral regressions
- contract drift at the CLI/config/release-artifact surface
- layer violations
- filesystem ownership leaks
- undocumented authority drift

Changes in `orchestration/coordinator.py`, `errors.py`, `services/report/**`, or packaging workflows should receive extra scrutiny because they are current hotspots or blast-radius multipliers.

Production LOC is an architecture-attention signal, not a decomposition rule.
Exclude generated assets. For a touched owner above 500 lines, inspect the full file
and record `Owner | Existing responsibility | New behavior | Decision | Evidence`.
For a touched owner above 800 lines, a named hotspot, or a composition root, require
one fresh `reviewer` architecture review. A cohesive owner may grow; a smaller file
must still split when it gains a distinct responsibility.

Review is risk-triggered, not universal ceremony. One independent final review is
the default high-risk gate. Review a plan only when its seam or public contract is
still expensive to get wrong. Do not require both same-reviewer closure and a fresh
clean review for an unchanged artifact.

## Subagent Transparency

When dispatching a subagent, record the selected role and its
`.codex/agents/<role>.toml` path. At task closeout, list each role used with
the `model` and `model_reasoning_effort` read from that TOML. The child role's
`CONFIGURED ROLE` opening line is a visible confirmation of the selected role;
the TOML remains the authoritative configuration and avoids duplicating model
names in prompts or workflow docs.

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

- Keep config and env-var interpretation inside `config/*`, `cli/entry.py`, and preflight/bootstrap owners.
- Keep HTTP integrations inside `services.metadata`, `services.publishers`, or explicit diagnostics code.
- Use existing atomic-write owners for config and cache persistence paths.
- Preserve lazy CLI import boundaries that avoid importing VS-heavy modules at CLI import time.
- Keep cohesive behavior with its current owner. When a hotspot gains a distinct
  present-day responsibility, move that responsibility to one focused adjacent owner.
- Do not create thin wrappers, speculative extension points, or extra modules solely
  to satisfy a file-length threshold.
- Do not add compatibility shims or legacy bridges unless explicitly requested.
