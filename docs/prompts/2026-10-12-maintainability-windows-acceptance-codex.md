---
search:
  exclude: true
---

# Windows acceptance for the maintainability remediation

**Status: Historical; superseded by the accepted remediation closure.**

The [remediation plan](../plans/2026-10-12-maintainability-remediation.md)
records acceptance of human-provided U2 and unsigned-U8 Windows evidence at
`929c076ac7fb570f28cb0ef7a641beb2a51843cb` and marks the plan Historical.
The procedure below is preserved as historical evidence, not a current execution
request or continuing authorization. Its former execute/keep-Active directions
are retired.

For new changes, use the applicable procedures in the current
[Engineering Runbook](../ENGINEERING_RUNBOOK.md). Historical acceptance does not
verify later source changes or prohibit justified Windows checks. Visible VSView
interaction, broader physical-media coverage, predecessor migration, signing,
legal release disposition, and hosted-CI acceptance remain separate claims.

## Historical handoff context

This handoff requested the remaining Windows acceptance for Frame Compare's
maintainability remediation on `v0.7.0`. The following scope, commands, prior
results, and return-report instructions document that completed handoff; they
are not current work instructions.

## Source and outcome

The six remediation commits end at
`b5df8a4d3060cb2550b5ba9c0f037ad1b85a63c3`; the following documentation commit adds
this handoff and records the authorized branch push. The implementation baseline
was `933395d820d780207b953b4231f6761390f66689`. Resolve and record the actual pulled
HEAD before testing; the minimum candidate must contain `b5df8a4d`. Inspect any
later source changes rather than silently reusing evidence for a different runtime.

Read these sources relative to the Windows checkout:

- `docs/plans/2026-10-12-maintainability-remediation.md`: decisions, U2/U8 and evidence.
- `docs/ENGINEERING_RUNBOOK.md`: complete Windows Portable / Release-Path
  Verification procedure and separate physical-Windows limitations.
- `docs/supported-media-runtime.md`: supported runtime and cache identities.
- `.github/workflows/windows-portable-build.yml`: unsigned build/ZIP/extracted proof.
- `tools/windows_portable/build_portable.ps1`, `runtime_smoke.py`,
  `write_bundle_inventory.py`, and `verify_extracted_bundle.ps1`.
- `src/frame_compare/render/naming.py`, `render/batch/expansion.py`,
  `tests/render/test_naming.py` and `test_expansion.py`.

The then-open gates were actual unsigned Windows bundle acceptance (U8) and
actual Windows-volume screenshot identity, preservation and cleanup (U2). Both
were subsequently accepted for the source identified in the closure above.

## Approved decisions and boundaries

Physical screenshot-name collisions must fail before native preparation with typed
`FC-4021` / `SCREENSHOT_OUTPUT_COLLISION`. Preserve existing files, naming and
selectors. Use actual filesystem equivalence, including Unicode rules; distinct
names must remain valid. Exact generated duplicates also fail.

There are no current users. Run-local `manual_overrides.toml` is now version "2"
without `confirmed`; record presence represents accepted manual authority. Old
versions are recoverable cache misses without migration. Native VSView result
sidecar schema v1 and its `confirmed` / `keep_current` actions are unchanged.

The human authorized correcting discovered regressions within agreed contracts;
consult them before a material contract change or new functionality tradeoff.
Preserve alignment authority, valid zero offsets, typed sanitized errors,
JSON-clean stdout, deterministic artifacts, committed provenance and owned cleanup.
Do not add compatibility shims, weaken assertions, bypass hash/license/source
checks, downgrade dependencies or accept a timeout/native skip as a pass.

Build and verify locally without signing, publishing, release tags, PRs or live
slow.pics/webhook calls. Do not dispatch the manual signed Windows workflow.
The Mac orchestrator owns this branch push; subsequent pushes require human
direction. Preserve unrelated Windows checkout changes, existing installations,
media/configuration, caches and credentials. Use a fresh ignored acceptance path;
do not delete an old bundle to reuse its directory.

If a fix is necessary, retain failure evidence, make a focused correction and
meaningful checks, obtain independent review, then create a conventional commit
and report its SHA. Use the requested GPT-6.1-Sol medium implementation / high
review selection for any delegated correction if available. Do not spawn chats
merely for ceremony. Do not push or change contracts without human direction.

## Establish the checkout and environment

Inspect `git status --short`, branch, HEAD and `origin/v0.7.0`. If the human has not
pulled, a clean checkout can use `git pull --ff-only origin v0.7.0`. Do not
stash/reset/force a dirty checkout or merge unrelated divergence; explain conflicts.

Use 64-bit Windows and PowerShell 7+ for the source build. Check Git, uv, toolchain
and disk space. Bootstrap source-test dependencies with the repository's
`uv sync --group dev --extra vsview --frozen` when needed. The portable builder uses
its own managed interpreter/runtime. Record OS build/architecture, PowerShell,
tool versions and actual source SHA. A global VapourSynth installation must not
satisfy a missing bundled-runtime obligation.

Run existing relevant regressions and retain their outputs and skips:

```powershell
uv run --no-sync pytest -q tests/windows_portable tests/workflows tests/render/test_naming.py tests/render/test_expansion.py tests/render/test_types.py
if ($LASTEXITCODE -ne 0) { throw 'Windows/platform regression checks failed' }
```

For U2, put pytest temporary files on the Windows output volume being accepted;
use a fresh `--basetemp` there when necessary. Record the volume/profile and actual
case sensitivity. Retained tests independently inspect physical identity for
Movie/movie, Ç/ç, NFC/NFD, Straße/Strasse, distinct-name controls and hard links,
plus preservation, cancellation and failed-reservation cleanup. Do not require
every Unicode pair to alias on Windows. Expansion tests prove typed refusal before
preparation/render admission. Also exercise the changed naming owner from the
extracted bundle using its interpreter and application source against disposable
actual-volume files; retain typed error, distinct-name and cleanup observations.
This packaged probe supplements the retained tests, rather than replacing them.

## Actual unsigned build and extracted-bundle proof

Read the runbook and scripts first. Start from the repository root in PowerShell
7+, use fresh paths, and retain logs outside the bundle's owned cleanup. Check each
exit before continuing. Do not pass `-RequireReleasePublicKey` or provide secrets.

```powershell
$ErrorActionPreference = 'Stop'
$candidateSha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve candidate SHA' }
git merge-base --is-ancestor b5df8a4d3060cb2550b5ba9c0f037ad1b85a63c3 HEAD
if ($LASTEXITCODE -ne 0) { throw 'Checkout lacks the accepted remediation' }
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffZ')
$acceptanceRoot = Join-Path (Join-Path $PWD 'dist') "maintainability-acceptance-$stamp"
if (Test-Path -LiteralPath $acceptanceRoot) { throw 'Acceptance directory already exists' }
New-Item -ItemType Directory -Path $acceptanceRoot | Out-Null
$bundlePath = Join-Path $acceptanceRoot 'frame-compare-portable-win-x64'
$zipPath = Join-Path $acceptanceRoot 'frame-compare-portable-win-x64.zip'
$extractRoot = Join-Path $acceptanceRoot 'zip_extract_check'

pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir $bundlePath -CacheDir .portable_cache 2>&1 | Tee-Object -FilePath (Join-Path $acceptanceRoot 'build.log')
if ($LASTEXITCODE -ne 0) { throw 'Unsigned portable build failed' }
Compress-Archive -Path $bundlePath -DestinationPath $zipPath
Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath | Format-List | Out-File (Join-Path $acceptanceRoot 'zip-sha256.txt')

pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/verify_extracted_bundle.ps1 -ZipPath $zipPath -ExtractRoot $extractRoot -DoctorStdoutPath (Join-Path $acceptanceRoot 'extracted-doctor.json') -DoctorStderrPath (Join-Path $acceptanceRoot 'extracted-doctor.stderr.txt') -ExpectedCommitSha $candidateSha -CommandTimeoutSeconds 300 2>&1 | Tee-Object -FilePath (Join-Path $acceptanceRoot 'extracted-proof.log')
if ($LASTEXITCODE -ne 0) { throw 'Extracted portable proof failed' }
```

The builder requires `runtime_smoke.py` and inventory source bytes to match Git.
If a fix is needed, commit the reviewed correction, resolve the new candidate SHA,
and rebuild into another fresh directory. Do not edit an extracted candidate in
place or substitute a mocked proof and call the bundle accepted.

Require all eight ordered Python phases with their required start/ok/failure
semantics: `package_imports`, `runtime_contract`, `vapoursynth_environment`,
`lwlibavsource_frame`, `placebo_tonemap_api`, `apply_tonemap_frame`,
`placebo_tonemap_frame`, `vsview_runtime`. Check preload-before-Qt, managed plugin
topology, generated L-SMASH media, application tonemap, VSView entry point/panel,
whole-set metadata/result roundtrip, malformed-result rejection, offscreen launch
and owned process cleanup. FFMS2 stays absent from the Windows baseline.

Require extracted help/version/doctor, ZIP layout, licenses/inventory/runtime
fingerprint and exact source commit; require `WINDOWS_EXTRACTED_PROOF result=ok`.
An "ok" substring alone is insufficient. The runbook permits only its exact
Vulkan-unavailable outcome on hosts lacking that runtime; record it without
claiming physical GPU acceptance. Offscreen proof is distinct from visible
desktop acceptance. Perform applicable physical-host checks if available and
report them separately; otherwise state the limit. Updater/signing changes are
outside this remediation; do not expand into signing or existing install mutation.

## Prior evidence and return report

Source implementation used GPT-6.1-Sol medium workers and high independent
reviewers. Mac native suite passed serially: 3404 passed, 99 platform/opt-in skips.
Docker media gate passed 281 tests with zero skips plus production CLI artifacts.
Linux production-image offscreen VSView and 50 filesystem tests passed; exclusive
real-Chrome browser tests passed all 21 cases. Static/import/API/strict-doc checks
passed. None establishes Windows acceptance. Parallel Mac Chrome dumps sometimes
exited 2 with a teardown-watchdog message; no product defect/root-cause fix was
established, and assertions/timeout/retry requirements were not relaxed.

Return a concise report in the Windows chat for the human to bring back. Include
exact source SHA, host/runtime versions, commands and exit/results/counts/skips,
absolute artifact/log paths and ZIP hash, every phase/extracted-proof outcome,
U2 actual-volume identity/preservation/cleanup observations, process cleanup,
correction commits/diff and review, and remaining visible/GPU/platform limits.
Do not claim a skipped/mocked/static phase or absent CI job as a runtime pass.

The original handoff required keeping the plan Active until Windows acceptance.
That requirement was fulfilled; the accepted closure supersedes this handoff.
The historical return route was a human-pasted report to Mac orchestrator chat
`01a131e8-0fff-7692-8a33-73c7acee693d`, not an automatic cross-chat callback.
