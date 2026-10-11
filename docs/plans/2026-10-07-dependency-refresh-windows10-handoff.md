---
search:
  exclude: true
---

# Dependency refresh: Windows 10 acceptance handoff

Status: Active

Prepared 2026-10-07. Continue the user's authorized dependency refresh, finish the
Windows checks, fix demonstrated regressions, and return an evidence-backed acceptance
report. Read `AGENTS.md` and `.agents/project.md` first. Use the shared coding and
verification skills. Do not publish, deploy, merge, or send external messages.

The returned Windows record reports automated acceptance complete after the verifier
fix below. Continue with the remaining physical-display and maintainer dispositions;
the original execution instructions remain available for reproducing or invalidated
checks. No open item has been waived.

## Candidate and transfer

The original macOS implementation was prepared as an uncommitted diff on
`agent/e2e-test-strategy`, based on
`095fbd92281451a73a15a9e51bf14001259a119f`. No PR or remote candidate exists yet.
The transfer package contains `dependency-refresh.patch`, this document through that
patch, and local evidence. Use the supplied patch or a subsequently committed exact
candidate; do not rerun dependency resolution to recreate the changes.

For patch transfer, start from a separate clean checkout at that base:

```powershell
git status --porcelain
git switch -c dev/dependency-refresh-windows10 095fbd92281451a73a15a9e51bf14001259a119f
git apply --check C:\path\to\dependency-refresh.patch
git apply C:\path\to\dependency-refresh.patch
```

Stop on any failed Git command. Confirm the initial status was empty, inspect the
diff, and preserve patch line endings. Verify the selected inputs before building:

| Input | SHA-256 of candidate bytes |
| --- | --- |
| `uv.lock` | `5fda9e880eb2dcf68dd9a60a2fc40acf7ee8e956ffd3fcd66efca982ceb90a5f` |
| `tools/windows_portable/manifest.windows-x64.json` | `e7b0ba3f594f161397466d198b5563535abba4834831305813f18fad7533840e` |

Use `Get-FileHash -Algorithm SHA256` for those files. If a checkout has converted
line endings, reconcile that difference against the patch rather than accepting an
unexplained mismatch. Make a local conventional candidate commit after inspecting
the changes, for example `chore(deps): refresh supported dependency stack`, and record
its exact SHA. This local commit is necessary: the portable builder archives `HEAD`
for application code and package metadata, and the update builder refuses dirty app
source. Do not build an ostensibly new bundle containing the old committed source.
Require a clean worktree for the acceptance build. Any later fix needs a new recorded
candidate commit and reruns of the evidence it invalidates.

When using an actual PR instead, use the exact-head checkout procedure in
[Physical Windows Media Runtime Validation](../media-runtime-windows-validation.md).
For a local candidate, substitute the recorded local candidate SHA wherever that
checklist expects `$ExpectedPrHeadSha`; identify the run as local candidate acceptance.

## Returned Windows evidence, 2026-10-07

The user supplied the Windows acceptance record as pasted text. The Windows commit
objects, ZIP, raw logs, and media are not available in this macOS checkout; the
following results are attributed to that record rather than independently rerun or
authenticated here. Its input hashes match the original transfer. A verbatim copy is
retained outside the repository in the transfer directory's
`windows-return/acceptance-record.md`; its relative evidence links refer to Windows
artifacts, not files available on this Mac.

| Identity | Reported value |
| --- | --- |
| Initial Windows candidate | `cdd183caed60ceac7855acc79a118164576a71fd` |
| Corrected tested Windows candidate | `4a35abe44ea7b54648dc0edfb08dc3a59dabcc32` |
| Windows branch | `codex/dependency-refresh-windows10` |
| Supplied patch SHA-256 | `ced0764daa7525f69574564a44a16a145dfe14e55135fa799c6ebc3e1bcae9c3` |
| Tested full bundle ZIP SHA-256 | `73538984f9f652f572120e00e9fb4a2ed7839c1757fd14f59264444d640b4f99` |
| Machine | Windows 10 Home x64 build 19045; Ryzen 9 5900X; 32 GiB RAM |
| GPU | RTX 5080; driver 617.14; Vulkan loader 1.4.341 / device API 1.4.351 |

The initial bundle proof retained a stale `vsview.main` import. Windows corrected it
to `vsview.app.main`, updated the proof marker and three test expectations, and reran
the affected checks and full artifact proofs. This fix is now integrated into the
macOS working diff. Local inspection of the installed 0.12.0 distribution confirms
that `vsview/main.py` is absent and `vsview/app/main.py` is present; the existing managed
launcher already imports the latter. The dependency inputs and runtime fingerprints
are unchanged. The original transfer ZIP remains the original evidence package and
does not contain this subsequent correction.

For a new transfer from the explicit base, use the transfer directory's
`windows-return/reconciled-dependency-refresh.patch`. For a checkout containing only
the original transfer, use `windows-return/windows-verifier-correction.patch` for
the two-file verifier correction. The reported corrected Windows candidate already
contains that code fix; do not apply it again. The reconciled full patch also contains
this updated task record.

The user subsequently requested commits. The macOS dependency refresh, Windows
verifier correction, and this reconciled task record are committed together on
`agent/e2e-test-strategy`. Use the commit containing this version of the record for
further builds; the original transfer and returned Windows SHAs remain evidence of
their respective tested source states. The macOS commit does not waive the remaining
acceptance items or establish a hosted CI result.

After integrating the correction, macOS checks passed 59 build-verifier tests with
32 Windows/PowerShell skips, actual `vsview.app.main` import after Qt startup, owned
Ruff lint/format checks, strict documentation build, and `git diff --check`. These
checks supplement the reported 91-case Windows module pass; they do not rerun it.

| Check | Reported Windows outcome |
| --- | --- |
| Full serial source suite, initial candidate | 3221 passed, 45 skipped, no failures/errors |
| Windows portable subset within that suite | 181 passed, zero skips |
| Build-verifier module after correction | 91 passed, zero skips |
| Actual Edge report-browser smoke | 17 passed, zero skips |
| Static gates, frozen graph, docs, advisory audit, distributions | Passed; isolated installed help/version worked without Qt or VapourSynth |
| Corrected full bundle, fresh ZIP, extraction/install verifier | Passed all eight proof phases and required markers; 105 inventory/license records |
| Physical GPU/native frames | Actual placebo frames passed; application RGBS/32-bit and direct RGB48/16-bit outputs |
| Extracted Rust packing | Five RGB formats, with/without alpha, matched Python bytes |
| Media and normal CLI | Eight generated and six private SDR/HDR10/Dolby Vision cases; sampled old/new frames and tested tone-map frames matched; repeat render PNGs matched |
| Alignment authority | Verified 0.5-second delay applied four frames; unrelated audio remained provisional with no applied deltas |
| Cache/index behavior | Actual source-R80 analysis-cache migration, warm/cache-only/no-cache and corruption behavior; owned index recovery and legacy/foreign preservation |
| Update apply/rollback | Temporary-key signed candidate passed matching apply/backup/hash rollback; eight simulated invalid/old metadata variants refused before replacement |

The GPU attribution follows enumeration of a single RTX 5080; the render logs did not
record a selected adapter ID separately. The R80 comparison used the existing source
environment, not an exact immediate-predecessor portable installation. The index
fallback used a filesystem obstruction, not ACL denial. Alpha packing does not prove
alpha-bearing media decoding, and generated interlace metadata does not prove real
interlaced-motion behavior. No separate actual portable probe/alignment-cache migration
was performed.

The source-suite skips included browser availability later exercised with Edge,
opt-in media later exercised through bundled CLI checks, Linux/Darwin-only long-audio
RSS measurement, unauthorized live services, and POSIX-only or unavailable-tool cases.
Do not rewrite the original skip counts. Doctor's optional slow.pics HTTP 403 and
missing TMDB key were recorded; neither is a passing network/configuration check.

Visible automation could read accessibility but failed screenshot/input recovery with
`FrameArrived timed out`, a window capture timeout, and unavailable coordinate geometry.
The ordinary workspace loaded with inert alignment actions. Qt logged Windows exception
`0x8001010d` in both R80 and R81 comparison processes. That observation establishes
neither a candidate-specific regression nor successful visible acceptance; the
underlying host/viewer/automation interaction remains undiagnosed. No visible playback,
generated-session confirm/keep/cancel, or color-managed perceptual pass is claimed.

| Remaining item | Owner and revisit condition |
| --- | --- |
| Visible ordinary/generated VSView operation and display perception | User/physical tester: use a working capture session or manual display session; complete playback, seeking, reload, SAR, confirm/reopen/keep/cancel and 100%-scale HDR/gradient checks |
| Exact predecessor portable migration | Maintainer: provide the exact old bundle or explicitly disposition the narrower source-R80 and simulated-refusal evidence |
| Private interlaced-motion/VFR/SAR/alpha cases | Media owner/maintainer: supply cases or explicitly disposition unavailable coverage |
| Production private-key signing | Release maintainer: authorized production signing context; public-key validation and temporary-key success are separate evidence |
| Corresponding-source/legal release acceptance | Release/legal maintainer: adjudicate the deployed subset and source offer; inventories alone do not grant release acceptance |
| Hosted Actions, Docker amd64, Linux NVIDIA/X11 | Platform maintainers: run the intended platform gates; preserve local aarch64/offscreen evidence separately |

The Windows record reports independent review of corrected SHA `4a35abe4` with no
material findings. Full local Windows acceptance and merge/release readiness remain
conditional on the required display evidence and maintainer dispositions. Keep this
record Active until those outcomes are recorded.

## What changed

| Surface | Candidate |
| --- | --- |
| Packaged Python | 3.13.16, preserving the CPython 3.13 runtime |
| VapourSynth | R81 / API R4.3; source `dd11a9da6f8e2bb24ab4bb084d44bf01fb93612a` |
| Viewer | VSView 0.12.0; Cyclopts 5.2.0 replaces `vsview-cli` |
| RGB packing | vspackrgb 2.0.0, `vspackrgb.rust` replaces the Cython extension |
| Windows FFmpeg | BtbN `autobuild-2026-09-30-13-08`, `n8.1.3-9-g29e619e767`, win64 LGPL 8.1 |
| Tooling | uv 0.12.23, Ruff 0.16.10, Zensical 0.0.68 |
| Python graph | Typer 0.27.3, filelock 4.0.12, iniconfig 2.3.1, jetpytools 3.1.2, MarkupSafe 3.0.4, platformdirs 4.12.3, python-dotenv 1.2.4, tomli 2.5.0; new Cyclopts transitive dependencies |
| Hosted artifact actions | upload-artifact 7.0.2 and download-artifact 8.0.2, immutable commit pins |

The user explicitly chose official upstream plugin wheels. Keep L-SMASH-Works 1310,
vs-placebo 2.0.4, BestSource 22, PySide6 6.11.2, and their exact bundled-library
provenance. Do not invent custom builds to upgrade standalone dav1d, libxml2, libvpx,
xxHash, nv-codec-headers, or libdovi. Qt source releases alone do not upgrade the
PySide6 wheels. `pydantic-core` stays at 2.46.5 because Pydantic 2.13.5 requires it.

Windows full fingerprint:
`b47d64de188aab069cf3c3b9d51add6d0b3416c5ee175b4c0646b72436219320`.
Windows index token: `lsw1310-f125953022b6`.
Docker full fingerprint:
`916760dd9ca2156521326493fbe92c395118d6f1ee36cc421d9bb9e2f66a8697`.
The runtime owner computes scope-specific identities; do not hand-edit them merely
to satisfy a test. Crossing the previous R80 full fingerprint requires a complete
portable reinstall. The current code-only update must refuse the predecessor.

## Evidence already established here

Host: macOS Apple Silicon; Python 3.13.16; uv 0.12.23 invoked through uvx;
Docker Desktop Linux aarch64 engine 29.8.0. Native macOS has BestSource but lacks
L-SMASH, FFMS2, and vs-placebo. PowerShell is absent.

The source, lock, and manifest identify these results; the original local checks ran
on the working diff against the base above, not a hosted CI commit. Evidence filenames below are included in
the transfer package's `evidence` directory.

| Check | Result / retained evidence |
| --- | --- |
| Frozen lock and sync | Passed with all groups and the VSView extra |
| Type, lint, format, security, import contracts | Passed; Pyright has zero errors/warnings; Bandit passes the configured medium/high gate |
| Full native suite | 3126 passed, 90 skipped; `frame-compare-native-bumps-final.log` and JUnit XML |
| Windows portable suite on macOS | 107 passed, 74 skipped; skips require PowerShell or Windows semantics |
| Canonical Docker media gate | 276 passed, zero skips, production installed-CLI/media artifact proof passed; `frame-compare-docker-bumps-accepted.log` |
| Opt-in Docker audio resource gate | 3 passed; three-hour and maximum-lag RSS stayed within the contract; cancellation reaped both children; `frame-compare-resource-bumps.log` |
| Docker GUI image + offscreen proof | Passed; `frame-compare-gui-proof-bumps.log` |
| Native Rust packing | RGB24/RGB30/RGB48/RGBH/RGBS with and without alpha matched the Python backend byte-for-byte at width 17; `frame-compare-rust-packing-bumps.log` |
| Wheel/sdist and installed CLI | Passed contents/metadata verification and fresh Python 3.13.16 install; version/help passed |
| API reference and strict docs | Passed, including the handoff; `frame-compare-docs-bumps-final.log` |
| Advisory audit | No known PyPI advisories in the hash-locked export, plus a cross-platform audit of all 96 non-project locked packages and Hatchling; `frame-compare-updated-audit-all.json` |
| Windows artifact provenance | Downloaded and checked 13 changed binary/source/build objects against bytes/SHA-256; BtbN upstream checksum, R81 license, and ABI3 wheel layout verified; `windows-artifact-evidence.json` |
| Independent review | No material correctness/maintainability findings; one stale jetpytools documentation version corrected |

The Docker image was built with refreshed immutable Python/uv images and R81 from a
no-cache build. Native Docker proofs covered actual L-SMASH/FFMS2/placebo frames,
source-tree provenance and OBUParse shared linkage, generated H.264 limited/full-range,
VFR/interlaced, HEVC10 HDR10 tone mapping, AV1, software Vulkan, JSON doctor, and
non-root execution. Debian FFmpeg remains `7:7.1.5-0+deb13u1`.

The GUI proof used `tools/verify_docker_gui.sh --inside-container` in the built
`gui-linux` image, with `QT_QPA_PLATFORM=offscreen`, a temporary HOME/runtime directory,
and `PYTHONUSERBASE=/home/framecompare/.local`. It passed VSView help, Qt startup,
BestSource, doctor, the exact native panel entry point, real generated L-SMASH session
loading, named three-source outputs, frame-0 rendering and indexes, position/keep
decisions, result validation, and cleanup. This is Linux-container offscreen media
proof on macOS Docker Desktop. It does not establish the Linux X11 host wrapper,
visible desktop interaction, native Windows RGB packing, or physical GPU behavior.

PyPI advisory results do not establish a native-library CVE clearance. Hosted GitHub
Actions, Docker amd64, Linux NVIDIA, and visible Linux X11 were not run here. Signing,
corresponding-source/legal acceptance, and physical Windows acceptance remain open.

## Windows execution

Use Windows 10 x64 with the intended production GPU/driver, PowerShell 7 (`pwsh`), Git,
uv/uvx, enough disk, and the private real-media corpus. Record OS build, CPU/RAM,
GPU/driver/Vulkan, PowerShell, Python, uv, exact candidate SHA, prior bundle identity,
and media case identifiers before changing the installation.

Use the pinned toolchain without upgrading the lock:

```powershell
$ErrorActionPreference = 'Stop'
function Invoke-RefreshUv {
    & uvx --from 'uv==0.12.23' uv @args
    if ($LASTEXITCODE -ne 0) { throw "uv failed: $args" }
}
Invoke-RefreshUv python install 3.13.16
Invoke-RefreshUv lock --check
Invoke-RefreshUv sync --all-groups --extra vsview --frozen --python 3.13.16
```

Run the repository gates in checklist section 1 through `Invoke-RefreshUv` (replace
the leading `uv` in each command). Run pytest **serially** on Windows and retain JUnit
and console logs. Inspect every skip: a mocked source suite is separate from the
bundled native proof. Run the locked advisory audit from the runbook on Windows.
Build a wheel/sdist into a fresh directory, run `scripts/verify_distribution.py`,
and test a fresh installed wheel's version/help as well as source commands.

Then execute all ten sections of
[Physical Windows Media Runtime Validation](../media-runtime-windows-validation.md)
and the [Windows Portable / Release-Path Verification](../ENGINEERING_RUNBOOK.md#windows-portable-release-path-verification)
procedure. Those sources own the full requirements and commands; this handoff adds
candidate-specific emphasis:

1. Build one fresh full bundle using `build_portable.ps1` from the clean committed
   candidate. Retain `WINDOWS_BUNDLE_PROOF` output and check every phase/marker in
   `.github/workflows/windows-portable-build.yml`. Run the real GPU/placebo frame
   proof; a hosted-runner Vulkan skip does not satisfy this physical-machine check.
2. Package that exact directory, record ZIP SHA-256, and run
   `verify_extracted_bundle.ps1` with `-ExpectedCommitSha` equal to the recorded
   candidate HEAD, a fresh extraction root, retained doctor streams, and the
   five-minute command deadline. Check `WINDOWS_EXTRACTED_PROOF`, installed shim
   parity, canonical DLL loading, LGPL FFmpeg, absent FFMS2/WebEngine, retained Qt
   Multimedia, inventories/licenses/source provenance, and native-extension imports.
3. In the extracted bundle, visibly open VSView 0.12 through the managed launcher.
   Exercise an ordinary workspace (inert Frame Compare panel) and a generated
   L-SMASH alignment session with `Reference`, `Comparison 1`, and `Comparison 2`.
   Check preview/framebuffer colors and precision with the Rust packer, playback,
   seeks, reload/workspace switching, aspect ratio, and panel callbacks. Capture
   all three positions, confirm, reopen and keep current alignment, cancel/close,
   and validate complete atomic result sidecars without granting unconfirmed offsets
   cache/trim authority. Preserve valid zero offsets.
4. Run generated fixtures plus private real SDR/HDR10/Dolby Vision, VFR/interlace,
   non-square SAR, range/chroma, alpha where available, and audio-sync cases.
   Compare old/new frames, metadata, seek boundaries, and end-to-end reports.
   Retain objective differences and perceptual notes on the intended display.
5. Prove cache/index migration from R80 to R81, stale-cache-only refusal,
   cache-free behavior, corruption recovery, unwritable fallback, and warm reuse.
   Preserve unrelated media/index/generated data and keep the old installation intact.
6. Build the candidate code-only update with `build_update.ps1`. Prove R80 refusal
   before replacement, schema-2 refusal, malformed/legacy identity refusal, unsafe
   override refusal, full reinstall, and matching-candidate apply/backup/rollback
   with hash restoration. Complete the serial Windows installer/uninstaller,
   PATH/shim, process-tree, timeout/output-cap, and updater tests that skipped here.
7. Retain existing signing and corresponding-source/legal gates. A temporary-key
   test is separate from production-key acceptance. Never copy secrets into evidence.
   If the production key or a maintainer decision is unavailable, record that gate
   as unavailable with its owner and revisit condition; do not claim release readiness.

Fix demonstrated regressions within this refresh, commit the corrected candidate,
and rerun affected proofs. Preserve upstream provenance and fail-closed assertions.
Ask for missing hardware/media or an actual maintainer decision only when required;
continue independent checks meanwhile.

## Return and completion

Return the exact tested candidate SHA, bundle ZIP SHA-256, machine/GPU identity,
commands with exit codes, pass/fail/skip counts and reasons, proof markers, tested media
categories, old/new output observations, migration/update results, visible UI results,
and evidence locations. For every unavailable/deferred case, name the owner, reason,
supporting evidence, acceptance rationale if authorized, and revisit event.

State separately whether local Windows acceptance, hosted platform gates, signing,
and release/legal acceptance are complete. Do not infer amd64 Docker or Linux X11/GPU
acceptance from Windows success. Give an evidence-backed merge recommendation;
unresolved production-significant failures block readiness. Mark this task record
Historical once the remaining acceptance and disposition are recorded.
