---
search:
  exclude: true
---

# Outstanding verification ledger — 2026-10-17

Status: HDR output correction committed on 2026-10-21; Windows UCRT verification
reconciled on 2026-10-22. See the final HDR section for current source, native
evidence, measured performance and the remaining adoption prerequisites.
The earlier MacBook continuation completed on 2026-10-18. Actual Windows-to-MacBook
report transfer, native macOS picker, Merge/Replace/conflict choices and exact
review/image/identity/reload acceptance passed. Acceptance remains OPEN for the
explicit prerequisites in the final disposition table. Visible Windows native
review and the bounded repeated native-console-event observation retain their passes.
The repeated rendering Ctrl+C failure is preserved as a historical observation,
resolved by the separately authorized fix and affected verification below.
This ledger is chronological: interim pending/failed observations retain their
original scope. The final MacBook disposition table supersedes the Windows handoff
table; its checkout is 698d1e76, with unchanged product content since 6739bfb2.
This is the canonical ledger. Supporting
receipts, raw logs, downloads, probes and sidecars are retained under
`generated/verification/2026-10-17/` on Windows and the durable MacBook evidence
directory recorded below, outside scratch. Initial verification made
no product changes; the later authorized Ctrl+C fix and commit/push are recorded
separately. The MacBook continuation changes only this ledger after a safe local
fast-forward. No destructive reset, PR merge,
credential migration, protected dispatch, publication or live product-service
request was performed.

## Source and evidence baseline

Initial checkout was clean, branch `v0.7.0`, HEAD
`104491b5b023b5a666d37bb7ea9d6742b030c749`. `git ls-remote` and GitHub PR metadata
independently agree. PR [138](https://github.com/TJZine/frame-compare/pull/138)
was open against `pre-release` at `35792220ae59d514ed626707340e2a86a7a14d05`;
the then-current PR merge was `b7d64df92eea6500e92f05b2dd233a24297b79e7`. Hosted checkout
logs record that merge SHA. Its tree and local HEAD tree are identical:
`28c1a0ec1fc4f38da27c69e2ef3375261c344c34`. Thus these hosted results apply to
the candidate's exact source content, without pretending their checkout SHA was HEAD.

| Gate | Disposition and exact evidence |
| --- | --- |
| CI | **Satisfied by identified hosted evidence:** [38868462860](https://github.com/TJZine/frame-compare/actions/runs/38868462860). Static checks, import contracts, locked Windows/Ubuntu dependency audits, fresh distribution installation/help/version, real Chrome browser module all successful. Browser: 23 passing symbols, zero skips, including three helper cases and 20 browser-dependent cases. Chrome 155.0.8059.39. |
| Docker | **Satisfied by identified hosted evidence:** [38868462863](https://github.com/TJZine/frame-compare/actions/runs/38868462863), cold canonical gate: 300 passed, zero skips; separate streaming-resource proof: three passed, zero skips. Three-hour sample volume is accelerated, not three-hour wall-clock endurance. Software Vulkan is not NVIDIA hardware proof. |
| Windows unsigned | **Satisfied by identified hosted evidence:** [38868462963](https://github.com/TJZine/frame-compare/actions/runs/38868462963). Full suite, portable build, extracted smoke, unsigned update build/layout/upload successful. Twenty terminated-lock-owner journal-recovery cases cover PS5.1/PS7, apply/rollback and five journal states; no updater/interpreter skips. Do not rerun the suite merely to duplicate this proof. |
| Documentation | **Satisfied by identified hosted evidence:** [38868462811](https://github.com/TJZine/frame-compare/actions/runs/38868462811), strict build/search scope successful; deployment skipped. |
| Signed verification, migration, release | **Blocked by protected prerequisites; skipped, not passed.** Four whole Windows jobs skipped, as did signing, attestation and release-asset steps in the unsigned job. |

Quiet pytest logs suppress numeric totals. Derived CI progress counts are 3,530
passing and 267 skip symbols, with 276 skip-summary items including collection skips;
Windows 3,893 passing and 86 skip symbols, with 87 summary items including collection
skip. These are explicitly derived counts, not emitted pytest totals. CI native,
Windows, media, resource and live capabilities have relevant skips. Windows has
media/browser/live/POSIX skips; direct GPU frame proof reports
`vulkan_runtime_unavailable`; GUI/package panel proof is offscreen. Detailed skip
accounting and full decoded logs are in `hosted/skip-accounting.json` and
`hosted/job-*.log`. Full supporting analysis: `hosted/findings.md`.

| Hosted artifact | ID | Bytes | GitHub artifact ZIP SHA-256 |
| --- | --- | --- | --- |
| Portable | 12032517001 | 422846881 | `a240e18c49dde60b61cbd81930924c9cfd991f3b7d9cac294c167650945fb1b1` |
| Unsigned update | 12033195748 | 698096 | `728c9f39d2845a4c1d74fcb751f2559aeb71c8a77aaf75f2c4b8a8f4abc7572c` |
| Docker evidence | 12032695341 | 465167 | `0dd92a3eb16dc716ad6f6f424623e692834ecb403ad652fce8fd3c9b730ad30d` |

Downloaded portable, unsigned-update and Docker artifact digests match locally. The portable
inner ZIP is 425837437 bytes, SHA-256
`35b6901f10853d67c0751e0bc956aadf3718de23bc94ade0fbc46240bf4a63a5`.
Physical extraction/layout/license/provenance/help/version/doctor passed using a
transparent unchanged prefix of the canonical verifier before its install stage,
exit 0; this is explicitly not another full canonical verifier pass. Receipts:
`hosted/physical-*`, `hosted/portable-download-checksums.json`. Schema 3, version
0.7.0, requirements lock `e9d8f405cc2ea6169e1e8ca1139bf180666f03c2677d58d6e9d2ce629c25a6b8`,
runtime `b47d64de188aab069cf3c3b9d51add6d0b3416c5ee175b4c0646b72436219320`.
The unsigned
inner update is 722994 bytes, SHA-256
`9c2b0fb27c539622285eb007e6b72cd6aa18ac43396f084d94794623cdaab4fa`.
No fixture or unsigned signature is a protected signing pass.

## Prior physical Windows acceptance and refresh scope

**Satisfied by identified prior evidence within its original scope:**
`262f624655ebc35b046c6993ba1c85282b994064`, physical Windows 10 Home build 19045,
PS5.1.19041.7725/PS7.6.4, contributor Python 3.13.7/bundle 3.13.16, RTX 5080
driver 617.14. Retained JUnit proves 399 passed, zero failures/errors/skips in
462.670s. It includes both-shell installation/data preservation, source Move/Leave,
activation recovery, non-ASCII UTF-8 state, installed configuration/render,
fixture-signed real-runtime update/rollback, mismatch refusal and actual GPU frames.
Receipts were inspected and hashed in `reconciliation/prior-evidence-receipts.json`.

Portable ZIP at that source: 425718034 bytes, SHA-256
`7624f1ed9d144edd9679fdb0411e794d32bb0ba5428a6e898b66c34337c70f38`.
These are retained manifest identities, not claims of newly rehashed old archives.
The latest remediation-plan evidence supersedes its earlier failed candidates.

`git diff --quiet 262f6246..HEAD -- tools/windows_portable/manifest.windows-x64.json tools/windows_portable/build_portable.ps1 tools/windows_portable/install* pyproject.toml uv.lock src/frame_compare/render src/frame_compare/vs src/frame_compare/vsview`
returned 0. No native dependency/builder/installer/render-graph change invalidates
all that earlier proof. Current relevant deltas are updater exclusive persistent
lock ownership/recovery, alignment-cache crop identity, upload/cancellation fact
retention, config error narrowing and report cross-tab state. Hosted evidence
already covers the latest updater matrix under both shells.

**Passed fresh physical AppData-helper delivery:** actual hash-verified hosted full-bundle
`install.ps1` installed into isolated AppData, exit 0. The delivered helper matches
the current bundle/source SHA-256
`da3d516d0c9d1e0e648bb6a57338a7e634425c673d4f6b6614bfa6c6dc6abc10`.
Installed `list-backups` passed under PS5.1/PS7, exit 0 each. Real held exclusive
update lock caused refusal, exit 1 each; immediately after release both retries
passed, exit 0, retaining the persistent lock file. Current hosted code-only
update contains 200 application files and no helper/shim payload. Exact commands,
receipt and logs: `local/helper-install/`; user registry PATH raw value/type and
process AppData were restored exactly, isolated install removed. This is new
full-bundle delivery, not predecessor migration or signed apply/recovery proof.

**Remaining physical obligations:** genuine previous-bundle migration,
representative owned/authorized HDR10 and Dolby
Vision output, range/bit-depth and timing/frame properties, old/new index/cache
migration, objective and perceptual comparisons. Generated PQ/BT.2020 AV1 and GPU
proof at 262f retain their narrower claim; they do not establish that media corpus.
No authorized representative Dolby Vision corpus or protected signed predecessor
update was supplied. Code-only updates cannot replace the repaired AppData helper;
full reinstall must use a fresh empty root and preserve user data, never overlay.

## Local native review observations

Environment: this second physical computer is Windows 10 build 19045. Source
runtime Python 3.13.7, real VapourSynth R81/API R4.3, `core.lsmas` required functions
present, PySide6 6.11.2, VSView 0.13.0, vs-placebo 2.0.4, `core.fpng` absent.
`uv run --no-sync frame-compare doctor --json`: exit 0. Native capability probe:
exit 0. Doctor labels this **unmanaged** runtime; PATH FFmpeg is a 2025 custom
build rather than the managed bundle's pinned LGPL binary. Doctor's configured
TMDB-key status is not a live request/authentication pass.

Owned media: 12-second 640×360/24fps testsrc2, H.264 plus PCM sine audio, copied
byte-identically as comparison. The recorded FFmpeg generation exited 0;
`local/media-sha256.json` binds both sources. Work roots are recorded in
`local/run-root.txt`; inputs, configs, indexes, generated sessions, diagnostic
JSON and run records are copied to `local/native-first` and `local/native-second`.
Metadata, upload and report auto-open were disabled; no private media was used.

Command for each separate root:
`uv run --no-sync frame-compare run --root <owned-root> --force-interactive-alignment --skip-metadata --no-upload`,
executed with actual PTY (`sys.stdin/stdout/stderr.isatty()` all true).

1. Production-generated two-source L-SMASH session launched a real desktop window
   titled `VS View`. The accessibility tree exposed the installed alignment panel,
   Reference/Comparison, source controls and whole-set actions. Audio evidence was
   `video_check_inconclusive`, no usable candidate, explicitly NOT APPLIED. The
   whole-set Confirm action was disabled before capture.
2. **Harness failure:** capture reported `FrameArrived timed out` and, after
   activation/recovery, `window capture timed out`. A refreshed accessibility click
   reported `element 52 has no cached bounds`; Tab did not change observed focus.
   Normal-close key injection also left the window listed. No matching-position,
   manual-offset or Keep-current action can be claimed from these observations.
3. The first run subsequently emitted native exception `0x8001010d` and
   `FC-4005` missing result, actual CLI exit **5**. It recorded status `failed`,
   selected frames 0, render/report/publish durations 0. Normal-close injection and
   a later PTY Ctrl+C attempt confound the trigger, so this is **not a Ctrl+C
   reproduction** or an accepted close-without-save result.
4. A fresh separate launch, with no desktop input and no Ctrl+C sent, crashed in
   VSView loading with `0x8001010d`, access violation and child code 3221226525.
   Frame Compare returned **5**, typed `FC-4019`. Full command/trace is retained in
   `local/native-interrupt-transcript.txt` and `.exit.txt`. Despite the filename,
   interruption was **not reached**. This is a demonstrated source-environment
   native launch failure, not proof of a candidate bundle failure or a diagnosed
   product cause. Expectations were not weakened and no product changes were made.

The two source roots have failed run records and no alignment-result/manual-override output,
rendered screenshot or report. Post-run owned-process checks are retained; no
matching owned media/viewer child remained. Original diagnostics/session metadata
remain available. **Visible-native acceptance remains blocked** pending a usable
supported runtime and functioning desktop capture/input: matching capture/full-set
save/close/resume, known zero/nonzero offsets, Keep current, optional/forced
unsaved close, exact authority/evidence/trim/cache observations. Offscreen tests
already passed but do not close this gate.

### Current bundled console cancellation observations

The hash-verified current hosted bundled runtime subsequently decoded the fixtures and
launched native review. It also logged `0x8001010d` native exceptions while still
reaching the waiting state; those diagnostics remain unresolved, and are not a
clean visible-interaction pass. To avoid the PowerShell wrapper's own Ctrl+C
termination hiding the application's exit, the retained evidence-only
`local/console-supervisor.py` launches the real bundled Python CLI with the
launcher's process environment and inherited PTY. It records actual received
console signals and child exit; it does not call `signal.raise_signal`, inject
an application exception, replace a renderer, or change cancellation handlers in
the child. Actual input was `write_stdin` Ctrl+C on this Windows host. The
observer's own handler only records its signals. The outer PowerShell tool can
return 1 when its pipeline stops; that is distinct from the recorded child exit.

Renderer fixtures are nonconstant generated 3840×2160 H.264, 24fps, 288 frames,
100 requested random screenshots per source, metadata/upload/alignment disabled.
An initial 300-frame request was honestly refused, child exit 2 (`FC-1003`);
only disposable config was corrected to the documented 100 maximum. One observer
attempt failed 1 because optional psutil was absent; it was removed from the
evidence observer, with no package installation or product change. Earlier fast
uninterrupted render probes completed (exit 0, 200 images/report); their names
containing `single` do not make them interruption proof. The armed observer then
allowed real signals to be sent while image files demonstrably existed.

| Physical console case | Observed disposition |
| --- | --- |
| Native review, first Ctrl+C | **Passed observed exit/phase/cleanup scope:** `review-observed-supervisor.json` records one actual signal, bundled child exit **130**, failed run, zero selected/rendered frames, no report/review result/manual authority. No matching owned children survived. |
| Native repeated Ctrl+C | **Blocked/unobserved:** two bounded attempts exited 130 after the first signal before a second could be delivered. `review-repeated-observed` was interrupted during startup; it does not establish repeated interruption during review. |
| VapourSynth render, first Ctrl+C | **Passed observed exit/phase/cleanup scope:** `render-vs-single-supervisor.json`, one signal, child **130**, failed record, no later report/publish, preservation sentinel unchanged; pre-signal snapshot had 102 images, cleanup removed incomplete render outputs. |
| FFmpeg render, first Ctrl+C | **Passed observed exit/phase/cleanup scope:** `render-ffmpeg-once-supervisor.json`, one signal, child **130**, failed record, no later report/publish, sentinel unchanged; pre-signal 39 images, final zero after cleanup. |
| FFmpeg render, repeated Ctrl+C | **Passed observed exit/phase/cleanup scope:** `render-ffmpeg-repeated-supervisor.json`, two actual signals 363.514ms apart, child **130**, failed record, no report, sentinel unchanged; pre-signal 77 images, final zero. |
| VapourSynth render, repeated Ctrl+C | **FAILED requested exit-130 acceptance:** `render-vs-interrupt-supervisor.json`, actual signals at 07:59:23.026751Z and 07:59:23.399629Z (372.878ms apart), child **3221225786 / 0xC000013A**. Failed run/no report, sentinel unchanged. Pre-signal 106 images; final 110 partial images remain. No remaining owned child was found. Partial PNG retention is permitted and is not itself a cleanup defect. Cause/OS-versus-Python shutdown boundary unresolved; no confirmed new product regression or speculative fix. |

All interrupted runs retained `status=failed`; their failure record uses generic
`FC-0001/INTERNAL_ERROR`, which is recorded rather than reclassified as a nicer
interruption diagnostic. No manual/alignment result was created. Native original
attempt evidence and diagnostic digest remain in retained session/JSON files.
Current narrower automatic admission assertions are reused; physical file/process
snapshots alone do not observe every internal admitted frame ID or prove that the
second render signal reached the application before its first exit. In the failing
VS case its actual exit does not satisfy the requested 130 expectation.
Current CLI contract lines 745–747 also say a second Ctrl+C keeps its existing
behavior, native work has no guaranteed finite drain deadline, and already-written
PNGs may remain. This does not invent a repeated-signal escalation or PNG cleanup
guarantee. Exact command, PIDs, UTC times, signal
counts/exits, file inventories/hashes and run records are in `local/*supervisor.json`,
`local/*-processes-before.json`, `local/cases/` and `local/case-observations.json`.
`local/owned-processes-final.json` is `[]`. These are console-input physical-host
observations, not a claim of human keyboard or successful visible panel operation.

## Offline report and remaining browser observations

Current hosted Chrome proof is reused. It covers encoded image paths, selected
mode/fit/offset/ARIA/focus behavior, trusted Unicode note editing, two-tab storage
conflicts, stale import rejection and draft retention. Node pointer/reduced-motion
and denied/quota-storage cases are component proof. Neither establishes physical
touch, actual browser storage policy/quota, OS motion settings or native picker.

The user correctly identified this Windows host as the second physical computer
relative to the macOS pilot. However the pilot explicitly states transfer was not
performed, and no UI-downloaded review package matching that report was found in
the repository/retained generated evidence or targeted Downloads/Desktop search.
It is not valid to invent that source export or call two Windows profiles two
machines. **Cross-machine transfer remains blocked by a matching report/assets
and actual UI-exported review from the other machine, or access to it to complete
the export half.**

**Passed narrower actual Windows browser export/relocation/import/reload:**
Brave 155.1.97.59 / Chromium 155.0.8059.85, headless 1440×1000 scale 1, isolated
profiles. Trusted mouse/keyboard editing set a Unicode note and bookmark; actual
Export click downloaded retained JSON. Exact bytes of report/assets/export were
copied to a second local path. Four fresh destination profiles drove the real
Import trigger/file input, Merge/Keep local, Merge/Use imported and Replace.
Import used CDP `DOM.setFileInputFiles`, so no native OS picker claim is made.
Preview deltas, exact notes/bookmarks/ordinals and loaded images/report identity
were checked after Apply and reload. All final stage helpers exited 0. Three
driver/wrapper failures and their corrections are retained, not hidden product
passes. Full actions, assertions, commands, downloaded JSON and screenshots:
`browser/transfer/acceptance.md` and adjacent receipts.

Report ID `report_381ff1102c183e0764f342a2b68bf9d7`, payload 1.3. Downloaded JSON
391 bytes, SHA-256 `850858fbc1c85a4d055a9515ea5fbdae99a7bd7596f67e72ba639aae164031cd`.
Portable cross-machine handoff package: `browser/transfer/transfer-package.zip`,
351229 bytes, SHA-256 `586ab45c45931a62c4bbfb6fafadb47f410e1cb006da519a16b2210b377d6875`.
Profiles were removed; report, assets, exported JSON, screenshots and package
remain. Another local path/profile does not supply the missing machine transfer.
The concrete remaining transfer step can now use this Windows-exported package
on the Mac or another separately identified computer: verify bytes, import with
fresh browser storage through UI, compare exact records/images/identity and reload.

**Passed additional actual-browser observations:** trusted CDP mouse click/pan
with paused Blink retained the active clip across 9×100ms during-drag and
16×100ms after-release samples, with truthful Pause/Resume state. A separate
`--force-prefers-reduced-motion` launch had real `matchMedia(...reduce)=true` and
the same paused behavior; this is browser-preference proof, not an OS setting.
Trusted Escape from the note textarea closed Inspector and returned focus to
`btn-inspector`. Isolated browser profile cookies policy 2 made native localStorage
throw `SecurityError`; real note/bookmark editing retained honest memory-only/
unsaved warning and actual UI Export downloaded the exact state. All final stage
helpers exited 0; profiles removed. Screenshots, commands, event trust/state and
cleanup receipts: `browser/physical-controls/acceptance.md` and adjacent files.
Two bounded Ctrl+Plus attempts per sampled profile changed no browser metrics;
zoom is **unobserved due driving limitation**, not a demonstrated product failure.

**Passed real quota exhaustion/draft export:** a final fresh profile used native
localStorage, bounded 8MiB cumulative ASCII/UTF-8 logical writes and 15 seconds.
It completed in about 1.4 seconds: 47 attempts, 28 accepted, 19 actual
`QuotaExceededError` code 22 results, 5,767,394 submitted logical bytes including
keys, 5,242,442 retained bytes (10,484,884 UTF-16 logical bytes). Trusted note and
bookmark remained exact in memory, persisted review key was null, warning
truthfully said session-only, and actual UI Export downloaded the exact draft.
Storage still existed (`memoryOnly=false`) but saving failed (`unsaved=true`);
no durable-save/reload claim follows from this quota observation.
Task fill keys and profile were removed. `browser/physical-controls/quota-utf8/`
contains commands, result, screenshot, download and cleanup receipt, helper exit 0.
An earlier conservative 8MiB UTF-16-accounted attempt stopped before quota and is
retained as an unobserved bounded attempt, not a failure or a discarded pass.

Still distinct: physical mouse/touch pinch/Lens on compatible hardware, OS motion
settings, actual browser zoom, native picker and cross-machine transfer.
Trusted headless browser input supplies no physical-device or OS-settings claim.

## Protected signing and operational gates

**Preparation passed; execution blocked by explicit prerequisites.** Supporting
`signing/findings.md` provides the concrete ordered dispatch/evidence checklist and
`signing/readbacks.json` live sanitized metadata. Ruleset reads confirm active
protected main/pre-release and App 5338382 bypass only on pre-release, none on
main/archive. Required PR approving-review count is actually 0; this is not an
enforced human approval count. Branch-protection API returned 403; the connector
does not support environment/secrets API families and `gh` is absent. Current
secret scope was unavailable, not successfully empty. No secret values were read.

Maintainer actions, separately authorized:

1. Read protected environment/reviewer/allowed-ref and signing-secret name/scope
   metadata, including repository and organization grants. Confirm windows-ci has
   no signing credential; provision/migrate protected copies only through the
   approved secure runbook. If needed, separately approve one-time migration and
   remove its temporary token/ref permission afterward.
2. Integrate the reviewed candidate into protected pre-release, then resolve and
   review its **then-current exact SHA**. The latest candidate is now
   `6739bfb276390ddefee00e28e61c2d7c2af69377`, still absent from protected
   pre-release `35792220ae59d514ed626707340e2a86a7a14d05`;
   a squash integration changes its SHA.
3. Separately authorize verification-only dispatch and release-candidate approval:
   `gh workflow run windows-portable.yml --repo TJZine/frame-compare --ref pre-release -f operation=verify -f channel=rc -f expected_sha=<then-current-protected-head>`.
4. Retain run URL, workflow/checkout SHA, environment approval, real signing/public
   key match, artifact IDs/digests and downloaded inner ZIP/hash/signature proof.
   After successful protected value proof, authorize removal of legacy repository
   and organization key access, metadata-read back, then run controlled negative
   access in windows-ci and ordinary/no-environment context without printing or
   hashing the secret. Repeat protected proof as necessary for final scope.

Maintenance App variable/private-key-name configuration is **satisfied by prior
metadata**, live bypass scope reconfirmed. App installation permissions, actual
token minting and postpublication pre-release recreation remain **blocked by their
first separately approved operational run and publication/freeze prerequisites**.
No branch recreation or publication solely for a test.

Live slow.pics, webhook receiver-count/uncertain-delivery, and authenticated TMDB
lookup/cache observations remain **blocked by explicit live authorization**,
dedicated credentials/test receiver/owned media and bounded request/cleanup plan.
Newer mocks/local confirmed-upload persistence do not supply real remote receipts.

Linux NVIDIA and Linux X11 wrapper/visible GUI are **outside the current default
release obligation as separate optional profiles**, blocked for their own claims
by compatible Linux GPU/X11 hosts. Windows GPU proof supplies neither profile.
Release publication and legal/corresponding-source approval are outside this task.

## Bounded investigations and older observation accounting

**CQ7:** bounded Node investigation now passed using the existing public Next
button dispatch, fixing only the evidence probe's earlier nonexistent-navigation
gap. Withheld RAF delays retry despite an ordinary timer; rebuild and navigation
reject stale callback/load and cleanup clears cells/RAF. Driver, stdout and exit 0
are retained in `reconciliation/cq7_probe.*`; the initial CRLF marker harness error
exit 1 is retained too. No real browser-managed background suspension was observed.
Disposition: **outside accepted refactor/release-blocker scope; retain separate
owners**. Grid-local scheduling correction is the smaller option if actual-browser
evidence establishes a visible failure. No speculative consolidation.

**CQ14:** current Pillow Lanczos, VS fpng Spline36 and default FFmpeg scale differ
in policy; there is no established universal pixel-equality promise. Actual
Pillow/fpng comparison is **blocked by supported fpng-capable runtime and a defined
equality/disclosure contract**; current real core has no fpng. Disposition:
**outside accepted refactor/release-blocker scope; retain behavior**. Remaining
discriminator is nonconstant owned media/same geometry through both real paths,
unobscured pixel/frame/fact/report-ID comparison, then contract-based disposition.

All historical O-items are reconciled in `reconciliation/findings.md`:

| Item | Final disposition for the historical claim |
| --- | --- |
| O-01 non-ASCII PS5.1 state | Satisfied by identified 262f physical evidence, within recorded direct-shell scope. |
| O-02 source PS5.1 fallback | Satisfied by newer explicit PS7 source-build prerequisite and existing proof; PS5.1 remains supported for bundles. |
| O-03 overlay/retained backup | Outside supported fresh-root reinstall contract; genuine full predecessor migration remains blocked separately. |
| O-04 NTFS first target rename | Outside accepted blocker scope as unconfirmed hypothesis; authentic source-leaf deny-delete lock experiment remains unobserved. |
| O-05 native proof stall | Outside accepted blocker scope as unconfirmed hypothesis; no real plugin stall reproduced. Native crash above is a different observation. |
| O-06 late image loss | Satisfied by newer main-stage error/retry implementation and current browser Blink retry/focus proof for its assertions; no exhaustive physical every-mode claim. |
| O-07 infinite operation timeouts | Satisfied by newer `allow_inf_nan=False` schema and current schema tests; old premise superseded. |
| O-08 response-body budgets | Outside accepted release obligation; no agreed normal budget or demonstrated failure. |
| O-09 actual Ctrl+C | Historical repeated-VS failure is retained and resolved by the separately authorized fix/affected reruns below. First native/VS/FFmpeg, repeated FFmpeg and latest two-real-OS-event native-review exit/cleanup scope passed. Two separate Python callbacks during native review remain unestablished; final table preserves that boundary. |
| O-10 physical/browser settings | Partial prior/current automated proof; remaining physical, picker, cross-machine and settings cases blocked as above. |
| O-11 Linux optional profiles | Outside default release obligation; their separate host-dependent acceptance remains blocked. |
| O-12 Docker/resource | Satisfied by exact-tree hosted Docker and distinct resource job evidence. |
| O-13 hosting/signing/live | Hosting satisfied; signing/live execution blocked separately; no skipped job promoted to pass. |
| O-14 Windows/media/release | Prior physical and current unsigned hosted scope satisfied; remaining native/media/migration/signing claims explicitly blocked; release/legal authorization outside task. |

## Evidence retention and cleanup

The skills, runbook procedures and historical source documents requested by the
task were read. Independent metadata/source investigations ran in parallel;
browser/native sessions each retained one owner. No satisfied full suite was
rerun. Tool/collection errors are retained or described in supporting findings and
are not product passes. The tracked checkout is preserved; only this ledger is an
intended tracked addition. Process readback before cleanup was `[]` for both
the verification root and extracted bundle. Sidecars/configs/diagnostics/run
records, screenshot byte/hash inventories, representative images and original
owned fixtures were copied out before exact-marker scratch cleanup, exit 0.
`local/cleanup.json` records scratch removal. The hash-verified extracted bundle
is deliberately retained uninstalled at the exact path in
`hosted/physical-extraction-receipt.json` for reproducibility, alongside its durable
downloaded ZIP. Browser profiles and the isolated helper installation were removed.
Existing installation/config/media were preserved. The full-bundle installer's
temporary user PATH change was restored byte/type-exactly.

A combined PowerShell cleanup/check command was automatically rejected before
execution. Independent process readback and a smaller exact-literal scratch-only
cleanup succeeded; no permissions were escalated. `local/cleanup-owned.py` and
receipt preserve the safer operation and containment assertions.

Strict ledger documentation build `uv run --no-sync zensical build --clean --strict`
passed, exit 0, “No issues found” (`local/ledger-docs-build.*`). Tracked whitespace
check and explicit new-ledger whitespace/conflict scan passed, exit 0. The
new-file `git diff --no-index --check -- NUL <ledger>` returned 1 for the new-file
difference, with only the normal LF-to-CRLF notice; its actual exit/stderr are
retained rather than labeled exit 0. Final integrity manifest and source/status receipts are
under the same durable evidence root; the private local PATH rollback snapshot is
not intended for publication.

## Follow-up: repeated Ctrl+C during VapourSynth rendering

**Disposition: diagnosed product exit-boundary bug, fixed and affected verification
passed.** Work remains based on HEAD `104491b5b023b5a666d37bb7ea9d6742b030c749`
with the recorded working-tree patch. During that verification no reset,
commit/push, signing or release operation occurred. Exact file hashes/patch, commands, JSONL lifecycle events,
real console sender observations, artifacts and cleanup are under
`generated/verification/2026-10-17/ctrl-c-investigation/`.

### Distinguishing observation and cause

The failure was not a demonstrated frame-admission or child-leak bug. With the
unchanged hosted bundle and actual 4K fixture rendering, an evidence-only child
wrapper recorded CLI exit, thread shutdown and Python atexit boundaries without
changing the child's signal handler. A separate child sent real Win32
`GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0)` events to its owned inherited PTY
console. Both sends checked the application was still running. This supplies real
Windows console-signal/native-runtime proof; it is programmatic event delivery,
not a human keyboard or visible-GUI acceptance claim.

In `finalization-two-signals`, the CLI selected `SystemExit(130)` at
08:14:09.885372Z, the last observed Python atexit callback ran at
08:14:09.889225Z, and the second console event was sent at
08:14:09.913360Z while the child was still active. The final process exit became
**3221225786 / 0xC000013A**. In the distinguishing `active-two-signals` control,
both events were sent while the CLI was active, about 11.5ms apart, and exit was
**130**. The original first-interrupt-only boundary probe also exited 130.

The exact bundled CPython 3.13.16 source resets callable SIGINT handlers before
garbage collection/module destruction; it preserves `SIG_IGN`. Native VS teardown
leaves time for a second event after Python has selected the correct exit. Source
and SHA receipts are retained in `cpython-3.13.16/`; relevant upstream owners are
[CPython lifecycle](https://github.com/python/cpython/blob/v3.13.16/Python/pylifecycle.c)
and [signal finalization](https://github.com/python/cpython/blob/v3.13.16/Modules/signalmodule.c).
This identifies the application/process boundary; no native debugger claim about
the precise instruction at signal delivery is made.

### Correction and ownership

The new standalone `frame_compare.cli.entry:console_main` catches the selected
Windows `SystemExit(130)` only after the reusable Typer application unwinds. If the
handler is still Python's default, it sets `SIG_IGN` before re-raising that same
exit. This survives CPython signal finalization and prevents a later event from
replacing 130. It does not suppress a second interrupt while rendering/draining,
bypass native/resource cleanup, change other exit codes, or replace a custom
caller-owned handler. The reusable `app` and existing `main(ctx)` Typer callback
retain their policies. Both the packaged console-script metadata and module
entrypoint now use `console_main`; ownership docs and the CLI contract agree.

### Affected verification only

| Evidence | Result and boundary |
| --- | --- |
| Corrected actual native render, late-finalization second event | **Passed:** `corrected-finalization-supervisor.json`, two real console events; CLI selected 130 with SIG_IGN; Python atexit completed; second event was sent while still active; final process **130**. Source import is explicitly the changed checkout, using the unchanged supported bundle's Python/DLLs/plugins. This is not a rebuilt full-portable artifact claim. |
| Corrected actual native render, second event during active CLI | **Passed:** `corrected-active-supervisor.json`, two real events about 11ms apart before CLI unwound; final process **130**. Existing active repeated-interrupt behavior retained. |
| Run artifacts/ownership | Both corrected runs recorded `failed`, no report or new alignment/manual authority; preservation sentinel matched. No matching owned process remained. `observations.json`, per-case TOML/JSON sidecars and `cleanup.json` retained. Allowed partial PNGs are not recategorized as a failure. |
| Focused regression/cancellation/CLI-contract selection | **26 passed, 0 failed/errors/skipped**, 12.188s. `final-focused-results.xml` and `.log/.exit.txt`. Includes five isolated subprocess cases exercising actual shutdown SIGINT with standalone interrupted/normal/error exits, reusable app and custom handler ownership, plus affected existing first-signal/cancellation and CLI documentation checks. These component fixtures do not replace the native controls above. |
| Targeted static checks | Ruff lint/format, Pyright (0 errors/warnings), medium-severity Bandit on changed CLI source and whitespace check all exit **0**; exact argv/results in `static-results.json`. No renderer implementation changed. |
| Distribution entrypoint | Wheel/sdist build, repository distribution verifier, fresh environment installation from locked requirements, installed help/version and neutral-cwd module-origin/entrypoint checks all **passed**. Installed code resolved inside the fresh venv and metadata to `entry:console_main`. Wheel 728401 bytes, SHA-256 `9aa03cade1626c11fb2ce98a34c1fa73b0a3d4309d49dd2864b8ce51babcdf69`; sdist 4826529 bytes, `17bcb0f6b91e30f4ec278d2268a74789099f6eee2c72cc97a162b70d13955d09`. Full commands/results: `distribution-receipt.json`. |
| Independent review | Initial duplicate `main` declaration was found by review/static checks and corrected to `console_main`; final read-only review found no actionable issue. Reviewer performed no competing runtime sessions. |

The exact pytest selection was:

```text
uv run --no-sync pytest -q -rs tests/cli/test_standalone_exit.py tests/orchestration/test_execute_run_lifecycle.py tests/test_cli_contract_docs.py -k "shutdown_signal or first_sigint or interrupt or cancellation or contract" --junitxml generated/verification/2026-10-17/ctrl-c-investigation/final-focused-results.xml
```

Retained non-product failures: the initial offline dependency install exited 1
because three locked wheels were absent from cache; retrying only installation
with normal index access and the same lock export passed. The already-built
artifacts were reused. An initial cleanup assertion noticed that an old child PID
had been reused by an unrelated Node process; it refused without deleting anything.
Cleanup then matched the unique owned command paths, found no survivors and
removed only marker/containment-checked scratch plus the fresh distribution venv.
No unrelated process was stopped. Original bundle/shared caches were preserved.

The prior 0xC000013A observation remains in the historical table; its requested
exit-130 gate is now **satisfied for the fixed working-tree source by the
distinguishing native rerun**. Other blocked acceptance items are unchanged.
Per the user's instruction, no unrelated full native, Docker, Windows, browser,
dependency-audit, signing or release suite/action was rerun. Hosted results above
retain their original exact-source scope and are not relabeled as tests of this
then-uncommitted correction or a new full portable build.

## Commit and PR handoff, 2026-10-17

The subsequent maintainer instruction authorizes committing/pushing the reviewed
fix and this ledger to `v0.7.0`, updating PR #138 and inspecting resulting CI.
Signing and release actions remain expressly excluded.

Implementation commit: **`af590b58e6117ca08bacef0e7f02d25c89dd1970`**
(`fix(cli): preserve interrupted Windows exit during native teardown`). It contains
the tested CLI source, console-script metadata, five subprocess regression cases
and corresponding ownership/contract documentation. This ledger follows in a
documentation-only commit; it changes none of that tested application content.
The push must be a normal fast-forward to `refs/heads/v0.7.0`, preserving the base
and earlier work. Its final exact head and actual PR merge SHA must be read back
from GitHub; neither is inferred from the implementation commit alone.

Resulting hosted run/job/skip/artifact receipts are retained locally under
`generated/verification/2026-10-17/post-push-ci/` and summarized on
[PR #138](https://github.com/TJZine/frame-compare/pull/138). A new hosted pass is
claimed only after inspecting its actual result. The earlier run links above
remain historical evidence. Raw local diagnostics, disposable-media files,
package ZIPs, private PATH rollback snapshot and caches are intentionally outside
the commit; their identities and claim boundaries are recorded here. No signed
dispatch, migration, publication, merge or protected-branch operation is authorized.

## Visible native alignment continuation at 6739bfb2

The subsequent verification-only instruction resumes outstanding acceptance,
starting with visible native alignment. No signing/release action or product
change is authorized by this continuation. Initial checkout and remote branch
both remain `6739bfb276390ddefee00e28e61c2d7c2af69377`, with clean tracked state;
PR merge remains `6d9200e03b1b8808744e985681ff6be66df9080d`. The four newer
post-push hosted passes and their explicit skips remain reusable as recorded on
PR #138 and in `generated/verification/2026-10-17/post-push-ci/`.

New supporting receipts are under
`generated/verification/2026-10-17/native-visible/`. Disposable roots and exact
commands are recorded in `run.json` and the per-command/process JSON files.
Managed Python 3.13.16, VS R81/API 4.3, PySide6 6.11.2, VSView 0.13.0 and runtime
fingerprint `b47d64de188aab069cf3c3b9d51add6d0b3416c5ee175b4c0646b72436219320`
reuse the previously hash-verified extracted bundle, without installing it.
Doctor and actual `core.lsmas.LWLibavSource` frame-24 decode both exited 0.

The first disposable fixture command failed because the managed LGPL FFmpeg has
no `libx264` encoder; its command, stderr and exit are retained under
`prepare-attempt1/`. Lossless FFV1 generation then exited 0. The lineup contains
the existing owned 288-frame, 640×360/24fps source, an identical comparison, and
a 276-frame comparison starting 0.5 seconds later. Matching source positions
therefore include reference/comparison1 frame 24 and comparison2 frame 12.
No private media or live service request is involved.

An evidence-driver import assumption was corrected: embedded `python313._pth`
ignores `PYTHONPATH`, so the first capture case actually uses the extracted
bundle source, rather than the initially intended checkout overlay. The capability
receipt exposes its exact import path. `source-equivalence.json` proves 184 Python
files identical to the current checkout; only `cli/entry.py` differs. Thus native
alignment owners are identical, but this first launch must not be called a test
of the corrected standalone Ctrl+C entry boundary. Later driver invocations
explicitly insert current checkout source for the parent CLI.

The actual PTY has stdin/stdout/stderr all true. Production generated the
three-output session and retained original `video_check_inconclusive` evidence
for both comparisons, with no usable audio candidate and no automatic authority.
The CLI is waiting for its owned viewer. Windows computer-use inventory did not
expose a targetable VSView window; the user explicitly confirmed **VSView is
visible and responsive**. This is an automation-observation gap, not a diagnosed
native launch failure. The prior native crash observations remain historical
failures; they are not erased by this newer launch.

`capture-before-interaction/` retains initial session/config/diagnostic files and
hashes before review choices. Matching capture, whole-set Save, actual close/resume,
known offsets, Keep current and optional/forced unsaved close are still **pending
visible observation**. No new visible acceptance pass is claimed yet. The active
owned viewer is intentionally retained for the next user-assisted screenshot and
review action; final sidecar, authority, trim/cache and cleanup results remain to
be appended here after those actions.

The user's subsequent two screenshots are retained as `user-initial-panel.png`
and `user-initial-window.png`, with SHA-256 receipts. They show the actual visible
three-output session, rendered Comparison 2 at frame 0, both no-usable-candidate
warnings explicitly NOT APPLIED, 1/3 positions captured, and the whole-set Confirm
button disabled. This establishes visible initial panel/rendering behavior; it
does not yet establish a saved decision or resumed parent execution. A fresh
automation inventory still does not expose a targetable VSView window.

The next user screenshot, `user-capture-ready.png`, shows unlinked playheads and
**3/3 positions captured — ready to confirm**: reference frame 24, Comparison 1
frame 24 with raw offset +0, and Comparison 2 frame 12 with raw offset +12 and
the reference-trim preview. Confirm is enabled. A separate real L-SMASH decode
of those exact three source frames exited 0 and produced identical SHA-256
hashes for all three YUV planes (`matching-source-frames.*`). This establishes
the matching-position capture and complete-set readiness path, including zero
and nonzero previews, before any confirmation. `capture-ready-observation.json`
records screenshot hash, process state and the still-absent result/override/run
completion artifacts. Save, close/resume and resulting authority remain pending.

The initial evidence supervisor's 20-minute wait limit expired during the
user-assisted positioning. `capture-process.json` honestly records this timeout
and no child exit code; it did not terminate the application. The same CLI PID
8652 (creation time and command rechecked) and viewer PID 7696 remained alive and
responsive, with no saved result or completed run record. Before confirmation,
a separate passive Win32 process-handle observer was attached to PID 8652 to
retain its eventual actual exit status. It only queries the held process handle;
it sends no input/signals and changes no application policy. Its receipt is
`capture-passive-exit-observer.json`. This collection timeout is not classified
as an application failure. Subsequent user-assisted case supervisors allow a
longer bounded wait.

**Visible whole-set Save passed its pre-close boundary.** The next user screenshot
(`user-capture-saved-open.png`) shows **Alignment choices saved**, **Close VSView
to resume Frame Compare**, manually confirmed +0/+12, the retained captured
24/24/12 positions and disabled saved actions. Exactly one schema-1 sibling result
was written for session `4ed2ac74bfb342c7a1b7a2583be2ee97`, with ordered confirmed
decisions `reference:comparison1` (24,24) and `reference:comparison2` (24,12).
Its SHA-256 is `6c33566a35c95ea8dcb1bdff5998bc9169614e213786c77d98faa880b21089bc`.
The current production result reader validated session identity, complete order
and raw-frame bounds, exit 0 (`capture-saved-open-validation.json`). Both initial
diagnostic files remain byte-identical; no manual overrides, completed run record
or rendered PNG exists yet, while both original processes remain alive. This
demonstrates Save persists a session-bound choice but does not resume parent
execution before the viewer closes. Actual close/resume, final applied authority,
trim/cache effects and cleanup are the next pending observations.

**Actual user close/resume passed the observed execution boundary.** After the
user closed the whole viewer and reported `closed`, the passive held-handle
observer recorded CLI PID 8652 exit **0** at `2026-10-17T09:17:06.031001Z`.
The transcript reports acceptance of both confirmed pairs, offset +0 with
reference/comparison1 trims 12..287/12..287, and offset +12 with
reference/comparison2 trims 12..287/0..275. It then completes one aligned frame
(71), writes three PNGs and `report.html`, and reports no metadata/publication.
The original supervisor's exit 1 belongs to its documented wait-limit exception,
not to the application: the passive process receipt separately proves actual CLI
exit 0. Original CLI/viewer process IDs are no longer present. Complete non-media
run artifacts and hashes are retained in `capture-after-close-artifacts/` and
`capture-after-close-inventory.json`; owned fixtures are retained once under
`fixtures/`. Detailed final authority/original-evidence/cache inspection is being
reconciled against these retained outputs.

The separate `known-offsets` case now runs with a fresh disposable generated
directory, actual TTY and explicit current-checkout parent source bootstrap.
Its doctor and source-provenance preflight both exited 0; the latter resolves
`C:\Software\video\frame-compare\src\frame_compare\cli\entry.py` with SHA-256
`210e50e13bf5c1120c7e497612e1d3bdaa4cf020171802382ff92ba90acaa93d`.
Its production-generated three-output session is waiting for user review;
`known-offsets-before-interaction-*` preserves the initially absent sidecar,
manual override, completed run and PNGs. This next case exercises signed numeric
entry deliberately; arbitrary acceptance input values are not an accuracy claim
about the fixture's real +0/+12 correspondence.

**Capture final authority/evidence/trim/cache audit passed.** The read-only
`capture-authority-audit/receipt.md` and `result.json` retain 18 artifact predicates,
copied outputs and hashes. Both original decisions were **unavailable**, not
provisional; their complete attempts and canonical digests are unchanged after
confirmation. Final authority is `interactive_confirmed_this_run`, applied at
0/+12, with an explicit zero manual override in version "2". The complete shared
reuse set has two `interactive_confirmed` entries and no `computed_result`.
The completed one-frame/three-source run has zero warnings. Report aligned frame
71 maps to raw source frames 83/83/71, consistent with global trim starts 12/12/0,
common length 276 and inclusive ends 287/287/275. All three 640×360 PNGs have
identical pixels. Inputs and preservation sentinel are unchanged; no matching
owned CLI/viewer/native process remains. This closes the first visible
capture/save/close/resume case in its documented source/runtime scope. It does
not add native provisional-original coverage; existing automated authority
evidence retains that separate scope.

**Known-offset Save passed its pre-close boundary.** The user's next screenshot
(`user-known-offsets-saved-open.png`) shows input basis **Known offsets**, entered
+4/-3, corresponding manually confirmed offsets, saved status, disabled controls
and the close-to-resume message. The current production reader validated session
`1130ce05432241adbde18afa85f760ea` and complete ordered canonical frame pairs
(4,0)/(0,3), exit 0. Sidecar SHA-256:
`4d60dba43e1b0180553a44befd415b47fe2bf8522b92c224f71b0dfc6556a62d`.
`known-offsets-saved-open-validation.json` and the saved-open artifact snapshot
also show unchanged initial diagnostics, no manual overrides, no completed run
and zero PNGs while the viewer is still open. Known-offset close/resume and
final normalized trims/persistence remain pending.

The user then closed the known-offset viewer. Its current-checkout CLI completed
with exit **0**, independently recorded by the 2-hour supervisor and normal PTY
exit (`known-offsets-process.json`, `known-offsets-complete-transcript.txt`). The
transcript confirms manually applied +4/-3 and normalized ranges reference
4..272, Comparison 1 0..268, Comparison 2 7..275, aligned frame 79, three PNGs
and a completed report. Its after-close artifacts are archived and a read-only
authority/cache/original-attempt audit is being reconciled against those outputs.

The separate fresh `keep-current` case is now waiting in its production-generated
three-source session. Doctor/source-provenance preflights exited 0, all TTY flags
are true, and `keep-current-before-interaction-*` records no result, override,
completed record or image. Both source attempts are unresolved/unavailable and
NOT APPLIED; this case targets preserving that absence of authority when the
user chooses Keep current. Existing automated valid-zero/provisional authority
observations retain their own scope, rather than being relabeled as physical
coverage by this fresh-root case.

**Known-offset final audit passed.**
`known-offsets-authority-audit/receipt.md` and `result.json` retain 16 read-only
artifact predicates. The complete +4/-3 manual-v2 and shared interactive cache
authority matches the UI result, with no `computed_result`. Both unavailable
original attempts and canonical digests remain unchanged. Report aligned frame
79 maps to source frames 83/79/86, consistent with starts 4/0/7 and common length
269; inclusive ends are 272/268/275. Three PNGs are readable 640×360 outputs;
pixel equality is intentionally not expected for these deliberately incorrect
alignment input values. The completed run has zero warnings and no upload.
Inputs, config and sentinel are unchanged; no matching owned native child remains.

**First Keep current attempt: visible Save passed; close/resume unverified after
collector timeout.** The user's screenshot (`user-keep-current-saved-open.png`)
shows saved choices and both comparisons explicitly unresolved, with no accepted
alignment. The actual schema-1 sidecar for session
`4b7ee8467e5a487495017d58cfd7e62b` contains only the complete ordered pair of
`keep_current` actions, no frame/offset fields. The current production reader
accepted it; SHA-256
`229889c1ed1938137070dd6c49bda3a74bbdc8735e4bd6436ff70988729d2882`.
Both diagnostic files remain byte-identical to the initial snapshots, and no
manual override, completed run record or PNG exists. The supervisor reached its
7200-second wait limit at `2026-10-17T11:31:54.702856Z`; the sidecar was written
later at `2026-10-17T18:13:55.3214451Z`. When inspecting the user's response, the
collector's outer status was 1 from that timeout, and no original CLI/viewer
process remained. There is no captured actual CLI exit status or resumed run.
This is a failed/expired collection boundary, not a demonstrated product defect
or accepted close/resume. Raw transcript, file times, screenshot, validation and
artifacts are retained. The previous `after-close` snapshot name is merely its
collection stage; its absent completion artifacts do not establish a clean close.

Only this invalidated lifecycle case is retried as `keep-current-retry`, in a
new disposable root with the same owned media/config and no initial authority.
The source/remote head remains 6739bfb2; only this ledger is modified. Doctor and
current-source preflights exited 0, actual TTY flags are true, and the generated
session is waiting for user input. The evidence supervisor now allows a bounded
24-hour wait; a separate read-only held-handle observer records both actual CLI
and viewer exits, without injecting signals or changing application policy.
No previously satisfied capture, known-offset, full-suite or hosted gate is rerun.

**Retry observed normal viewer close with no result; action clarification pending.**
After the user reported `closed`, the held-handle observer recorded viewer PID
23872 exit **0** and current-checkout CLI PID 17536 exit **5** at approximately
`2026-10-17T18:20:18Z`. The typed CLI diagnostic was **FC-4005**, “Interactive
alignment did not return a valid VSView review result: alignment review result is
missing.” Its recorded run is failed; no review sidecar, manual override or PNG
exists. Complete raw transcript, actual process statuses and archived run files
are retained under `keep-current-retry-*`. A new confirmation question asks
whether this retry actually showed saved status before closing. Until answered,
this is **not** a Keep current pass or a diagnosed Save defect. It establishes
the missing-result fail-closed behavior after a normal viewer exit; whether it
also satisfies the intended human close-without-save case depends on the actual
UI action. No expectation is weakened and no product code is changed.

The independent read-only `keep-current-retry-authority-audit/receipt.md` and
`result.json` confirm 12 artifact predicates: both initial diagnostics remain
byte-identical, including unavailable attempts and recomputed original digests;
their outcome is pending and authority remains absent. No result, manual/shared
alignment cache, PNG or report was created. The failed record selected zero frames
and has zero render/report/publish durations, with no upload. Media, config and
sentinel hashes are unchanged, and all matching owned native processes are gone.
This completes feasible artifact/cleanup inspection while the UI-action
clarification remains pending; it does not settle that action by inference.

**User clarification resolves the apparent Save contradiction.** The user first
recalled seeing saved status, then clarified that they assumed the reopened
window was the same earlier saved window, and requested repeating the last case.
The earlier saved-status observation therefore does not establish Save in retry
session `8567fc57d36c4632b4fcf86442013ca8`. The observed normal viewer exit,
missing sidecar and forced exit 5 remain valid fail-closed evidence; there is no
confirmed Save defect. The confusing session handoff is recorded rather than
silently converting an instruction into an observed click. The prior
`keep-current-retry-authority-audit/` action-pending wording is historical,
superseded by this clarification.

The user explicitly authorized repeating Keep current. A fresh
`keep-current-check` root now uses distinct `KEEP_CHECK_reference.mkv`,
`KEEP_CHECK_comparison1.mkv` and `KEEP_CHECK_comparison2.mkv` names so its visible
lineup identifies the new case. Media bytes/config behavior are otherwise the
same owned fixtures. Doctor and exact checkout-source preflights passed; the
actual TTY-generated three-output session is waiting with no initial result,
manual override, completed record or PNG. Its 24-hour collector and separate held
CLI/viewer handles are active. The next step deliberately holds the viewer open
after Save for immediate file validation before a separate close instruction.

**Distinct KEEP_CHECK Save passed while viewer remains open.** The user's next
screenshot (`user-keep-current-check-saved-open.png`) visibly identifies all
three KEEP CHECK sources, saved choices, disabled controls, and both comparisons
explicitly unresolved with no accepted alignment. The actual sibling sidecar for
session `b1ba57ca08944c6ba172f5cbda6fa5e1` exists and the current production reader
accepted its complete ordered `keep_current` actions for
`KEEP_CHECK_reference:KEEP_CHECK_comparison1` and
`KEEP_CHECK_reference:KEEP_CHECK_comparison2`; neither contains frame/offset
authority. SHA-256:
`ec457b6451fe9603781844a163775bd2a33e5103d1a239a9cb1ce76834951158`.
`keep-current-check-saved-open-validation.json` records exit-0 validation,
unchanged initial diagnostics, no manual overrides, no completed run and zero
PNGs. The held-handle observer has not observed an exit for either original
CLI/viewer process. Thus the new visible Save and actual file are established
together; actual close/resume and final no-authority/cache behavior remain the
next pending observations. No product fix or speculative consolidation was made.

**KEEP_CHECK close/resume and final audit passed.** User close was followed by
viewer PID 13764 exit **0** and CLI PID 5808 exit **0**, recorded by both the
normal supervisor and held process handles. The run accepted zero confirmed
pairs and kept both comparisons unresolved; it completed with the two expected
honest alignment warnings and no upload. The read-only
`keep-current-check-authority-audit/receipt.md` and `result.json` confirm 14
artifact predicates: the exact complete keep-current sidecar is retained;
original unavailable attempts and canonical digests are unchanged; final outcome
is `keep_current`, authority `none`, `applied=false`, and all offset/frame fields
remain null. No manual override or shared alignment cache was created. Report
frame 83 maps to raw 83/83/83 with inferred starts 0/0/0 in best-effort rendering;
all three PNGs are readable 640×360, without an aligned-pixel-equality claim.
Inputs, config and sentinel are unchanged; no matching owned native child remains.
This proves Keep current with absent initial authority; retention of pre-existing
accepted offsets/provisional behavior keeps its identified automated/prior scope.

The forced missing-result obligation is already observed in
`keep-current-retry`: normal viewer exit 0, typed FC-4005/CLI exit 5, zero selected
or rendered frames and no unintended authority/persistence. The user's clarified
old-window assumption means it is not a confirmed Save failure. That exact
fail-closed guard need not be rerun solely to give its directory a different name.

The distinct `optional-unsaved-check` case now waits in a new production session
whose source names begin `OPTIONAL_CLOSE`. It omits
`--force-interactive-alignment`; the run plan explicitly says audio then VSView
review. Doctor/current-source preflights passed and actual TTY flags are true.
The pre-action snapshot contains no sidecar/manual override/completed run/PNG.
Its CLI/viewer process handles are held separately. The intended next action is
to close the whole viewer without choosing Confirm or Keep current, then verify
optional retention/continuation rather than the forced refusal above.

**OPTIONAL_CLOSE unsaved close/resume passed.** The user reported closing that
distinct viewer without Confirm or Keep. Held handles recorded viewer PID 22932
exit **0** at `2026-10-17T18:32:05.877785Z` and current-checkout CLI PID 29472
exit **0** at `18:32:06.279426Z`. The completed run honestly retains two
unresolved-alignment warnings, one selected frame, three readable 640×360 PNGs
and no upload. No result sidecar, manual override or shared alignment cache was
created. Final authority remains `none`, `applied=false`, offset/source frames
null; both unavailable original attempts and canonical digests are unchanged.
Report `report_f86b247b2dbed51288634d4fb7685b7c` maps reference frame 83 to raw
83/83/83 with starts 0/0/0, best-effort rather than an aligned-image claim.
The exact diagnostic outcome is **`rejected_result`**, the current optional
missing-sidecar validation path; `no_result` belongs to launch-disabled/nonTTY
paths. No expectation was changed to accommodate this token. The independent
read-only `optional-unsaved-check-authority-audit/receipt.md` and `result.json`
passed 13 artifact predicates, exit 0, including input/config/sentinel preservation
and no remaining owned native process. Before/after files, actual exit observations
and complete transcript remain under `native-visible/optional-unsaved-check-*`.

### Final repeated native-review console-event observation

The remaining native repeated-interruption obligation used actual Windows
`GenerateConsoleCtrlEvent(CTRL_C_EVENT,0)` in a dedicated owned console with
actual stdin/stdout/stderr TTYs and a production-generated three-source review.
The evidence observer records lifecycle boundaries without replacing product
signal handling or delaying product cleanup. The console guard refuses unknown
participants; no unrelated terminal or existing viewer was targeted.

**Attempt 1 failed its harness guard before sending any event.** The evidence
interpreter's venv redirector introduced additional proxy PIDs; sender events
and supervisor signals are both empty. The guard refusal is retained in
`cancel-check/attempt1/`. Later bounded owned cleanup ended CLI/viewer with 1;
those exits are not product Ctrl+C results. Only the evidence launcher was
corrected to use its resolved base interpreter. No guard expectation was weakened.

**Attempt 2 passed the bounded two-real-OS-event exit/cleanup scope.** Fresh session
`063765aba849444cb82b0d5590ed62c6` used current checkout `entry.console_main`
at source 6739bfb2, the unchanged managed runtime and byte-identical native
alignment child. Doctor exited 0. Before input, the real VS View child PID 7184
had a responding window and was owned by CLI PID 2556. Console membership was
exactly the owned supervisor 39424, CLI 2556, viewer 7184 and sender 24000.

| Boundary | Actual observation |
| --- | --- |
| First OS event | Successful at `2026-10-17T18:35:53.876260Z`; CLI and viewer both STILL_ACTIVE (259). |
| Second OS event | Successful at `18:35:53.897802Z`, **21.5469 ms** later; CLI still 259, viewer already exit 1. |
| CLI unwind | `18:35:53.997310Z`, after both events, `SystemExit(130)` with the standalone teardown handler now SIG_IGN. |
| Final processes | CLI **130**, viewer **1**, sender **0**, supervisor **0**; no deadline cleanup in this attempt. |

The supervisor recorded **one Python SIGINT callback**. Closely spaced console
events can coalesce: this proves two successful real OS events while the CLI was
alive before unwind, not two separately executed Python callbacks, physical human
keystrokes, every repeat timing, or a still-live viewer at the second event.
Existing first-native and rendering interruption evidence retains its separate
scope; no satisfied case was repeated merely to enlarge a test count.

The actual failed run record has selected frame count 0, render/report/publish
timings 0 and no upload. Its recorded code is **FC-0001 INTERNAL_ERROR**, preserved
exactly; overall process exit **130** is a separate observation. No dedicated
cancellation-diagnostic claim is made. No sidecar, manual/shared alignment cache,
PNG or report exists. Both diagnostic outcomes remain pending with no authority;
original unavailable attempts have valid recomputed canonical digests and match
the earlier production script's retained audio projection after its documented
per-chunk-row omission. **No full pre-signal diagnostic-byte snapshot exists**;
canonical consistency is not promoted to temporal equality of omitted rows.
Input/config/sentinel hashes are unchanged. Fresh scoped process readback found
no owned participants from either attempt and no commands referring to the case.

Exact invocations, doctor, actual event membership/timestamps/statuses and lifecycle
JSONL are under `cancel-check/attempt2/`; the independent read-only
`cancel-check/acceptance-audit/receipt.md` and `result.json` passed 15 artifact
predicates, exit 0. The post-event case snapshot is explicitly named
`review-repeated-check-probe-observation-*`, not a pre-signal snapshot.

### Final baseline, disposition and cleanup

Final local and remote readbacks still agree on branch/PR head
**`6739bfb276390ddefee00e28e61c2d7c2af69377`**, actual PR merge
**`6d9200e03b1b8808744e985681ff6be66df9080d`**, and protected base
**`35792220ae59d514ed626707340e2a86a7a14d05`**. Head and tested merge share tree
**`c42dd46936a14c2029839893ec29f133934b0a9f`**. The previously inspected automatic
attempt-1 runs remain valid; native verification changed no product source:

| Automated gate | Reused current-head evidence and claim boundary |
| --- | --- |
| CI | [39017432736](https://github.com/TJZine/frame-compare/actions/runs/39017432736): ten successful jobs; derived 3,535 passing progress symbols, 276 skip-summary items including nine collection skips. Real browser 23 passed/zero skips, fresh distribution install, static/import checks and dependency audits passed. Derived counts are not emitted pytest totals. |
| Docker | [39017432739](https://github.com/TJZine/frame-compare/actions/runs/39017432739): 300 passed/zero skips plus separate three streaming-resource cases passed/zero skips. |
| Windows unsigned | [39017432807](https://github.com/TJZine/frame-compare/actions/runs/39017432807): derived 3,898 passing symbols, 87 skip-summary items including one collection skip. New five standalone-exit cases and latest updater lock/recovery under PS5.1/7 ran without relevant skips. Full/extracted portable and unsigned update packaging passed. Hosted GUI is offscreen; GPU proof skipped for unavailable Vulkan. |
| Documentation | [39017432765](https://github.com/TJZine/frame-compare/actions/runs/39017432765): strict build/search passed; deployment skipped. |
| Protected jobs | Four whole Windows signing-validation/verification/migration/release jobs and seven related unsigned-build steps were skipped, not passed. No protected dispatch or publication occurred. |

Current-run artifact identities below are GitHub API/upload digests; these new
archives were not downloaded and locally rehashed. Prior downloaded archives and
their local hashes remain separate evidence. Complete logs, skip lists, jobs and
readbacks are under `post-push-ci/`, including `inspection-receipt.md` and
`windows/findings.md`.

| Artifact | ID | Bytes | GitHub ZIP SHA-256 |
| --- | --- | --- | --- |
| Docker evidence | 12095945385 | 465164 | `6da4799495b484c37677c0017b3c2ed99501858d25d5060f42fd379fa85a5056` |
| Windows portable | 12095666834 | 422846700 | `ae7d44555054da0b9c7db3c653d718dbb979e010018a43a945ffc41720bebe60` |
| Windows unsigned update | 12094948978 | 698437 | `0c339c3f021175cbe749981ddbc1907cf34b4b145690b4906d04faad3b335223` |

The following is the Windows handoff disposition at 6739bfb2, retained as historical
evidence and superseded by the final MacBook disposition below. A pass is
limited to its named source/environment/path; automated, human-visible native,
physical-host and protected-signing claims remain distinct.

| Obligation | Final disposition and remaining distinguishing evidence/prerequisite |
| --- | --- |
| Actual checkout, remote, hosted run/artifact/skip baseline | **Passed / satisfied by identified prior evidence.** Current refs/tree and newer four automatic runs above; older 104491b5 runs retain their historical scope. No reset or redundant full suite. |
| Offline actual UI export/import, Merge/Replace/conflicts, identity/images/exact review state and reload in isolated storage on Windows | **Satisfied by identified prior evidence**, `browser/transfer/` and `browser/physical-controls/`; the retained UI download and input/action/result receipts delimit this single-host proof. |
| Actual cross-machine report/assets/review transfer | **Blocked** by access to the matching first-machine report/assets/UI-exported review, or an identified receiving machine/person for the ready outbound package. This Windows host is the second physical computer; no matching first-machine artifact was found. Two profiles do not supply transfer. Ready package SHA-256 `586ab45c45931a62c4bbfb6fafadb47f410e1cb006da519a16b2210b377d6875`, report `report_381ff1102c183e0764f342a2b68bf9d7`, retained review JSON SHA-256 `850858fbc1c85a4d055a9515ea5fbdae99a7bd7596f67e72ba639aae164031cd`; receiving fresh-storage UI import, image/state/reload comparison still required. |
| Browser focus/storage/gesture/reduced-motion reconciliation | **Satisfied by identified prior evidence** for hosted browser focus/retry and the recorded denied/quota/UTF-8 storage/browser-control assertions. **Blocked** for remaining physical mouse/touch pinch/Lens, OS reduced-motion/browser zoom and native picker observations by compatible device/settings interaction. Trusted headless input is not physical-device proof. |
| Supported native decoder/doctor/actual L-SMASH | **Passed**, managed Windows runtime fingerprint above, real frame decode and production three-source sessions; no native/offscreen substitution. |
| Visible matching-position whole-set capture, Save, close/resume | **Passed**, human screenshots + actual file/readback + real CLI completion, session 4ed2ac74…; 24/24/12 capture, accepted 0/+12, trims 12/12/0 and equal rendered pixels. Initial packaged entry limitation is recorded; alignment code is byte-identical to current source. |
| Known offsets, zero/nonzero authority, original attempts, trims/cache | **Passed** visible/current-parent +4/-3 session 1130ce05… and explicit-zero capture above. Version-2 manual authority and complete interactive-only shared reuse set verified; original unavailable attempts retained, no computed authority. Existing automated provisional-original/authority combinations retain their separate scope. |
| Keep current, saved result then close/resume | **Passed**, distinct KEEP_CHECK session b1ba57ca…, viewer/CLI 0, honest unresolved warnings, no authority/manual/shared cache. First expired collector remains a failed collection boundary; ambiguous old/new-window recollection was clarified, not diagnosed as a Save bug. |
| Optional close without Save | **Passed**, OPTIONAL_CLOSE session ae47b65f…, viewer/CLI 0, rejected_result, best-effort rendering with absent authority/cache and retained original evidence. |
| Forced close without a valid saved result | **Passed fail-closed behavior**, retry session 8567fc57…, normal viewer 0 then FC-4005/CLI 5, zero admission/render/report/persistence. No confirmed Save occurred in that session. |
| First Ctrl+C in native review and VS/FFmpeg rendering; repeated FFmpeg | **Satisfied by identified prior physical-host evidence**, exact exit-130/phase/admission/cleanup receipts above. |
| Repeated Ctrl+C in VapourSynth rendering | **Passed after the authorized product fix**, af590b58…/current 6739bfb2, affected native active-render and teardown reruns + five hosted standalone-exit cases. Original 0xC000013A failure is retained. Partial-image retention remains permitted. |
| Repeated native-review console input | **Passed bounded real-OS-event exit/admission/no-authority/cleanup scope**, two events 21.5469 ms apart before unwind, CLI 130; viewer exited after first. Two distinct Python callbacks and human keystrokes are **unestablished**, not claimed. Attempt-1 guard refusal remains a harness failure. |
| Earlier physical Windows PS5.1/7, installation preservation, render/updater and RTX5080 | **Satisfied by identified prior evidence** at 262f624655ebc35b046c6993ba1c85282b994064, within the environment/routes recorded above. Current runtime/native owners unchanged except separately verified CLI exit boundary. No blanket invalidation or full physical-suite rerun. |
| Latest updater lock/recovery and AppData helper delivery | **Satisfied by identified prior evidence**, current hosted twenty PS5.1/7 cases plus actual isolated fresh-full-bundle helper install/hash, both-shell lock refusal/recovery and exact PATH restoration. Code-only updates cannot replace that helper. |
| Actual HDR10/Dolby Vision, range/bit-depth, real-media timing/frame properties | **Blocked** by representative owned/explicitly authorized corpus and corresponding native observations; generated PQ/BT2020/GPU evidence retains its narrower recorded scope. No private media was swept. |
| Index/cache migration, genuine previous-bundle update/full reinstall and objective/perceptual media comparisons | **Blocked** by genuine predecessor installation/update inputs and representative authorized corpus/defined comparison target. Fixture-signed updates and unsigned artifacts do not supply real full-bundle migration proof; fresh full install is required for AppData helper repair. |
| Protected signing checklist/preparation | **Passed preparation**, sanitized metadata and concrete dispatch/receipt sequence in `signing/findings.md` plus current-candidate correction above. No secret values exposed. |
| Key scope/migration, negative access, protected signed RC verification | **Blocked** by maintainer-readable scope metadata, separately authorized credential operations, reviewed candidate integration into protected pre-release, its then-current exact SHA and RC/environment approval. Current dev SHA is not a protected dispatch target. No merge, migration or signed dispatch authorized/performed; fixture/unsigned proof does not close this gate. |
| Linux NVIDIA and X11 wrapper/visible GUI | **Outside current default release obligation**, separate optional profiles requiring compatible Linux GPU/X11 hosts for their own still-unobserved claims. |
| Maintenance App actual token creation and postpublication pre-release recreation | **Blocked** by separately approved first operational run and publication/freeze prerequisites; prior App-name/bypass metadata scope remains satisfied. No branch recreation/publication solely to test it. |
| Live slow.pics/webhook/TMDB | **Blocked** by explicit live-request authorization, dedicated credentials/receiver/owned media and bounded request/cleanup plan. Prior mocks/local persistence and newer source reconcile older premises but do not supply live receipts. |
| CQ7 image-request lifecycle | **Outside accepted refactor/release-blocker scope**; bounded public-Next/RAF stale-lifecycle investigation passed. Actual browser background-suspension discriminator remains unobserved; retain owners, no speculative consolidation. |
| CQ14 resampling | **Outside accepted refactor/release-blocker scope**; intentionally different current resampling policies retained. Real Pillow/fpng discriminator additionally **blocked** by supported fpng runtime and an agreed comparison/disclosure contract. |
| Historical unmanaged-native crashes and failed evidence attempts | **Failed historical observations retained**, including unmanaged COM/crash, missing libx264 encoder, collector timeouts and initial proxy-console guard refusal. New managed visible passes resolve the managed-profile acceptance gap, not the cause of an unmanaged crash or a different proof level. |
| Release/publication and legal/corresponding-source approval | **Outside this task**, expressly excluded; no signing/release action. |

**Cleanup passed, exit 0**, `native-visible/finalize_cleanup.py prepare` then
`remove`. Absolute root/parent containment, exact 6739bfb2 ownership markers,
complete file inventories, zero reparse points and no matching owned native/helper
process were verified before recursive removal. All 173 files (197,982,091 bytes
across the main and failed-preparation roots) have retained copies or exact
byte-identical fixture references; every retained SHA-256 was rechecked before
deletion. `cleanup-prepared.json`, `cleanup-archive/`, `cleanup.json` and
`processes-before-final-cleanup.json` preserve the targets, provenance, archive
mapping and result. Both disposable roots were removed; unused initial
`optional-unsaved`/`forced-unsaved` plans are **not run**, with acceptance supplied
only by their separately named actual cases above. Reused extracted bundle and
downloaded ZIP remain uninstalled and retained; user installation/media/profiles
were untouched. Environment overrides were child-only, with no parent PATH/Qt
change to restore. Screenshots, actual downloaded JSON, native sidecars, reports,
diagnostics, process receipts and owned fixtures remain outside scratch.

At completion of this verification continuation, the only tracked edit was this
ledger, then uncommitted. No product change, commit/push, signing/release operation
or live product request occurred during that continuation.
Final whitespace/conflict/readback checks and refreshed evidence-integrity receipt
record the final local document state; no satisfied application suite is rerun
for a prose-only ledger update. Previous integrity manifests remain retained.

The subsequent user instruction authorizes committing/pushing this updated ledger
to `v0.7.0` and preparing a MacBook handoff. This is a documentation-only commit
on top of tested head 6739bfb2; the exact new commit/remote readback belongs to the
handoff receipt. Product/runtime content and all tested source identities above
retain their scope. Supporting ignored Windows evidence does not travel with a
Git pull: transfer the accompanying evidence package separately for artifact-level
review. Its exact archive/included-file hashes and omissions belong to its manifest.
The small original `browser/transfer/transfer-package.zip` remains the unmodified
UI-exported report/assets/review input for actual fresh-storage MacBook import,
state/image/identity/reload acceptance. Receiving that package on the MacBook can
close the cross-machine prerequisite; reading this ledger alone cannot. No merge,
credential migration, protected signing dispatch, publication or release action
is authorized by this commit/push/handoff instruction.

## MacBook continuation — 2026-10-18

### Checkout and transferred evidence

The Mac checkout was clean on `v0.7.0` at
`104491b5b023b5a666d37bb7ea9d6742b030c749`. Remote readback identified the supplied
`698d1e7647c3f580b07939ff07bf8b3dbfc334f0`; fetch and `merge --ff-only` advanced
the clean checkout without resetting or discarding work. PR138 remains open and
unmerged against protected base `35792220ae59d514ed626707340e2a86a7a14d05`.
Only this ledger differs between tested product baseline 6739bfb2 and 698d1e76;
source, tests, workflows, tools and dependency files are unchanged across that range.
The supplied handoff and its scripts were read as evidence; no transferred Windows
helper was executed on the Mac.

Durable receiving directory:
`/Users/tristan/Downloads/frame-compare-macbook-verification-2026-10-18-qrg1myxu/`.
`windows-evidence/` holds the unpacked Windows receipts; `mac-evidence/` holds new
observations, screenshots, actual downloaded exports and decoded CI logs.

The received `frame-compare-windows-evidence-698d1e76.zip` is **29,872,391 bytes**,
SHA-256 `35f9e80ddf5453cf21c2a20f81ae5aaae85a313cf7760ca95c0006d3a84cd6ef`,
matching `package-receipt.json`. All **1,226 included entries** match the sizes
and SHA-256 values in `HANDOFF-MANIFEST.json`; **zero mismatches**. The manifest's
own received SHA-256 is
`f8dabaec2451a5ceeae21f43a49000189101f0e7944fb0c0934d616c4f793cc0`.
The 52 explicitly omitted files were not received or locally rehashed. Their
recorded original identities remain historical evidence, not inspected Mac bytes.
Receipts: `transferred-integrity.json`, `mac-receipt.json`, original package manifest
and receipt. Extraction refused escaping paths and symlink entries.

The final Windows disposition was reconciled with transferred source-equivalence,
native authority/cancellation audits, browser transfer acceptance and cleanup
receipts. In particular, the first visible capture's packaged CLI entry limitation
is preserved; alignment owners were byte-identical, while later current-parent
console observations establish their separately recorded entry-boundary claims.
The capture, known-offset, Keep-current, optional-close and repeated-event audits
remain artifact evidence of the original Windows sessions, not new native Mac runs.
Earlier 262f PS5.1/7, installation/updater/render and RTX5080 proof keeps its exact
source/runtime scope. `mac-evidence/reconciliation.json` records the inspected
receipt identities. No satisfied suite or native session was repeated.

### Latest automatic CI inspected

All four automatic attempt-1 workflows triggered by 698d1e76 completed successfully.
Decoded checkout logs establish actual tested PR merge
**`d778a55db214f4a62102d0a4aff93d167463efb5`**. GitHub Git-object readbacks show
that merge and head698d1e76 share exact tree
**`890a2216cb2f536c646393f1b806b2dd499d9e2b`**. These are observed completed
automatic runs; no dispatch or rerun was requested.

| Gate | Inspected result and boundary |
| --- | --- |
| [CI39059652931](https://github.com/TJZine/frame-compare/actions/runs/39059652931) | Ten successful jobs, including browser, fresh distribution install, static/import checks and both dependency audits. Browser log has23 passing progress symbols and zero skips; quiet output does not emit a numeric total. General pytest has77 skip-summary lines summing276 items; these include collection/platform/capability/opt-in gaps and are not passes. |
| [Docker39059652932](https://github.com/TJZine/frame-compare/actions/runs/39059652932) | Canonical cold gate explicitly reports300 passed; separate resource step3 passed; no skip-summary entries. Container/software-Vulkan and accelerated sample-volume scope remains distinct from Linux NVIDIA hardware/endurance. |
| [Windows39059653003](https://github.com/TJZine/frame-compare/actions/runs/39059653003) | Full suite, full/extracted portable smoke and unsigned update layout/upload succeeded.61 skip-summary lines sum87 items, with no updater/interpreter skips. Extracted provenance explicitly identifies tested merge d778a55. Direct GPU proof reports `vulkan_runtime_unavailable`; hosted panel proof is offscreen. Four whole protected jobs and seven signing/release-related unsigned-build steps remain skipped. |
| [Documentation39059652950](https://github.com/TJZine/frame-compare/actions/runs/39059652950) | Build and search-scope steps succeeded; Pages configuration/upload and deployment skipped. |

`automatic-ci-readback.json`, `ci-source-and-artifact-readback.json`,
`latest-ci-skip-accounting.json` and `ci-{pytest,browser,docker,windows}.log`
retain source/job/step/skip observations under `mac-evidence/`. Original 6739bfb2
and104491b5 results retain their own identities rather than being relabeled.

| Latest artifact | ID | Bytes | GitHub API ZIP SHA-256 |
| --- | --- | --- | --- |
| Docker evidence | 12111460285 | 465242 | `8469ae50853d4834845547aa0a2759e468d1db09045547fcb7ca8f002a549b92` |
| Windows portable | 12111720132 | 422847488 | `f962eef03573fffccfd0e9e99ea3295a8088058a12969611a72ee0d63790bc92` |
| Windows unsigned update | 12111530917 | 698436 | `eeb3aca9f02f381e1a35ffa5659ba41981d0236f4e1de2578ce1eed863b6dcb8` |

These latest archive digests are API metadata, not locally downloaded/rehashed ZIPs.
They are separate from the Windows evidence package actually transferred and hashed.

### Actual Windows-to-MacBook report transfer

**Passed.** Receiver: physical MacBook Pro (MacBookPro18,1), Apple M1 Pro,
macOS 27.0.1 build 26A434, Google Chrome 155.0.8059.82. Sender: the original
Windows 10/Brave Chromium 155.0.8059.85 UI-export session identified in
`browser/transfer/acceptance.md`.
Serial numbers, hardware UUIDs and account data are not needed in retained receipts.

The unmodified original `browser/transfer/transfer-package.zip` is351,229 bytes,
SHA-256 `586ab45c45931a62c4bbfb6fafadb47f410e1cb006da519a16b2210b377d6875`.
Receiving extraction preserves the intentional space, `#`, literal`%20` and Unicode
paths. All four entry hashes match the sender: report
`8bd38594f21165b8c197ff7dba1b11fd79747da2242e0d5505943c658967b3a8`, original
review JSON `850858fbc1c85a4d055a9515ea5fbdae99a7bd7596f67e72ba639aae164031cd`,
and each image `63ef318d96b5d0d0ceba6e04a4e622b1158335cdc67c49e27839132c6f655058`.
No report was regenerated. Report identity remains
**`report_381ff1102c183e0764f342a2b68bf9d7`**, payload**1.3**.

Actual native Chrome Guest windows opened the received offline `report.html`.
Every accepted scenario began with a new Guest session and observed **0 review
records saved in this browser**; the previous Guest window was closed first.
The report's Inspector→Review controls edited local records and opened **Import
review JSON**. The **native macOS Open dialog**, including Go to Folder and the
selected file's preview, supplied the original transferred disk JSON. No CDP
file-input assignment, injected File object or review/model/storage mutation via
evaluation was used. Native Save dialogs retained actual UI re-exports.

Apply UI state was captured, then each accepted case was reloaded and exported.
All fields, not merely record counts, were compared in those actual re-exports:

- Imported ordinal0: bookmark true, note exactly `Transfer é 😀 — source note`,
  tag null and preferred_clip_id null.
- Local conflicting ordinal0: bookmark false, note exactly `Local conflict Ω`,
  tag null and preferred_clip_id null.
- Local-only ordinal1: bookmark true, note exactly `Local-only frame 15 🚀`,
  tag null and preferred_clip_id null.

| Accepted receiving scenario | Observed preview: Add / Change / Remove / Unchanged | Exact state in the receiving UI export after reload |
| --- | --- | --- |
| Fresh Merge/Keep local | 1 / 0 / 0 / 0 | Only imported ordinal0, exact sender record. |
| Merge/Keep local with conflict | 0 / 0 / 0 / 2 | Exact local ordinal0 and local-only ordinal1 retained. |
| Merge/Use imported with conflict | 0 / 1 / 0 / 1 | Exact imported ordinal0 and local-only ordinal1 retained. |
| Replace with conflict | 0 / 1 / 1 / 0 | Only exact imported ordinal0 retained; local-only ordinal1 removed. |

Actual Mac UI-exported JSON after reload matches format/schema/report identity
and every expected review field for all four scenarios. Newly generated
`exported_at` timestamps differ legitimately; whole-file equality with the old
Windows download is not required. `transfer-acceptance-result.json` records exact
records, export hashes and preview predicates; `*-initial`, `*-local-frame*`,
`*-preview`, `*-applied` and `*-reloaded` AX/screenshot receipts record the path.

Read-only expressions entered through the actual Chrome DevTools console observed
both main images `complete=true`, intrinsic dimensions1×1, at correctly encoded
transferred URLs after the fresh import/reload and later Replace/reload, including
frame15. No state was set through those expressions. Image observations during an
initial conflict-driver attempt remain valid independently of its note-input gap;
the successful fresh-import image observation also has exact accepted review state.
These synthetic1×1 assets prove loading/path handling, not real-media visual quality.

**Driver failures retained, expectations unchanged:** direct CUA Chrome-tab creation
was unavailable, so native Chrome Guest was used. Stale native accessibility IDs,
an invalid text-entry invocation and a premature file-picker path entry were
corrected using fresh AX observations; an incidental Find overlay was dismissed.
More significantly, native `typeText` omitted the rocket from the initial local-only
note. Exact downloaded-JSON comparison caught it; those three conflict attempts
are retained under `initial-native-text-entry-omitted-rocket/` and do not satisfy
the required exact-string cases. Clipboard paste plus explicit pre-import exact
note checks corrected the driver. Only those three conflict scenarios were repeated
in new Guest sessions; the valid fresh import was reused. No product failure or
product change was established.

Owned Guest windows were closed after exports; `guest-cleanup.json` records the
final non-Guest/non-report front window. The report was never opened in the regular
profile, and no user profile storage was cleared. Native paste restored the user's
clipboard through the computer-use API. Regular Chrome windows were retained;
there was no application-name process kill. Inputs, screenshots, successful and
failed exports, decoded CI logs and Windows receipts remain outside scratch.

The retained read-only artifact audit `mac-evidence/check_transfer_receipts.py`
ran with `python3`, exited 0, and verified all four actual re-exports, previews,
fresh-storage/exact-input predicates and retained image observations. This audits
browser-produced artifacts; it is not an additional product-test suite. Only this
ledger changed in the repository. `git diff --check` and
`uv run --no-sync zensical build --clean --strict` passed; no product suite was
repeated for the documentation update.

### Final disposition after the MacBook continuation

This table is the current acceptance summary. Earlier pending/failed rows above
remain historical observations. No satisfied application suite was repeated.

| Obligation | Current disposition and exact remaining boundary/prerequisite |
| --- | --- |
| Checkout/remote preservation and transferred evidence integrity | **Passed.** Clean checkout safely fast-forwarded to698d1e76; all1,226 included hashes match.52 omissions retain their original scope. Only the ledger is edited locally. |
| Latest automatic CI/browser/distribution/Docker/resource/unsigned Windows/docs | **Passed / satisfied by identified evidence.** Four completed automatic runs above at exact tested merge d778a55, tree identical to698d1e76. Relevant skips retained; no signed/GPU/visible-host inference. |
| Windows original UI export and single-host browser acceptance | **Satisfied by identified prior evidence**, transferred `browser/transfer/` and `browser/physical-controls/` receipts at their original Windows source/runtime. |
| Actual Windows-to-MacBook transfer, receiving UI import, Merge/Replace/conflict choices, exact records/identity/images and reload | **Passed**, original unmodified package on independently identified physical MacBook, four accepted fresh-Guest scenarios and exact actual UI re-export comparisons above. |
| Native OS file picker | **Passed on macOS Chrome**, actual Open/Go to Folder/selected-file preview and Save dialogs. Native Windows picker and other browsers are not inferred. |
| Remaining physical gestures, OS motion/browser zoom and browser-policy observations | **Satisfied by prior evidence only for its recorded automated/trusted-input/storage cases; blocked for remaining physical-device/OS-setting observations** by the specific device/settings interaction. This continuation did not change system settings or claim physical touch/pinch/assistive-technology proof. |
| Native decoder/doctor, visible capture, known offsets, zero/nonzero/original authority, Save/close/resume, Keep current and optional/forced unsaved close | **Satisfied by identified Windows evidence**, original managed runtime and session-specific authority/artifact receipts. First packaged-entry limitation and later current-parent boundaries remain explicit; no new native Mac claim. |
| First native/VS/FFmpeg Ctrl+C, repeated FFmpeg and corrected repeated VS rendering | **Satisfied by identified physical Windows evidence** at its recorded source and af590b58 correction/affected reruns. Original failure retained. |
| Repeated native-review console events | **Satisfied by identified bounded Windows evidence**: two OS events21.5469ms apart before unwind, CLI130 and cleanup/no authority. Two separate Python callbacks, physical keystrokes/every timing and a full pre-signal diagnostic-byte snapshot remain unestablished. |
| Earlier physical PS5.1/7 installation/updater/render/RTX5080 acceptance | **Satisfied by identified prior evidence at262f**, within its unchanged runtime/routes; no blanket repeat or new Mac/GPU claim. |
| Latest lock/recovery and full-bundle AppData-helper delivery | **Satisfied by identified prior physical/helper receipts and latest hosted Windows coverage** without updater/interpreter skips. Code-only updates still cannot deliver the helper. |
| Representative HDR10/Dolby Vision, range/bit-depth and real-media timing/frame properties | **Blocked** by representative owned/explicitly authorized corpus and corresponding native observations. Generated PQ/BT2020/GPU proof remains narrower. |
| Index/cache migration, genuine predecessor update/full reinstall and objective/perceptual comparisons | **Blocked** by genuine predecessor installation/update inputs and authorized corpus/defined comparison target. Fresh full installation is required for the helper repair; fixture signatures/unsigned artifacts do not establish predecessor migration. |
| Signing preparation | **Satisfied by identified prior preparation evidence**, sanitized metadata/checklist only. |
| Key scope/migration, negative access and protected signed RC verification | **Blocked** by maintainer-readable scope metadata, separately authorized credential operations, reviewed integration into protected pre-release, its then-current exact SHA and RC/environment approval. Dev head698d1e76 remains outside protected pre-release; no protected action authorized/performed. |
| Maintenance App token creation and postpublication pre-release recreation | **Blocked** by separately approved operational run and publication/freeze prerequisites. Configuration metadata is narrower; no recreation/publication solely for testing. |
| Live slow.pics/webhook/TMDB | **Blocked** by explicit live-request authorization, dedicated credentials/receiver/owned media and bounded request/cleanup plan. No live product-service request occurred. |
| Linux NVIDIA and X11 wrapper/visible GUI | **Outside current default release obligation**, separate optional profiles requiring compatible Linux hosts for their own unobserved claims. |
| CQ7 and CQ14 | **Outside accepted refactor/release-blocker scope.** Prior bounded CQ7 lifecycle proof retained; actual browser-managed background-suspension discriminator unobserved. CQ14 real fpng comparison additionally needs a supported runtime and agreed comparison/disclosure contract. No speculative consolidation. |
| Historical failed native/harness/input attempts | **Failed historical observations retained**, not converted to passes. Later successful managed Windows or exact Mac receiving cases establish only their stated scopes. |
| Release/publication/legal approval | **Outside this task.** No signing, credential migration, protected dispatch, PR merge, publication or release action. |

## HDR output correction and native optimization preparation — 2026-10-21

This section updates the HDR-specific obligations. Earlier acceptance keeps its
identified source/runtime scope; it does not establish acceptance of these changed
pixels or of a future native optimization. The user's later MacBook HDR/SDR/DV
observations are useful attributed observations, not independently captured
evidence for this exact replacement implementation.

### Committed source and evidence identity

Implementation: **`5c15cbf4daa7bb8630706259a42d2674ec5d9f5f`**, parent
`124d75575d9ceb35987649724e029f9f4dc3cd98`, branch `v0.7.0`.
Before acting, actual local and remote heads both identified that parent; PR138
remained open against `pre-release` at
`35792220ae59d514ed626707340e2a86a7a14d05`. The first sandboxed remote read failed
to connect; the scoped authorized `git ls-remote` retry succeeded. No checkout
reset, merge, protected branch update or installation replacement occurred.

The 18 implementation/doc/test files were tested as an uncommitted snapshot atop
that parent. Their retained raw diff SHA-256 is
`8fc37585a8c6107f4a4a97416e0ee89de1cc83fcfe468efabbf73183470f783c`.
All 18 working-file hashes were rechecked before committing, with an initially
empty Git index. Git blob comparison reconciles checkout line-ending normalization;
the original Windows raw-byte hashes are not portable Linux checkout hashes.
Five preexisting untracked VSView plans remain outside these HDR commits.

Raw evidence remains outside scratch at these local roots, relative to the Windows
checkout `C:\Software\video\frame-compare`:

- `generated/verification/2026-10-20/hdr-color-study/`: canonical diagnostic
  `study-summary.json`, original mastering/curve studies, retained Pro packets,
  and `output-history-controls/`.
- `generated/verification/2026-10-20/hdr-color-study/srgb-implementation/`:
  source receipt/snapshots/diff, command receipts and exits, JUnit, media results,
  numerical oracle comparison, timing, skip accounting and cleanup.
- `generated/verification/2026-10-21/hdr-native-still-prototype/`:
  Pro response, independent source review, paired native16/sRGB8 arrays,
  negative controls, compatibility-guard self-test, build prerequisites and handoff.
- `generated/verification/2026-10-21/hdr-commits/`: commit/tree reconciliation
  and the committed-source continuation receipt.

The raw film, generated reports/images, full native binaries, caches, test keys and
large diagnostic arrays are intentionally not Git contents. This ledger and the
reusable synthetic harness are committed. Original ZIPs remain immutable historical
evidence; a committed-source continuation identifies the new Git revisions.

| Frozen handoff artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `hdr-performance-options/frame-compare-HDR-performance-Pro-packet.zip` | 1,503,348 | `84c47d6298eb963423457970135247b5e831584d816136100d3f1d00e7cf6384` |
| `hdr-native-still-prototype/frame-compare-native-still-MacBook-handoff.zip` | 1,651,810 | `232ef769c25cc35bf315973e0577fa6abf31e5129ba3ead9511de54de995b42b` |

Each ZIP's CRC and member SHA-256 manifest passed. The first contains the earlier
dirty source and pinned upstream source; the second contains that packet plus the
new Windows references and build handoff. No movie footage or secret values are
needed for those packets. Their earlier statements that source was uncommitted
describe packaging time, not the current Git state.

### Behavior implemented; defaults retained

Known libplacebo BT.1886 SDR destination samples now pass through explicit
destination-black/white decoding, endpoint-relative normalization and the sRGB
OETF in RGBS before RGB8. The existing optional gamma stage retains its position.
Output properties specify full-range RGB/sRGB/BT.709 and discard stale HDR/RPU/
mastering/scene/chroma properties; original source diagnostics stay available.
Pillow declares sRGB for known matching samples. Arbitrary SDR and degraded
fallback output do not inherit this native-output conversion.

Screenshot preparation alone requests independent native frames. An eager
one-frame prototype preserves admission/fallback; other source positions use
transient one-frame Tonemap nodes through FrameEval, with Loop after Tonemap.
Later native failures propagate rather than silently mixing fallback pixels.
Sequence callers retain sequence state. Applied report identity/disclosure includes
`output_encoding=srgb` and `frame_policy=independent_frames` where selected.
No BT.2390 knee, gamut, dynamic-detection, smoothing, metadata, Dolby Vision,
contrast, destination or preset default changed.

### Executed verification and failure/skip accounting

Environment: unmanaged native Windows10 build19045, Python3.13.7, VapourSynth R81,
vs-placebo2.0.4, native libplacebo log v7.371.0/API371, L-SMASH1310,
RTX5080, Pillow13.0.0 and NumPy2.5.4. Runtime binary hashes and package inventory
are retained in `output-history-controls/environment.json`. Loaded vs-placebo DLL
SHA-256 is `b0a0689946e03f6f7467b798fba4678018bb28ba6b1caecdded8d08945049310`.
This is not fresh portable-bundle or Docker acceptance.

| Check / command owner | Observed result | Boundary |
| --- | --- | --- |
| Changed implementation test files in the full native run | **Passed: 109 cases.** | Overlaps other selections; do not sum these rows as independent cases. |
| `pytest -q tests/vs/test_integration.py -k 'srgb or still_tonemap'` | **Passed: 3, exit0.** `native-final-tests-command.json` / JUnit. | Native arithmetic/PNG goldens, original props, quantized PQ exactly-once conversion, sampled history/concurrency. |
| `pytest -q tests/e2e/test_media_tonemap.py`, media/backend required | **Passed: 2, zero skips, exit0.** `media-tonemap-command.json` / JUnit. | Actual installed CLI/native rendering; not all media/platform journeys. |
| `real_media_probe.py` and `run_real_media.py` | **Passed within sampled scope:** RPU/noRPU direct/helper/forward/reverse/repeated/parallel, plus noRPU lifetime; 13 children, exit0. Separate sequence benchmark child also exit0. | Owned Kill Bill original media/index/config unchanged; exact sampled finalRGB8 equality. No generic DV reshaping or exhaustive history guarantee inferred. |
| Retained porch native16 vs independent float64 conversion oracle | **Passed:** finalRGB8 maximum difference1 code;211 components near rounding boundaries. | Arithmetic oracle tolerance is distinct from the future optimization's zero-difference gate. |
| Ruff lint/format, Bandit medium gate, import-linter no-cache, Pyright `--warnings`, VS stub lint/format | **Passed, exit0**, exact receipts under `srgb-implementation/`. | Static evidence, not native acceptance. |
| `pytest -q -n4 --dist loadgroup` | **Failed, exit1:** initially4091 passed/82 failed/77 skipped. Failed-fixture retry leaves4165 passed/8 unresolved/77 skipped. | Six failures reproduce on unchanged parent; two lifecycle cases require user-PATH registry access. Whole gate is not green. |
| New paired-checkpoint harness | **Passed:** six stock Windows histories,35 captures over10 synthetic frames; native16 and corrected sRGB8 agree exactly across sampled histories. | Same evaluation linked by carried tap token/hash. Tap count is not a native invocation/eviction counter. |
| Shared-sequence negative control | **Expected rejection, exit1:** frames2–8 differ at both checkpoints. | Demonstrates comparator sensitivity to the history effect, not a new failure of the independent implementation. |
| Comparator enforcement | **Passed:** equal accepted; native16-only1-code difference rejected with unchangedRGB8; identical pixels with incompatible tone kwargs rejected. | Also guards fixture/settings/kwargs/platform/Python/VS and requested histories; source/GPU identity remains a separate receipt obligation. |

The 74 original updater-key fixture failures came from a scratch root inside the
repository, which the fixture generator deliberately refuses. Retrying that failed
setup outside the repository established74 passes; it did not waive a product
expectation. The six remaining baseline failures are one collection-warning
orchestration fixture, two alignment path-separator expectations, two terminal CRLF
expectations and a copied-interpreter Windows launcher fixture. The two blocked
installation lifecycle cases are the PS5.1/PS7 variants requiring registry access.
Exact IDs/reproductions are in `suite-accounting.json`; no unrelated repair was made.

The 77 full-suite skips are retained by reason: browser unavailable20; Windows
filesystem/POSIX-execute distinctions5; media opt-in7; streaming-resource opt-in3;
live services2; POSIX/signal/PTY/interpreter-specific cases21; Perl1; jq18.
These sum77 and establish no platform pass. Separately opted-in tonemap E2E above
does not close every skipped media case.

Initial harness setup failures are retained: incorrect ModifyFrame callback
parameter name, then bytes-versus-string interpretation of the carried hash.
Both were corrected; the six accepted native children use the final probe.
Independent review confirmed paired checkpoint linkage and identified the missing
input compatibility guard; the strengthened comparator was checked against retained
arrays and deliberate violations without repeating GPU work. Small arrays/logs
remain outside scratch; all seven accepted/negative-control native children exited.

Commit preparation reused these native results after proving all18 tested files
match the implementation commit's Git blobs. The tracked harness migration changes
only entrypoint references/formatting; its AST matches the accepted harness with
those substitutions. The tracked runner's comparator self-test and probe help
exited0. Repository Ruff lint and formatting checks and `git diff --check` passed;
an initial filename-length formatting failure was corrected and retained in the
commit-preparation receipts. Strict Zensical was not rerun because its dependency
is unavailable locally. No unchanged full suite or GPU benchmark was repeated.

### Measured performance cost and next experiment

Same-host, same-kwargs, noRPU 4K Kill Bill frames12382–12413:
independent34.82651080004871s versus shared sequence6.868044199887663s,
ratio5.070804698755192. **Both paths include the sRGB correction.** The helper's
implicit frame0 request occurs before timing. Timed work includes get_frame,
measurement/hashing and GC, so this is not full-CLI wall time or native stage
profiling. Host private memory stabilizes around2.1GiB after warm-up; host counters
do not establish VRAM bounds. No universal5x penalty or achievable5x speedup is claimed.

Pro's recommendation and independent pinned-source review support an experiment,
not adoption: retain a native device/renderer, reset temporal state per still,
keep constructor metadata immutable/per-frame, and reject/poison failed native
transactions. Flush does not clear failed shader/LUT/error caches. The review also
found a WARN-only missing-peak-data path: an ERR-only event latch is insufficient
for the strict first prototype. Internal capture must include the relevant numeric
severity independently of visible logging, or expose structured detection status.
Do not parse English logs or clear errors and continue with degraded pixels.

Generic native CSP_DOVI reshaping remains excluded until previous-RPU semantics
are defined. Pinned source also shows an unused reshape allocation in the metadata-only
RPU route; that is a source finding, not measured installed-DLL leak proof or a claim
that current RGB/HDR10 pixels consume process-static reshape state. Preserve actual
L1/L6/endpoints handling when addressing it in the isolated native prototype.

The user chose **MacBook Docker build, then Windows testing here**. Current Windows
has Visual C++ Build Tools but no detected upstream MSYS2/Meson/development-library
build stack or Docker runtime. No native candidate was implemented, built or installed.
Linux ELF `.so` output cannot provide Windows acceptance: return a Windows x64 PE DLL
from the same reviewed patch/dependencies through a separately demonstrated cross-build
or Windows build route. No protected dispatch/publishing is authorized.

Reusable harness entrypoints now live in `tools/hdr_still_probe.py` and
`tools/verify_hdr_still.py`. The former is the accepted probe with its paired
checkpoints; the runner points at that sibling name. Example in the matching locked
environment, with fresh disposable output directories:

```text
python tools/verify_hdr_still.py --self-test --output /proof/comparator
python tools/verify_hdr_still.py --mode stock-fresh --output /proof/stock
python tools/verify_hdr_still.py --mode candidate-fresh --plugin /build/libvs_placebo.so --output /proof/rebuild-fresh --reference /proof/stock
python tools/verify_hdr_still.py --mode candidate-independent --plugin /build/libvs_placebo.so --output /proof/independent --reference /proof/stock
```

Use original installed, unchanged rebuild, patched fresh and patched independent
controls on the same environment; intentionally different binaries must retain
their own identities. The supplied ordinary synthetic fixture does not replace
epsilon/rounding adversaries, metadata/RPU transitions, injected faults/warnings,
genuine eviction/recomputation, cancellation, RPU allocation/VRAM/lifecycle and
production sparse/multiclip/CLI profiling. Native16 **and** finalRGB8 require zero
sample differences from the current reference for the optimization gate.

### Isolated MacBook native prototype — 2026-10-21

Continuation source was clean `79c52a6c5de5bb1597ea011780585106aa100628`,
matching origin and PR138. The supplied committed handoff passed CRC and all167
manifest hashes; all21 normalized source exports matched exact committed Git bytes.
No historical `source.diff` was applied. Product source, tone controls, sRGB
conversion, stock plugins and the application's fresh-node path remain unchanged.
The three-file native experiment and binaries are outside the repository in
`frame-compare-native-still-prototype-results-2026-10-21.zip`, with a complete member
manifest, source archives, build recipes, commands, failed attempts and evidence.

The opt-in API is `independent:int:opt`, default0. This first candidate admits only
fixed RGB48 HDR10/PQ to native16 SDR; HLG, EL and generic native DOVI reshaping are
rejected. It retains device/renderer resources, flushes temporal state per still,
keeps constructor metadata immutable and frame metadata local, and permanently
poisons failed transactions. Numeric WARN-or-higher capture works independently
of visible logging. Constructor texture admission, owned cleanup and native
locking received an independent source review; its identified eager-allocation
gap was corrected and re-reviewed before building. No unresolved material source
finding remained; source review alone establishes no runtime pass.

Patch SHA256: `8ef323fd80a08619977c26173786f079c872e2374b55eb0f51e11f4dcdc9cc7c`.
Both platforms use vs-placebo `3cfd23f257ecb62b0cbd81eaaca092e18ae8e579`,
libplacebo `a7a18af88ff0a17c04840dcb3246047bb6b46df3`, exact wrapped libp2p and
libdovi3.3.2. Actual compiler/dependency differences remain explicit in the packet.
Source-provenance checkouts were not mistaken for a compiled native plugin.

| Evidence | Observed result and boundary |
| --- | --- |
| Linux arm64 original stock, unchanged rebuild, patched-fresh, patched-independent | **Passed:** each of the three comparisons has35 captures across six histories, zero native16/sRGB8 differences from the original same-runtime reference. Python3.13.16, VS R81, NumPy2.5.4, vs-placebo2.0.4, llvmpipe/Mesa25.0.7 software Vulkan. |
| Comparator and sequence controls | **Passed:** equal accepted; native-only1-code and wrong-kwargs violations rejected; shared-sequence negative differs on frames2–8 at both checkpoints. Original and patched default sequence agree over10 forward frames. |
| Extended core, metadata, PQ-code and RPU fixtures | **Passed:** original-fresh, patched-fresh and independent agree at both checkpoints under all six histories per fixture. Includes every PQ16 input code, missing-after-present mastering/scene metadata, valid nonzero/zero/missing-L1 RPU, absent/malformed RPU and transitions. Exact libdovi inspector validates the generated RPU classes. This is not measured peak-epsilon or rounding-midpoint coverage. |
| Native recomputation | **Passed within cache-disabled scope:** native and downstream caches disabled; repeated requests have native render-call counters1–6, including target2 at calls2/4/6. This proves actual recomputation, not ordinary-cache eviction or only tap evaluation. |
| Constructor admission | **Passed:**11 invalid/unsupported configurations rejected and the supported RGB48 case constructed. |
| C-boundary fault injection | **Passed:**11 cases including the healthy control. Real ELF interception proves constructor failure, texture/upload/render/download rejection, successful render with error/device status or quiet numeric WARN rejection. Removing the injected fault still leaves a different frame permanently rejected. Actual internal peak/shader/LUT/driver failures, allocation failure and concurrent callbacks remain unproved. |
| RPU node lifetime diagnostic | **Completed, unresolved:**100 native renders across10 node/device lifetimes per mode with equal native16 hashes. Candidate host RSS rose200,781,824→271,110,144bytes; stock229,265,408→255,954,944bytes. These single samples do not attribute a leak, establish bounds or measure VRAM. Elapsed23.34s stock/3.42s candidate includes hashing and GC; no benchmark or production speedup is claimed. |
| Windows cross-build | **Built:** actual unchanged and patched PE32+ x64 DLLs, same reviewed patch/dependencies, VapourSynth entrypoint and imports inspected. Static compiler dependencies; Windows system DLLs and existing `vulkan-1.dll` remain runtime dependencies. Native Windows loading/pixels/faults and the packaged PowerShell driver are **unrun**. |

Linux candidate SHA256:
`33dda72a7a3da6549553e15461e920b7d07957f318890d0ee5976c814c6323e3`.
Windows unchanged DLL SHA256:
`a0b2ba4b27da3c108c1266338ffe49571470901b9bffeb611f8a9e45a5c6aae3`.
Windows candidate DLL SHA256:
`1665e0dd4dd8b6491b54050e38a0d48e60316e381224ff5f0cf9afa6d78876fe`.
The Windows driver verifies source/DLL/harness identities and creates a fresh
original Windows reference before all three comparisons. Linux pixels are never
used as Windows expectations. Build/header/toolchain setup failures and the initial
cache-control harness error remain retained rather than being counted as passes.

At this initial-screen stage, Windows runtime, histogram/rounding adversaries,
internal failures, interleaving, cancellation, RSS attribution, allocation/VRAM and
paired profiling were still open. The following dated follow-up sections supersede
those gaps only within their explicit environments and cases. The application does
not select this candidate.

Hosted readback for application head79c52a6c: [Docker39551756319](https://github.com/TJZine/frame-compare/actions/runs/39551756319)
completed successfully on merge `0e581afb5eec1c8a387b1893a97917f40698bb2c`:
306 native/media cases with zero skips, then3 separate resource cases. This is
stock application/runtime proof, not patched-plugin acceptance.
[Unsigned Windows39551756413](https://github.com/TJZine/frame-compare/actions/runs/39551756413)
failed its full suite; bundle build/upload were skipped. Its eight reported failures
include absent FFmpeg, path/CRLF expectations and two HDR native subprocess access
violations after `VK_ERROR_INCOMPATIBLE_DRIVER`. Existing CI/audit failures retain
their prior scope; documentation passed. No rerun, protected dispatch, installation
replacement, signing, credential operation, merge or publication occurred.

### MacBook Docker follow-up — 2026-10-21

This supplements the frozen prototype above; it does not replace its failed-attempt
history or establish Windows acceptance. Task HEAD was docs-only
`12cb7f54a692aea34e600fc7fd2ac875c68a883e`; application source and both tracked HDR
harnesses remain byte-identical to `79c52a6c5de5bb1597ea011780585106aa100628`.
The same frozen Linux candidate and Windows DLL hashes above were preserved.
No application/native implementation, installed plugin, tone setting, sRGB path,
packaging selection or release state changed. The only tracked follow-up is this
ledger. Supplementary executable diagnostics and evidence are outside Git in
`frame-compare-native-still-mac-followup-2026-10-21.zip`; its manifest identifies
included members, and local receipts identify excluded full-size movie arrays.

**RSS diagnosis:** a streaming 500-node/500-RPU-render candidate run has balanced
observed renderer/Vulkan creates/destroys and RPU opaque/header/DM get/free calls.
glibc allocated arena blocks at 100/200/300/400/500 lifetimes are
11.569/11.605/11.615/11.619/11.617 MiB; mmap allocation accounting stays 1.301 MiB.
End RSS 274.363 MiB falls to 187.996 MiB after diagnostic `malloc_trim(0)`, while
allocated-block accounting is effectively unchanged. Heap/anonymous pages explain
most of that release; newly resident LLVM mappings account for 53.867 MiB that
trim retains. Stock without RPU also shows large retained RSS. A persistent-node
500-request contrast stays around 214–220 MiB before node destruction. These
observations support allocator high-water retention plus library residency as
the main growth mechanism. They do not exhaustively assign residual mappings or
prove the native stack leak-free. Balanced wrapper entries establish observed
calls, not every transitive allocation. No production allocator trim was added.
The pinned legacy RGB metadata-only unused reshaping allocation loss remains
source-supported; the frozen candidate already avoids it. Heaptrack exited 139
before its first completed render; its partial profile is a tooling failure and
is excluded from leak conclusions. Two initial stock raw hash fields erroneously
name the candidate; the RSS README qualifies them against the separately recorded
actual loaded stock path/hash.

| Follow-up obligation | Observation and limit |
| --- | --- |
| Measured epsilon | Actual 3,264-byte GPU histogram readbacks reconstruct pinned float32 mean/99.995-percentile arithmetic below/at/above epsilon. Low-PQ codes 88→112 differ by exactly float32(1/16383). Public detected metadata matches fresh in independent mode; sequence differs on 9/10 frames and changes at equality. Four native paths and observed controls retain exact outputs. The near-uniform fixture also leaves sequence native16/RGB8 unchanged; detected metadata, rather than pixel bytes, is the distinguishing negative control here. |
| Quantization | Same-evaluation corrected-float samples bracket RGB8 midpoints. A public same-pass extra-SSBO diagnostic observes actual shader values before the unchanged UNORM16 attachment across all 65,536 neutral PQ codes. Four native paths and observer-off match native16/corrected-float/RGB8; deliberately adding 1/65535 changes 183,278 native16 and 664 RGB8 samples. This is explicit shader instrumentation, not a float-attachment counterfactual or private-state reset. |
| Internal failure paths | Public-boundary failures reach real `update_peak_buf`, `finalize_pass` and `sh_lut` callers, including an actual numeric WARN-only zero-readback path. Disabled hooks, candidate-context calloc and four concurrent WARN callbacks reject output; after disarming, a different frame remains rejected. Representative paths only, not physical driver damage or a complete allocator/shader matrix. |
| Ordinary-cache eviction | Automatic caching and a 1 MiB budget: first target native call 1, immediate repeat still 1, 48 intervening distinct frames, target call 50. Recomputed native16/sRGB8 match original stock exactly. |
| Multiple sources | Two differing sources/metadata/endpoints with valid/zero/absent RPU: six interleaved and four concurrent requests, exact at both checkpoints. |
| Real-media cache hit/recompute | At 512 MiB the immediate duplicate has native counter 2→2; reducing the owned cache budget to 1 MiB and introducing distractors produces target counters 4/6/8. Final RGB8 matches the exact pressure-run reference in both native paths. |
| Native cancellation | Paused real render plus a second node waiting for the native mutex; cooperative diagnostic SIGINT releases only the test barrier, drains owned futures and observes balanced native destruction. Direct-PID1 TERM confound required KILL 137; `--init` forwarding exits 143/reaps. No GPU-operation preemption claim. |
| Real media | Two 4K HDR/DV encodes of the same film (The Witch), seven sampled frames each: original stock, unchanged rebuild, candidate fresh and independent match exact native16 and sRGB8 from linked same-evaluation captures. Sparse samples do not prove whole-film equality. Full real-media arrays are omitted from transfer; this host audited their hash/comparison receipts, not the omitted pixels. |
| Installed console/report | The installed console entrypoint uses read-only current-source `PYTHONPATH` plus process-local factory substitution, source probing, resolved HDR kwargs (source peaks 10,000/347 nits), Pillow output and report. Stock and candidate six PNG active RGB bytes, sRGB declaration and report rendering facts agree. Five later same-binary pairs each repeat those checks. This does not integrate candidate selection into the product. |
| Installed-console failed output | After both sources admit/produce frame 0, one real peak-readback failure at target 100 exits 5 with JSON FC-4013; failed record persists and no completed report is created; metrics caching is skipped in this manual-frame setup. One already-written exact PNG remains under the existing partial-output contract. Initial ineffective preload-into-stock-probe attempt is retained and rejected. |
| Installed-console SIGINT | Actual installed command with candidate adapter and Docker `--init`, interrupted while inside real native render: exits 130, failure record classified FC-0001/INTERNAL_ERROR, no report or later screenshot admission; the two admitted frame 100 PNGs drain and match stock, with balanced observed renderer/Vulkan destruction after releasing the test barrier. This is finite-work draining, not a universal finite native drain bound. |

**Performance scope:** five alternating fresh/independent pairs, fixed same candidate
binary/dependencies/kwargs and a 4-thread software-Vulkan profile, no diagnostic
interposer or native16 tap in clean timings. Every completed output is validated.
The graph matrix uses a 64 MiB VS cache pressure budget; CLI workspaces use 512 MiB.
Graph calls use current default controls without the CLI external HDRMetadata
object; kwargs are paired exactly, and the full CLI separately exercises its
resolved source endpoints. Graph preparation/frame 0 is separate. Frame-fetch
intervals include decoder, native, conversion and synchronization work; caller
output copying and hashing are outside them. Natural internal GC and some cleanup
may occur inside frame-fetch; final process teardown is separate.
The 52-request matrix has 32 adjacent, 4 sparse, 8 repeated and 8 interleaved two-clip
requests. Both real sources carry RPU; this does not reproduce the earlier Windows
32-frame no-RPU profile. Fresh child processes share driver disk-cache/home state;
source indexes are reused for graph tests and regenerated in fresh CLI workspaces.
Host contention and Docker CPU/memory limits are retained; the host was not isolated.

| Graph workload | Fresh median (min–max),5 samples | Independent median (min–max),5 samples |
| --- | --- | --- |
| adjacent | 95.75s (87.87–105.40) | 88.88s (80.17–91.23) |
| sparse | 26.34s (24.25–29.69) | 25.07s (24.08–26.62) |
| repeated | 49.06s (44.08–50.68) | 44.33s (42.39–48.34) |
| two-clip | 43.83s (41.04–55.33) | 40.94s (39.77–42.26) |

Installed-console full wall medians: fresh **50.29s (48.91–52.44)**, independent
**47.43s (43.61–48.02)**; descriptive median difference
**5.7%**. All five paired observations
favor reuse, but the median gap is smaller than the full run-to-run variation;
this is a modest observed result, insufficient for a broad performance/adoption
claim. Every CLI pair completes six exact PNGs and equivalent rendering facts.
Factory counts are 8 fresh native constructions versus 2 independent per CLI run.
The separate full graph diagnostic observes 54 versus 2 renderer/device lifetimes,
all balanced at teardown, and 324 versus 12 shader-pass creations.
Separate API CPU-interval/creation-count diagnostics identify setup/render/download
work and teardown with unchanged parameters; their nested intervals include
instrumentation and software-driver waits and must not be summed as a GPU partition.

The initial CLI teardown observer lacked destroy hooks, and a subsequent zero-PNG
assertion ignored draining of already-admitted work. Both invalid conclusions are
rejected; corrected hooks and passive admission traces establish the final result.
Raw attempts and the reconciliation remain in the packet.

The tested Linux correctness gaps above are closed within their declared cases.
Windows runtime/performance, physical-GPU VRAM/device behavior, exhaustive residual
allocation ownership and fault coverage, and actual candidate packaging/selection
remain open. Native macOS, fpng/display/physical-luminance and unrelated suite/CI
obligations retain their existing scope. The stock application still uses fresh
nodes; this follow-up is not adoption, installation or release approval.

### Windows frozen-DLL follow-up — 2026-10-21

This reconciles the received MacBook follow-up without replacing earlier Windows
acceptance. Checkout `v0.7.0` was inspected and safely fast-forwarded from
`79c52a6c5de5bb1597ea011780585106aa100628` to docs-only
`12cb7f54a692aea34e600fc7fd2ac875c68a883e`. Both revisions have application
`src` tree `704ea71074278ddc4d139e27b7d1e2d24f3f2270`; both HDR harnesses match
canonical frozen Git bytes. Existing unrelated VSView plans remain untouched.
No reset to the historical source, implementation change or installation replacement
occurred. All ledger content before the isolated MacBook prototype section was
verified unchanged against HEAD.

Received artifacts, CRC and complete member accounting:

- Mac follow-up ZIP: 13,609,139 bytes, SHA256
  `3e956fd9a5eff124283f53e190d8d8890de9261a43b7895e5b70d9f55b2385cf`;
  all 1,307 manifest hashes passed. Windows read-only receipt review independently
  checked the 14 real-media native16/sRGB8 hash pairs and kwargs, and recomputed all
  eight graph timing medians/ranges. Full movie arrays are omitted from that ZIP;
  no claim of independently recomparing those omitted pixels is made.
- Original prototype ZIP: 67,719,883 bytes, SHA256
  `084e439719b94181c32b35de7764041c49d4b843812e43316c668c14525a064e`;
  all 1,233 manifest hashes passed. The original unchanged/candidate DLLs retain
  exactly the frozen hashes recorded above. Neither was rebuilt or installed.

Windows evidence is retained under
`generated/verification/2026-10-21/windows-native-still-original/`;
transfer/reconciliation receipts are under
`generated/verification/2026-10-21/mac-followup-reconciliation/`.
Environment: Windows 10 build19045, Python3.13.7, VapourSynth R81, RTX5080,
NVIDIA617.14. The candidate's Vulkan diagnostic actually selects RTX5080,
Vulkan1.4.351, device10de:2c02, UUID9A:01:71:49:35:D0:CC:92:F4:75:E7:07:54:DC:C8:65.
The stock installed DLL remains SHA256
`b0a0689946e03f6f7467b798fba4678018bb28ba6b1caecdded8d08945049310`.

| Windows obligation | Actual result and boundary |
| --- | --- |
| Runtime preflight and side-by-side load | **Passed:** `frame-compare doctor --json`, GPU inventory and explicit `LoadPlugin` using the two frozen DLLs in fresh children. Existing stock remains installed. A separate log-level4 diagnostic records actual Vulkan device selection; comparison probes retain application log-level2. |
| Initial frozen paired screen | **Passed:** original-stock, unchanged-rebuild-fresh, patched-fresh and independent; each35 paired captures over direct/helper/forward/reverse/repeated/parallel. Native16 and final sRGB8 are exactly equal to original Windows stock. |
| Mastering/scene metadata, PQ inputs and RPU transitions | **Passed within synthetic scope:** three additional fixtures, same four controls and six histories, each35 captures. Includes missing-after-present metadata, all65,536 PQ16 codes and valid/zero/missing-L1/absent/malformed RPU transitions. Across initial and extended screens:560 paired captures,12 strict comparisons, zero differences. These are not measured epsilon/midpoint, native-counter recomputation or physical fault tests. Expected deprecated-property and malformed-RPU diagnostics remain in logs. |
| Constructor admission | **Passed:**11 invalid/unsupported inputs rejected; supported RGB48 HDR10-to-SDR constructed. |
| Real-media unchanged rebuild against original stock | **Failed at native16:** no-RPU Kill Bill frames12382 and14943 differ; respectively64 components/max12 codes and20 components/max8 codes. Frame0 and110257 match at both checkpoints in the initial four-frame sample. All four sampled final sRGB8 hashes match. Exact native16 remains required; matching final8 does not close this gate. |
| Failure attribution controls | **Passed as distinguishing diagnosis:** two original-stock captures repeat exactly, and two unchanged-rebuild captures repeat exactly. Patched-fresh and independent are bit-identical to the unchanged rebuild at both failing frames. A further input-tap experiment confirms identical actual RGB48 input samples and all recorded properties, matching kwargs/defaults, and repeats the same output hashes. The observed divergence precedes independent reuse; its exact compiler/dependency/shader arithmetic cause remains unresolved. |
| Paired no-RPU performance, real-media RPU, full console candidate journey | **Blocked/deferred after failed rebuild-equivalence prerequisite.** The guarded real-media driver exits1 after the first unchanged-rebuild comparison; its two render children exit0. No candidate speed claim, completed benchmark, real-RPU acceptance or Windows console/packaging acceptance is inferred. Earlier Windows stock timings and the Mac software-Vulkan paired timings retain their respective scopes. |
| Windows measured boundary/fault/lifecycle acceptance | **Still unverified:** no Windows-equivalent measured histogram/quantization diagnostic, native internal fault/warning/poisoning test, multi-source native-counter eviction proof, candidate SIGINT/owned teardown or allocation/VRAM attribution. Linux ELF interposition and glibc accounting do not provide these Windows observations; Windows-compatible diagnostic hooks/accounting are prerequisites. |

The real-media probe reads the existing owned Kill Bill HDR file and strips RPU
only in the disposable graph. Exact file size/mtime, index SHA256, source properties,
resolved kwargs and decoded RGB48 hashes are in the retained receipts. It copies
the decoder index into an owned scratch directory, verifies the original index
unchanged and removes its scratch copy after every child. No original film, index,
user configuration or shared cache was replaced. No new media copying occurred.
All launched native children have bounded exit receipts with no native timeout.
The optional OS process inventory was denied by Windows; that check is unavailable,
not proof of zero processes (`owned-processes-after.json`). Earlier inspection
encoding/path-access errors and their recoveries are retained separately.

Reproduction commands, invocation/exit receipts and adaptations are retained:
`run_screening.py` invokes the unchanged bundled paired harness; `run_extended.py`
uses its strict comparator with the Windows-portable extended fixture;
`run_real_media_windows.py` records the failed gate; `run_real_media_diagnostic.py`
and `real-media-input/commands.json` record repeatability and actual input proof.
The supplied PowerShell driver's literal79c52a6c HEAD guard was not executed or
silently bypassed: the owned Python driver explicitly verifies current/frozen
source equivalence, clean affected source and frozen DLL/harness hashes instead.
The extended fixture removes only the Linux-interposer `_FCNativeRender` assertion
and corrects descriptive fields; it makes no Windows native-counter claim.

`synthetic-summary.json`, `real-media-diagnostic/mismatch-summary.json` and
`real-media-input/comparison.json` record reductions. Full original-stock arrays
for the two failing frames and lossless XOR deltas retain every compared sample;
reconstruction was verified exact before removing duplicate array containers.
`array-storage-receipt.json` records reduction from465.53MiB to78.11MiB without
losing native16 or sRGB8 samples. This changes storage, not the zero-tolerance gate.

**Adoption is blocked first by the demonstrated Windows rebuild-equivalence
failure**, then by remaining Windows-specific lifecycle/fault/boundary/performance
and shipped capability-selection/packaging obligations. Resolve the native build
variance against original Windows stock before resuming the stopped acceptance
sequence; do not redefine the oracle or relax tolerance. No new application bug
or reuse-specific pixel divergence is established by this failure. The current
sRGB correction, fresh-node policy and tone-map defaults remain unchanged.
No signing, credential migration, protected dispatch, PR merge, tag or publication
was performed; protected signing and unrelated earlier gates remain separate.

### Windows rebuild variance diagnosis — 2026-10-21

Continued at the same12cb7f54 checkout and unchanged79c52a6c application source.
Installed stock and frozen unchanged/patched DLLs retain the hashes above. No
product code, default tone controls or native binaries were changed. This section
supersedes the earlier four-frame real-media final8 observation only for its
expanded cases; earlier native16 failure and other platform scopes remain valid.
Evidence and executable diagnostics are retained at
`generated/verification/2026-10-21/windows-rebuild-diagnosis/`.

**Build-path distinction established:** installed stock is byte-identical to the
pinned2.0.4 wheel (wheel SHA2563715ee44db698a52334a9a4be61ef29bd6d06d3d491eb905b2af7a4193d27411).
Embedded markers and its pinned upstream Windows recipe identify MSYS2 GCC16.1 /
UCRT64 lineage; the cross-build uses GCC14 / msvcrt. Runtime trace logs prove
stock actually selects **shaderc** and the unchanged rebuild selects **glslang15.2.0**.
Both report libplacebo7.371/API371. All10 publicly logged GLSL source blocks match
byte-for-byte. Pinned libplacebo adapters request shaderc performance optimization
versus glslang size optimization. These establish differing compilation routes;
identical GLSL does not establish identical SPIR-V, dynamic uniforms or CPU LUT data.
`build-provenance.json`, `compiler-logs/excerpt.json`, `shader-sources/comparison.json`
and the retained pinned compiler sources distinguish observation from inference.

| Diagnostic | Actual observation and limit |
| --- | --- |
| Decoder-free replay | **Passed as reproduction:** full RGB48/props fixtures12382/14943 match prior actual native-input taps; new5000 fixture reproduces the broad test's complete native16/final8 hashes. Three full frames and kwargs are exported, avoiding full-movie/decoder/index prerequisites for build diagnosis. Single-still replay reproduces the mismatch without prior request history. |
| Broader real-media defaults | **Completed with exact-equivalence failures:**46 no-RPU plus8 retained-RPU frame/profile pairs, native-resolution3840x1600. All settings, effective transform, kwargs and original media/index identities match. Native16 differs on36/46 no-RPU frames (1332 components/max45) and4/8 retained-RPU frames (73/max12). FinalRGB8 differs on exactly1 component of1 no-RPU frame; the other53 final frame/profile outputs match. This is one film and selected positions, not whole-film or visual-quality equivalence. |
| Final8 witness | **Reproduced:** frame5000, red/y144/x1154 is254 stock versus253 rebuild. Native16 is65150 versus65142; corrected sRGB float times255 is253.5304364562 versus253.4998860955. Opposite sides of253.5 explain the final quantization difference. Fresh patched and independent outputs match unchanged rebuild exactly at native16/corrected-float/final8. No new reuse-specific difference is observed in this case. |
| Actual PNG writer | **Passed as impact reproduction:** current `_render_vs_pillow` writes both native-resolution5000 PNGs, without overlay or geometry transform. Both declare sRGB and exactly match captured finalRGB8. The PNG active pixels retain precisely the single254→253 component. Their file hashes and actual commands are in `writer-witness/summary.json` and `commands.json`. This is not full CLI/report/resizing or calibrated-display acceptance. |
| Stage controls | **Diagnostic only; defaults unchanged:** gamut0 removes all differences on12382 and5000. Contrast0 removes all on12382; on5000 it removes the final8 difference but leaves2 native16 components/max4. Peak-detection0 on12382 still differs (33 components/max9). This narrows the relevant gamut/contrast processing path and does not justify changing those settings. |
| Synthetic colour sensitivity | **Completed with differences:** two64-cubed PQ colour grids (448/1000nit endpoints) and a seeded448nit random palette,512x512. Native16 differences155/max190,125/max57,162/max194; final8 differences1/0/3 components, all max1. These are artificial numeric stress inputs, not film quality examples or a tone-map ranking. |
| Portable Windows handoff tooling | **Passed:** explicit hash-bound side-by-side stock and unchanged replay tools reproduce all three5000 checkpoint hashes on this PC. Their strict comparator intentionally exits1 for the known mismatch (native75/max12, float75, final8 one/max1). Linux pixels are never Windows golden expectations. |

**Cause remains bounded:** differing shader/SPIR-V compiler and optimizer routes in
the gamut/contrast path are the leading explanation. CPU-generated LUT/CRT/math
variation is not excluded. The frozen source generates identical public GLSL;
there is no demonstrated decoder, alignment, sRGB conversion or reuse-state cause
for these reproduced differences. A controlled unchanged Windows build enabling
shaderc while preserving other frozen build inputs is required to isolate causality.
This host has no discovered C/C++ cross-compiler, CMake, Meson or Docker on PATH;
the recorded MacBook Docker builder is the prepared build route. A compiler inventory
is a prerequisite observation, not a request to replace the Windows environment.

`macbook-handoff/` contains README, a self-contained Mac task prompt, original stock
and unchanged Windows DLLs/licenses, exact decoded inputs, default kwargs, public
shader logs/sources, Windows goldens, paired reductions, actual PNGs, and tested
replay/comparison tools. The complete original native-build ZIP remains the source
archive/recipe authority; its exact hash is in the prompt. The requested Mac variant
changes only shaderc availability initially, retaining glslang and all capabilities.
Return new hashes and full build receipts; test back on original Windows stock.
Do not replace the frozen artifacts, change tone defaults, drop DOVI or relax the
zero-tolerance acceptance gate. Native internal/fault/lifetime/VRAM/selection and
protected-signing gates retain their earlier dispositions.

Full broad-test NPY references were temporary:108 owned arrays (2.78GiB) were
validated against recorded active-array hashes before removal. Per-frame reference
and actual hashes, difference counts/locations and command receipts remain; the
new final8 witness is independently replayable from its exported input and full
PNGs. Other retained native/float captures are stored losslessly with verified XOR
reconstruction where useful (`lossless-storage.json`). Original source/index remain
unchanged and all owned decoder-index scratch copies were removed. The first input
collector's property-container comparison failed after its RGB hash matched; JSON
normalization and the prior `_AbsoluteTime` exclusion fixed that diagnostic check.
Its failed attempt and cleanup are retained, not counted as product failure.

The verified handoff ZIP is
`frame-compare-windows-rebuild-diagnosis-mac-handoff-2026-10-21.zip`,
93,765,545bytes, SHA256
`5305b60670a7810b04400271fb21b74581af80064cfc0a8c9763ba4d32d0b4d9`.
CRC, all106 member-manifest hashes and complete member accounting passed.
Its canonical-ledger snapshot includes all substantive evidence above and precedes
this final archive-identity paragraph (`handoff-transfer.json`).

These findings show sparse numeric differences reaching final image bytes; they do
not demonstrate the broad HDR blowout or establish fidelity against an independently
graded SDR release. Tone-map quality selection remains separate. No adoption,
performance claim, installation replacement, signing, release or publication occurred.

### Windows UCRT equivalence and native acceptance — 2026-10-22

This dated reconciliation supersedes the earlier **current adoption blocker** of
Windows rebuild equivalence for the UCRT candidate identified below. Earlier
msvcrt failures, cross-driver golden differences and Linux-only acceptance retain
their historical scope. No tolerance was relaxed and no historical golden was
overwritten. The current same-driver stock comparison passes; NVIDIA version
621.01 is **not a blocker and does not require rollback**.

Source remains `v0.7.0` at `12cb7f54a692aea34e600fc7fd2ac875c68a883e`, application
`src` tree `704ea71074278ddc4d139e27b7d1e2d24f3f2270`. Environment is Windows 10
build19045, Python3.13.7, VapourSynth R81, RTX5080 and NVIDIA621.01. The installed
driver, stock plugin, application source, tone settings, source film and original
decoder index were unchanged. Candidate selection occurred only in owned child
processes; the application still uses the fresh-per-frame implementation in
`src/frame_compare/vs/tonemap_libplacebo.py::_independent_frame_tonemap`.

Binary SHA256 identities:

- Installed stock: `b0a0689946e03f6f7467b798fba4678018bb28ba6b1caecdded8d08945049310`.
- UCRT glslang: `1b791acc9c21f2fc3fcf5183d1b583fd88fa91b796663a4e3192585e641de130`.
- UCRT shaderc: `7e4336007fbff9a4095c621d4c9a61837be46eb7fa6b0c7c526f14b45b55cd26`.
- **Patched UCRT shaderc under consideration:**
  `33a6ce9743e63ced306c9038263f742e339fd3eefef9460c0897b1dbc7d7fe6c`.

**Build variance and historical goldens:** repeated installed-stock captures on
621.01 are exact within that runtime but differ from the retained617.14 goldens,
despite matching stock DLL, decoded RGB48 inputs, properties and kwargs. All ten
publicly logged stock SPIR-V blocks match across the two captures. A driver/runtime
change is a leading explanation for that separate historical drift; causation was
not isolated by rollback. On the same current driver, switching only shaderc
availability in the msvcrt build does not remove its mismatch; both UCRT variants
match fresh stock. This supports the CRT/build route as the distinguishing factor
for the rebuild variance and supersedes the earlier leading shader-compiler
attribution. It does not isolate an individual math function or prove all dynamic
uniform/LUT contents equal from SPIR-V alone. The msvcrt frame5000 negative control
still differs at all three checkpoints, including one RGB8 component by one code.

| Windows obligation | New evidence and disposition |
| --- | --- |
| Broad exact equivalence | **Passed:** fresh stock, UCRT glslang, UCRT shaderc, patched fresh and patched independent; each54 pairs (46 no-RPU,8 retained-RPU selected positions from one film). Same-evaluation native16, corrected-float and RGB8 match with zero differences; input hashes/properties, source/index identity, settings and kwargs agree. |
| Palette equivalence | **Passed:** all four candidate paths match fresh stock on cube448, cube1000 and seeded random448 palettes at all three checkpoints. These are numerical stress cases, not visual-quality or whole-film acceptance. |
| Request history and RPU/metadata transitions | **Passed:** stock, UCRT shaderc, patched fresh and patched independent each140 linked native16/RGB8 captures over four fixtures and six histories (direct, helper-first, forward, reverse, repeated, parallel). Includes every PQ16 code and valid/zero/missing-L1/absent/malformed RPU. Additional full-resolution mixed histories give12 requests per mode for stock/patched fresh/independent, exact at all three checkpoints. |
| Actual native recomputation and eviction | **Passed:** raw `_FCNativeRender` counters with caching disabled give fresh1 per request and independent1–6 for `[8,2,1,2,0,2]`, with equal native16. Under ordinary1MiB automatic caching, first target1, immediate hit1,48 distinct intervening frames, recomputed target50; native16/RGB8 remain exact. |
| Source isolation and admission | **Passed within synthetic scope:** two differing pixel/metadata sources and RPU transitions, six interleaved plus four concurrent requests, exact native16/RGB8 against patched fresh. Eleven unsupported/invalid constructors rejected; supported RGB48 HDR10-to-SDR constructed. |
| Native fault/warning/poisoning | **Passed within injected scope:**25 CDB case/policy runs plus six follow-ups cover allocation, Vulkan/renderer admission, texture, upload, render, download, packed-host allocation, shader, LUT, peak-buffer read, GPU-status and health-latch paths. Real WARN callbacks (one/four thread-pool invocations) and a real numeric ERR callback reject independent output at visible log level0. Second requests stay permanently unhealthy; replacements succeed; monitored create/render/upload/download entries are absent on poisoned retry. Fresh replacement recovers; legacy fresh LUT failure can emit different fallback pixels and is not called equivalent failure behavior. |
| Native cleanup and resource samples | **Passed for observed cleanup/parity, resource acceptance qualified:** successful Vulkan/renderer creations balance non-null destruction in all31 fault/control runs. Three200-frame resource runs (fresh, independent recreated every5 frames, persistent independent) give600 exact native16 outputs and expected render counters. Separate allocator logs show zero used/reserved pooled slices at teardown across6/2/1 contexts; dedicated allocations are excluded. |
| Windows interruption/drain | **Passed at native diagnostic graph scope:** real `CTRL_BREAK_EVENT` arrives with8 requests pending in each mode; all8 drain with equal native hashes and expected counters, children exit cleanly. Observed drain1.414s fresh/0.287s independent. This does not establish installed-CLI Ctrl+C handling, failed-record/report persistence or GPU preemption. |
| Paired graph performance | **Passed as a bounded measurement:** one warmup pair plus five alternating measured pairs,52 requests per child. All624 request hashes match current fresh-stock RGB8. Full child wall medians63.303s fresh (60.283–65.738) and25.841s independent (24.365–27.099); independent wins every pair,56.95–61.34% less wall time. Sum-of-`get_frame` medians59.125s/21.758s; fresh52 versus independent2 factory constructions. Two decoder/native graphs are of the same film, RPU stripped; warm caches, fixed section order, non-isolated host and active overlays. No installed-CLI or isolated GPU-kernel speed guarantee. |

**Resource finding, not a new reuse regression:** in the200-frame sample, settled
fresh handles grow about25 per five-frame cycle; repeated independent grows5 per
cycle; persistent independent stays392 after warmup and drops to329 on teardown.
Host-private samples retain driver/process caches and modest variation; they do
not prove a universal leak-free bound. A separate36-frame comparison reproduces
the same per-context retention in **installed stock and patched fresh**. Over nine
settled stock cycles,81 events,27 mutexes and27 sections remain: three events,
one mutex and one section per destroyed context, still present after two seconds.
The retained mutex's open stack passes through NVIDIA ShadowPlay
`nvspcap64!QueryShadowPlayDdiShimInterface`; this does not independently attribute
every event/section or establish when the behavior began. Installed overlays were
not disabled. This existing-stock behavior needs a bounded lifetime/risk disposition,
not an assumed candidate-specific fix or a driver rollback prerequisite.

DXGI identifies the RTX5080 but reports zero local usage and constant278528-byte
nonlocal usage after initialization, so it does **not** establish physical Vulkan
VRAM ownership. Native pooled-slice accounting and balanced wrapper destruction
close narrower obligations; dedicated allocations, residual host ownership and
physical-device behavior remain qualified. CDB return/state injection modifies
only owned child memory, not DLL files or the physical driver. Thread-pool callbacks
under debugger stops are not a race-detector result. An overly broad mutex-stack
probe triggered the strict slow-device WARN guard through instrumentation overhead;
its rejected attempt is retained, and the narrower mutex-open trace passed. Setup
pilots and this observer effect are not counted as successful acceptance cases.

**What still blocks adopting patched UCRT independent mode:**

| Remaining adoption obligation | Concrete closure needed |
| --- | --- |
| Windows numeric boundary acceptance | **Remaining seam: actual shader float before original UNORM16 conversion**, with same-pass target/download linkage, observer-off parity and a deliberate shader-effect control. The later Unit A observation below closes measured Windows peak-histogram/float32 epsilon and downstream RGB8 midpoint checks; do not rerun them merely to add the native16 observer. |
| Product capability selection and error policy | **Experimental integration passed below:** default-off runtime selection binds actual canonical plugin/signature/path/reviewed digest and admitted inputs, preserving supported old/unknown/unsupported paths, sequence/settings/fallback and late poison propagation. Automatic production selection remains deferred until numeric/distribution/matching-source gates close; the experimental opt-in is not automatic adoption. |
| Windows production CLI acceptance and profiling | **Actual ordinary source-CLI acceptance passed below**, including same-binary safety child, RPU/sparse/distinct-source PNG/report parity, late ERR/clean JSON, real Ctrl+C, failed persistence/partial outputs and five profiling pairs. It uses an owned canonical runtime without factory substitution. Supported full portable/wheel distribution acceptance remains separately scoped; source CLI success alone cannot close it. |
| Bounded resource acceptance | **Native requested-memory ownership now passed within Unit A's bounded workload**, including dedicated allocations and source teardown. Actual CLI source lifetimes retain their own acceptance scope. Stock-shared ShadowPlay handles are an existing external-retention risk, not a demonstrated reuse regression or a requirement to roll back the driver. Physical residency, all driver caches and universal leak freedom are not established or imposed as new blanket adoption prerequisites. |
| Reproducible distribution and matching-source gates | Bind the selected DLL to reviewed patch/dependency/toolchain/UCRT identities and package/select it through the supported runtime; verify capabilities/licenses/layout and the actual candidate artifact on Windows. Run the integration's required matching-source checks. The last recorded full native/unsigned Windows gate failed and artifact build was skipped; earlier stock Docker/portable successes cannot accept a newly integrated candidate. |

The driver version, the resolved UCRT sampled equivalence gate, the observed
same-driver graph speedup and already-passed representative poisoning/recomputation
checks are **not remaining blockers**. Complete physical device-loss causation,
universal whole-film equivalence and protected signing/release are not inferred
from these tests; protected publication prerequisites retain their separate scope.
This reconciliation records evidence and the remaining implementation/acceptance
work; it does not adopt, install or publish the candidate.

Canonical receipts are local under `generated/verification/2026-10-22/`:

- `windows-build-diagnosis/` and `stock-golden-investigation/findings.md` retain
  the controlled build comparison, repeated stock and historical-SPIR-V diagnosis.
- [Broad parity report](../../generated/verification/2026-10-22/ucrt-broad-validation/summary.md)
  and `final-summary.json` retain the54-pair/palette/history reductions and commands.
  `frame-compare-ucrt-broad-reuse-results-2026-10-22.zip`:60,120,193bytes, SHA256
  `c61cc4d27caef29184c9c01457f22abd780d556d8158c607d451e8b8612ce1c9`.
  Compact transfer omits full-size stock NPY arrays, which remain locally.
- [Native acceptance report](../../generated/verification/2026-10-22/ucrt-native-acceptance/summary.md),
  `summary.json`, raw commands/logs and `verify_receipts.py` retain native counters,
  fault controls, callback levels, resource/allocator/handle stacks, cancellation
  and benchmark reductions. `frame-compare-ucrt-native-acceptance-2026-10-22.zip`:
  1,456,726bytes, SHA256
  `e2de0b441a56cb0796d75ae74a22ffea8ebaff974441c06c776c9e1915eb4246`,598 members.

Both archive CRCs and SHA256 identities were rechecked for this ledger update;
the native packet's retained receipt assertions passed again without GPU work.
No native, performance or whole-suite rerun is implied by this documentation edit.
All earlier ledger entries and unrelated VSView plans were preserved.

### Windows measured boundaries and allocation follow-up — 2026-10-22

Under the user-authorized separate-chat Windows completion workflow, Unit A
(`01a162a9-0d97-7c41-bda1-edfbabd3f0f2`) completed native observations against the
same reviewed UCRT DLL and froze its source state before integration edits.
Application HEAD/src tree, stock/candidate hashes and NVIDIA621.01 retain the
identities in the preceding section. Installed driver/plugin/overlays, original
media/index and product source were unchanged by Unit A. All27 final native jobs
exited normally, without timeout/forced termination; GPU ownership was released.
The controller inspected the observer/reducers and reran
`verify_results.py --manifest`: retained arrays, reductions, exact probe hashes,
negative controls, native identities and complete member accounting passed with
zero new GPU jobs.

| Additional Windows observation | Result and acceptance boundary |
| --- | --- |
| Real histogram and percentile | **Passed:** CDB copies the completed3264-byte public buffer read, using the pinned producer's12-slice/64-bin wire format. A captured public peak-state handle is read through `pl_get_detected_hdr_metadata` after the same render; public structure size/offsets are independently compiled from pinned headers. Each evaluation has exactly one peak read/state capture/public return; the explicit metadata read adds no peak read. Fresh/independent metadata equals the measured float32 reduction. All-code sweep percentile0.9999392032623291 differs from raw max1.0, so percentile interpolation is actually exercised. |
| Epsilon/state-sensitive controls | **Passed:** below-epsilon mean/peak delta0.00006103515625 retains first uniform sequence state; exact epsilon0.00006103888154029846 changes first low-PQ sequence state; above delta0.0001220703125 also changes state. Sequence public metadata differs on9/10 requests in each ten-frame fixture even though pixels match. Across low/uniform/all-code fixtures,63 observed plus84 observer-off/current-stock evaluations retain exact linked native16/corrected-float/RGB8 parity for fresh/independent; sequence is the distinguishing metadata control. No private instructions/layouts are inferred as runtime proof. |
| Downstream RGB8 quantization | **Passed:** actual float32-scaled witnesses below22.499990463256836→22, equal118.5→118, above190.50003051757812→191. All196,608 sweep components match float32 ties-to-even, including19 exact halves. Float64 multiplication of a stored float32 can place it on another side and is recorded separately. This is downstream of the native16 attachment. |
| Pre-UNORM16 shader midpoint | **Still open:** the verified DLL lacks a faithful same-pass preconversion side channel. Postprocessing/native16 reconstruction or a substituted float attachment cannot close it. A concrete separate Windows UCRT same-UNORM16-pass SSBO observer build and Windows-return acceptance contract is prepared for the MacBook. |
| Actual Vulkan memory ownership, including dedicated allocations | **Passed within measured lifetime scope:** public resolved `vkAllocateMemory`/`vkFreeMemory` arguments/results and dedicated `pNext` structures are observed, with public header/ABI compilation. Two cycles of64x32,1280x720,3840x1600 sources request `[0,1,0]` across absent/valid RPU. Stock fresh and patched fresh each300 allocations/300 frees,36 dedicated; independent102/102,12 dedicated. Every source teardown and final phase has zero observed live allocations/bytes. Both cycles repeat source peaks9,150,464/48,881,664/276,873,216 bytes; maximum264.046875MiB, dedicated subset113.4375MiB.54 observed and54 observer-off native frame hashes agree with stock. Removing a real free receipt is correctly rejected by the reducer. |

The new memory proof replaces the earlier **unobserved dedicated-allocation** gap
with actual native allocation/free accounting. It does not measure physical
residency, every driver-internal cache/allocation, residual host ownership or all
possible lifetimes. Existing stock-shared ShadowPlay retention remains separately
recorded; it has not been attributed to native reuse. Acceptance now targets actual
CLI source lifetimes rather than demanding a universal physical-VRAM/leak-free
proof. No physical driver corruption or overlay reconfiguration was performed.

Evidence is under
`generated/verification/2026-10-22/windows-ucrt-boundaries-resources/`:
`summary.{md,json}`, `boundary-analysis.json`, `allocation-analysis.json`, raw
readbacks/linked arrays, observed/off commands, ABI/source/provenance receipts,
`verify_results.py` and `MANIFEST.json` (1,208 accounted members,5,475,655 bytes).
`macbook-observer-requirements.md` specifies exact source/DLL hashes, same final
UNORM16 raster pass and target/download linkage, separate observer DLL, no changed
math/geometry, disabled/enabled parity and deliberate `1/65535` effect controls.
It is a build/return contract, not Windows acceptance of an unbuilt observer.
Corrected callback/setup and the initial float64-rounding analysis are preserved
as tool/observer errors; none is counted as a native pass or candidate failure.

Unit B's CPU proposal (`01a162a9-1b1c-7793-a6fa-a30f99559916`) was reviewed. The
controller approved a **default-off experimental runtime opt-in**, restricted to
the actual canonical plugin's verified signature/path/digest and admitted RGB48
PQ/HDR10-to-SDR inputs; retained base-layer RPU is admitted. It adds no persisted
tone setting, preserves old/unknown/unsupported paths and sequence behavior, and
does not constitute automatic adoption. Unit B now owns implementation and the
exclusive Windows CLI runtime after A's release. Those product/CLI changes are
**in progress, not yet accepted**; candidate wheel/native observer builds and the
matching-source Docker gate remain MacBook handoff work where unavailable here.
The detailed decisions and dispatch map are in
`docs/plans/2026-10-22-ucrt-windows-adoption.md`.

### Windows experimental integration and CLI follow-up — 2026-10-22

Unit B implemented the approved dormant native-still policy in
`vs/tonemap_runtime.py`, `vs/tonemap_libplacebo.py` and `vs/tonemap.py`, with
`tests/vs/test_native_still_policy.py` and existing architecture/runtime docs.
The uncommitted six-file implementation manifest is SHA256
`5999ee941ed5bd9765b0fbaa6db6c0357282e73667e90a2101f31900b35ba6b7`;
tracked diff SHA256
`e517cc12d385b0e66ba008702bd1d8897ccbec6ec148c49d4e36b29d8122bf41`.
The new test is untracked and separately inventoried/exported; tracked diff alone
does not include it. Source HEAD remains12cb7f54; the working source contains this
reviewed patch. Independent read-only Unit D found no actionable findings and
confirmed all six file hashes without identity drift. No Git integration occurred.

`FRAME_COMPARE_EXPERIMENTAL_NATIVE_STILLS=1` is default-off, not persisted and not
a tone/CLI config field. It requires canonical `com.vs.placebo`/`placebo`, exact
`independent:int:opt` signature token, actual loaded path and reviewed DLL digest,
plus fixed integer RGB48 PQ/HDR10-to-SDR/no-EL admission. Retained base-layer RPU
is admitted. Old/unknown/unsupported classes keep the fresh route; sequence and
tone controls, constructor fallback and late-error ownership remain unchanged.
The normal safety subprocess must identify the same candidate; its cache is bound
to that identity. No Python factory replacement, generic probe assumption or
`PYTHONPATH`-only override is counted as native selection proof.

| Actual Windows observation | Result and boundary |
| --- | --- |
| Focused/integrated checks | **Passed:**162 focused cases plus3 existing native history/sRGB cases through actual canonical candidate runtime, zero failures/errors/skips. Invalid opt-in gives actionable FC-4004/exit5 without raw supplied value. Ordinary console help/version import no VapourSynth; doctor JSON exits0. |
| Canonical ordinary source CLI | **Passed:** owned venv/VapourSynth package copies, original console entrypoint ZIP bytes with only its inspected UVSC interpreter trailer selecting owned Python, ordinary source imports through `.pth`. Actual plugin ID/path/signature/hash, owned decoder path and the application's real safety child agree. This proves the source-console journey, not a production portable artifact. |
| Success/routing parity | **Passed:** stock/candidate-fresh/candidate-reuse each12 real-film PNGs at6 sparse positions with retained RPU; separately encoded differing PQ sources stock/reuse each6 PNGs; old-stock-plugin opt-in6 exact PNGs on fresh route; HLG stock/opt-in each6 exact PNGs on unsupported-input fresh route. Exact active RGB bytes, PNG sRGB/dimensions, source frame/picture/RPU facts, settings/geometry and report identities agree. Film aliases establish two graphs; distinct generated PQ files separately establish source isolation. |
| Real native ERR and failed CLI output | **Passed within callback/poison scope:** after rendering starts, CDB captures the actual callback context through public log parameters and invokes the real strict native ERR2 callback at unchanged visible level2. Native poison rejects output; normal console exits5 with exactly clean FC-4013 JSON, sanitized failed record, no report and3 admitted stock-exact partial PNGs. ERR sentinel is stderr-only. Safety child runs normally; no mute/default change or bypass. This is not physical device loss or a failed GPU download. |
| Actual Windows Ctrl+C | **Passed:** owned hidden-console CTRL_C_EVENT with2 actual Cython native `get_frame` calls pending, exit130/empty stdout, failed record,2 exact admitted PNGs, pending calls drain to0, no report/new cache/diagnostic publication. The fixture clears only the owned process's inherited Windows Ctrl+C-ignore attribute before app startup; Python handler is unchanged. Exact main-handler timestamp is not exposed, so admission checks use the earlier signal-send time; no screenshot admission occurs after send. Not a specific GPU kernel/preemption or universal finite drain bound. |
| Actual CLI performance | **Passed as a bounded measurement:** warmup plus5 alternating same-candidate fresh/reuse pairs,2 aliases of one film, retained RPU,6 sparse positions/12 PNGs per child. All144 outputs/report facts match stock. Wall medians22.393s fresh (22.366–22.572) and14.711s reuse (14.450–15.310); render-phase medians20.212s/12.423s. Reuse wins all5 pairs,32.17–35.39% lower wall time. Wall includes app probing/writing/report/teardown, excludes host setup/reducers; warm caches, active overlays, non-isolated host. No multi-film or isolated GPU-kernel guarantee. |

Controller reran the CPU-only source/CLI receipt verifier successfully, rechecking
the exact source manifest and actual PNG/report/fault/cancellation/profile facts.
Original-media size/mtime and index SHA remain unchanged; no new whole-film hash
was computed. Marker-owned hardlink/scratch aliases were contained and removed.
Known diagnostic PIDs were no longer openable, not a global process census.
Installed stock DLL and NVIDIA621.01 retain the recorded identities. Tool/setup
and initial ineffective injection/signal attempts remain rejected attempts in the
receipts, not added native passes. Evidence:
`generated/verification/2026-10-22/windows-ucrt-integration/implementation-report.md`,
`verification-summary.json`, commands, raw accepted CLI04 controls,
`profile-summary.json`, `verify_integration_receipts.py`; independent review is
`windows-ucrt-review/review.{md,json}`.

**Combined matching-source Windows checks:** global Pyright (zero warnings),
Ruff/check-format, Bandit and import contracts pass. The normal `uv` launch was
blocked before tool execution by inaccessible uv cache metadata; direct locked
`.venv` tools were used. Ruff required `--no-cache` for an inaccessible existing
root cache. The full suite completed **4198 passed,9 failed,77 skipped**; all34
new policy cases passed. Eight failures match the six recorded baseline failures
and two registry-access gaps (xdist group suffixes normalized). The additional
live-Matroska known-offset alignment case passed isolated retry; its full-run
failure is retained without assigning a cause. The full run also hit a final
protected pytest-cache write. This is **not a green full gate**, and skips are not
acceptance. Logs/JUnit/source-stability/skip accounting are under
`windows-ucrt-orchestration/combined-direct/`; the isolated retry used an owned
cache and retained its JUnit. No unrelated failure was silently fixed.

**Windows wheel assembly:** Unit C assembled an honestly downstream/local
`vs_placebo-2.0.4+fc.ucrt.20261022-py3-none-win_amd64.whl` from the unchanged verified
DLL; two independent assemblies,80-member RECORD/CRC/metadata checks, tamper
negative control and private no-index/no-deps installation pass. Wheel7,227,421bytes,
SHA256 `dd96afd44751d3e2e5ac22010607699b1a351520bb016a15a47a249158ef3349`.
Companion frozen-source-inputs ZIP25,713,919bytes, SHA256
`87775560eb1f37c9bf9fd23bf6c4f893e416be62f0e427bb25f356d5f5e79360`.
This proves assembly, not native source rebuilding. Actual linked Cargo/runtime
source/notice closure remains incomplete; a lockfile containing dev/optional
dependencies does not identify the linked subset. Preserve applicable required
sources/notices/exceptions without inventing an aggregate license or demanding
irrelevant development dependencies. `windows-ucrt-wheel/report.md`, `verify.py`
and source availability inventory retain exact gaps. Parent reran verification.
**Bounded wheel-backed canonical CLI follow-up passed:** the exact local wheel was
installed offline/no-index/no-deps into a new empty non-symlink owned target,
then supporting VapourSynth files were materialized excluding the wheel's native
member. Its local distribution metadata and all80 wheel/84 installed RECORD
members verify. Actual canonical plugin/path/hash, owned decoder and ordinary
safety child agree; no copied-over official-wheel identity or factory override.
One real/RPU ordinary console run gives12 active-RGB/sRGB/source/settings/geometry/
report facts exact to stock, no fallback, two experimental selections and one
normal same-binary safety confirmation. Help/version stay native-import-free.
Parent reran `wheel_followup.py --verify-only`; B released runtime ownership.
Evidence is `windows-ucrt-integration/wheel-followup/`. No production lock,
portable manifest or full-runtime fingerprint was changed to relabel stock.

Remaining handoff work is the separate pre-UNORM16 native observer/build and Windows
return acceptance, native source/build/linked-dependency package provenance and
applicable source/notice closure, final matching-source Docker proof, and coherent
supported artifact/runtime-identity acceptance before automatic adoption. The
current global Windows gate remains red as recorded. No installed driver/plugin,
registry/user configuration, overlay, protected signing, push or publication was
changed by the experimental integration/assembly work.

The final transfer is
`generated/verification/2026-10-22/frame-compare-ucrt-macbook-handoff-2026-10-22.zip`,
80,733,247bytes, SHA256
`dfac69a1de4c064087859c382ca21fb05d4f997aa36c027dc1e1a90b252ccefa`.
All2,067 members, CRC,2,066 manifest hashes/sizes and complete accounting passed.
The checked source patch includes the untracked new test; before/after identity
also covers all204 application source members. `TASK.md` is the self-contained
MacBook prompt; `NATIVE_OBSERVER_TASK.md` is the remaining exact native seam.
The packet's canonical-ledger snapshot contains all substantive results above and
precedes this archive-identity paragraph. At that initial transfer, no source
commit, push, installed driver/plugin replacement or publication had occurred.
The Windows completion plan is
historical; the listed MacBook build/return and adoption gates remain open.

The subsequent committed-source refresh includes the implementation, new test,
this ledger and the Windows plan in one commit. Its packet retains the checked
patch and includes an incremental Git bundle. The exact commit, ZIP identity and
verification receipt are recorded in
`generated/verification/2026-10-22/windows-ucrt-orchestration/committed-handoff.json`.
Use that refresh for the MacBook continuation. This source-identity step does not
change the verified application bytes, native acceptance scope or installed
driver/plugin, and includes no push or publication.

### MacBook observer build, provenance and Docker follow-up — 2026-10-22

Continued on the MacBook from the verified Windows handoff (archive SHA256
`c85dcb2b23f141a9e0696261fb8024e841c4471a49ae6020485d3232c1ed110b`, 2,069 members).
The bundle verified, and `FETCH_HEAD` was `e193e955153630295f63bed2f0f1330990c412f8`.
After the user's pull, `v0.7.0` equals `origin/v0.7.0` at that commit (tree
`2008374067be439befa955bfccfca58c91f740d4`, `src` tree
`cf637961bb751dbbff4cb16ab75c95eddae51745`). The before- and after-state verifiers
passed. No product code, tone default, installed plugin or production fingerprint
changed. Evidence is retained at
`generated/verification/2026-10-22/mac-ucrt-observer/` and in its return ZIP.

| Check | Actual observation and limit |
| --- | --- |
| Same-pass UNORM16 observer DLL | **Built; Windows UNRUN.** Diagnostic `ucrt-shaderc-observer` SHA256 `d90f8b91ec55e90f0c7b8a022af373e2cd8588e91cbe7a2b1f0cf8f571eddc2f`, from the frozen UCRT/shaderc image `9f563b14…` and prefix. The three reviewed native files keep their hashes. One observer object is added to the plugin target, which is linked with `--wrap` for `pl_pass_create/run/destroy` and `pl_tex_download`. Disassembly shows every original call site (dispatch `finalize_pass`, `run_pass`, `pl_pass_run_vbo`, teardown, `VSPlaceboTMGetFrame`/`vspl_tonemap_filter` downloads) now reaches the wrappers, and the real functions are called only from them. Compile commands are otherwise identical (59/59), and imports and exports equal the candidate's. `FC_OBSERVER_MODE=off/on/effect` provides the controls. A stub-GPU selftest and pinned shaderc/glslang compilation of the instrumented stage-08 shader passed; these are not GPU acceptance. |
| Unchanged candidate and repeat build | **Candidate preserved; repeat build identical modulo link timestamps and checksum.** A fresh preparation and full deps/Rust/libdovi/plugin rebuild gives `05539216…`, which normalizes to `33a6ce97…` (8 bytes differ: COFF timestamp, export timestamp, PE checksum). A map relink also normalizes identically. Not bit-reproducible. |
| Linked dependency and notice provenance | **Closed with stated gaps.** The link map has 916 members from 19 archives; spirv-cross is not linked. libdovi links 12 normal crates (84 lock entries: 71 dev/optional unused, 0 build-only), retained with Cargo.lock-verified `.crate` files. Linked Rust std crates and their registry sources are identified. GCC runtime (Runtime Library Exception 3.1), mingw-w64 12.0.0-5 (ZPL-2.1 and per-file terms) and winpthreads are mapped from the actual link. A 52-component inventory and NOTICE file are provided. LGPL source obligations are vs-placebo, libplacebo and, conservatively, the VapourSynth headers. Unavailable: upstream GCC/binutils/mingw-w64 and rust-src tarballs (only `.dsc` checksums retained), a rebuild of Rust's prebuilt std objects, and a per-file license audit of vs-placebo/glslang/SPIRV-Tools. |
| Matching-source Docker gate | **Passed.** `bash tools/verify_docker_integration.sh` built a fresh image `sha256:14b0aed991403f9c02e6679746188d6411b5fdade2c8d13ec4813cd57d89cb10` and ran 340 passed, 0 failed, 0 skipped/xfailed/xpassed, with all runtime proof markers. The baked `src` equals HEAD across 205 files. The run was at the cherry-picked tree identical to `e193e955`. The streaming-resource gate is not required (no alignment changes) and was not run. Linux results do not establish Windows GPU behaviour. |

The Windows return driver `run_observer_acceptance.py` runs fresh stock,
candidate fresh/independent and observer off/on/effect in bounded child processes
on the 256×256 all-codes neutral PQ sweep. Its analyzer applies zero-tolerance
comparisons, target/run/download linkage, the orientation/channel check,
float32-vs-float64 midpoint witnesses, the ties-to-even prediction and effect
rejection. It was exercised on the Mac only with synthetic data and a stub child.
Independent mode remains default-off. Remaining adoption blockers:

- Windows observer acceptance
- supported artifact/runtime identity and Windows-only fingerprint migration
- the red Windows full suite
- the stated provenance gaps for any distributable artifact

The observer DLL is diagnostic only. No push, merge, signing, publication,
installation or default change occurred.

### Current HDR disposition

| Obligation | Disposition |
| --- | --- |
| sRGB correction, truthful properties, PNG declaration and report identity | **Implemented; passed within identified native/media/static scope.** |
| Independent still policy with unchanged tone settings | **Implemented; passed within sampled native/media/history scope.** Measured cost remains explicit. |
| Current full native gate | **Failed:** latest matching-source Windows run4198 passed,9 failed,77 skipped. Eight match prior baseline/registry cases; additional live-Matroska case passes isolated retry, with full-run failure preserved. All34 new native-policy cases pass; global static/type/import checks pass. |
| Matching-source Docker/runtime and unsigned portable artifact proof | **MacBook matching-source Docker passed** at the `e193e955` tree: 340 passed, zero skips, fresh image source identical. The streaming-resource gate is not required for this change. Earlier stock Docker: 306 native/media and 3 resource cases at the recorded merge SHA. **Unsigned Windows failed; artifact build skipped.** Earlier green artifacts retain earlier source scope. |
| fpng writer runtime, browser/profile and calibrated physical luminance | **Blocked** by the corresponding supported writer, browser/display-profile observation and measurement prerequisites. Numerical samples do not establish them. |
| Faster native still mode | **Implemented as default-off experimental UCRT reuse; not production adopted.** Reviewed capability/error-policy integration, actual ordinary Windows CLI parity/ERR/Ctrl+C,165 focused/native checks and5 CLI timing pairs pass (median22.393s fresh/14.711s reuse). Earlier same-driver54-pair/palette/history and measured native histogram/epsilon/downstream-midpoint/dedicated-allocation proof retain scope. Honest local wheel assembly and bounded wheel-backed canonical CLI acceptance pass. The MacBook built the same-pass observer DLL (Windows acceptance UNRUN), showed a repeat native build reproduces the candidate modulo link timestamps/checksum, closed linked-dependency/notice provenance with stated gaps, and passed matching-source Docker. Remaining gates are Windows observer acceptance, supported artifact/full-runtime identity, the red global suite and those provenance gaps for any distributable artifact. NVIDIA621.01 and stock-shared ShadowPlay retention are not assumed reuse-specific blockers; universal physical residency/leak freedom is not newly required. |
| Older Windows/MacBook acceptance | **Satisfied only within identified prior scope.** No blanket invalidation or new pass for changed pixels. |
| Protected signing, credential migration, release/publication | **Outside this work; no action performed.** Ordinary branch commits and automatic PR verification are separate. |
