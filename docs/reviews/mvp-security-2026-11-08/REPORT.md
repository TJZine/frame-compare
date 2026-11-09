# MVP security audit

- Audit date 2026-11-08
- Original audit base `e56f00a429ef494549cba153b2a7ff49230b2ea2`
- Remediation base `origin/v0.7.0` at `1ad19886efc1424a9e475a52f156c86f5013782a`
- Remediation branch `dev/mvp-security-hardening`

## Scope and method

This review covered application input handling, local file and process boundaries,
network publishers, generated state, Windows portable construction and updates,
GitHub Actions trust boundaries, Docker build inputs, dependency assurance,
release publication and operational security documentation.

The review used the repository production-review, security/privacy specialist,
build/release specialist, correctness/failure-mode specialist, reliability
specialist, tests/CI specialist and evidence-calibration procedures. The accepted
findings were converted through the remediation-plan procedure. Implementation
used the shared design, develop, review, verify, blast-radius and Frame Compare
acceptance procedures. Speculative findings without a reachable source path or a
concrete violated obligation were rejected.

The threat model treated media and archives as hostile, local environment values
as mixed-trust, hosted build artifacts as untrusted until independently verified,
the signing environment as privileged, and publication as a separate privilege.
No production secret, private media, live publisher account or installed user
runtime was used during the audit.

Severity uses S0 critical, S1 high, S2 medium, S3 low and S4 informational. No S0
finding was accepted.

## Accepted findings

### FC-SEC-01 — S1 — Media-adjacent decoder indexes crossed the data boundary

The VapourSynth/L-SMASH-Works source path could allow generated decoder index
state to live beside user-selected media. That location is outside Frame Compare's
owned generated-data root and can be pre-positioned, redirected or shared across
runs. A decoder index can affect how later media bytes are interpreted, so it is
not merely an expendable performance cache.

Remediation: all generated indexes use a private staged write, durable index bytes
and metadata-last commit beneath the generated root. Reuse requires
replacement-sensitive source identity (device, inode, size, mtime and change time),
geometry policy and probe identity, the native runtime token and the index digest.
Windows reads NTFS ChangeTime from the file handle and uses a write-capable
non-truncating handle for the durable flush. The loader and VSView share the
same owner. VSView re-establishes authority under the cache lease through the
native open.

Status: remediated in the candidate branch with focused cache, loader, VSView and
native-policy coverage.

### FC-SEC-02 — S1 — Signed release jobs combined incompatible trust roles

The prior release topology did not make the unsigned producer, independent
verifier, protected signer, package attester and publisher sufficiently distinct.
This increased the consequence of a compromised build job and made it harder to
prove that the key signed only independently approved bytes. Draft collisions and
publisher mutation ordering also needed fail-closed handling.

Remediation: split the chain into build, fresh-runner verification, final-artifact
security, protected manifest signing, packaging/attestation and key-free
publication. Every handoff uses an immutable artifact ID and digest. The publisher
paginates drafts, proves tag/release absence before mutation, rechecks the exact
remote body and assets before publication, and never receives the signing secret.

Status: remediated in the candidate branch with workflow-structure, release-chain,
artifact-binding and refusal tests. Hosted environment policy and secret-resolution
canaries remain release acceptance evidence rather than source-code claims.

### FC-SEC-03 — S1 — Portable runtime construction lacked inert byte authority

A normal package installation path can execute dependency build hooks and can make
the result depend on mutable installer behavior. Rechecking only the producer's
output would not establish independent authority for the shipped runtime.

The portable assembler stages exact lock-authenticated inputs and uses pinned
uv to install hash-verified dependencies from an offline wheelhouse. A
package-specific deterministic conversion builds the wheel for the pinned
`anitopy` 2.1.1 source archive without running build hooks. The assembler
retains archive safety checks, the Qt subset with WebEngine excluded, native
manifest pins, licenses and committed project metadata. A fresh verifier
independently reconstructs the tree and requires byte equality for the
canonical ZIP before the signed chain can proceed.

The candidate implements this control in `01f4019b`. Hosted Windows
reproduction for the simplified candidate remains a release observation.

### FC-SEC-04 — S2 — Child process output and inherited credentials were overbroad

Several application and diagnostic subprocesses used combined or unbounded output
capture. A hostile input or noisy tool could exhaust memory, deadlock on one pipe,
or leave children behind after timeout. Application children also inherited
unrelated parent credentials.

Shared process execution drains stdout and stderr independently under
separate limits, owns timeout/cancellation/nonzero cleanup and reports typed
failure. POSIX process groups and Windows kill-on-close Job Objects retain
ownership of their descendants after the leader exits. Windows uses normal
`Popen` followed by immediate assignment to a preconfigured job. The small
pre-assignment interval can let descendants escape, and an interrupt inside
`Popen` can prevent the caller from acquiring the child handle for cleanup.
Paired FFmpeg alignment and interactive VSView share this bounded cleanup owner.
The shared child environment filter removes known Frame Compare credential
variables, including the TMDB and slow.pics section JSON and credential-specific
nested variables. The benchmark streams bounded frame records.

The candidate implements the simplified Windows owner in `4b7d084f`.
Focused coverage includes overflow, timeout, malformed output, nonzero exit,
cleanup, credential filtering and a real FFmpeg sample. Physical Windows
cleanup remains an acceptance gate.

### FC-SEC-05 — S2 — Media-derived dimensions could allocate unbounded canvases

Image, frame and overlay dimensions cross decoder and renderer boundaries. Without
one consistent ceiling, small hostile inputs or forged metadata could request very
large Pillow, FFmpeg or VapourSynth allocations.

Source and VSView admission start with a bounded ffprobe header check for
exactly one real video stream. Cold and private cache-free opens, including
the VSView fallback, scan complete coded and visible frame geometry before
L-SMASH indexing or decoding. A real mixed-resolution H.264 transport stream
reproduced a native L-SMASH heap abort when admitted without that scan. Warm
managed opens can reuse the proof for positively recognized single-file
formats when the source identity, geometry policy version, ffprobe file
identity and reported program/library versions, native runtime token, and
index digest match. Referencing and unknown formats use the private full-scan
path on each open. L-SMASH playback receives an owned maximum-pixel option that
caller options cannot remove. Pillow, FFmpeg,
VapourSynth, batch expansion and overlay paths enforce the same limits.

The candidate implements proof reuse in `dca6af39` and restricts its scope
in `a66fbd70`. Focused tests cover cache binding, geometry and the caller
paths.

### FC-SEC-06 — S2 — slow.pics success accepted an under-bound response

The publishing path needed to prove that every requested comparison was represented
and that the returned result URL was the canonical HTTPS URL for the returned
identifier. Partial or inconsistent responses could otherwise be reported as a
successful publish.

Remediation: validate all returned comparison identifiers, reject missing, extra or
duplicate image identity before any image upload, construct the canonical URL from
the validated response identifier, and keep webhook delivery on its existing
no-redirect HTTPS policy.

Status: remediated with shortcut, publisher and webhook tests.

### FC-SEC-07 — S2 — Source and final-artifact advisory gates were incomplete

The normal CI and release path did not share an exact-revision source-security gate,
and the final portable bytes lacked an automated SBOM/advisory decision before key
use. A source-only dependency audit does not prove the content of the shipped native
runtime.

Remediation: reusable exact-SHA security CI runs maintained-owner Bandit/Ruff checks
and frozen dependency audits on Linux and Windows. The audit emits JSON and rejects
zero or malformed dependency coverage. The release caller requires that gate. The
final-artifact job safely extracts the exact independently verified ZIP and
runs checksum-pinned Syft and Grype. It checks scanner identity, requires
nonempty inventories and a fresh, size-bounded advisory database, and refuses
suppressions, unknown/high/critical severity and CISA KEV matches. The job
retains the unsuppressed evidence and receipt for 90 days. Signing requires a
successful policy result.

Status: remediated for source and Windows portable automation. Native component
identification/provenance review and evidence archival remain explicit human release
gates. A future distributed Docker image requires the equivalent immutable-digest
gate.

### FC-SEC-08 — S2 — Docker context admitted unnecessary repository material

A broad Docker build context can transmit local credential files or unrelated
repository content to the builder even when the final image does not copy them.

Remediation: credential patterns are excluded at the context boundary, the runtime
application-input stage copies only the committed README, license and application
source, and a synthetic sentinel test exercises Docker's real ignore and COPY
behavior.

Status: remediated with Dockerfile, ignore-policy, workflow and contract coverage.

## Residual release gates

The candidate code can be reviewed and merged without claiming that release
acceptance has already happened. Public distribution remains blocked until the
runbook's records are complete:

- Hosted Windows exact reproduction, artifact handoffs and protected signing,
  including approval and secret precedence. Obtain provenance attestations
  from the guarded release packaging job for both exact release ZIPs.
- Physical Windows Job Object cleanup, NTFS ChangeTime and index durability,
  PowerShell 5.1 and 7 install/update/rollback/refusal paths, GPU Vulkan/HDR,
  real-media checks and visible desktop UI acceptance tied to the bundle digest.
- Final-bundle native provenance, notices, corresponding-source offer, SBOM
  coverage reconciliation and advisory adjudication for embedded Python, Qt
  Multimedia, FFmpeg, VapourSynth and decoder/plugin libraries.
- Lifetime archival of the accepted SBOM, advisory, waiver and provenance evidence.

These are observable environment, platform and legal/provenance obligations. A
source review or simulated test must not be reported as satisfying them.

## Verification before simplification

The pre-simplification candidate's verification was recorded on 2026-11-09
in `34b7c5da`. Ruff lint and formatting, Pyright, the maintained security
script, import contracts, actionlint, strict docs,
workflow/portable structure tests, Docker-context containment and `git diff --check`
passed. The complete local non-browser suite passed with platform/capability skips
recorded. The full Docker media gate passed 427 tests with zero skips and proved the
installed non-root runtime, native plugin provenance, real frame rendering, software
Vulkan, production-tooling exclusion and an application journey. After the final
POSIX descendant-cleanup correction, that candidate passed its focused Docker
runtime/application journey with zero skips.

That macOS headless Chrome run had one fullscreen failure because the environment
refused the fullscreen transition. The remaining browser cases passed.
Windows Job Object, NTFS ChangeTime, protected signing and physical Windows runtime
claims remain in the residual gates above. The user-directed omission of further
active adversarial exercises is recorded rather than counted as evidence.

## Final integration and review

Independent defensive review of `6c17ca10` found two P2 issues. The review
identified no P0 or P1 issue and no release-chain integrity defect.

- Referenced-media manifests could reuse geometry proof keyed only to the
  manifest file. `a66fbd70` restricts reuse to positively recognized
  single-file demuxers. Referencing and unknown formats run the full scan and
  open privately each time. The full rebuilt Docker suite passed 495 tests
  with zero skips. The broader host suite passed 4,297 tests with 368 skips.
  The separate headless Chrome fullscreen refusal also occurs on the
  baseline.
- Desktop broker cleanup could kill a background handler after returning
  success. `ce672500` keeps the broker on the shared environment filter,
  silent and time-bounded, while allowing desktop handlers and clipboard
  selection owners to outlive it. The focused real delayed-handler and
  broker timeout/reap tests passed. The generic subprocess owner is unchanged.

A final P2 follow-up on `6adfa2c9` found that the shared filter removed nested
credential variables but passed through `FRAME_COMPARE_TMDB` and
`FRAME_COMPARE_SLOWPICS`. The normal config loader accepts credentials in
these JSON sections, and real subprocesses and a desktop browser handler
received both raw values. The shared predicate now excludes both names
case-insensitively, including after caller overrides, and snapshots their
complete raw values for diagnostic redaction. The loader control passed on
the old revision, while the subprocess, browser handler and diagnostic
assertions reproduced the leak. After the fix, all 361 focused config,
subprocess and desktop tests passed. A separate macOS run through the desktop
broker and pyperclip confirmed that a synthetic `pbcopy` received the
canonical URL and plugin path with neither credential names nor values.
The full local suite had one failure at the Chrome fullscreen transition,
which also reproduced on `6adfa2c9`. Platform and capability skips leave
native media and physical Windows acceptance open.

The review concluded that the release controls are proportionate for public
signed updates. Removing the pre-equality producer-archive traversal in
`portable_bundle.py` is an optional post-MVP simplification. Independent
reconstruction and canonical ZIP equality remain required.

All three findings are resolved. The orchestrator's next action is to update
PR #173. Further active adversarial exercises remain outside the authorized
scope. The release acceptance gates above remain open.
