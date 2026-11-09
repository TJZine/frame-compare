# Proportional MVP security simplification

Status: Active

This contract replaces the implementation choices in `IMPLEMENTATION_PLAN.md`
where they conflict with the decisions below. The accepted security outcomes remain,
but their implementation must be proportional to a single-developer desktop/CLI
application entering MVP.

## Source and workflow

- Target branch: `dev/mvp-security-hardening`.
- Current base: `origin/v0.7.0` at
  `1ad19886efc1424a9e475a52f156c86f5013782a`.
- Rebased security head before simplification:
  `34b7c5da0be04f9424534517b71b1bbd66f52031`.
- PR: #173 into `v0.7.0`. The orchestrator owns commits, force-push after
  rewritten history, PR text, and final acceptance.
- Implementation chats may edit only their assigned paths and must callback
  directly to orchestrator thread `01a1bd75-630d-7521-baed-2888a91541d2`
  on blockers and completion. They do not ask the user to relay messages.
- Do not merge, release, publish, use production credentials, or perform active
  red-team exercises.

## Outcomes that remain required

1. Media dimensions are bounded before application-owned allocations. FFmpeg and
   L-SMASH retain decoder-side pixel limits. User configuration cannot override
   those limits.
2. Generated L-SMASH indexes remain under Frame Compare's generated-data root,
   not beside selected media. Managed publication, source identity, and cache
   ownership remain intact.
3. Captured subprocess output remains independently bounded, credentials remain
   filtered/redacted, and timeout/cancellation cleanup remains explicit.
4. slow.pics identity/URL validation, Docker-context narrowing, pinned actions,
   source dependency checks, and exact artifact/check-out bindings remain.
5. The release signer remains isolated from build and publication authority.
   Final Windows artifacts remain inventoried and checked for unacceptable known
   vulnerabilities before signing.

## S1 — Media admission without a full-source pre-scan

Owned paths:

- `src/frame_compare/vs/source_admission.py`
- `src/frame_compare/vs/source.py`
- `src/frame_compare/vsview/session_runtime.py`
- directly corresponding VS and session-runtime tests

Required implementation:

1. Remove the mandatory `ffprobe -show_frames` scan of every source frame and its
   30-minute/128-MiB admission machinery.
2. Retain one bounded stream-header probe before L-SMASH admission. Require the
   supported real video-stream count and valid coded dimensions, while preserving
   the current attached-picture handling.
3. Retain source identity checks around admission/open where they protect a real
   time-of-check boundary. Do not copy arbitrary media into private storage.
4. Retain `bounded_decoder_options()` and ensure the owned `max_pixels` value
   cannot be absorbed or replaced by caller options.
5. Retain the central canvas policy at Pillow, FFmpeg, VapourSynth, overlay, and
   batch allocation boundaries. Variable in-bounds source geometry is handled by
   actual decoder/render behavior; do not reject an entire source through a
   preliminary full-file scan.
6. Remove tests and documentation that exist only for the full-frame admission
   scan. Keep focused header, source-change, option-injection, missing-stream, and
   boundary coverage.

Acceptance:

- Source opening no longer invokes `-show_frames` as an admission prerequisite.
- Existing normal source, HDR fallback, VSView, decoder-option, and canvas tests
  pass.
- Ruff and focused Pyright/test coverage pass.

## S2 — Proportional Windows portable and artifact assurance

Owned paths:

- `tools/windows_portable/portable_*.py`
- `tools/windows_portable/artifact_security.py`
- portable build/release PowerShell scripts
- `.github/actions/windows-portable-*`
- `.github/workflows/windows-portable*.yml`
- `.gitattributes`, `.pre-commit-config.yaml`
- corresponding Windows portable/workflow tests

Required implementation:

1. Delete the committed `release-runtime-files.json`, its pre-commit exception,
   byte-normalization rule, workflow presence checks, receipt field, and tests that
   treat the generated 8,086-file listing as independent human authority.
2. Preserve exact pinned inputs and the fresh-runner reproduction/byte comparison.
   A complete tree manifest may be generated and retained as build evidence, but
   it is not committed as a 41,000-line source artifact.
3. Stop implementing a general-purpose wheel installer in project code. Install
   exact local, hash-verified wheels through a conventional inert wheel-install
   path that does not run dependency build hooks or fetch undeclared inputs.
4. Handle the pinned `anitopy` sdist through the smallest package-specific,
   reviewable solution. Acceptable choices are a repository-owned reviewed wheel
   with recorded source/hash provenance, or a narrowly scoped deterministic
   conversion that does not execute its build hooks. Do not retain a custom
   installer for every dependency merely to handle this one package.
5. Preserve the deliberate Qt/WebEngine trimming profile, native component pins,
   deterministic archive production, safe extraction, complete-tree comparison,
   signer separation, artifact-ID/digest binding, and updater signature contract.
6. Keep checksum-pinned Syft and Grype, nonempty inventory checks, scanner identity,
   database validity/freshness, no hidden suppressions, KEV refusal, and blocking
   high/critical/unknown findings. Remove exhaustive revalidation of scanner-owned
   JSON schemas and every inventory object's private shape.
7. Keep one concise receipt tying the scanned archive, exact commit, verifier
   result, scanner versions, database identity, evidence hashes, counts, and policy
   outcome together.
8. Update affected tests to prove outcomes rather than private scanner schemas or
   the deleted catalog.

Acceptance:

- The committed catalog is gone and no runtime path references it.
- The portable build consumes only authenticated local inputs and never executes
  package build hooks.
- Fresh verification still reconstructs and byte-compares the portable ZIP.
- Artifact inventory/advisory policy remains fail-closed for empty evidence,
  stale/invalid database state, suppressions, KEV, and high/critical/unknown results.
- Workflow parsing, portable tests, Ruff, Pyright, and PowerShell parsing pass where
  available. Physical Windows runtime acceptance remains a release gate.

## S3 — Proportional process ownership

This unit starts after S1 because VSView tests overlap.

Owned paths:

- `src/frame_compare/utils/subproc.py`
- `src/frame_compare/services/alignment_streaming.py`
- `src/frame_compare/vsview/adapter.py`
- directly corresponding subprocess, alignment, and VSView tests

Required implementation:

1. Keep concurrent independently capped stdout/stderr draining, bounded diagnostic
   retention, cancellation/timeout/nonzero distinctions, credential filtering, and
   POSIX process-group cleanup.
2. Reassess the Windows `CREATE_SUSPENDED` plus Toolhelp thread-reopen implementation
   against the actual supported Windows contract. Prefer the smallest reliable
   Job Object owner. If pre-execution assignment cannot be implemented safely with
   the repository's existing dependency/runtime constraints, use a simpler explicit
   Windows tree-cleanup path and document the remaining race rather than shipping
   unverified low-level machinery as proven.
3. Isolate any retained Windows-native implementation from the generic pipe/event
   loop so ordinary subprocess behavior remains readable and testable.
4. Do not weaken bounded output or restore unowned descendants on timeout/cancel.
5. Keep only tests that prove distinct lifecycle obligations. Physical Windows
   behavior must be reported as unavailable unless actually observed.

Acceptance:

- POSIX real-child lifecycle and output-limit tests pass.
- Windows-specific structure/tests prove the selected implementation as far as the
  host permits; physical Windows acceptance remains explicit.
- Alignment and VSView callers preserve their cancellation and cleanup contracts.

## S4 — Integration, documentation, and review

Owned by the orchestrator or a fresh documentation/review chat after S1–S3.

1. Update `REPORT.md`, `IMPLEMENTATION_PLAN.md`, architecture/runbook/security
   documentation, changelog, and PR body so they describe the simplified design.
2. Remove superseded claims such as full-frame geometry admission, committed catalog
   authority, exhaustive scanner schema validation, or unobserved Windows guarantees.
3. Run focused package checks, then the applicable integrated Ruff, formatting,
   Pyright, security, import-contract, test, Docker, workflow, and docs gates.
4. Perform one fresh standard code/design review of the integrated diff. This is not
   an active adversarial exercise. Resolve material findings before updating PR #173.
5. Force-push the rewritten topic branch only after integration acceptance, then
   verify the live PR base/head/check state. Stop without merging or releasing.

## Completion signal

The change is review-ready only when the simplified design is implemented, the
working tree is clean, meaningful available checks pass, residual Windows/hosted
release evidence is explicit, PR #173 reflects the rewritten branch, and no omitted
platform or active exercise is represented as passing.
