---
search:
  exclude: true
---

Status: Active
Scope: Coordinated VapourSynth R80, BestSource R22, and retained Windows FFmpeg 8.1 runtime refresh
Owner: Next media-runtime refresh sessions

# Coordinated Media Runtime R80 Refresh

## Outcome

Refresh the supported media runtime from VapourSynth R79 to R80 while preserving
Frame Compare's existing decoder, tone-mapping, viewer, cache, packaging, licensing,
and update-safety contracts. Move the VSView support graph to BestSource R22, which
requires VapourSynth 80, and advance the portable Windows standalone FFmpeg artifact
to the retained August 2026 build from the existing 8.1 LGPL release line.

The routine dependency refresh is already isolated in commit `6e5e47cd`
(`chore(deps): refresh routine dependencies`). Start implementation from a branch
that contains that commit and the maintainer's completed alignment work. Do not
absorb or overwrite unrelated dirty alignment files.

## Selected Targets

| Component | Current | Target | Immutable selection |
| --- | --- | --- | --- |
| VapourSynth | R79 | R80 | tag `R80`, commit `732845793a1caf5838d4f7b94f6ce668a19c908e` |
| VapourSynth portable ZIP | R79 | R80 | 31,533,239 bytes; SHA-256 `5d927152d9db29d104c8960bf44d0df7777835f7741d310184bfae6fda2f4f22` |
| VapourSynth PyPI | 79 | 80 | CPython 3.12 ABI3 wheels; Windows wheel SHA-256 `7a1475ab0709a007bc54331fd0eea44eb45e2abeb76879e12d6295ff335317dc` |
| BestSource | 21.0 | 22 | tag `R22`, commit `a0fab5708b28920957679825797692f6e4a23674` |
| BestSource Windows wheel | 21.0 | 22 | 15,890,493 bytes; SHA-256 `4dc2275d145128a2a86fa32efaab9fbab8e22582bfdf173b460f2ff33858c230` |
| Windows FFmpeg | `n8.1.2-34-g9b6c8969e0` | `n8.1.2-50-g1a748fe2cd` | BtbN `autobuild-2026-08-31-13-27`, 146,078,616 bytes; SHA-256 `f6274bbd9c247f9e90c1bbed066b03ed4a3907cece2fb91be6dd352393936365` |

Primary artifact URLs:

- `https://github.com/vapoursynth/vapoursynth/releases/download/R80/VapourSynth64-Portable-R80.zip`
- `https://files.pythonhosted.org/packages/e1/01/8b65d43d73d6d3a5dab3aa79a65e98cf8fac33cfe24e94bdcad46ded390e/vapoursynth_bestsource-22-py3-none-win_amd64.whl`
- `https://files.pythonhosted.org/packages/a4/19/c0f06506a49815e79d6ab95193986686969531755ebccbb81e06bb99b541/vapoursynth_bestsource-22.tar.gz`
- `https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-08-31-13-27/ffmpeg-n8.1.2-50-g1a748fe2cd-win64-lgpl-8.1.zip`

## Frozen Decisions

- Adopt stable R80; do not use an alpha, RC, moving branch, or unpinned artifact.
- Keep VapourSynth API R4.2 as the plugin contract unless observed R80 metadata
  proves otherwise. Record release and API identities separately.
- Keep L-SMASH-Works 1310, L-SMASH, OBUParse, FFMS2 5.0, vs-placebo 2.0.4,
  libplacebo, libdovi, VSView 0.11.0, VSJetEngine 1.7.0, vspackrgb 1.4.0,
  PySide6 6.11.2, and Debian Trixie FFmpeg unchanged unless compatibility proof
  demonstrates a concrete blocker.
- Keep generated Frame Compare sessions on L-SMASH-Works. BestSource remains a
  VSView/UI dependency and is not a replacement for analysis, probe, render,
  index, or cache-key source loading.
- Keep the Windows standalone FFmpeg artifact on the retained 8.1 LGPL-only line.
  FFmpeg 9 adoption is a separate compatibility, licensing, and deployment decision.
- R80 GPU-frame support is accepted as an upstream capability, not enabled as a
  new Frame Compare execution path in this work. Preserve the current CPU-frame
  and software-Vulkan validation path.
- Do not store VapourSynth nodes or functions in frame properties. R80 prohibits
  this; existing scalar/frame-property behavior must remain valid.
- Recompute every runtime fingerprint from the selected components. Do not retain
  an R79/BestSource 21/old-FFmpeg fingerprint or add compatibility overrides.
- A code-only update must continue to reject the changed media-runtime fingerprint;
  crossing this boundary requires a complete portable bundle reinstall.

## Non-Goals

- No new GPU configuration, CLI flags, environment variables, or runtime profiles.
- No FFmpeg 9 migration and no custom Linux FFmpeg build.
- No decoder migration from L-SMASH-Works to BestSource.
- No VSView upgrade beyond 0.11.0 and no expansion to its `recommended` or `full` extras.
- No cache-schema migration. Old runtime fingerprints and indexes should miss and
  rebuild under the existing policy.
- No unrelated alignment, report-viewer, CLI, or configuration behavior changes.

## Owner And Write Boundary

The implementation may update the existing owners below and adjacent focused tests
or generated lock data required by those changes:

- dependency selection: `pyproject.toml`, `uv.lock`
- Docker runtime and proof: `Dockerfile`, `tools/verify_docker_integration.sh`
- runtime identity: `src/frame_compare/vs/runtime_contract.py`
- portable selection/provenance: `tools/windows_portable/manifest.windows-x64.json`
- portable build and verification scripts only where version/layout assertions require it
- focused runtime, doctor, Docker, and Windows portable tests
- `docs/supported-media-runtime.md` and `docs/media-runtime-windows-validation.md`

Do not edit current architecture or CLI authority unless implementation changes an
actual responsibility or public contract rather than only selected versions. Stop
and reassess if a required fix escapes these owners.

## Execution Packages

### 1. Resolve And Record The Python Graph

1. Change the `vapoursynth` extra pin to `==80` and refresh `uv.lock`.
2. Confirm the resolver selects BestSource 22 because it declares
   `VapourSynth>=80`; do not add a redundant direct BestSource dependency merely
   to force the transitive version.
3. Inspect the entire lock diff. Expected material changes are VapourSynth 80,
   BestSource 22, their hashes, and any genuinely required compatible transitives.
4. Confirm R80 wheels exist for every locked supported platform and that Python
   3.13 continues to use the CPython 3.12 ABI3 wheel.

Acceptance: universal locking succeeds without prereleases or dropping a supported
platform; unrelated dependency churn is absent or explicitly justified.

### 2. Refresh Docker And Runtime Identity

1. Update both Docker VapourSynth version arguments, R80 commit, tracked-tree
   digest, wheel hashes, comments, and provenance output.
2. Derive the tracked-tree SHA-256 with the existing
   `tools/checkout_source_commit.sh` algorithm; do not substitute GitHub archive
   bytes for the tracked-tree digest.
3. Update `VAPOURSYNTH_RELEASE`, source metadata, Windows FFmpeg release identity,
   and derived runtime fingerprints in `runtime_contract.py`.
4. Update doctor and Docker proof assertions from R79 to R80 while continuing to
   assert API R4.2 independently.
5. Confirm current frame-property use contains no node/function values and that
   all L-SMASH-Works, FFMS2, and vs-placebo registrations still load under R80.

Acceptance: no R79 identity remains in active runtime code, Docker provenance, or
runtime tests except an intentional previous-baseline statement in documentation.

### 3. Refresh Windows Portable Provenance

1. Replace the R79 portable artifact with the exact R80 ZIP above, including size,
   digest, source commit/ref, source archive metadata, license URLs, and notes.
2. Replace BestSource 21 with the exact R22 wheel/source artifacts and update its
   license/source reference to R22.
3. Replace the retained July FFmpeg artifact with the exact retained August 8.1
   LGPL artifact above, including URL, size, digest, strip prefix, source ref, and
   corresponding source metadata.
4. Recompute the manifest component fingerprints and update all expected values in
   runtime/portable tests. Preserve fingerprint scope rules: standalone FFmpeg must
   affect alignment/probe/full scopes but not analysis/index scopes that exclude it.
5. Preserve the canonical VapourSynth plugin directory, Qt subset exclusions,
   non-root behavior, license inventory, and complete-reinstall boundary.

Acceptance: manifest schema validation, exact artifact verification, inventory
generation, and fingerprint tests all fail closed on old or mismatched metadata.

### 4. Update Authority Documentation

Update the supported component matrix, runtime profiles, compatibility notes,
artifact provenance, cache/fingerprint implications, and Windows validation matrix.
Document these R80 changes accurately:

- Vulkan 1.4 GPU-frame support exists upstream but Frame Compare does not adopt a
  new GPU-frame path here.
- free-threaded Python support was added upstream but the packaged runtime remains
  CPython 3.13's existing supported layout.
- nodes and function types can no longer be stored as frame properties.
- BestSource R22 reworked GPU support and is source-incompatible with R21, while
  remaining UI-only in Frame Compare.

Acceptance: active docs describe only the selected R80/R22/August-FFmpeg profile;
historical baseline language is clearly labeled and not presented as current.

## Verification

Risk: high. Primary mode: native integration and packaging contract.

Required local gates after integration:

```bash
uv sync --group dev --group docs --extra vsview --locked
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
bash tools/verify_docker_integration.sh --no-cache
```

Also run the locked runtime dependency audit from the engineering runbook. Inspect
all skips; the canonical Docker gate must finish with zero skips and must report R80,
API R4.2, both source loaders, vs-placebo invocation, software Vulkan, native linkage,
provenance, generated fixture coverage, non-root execution, and production-tooling
absence.

Required Windows proof:

- manifest/schema and portable-script pytest coverage locally;
- hosted Windows portable build at the exact candidate SHA;
- extracted-bundle verification for R80, BestSource 22, VSView, Qt subset, plugin
  layout, licenses/SBOM/provenance, FFmpeg/ffprobe versions, and code-only update refusal;
- native generated-session and alignment-panel proof;
- physical Windows validation for RTX/Vulkan, real HDR10 and Dolby Vision media,
  timing/VFR/interlacing/repeated-field behavior, old/new indexes, perceptual output,
  and complete-reinstall transition.

Do not claim release readiness from macOS, source inspection, or offscreen Qt proof
alone. Windows signing and protected release dispatch remain maintainer-only.

## Commit And Review Shape

Use reviewable conventional commits that keep generated lock/fingerprint updates
with their owning selection change. A reasonable sequence is:

1. `chore(runtime): update VapourSynth to R80`
2. `chore(windows): refresh portable media artifacts`
3. `docs(runtime): document the R80 media profile`

Adjust grouping if a smaller coherent boundary emerges, but do not mix unrelated
alignment or product behavior. Before each commit, inspect the staged diff and stage
only task-owned files. The final integrated diff requires an independent review
focused on runtime identity, fingerprint scope, artifact provenance, packaging
fail-closed behavior, and verification gaps.

## Rollback

Rollback is the complete coordinated profile, not individual packages: revert R80,
BestSource 22, the August FFmpeg artifact, all manifests/hashes/fingerprints, lock
data, tests, and authority docs together. Never publish a mixed R79/R80 profile or
reuse code-only updates across either fingerprint.

## Stop Conditions

Stop and return to planning if any of these occurs:

- R80 changes API identity or breaks L-SMASH-Works 1310, FFMS2 5.0, or vs-placebo 2.0.4.
- BestSource R22 cannot launch/render through VSView 0.11.0 in the supported bundle.
- Vulkan 1.4 becomes mandatory for the existing CPU-frame path rather than optional
  for upstream GPU-frame support.
- the selected FFmpeg artifact changes the LGPL-only license posture or requires a
  new Windows runtime dependency.
- compatibility requires a new public option, runtime profile, cache migration,
  decoder policy, or FFmpeg major-line decision.
- exact upstream artifacts, provenance, licenses, or corresponding source cannot be
  verified.

## Completion

When all required proof is recorded and no release blocker remains, change this
plan to `Status: Historical` in the final implementation pass. Record unavailable
physical-host or signing proof explicitly rather than treating the plan as complete.
