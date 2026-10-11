---
search:
  exclude: true
---

# Runtime and acceptance observations still needed

Reviewed source `58e50a6d48c0004b63f60b9b3ba53c1ac4b31537`. This is a list of unresolved evidence, not authorization to build/install/sign/publish or contact live services. No hypothesis is included in accepted remediation. Recheck current source/artifact identities when executing a later authorized observation. Use disposable workspaces/accounts/output, bounded processes, exact command/exit/log identity and owned cleanup; retain useful failure evidence and never touch production installations/private media.

CONFIRMED defects can still need target-host acceptance after correction. LIKELY findings have a supported source trace but lack the particular platform/hosted execution. Historical offscreen/Windows handoff records are not a current-SHA pass.

## O-01 — Windows5.1 non-ASCII install-state decoding

**Acceptance gap for LIKELY F-010; high source confidence.** Host: physical Windows10 x64 or supported Windows target with Windows PowerShell5.1, ANSI system code page, no pwsh on PATH/fixed discovery route, and isolated LOCALAPPDATA/PATH. Record OS, `$PSVersionTable`, ANSI code page, bundle source SHA and authenticated ZIP SHA256; use a real complete bundle, not metadata fixtures.

Extract into a disposable non-ASCII path such as `C:\Review\José\bundle`, run that bundle's `install.cmd`, open a fresh terminal and run `frame-compare version` and `frame-compare-update list-backups`. Capture BOM-less install-state path bytes without credentials. Pass: both readers use the exact installed Unicode path and commands succeed. Fail: mojibake/nonexistent launcher or bundle path. Controls: ASCII path under5.1 and non-ASCII underPS7. Restore only the disposable account's managed PATH/shims; preserve unrelated config/files. PS7-only or UTF-8-locale runs do not settle this case.

## O-02 — Source CMD fallback interpreter

**Acceptance gap for LIKELY F-011; D-01 required.** Host: Windows10 x64 with Git/uv and existing pre-synced dependencies, noPS7 in the wrapper's discovery routes. Input: clean exact-SHA disposable source clone. Command: root `install.cmd -SkipSync`. A minimal5.1 reflection command `[System.IO.Path].GetMethods() | Where-Object Name -eq GetFullPath` independently shows available overloads without building.

Before correction, source predicts raw no-two-argument-GetFullPath failure at builder30. Pass under chosen contract: working supported5.1 installation, or an explicit documented earlyPS7 prerequisite refusal before bootstrap/sync/build output. Fail: unsupported .NET method error after work. Control: PS7 root route successfully enters canonical builder. The reflection check alone is API evidence, not source-route acceptance. No current macOS test proves it.

## O-03 — Authentic retained backup across complete full-runtime replacement

**HYPOTHESIS · insufficient data · conditional S2 · medium confidence; D-03 required.** Source-only backups lack compatibility identity; rollback608–627/restore601–605 checks no runtime contract before deletion. Supported retained-backup reachability remains unresolved, so this is not an accepted defect.

Host/input: isolated physical Windows x64 installation/account; authenticated full A and B with recorded source/ZIP identities and different requirements/runtime fingerprints. A must support a correctly signed compatible code-only update that genuinely creates an owned backup. B must be a complete valid bundle; no hand-edited metadata or manually copied backup.

1. Install A and prove baseline runtime. Apply the compatible signed A update with `frame-compare-update apply <A-update.zip>`. Record `list-backups`, exact authentic backup ID and complete source hash manifest.
2. Extract B freshly as a reference. If D-03 supports overlay, perform that prescribed full reinstall into A's parent (candidate `Expand-Archive -LiteralPath <B.zip> -DestinationPath <A-parent> -Force`), run replaced bundle install.cmd, and observe whether the authentic A backup survives/listed. If supported replacement removes/strands it, this route rejects the hypothesis.
3. Prove current B inventory, runtime and application bytes match the fresh B reference, accounting only for documented generated/user state. Require B to be complete and functioning before rollback. An already-invalid mixed overlay is not a rollback reproduction.
4. Snapshot B source bytes/identity, run `frame-compare-update rollback <A-backup-id>`. Pass if compatibility refusal occurs before any B code byte changes, or the supported invariant prevents the incompatible candidate from being current. Source predicts A code restored while B runtime remains; record exact exit/stdout/stderr/trees and actual runtime behavior before claiming breakage.
5. Same-runtime control: apply/rollback restores exact prior source tree and external generated-data sentinels stay byte-identical. Do not fix a failing experiment by copying backups manually. Preserve failure evidence; clean only disposable installation.

If overlay is explicitly supported, missing-guard trace supports LIKELY before runtime. If fresh-root replacement is the contract, document/enforce and prove that route instead. Independent VW3 found source builder deletes output and installer E2E uses another directory; that materially mitigates reachability.

## O-04 — First target rename fails under Windows sharing lock

**HYPOTHESIS · insufficient data · S3 impact ceiling · low confidence.** Updater865 first Move-Item can fail; catch871–875 and restore601–605 may treat intact original as partial new and remove unlocked leaves. Backup mitigates recovery risk. POSIX rename intuition and a fake second-rename failure do not establish NTFS behavior.

Host: real Windows NTFS, disposable authenticated bundle and correctly signed compatible update. Snapshot every original application byte. Hold an existing original source leaf using a separate process with FileShare denying Delete; leave other leaves unlocked. Run `frame-compare-update apply <compatible.zip>` under an outer deadline, capture first-rename failure and exact residual tree. Pass: failure leaves original complete/working or fully restores it with typed actionable error and no leftover owned lock/process. Fail: unlocked originals disappear while locked leaf remains and restoration fails/incomplete. Release holder in finally, compare backup/current hashes and external sentinels. No production lock or installation is used.

## O-05 — Real native proof stall in local Windows builder

**HYPOTHESIS · insufficient data · S3 ceiling · low confidence.** Builder801–829 runs eight synchronous native proof phases without local per-phase deadline; later offscreen proof831–892 is bounded and hosted job has outer timeout. No currently hanging dependency was reproduced.

Host/input: real Windows candidate runtime that actually stalls at native import or placebo_tonemap_frame, exact source/dependency/artifact identities and known phase-start marker. Command: canonical `pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir <owned output> -CacheDir <owned cache>`, observed with an independent finite supervisor. Pass: local phase ends/refuses within documented limit and descendants/streams drain; fail: phase remains indefinitely after agreed limit or descendants survive termination. A deliberately sleeping replacement stub only proves harness mechanics; label it simulated and do not claim native hang. Stop at supervisor limit and retain evidence.

## O-06 — Later screenshot loss in offline pair modes

**HYPOTHESIS · insufficient data · S3 ceiling · medium-low confidence.** Main preloader resolves error and lacks visible-image error listener (`viewer.js:1900,1945,2051,2202`); Grid/Lens have separate state. Generation validates files and normal post-upload deletion requires embedding, so ordinary cleanup does not trigger it.

Host: Chrome/Chromium on supported macOS/Windows; owned tiny generated report with embed_images=false and at least two frames/sources. Delete/move one referenced screenshot only after successful generation. Open report.html via file URL and history route. Exercise Slider, Single, Diff, Blink and Grid, navigate away/back; restore file and repeat/retry. Pass: honest unavailable/error indication identifies selected missing content, navigation remains usable and recovery works. Fail: blank/broken primary image without actionable unavailable status while Grid distinguishes failure, or stale pair facts. Record actual DOM/console and screenshots, not just payload validity. No private media/native decode needed for this observation.

## O-07 — Infinite configured timeouts at actual owners

**HYPOTHESIS · insufficient data · S3 ceiling · low confidence.** Schema permits inf in screenshot FFmpeg, slow.pics navigation/image and TMDB timeout fields. Accepted F-005 concerns only demonstrated lead/trail window crash; infinite minimum window is not a crash. No real-service hang asserted.

Use local-only delayed HTTP endpoints with synthetic responses and the real HTTP owner, plus an owned sleeping subprocess through the FFmpeg timeout owner. Read each path's real injection seam first; never redirect credentials or contact product origins. Set the corresponding config timeout to inf; use a finite outer15s supervisor and cleanup. Controls: finite short timeout terminates/reaps within expectation, ordinary positive timeout succeeds. Pass: owner rejects inf before work with typed error or preserves an explicitly documented bounded deadline. Fail: operation remains waiting until supervisor, or raw numeric timeout exception defeats typed handling. Record exact selected config field/caller/transport/process behavior separately; do not infer all four outcomes from one owner or from dry-run acceptance.

## O-08 — Service response/body budget

**HYPOTHESIS · insufficient data · S4 · low confidence.** No response cap alone is not a demonstrated S2 failure. Fixed service origins, page1, bounded planner/concurrency and expected finite bodies mitigate; no normal-workload memory failure was established. This item is a budget question for future evidence, not an accepted implementation package.

First agree a maximum supported normal body/latency/memory budget from legitimate response measurements under separately authorized service access. Then use an owned localhost transport at a supported injection seam to deliver a bounded abnormal response and record peak RSS/decode time under a finite supervisor. Pass: typed bounded refusal or consumption within agreed contract, no secret diagnostics; fail: measured limit exceeded/hang attributable to that actual owner. Ordinary canned mocks or an arbitrarily giant string do not establish expected service behavior. No live/stress request was made here.

## O-09 — Real first/repeated Ctrl+C across media and native review

**Target acceptance gap for CONFIRMED F-001, not a new orphan hypothesis.** Host: supported native runtime with actual plugins/visibleVSView, plus Windows portable in a separate observation. Input: owned generated media configured for VS renderer, FFmpeg renderer and native alignment review in separate runs; external generated-data sentinel.

Run `frame-compare run --root <owned fixture workspace>` with explicit no-upload/skip-metadata configuration. Press Ctrl+C once while native review waits, once during render, and in separate runs repeat during cleanup/escalation. Record start/stop times, admitted frame/clip IDs, reserved run folder/record status, actual process PIDs and exit130. Pass after correction: no later phase/unit admission or applied review/manual/cache result, interrupted/failed record, owned children/work drained, external sentinel unchanged. Fail: later work/success record or surviving owned process. Native stuck thread must be distinguished from pending main-task cancellation; direct wait-adapter KeyboardInterrupt tests do not prove the runner contract. Existing real bounded child was reaped; no child leak claimed here.

## O-10 — Viewer physical gestures, reduced motion and storage/focus

Actual Chrome DOM/timer/File integration confirmed F-012/F-013 after using the existing launcher. This is synthetic event acceptance, not OS-native file picker, assistive technology or physical touch.

Use the owned tiny report on supported Chrome/Windows browser. Pause Blink, physically click/pan image, then pinch/Lens tap where available; repeat with prefers-reduced-motion enabled. Pass after P9: stays paused/no image alternation, controls truthful; initially running Blink resumes only after suspension. For P10, create actual same-report conflict JSON, use native file picker under Merge+Keep local then Use imported; pass: preview counts equal exact apply deltas and local data preserved. Test keyboard focus/Inspector escape/return, zoom and storage blocked/quota cases with actual browser settings. Record browser/version/viewport/device/reduced-motion/storage policy and screenshots. No broad accessibility claim follows from DOM ARIA or static CSS alone.

## O-11 — Linux GPU/X11/visible GUI and native HDR capability

Host: compatible Linux NVIDIA driver/Vulkan device for `bash tools/verify_docker_gpu.sh`; Linux X11 desktop for `bash tools/verify_docker_gui.sh`, followed by visible manual launch prescribed by its output/runbook. Use current-SHA owned source/output and generated media; serialize verifiers. Pass: required markers, correct selected Vulkan device/render behavior, installed production tooling absent, real three-source session/frame0/panel/result and owned cleanup; visible playback/seek/interaction/display actually works. Fail: missing markers/wrong device/render/session/leftover processes. Offscreen inside-container success alone is not X11 wrapper/visible pass.

Native F-002 acceptance also requires actual installed libplacebo probe from hostile cwd/PYTHONPATH with marker absent and capability unchanged; local native lacked placebo. Repeat portable startup/isolation on Windows where ._pth mitigates. Local Docker software Vulkan does not establish NVIDIA/native display behavior.

## O-12 — Managed runtime architecture and long-resource proof

Current review passed the local Docker aarch64 gate, actual codec/frame/software-Vulkan/source-provenance and production mount/application. Cached layers were allowed; no cold all-source rebuild is claimed. Docker amd64 and fresh cold provenance/build need their actual architecture/CI context and exactSHA. Run canonical `bash tools/verify_docker_integration.sh` serialized in a disposable checkout/output tree, optionally its documented no-cache build when auditing cold producer inputs; pass requires zero nonpassing outcomes and all production/mount markers.

The separate three-hour streaming RSS/admitted-lag/collector-reaping proof was deliberately not run: no accepted finding concerns those collectors/bounds. Canonical gate excludes the module and native three cases skipped. If that obligation changes, after building the test image use:

```bash
docker compose run --rm --no-deps \
  -e FRAME_COMPARE_CONTINUOUS_ALIGNMENT_RESOURCES=1 \
  --entrypoint python frame-compare-test \
  -m pytest -o cache_dir=/tmp/frame-compare-resource-pytest-cache \
  tests/integration/test_alignment_streaming_resources.py -rsx -s
```

Record actual RSS/lag/child results and skip reasons; pass only the distinct assertions, not simulated collectors. This resource recipe writes only within the disposable container/source outputs; choose owned mounts and do not overlap cache/pruning.

## O-13 — Hosted CI selection, protected release/signing and live services

No remote PR/workflow dispatch, signing, publication, repository-setting mutation or credential-bearing product request is authorized by this review. Later explicit authorization is required.

For F-008, on an authorized test PR change only checkout_source_commit.sh, then only .dockerignore; record exact base/head/files and actual Docker job URL. Pass after correction: job selected and meaningful managed gate executes; fail: absent job. Configuration matching alone does not certify GitHub's hosted execution.

For release: inspect protected environment/branch/ruleset and secret scope without reading values; prove authorized signer can sign and untrusted/unprotected workflow cannot access signer. Bind exact tag/commit/version/channel, draft notes/assets, checksum files, remote bytes and final publication state using existing guarded release procedure. Pass: all guards and byte identities hold and unauthorized access fails; fail: wrong source/artifact/channel, missing gate or accessible signer. Static action pins/validators and unit negatives are supporting, not actual production signing/release proof.

For live slow.pics/webhook/TMDB: use separately authorized dedicated credentials/test collection/receiver and harmless owned media. Verify real navigation/upload schema, report-first decline/order, cleanup/shortcut, webhook uncertain delivery and receiver count, TMDB auth/cache results and redacted diagnostics. Agree bounded request counts and cleanup before execution; distinguish local simulated uncertain delivery from actual receiver observation. Native two live tests skipped, and built-in unauth doctor responses were not live-service acceptance.

## O-14 — Current Windows artifact, GPU/visible interaction and release/legal acceptance

Host/input: physical supported Windows x64, complete authenticated current-SHA portable ZIP, disposable extract/output, actual GPU/display and production signing context only when authorized. Run canonical extracted verifier with its real arguments:

```powershell
pwsh -NoProfile -File tools/windows_portable/verify_extracted_bundle.ps1 `
  -ZipPath <authenticated-zip> -ExtractRoot <owned-empty-extract-root> `
  -DoctorStdoutPath <owned-log-dir>/doctor.stdout.json `
  -DoctorStderrPath <owned-log-dir>/doctor.stderr.txt `
  -ExpectedCommitSha <exact-40-character-source-sha> -CommandTimeoutSeconds 300
```

Record source/ZIP/inventory/signature/requirements/runtime fingerprints, component versions, exact stdout/stderr/exit and recognized GPU skip. Follow current runbook and physical checklist for embedded ._pth/cwd/user-site isolation, plugin loading after Qt, actual generated L-SMASH/tonemap frame, panel entry point/metadata/result refusal, fresh terminal install/PATH/uninstall preservation, matching signed apply/rollback, mismatched fingerprint refusal and exact predecessor migration. Pass only observed obligations; hosted `vulkan_runtime_unavailable` is not physical GPU pass. Visible playback/seek/panel/display remains separate from offscreen construction.

Current corresponding-source/license inventory and publication/legal authorization require maintainer review of actual shipped native binaries/source/provenance and distribution obligations. No legal conclusion or release approval was made. Historical 10-07 supplied Windows artifact/handoff evidence is useful context, not authenticated currentHEAD acceptance. Preserve useful prior installs/data and exact failure evidence; do not silently substitute a metadata fixture or unsigned update for a real signed-runtime obligation.
