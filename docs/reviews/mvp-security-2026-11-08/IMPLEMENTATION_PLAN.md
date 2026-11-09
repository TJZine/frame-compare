# Approved MVP security implementation contract

This is the explicit, implementation-ready contract derived from the accepted
findings in `REPORT.md`. It is intentionally specific enough for an implementation
chat to execute without inventing product policy or redesigning the solution.

## Execution and repository workflow

1. Start from exact base `e56f00a429ef494549cba153b2a7ff49230b2ea2`
   (`v0.7.0`) on branch `dev/mvp-security-hardening`.
2. Keep one integration owner. Parallel chats may investigate, implement or review
   only their assigned package. They must send contradictions, ownership conflicts,
   failing external prerequisites and completion evidence directly to the parent
   orchestrator; they do not ask the user to relay callbacks.
3. Implementation chats use GPT-6.1 Sol at high reasoning. Execute this contract as
   written. Additional design is authorized only when current source proves a
   contradiction; report that contradiction to the orchestrator before changing
   another package's contract.
4. Do not use production secrets, private media, installed user runtimes or live
   publisher accounts. Do not merge, release or deploy.
5. Preserve unrelated work. Use repository-native tests and the smallest faithful
   verification before the integrated full matrix.
6. After implementation, run a defensive code/security review of the complete diff
   and its verification evidence. Resolve or explicitly reject every finding with
   source evidence. Active crafted-input reproduction and additional red-team work
   are omitted at the user's direction because the available Daybreak environment
   repeatedly blocked that work; record the omission instead of treating it as a
   pass.
7. Record user-facing changes in `CHANGELOG.md`, create conventional commits, push
   the branch, and open a PR into `v0.7.0` titled
   `fix(security): harden MVP trust boundaries and release pipeline`. Stop after the
   PR is open so the user can inspect it.

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
2. Bind reuse to the canonical source identity and required cache metadata.
3. Write into a private staging location, make the completed index durable, then
   publish metadata last so interruption cannot authorize a partial index.
4. Set stable cache behavior explicitly and share the owner across render,
   alignment and VSView callers.
5. Preserve valid zero values and typed unavailable evidence.

Acceptance:

- Alias, symlink, stale metadata, interrupted write and concurrent reuse tests.
- Same-size/same-mtime atomic source replacement and lease-held native-open tests.
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

1. Separate unsigned build, fresh-runner verification, protected signing,
   package/attestation and publication into distinct jobs.
2. Transfer only exact immutable artifact IDs and digests. Recompute canonical
   manifest bytes from the exact checkout before signing.
3. Expose the signing secret only to the protected signer. The signer receives no
   publication permission; the publisher receives no signing secret or environment.
4. Independently verify the complete tree and source/launcher/key/catalog bindings.
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
- `tools/windows_portable/release-runtime-files.json`
- `.gitattributes`
- Windows portable actions/workflows and derivation tests

Required implementation:

1. Build the runtime from `uv.lock`, pinned archives and the approved catalog
   without importing or executing dependency build/install hooks.
2. Validate every input archive before projection: path spelling, case collisions,
   file types, entry counts, compression ratio, member and aggregate expansion,
   offsets, CRC and decompression completion.
3. Project wheels from exact RECORD authority. Handle the approved source archive
   using inert package-specific projection, never its hooks.
4. Remove the exact WebEngine runtime profile while preserving required PySide6/Qt
   and native media components.
5. Generate a deterministic complete-tree catalog independently, review and commit
   it, then require a fresh job to reproduce and byte-compare the canonical ZIP.

Acceptance:

- Archive-confusion, path, RECORD, tamper, omission, extra-file and reproducibility
  tests.
- Python, Ruff, Pyright, actionlint and PowerShell parsing.
- One real inert Windows-runtime build with exact ZIP digest reproduction.

Rollback: revert assembler, catalog and workflow consumers together. A stale catalog
must block rather than fall back to producer authority.

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
   Timeout, overflow, cancellation and nonzero exit terminate and reap the owned
   process tree and return typed failure without partial success.
2. Filter application child environments. Pass only each integration's owned
   credential; do not treat ignored legacy aliases as supported secrets.
3. Enforce one canvas dimension/pixel policy before Pillow, FFmpeg, VapourSynth,
   batch or overlay allocation. Before native source admission, stream bounded
   ffprobe records for every video frame and reject missing, changing or out-of-policy
   coded/visible geometry. Supply an owned decoder-side maximum-pixel option that
   caller options cannot remove.
4. Validate every slow.pics comparison identity, reject duplicates across the
   complete matrix before upload, and construct the canonical HTTPS result URL.
5. Stream FFprobe frame-type CSV with bounded rows, bytes, pending gaps and counters.
   Any malformed, partial, overflow, timeout or stderr-on-success condition returns
   unavailable evidence, never a partial histogram.

Acceptance:

- Independent pipe overflow/deadlock, timeout, cancellation and cleanup tests.
- Nonzero-leader/DEVNULL-descendant coverage, including Windows Job Object ownership.
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
6. Run Grype against the Syft JSON with update-check, age and hash validation. Require
   a valid database no older than five days and retain its source checksum, build
   time and local digest.
7. Reject empty inventories, scan errors, ignored matches, unknown/high/critical
   severity and any known-exploited metadata. Pin Syft JSON 16.1.12 and CycloneDX
   1.7 document identity and validate nonempty package/component/source entries.
   Keep the unsuppressed result. Upload
   all evidence for 90 days even when policy fails; only a successful job may allow
   the protected signer to run.
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
bash tools/verify_docker_context.sh
bash tools/verify_docker_integration.sh --no-cache
```

Also run actionlint, PowerShell parsing and the focused portable/release chain under
PowerShell 7. Record native/platform skips exactly. The following are separate final
release observations, not local substitutes: hosted Windows signed-chain canary,
protected-environment secret precedence, GitHub attestation, physical Windows
PowerShell 5.1/7 update journeys, GPU Vulkan/HDR and real-media acceptance.

## Completion and ready signal

The orchestrator may give the ready signal only when:

- every accepted code finding is remediated;
- the integrated verification appropriate to the changed contracts is green;
- documentation and user-facing changelog match the implementation;
- the integrated diff has passed the recorded defensive code/security review, with
  the user-directed omission of further active adversarial exercises disclosed;
- conventional commits contain only this branch's intended changes; and
- the PR into `v0.7.0` is open, with no merge or release performed.
