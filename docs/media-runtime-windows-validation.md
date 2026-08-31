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
- Pull-request number, fetched pull-request head ref, and detached exact
  40-character commit SHA.
- Python and `uv` versions used for repository validation.
- Previous portable bundle version/runtime fingerprint used for migration testing.
- Real-media case identifiers without publishing private filenames when inappropriate.

The expected candidate profile is:

| Component | Expected Windows identity |
| --- | --- |
| Python | 3.13.15 |
| VapourSynth | R79, API R4.2 |
| L-SMASH-Works | `vapoursynth-lsmas` 1310.0.0.0 / native lineage 1310.0.0.0 |
| FFMS2 | Absent from the Windows baseline |
| vs-placebo | 2.0.4 |
| FFmpeg | `n8.1.2-34-g9b6c8969e0`, BtbN win64 LGPL 8.1 build |
| Full runtime fingerprint | `6b09db7e3f3d388c4b61b2495b325968b336e4c84bc1b846d90afa5a125ee7a1` |
| L-SMASH index token | `lsw1310-56c451f754fd` |

## 1. Exact source and repository gates

From a clean clone or worktree, fetch the pull request and verify that `HEAD` is the
exact SHA recorded in the pull request. Do not test an older cached checkout.

```powershell
$PrNumber = '<pull-request-number>'
$ExpectedPrHeadSha = '<recorded lowercase 40-character PR head SHA>'
if ($PrNumber -notmatch '^[1-9][0-9]*$') {
  throw 'Pull-request number must be a positive integer.'
}
if ($ExpectedPrHeadSha -notmatch '^[a-f0-9]{40}$') {
  throw 'Expected PR head must be a complete lowercase 40-character SHA.'
}

$WorkingTree = git status --porcelain
if ($WorkingTree) {
  throw 'Validation requires a clean worktree.'
}

$PrHeadRef = "refs/pull/$PrNumber/head"
$LocalPrHeadRef = "refs/remotes/origin/pr/$PrNumber/head"
git fetch --no-tags origin "+${PrHeadRef}:${LocalPrHeadRef}"
if ($LASTEXITCODE -ne 0) {
  throw "Failed to fetch pull-request head ref: $PrHeadRef"
}

$ResolvedPrHeadSha = (git rev-parse --verify "${LocalPrHeadRef}^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or $ResolvedPrHeadSha -ne $ExpectedPrHeadSha) {
  throw "Candidate moved: expected=$ExpectedPrHeadSha resolved=$ResolvedPrHeadSha"
}

git switch --detach $ExpectedPrHeadSha
if ($LASTEXITCODE -ne 0) {
  throw "Failed to switch to the recorded pull-request head: $ExpectedPrHeadSha"
}
$ActualHeadSha = (git rev-parse --verify HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $ActualHeadSha -ne $ExpectedPrHeadSha) {
  throw "Detached checkout mismatch: expected=$ExpectedPrHeadSha actual=$ActualHeadSha"
}
```

`git status --short` must be empty. Then run the repository-standard validation using
the repository-pinned Python and `uv` versions:

```powershell
uv lock --check
uv sync --all-groups --extra vsview --frozen
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
$Manifest = Join-Path $Repo 'tools\windows_portable\manifest.windows-x64.json'

Remove-Item -LiteralPath $Candidate -Recurse -Force -ErrorAction SilentlyContinue
pwsh -NoProfile -ExecutionPolicy Bypass -File `
  tools\windows_portable\build_portable.ps1 `
  -ManifestPath $Manifest `
  -RepoRoot $Repo `
  -OutDir $Candidate `
  -CacheDir $Cache
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

This is the canonical manifest-based build command. For a release run, add
`-RequireReleasePublicKey` to this same invocation; do not rebuild a second candidate.
All evidence, packaging, and digest verification must use this exact `$Candidate`.

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

Package `dist/frame-compare-portable-win-x64` as
`dist/frame-compare-portable-win-x64.zip`, record its SHA-256, verify that digest, and
verify the ZIP layout before extraction.

## 3. Extracted-bundle smoke tests

Extract the candidate ZIP into a new path that is not the repository checkout and is
not the previous installation. Run commands through the bundle's own shim/runtime,
not a globally installed Frame Compare environment.

The focused verifier below is also invoked by the hosted workflow's
`Verify extracted portable bundle` step. It owns ZIP containment/layout, extraction,
default workspace directories, candidate launcher and doctor checks, installation,
and installed-shim parity. Every command it reports must exit `0`; a thrown assertion
is a failed check. The verifier atomically reserves the fresh extraction root, writes
without overwrite, and retains extracted evidence after any later failure. Its
expected commit argument must be the recorded detached pull-request head used to build
the candidate. Each external command is assigned to a kill-on-close Windows Job Object
before its gated payload starts. Its stdout and stderr streams are independently copied
to capped evidence files rather than retained in verifier memory. Version stdout is
capped at 64 KiB and doctor JSON at 4 MiB so successful output cannot exceed its reread
limit; every other stdout or stderr evidence file is capped at 16 MiB. Exceeding either
cap preserves that stream's exact capped prefix, immediately terminates the complete
job, reports the overflowing stream and byte limit, and fails without waiting for the
command deadline. Each command also has a five-minute deadline; a timeout terminates
the complete job, fails the verifier, and retains the capped output written so far
under the extraction root's `command-evidence` directory (with doctor output kept at
the exact paths supplied below).

```powershell
$Zip = (Resolve-Path 'dist\frame-compare-portable-win-x64.zip').Path
$ExtractRoot = Join-Path $env:TEMP `
  ("frame-compare-pr{0}-zip-{1}" -f $PrNumber, [guid]::NewGuid().ToString('N'))
$DoctorStdout = Join-Path $ExtractRoot 'doctor-candidate.json'
$DoctorStderr = Join-Path $ExtractRoot 'doctor-candidate.stderr.log'

pwsh -NoProfile -ExecutionPolicy Bypass `
  -File tools\windows_portable\verify_extracted_bundle.ps1 `
  -ZipPath $Zip `
  -ExtractRoot $ExtractRoot `
  -DoctorStdoutPath $DoctorStdout `
  -DoctorStderrPath $DoctorStderr `
  -ExpectedCommitSha $ExpectedPrHeadSha `
  -CommandTimeoutSeconds 300
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Inspect `doctor-candidate.json`. Required results:

- The observed and expected media-runtime fingerprints match.
- VapourSynth reports R79 independently from API R4.2.
- `lsmas` registers both `LibavSMASHSource` and `LWLibavSource`.
- `placebo` registers `Tonemap`.
- FFMS2 is reported as intentionally absent on Windows, not as a missing requirement.
- `ffmpeg` and `ffprobe` resolve inside the bundle and report the selected BtbN build.
- Plugin loading uses deterministic package/extra-plugin paths.
- No plugin DLL is loaded from the standalone FFmpeg directory.
- No missing shared-library or recursive DLL-probing warning appears.

Retain the verifier's `WINDOWS_EXTRACTED_PROOF` lines. Record its resolved candidate
launcher, installed shim, doctor stdout/stderr, ZIP and digest artifact paths, every
reported command exit code, and the hosted `Verify extracted portable bundle` step.

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
  `<media>.frame-compare-lsw1310-56c451f754fd.lwi`.
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

Keep one untouched installation of the immediate predecessor to this 1310 candidate:
the R79 / L-SMASH-Works 1296 bundle with full runtime fingerprint
`59c875f1d2a3eb3df541ed6c7a434eea6ebe40473666920699b698e8738840dd`.

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
