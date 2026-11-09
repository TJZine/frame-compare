# Approved MVP security implementation contract

This contract records the remediation requirements derived from
[the accepted findings](REPORT.md) and incorporates
[the simplification decisions](SIMPLIFICATION_PLAN.md).

## Execution and repository workflow

1. The candidate is on branch `dev/mvp-security-hardening`, based on
   `origin/v0.7.0` at `1ad19886efc1424a9e475a52f156c86f5013782a`.
2. Keep one integration owner. Parallel chats may investigate, implement or review
   only their assigned package. They must send contradictions, ownership conflicts,
   failing external prerequisites and completion evidence directly to the parent
   orchestrator; they do not ask the user to relay callbacks.
3. Report source contradictions to the orchestrator before changing another
   package's contract.
4. Do not use production secrets, private media, installed user runtimes or live
   publisher accounts. Do not merge, release or deploy.
5. Preserve unrelated work. Use repository-native tests and the smallest faithful
   verification before the integrated full matrix.
6. After implementation, run a defensive code/security review of the complete diff
   and its verification evidence. Resolve or explicitly reject every finding
   with source evidence. Further active adversarial exercises are out of scope
   at the user's direction.
7. Record user-facing changes in `CHANGELOG.md` and create conventional commits.
   The orchestrator owns updating PR #173 into `v0.7.0` after verification.

## Package P0A — Generated decoder index authority

Owner scope:

- `src/frame_compare/vs/source_index_cache.py`
- `src/frame_compare/vs/loader.py`
- `src/frame_compare/vs/source.py`
- `src/frame_compare/vsview/`
- corresponding VS/VSView tests and architecture/runbook text

Required implementation:

1. Resolve every generated L-SMASH-Works index beneath the canonical generated-data
   root; never select or mutate a media-adjacent index.
2. Bind reuse to the canonical source identity, geometry policy version, geometry
   probe token, native runtime token, and index size and digest. The probe token
   covers ffprobe's resolved path, file identity and reported program/library
   versions. Reuse only after a fresh header probe positively recognizes a
   single-file demuxer. Referencing and unknown formats use the private
   full-scan path every time.
3. Write into a private staging location, make the completed index durable, then
   publish metadata last so interruption cannot authorize a partial index.
4. Set stable cache behavior explicitly and share the owner across render,
   alignment and VSView callers.
5. Preserve valid zero values and typed unavailable evidence.

Acceptance:

- Alias, symlink, stale metadata, interrupted write and concurrent reuse tests.
- Same-size/same-mtime atomic source replacement and lease-held native-open tests.
- Warm reuse skips the frame scan. A probe or policy mismatch invalidates proof.
- Loader/source/VSView caller tests and affected native-policy coverage.
- No writes beside selected media.

Rollback: revert the package as one unit. Do not leave caller propagation without
the cache owner or restore media-adjacent reuse as a fallback.

## Package P0B — Release trust separation

Owner scope:

- `.github/workflows/release.yml`
- `.github/workflows/windows-portable*.yml`
- `.github/actions/windows-portable-*`
- `tools/windows_portable/release_update*.ps1`
- signer/publisher workflow tests and release documentation

Required implementation:

1. Separate unsigned build, fresh-runner verification, final-artifact security,
   protected signing, package/attestation and publication into distinct jobs.
2. Transfer only exact immutable artifact IDs and digests. Recompute canonical
   manifest bytes from the exact checkout before signing.
3. Expose the signing secret only to the protected signer. The signer receives no
   publication permission; the publisher receives no signing secret or environment.
4. Independently reconstruct the complete tree and compare the ZIP. Verify the
   exact source, launcher, key and update compatibility bindings.
5. Make skipped or failed upstream jobs fail closed, including `always()` guards.
6. Paginate remote draft enumeration and prove tag/release/draft absence before any
   mutation. Recheck exact tag target, release body, asset set and remote asset
   digests immediately before publication and after publication.

Acceptance:

- Workflow graph and permission tests.
- Detached manifest/digest/refusal tests under PowerShell 7 where available.
- Publisher pagination, collision, mutation-order and remote-byte tests.
- Action pins are full immutable commit SHAs.

Rollback: revert the topology, scripts and their tests together. Never retain a
signer that consumes an artifact no current verifier produces.

## Package P0C — Inert portable runtime derivation

Owner scope:

- `tools/windows_portable/portable_*.py`
- `tools/windows_portable/build_portable.ps1`
- Windows portable actions/workflows and derivation tests

Required implementation:

1. Authenticate the exact Windows Python inputs from the frozen lock and native
   archives from the committed runtime manifest. Apply archive safety checks
   and bounded extraction at the assembly boundary.
2. Convert the authenticated `anitopy` 2.1.1 sdist deterministically using its
   allowlisted source and metadata files without executing build hooks. Install
   the hash-verified local wheelhouse with pinned uv offline, with index access,
   dependency resolution and builds disabled.
3. Exclude Qt WebEngine while preserving required PySide6/Qt and native media
   components, licenses and committed project metadata and entry points.
4. Require the fresh release verifier to reconstruct the complete tree from the
   exact approved inputs and reproduce the canonical ZIP byte-for-byte.

Acceptance:

- Archive-confusion, path, tamper, omission, extra-file and reproducibility
  tests.
- Python, Ruff, Pyright, actionlint and PowerShell parsing.
- Hosted Windows candidate build and fresh verification with exact ZIP digest
  reproduction for the signed chain.

Revert assembler and workflow consumers together if rollback is needed.
Independent verification must remain a prerequisite of signing.

## Package P1 — Application input and resource boundaries

Owner scope:

- `src/frame_compare/utils/subproc.py`
- `src/frame_compare/utils/canvas.py`
- `src/frame_compare/utils/child_environment.py`
- render, alignment, publisher, slow.pics and diagnostic callers
- `tools/benchmark_analysis_tiers.py`
- corresponding tests and public contract documentation

Required implementation:

1. Drain child stdout and stderr concurrently with independent byte ceilings.
   Use bounded cleanup of the owned process tree on timeout, overflow,
   cancellation and nonzero exit, and close descendant-held capture pipes on
   leader exit. Windows uses normal `Popen` followed by immediate assignment
   to a preconfigured kill-on-close Job Object. The pre-assignment interval can
   let a descendant escape, and an interrupt inside `Popen` can prevent it
   from returning the child handle needed for cleanup.
2. Filter application child environments. Pass only each integration's owned
   credential. Ignored legacy aliases remain unsupported. The silent,
   time-bounded desktop broker owns its own lifetime and lets desktop handlers
   and clipboard owners outlive it.
3. Enforce one canvas dimension/pixel policy before Pillow, FFmpeg, VapourSynth,
   batch or overlay allocation. Start native admission with a bounded header
   probe. On cold and cache-free opens, including the VSView fallback, scan
   complete coded and visible frame geometry under the output and time limits.
   Warm managed opens can reuse the bound proof in P0A. Supply an owned
   decoder-side maximum-pixel option that caller options cannot remove.
4. Validate every slow.pics comparison identity, reject duplicates across the
   complete matrix before upload, and construct the canonical HTTPS result URL.
5. Stream FFprobe frame-type CSV with bounded rows, bytes, pending gaps and counters.
   Any malformed, partial, overflow, timeout or stderr-on-success condition returns
   unavailable evidence, never a partial histogram.

Acceptance:

- Independent pipe overflow/deadlock, timeout, cancellation and cleanup tests.
- Leader-exit descendant and pipe cleanup coverage, including Windows Job
  Object assignment and bounded failure handling.
- Credential filtering tests for application and diagnostic children.
- Canvas exact-boundary/overflow tests through each allocator.
- Network identity/canonical URL tests.
- Benchmark malformed/overflow/timeout tests plus a real small H.264 sample.

Rollback: revert shared owners and callers together. Never restore an unbounded
fallback when a bounded result is unavailable.

## Package P2 — Security assurance and release evidence

Owner scope:

- `.github/workflows/source-security.yml`
- CI/release/Docker workflow callers
- `tools/check_python_security.sh`
- `tools/verify_docker_context.sh`
- `tools/windows_portable/artifact_security.py`
- `Dockerfile`, `.dockerignore`, security/release docs and tests

Required implementation:

1. Reusable source security checks out an explicit full SHA, verifies HEAD, runs
   Ruff/Bandit against maintained owners and audits the frozen all-group/all-extra
   dependency graph on Linux and Windows. JSON dependency entries are validated so
   scanner failure, malformed evidence and empty coverage fail.
2. Normal CI uses the PR head/event SHA. The release workflow requires the same
   gate against its validated SHA before Windows build or signing.
3. Exclude credential patterns from the Docker context and copy only required
   application inputs into the runtime stage. Prove the real ignore/COPY behavior
   with harmless sentinels.
4. Consume the independently verified portable ZIP and verification receipt by
   immutable IDs. Validate the ZIP with portable archive policy and extract into a
   new isolated directory without executing bundle content.
5. Download Syft 1.56.0 and Grype 0.121.0 Linux x64 archives, require their committed
   SHA-256 values, then generate native Syft and CycloneDX inventories from the same
   extracted tree.
6. Run Grype against the Syft JSON with update-check, age and hash validation.
   Require a valid database no older than five days and no larger than 8 GiB.
   Retain its source checksum, build time and local digest.
7. Check scanner identity and require nonempty Syft and CycloneDX inventories.
   Reject scan errors, ignored matches, unknown/high/critical severity and KEV
   matches. Keep the unsuppressed result and a receipt binding the candidate,
   verifier result, database, evidence hashes and policy result. Retain
   available evidence for 90 days even when policy fails. The protected signer
   requires a successful policy result.
8. Document exact waiver fields, signer-compromise response, native coverage and
   legal/provenance release gates. Do not claim source scanning covers unidentified
   native binaries.

Acceptance:

- Security script fail-closed tests and a clean maintained-owner scan.
- Linux and Windows frozen audit workflow structure.
- Docker sentinel/context contract tests.
- Receipt binding, safe extraction, empty/malformed SBOM, stale DB, suppression,
  severity and KEV policy tests.
- Workflow proves artifact-security success and retained evidence are dependencies
  of protected signing.

Rollback: revert source/artifact gates and their callers together. If automation is
temporarily unavailable, publication remains blocked until the runbook's equivalent
external evidence is complete; do not silently skip the gate.

## Integrated verification matrix

Run from the candidate branch after all packages are integrated:

```bash
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pyright --warnings
bash tools/check_python_security.sh
uv run --no-sync lint-imports --config importlinter.ini
uv run --no-sync pytest -q -n 4 --dist loadgroup --ignore=tests/browser
uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py
uv run --no-sync zensical build --clean --strict
bash tools/verify_docker_context.sh
bash tools/verify_docker_integration.sh --no-cache
```

Also run actionlint, PowerShell parsing and the focused portable/release chain under
PowerShell 7. Record native/platform skips exactly. The following are separate final
release observations, not local substitutes: hosted Windows signed-chain canary,
protected-environment secret precedence, GitHub attestation, physical Windows
PowerShell 5.1/7 update journeys, GPU Vulkan/HDR and real-media acceptance.

## Completion and ready signal

The [final integration record](REPORT.md#final-integration-and-review) records
the defensive review, the original remediation and its verification results.
Follow-up review findings on persisted probe authority, referenced-media admission,
Windows executable resolution, hosted Windows fixtures, and source-interpreter
provisioning are tracked in the PR's subsequent implementation and review evidence.
The known headless Chrome fullscreen refusal is present on the baseline. The
remaining PR handoff is the orchestrator's update of PR #173 to the verified
candidate.

The [residual release gates](REPORT.md#residual-release-gates) require separate
hosted and physical Windows evidence before public distribution.
