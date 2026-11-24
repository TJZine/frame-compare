# Physical Windows Media Runtime Validation

Run this checklist on a supported physical Windows 10/11 x64 system with the
intended production GPU and private real-media corpus. Keep the results with the
hosted Linux, Docker, and Windows packaging evidence.

- Before merging a coordinated media-runtime change, start at
  [section 1](#1-exact-source-and-repository-gates) and build from the exact pull request head.
  Record the result or maintainer disposition for every required item before merging.
- Before promoting a release candidate, start at
  [Published RC acceptance](#published-rc-acceptance) and use the issued ZIP.

Keep command output, JSON diagnostics, hashes, screenshots, and comparison notes
with the evidence for the route you ran.

## Test-system record

Record these facts before changing the machine or installing the candidate bundle:

- Windows edition, version, and OS build.
- CPU, installed memory, and free disk space on the build and generated-data volumes.
- GPU model, driver package/version/date, and Vulkan runtime/loader version.
- PowerShell version and execution policy.
- Git version.
- For a local build, the pull-request number, fetched head ref, and detached exact
  40-character commit SHA.
- For a published RC, the release URL, tag, and hosted release and Windows job logs.
- Python and `uv` versions used for repository validation.
- Previous portable bundle version/runtime fingerprint used for migration testing.
- Real-media case identifiers without publishing private filenames when inappropriate.

The expected candidate profile is:

| Component | Expected Windows identity |
| --- | --- |
| Python | 3.15.2 embeddable CPython, with the optional SQLite extension and DLL omitted |
| VapourSynth | R82, API R4.3 |
| L-SMASH-Works | `vapoursynth-lsmas` 1310.0.0.0 / native lineage 1310.0.0.0 |
| FFMS2 | Absent from the Windows baseline |
| vs-placebo | 2.0.5 |
| BestSource (VSView/UI only) | 23 |
| VSView / CLI parser | 0.14.0 / Cyclopts 5.4.2 |
| vspackrgb | 2.0.0 (Rust extension) |
| PySide6 family | 6.12.0; WebEngine/PDF distribution metadata 6.12.0.140 |
| Qt Multimedia | Qt's native Windows backend, with the Qt FFmpeg plugin and DLLs excluded |
| Standalone FFmpeg | `n8.1.3-27-g8dca1586f4`, BtbN win64 LGPL 8.1 build `autobuild-2026-10-31-12-59` |
| Full runtime fingerprint | `59b7ca351512938b4da41e5d7b3a06c7c5b37de84c899604c7b8d8b9bba4cd4d` |
| L-SMASH index token | `lsw1310-47d07506e489` |

## Published RC acceptance

1. Open the published RC on [GitHub Releases](https://github.com/TJZine/frame-compare/releases).
   Confirm it is a pre-release with the tag `vX.Y.Z-rc.N`. Download both assets
   from that release into the same directory. Expect exactly
   `frame-compare-portable-win-x64-<tag>.zip` and the corresponding `.zip.sha256`.
2. Verify the sidecar and ZIP before extraction. From the download directory,
   substitute the actual RC tag in the following commands.

   ```powershell
   $Tag = '<published RC tag>'
   $ZipName = "frame-compare-portable-win-x64-$Tag.zip"
   $Zip = (Resolve-Path -LiteralPath $ZipName -ErrorAction Stop).Path
   $ZipDigest = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
   $Sidecar = (Get-Content -LiteralPath "$Zip.sha256" -Raw -Encoding ASCII -ErrorAction Stop).TrimEnd([char[]]"`r`n")
   if ($Sidecar -cne "$ZipDigest  $ZipName") {
     throw 'The published ZIP does not match its SHA-256 sidecar.'
   }
   $ZipDigest
   ```

   Record the full ZIP SHA-256. In the Windows scan evidence for this RC, check that
   `portable_sha256` matches it and record the producer artifact ID.
3. Use a clean repository checkout. Fetch the fully qualified RC tag from the
   release repository and peel it to its commit. Check that the commit matches
   the exact Windows build checkout SHA and the scan evidence's `commit` field.

   ```powershell
   $TagRef = "refs/tags/$Tag"
   git fetch --no-tags origin $TagRef
   if ($LASTEXITCODE -ne 0) { throw "Failed to fetch $TagRef." }
   $ExpectedBundleCommit = git rev-parse --verify 'FETCH_HEAD^{commit}'
   if ($LASTEXITCODE -ne 0) { throw "Failed to resolve $TagRef to a commit." }
   $ExpectedBundleCommit
   ```

   Record the tag and commit with the hosted build, smoke, packed installer, and
   scan results. Use this exact commit for the focused repository tests in
   [section 7](#7-cache-and-index-isolation). Detach at `$ExpectedBundleCommit`
   and sync the frozen contributor environment before running those tests.
4. Start at [section 3](#3-extracted-bundle-smoke-tests) with the downloaded `$Zip`.
   Check `bundle_inventory.json` against `$ExpectedBundleCommit` before running any
   bundle code. Use the verified ZIP throughout sections 3–11, including the
   previous-release installation, production GPU and HDR tests, and native VSView
   panel checks.

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
bash tools/check_python_security.sh
uv run --no-sync lint-imports
uv run --no-sync pytest
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
  -ExpectedCommitSha $ExpectedPrHeadSha `
  -OutDir $Candidate `
  -CacheDir $Cache
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

This is the canonical manifest-based build command. The builder uses the supplied
commit for the projected application source, dependency lock and source inventory.
A local invocation without `-ExpectedCommitSha` resolves `HEAD` once at the start.
To exercise the release build rules locally, add `-ReleaseBuild` to this invocation.
Tie local evidence, packaging, and digest verification to this exact `$Candidate`.

Required evidence:

- Every download passes exact byte-size and SHA-256 verification.
- Every destination declared through `license.files` has the manifest-pinned
  SHA-256 in the bundle inventory.
- No artifact is accepted from a mutable fallback URL.
- The bundle contains `bundle_info.json`, `bundle_inventory.json`,
  `licenses/SOURCE_URLS.txt`, and `licenses/THIRD_PARTY_NOTICES.txt`.
- `bundle_info.schema_version` is 3, identifying a native-panel-capable full bundle;
  this schema identifies the layout used by the runtime and installer.
- The recorded source SHA equals the tested pull-request SHA.
- The direct libplacebo frame proof reports a separate result before and after
  Qt initialization. The hosted skip is reserved for Windows exit code
  `3221225477` with `VK_ERROR_INCOMPATIBLE_DRIVER` or `Failed creating instance`
  in stderr. Other probe failures fail the build. Record a successful direct
  frame on the physical Windows GPU.
- The bundle runtime fingerprint equals the expected value above.
- FFmpeg is the LGPL-only artifact; no GPL or nonfree build is present.
- FFMS2 is not present in the Windows bundle or plugin manifests.
- PySide6 Addons and Qt Multimedia remain present, while Qt WebEngine/Chromium runtime
  files are absent. Record the build runtime proof and verify the absence in the ZIP.
- Record the `WINDOWS_BUNDLE_PROOF qt_multimedia_backend=windows` line, including
  the audio-device status and output count. The smoke verifies that Qt loaded the
  bundled Windows media plugin and constructs a stereo 48 kHz Int16 audio sink
  when a default output exists. A hosted runner can report `audio_device=none`.
  Verify the Qt FFmpeg plugin and all five Qt FFmpeg DLLs are absent from the ZIP.
  The standalone BtbN FFmpeg executable is unchanged.
- L-SMASH-Works and vs-placebo license/source records include their statically bundled
  dependency notices.
- Native plugins do not depend on unbundled DLLs outside the documented Windows/UCRT
  system surface.

Pack the tested build with the same host Python 3.13 lookup as the builder. Use a
fresh ZIP path on each run and record its SHA-256 before extraction.

```powershell
$ExpectedBundleCommit = $ExpectedPrHeadSha
$HostPython = (& uv python find --system --no-project --no-python-downloads 3.13).Trim()
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$Zip = "$Candidate-$([guid]::NewGuid()).zip"
& $HostPython -B -I -S tools/windows_portable/portable_bundle.py pack --root $Candidate --output $Zip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Get-FileHash -LiteralPath $Zip -Algorithm SHA256
```

## 3. Extracted-bundle smoke tests

Extract the checked ZIP into a fresh directory outside the repository and the
previous installation. Check that it contains one portable root. From that root,
verify that the inventory records the source commit for this route.

```powershell
$Inventory = Get-Content -LiteralPath '.\bundle_inventory.json' -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
if ($Inventory.bundle.commit_sha -cne $ExpectedBundleCommit) {
  throw 'The bundle source commit does not match the expected commit.'
}
```

Verify the manifest-pinned notices in the extracted bundle against the inventory.
From the extracted root, run:

```powershell
.\python\python.exe -c "import importlib.util, sys; assert sys.version_info[:3] == (3, 15, 2) and sys.version_info.releaselevel == 'final'; assert importlib.util.find_spec('_sqlite3') is None; print(sys.version)"
.\frame-compare.ps1 --help
.\frame-compare.ps1 version
.\frame-compare.ps1 doctor --json 1> doctor-candidate.json 2> doctor-candidate.stderr.log
```

Confirm that the extracted `python/` directory contains neither `_sqlite3.pyd` nor
`sqlite3.dll`. Require exit 0 from each command and the exact `frame-compare X.Y.Z` version from
the candidate. Complete the [ZIP installation check](#8-zip-installation-over-the-previous-release)
before running checks that use the installed shim. Use the bundled Python and
VSView for the native-panel check in section 10.

Inspect `doctor-candidate.json`. Required results:

- The observed and expected media-runtime fingerprints match.
- VapourSynth reports R82 independently from API R4.3.
- `lsmas` registers both `LibavSMASHSource` and `LWLibavSource`.
- `placebo` registers `Tonemap`.
- FFMS2 is reported as intentionally absent on Windows, not as a missing requirement.
- `ffmpeg` and `ffprobe` resolve inside the bundle and report the selected BtbN build.
- Plugin loading uses only the deterministic canonical package plugin path.
- No plugin DLL is loaded from the standalone FFmpeg directory.
- No missing shared-library or recursive DLL-probing warning appears.

Record the ZIP digest, launcher paths, exit codes, doctor stdout and stderr, and
the build and packed ZIP succession job results.

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

## 7. Cache and index isolation

Use copies of media so test cleanup cannot damage a production library.

### L-SMASH-Works indexes

Verify all of the following:

- Use a read-only media directory containing both a legacy `<media>.lwi` and an
  old runtime-token-named sidecar. Retain their original byte hashes and directory
  listing. Run the installed CLI and a generated VSView session. Both legacy
  files and the directory listing must remain unchanged. Deliberately invalid
  sidecar bytes must have no effect on the decoded result.
- A first run creates an index and commit metadata under
  `<resolved paths.generated_dir>/cache/source-indexes/`. A second run opens it
  with `cache=0` and leaves the committed bytes and modification times unchanged.
  Confirm the warm open still probes headers and reuses the committed geometry
  proof. Cold opens and the private fallback, including in VSView, scan complete
  coded and visible frame geometry before the native open.
- On NTFS, replace source bytes in place with the same byte length and restore the
  original modification time. The next run must reject the old index because the
  handle-reported ChangeTime changed. Repeat a normal cold write and warm hit to
  prove the staged index flush succeeds with the Windows write-capable handle.
- A missing or corrupt managed entry rebuilds in a private staging directory.
  Invalid metadata, geometry policy or probe mismatches, runtime-token or digest
  mismatches, and redirected entries cannot authorize stable reuse. An unwritable
  cache falls back to a cache-free open.
- Confirm cancellation and failures do not commit incomplete index metadata, and
  the native plugin never creates or changes an index in the media directory.

Run the focused process and cache cases from the exact candidate checkout on Windows:

```powershell
uv run --no-sync pytest -o addopts="" -q -ra `
  tests/utils/test_subproc.py::test_windows_child_uses_kill_on_close_job `
  tests/utils/test_subproc.py::test_windows_failed_assignment_stops_and_reaps_child `
  tests/utils/test_subproc.py::test_windows_reports_job_close_failure_after_reaping_leader `
  tests/utils/test_subproc.py::test_successful_leader_cannot_leave_a_capture_pipe_open `
  tests/services/test_alignment_paired_streaming.py::test_paired_collection_finishes_when_descendant_inherits_pipe `
  tests/vs/test_source_index_cache.py::test_cold_write_warm_hit_and_same_length_source_overwrite `
  tests/vs/test_source_index_cache.py::test_source_overwrite_after_index_replace_prevents_metadata_commit
```

The application starts its children with normal `Popen` and immediately assigns
them to a preconfigured kill-on-close Job Object. The focused assignment tests
use a simulated Win32 API. On Windows, verify bounded cleanup and that a job-owned
descendant retaining an inherited capture pipe stops after its leader exits. Also
close or cancel an installed VSView review and a paired FFmpeg alignment run and
check for leftover descendants. A descendant can escape if it starts in the small
interval before assignment. An interrupt inside `Popen` can also prevent the
application from receiving the handle needed for cleanup.

### Application caches

Verify with old and newly generated data:

- Old analysis cache misses and regenerates when decoder identity differs.
- Probe cache keys include the candidate probe fingerprint.
- Alignment reuse misses when the standalone FFmpeg lineage differs.
- Render/run metadata records the complete candidate runtime contract.
- `--from-cache-only` fails closed when only stale cache data exists.
- `--no-cache` removes the matching analysis entry, recomputes, and persists a fresh
  entry; repeated runs without it then hit. See the
  [run command contract](current-cli-contract.md#run-command-contract).
- Repeated candidate runs produce valid cache hits without changing selected frames.
- Unrelated cache scopes are not invalidated without a documented reason.

## 8. ZIP installation over the previous release

Keep a separate active installation of v0.6.1 with test data in the bundle's
config, input, and generated folders. Check the candidate ZIP against the digest
recorded for your route. Extract it into a fresh directory on the same volume
as v0.6.1 and run `install.cmd` before uninstalling anything. Open a new terminal
and use the installed shim to check `frame-compare --help`, the candidate version,
existing config, and run history. Check the moved configuration, sources, run folder, and report assets
in the candidate. Check that the previous bundle's application remains usable
and that the installed AppData fallback and any configured external generated-data
root retain their contents. Check `install.cmd -UserData Leave` with a separate test
installation. If you run the v0.6.1 installer again, it reactivates v0.6.1 and
restores its updater. The moved folders stay in the candidate. To test moving
data back with `install.cmd`, use two bundles that support carry-over.

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

## 10. Native VSView panel acceptance

Hosted Windows verification is required to prove the exact package, embedded runtime,
same-environment entry-point discovery/loading, offscreen panel construction,
generated-session metadata, atomic result round trip, and fail-closed result
validation. After that proof
passes, record these remaining interactive checks on a physical Windows 10/11 x64
system:

- open a real Frame Compare-generated session through the installed portable launcher;
- verify audible VSView playback through the Windows output device with the
  [alignment-review audio fixture](#alignment-review-audio-fixture);
- verify the panel is discoverable from VSView's Tool Panel and remains inert in an
  ordinary VSView session;
- verify one `Reference` and ordered `Comparison N` tabs, current-frame context, bounded
  suggestion markers, source-frame bounds, signed relationship, and trim-direction text;
- unlink playheads, visit every source, use the whole-set positions action, then close
  VSView and verify Frame Compare applies only the validated offsets;
- exercise the manual source-frame and known-offset bases plus the whole-set keep-audio
  action;
- close or cancel before saving and verify optional mode retains the current result
  while forced mode fails with an actionable diagnostic;
- exercise missing/malformed/stale/mixed/duplicate/incomplete/out-of-bounds sidecars,
  bounded readiness failure, child-process failure, and timeout behavior;
- use real L-SMASH-backed media to verify native decoder/index diagnostics, then inspect
  early, middle, late, and final shared-content evidence for drift or edit changes;
- on the production GPU, verify Vulkan/HDR behavior and compare report output against
  the prior supported bundle where the release changes runtime behavior.

Record exact bundle SHA, OS/GPU/driver/runtime facts, commands, logs, sidecar fixtures,
screenshots, and pass/fail results. Hosted or macOS offscreen proof must not be reported
as physical Windows desktop acceptance.

### Alignment-review audio fixture

The generated session registers video outputs. To check audio playback with the
alignment panel open, use disposable inputs and give the reference a known audible
track. Copy the generated script to a separate directory, keeping its filename,
and append this after the existing `run_session(...)` call:

```python
import vapoursynth as vs
from vsview import set_output

audio = vs.core.bs.AudioSource(SESSION_DATA["reference"]["path"], cachemode=0)
set_output(audio, "Reference audio")
```

From the extracted candidate root, open the copied script in a fresh PowerShell
session. Substitute its absolute path:

```powershell
$env:QT_MEDIA_BACKEND = 'windows'
$env:FRAME_COMPARE_RUNTIME_KIND = 'windows-portable'
.\python\python.exe -m frame_compare.vsview.launcher --no-settings '<copied session script>'
```

Open the alignment panel, select **Reference audio**, and play the reference. Record
whether the sound is audible. Close the fixture without saving an alignment result.
Use the original generated session for the production panel and result checks.

## 11. Completion record

Record the physical results in the media-runtime pull request for a local build
or in the promotion pull request for a published RC. Include the following.

- Tested commit SHA and bundle ZIP SHA-256.
- For a published RC, the release URL, tag, hosted run URL, and producer artifact ID.
- Test-system and GPU/driver identity.
- Passed, failed, skipped, and unavailable cases.
- Exact real-media categories exercised.
- Source-loader behavior changes and their classifications.
- Cache/index and ZIP installation results.
- HDR/Dolby Vision objective and perceptual findings.
- Residual risks or platform-specific limitations.
- Independent final reviewer identity/session, reviewed commit SHA, verdict, and any
  findings or accepted counter-evidence.
- A clear recommendation on whether to merge or promote.

Resolve production-significant failures before marking the media-runtime pull
request ready or promoting the RC.
