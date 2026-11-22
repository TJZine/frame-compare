# Engineering Runbook

Specialist verification and release procedures for Frame Compare.

## Entrypoint

Start at the repository-root `AGENTS.md` and `.agents/project.md` profile
(these source files are outside the documentation site). The shared `develop-code`,
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
- `docs/DECISIONS.md`: historical rationale.
- `CONTRIBUTING.md`: contributor setup and PR mechanics; `README.md`: user overview.
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

Documentation site setup, strict build, and local preview:

```bash
# Install only the locked documentation toolchain
uv sync --only-group docs --locked

# Build with link and configuration validation
uv run --no-sync zensical build --clean --strict

# Preview the site locally
uv run --no-sync zensical serve
```

`docs/**` owns authored site content and its assets. Root `zensical.toml` owns site
structure, navigation, and theme features, and `overrides/` owns the theme templates.
Generated output belongs in the ignored `site/` directory. Restore the contributor
environment together with the documentation toolchain before running Python gates after
a docs-only sync:

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

Windows portable local packaging path:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir dist/frame-compare-portable-win-x64 -CacheDir .portable_cache
dist/frame-compare-portable-win-x64/frame-compare.ps1 doctor --json
```

The Windows commands require a Windows host with PowerShell and the expected
toolchain. `build_portable.ps1` uses one commit for the application source,
wheel metadata, dependency lock, default portable manifest, vendored
notices, and source inventory. Use `-ExpectedCommitSha` to select it, or let
the builder capture `HEAD` once. A custom `-ManifestPath` supplies its own
manifest and adjacent notices. The installer and shims come from the live
worktree. Record the selected SHA and worktree differences for a local build
of an older commit. Version 2 manifests remain available for local builds with
matching application source, the original embedded Python files and wheel-provided
Qt FFmpeg. Version 3 omits the optional Python SQLite binaries and requires one
Qt FFmpeg overlay. Hosted builds require version 3. `-ReleaseBuild` also requires
a clean worktree at the selected commit before reserving output.

Locked dependency audit (PowerShell):

```powershell
$auditRequirements = Join-Path $env:TEMP "frame-compare-audit-requirements.txt"
uv export --frozen --all-groups --all-extras --no-emit-project --format requirements.txt --output-file $auditRequirements
uv run --no-sync pip-audit --strict --require-hashes --disable-pip --progress-spinner off --timeout 20 --vulnerability-service pypi --requirement $auditRequirements
Remove-Item -LiteralPath $auditRequirements
```

The reusable source-security workflow runs the lock audit on both Windows and
Linux against the explicit candidate SHA. On a PR, the caller supplies the PR head
SHA, and on a push or CI dispatch it supplies the event SHA. The release caller
uses its planned release SHA and requires the audit before the Windows build. Both audit
jobs verify the checked-out commit before installing tools or reading inputs.
The PyPA advisory database exposed by PyPI is the authority for this dependency
check. Known advisories and dependency collection failures block the gate.
The source audit has no advisory suppressions.

`bash tools/check_python_security.sh` runs Ruff and Bandit over the application,
maintained release scripts, and the selected runtime and diagnostic tools. It
fails on missing targets, incomplete scans, and medium or high findings. Bandit
excludes tests and fixtures. Triage subprocess findings at the call site. The
reviewed low-severity cases in the release and runtime tools use argument
vectors without shell evaluation for pinned tools, resolved executables, or the
invoking interpreter. Retain the medium/high gate and use rule-specific
annotations for any justified exception at that severity.

## Verification Policy

Use `verify-code` and `.agents/project.md` to identify the changed claims and select
the relevant routes below. Keep proof tied to the actual source, inputs, dependency
set, and environment. Reuse inspected results while those conditions remain valid;
do not repeat a clean check solely because another workflow stage began.

The repository-local `verify-frame-compare` skill under
`.agents/skills/verify-frame-compare/` owns the application user-journey map and
driving entrypoint. Use affected journeys alongside the relevant procedures below;
it adds no universal gate. Its shared creation/maintenance procedures run on
request. Native and physical Windows acceptance remain separate proof obligations.

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
- Run `bash tools/check_python_security.sh`.
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
bash tools/check_python_security.sh
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
"$distribution_dir/venv/bin/python" -c 'from frame_compare.services.report.viewer import get_css, get_js; assert get_css() and get_js()'
```

The verifier requires exactly one wheel and sdist, with the report viewer assets
and `py.typed` present in both. CI also reads the report CSS and JavaScript from the
freshly installed wheel. Inspect any other installed behavior affected by the task. On Windows use the corresponding `Scripts`
executables or an observed matching-SHA CI package result. This route does not prove
Windows portable layout, native plugins, ZIP installation, or artifact scanning. Runtime
dependency changes also need the matching dependency audit and deployment proof.

### Docker / Runtime Verification

Required when changing runtime behavior, dependencies, or executable integration
contracts in these surfaces. Route by the changed external call even when its
owner is outside a listed directory:

- `Dockerfile`
- `docker-compose*.yml`
- `tools/verify_docker_*.sh`
- `tools/docker_runtime_smoke.py`
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
bash tools/verify_docker_context.sh
bash tools/verify_docker_integration.sh
```

The context probe uses disposable, harmless `.env` and private-key-style
sentinels. It checks the real Docker ignore rules, then exports the exact
`application-inputs` stage used by the runtime and compares its entire file
list. The production image copies that stage and the explicit locked package
metadata. The test service mounts the checkout for tests and verification tools.

CI runs this gate on native AMD64 and ARM64 Linux runners and uploads a separate
artifact for each architecture. The separate alignment resource benchmark runs on AMD64.

The full default gate runs `tests/e2e/`, `tests/integration/` and `tests/vs/` with
10 workers and `--dist loadgroup`, plus runtime and production-image proofs.
It explicitly excludes `tests/integration/test_alignment_streaming_resources.py`.
`tools/verify_docker_integration.sh` owns image builds, container invocation,
cleanup, logs, and artifact handling. It retains `pytest.xml` in each run's artifact
directory. The gate requires a readable JUnit report with at least one test and
zero skipped or xfailed tests. The verifier sets pytest's xfail default to strict,
so an unexpected pass fails unless the test explicitly sets `xfail(strict=False)`.
A Docker or log-writer failure fails the gate. The verifier invokes the repository-owned
`tools/docker_runtime_smoke.py` from the test service's repository mount for
native runtime, provenance, fixture, and application assertions. The tool remains
in the workflow trigger paths.
Lint and shell-routing tests support the canonical gate but do not replace it.

The production-image proof must run with a read-only media mount and writable
generated mount. Record first-run managed index creation and second-run
`cache=0` reuse. Preserve hashes and modification times for both managed
entries on reuse and legacy media-adjacent sentinels throughout the proof.
Compare the media directory listing before and after. The corresponding native
Windows observations belong to the
[physical Windows validation](media-runtime-windows-validation.md#7-cache-and-index-isolation).

For changes to whole-track memory bounds, maximum admitted lag, or streaming collector
cleanup, run the existing resource proof separately after the canonical gate has
built the test image:

```bash
docker compose run --rm --no-deps \
  -e FRAME_COMPARE_CONTINUOUS_ALIGNMENT_RESOURCES=1 \
  --entrypoint python frame-compare-test \
  -m pytest -o cache_dir=/tmp/frame-compare-resource-pytest-cache \
  tests/integration/test_alignment_streaming_resources.py -rsx -s
```

This observes three-hour RSS bounds, the largest admitted lag, and cancellation
with real child reaping. Docker CI invokes it in a separate step. A successful
canonical gate alone does not establish those resource claims.

Use `--pytest-path tests/e2e` for focused development or scenario proof; it does not
replace the full gate when the runtime/dependency/media triggers above apply.
The script builds images by default. After `docker-test` dependency or `uv.lock`
changes, rebuild before using the new plugin/runtime; `--no-build` reuses only
known-current images.

The verifier exports `FRAME_COMPARE_TEST_MEDIA_CACHE=/workspace/generated/test-media-cache`
(host `generated/test-media-cache`). Only u4 media is cached, under
`<cache>/<generator>/<key>/`; E2E media is regenerated. The SHA-256 key includes the
exact `tests/integration/alignment_u4_media_recipes.py` source and complete
`ffmpeg -version` output, obtained with an explicit timeout. Assertion-only and
store-only edits retain cached media. Recipes generate on demand with their declared
prerequisites; each file publishes atomically by temporary file + replace. The full
verifier passes `FRAME_COMPARE_U4_MEDIA_FULL=1` to prepare all 40 files; focused
`--pytest-path` runs remain demand-driven. Only that generator's obsolete keys and
temporary files are pruned while a session-held `.verifier.lock` protects generation
and use. The lock file is never pruned. Tests consume temporary symlinks so source
indexes stay outside the cache. Unset the cache variable for lazy temporary generation.
Worker preparation stats (key, created/reused recipes, per-recipe seconds) are JSON
files under `FRAME_COMPARE_E2E_ARTIFACTS`; see
`tests/integration/NOTES-u4-media-preparation.md`
for measured cold/focused and full-matrix costs.
Run the verifier one at a time from a checkout: overlapping pruning is unsupported.
No CI cache was added; Docker CI retains `--no-cache` and cold regeneration receives
no warm-cache speedup.

If this path cannot be run locally, record it as documented-only until an observed
matching-SHA run of `.github/workflows/docker-integration.yml` supplies the proof.
On pull requests to any base branch, the job runs when changes
touch `src/**`, `tests/**`, the project lock/config files, Docker files, verifier
scripts, or the workflow itself.
Obtain an authorized manual run when required; an absent or skipped CI job is not
successful proof.

`src/frame_compare/vsview/**` also owns an external plugin/process/UI boundary.
Pure metadata/result validation uses focused Python proof and the applicable full
gate. Changes to plugin discovery, launch/lifetime, Qt callbacks, or generated native
sessions require integration proof on the affected platform. Follow the
[native Linux installation](getting-started/native.md#install-with-uv) with
`--extra vsview` or the [Windows portable procedure](#windows-portable-release-path-verification).
Use the [alignment review guide](guides/vsview-review.md) for the visible desktop
journey. Offscreen checks establish the Python, Qt, and plugin behavior they
exercise. Native media proof requires the L-SMASH-Works decoder (`core.lsmas`).

For a coordinated media-runtime change, the gate additionally owns immutable
source/wheel hashes and byte sizes, native SONAME/symlink preservation,
`manifest.vs` layout, source-index creation, generated SDR/HDR fixture coverage
where codecs are available, software-Vulkan initialization, vs-placebo filter
execution, runtime fingerprint agreement, and absence of build tooling from the
runtime stage. Do not replace Debian FFmpeg with a custom build without an
explicit security, ABI, licensing, image-size, and multiarchitecture decision.

Current capability contract:

| Environment | Supported runtime |
| --- | --- |
| macOS Docker Desktop and Linux Docker | Headless rendering, reports, and software-Vulkan tonemapping |
| Native Linux with `--extra vsview` | Desktop alignment review |
| Native Windows portable | Native rendering, desktop alignment review, and the Windows release path |

### Alignment Accuracy Benchmark

`tools/alignment_benchmark.py` runs every pair in a maintainer-supplied label
file through the production alignment path (result cache disabled, per-pair
diagnostics) and classifies each pair as `correct_applied`, `wrong_applied`,
`provisional`, `unavailable`, or `correctly_withheld` for pairs that must never
apply. Before measuring, it verifies that the prepared clip order resolves to the
labelled reference/comparison paths. Aborted or operationally failed attempts are
`unavailable`; completed no-signal and inconclusive negative controls remain
`correctly_withheld`. It prints a sanitized summary (pair ids and categories only)
and writes the full per-pair JSON plus diagnostics to the output directory. Run it
in the Docker test service:

```bash
mkdir -p /tmp/u5-real-media
docker compose run --rm \
  --volume "$PWD/comparison_videos:/media:ro" \
  --volume "/tmp/u5-real-media:/proof" \
  frame-compare-test -lc \
  'python tools/alignment_benchmark.py --labels /media/alignment_labels.json --output /proof'
```

Label schema (media paths are relative to the label file's directory):

```json
{
  "pairs": [
    {"id": "pair-1", "category": "development", "reference": "A.mkv",
     "comparison": "B.mkv", "expected_frame": 0, "expected_automatic": "applied"},
    {"id": "control-1", "category": "negative_control", "reference": "C.mkv",
     "comparison": "D.mkv", "expected_frame": null,
     "expected_automatic": "not_applied"}
  ]
}
```

`speed_change` pairs run with the comparison's effective FPS set to the
reference's probed FPS, matching `sources.match_fps = "assume_reference"`.

### Windows Portable / Release-Path Verification

Required when changing:

- `.github/workflows/release.yml`
- `.github/workflows/rc.yml`
- `.github/workflows/release-please.yml`
- `.github/workflows/windows-portable.yml`
- `.github/actions/windows-portable-build/action.yml`
- anything under `tools/windows_portable/**`
- installer/update commands or release asset layout in docs
- bundle manifests or scan policy

Source builds and source install entrypoints require PowerShell 7 or newer before
bootstrap, Python 3.13 provisioning, or output changes. Published-bundle
installation and launch retain Windows PowerShell 5.1 support; exercise
BOM-less UTF-8 install state from a non-ASCII bundle path under that interpreter.
Windows portable pytest fixtures clear inherited `PSModulePath` for each test so
Python-launched PS5.1 and PS7 initialize their own compatible module paths. The
fixture restores the parent process environment after each test.

For source-install changes, run `tests/windows_portable` on Windows with PowerShell
7. Verify the default path provisions Python 3.13 before the builder and that
`-SkipPythonInstall` (plus the legacy `-SkipSync` alias) still requires an existing
discoverable Python 3.13. Manually rerun source installation with populated
config/media/generated sentinels using both default Move and `-UserData Leave`, and
inject a manifest failure. Verify old runtime/code and the previous pointer survive failures, moved
folders reverse on failed activation before and after pointer replacement, and the
shim launches the new bundle after success. Old bundles must remain for manual
removal. Source targets use a UTC timestamp; direct maintainer/CI builds retain the
same final path to preserve the requirements-lock fingerprint. Static tests and
non-Windows skips do not establish these filesystem observations.
The installer re-reads a single pointer byte snapshot after the build under the
exclusive `state/source-install.lock` handle. Source migration, bundle activation,
and source rollback retain that handle; a direct current-bundle installer acquires
it itself. Verify overlapping activation refuses before shim/pointer/data changes,
then succeeds after the handle closes (the lock file intentionally remains).
Also cover pointer changes at the build boundary, locked-pointer recovery diagnostics,
byte-exact pointer and shim restoration, malformed drive/root-relative pointers,
and junction aliases into previous user data, cache, or protected build roots.
Reparse ancestry is refused rather than inferring physical containment from a
lexical path. Cross-volume user-data renames still fail at the rename operation.

Canonical verification path:

1. Validate the runtime manifest and captured source identity.
2. Download every artifact with exact byte-size and SHA-256 verification.
3. The builder refuses occupied or unsafe output paths. Remove disposable candidate
   output explicitly before rebuilding; never remove a populated installed bundle.
   Build twice at the same final path (removing only the disposable first build)
   and compare `bundle_info.requirements_lock_sha256`; it must remain identical.
   Build the portable bundle and validate its deterministic ZIP layout, native
   plugin manifests, license inventory, source provenance, and runtime fingerprint.
4. Run the extracted bundle's `--help`, `version`, and `doctor --json` smoke checks;
   verify R82/API R4.3, L-SMASH-Works 1310, vs-placebo 2.0.5, VSView 0.14.0,
   PySide6 6.12.0, BestSource, vspackrgb, and the selected LGPL-only
   FFmpeg artifact. FFMS2 must remain absent from the Windows baseline. In one
   required bundled Python process, preload the managed VapourSynth runtime before
   importing PySide6 or VSView, then recheck the plugin environment, open the generated
   media through L-SMASH, and invoke the application tonemap path.
   `tools/windows_portable/portable_bundle.py` projects the exact commit's
   `src/frame_compare` into `app/src` and generates one
   `frame_compare-*.dist-info` directory in `app/site-packages` from the
   committed `pyproject.toml` and `LICENSE`. It checks the version against the packaged
   source and requires the exact `frame-compare-alignment-review` entry point.
   The bundled Python proof must discover and load that entry point, construct
   the panel offscreen, round-trip the generated
   metadata/result sidecar, and reject a malformed result. BestSource is VSView/UI-only
   and does not replace Frame Compare's generated-session source loader.
   The repository-owned `tools/windows_portable/runtime_smoke.py` supplies this
   bundled Python proof. The builder copies it to temporary `runtime-smoke.py`,
   runs every required phase with the bundled interpreter and environment, and
   removes it in the existing cleanup. Source provenance includes the Python file;
   lint, syntax, and source equivalence do not establish Windows bundle acceptance.
   Run the direct vs-placebo frame proof after Qt when Vulkan is usable. A
   reported `vulkan_runtime_unavailable` means this capability remains unproved.
   Before accepting a candidate with that hosted gap, the release maintainer
   records a candidate-specific capability waiver and the separate successful
   physical Windows GPU proof. See
   [acceptance records](#release-acceptance-records).
5. Pack the built tree with `tools/windows_portable/portable_bundle.py pack`.
   Run the packed ZIP succession test with `FRAME_COMPARE_TEST_PORTABLE_ZIP`
   set to the exact ZIP. Require all eight cases and zero skips, and record
   Windows PowerShell 5.1 and PowerShell 7 versions. Keep the actual installed
   shim, user-data movement and reactivation, external data, legacy leaf cleanup,
   and uninstall evidence. Upload the original raw ZIP after the post-pack proof.
6. Run the downstream [final-artifact scan](#final-artifact-security-evidence).
   Confirm the immutable producer artifact ID, source commit and SHA-256.
7. Complete [pre-merge physical Windows validation](media-runtime-windows-validation.md#1-exact-source-and-repository-gates)
   for a coordinated runtime change. For promotion, use the
   [published RC acceptance procedure](media-runtime-windows-validation.md#published-rc-acceptance).
   Both routes require real runtime, HDR, and native-panel proof.

The [Windows portable workflow](../.github/workflows/windows-portable.yml) runs
the Windows build and Linux scan on all pull requests. Release workflows call
the same jobs with their planned SHA and `release_build: true`.

#### Portable runtime input authority

Use the candidate's committed `uv.lock` and Windows runtime manifest with the
workflow's pinned Windows host Python 3.13.17 and uv 0.13.8. Review changed archive pins,
native provenance, Qt WebEngine exclusions and notices at the candidate commit.
The assembler authenticates the exact Windows Python dependencies against the
frozen lock and stages them in a local wheelhouse. It converts the authenticated
`anitopy` 2.1.1 source archive into a deterministic wheel from an explicit
allowlist of package files and metadata. Pinned uv installs the exact wheels
offline by version and hash with index access, dependency resolution and builds
disabled. Native archives use manifest size and SHA-256 pins. The assembled tree
retains the approved Qt/PySide6 subset, native components, licenses and committed
project metadata and entry points.

Use GitHub-hosted Windows to verify packaging and generated-fixture behavior. Complete
[physical Windows acceptance on the published RC](media-runtime-windows-validation.md#published-rc-acceptance). Record real GPU Vulkan initialization, HDR10/Dolby Vision
output, range and bit-depth preservation, real-media timing and frame properties,
managed-index isolation and reuse, ZIP installation, and objective and perceptual
comparison evidence.

#### Release acceptance records

The maintainer records the candidate SHA, exact artifact digests, owner and result
for each gate below before approving a public release. A skipped, missing or
unreachable proof leaves the corresponding gate open.

- Verify the exact commit, raw Windows ZIP, scanner evidence and matching
  `.zip.sha256`. Record the Windows smoke and both installer interpreters.
- Retain physical Windows acceptance tied to the candidate bundle SHA-256.
  If hosted direct Vulkan proof reports `vulkan_runtime_unavailable`, document
  the exact capability, candidate SHA, observed reason, accountable release
  maintainer, expiry in UTC, and a link to the successful substitute physical
  proof. A waiver expires at the earlier of its stated date or any candidate
  change. CI capability preflights otherwise fail closed. An unexplained skip
  has no waiver.
- Verify the shipped Qt/PySide6 subset, including WebEngine exclusion and the
  source and build configuration of Qt Multimedia's FFmpeg libraries. Retain
  matching third-party notices, license texts and a distributor-controlled
  corresponding-source offer for the exact shipped binaries. Resolve native
  provenance and license coverage for both Windows and Docker with the
  release maintainer and legal reviewer before public distribution.
- Retain the [final-artifact SBOM and advisory evidence](#final-artifact-security-evidence)
  for each distributable runtime.

#### Final-artifact security evidence

The Windows workflow scans the raw portable ZIP from the build by immutable
artifact ID and independently checks its producer SHA-256 before extraction.
It retains Syft JSON, CycloneDX JSON, unsuppressed Grype JSON, database status,
scanner versions, artifact binding and the policy receipt for 90 days. The
release maintainer reviews native-component coverage and archives the evidence.
A distributed Docker image requires equivalent external evidence tied to its
immutable image digest. The locked Python source audit is a separate check.

Use [Syft](https://oss.anchore.com/docs/guides/sbom/) for inventories and
[Grype](https://oss.anchore.com/docs/guides/vulnerability/scan-targets/) for
advisory matching. The candidate scanner pins for the Linux x64 scan are:

| Verified release archive | SHA-256 |
| --- | --- |
| [Syft 1.57.1 Linux x64](https://github.com/anchore/syft/releases/tag/v1.57.1) | `bf52519eb57f675d47c07d43213cb6dff6449f3d6d1147ff6701ed91f44eef0c` |
| [Grype 0.121.3 Linux x64](https://github.com/anchore/grype/releases/tag/v0.121.3) | `e9da18cc1429e786722e32161288103600efffd8e483c90761f90485bd1bec85` |

Verify archive hashes before extracting tools. For Windows, consume the original
portable ZIP by immutable artifact ID and SHA-256. Use the portable
archive safety policy for extraction into an empty isolated directory and
inventory that tree with Syft's directory source. Never execute files from the
bundle. For Docker, consume each distributable platform image by its immutable
OCI digest. If only a local image exists, export it and bind both its exact image
ID and the export SHA-256 to the evidence. Scan the runtime image's installed contents.

Retain CycloneDX JSON and the native Syft JSON from a single inventory. Require
nonempty inventories and check the scanner name and version in the Syft and
Grype reports. Run Grype against the Syft JSON with a required update check, age
and hash validation, and a valid database no older than five days. The gate
requires the database source checksum and hashes a nonempty local database file
up to 8 GiB. Retain the receipt with the tool versions, database identity, exact
commit, artifact ID and digest, evidence hashes,
counts and policy result. Reconcile coverage against the bundle
inventory and native runtime pins for Windows, and against the native provenance
records for Docker.
Manually account for packages or files a scanner cannot identify, including
embedded Python, Qt Multimedia FFmpeg, standalone FFmpeg, VapourSynth and native
decoder/plugin libraries. Record the exact version or commit, license, source and
advisory coverage for each missing native component using upstream advisories.
An empty inventory, scanner error, invalid or stale database, or unresolved
component coverage blocks acceptance.

The automated gate refuses suppressions, high, critical or unknown severity
(including unfixed findings), and any known exploited vulnerability (KEV)
match. It applies those rules to primary and related vulnerabilities. Keep the
unsuppressed machine-readable result and record lower-severity findings for
review. A waiver for a finding eligible for manual acceptance must match the
advisory ID, component identifier and version, target profile and artifact
digest. Record the release maintainer and independent approver, rationale,
compensating controls, UTC expiry and removal condition. The automated gate
must pass independently of manual waivers.

Keep scanner reports and policy receipts in CI for 90 days. Archive the
SBOMs, scan receipts, native coverage notes and waiver decisions with the
release evidence for the life of the supported release line. Record tool and
database identifiers so later reassessments can distinguish changes in the
artifact from changes in the advisory feed.

### Pre-release and stable publication

#### Release candidate

1. Before merging the active version branch (`vX.Y.Z`) into `pre-release`, complete
   the third-party notice, license text, and distributor-controlled corresponding-source
   requirements in the [release acceptance records](#release-acceptance-records).
   The maintainer then merges the branch with a merge commit using an identity
   that triggers push workflows.
   Merges made with `GITHUB_TOKEN` do not trigger the RC workflow.
2. On the push, the RC workflow reads the live `pre-release` head. If its stable
   version is already published, the run waits for the next version. Otherwise the
   head must include `main` in its ancestry. Merge `main` through the integration
   branch if that check fails. A complete RC for this commit already satisfies
   publication. A published but incomplete RC requires manual repair.
3. For a new candidate, the workflow chooses the next numeric `vX.Y.Z-rc.N` tag.
   The source audit and Windows workflow use the planned commit SHA. The publisher
   verifies the scanned ZIP by artifact ID and digest, creates a draft at that SHA,
   and verifies the uploaded files before publishing it as a GitHub pre-release.
4. Download `frame-compare-portable-win-x64-vX.Y.Z-rc.N.zip` and its matching
   `.zip.sha256` file. Run `sha256sum --check <zip-name>.sha256` beside the ZIP.
   The tag, ZIP name, and `bundle_inventory.json` field `bundle.commit_sha`
   identify the candidate. Inside the ZIP, `frame-compare version` prints
   `frame-compare X.Y.Z`.
5. Review the [acceptance records](#release-acceptance-records) and test the
   issued ZIP using [Published RC acceptance](media-runtime-windows-validation.md#published-rc-acceptance).
   Pause merges into `pre-release` during acceptance. If its head advances,
   accept the new candidate before promotion. If `main` advances, merge it
   through the integration branch and test the resulting candidate.

#### Stable promotion

1. After accepting the RC, open a PR from `pre-release` to `main` and merge it
   with a merge commit. Keep the accepted source tree intact.
2. On the push, the stable workflow reads the live `main` head. Before a new
   publication, it requires a complete published RC of the same version with
   a tree identical to that head. If the tree differs, return to RC acceptance.
3. The workflow audits the planned `main` commit, builds and scans its stable
   ZIP, and publishes `vX.Y.Z` as a full release. Verify the two assets
   (`frame-compare-portable-win-x64-vX.Y.Z.zip` and its `.zip.sha256`) and the
   release notes. Both channels extract the matching `CHANGELOG.md` section.
   The version must agree across the Release Please manifest, `pyproject.toml`,
   package `__version__`, and editable entry in `uv.lock`.
4. Check that the stable workflow moves the merged Release Please PR from
   `autorelease: pending` to `autorelease: tagged`. An already tagged PR
   satisfies this check.

Use **Re-run all jobs** on the applicable push run after a failure. This reruns the
plan against the live head. Rerunning only failed jobs can reuse an earlier
planned SHA. Each publication path clears its stale drafts before trying again
and verifies its new draft before publishing. A published release with missing
or mismatched assets requires manual repair. A stable rerun that finds a
complete release can still repair the Release Please label.

#### Start the next release cycle

1. Resolve the published stable tag via `refs/tags/vX.Y.Z` and start the next
   version branch at its exact commit. Merge that branch into `pre-release`
   with a merge commit before the next preparation cycle. This brings the
   stable commit into `pre-release` history while preserving the promotion's
   ancestry.
2. Release Please observes pushes to `pre-release` and prepares version and
   changelog PRs there. Its guard waits for a published stable release of the
   manifest version and for the stable tag's commit to be in the branch history.
   A missing release is treated as absent on HTTP 404. Other lookup errors fail
   the run. The Release Please action leaves publication to the release workflows.
3. Review the preparation PR for agreement across the manifest, `pyproject.toml`,
   package `__version__`, and editable lock entry. Check for one matching
   `## [X.Y.Z]` changelog section. Merge using an identity that triggers push
   workflows so the new version can produce an RC. Verify the stable label after
   promotion.

#### First 0.7.0 cutover checklist

1. Squash the G5 PR into `v0.7.0` using `--match-head-commit` with the reviewed
   PR head SHA. The integration branch has no required checks.
2. Fetch `main` and confirm that `refs/remotes/origin/main` still points to
   the reviewed `ba2d6c45` (`chore(release): 0.6.1`). If it has moved, review
   the intervening changes before proceeding. With maintainer approval, merge
   the reviewed SHA into `v0.7.0` using `git merge -s ours ba2d6c45`. Before
   pushing, verify the old integration head and the reviewed `main` commit
   are the first and second parents. Check that `HEAD^{tree}` equals
   `HEAD^1^{tree}` and that `origin/main` is an ancestor. The integration tree
   includes the prepared 0.6.1 changelog organization. Use qualified refs for
   lookups and exact SHAs for checkouts and tag targets since `v0.7.0` names both
   the integration branch and the planned stable tag.
3. After the G5 PR reports the new checks, configure the repository before the
   first integration merge.

   - Enable merge commits and keep squash merges available for feature PRs.
   - Remove linear-history requirements on `main` and `pre-release` so both
     can accept merge commits. Keep both branches protected against direct
     unauthorized writes, force pushes, and deletion. Keep `pre-release`
     protected from automatic deletion after promotion.
   - Replace required checks for the old unsigned verifier, signer, and
     wrappers with `CI Pass` and the Windows portable jobs `build_test` and
     `artifact_security` (displayed as **Inventory and scan portable ZIP**).
     Use the contexts reported by the G5 PR. Leave path-filtered Docker and
     docs jobs outside the universal required checks.
   - Confirm the release workflows can create `v*` tags and that
     `RELEASE_PLEASE_TOKEN` is configured.
4. Before merging, complete the third-party notice, license text, and
   distributor-controlled corresponding-source requirements in the
   [release acceptance records](#release-acceptance-records).
   Check for existing `v0.7.0-rc.*` tags. Merge `v0.7.0` into `pre-release`
   with a maintainer-created merge commit and expect `v0.7.0-rc.1` when there are
   no prior tags. Check the two assets and verify the downloaded ZIP with
   `sha256sum --check`. Follow [Published RC acceptance](media-runtime-windows-validation.md#published-rc-acceptance).
   Run the issued ZIP's `install.cmd` over an active v0.6.1 test installation
   and check comparisons, run history, and config after carry-over. Follow the RC acceptance freeze and repeat testing
   if the accepted candidate changes.
5. Promote `pre-release` into `main` with a merge commit. Check that `v0.7.0`
   is published with two assets and the 0.7.0 notes. The label job accepts
   the absence of a Release Please PR for this manually prepared version.
6. After promotion, Dependabot reads the default branch configuration that
   targets `pre-release`. Retarget or close open PRs against `staging` and review
   any staging-only commits before deleting that branch and its rules. Check
   for other consumers before removing the old environment rules for
   `release-candidate`, `production`, and `branch-maintenance`, the
   `WINDOWS_UPDATE_SIGNING_KEY_XML` and `SIGNING_KEY_MIGRATION_TOKEN` secrets,
   the `BRANCH_MAINTENANCE_CLIENT_ID` variable, the
   `BRANCH_MAINTENANCE_PRIVATE_KEY` secret, and the branch-maintenance App
   bypass. Keep historical release and archive tags.
7. Start the next cycle at the commit of `refs/tags/v0.7.0` and merge the new
   integration branch into `pre-release`. Check the first Release Please PR
   and its eventual stable label as described above.

Local workflow checks:

```bash
uv run --no-sync pytest -q tests/workflows/test_release_contract.py tests/workflows/test_github_workflows.py tests/windows_portable/test_windows_portable_workflow.py
```

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

`design-code` owns planning method. Keep task plans inline or in untracked
local notes. The tracked docs tree holds no plan or review records; git
history keeps the earlier ones.

## Documentation Freshness Triggers

Update `docs/current-architecture.md` when a scoped change alters composition,
runtime ordering, ownership, persistence, or external integration boundaries.
Update `docs/current-cli-contract.md` when its documented product behavior changes.

Update `.agents/project.md` for changed local facts, common command routes, or
test-policy decisions. Update this runbook for changed specialist procedures,
verification requirements, or release authorization. Update the corresponding
host or review-tool adapter when its discovery semantics change.
Shared methodology belongs in the shared skills, not another repository copy.

Correct stale active references in the same change.
