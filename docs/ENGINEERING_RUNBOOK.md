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
compatible runner is available. `build_portable.ps1` packages application source
and builds wheel metadata from committed `HEAD`, excluding uncommitted changes in
`src/frame_compare` and `pyproject.toml`. Record the packaged SHA and relevant
working-tree differences; a successful bundle check does not verify excluded edits.
Other packaging inputs may come from the worktree, so a SHA alone does not describe
a dirty local build. Use a candidate commit when authorized or record that candidate
packaging proof remains outstanding; this recipe does not authorize a commit.
A code-only update does not carry native media
artifacts. `build_update.ps1` accepts only a native-panel-capable full bundle with
`bundle_info.schema_version` 3, and copies the complete bundle's required
media-runtime fingerprint into the signed update manifest. The installed updater
refuses pre-native-panel schema-2 bundles, as well as missing, legacy, malformed,
or different fingerprints, before any unsafe dependency override; each refusal
requires a complete portable bundle reinstall. Crossing a media-runtime
fingerprint also requires a complete portable bundle reinstall.

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

Choose verification from the behavior and contracts changed, using the paths below
as discovery aids. Comments, formatting, and demonstrably nonbehavioral edits may
use Fast Local Sanity even in a hotspot or runtime directory; explain briefly why
the broader gate adds no relevant proof. Uncertain runtime, public-contract, or
release impact still requires the matching stronger gate.

Inspect affected owners, callers, contracts, and existing tests before narrowing a
gate. Read the relevant authority sections first and broaden when dependencies or
invariants remain unclear. Do not omit a changed boundary to reduce context.

Verification remains current when its output was inspected and the checked code,
inputs, dependencies, and relevant environment are unchanged. Reuse that evidence,
including a worker's observed results. Rerun affected checks after integration or
other changes invalidate it; run additional integration proof for interactions not
covered by unit results. Do not repeat an unchanged clean gate solely at closeout.

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
- behavior changes in `orchestration/`, `render/`, `vs/`, `services/`
- behavior or ownership changes to hot spots listed in the architecture doc
- architecture or CLI/config authority changes that can affect product behavior

Run:

```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
```

### Report Viewer Verification

For changed viewer state, reuse the focused `tests/services/test_report_*.py`
coverage and JavaScript harnesses through `tests/services/node_harness.py`, which
uses the locked Node runtime. Changes to browser initialization, DOM interaction,
keyboard/focus behavior, or layout also need real-browser proof:

```bash
uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py
```

The tests discover Chrome/Chromium on PATH or native macOS Chrome; `REPORT_BROWSER`
can select an executable explicitly. Inspect relevant skips: when no browser is
available, pytest success does not prove browser behavior. CI's `report-browser`
job preflights the executable and requires this smoke. Record an observed matching
SHA result when using hosted proof. Reuse a full-suite result if the relevant browser
tests actually ran; do not repeat the same check solely as a separate closeout gate.
Use focused visual/manual inspection for changed appearance or interactions the
existing smoke does not exercise. Node, markup, and browser smoke each prove only
their asserted behavior. Viewer work does not by itself require native media proof.

### Python Distribution Verification

Changes to build configuration, package inclusion, bundled assets, distribution
metadata, or installed entry points require distribution proof in addition to the
applicable Python checks. Use the existing `package` job in `.github/workflows/ci.yml`;
this POSIX local equivalent uses a fresh output directory and install environment:

```bash
distribution_dir=$(mktemp -d "${TMPDIR:-/tmp}/frame-compare-dist.XXXXXX")
uv build --out-dir "$distribution_dir"
uv venv "$distribution_dir/venv" --python 3.13
"$distribution_dir/venv/bin/python" scripts/verify_distribution.py "$distribution_dir"
uv pip install --python "$distribution_dir/venv/bin/python" "$distribution_dir"/*.whl
"$distribution_dir/venv/bin/frame-compare" version
"$distribution_dir/venv/bin/frame-compare" --help
```

The verifier requires exactly one wheel and sdist. Inspect the built artifacts and
installed behavior affected by the task; the verifier and help/version smoke do not
exercise every packaged feature. On Windows use the corresponding `Scripts`
executables or an observed matching-SHA CI package result. This route does not prove
Windows portable layout, native plugins, updater behavior, or signing. Runtime
dependency changes also need the matching dependency audit and deployment proof.

### Docker / Runtime Verification

Required when changing runtime behavior, dependencies, or executable integration
contracts in these surfaces. Route by the changed external call even when its
owner is outside a listed directory:

- `Dockerfile`
- `docker-compose*.yml`
- `tools/verify_docker_*.sh`
- `.github/workflows/docker-integration.yml`
- Docker workflow/contract tests that validate Docker/runtime script or profile semantics
- `src/frame_compare/render/**`
- `src/frame_compare/vs/**`
- native metric evaluation in `src/frame_compare/analysis/metrics.py` or `metric_strategies.py`
- FFmpeg/ffprobe execution in `src/frame_compare/services/alignment_audio.py`
- shared process behavior in `src/frame_compare/utils/subproc.py` affecting media calls
- integration tests that validate real VS/FFmpeg behavior

Pure calculations or serialization in these owners use the applicable Python gate
when the native execution contract is unchanged. The test suite may mock missing
VapourSynth and skip unavailable real integrations; inspect what actually ran.

Canonical command for the default Docker media runtime:

```bash
bash tools/verify_docker_integration.sh
```

If this path cannot be run locally, record it as documented-only until an observed
matching-SHA run of `.github/workflows/docker-integration.yml` supplies the proof.
Inspect its event/path filters: a PR need not trigger it for every relevant owner
(including alignment services or the workflow file itself). Obtain an authorized
manual run when required; an absent or skipped CI job is not successful proof.

`src/frame_compare/vsview/**` also owns an external plugin/process/UI boundary.
Pure metadata/result validation uses focused Python proof and the applicable full
gate. Changes to plugin discovery, launch/lifetime, Qt callbacks, or generated native
sessions require compatible-host integration proof: use the Linux GUI verifier or
Windows portable route for the platform changed. The default Docker gate does not
cover VSView. Retain the offscreen/visible/physical-host distinctions below.

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
| macOS Docker Desktop | Supported for backend rendering, reports, and software tonemap only; Docker-based VSView GUI launch is unsupported beyond those backend features, and native GPU acceleration/native Qt desktop forwarding are not supported |
| Linux Docker, CPU/software Vulkan | Canonical default Docker path; headless, deterministic, and CI-safe |
| Linux Docker with NVIDIA GPU | Optional `gpu-nvidia` override/profile plus dedicated GPU proof path; documented-only/unverified unless separately proved on a compatible Linux NVIDIA host |
| Linux Docker with X11 GUI | Optional `gui-linux` override/profile; the verifier contract covers offscreen VSView/plugin/session/metadata/result proof, but this feature run has static contract proof only and execution plus visible X11 launch remain unavailable/unverified until separately proved on a compatible Linux X11 desktop host |
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

The verifier contract covers this offscreen path: the `gui-linux` image must discover
and load the exact Frame Compare VSView panel entry point, construct the panel in its
inert ordinary-session state, load a production-generated L-SMASH session with VSView
0.10.3, register `Reference`, `Comparison 1`, and `Comparison 2`, render frame 0 for
all three outputs, and round-trip/validate the sibling result sidecar. This feature run has
static contract proof only; execution remains unavailable/unverified until a
compatible Linux/X11 host runs it. The contract does not prove a visible X11 desktop
launch, Qt ergonomics, native Windows behavior, or physical-Windows acceptance.

If the local machine cannot run the GUI proof command, record GUI support as
documented-only/unverified rather than supported.
On macOS, an offscreen or synthetic-panel check proves only the Python/Qt/plugin
contract; if `core.lsmas` is absent, it is not native L-SMASH media proof. Linux X11
visible-GUI behavior remains unavailable/unverified until a compatible host runs it.

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
   verify R79/API R4.2, L-SMASH-Works 1310, vs-placebo 2.0.4, VSView 0.10.3,
   PySide6 6.11.2, BestSource, vspackrgb, and the selected LGPL-only
   FFmpeg artifact. FFMS2 must remain absent from the Windows baseline. In one
   required bundled Python process, preload the managed VapourSynth runtime before
   importing PySide6 or VSView, then recheck the plugin environment, open the generated
   media through L-SMASH, and invoke the application tonemap path. The build must fail
   closed unless exactly one repository wheel and one `frame_compare-*.dist-info`
   directory exist; it copies only that metadata directory into `app/site-packages`,
   verifies the exact `frame-compare-alignment-review` entry point, and keeps executable
   application code resolved from `app/src`. The bundled Python proof must discover
   and load that entry point, construct the panel offscreen, round-trip the generated
   metadata/result sidecar, and reject a malformed result. BestSource is VSView/UI-only
   and does not replace Frame Compare's generated-session source loader.
   Run the direct vs-placebo frame proof after Qt when Vulkan is usable; an exact
   `vulkan_runtime_unavailable` skip is permitted only on hosts without that runtime
   and does not replace the separate physical-Windows GPU proof.
5. Build the code-only update ZIP when updater logic changes and prove both a
   matching-runtime apply/rollback and a mismatched media-runtime or requirements-
   fingerprint fail-closed refusal. Every pre-native-panel schema-2 bundle must be
   refused and fully reinstalled; a code-only update must not mix its old UI/native
   dependency graph with the new application code, even when the media-runtime
   fingerprint and L-SMASH index token are unchanged. The current full bundle
   advertises `bundle_info.schema_version` 3.
6. Sign the update ZIP when updater or release-package logic changes.
7. Confirm the GitHub Actions Windows workflow still matches the documented local path.
   For an exact hosted verification of a candidate SHA, dispatch the default-branch
   workflow with its explicit verify inputs (the workflow checks out the supplied SHA):

   ```bash
   WorkflowRef='<branch-containing-the-workflow>'
   ExpectedSha='<40-character-lowercase-head-sha-of-WorkflowRef>'
   gh workflow run windows-portable.yml \
     --ref "$WorkflowRef" \
     -f operation=verify \
     -f channel=rc \
     -f expected_sha="$ExpectedSha"
   gh run list --workflow windows-portable.yml --limit 1
   ```

   The secret-free validation job requires `ExpectedSha` to equal the selected
   protected branch head or protected, conventionally named release-tag head before
   the signed reusable workflow can start. The selected `release-candidate` or `production`
   environment owns the signing key, required reviewer approval, and allowed
   deployment branch/tag rules; `windows-ci` is the unsigned pull-request environment
   and must not contain signing secrets. Record the resulting workflow URL, exact SHA,
   success/failure result, and any uploaded portable/package proof. A hosted success
   proves package/offscreen behavior;
   complete physical Windows desktop acceptance remains a separate handoff.

   Before enabling this workflow, maintainers must finish the environment migration:

   - create `windows-ci` without secrets or approval requirements;
   - require reviewers and restrict deployment branches/tags on both
     `release-candidate` and `production`;
   - store `WINDOWS_UPDATE_SIGNING_KEY_XML` only as an environment secret in both
     protected environments; and
   - atomically remove the same-named repository secret and any organization secret
     that grants this repository access, then confirm `windows-ci` and an ordinary
     workflow cannot resolve it.

   GitHub resolves same-named environment secrets ahead of repository/organization
   secrets rather than enforcing an environment-only namespace. The migration and
   hosted negative-access proof are therefore release-blocking prerequisites.
   Guarded RC and stable releases must also be dispatched from a protected branch;
   the release workflow creates the validated release tag only after its preflight.

Current CI ownership:

- `.github/workflows/windows-portable.yml` is the existing default-branch
  PR/manual entrypoint. Its `release` operation calls
  `.github/workflows/release.yml` from the selected exact commit, which requires
  channel/version/tag/SHA inputs, rechecks stable against current `main`, rejects
  tag/release collisions, renders the matching validated `CHANGELOG.md` section as
  the release body, and publishes only after complete draft asset and body proof.
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
  zip creation and layout in the secret-free `windows-ci` environment. Reusable
  release and manual runs obtain `WINDOWS_UPDATE_SIGNING_KEY_XML` from the selected
  protected `release-candidate` or `production` environment only after its approval
  and branch/tag rules pass; they fail before artifact publication when the secret is
  absent, does not match the committed public key, or signing verification fails.
  Every public Windows release includes the signed update zip and its checksum.

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
run locally or in CI with `WINDOWS_UPDATE_SIGNING_KEY_XML` (mapped from the protected
environment secret in hosted CI), mark signing as
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
Corrections to an ownership description that only reflect existing code use this
structural route; an intentional architecture or public behavior change still uses
the stronger gate. For skill edits, validate front matter and references, then check
representative matching and adjacent nonmatching tasks against the description and
instructions. Structural validity alone does not establish good task routing.

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
- High risk: explicit plan, implementation, and risk-matched verification. Add one
  independent review when a consequential risk needs a second assessment under
  Review Policy; the tier alone does not require a reviewer.
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
diff, and confirms current verification under Verification Policy. Keep delegation
depth shallow. An approved write boundary may be established by the main agent
within the user's authorized task; it is not a separate user approval gate.

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
| Report viewer behavior | `docs/current-architecture.md` Report Viewer section | `services/report/**`, Node harnesses, `tests/browser/` | High | Full verification plus relevant browser/visual proof; reuse browser tests already exercised |
| Python distribution contents or entry points | this runbook + `pyproject.toml` | build settings, bundled assets, `scripts/verify_distribution.py`, CI `package` job | High | Full verification plus distribution verification; add platform gates only for affected deployments |
| Windows portable or release-path change | this runbook | `tools/windows_portable/**`, `.github/workflows/windows-portable.yml`, release-path docs | High | Full verification plus Windows portable/release-path verification |
| Workflow-only authority change | this runbook | `AGENTS.md`, repo-local skills, `.codex/config.toml`, `.codex/agents/**`, workflow-only runbook sections | Medium | Workflow/documentation verification |
| Architecture or public contract authority change | affected authority doc | `docs/current-architecture.md`, `docs/current-cli-contract.md`, related product/tests | High | Full verification |

### Continue Or Escalate

Carry authorized work through implementation, applicable verification, and repair
of failures caused by the change. Resolve routine ownership, implementation, and
verification questions from current source, tests, relevant authority sections,
and existing task decisions. Record consequential conclusions briefly.

Ask the maintainer only when investigation leaves a consequential choice outside
the established task: product intent, a compatibility promise, deployment/runtime
model, a security or data-loss boundary, or irreconcilable authoritative guidance.
Existing task authorization remains valid. Explicit release/production approval
boundaries elsewhere in this runbook still apply.

Workers return decisions outside their assigned boundary to the main agent. The
main agent resolves them within the user's authorization before escalating to the
user. Continue independent work while a genuinely required decision is pending.

## Discrepancy Handling

- `AGENTS.md` controls entrypoint order.
- `.agents/rules/general-guidelines.md` is an Antigravity shim and must defer to
  `AGENTS.md` plus this runbook when instructions conflict.
- Observed code, config, and successfully executed commands outrank stale prose in
  `docs/current-architecture.md`, `docs/current-cli-contract.md`, `README.md`,
  `CONTRIBUTING.md`, `docs/DECISIONS.md`, historical plans, and cached review material.
- Investigate doc/code mismatches using the task and current evidence. Ask only
  when a consequential intended contract remains unresolved; stale prose alone
  does not require confirmation.
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

Production LOC and named hotspots are attention signals. For behavior or ownership
changes in a large owner, inspect enough of its lifecycle, callers, and invariants
to judge cohesion; expand to the full owner when needed. Record a brief disposition
when the change adds or moves responsibilities. Neither the 500/800-line thresholds
nor a file's name requires an independent review or an extraction by itself.

Use one independent review when requested or when a consequential unresolved risk
benefits from a second assessment: novel security/data-loss boundaries, complex
concurrency or native lifetime changes, broad contract migrations, or weak proof
of changed behavior. State the concrete reason before dispatch. Small, well-proved
changes do not require a reviewer because of their location or risk label alone.
Review a plan separately only when its seam or public contract is still expensive
to get wrong. Do not require both same-reviewer closure and a fresh clean review
for an unchanged artifact.

## Subagent Transparency

When dispatching a subagent, resolve its `config_file` from `.codex/config.toml`
and record the selected role and resolved TOML path; role keys need not match file
names. At task closeout, list each role used with
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

- Keep config and env-var interpretation inside config, CLI command, and preflight/bootstrap owners.
- Keep HTTP integration at the current external-boundary owners: TMDB lookup behind
  the metadata facade, publishing, isolated webhook delivery, and diagnostics.
  The coordinator owns default shared-client creation; callers own injected clients.
- Use existing atomic-write owners for config and cache persistence paths.
- Preserve lazy CLI import boundaries that avoid importing VS-heavy modules at CLI import time.
- Keep cohesive behavior with its current owner. When a hotspot gains a distinct
  present-day responsibility, move that responsibility to one focused adjacent owner.
- Do not create thin wrappers, speculative extension points, or extra modules solely
  to satisfy a file-length threshold.
- Do not add compatibility shims or legacy bridges unless explicitly requested.
