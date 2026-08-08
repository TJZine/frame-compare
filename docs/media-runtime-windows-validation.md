# Physical Windows Media Runtime Validation

This checklist is the final pre-merge acceptance pass for a coordinated media-runtime
refresh. It supplements GitHub-hosted Linux, Docker, and Windows packaging checks; it
does not duplicate them. Run it on the supported physical Windows 10/11 x64 system
with the intended production GPU and private real-media corpus.

Do not merge the media-runtime pull request until every required item is recorded as
passed, failed with an accepted explanation, or explicitly deferred by the maintainer.
Keep raw command output, JSON diagnostics, hashes, screenshots, and comparison notes
with the pull-request evidence.

## Test-system record

Record these facts before changing the machine or installing the candidate bundle:

- Windows edition, version, and OS build.
- CPU, installed memory, and free disk space on the build and generated-data volumes.
- GPU model, driver package/version/date, and Vulkan runtime/loader version.
- PowerShell version and execution policy.
- Git version.
- Checked-out pull-request branch and exact 40-character commit SHA.
- Python and `uv` versions used for repository validation.
- Previous portable bundle version/runtime fingerprint used for migration testing.
- Real-media case identifiers without publishing private filenames when inappropriate.

The expected candidate profile is:

| Component | Expected Windows identity |
| --- | --- |
| Python | 3.13.14 |
| VapourSynth | R78, API 4 |
| L-SMASH-Works | `vapoursynth-lsmas` 1296.0.0.1 / native lineage 1296.0.0.0 |
| FFMS2 | Absent from the Windows baseline |
| vs-placebo | 2.0.4 |
| FFmpeg | `n8.1.2-34-g9b6c8969e0`, BtbN win64 LGPL 8.1 build |
| Full runtime fingerprint | `35d58736c651f4d8e52bd4d8e6750ebede4c4bc9676e4c9db7dfebaeadab018c` |
| L-SMASH index token | `lsw1296-e3c074652ffb` |

## 1. Exact source and repository gates

From a clean clone or worktree, fetch the pull request and verify that `HEAD` is the
exact SHA recorded in the pull request. Do not test an older cached checkout.

```powershell
git fetch --all --prune
git switch deps/media-runtime-refresh
git pull --ff-only
$WorkingTree = git status --porcelain
if ($WorkingTree) {
  throw 'Validation requires a clean worktree.'
}
$ExpectedPrHeadSha = '<recorded 40-character PR head SHA>'
if ($ExpectedPrHeadSha -notmatch '^[a-f0-9]{40}$') {
  throw 'Expected PR head must be a complete lowercase 40-character SHA.'
}
$ActualHeadSha = (git rev-parse HEAD).Trim()
$RemoteHeadSha = (git ls-remote origin refs/heads/deps/media-runtime-refresh).Split("`t")[0]
if ($ActualHeadSha -ne $ExpectedPrHeadSha -or $RemoteHeadSha -ne $ExpectedPrHeadSha) {
  throw "Candidate moved: expected=$ExpectedPrHeadSha local=$ActualHeadSha remote=$RemoteHeadSha"
}
```

`git status --short` must be empty. Then run the repository-standard validation using
the repository-pinned Python and `uv` versions:

```powershell
uv lock --check
uv sync --all-groups --frozen
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pyright --warnings
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync lint-imports
uv run --no-sync pytest
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
uv build
```

Record every command, exit code, and any skip reason. Do not weaken an assertion only
to make the candidate green.

For every failed, deferred, skipped, or unavailable item, record the owner, reason,
supporting command/log/artifact evidence, why it is non-blocking where applicable,
and the concrete event that requires revisiting or removing the exception.

## 2. Build the full portable bundle

Remove old candidate output while retaining a separate previous-release installation
for migration testing. Build into a fresh directory:

```powershell
$Repo = (Resolve-Path .).Path
$Candidate = Join-Path $Repo 'dist\frame-compare-portable-win-x64'
$Cache = Join-Path $Repo '.portable_cache'

Remove-Item -LiteralPath $Candidate -Recurse -Force -ErrorAction SilentlyContinue
pwsh -NoProfile -ExecutionPolicy Bypass -File `
  tools\windows_portable\build_portable.ps1 `
  -RepoRoot $Repo `
  -OutDir $Candidate `
  -CacheDir $Cache
```

Required evidence:

- Every download passes exact byte-size and SHA-256 verification.
- No artifact is accepted from a mutable fallback URL.
- The bundle contains `bundle_info.json`, `bundle_inventory.json`,
  `licenses/SOURCE_URLS.txt`, and `licenses/THIRD_PARTY_NOTICES.txt`.
- The recorded source SHA equals the tested pull-request SHA.
- The bundle runtime fingerprint equals the expected value above.
- FFmpeg is the LGPL-only artifact; no GPL or nonfree build is present.
- FFMS2 is not present in the Windows bundle or plugin manifests.
- L-SMASH-Works and vs-placebo license/source records include their statically bundled
  dependency notices.
- Native plugins do not depend on unbundled DLLs outside the documented Windows/UCRT
  system surface.

Build the portable bundle with the canonical command used by the GitHub-hosted workflow:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir dist/frame-compare-portable-win-x64 -CacheDir .portable_cache
```

For a release run, also pass `-RequireReleasePublicKey`. Package
`dist/frame-compare-portable-win-x64` as
`dist/frame-compare-portable-win-x64.zip`, record its SHA-256, verify that digest, and
verify the ZIP layout before extraction.

## 3. Extracted-bundle smoke tests

Extract the candidate ZIP into a new path that is not the repository checkout and is
not the previous installation. Run commands through the bundle's own shim/runtime,
not a globally installed Frame Compare environment.

```powershell
$ExtractedBundle = (Resolve-Path '.\frame-compare-portable-win-x64').Path
$CandidateLauncher = Join-Path $ExtractedBundle 'frame-compare.ps1'
Get-Command -CommandType ExternalScript $CandidateLauncher | Format-List Source,Path
& $CandidateLauncher --help
& $CandidateLauncher version
$DoctorStdout = '.\doctor-candidate.json'
$DoctorStderr = '.\doctor-candidate.stderr.log'
& $CandidateLauncher doctor --json 1> $DoctorStdout 2> $DoctorStderr
if ($LASTEXITCODE -ne 0) {
  throw "Candidate doctor check failed with exit code $LASTEXITCODE. See $DoctorStderr."
}
$DoctorPayload = Get-Content -Raw $DoctorStdout | ConvertFrom-Json -NoEnumerate -ErrorAction Stop
if ($DoctorPayload -isnot [pscustomobject]) {
  throw 'Candidate doctor output must be exactly one JSON object.'
}
```

Inspect `doctor-candidate.json`. Required results:

- The observed and expected media-runtime fingerprints match.
- VapourSynth reports R78 independently from API 4.
- `lsmas` registers both `LibavSMASHSource` and `LWLibavSource`.
- `placebo` registers `Tonemap`.
- FFMS2 is reported as intentionally absent on Windows, not as a missing requirement.
- `ffmpeg` and `ffprobe` resolve inside the bundle and report the selected BtbN build.
- Plugin loading uses deterministic package/extra-plugin paths.
- No plugin DLL is loaded from the standalone FFmpeg directory.
- No missing shared-library or recursive DLL-probing warning appears.

Also run the build script's installed/extracted smoke and ZIP-layout tests exactly as
the hosted Windows workflow does.

## 4. Deterministic generated fixtures

Use the bundled FFmpeg to create small test-scoped fixtures when the required encoder
is available. At minimum cover:

- 8-bit H.264 SDR with explicit BT.709 primaries, transfer, matrix, and limited range.
- 10-bit HEVC with explicit BT.2020/PQ metadata.
- Full-range and limited-range samples.
- Differing frame durations or a small VFR sample.
- Interlaced or repeated-field metadata where the bundled encoder supports it.
- AV1 only when the installed encoder and decoder are both available.

For every generated sample:

- Record the exact FFmpeg command and `ffprobe` JSON.
- Open the source through L-SMASH-Works.
- Check frame count, dimensions, format, frame rate/time base, per-frame duration,
  color primaries, transfer, matrix, range, chroma location, and field properties.
- Render representative frames and confirm that output precision is not silently
  reduced to 8-bit.
- Report unavailable codec coverage rather than treating it as passed.

## 5. Real-media source-loader matrix

Use non-copyright-distributed private cases representative of supported workflows.
Include, where available:

- CFR SDR H.264.
- 10-bit HEVC HDR10.
- Dolby Vision Profile 8 or another supported fallback case.
- VFR or differing-duration frames.
- Interlaced and repeated-field material.
- Non-square sample aspect ratio.
- Explicit limited/full range and unusual chroma-location metadata.
- Alpha-bearing content supported by the selected loader.
- A case using `av_sync` or other source options used by Frame Compare.

Compare the previous supported bundle with the candidate. A changed value is not
automatically a regression: classify it against upstream release notes, FFmpeg/media
specifications, and Frame Compare's contract. Record:

- Exact frame count and requested-frame availability.
- First/last frame behavior and random-seek stability.
- Frame duration/time-base behavior.
- VFR/repeat/interlace properties.
- Aspect-ratio and color-property propagation.
- Audio/video synchronization and selected-stream behavior.
- Any changed output, its failure category, and the acceptance rationale.

## 6. HDR, Dolby Vision, and Vulkan

Run this section on the production GPU and driver. Software-Vulkan Docker success does
not satisfy it.

Required checks:

- Vulkan initializes on the intended GPU without falling back to another adapter.
- A real vs-placebo `Tonemap` invocation completes.
- HDR10 to SDR uses the configured target nits and tone-map function.
- Dynamic peak detection and retry behavior remain functional.
- Dolby Vision metadata/fallback behavior follows the supported Frame Compare path.
- Primaries, transfer, matrix, and limited/full-range conversions are correct.
- The pipeline does not introduce an unintended RGB/YUV conversion.
- Intermediate/output formats preserve the intended 10-bit-or-higher precision.
- Measured output metadata and diagnostics agree with the actual render path.
- Expected Vulkan failures remain actionable and do not expose misleading success.

For representative dark, highlight, saturated-color, skin-tone, and gradient frames,
retain:

- Candidate screenshots.
- Previous-runtime screenshots.
- Objective metrics where useful.
- Difference visualizations.
- Manual perceptual notes at 100% scale on a color-managed display.

Metric equality alone is not sufficient evidence of perceptual equivalence.

## 7. Cache and index migration

Use copies of media so test cleanup cannot damage a production library.

### L-SMASH-Works indexes

Verify all of the following:

- A legacy adjacent `<media>.lwi` is ignored and not deleted.
- The candidate creates
  `<media>.frame-compare-lsw1296-e3c074652ffb.lwi`.
- A second run reuses the candidate-owned index.
- A corrupt candidate-owned index is removed and regenerated once.
- A missing index is created normally.
- An unwritable index location falls back to the documented cache-free open.
- Indexes from another runtime profile are not silently reused.

### Application caches

Verify with old and newly generated data:

- Old analysis cache misses and regenerates when decoder identity differs.
- Probe cache keys include the candidate probe fingerprint.
- Alignment reuse misses when the standalone FFmpeg lineage differs.
- Render/run metadata records the complete candidate runtime contract.
- `--from-cache-only` fails closed when only stale cache data exists.
- `--no-cache` does not read or persist reusable cache data.
- Repeated candidate runs produce valid cache hits without changing selected frames.
- Unrelated cache scopes are not invalidated without a documented reason.

## 8. Portable update boundary

Keep one untouched installation of the previous R76/1282/2.0.2 bundle.

Required cases:

1. Build the candidate code-only update ZIP and its manifest.
2. Attempt to apply it to the previous bundle.
3. Confirm refusal occurs before file replacement because the native-runtime
   fingerprint differs.
4. Confirm an unsafe Python-dependency override does not bypass that refusal.
5. Confirm the error directs the user to install the complete portable bundle.
6. Install/extract the complete candidate bundle and confirm generated data stored
   outside the bundle remains available.
7. Apply a code-only update whose required fingerprint matches the candidate bundle.
8. Verify backup creation, successful apply, rollback, and hash restoration.
9. Test missing, malformed, and legacy runtime-fingerprint metadata; each must fail
   closed without partially updating the installation.

## 9. End-to-end comparisons

Run at least one SDR and one HDR/Dolby Vision comparison using the normal user path.
Where practical, include sources with different encode characteristics and alignment
requirements.

For each run retain:

- `doctor --json` captured immediately before the run.
- Dry-run/diagnostic output.
- `run_info.toml` and `run_result.toml`.
- Source/index/cache metadata.
- Selected-frame/category metadata.
- Representative screenshots and the offline HTML report.
- Any warning or fallback and whether it was expected.

Confirm deterministic repeatability from a clean generated-data directory and from a
warm candidate cache.

## 10. Completion record

Summarize the physical pass in the pull request with:

- Tested commit SHA and bundle ZIP SHA-256.
- Test-system and GPU/driver identity.
- Passed, failed, skipped, and unavailable cases.
- Exact real-media categories exercised.
- Source-loader behavior changes and their classifications.
- Cache/index and updater migration results.
- HDR/Dolby Vision objective and perceptual findings.
- Residual risks or platform-specific limitations.
- Independent final reviewer identity/session, reviewed commit SHA, verdict, and any
  findings or accepted counter-evidence.
- A clear merge recommendation.

Do not mark the pull request ready or merge it while a production-significant failure
is unresolved. Preserve this checklist as the authoritative handoff rather than
reconstructing requirements from chat history.
