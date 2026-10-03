# Engineering Runbook

Specialist verification and release procedures for Frame Compare.

## Entrypoint

Start at [`AGENTS.md`](../AGENTS.md) and the repository profile
[`.agents/project.md`](../.agents/project.md). The shared `develop-code`,
`design-code`, `review-code`, and `verify-code` skills own general methodology;
`maintain-workflow` is for explicitly requested maintenance. These are conditional
responsibilities, not mandatory sequential stages.

This runbook owns the detailed verification, deployment, and release procedures
below. Load the applicable section, not the whole document by default.

## Repo Stance

Frame Compare is a CLI-first packaged Python application. The repository profile
owns compatibility scope, product obligations, and local test-design guidance.
Existing implementation structure may be redesigned within the authorized task;
preserve or explicitly change the corresponding product contracts and proof.

## Authority Surfaces

- `AGENTS.md`: concise agent entrypoint; `CLAUDE.md` imports it.
- `.agents/project.md`: local product obligations, source routes, common command
  entry points, and test-policy guidance for the shared skills.
- Shared skills: general implementation, design, review, diagnosis, and evidence
  procedures. Install one canonical copy per host.
- `docs/ENGINEERING_RUNBOOK.md`: complete specialist verification and release
  procedures; these retain their platform and authorization requirements.
- `docs/current-architecture.md`: current ownership, runtime flow, and boundaries.
- `docs/current-cli-contract.md`: documented CLI/config/output behavior.
- `docs/supported-media-runtime.md`: selected native-runtime matrix, provenance,
  licensing, and compatibility boundary.
- `docs/DECISIONS.md`: historical rationale; `docs/api.md`: generated reference,
  not a compatibility promise by itself.
- `CONTRIBUTING.md`: contributor setup and PR mechanics; `README.md`: user overview.
- `docs/plans/**`: task memory activated under Planning And Handoff below.
- Host configuration: tools, permissions, runtime capabilities, and model settings.
  It must not recreate the retired repository role/skill policy.

The old `.codex/review-context.md` and repository skill launchers are retired. Local
or global review consumers must use `.agents/project.md` through `review-code`.
Do not assume a legacy global suite can interpret a newly invented redirect schema.
Observed code describes current behavior; it does not by itself decide intended
behavior when the task or a supported contract requires something different.

## Command Canon

Common contributor setup and Python check entry points are in `.agents/project.md`.
The recipes below supply the additional documentation, runtime, and release proof.

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
uv sync --group dev --group docs --extra vsview --locked
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

Locked dependency audit (PowerShell):

```powershell
$auditRequirements = Join-Path $env:TEMP "frame-compare-audit-requirements.txt"
uv export --frozen --all-groups --all-extras --no-emit-project --format requirements.txt --output-file $auditRequirements
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

Use `verify-code` and `.agents/project.md` to identify the changed claims and select
the relevant routes below. Keep proof tied to the actual source, inputs, dependency
set, and environment. Reuse inspected results while those conditions remain valid;
do not repeat a clean check solely because another workflow stage began.

Full native runs use the measured local count of four workers with `--dist loadgroup`.
Focused selections, including single-test runs, may stay serial; `addopts` does not
enable parallelism. Native CI uses `-n auto --dist loadgroup` because runner core
counts differ. Windows portable CI stays serial. New tests must be parallel-safe:
use `tmp_path` and `monkeypatch`, avoid fixed paths or ports, and use `xdist_group`
only with a stated concrete reason. Existing groups serialize browser tests sharing
a Chrome profile and the alignment-u4 module sharing session-generated media.

### Fast Local Sanity

Use for docs-only changes and small internal refactors that do not touch runtime behavior.

- Run `ruff check .` and `ruff format --check .` when Python files changed.
- Run targeted `pytest` only when a touched module has direct tests.

### Logic Verification

Use for most code changes that do not affect packaging, Docker, Windows portable, or public CLI/config contracts.

- Run the touched tests or a focused `pytest` selection.
- Run `pyright --warnings`.
- Run `ruff check .` and `ruff format --check .`.
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
uv run --no-sync ruff format --check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q -n4 --dist loadgroup
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
- `tests/e2e/` media-tier scenarios
- behavior changes in `orchestration/`, `services/` or `analysis/` that change what a
  media-tier scenario observes: run output, selected frames, screenshots, alignment,
  cache or report payload

Pure calculations or serialization in these owners use the applicable Python gate
when the native execution contract is unchanged. The test suite may mock missing
VapourSynth and skip unavailable real integrations; inspect what actually ran.

Canonical command for the default Docker media runtime:

```bash
bash tools/verify_docker_integration.sh
```

The full default gate runs `tests/e2e/`, `tests/integration/` and `tests/vs/` with
10 workers and `--dist loadgroup`, plus runtime and production-image proofs.
Use `--pytest-path tests/e2e` for focused development or scenario proof; it does not
replace the full gate when the runtime/dependency/media triggers above apply.
The script builds images by default. After `docker-test` dependency or `uv.lock`
changes, rebuild before using the new plugin/runtime; `--no-build` reuses only
known-current images.

The verifier exports `FRAME_COMPARE_TEST_MEDIA_CACHE=/workspace/generated/test-media-cache`
(host `generated/test-media-cache`). Only u4 media is cached, under
`<cache>/<generator>/<key>/`; E2E media is regenerated. The SHA-256 key includes the
exact generator source and complete `ffmpeg -version` output, obtained with an
explicit timeout. Generation publishes by same-filesystem rename and prunes only
that generator's old keys. Tests consume temporary symlinks so source indexes stay
outside the cache. Unset the variable to generate in temporary storage as before.
Run the verifier one at a time from a checkout: overlapping pruning is unsupported.
No CI cache was added; Docker CI retains `--no-cache` and cold regeneration receives
no warm-cache speedup.

If this path cannot be run locally, record it as documented-only until an observed
matching-SHA run of `.github/workflows/docker-integration.yml` supplies the proof.
On pull requests to `main`, `pre-release`, or `staging`, the job runs when changes
touch `src/**`, `tests/**`, the project lock/config files, Docker files, verifier
scripts, or the workflow itself.
Obtain an authorized manual run when required; an absent or skipped CI job is not
successful proof.

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
0.11.0, register `Reference`, `Comparison 1`, and `Comparison 2`, render frame 0 for
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
   verify R80/API R4.3, L-SMASH-Works 1310, vs-placebo 2.0.4, VSView 0.11.0,
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

### Pre-release, staging, and dependency-update flow

- `pre-release` is the current pre-main integration branch. Pull requests targeting
  it receive the same path-applicable CI, documentation, and Docker checks as pull
  requests targeting `main`; `cleanup` previously filled this role and is retired
  from active workflow triggers.
- `staging` is synchronized from `main` and is the integration target for normal
  Dependabot version updates. It is not the pre-main release-integration branch.

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

For entrypoints, `.agents/project.md`, host configuration, review-tool instructions,
or workflow-only prose, use structural proof for the edited surface: run
`git diff --check`, parse edited TOML/YAML/JSON, and resolve changed references.
Confirm host discovery for a new import or installed shared skill. Exercise
representative matching and adjacent nonmatching requests when routing changes.

Run `uv run --no-sync pytest -q tests/test_cli_contract_docs.py` when the CLI
documentation contract it protects changes. It does not establish every Markdown
link or skill trigger. Do not run the product suite solely because workflow prose
changed. Product behavior, executable tooling, and runtime/release changes still
need their applicable proof; no workflow edit may silently weaken that claim.

## Shared Workflow

`develop-code` owns task control and integration. Use `design-code` for consequential
domain/interface decisions, `review-code` for requested or useful independent
assessment, and `verify-code` for diagnosis and evidence. Do not create extra
planner, reviewer, or closeout passes solely to satisfy a role catalogue.

Run independent investigation, checks, and implementation concurrently when useful.
Parallel writers require isolated worktrees or explicit disjoint shared-tree write
ownership, one Git/integration owner, and stable inputs for checks. Serialize real
dependencies, overlapping edits, and shared-runtime conflicts, including the Docker
verifier's single-checkout media-cache pruning. Integrate and verify interactions
that isolated branch results did not cover.

Model identifiers and effort belong to the installed host configuration, not to
permanent repository policy. Select capability against the task and available
allowance; configuration presence is not proof that a capability is available.

## Planning And Handoff

`design-code` owns planning method. The following repository-specific lifecycle
keeps durable task memory out of user-documentation search. `docs/plans/` is
inactive by default.

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

## Documentation Freshness Triggers

Update `docs/current-architecture.md` when a scoped change alters composition,
runtime ordering, ownership, persistence, or external integration boundaries.
Update `docs/current-cli-contract.md` when its documented product behavior changes.

Update `.agents/project.md` for changed local facts, common command routes, or
test-policy decisions. Update this runbook for changed specialist procedures,
verification requirements, plan-search metadata, or release authorization. Update
the corresponding host or review-tool adapter when its discovery semantics change.
Shared methodology belongs in the shared skills, not another repository copy.

Correct stale active references in the same change. Historical plans remain history
and do not require rewriting to resemble the current workflow.
