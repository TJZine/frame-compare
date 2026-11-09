# MVP security audit

Audit date: 2026-11-08
Reviewed base: `e56f00a429ef494549cba153b2a7ff49230b2ea2` (`v0.7.0`)
Remediation branch: `dev/mvp-security-hardening`

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
runtime metadata and the index digest. Windows reads NTFS ChangeTime from the file
handle rather than treating creation time as a mutation stamp, and uses a
write-capable non-truncating handle for the durable flush. VSView re-establishes
authority under the cache lease through the native open instead of trusting a
serialized path. The loader and VSView paths share the same owner.

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

Remediation: the portable assembler now derives the runtime from the frozen lock,
pinned distribution archives and committed catalog without executing package build
hooks. It validates archive layout, file types, expansion bounds, wheel RECORDs,
the trimmed Qt/WebEngine profile and the complete output tree. A fresh verifier
reproduces and compares the canonical ZIP byte-for-byte before it can reach the
signer.

Status: remediated in the candidate branch. A real inert build reproduced the
402 MiB candidate ZIP byte-for-byte during development. Hosted Windows execution
against the committed candidate remains a required CI/release observation.

### FC-SEC-04 — S2 — Child process output and inherited credentials were overbroad

Several application and diagnostic subprocesses used combined or unbounded output
capture. A hostile input or noisy tool could exhaust memory, deadlock on one pipe,
or leave children behind after timeout. Application children also inherited
unrelated parent credentials.

Remediation: shared process execution drains stdout and stderr independently under
separate limits, owns timeout/cancellation/nonzero cleanup and reports typed
failure. POSIX process groups and Windows kill-on-close Job Objects retain
descendant ownership after the leader exits. Windows children start suspended, are
assigned to the job, and only then resume; paired FFmpeg alignment and interactive
VSView use the same owner. Application children receive a filtered environment,
with integration-specific credentials supplied only by their owner. The benchmark
frame scan is streaming and bounded instead of materializing an unbounded JSON
document.

Status: remediated with overflow, timeout, malformed output, nonzero exit, cleanup,
credential filtering and real FFmpeg sample coverage.

### FC-SEC-05 — S2 — Media-derived dimensions could allocate unbounded canvases

Image, frame and overlay dimensions cross decoder and renderer boundaries. Without
one consistent ceiling, small hostile inputs or forged metadata could request very
large Pillow, FFmpeg or VapourSynth allocations.

Remediation: source and VSView admission require ffprobe to prove exactly one real
video stream, then stream every video frame's coded and visible geometry through
bounded output. Each admitted stream must retain constant dimensions inside the
central axis and pixel policy before L-SMASH indexing or decode. L-SMASH playback
receives an owned maximum-pixel option that caller options cannot remove. Pillow,
FFmpeg, VapourSynth, batch expansion and overlay paths enforce the same limits.

Status: remediated with boundary, malformed-record and caller-path coverage plus
the normal Docker native-media gate. At the user's direction, active crafted-input
crash reproduction and further red-team exercises were omitted because the
available Daybreak environment repeatedly blocked that work.

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
final-artifact job safely extracts the exact independently verified ZIP, runs
checksum-pinned Syft and Grype versions, pins and validates the Syft 16.1.12 and
CycloneDX 1.7 document contracts plus source/package/component identity, rejects
stale or invalid advisory data, empty inventories, suppressions,
unknown/high/critical severity and CISA KEV matches, then retains the unsuppressed
evidence and receipt for 90 days before the signer can run.

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

- Hosted Windows rebuild/reproduction, artifact handoff, protected-environment
  approval/secret precedence and provenance attestation against the final commit.
- Physical Windows PowerShell 5.1 and 7 install, update, rollback and refusal paths,
  plus real GPU Vulkan/HDR and real-media acceptance tied to the bundle digest.
- Native component provenance, notices, corresponding-source offer, SBOM coverage
  reconciliation and advisory adjudication for embedded Python, Qt Multimedia,
  FFmpeg, VapourSynth and decoder/plugin libraries.
- Lifetime archival of the accepted SBOM, advisory, waiver and provenance evidence.

These are observable environment, platform and legal/provenance obligations. A
source review or simulated test must not be reported as satisfying them.

## Candidate verification record

The integrated candidate was rechecked on 2026-11-09. Ruff lint and formatting,
Pyright, the maintained security script, import contracts, actionlint, strict docs,
workflow/portable structure tests, Docker-context containment and `git diff --check`
passed. The complete local non-browser suite passed with platform/capability skips
recorded. The full Docker media gate passed 427 tests with zero skips and proved the
installed non-root runtime, native plugin provenance, real frame rendering, software
Vulkan, production-tooling exclusion and an application journey. After the final
POSIX descendant-cleanup correction, the current source passed its focused Docker
runtime/application journey with zero skips.

The macOS headless Chrome baseline still has one fullscreen failure because that
environment refuses the fullscreen transition; the remaining browser cases pass.
Windows Job Object, NTFS ChangeTime, protected signing and physical Windows runtime
claims remain in the residual gates above. The user-directed omission of further
active adversarial exercises is recorded rather than counted as evidence.

## Review state

The integrated candidate must pass the verification matrix in
`IMPLEMENTATION_PLAN.md` and a standard defensive code/security review before the
branch is presented for inspection. The originally planned active adversarial
reproduction was stopped at the user's direction after repeated Daybreak policy
blocks; no omitted exercise is represented as passing. The orchestrator owns
finding adjudication, commits, push and PR creation; it does not merge or release.
