---
search:
  exclude: true
---

Status: Active
Scope: Replace the retired VSPreview integration with VSView and remove every active legacy implementation surface
Owner: Maintainer-directed Codex migration session, with physical-Windows acceptance handed back to the maintainer

# VSView Migration Plan

## Purpose

Replace Frame Compare's retired VSPreview integration with the maintained VSView
successor without leaving a dual stack, compatibility shim, stale type path, or active
documentation for the old viewer.

This is a high-risk cross-boundary migration. It changes an external GUI runtime,
public configuration and JSON identifiers, alignment persistence provenance, Docker GUI
proof, Windows portable dependencies, and documented runtime behavior. The MacBook pass
may complete the implementation and all locally available proof, but the migration is
not release-ready until the physical-Windows acceptance gate is recorded.

## Goal

Deliver one VSView-only implementation that:

1. uses the documented VSView API and the pinned base `vsview==0.10.3` package;
2. preserves Frame Compare's alignment semantics, generated overlays, output ordering,
   L-SMASH source path, color defaults, and terminal confirmation workflow;
3. removes the VSPreview package, dependency, compatibility mutations, public names,
   tests, screenshots, and active documentation;
4. makes every intentional functional and machine-readable contract change explicit;
5. proves everything available on macOS, Docker, and hosted Windows before requiring
   final hands-on validation on the physical Windows machine.

## Frozen decisions

- Rename the optional dependency extra to `vsview` and pin base
  `vsview==0.10.3`. Do not use the `recommended` or `full` extras.
- Replace `audio_alignment.use_vspreview` with `use_vsview`. Do not retain an
  alias, compatibility reader, or production-code tombstone. Old configurations fail
  strict unknown-key validation; the upgrade documentation identifies the replacement.
- Keep the viewer-neutral `--force-interactive-alignment` CLI option and
  `force_interactive` request field. Persisting the flag enables `use_vsview = true`.
- Preserve numeric errors `FC-2008` and `FC-4019`, but rename their exception types,
  symbolic names, messages, and hints to VSView.
- Rename the doctor check identifier to `vsview` and the dry-run JSON field to
  `browser_clipboard_or_vsview`. These are intentional machine-readable breaks.
- Preserve `manual_overrides.toml`, its v1 schema, path, ordering, atomic-write
  behavior, and offset semantics. Move it to the viewer-neutral owner
  `services/alignment_manual_overrides.py`.
- Bump the shared alignment reuse cache to schema v2. Replace viewer-specific
  provenance with `interactive_confirmed` and `interactive_confirmed_this_run`.
  Use the existing generic unsupported-version miss and recompute path; do not add a
  v1-specific reader, tombstone, or migration branch.
- Create `frame_compare.vsview` and `services/alignment_vsview`. Delete the complete
  `frame_compare.vspreview` and `services/alignment_vspreview` implementations.
- The managed Windows launcher may retain only the VapourSynth native-runtime preload
  required before Qt/VSView imports. Remove all VSJetPack, `vs_object`, `set_output`,
  `DitherType.is_fmtc`, and warning compatibility mutations.
- Generated sessions import `set_output` from VSView and assign explicit output names.
  Preserve reference/comparison order, multi-comparison behavior, Frame Compare
  overlays, BT.709 preview defaults, range policy, owned L-SMASH index paths,
  diagnostics, and terminal confirmation.
- Keep BestSource owned by VSView. Do not change Frame Compare's analysis, probe,
  render, index, cache-key, or generated-session source loader from L-SMASH.
- Retain the Linux X11 Docker GUI profile and migrate its proof contract to VSView.
- Remove Akarin, VSZip, and their bundled zstd/Zig provenance from Docker and the
  Windows portable runtime. They were VSPreview-transitive payloads with no current
  Frame Compare analysis, probe, render, or generated-session owner.
- Require a complete portable reinstall from every VSPreview-era Windows bundle. A
  code-only update must fail closed when the dependency/runtime requirements differ.
- Do not introduce a preview-provider abstraction, compatibility toggle, dual stack,
  or fallback to VSPreview.

## Retained behavior, gains, and intentional losses

| Category | Contract after the swap |
| --- | --- |
| Retained | Audio computation and the `reference frame - comparison frame` offset convention |
| Retained | Optional review falls back to computed alignment; forced review failure is fatal |
| Retained | Non-TTY, JSON, quiet, previous-offset, prompt, and write-config restrictions |
| Retained | Reference/comparison ordering, multi-comparison review, overlays, source identity, L-SMASH indexing, and confirmation prompts |
| Retained | Existing run-local `manual_overrides.toml` files remain readable |
| Gain | A maintained successor with current VapourSynth, PySide6, and named-output support |
| Gain | Documented named outputs instead of runtime monkeypatching and slot-only labels |
| Gain | VSView's modern synchronized-output, frame-properties, and plugin surfaces |
| Gain | The bundle no longer carries orphaned Akarin/VSZip native payloads or their zstd/Zig supply-chain surface; no Frame Compare feature used them |
| Loss/break | The old config key, optional-extra name, doctor ID, JSON field, symbolic errors, log events, imports, and generated-session paths disappear |
| Loss/break | Alignment reuse cache v1 is ignored and rebuilt as v2, including old computed and confirmed entries |
| Loss/break | VSPreview-era generated scripts are not supported by the new integration |
| Loss/break | VSPreview-specific plugins and PyQt6/PySide6/PyQt5 probing assumptions are removed |
| Pending proof | Visible synchronized seeking, frame-number presentation, native Linux X11 behavior, Windows GPU/HDR behavior, bundle size, and startup time |

## Non-goals

- Redesign audio correlation, offset signs, frame selection, rendering, reporting, or
  media analysis.
- Change the supported L-SMASH, FFmpeg, VapourSynth, or vs-placebo media-runtime
  components solely because the Python GUI dependency changes.
- Treat VSView's direct-file BestSource workspace as a Frame Compare source-loader
  migration.
- Rewrite Git history or delete historical generated sessions from user workspaces.
- Claim native Linux X11, Windows GUI, D3D12, HDR, or clean-machine behavior from
  macOS or headless tests.

## Owner seams and write boundaries

The controller owns this plan, cross-cutting integration, `importlinter.ini`, generated
documentation reconciliation, full verification, the repository-wide stale audit, and
final reviewer adjudication.

Bounded writers may own only one of these disjoint units at a time:

1. Runtime: `src/frame_compare/vsview/**`, `tests/vsview/**`, and deletion of only
   `src/frame_compare/vspreview/**` and `tests/vspreview/**`.
2. Alignment/persistence: alignment service owners, alignment orchestration/types,
   and alignment-focused tests. This unit exclusively owns cache schema, provenance,
   and manual-override changes.
3. Public contracts: config schema/overrides, CLI output/contracts/help, doctor owners,
   and their focused tests. It must not edit alignment owners.
4. Dependency/Docker: `pyproject.toml`, `uv.lock`, `Dockerfile`, the Linux GUI profile
   verifier, and Docker contract tests.
5. Windows packaging: `tools/windows_portable/**`, Windows workflows, manifests,
   inventory/license proof, and Windows portable tests. Start only after the dependency
   graph is stable.
6. Documentation: current user/authority docs, API model/generated docs, navigation,
   the changelog/upgrade note, image provenance, and deletion of the obsolete viewer
   screenshot. Start after behavior stabilizes.

Each writer must stop and report an out-of-bound need instead of crossing ownership.
The controller reviews every diff and reruns the required proof.

## Architecture dispositions

- `vsview/session_script.py` remains a focused generated-session owner even if it stays
  above the normal size threshold; do not expand it into alignment policy.
- `alignment_reuse_cache.py` remains the cohesive shared-cache owner; the v2 change is
  limited to schema/provenance and unsupported-v1 behavior.
- `doctor_checks.py` retains its existing responsibility; only the optional viewer
  capability check changes.
- `build_portable.ps1` retains its packaging responsibility; VSView/Qt dependency and
  startup proof do not move into application code.
- Public output changes remain owned by CLI/config/doctor layers and require focused
  contract assertions plus same-pass authority documentation.

## Evidence already recorded on macOS

The pre-cutover feasibility gate used an isolated environment rather than modifying the
project dependency graph:

- Base `vsview==0.10.3` installed and exposed its console/module CLI without
  `recommended` or `full` extras.
- The isolated runtime reported VapourSynth R79/API R4.2 and PySide6 6.11.2.
- A synthetic two-output script loaded through VSView with explicit `Reference` and
  `Comparison 1` names.
- A representative two-file Frame Compare-style script loaded real media through
  BestSource for this upstream smoke only, registered both named outputs, synchronized
  their frame playheads, requested frame zero, rendered it, and reported successful
  content loading under Qt's offscreen platform.
- An intentionally property-free clip failed color conversion; adding Frame Compare's
  BT.709 defaults made it render. The generated-session color-default behavior is
  therefore an invariant, not cleanup material.
- The base graph was materially smaller than `recommended`; no dependency compatibility
  mutation was needed.
- The focused pre-cutover VSPreview/alignment/doctor baseline suite passed.

This evidence permits implementation to start. It does not prove visible native GUI
ergonomics or the managed Windows bundle.

## Current release blockers after the Mac proof

- The exact PySide6 6.11.2 Windows wheels are pinned and hashed, but each wheel archive
  ships only `LicenseRef-Qt-Commercial.txt`; it does not include the LGPL/GPL text,
  third-party notices, an SBOM, or corresponding source.
- `PySide6_Addons` includes Qt WebEngine/Chromium resources and Qt Multimedia's FFmpeg
  DLLs. The provisional manifest records Qt, PySide, and FFmpeg source archives, but it
  does not yet enumerate the complete Qt WebEngine/Chromium third-party notice surface.
- Exact official Qt 6.11.2, PySide 6.11.2, and FFmpeg 7.1.5 source archives and hashes
  are known. Before release, publish a distributor-controlled corresponding-source
  offer, add the version-matched notice/SBOM evidence, and adjudicate the FFmpeg lineage
  against the built Windows wheel. An upstream-only source link is not treated as a
  completed distribution obligation; see Qt's
  [LGPL obligations guidance](https://www.qt.io/development/open-source-lgpl-obligations)
  and [Qt WebEngine licensing guidance](https://doc.qt.io/qt-6/qtwebengine-licensing.html).
- Hosted and physical Windows must still prove the extracted dependency inventory,
  native preload, offscreen and visible viewer behavior, GPU/HDR paths, clean-machine
  DLL resolution, complete reinstall, and fail-closed updater behavior.

These are release blockers, not reasons to retain or restore the retired integration.
The Mac cutover may be implementation-complete while this plan remains Active.

## Execution sequence

### Phase 1: Mac cutover

- [x] Implement the VSView runtime owner, documented output registration, launcher,
      diagnostics, and generated session.
- [x] Move viewer-neutral manual overrides, bump alignment cache schema/provenance, and
      update alignment policy without changing precedence or offset semantics.
- [x] Update config, CLI, doctor, orchestration, tests, dependency graph, Docker, and
      authority docs.
- [x] Delete all retired packages, tests, compatibility helpers, old screenshot, and
      active references in the same cutover.
- [x] Regenerate the lock and API documentation only through repository-owned commands.

### Phase 2: Mac and container proof

- [x] Run focused VSView, alignment, persistence, config, CLI, doctor, Docker-contract,
      and Windows-script tests.
- [x] Prove a generated VSView session with synthetic and real local media, explicit
      names/order, output rendering, inherited diagnostics, and clean close/exit.
- [x] Run the complete repository verification canon, strict documentation build, build
      artifact check, dependency inspection, and tracked-file stale audit.
- [x] Run the canonical headless Docker integration gate.
- [x] Build/probe the Linux GUI image on macOS where feasible. Record actual X11 launch
      as unavailable unless tested on a compatible Linux X11 host.
- [x] Obtain one fresh independent architecture/runtime review and adjudicate every
      finding.

## Windows continuation handoff

Continue from a clean checkout of the committed migration head. Record the complete
lowercase `git rev-parse HEAD` value before building, and do not mix artifacts from a
different commit or an earlier portable cache into the acceptance evidence.

Use `docs/media-runtime-windows-validation.md` as the executable Windows authority.
Complete its repository validation, fresh portable build, ZIP/extracted-bundle proof,
generated-fixture matrix, real-media matrix, GPU/HDR checks, cache/index migration,
updater migration, and end-to-end comparison sections. Install the repository test
environment with `uv sync --all-groups --extra vsview --frozen`; use only the bundled
runtime for portable-bundle proof.

The VSView-specific continuation must additionally:

1. retain a separate pre-VSView portable installation for fail-closed updater and
   complete-reinstall testing;
2. capture the exact bundle ZIP SHA-256, dependency/runtime fingerprints, Windows
   build, CPU, GPU, driver, Python, VapourSynth, VSView, PySide6, BestSource, and
   vspackrgb versions;
3. preserve the hosted/offscreen proof logs for managed VapourSynth preload before Qt,
   `QApplication`, VSView CLI/native imports, `core.bs`, generated named outputs,
   L-SMASH indexes, both frame-zero renders, and exact-PID cleanup;
4. run a visible, terminal-attached `--force-interactive-alignment` comparison with
   representative multi-comparison media and record output names/order, tab switching,
   link-by-frame/time, seeking, exact source frames, overlays/properties, confirmation
   offsets, skip/fallback behavior, final render/report behavior, and clean close;
5. prove SDR, HDR10, Dolby Vision fallback where supported, VFR, full/limited range,
   D3D12/Vulkan behavior, clean-machine DLL/plugin resolution, old/new indexes and
   caches, complete reinstall, matching code-only update/rollback, and pre-VSView
   code-only update refusal before replacement;
6. keep the PySide6/Qt distribution-compliance gate open until the exact Qt
   WebEngine/Chromium notices, matching SBOM/provenance, FFmpeg lineage, and a
   distributor-controlled corresponding-source offer are recorded and adjudicated.

For every failure, skip, or unavailable case, record the command, exit code, retained
log/artifact, owner, reason, whether it blocks release, and the exact revisit condition.
Do not weaken a test, restore retired compatibility code, or change the frozen public
contracts merely to make Windows green. Fix only a demonstrated integration defect and
rerun the smallest focused proof plus the affected canonical gate.

Update Phase 3 and Phase 4 below with links or paths to the retained evidence. Keep this
plan Active and the release blocked until every acceptance item and the distribution-
compliance gate is complete; then mark the plan Historical in the same final commit.

### Phase 3: Hosted Windows proof

- [ ] Build the complete portable bundle from the tested commit.
- [ ] Verify exact wheel/native hashes, bytes, distribution inventory, license/source
      notices, SBOM/provenance, and dependency fingerprint.
- [ ] Prove managed VapourSynth preload before PySide6/VSView, a controlled
      `QApplication`, VSView CLI/native extensions, `core.bs`, vspackrgb, and generated
      session loading through the extracted bundle.
- [ ] Verify the old dependency fingerprint refuses the new code-only update and directs
      the user to a complete portable reinstall.

### Phase 4: Physical Windows acceptance

- [ ] Record the exact commit, bundle hash, Windows build, CPU/GPU/driver, Qt/runtime
      versions, and previous VSPreview bundle identity.
- [ ] Launch the bundled VSView GUI with representative multi-comparison Frame Compare
      media and verify names/order, tab switching, link-by-frame/time, seeking, exact
      frame indices, overlays, properties, and clean child close.
- [ ] Verify terminal confirmation, confirmed offsets, skip/fallback behavior, and the
      subsequent render/report outcome.
- [ ] Exercise SDR, 10-bit HDR10, Dolby Vision fallback where supported, VFR,
      full/limited range, and representative real-media frame properties.
- [ ] Verify clean-machine Qt/DLL/plugin resolution, D3D12 rendering, cache/index
      transitions, complete reinstall, compatible code-only update, and rollback.
- [ ] Recapture a VSView alignment screenshot only if active documentation still needs
      one, then mark this plan historical.

## Verification record

```text
VERIFICATION_RECORD
RISK: high
PRIMARY_MODE: integration
RATIONALE: external GUI replacement plus public CLI/config/JSON, persistence,
Docker, and Windows portable changes.
TEST_DECISION: update and add
```

Mac proof commands:

```bash
uv lock --check
uv sync --all-groups --extra vsview --frozen
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pyright --warnings
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync lint-imports --config importlinter.ini
uv run --no-sync pytest
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
uv build
bash tools/verify_docker_integration.sh
git diff --check
```

Recorded Mac/container results on 2026-08-30:

- The focused VSView/alignment/public-contract, runtime/Docker-workflow, Windows
  portable-script, and documentation/package-contract suites passed.
- The complete suite produced 2,824 passes and 73 skips. The one native-Mac GOP
  integration test that requires the host-owned L-SMASH plugin failed because that
  plugin is absent from this unmanaged Mac; the canonical rerun excluding that
  host-owned test passed with the same 2,824 passes and 73 skips.
- Ruff check and 479-file format check passed; Pyright reported zero errors; Bandit
  reported zero medium/high findings; both import-linter contracts were kept; API-doc
  generation, strict Zensical, lock validation, and `uv build` passed.
- The canonical Docker integration rebuilt the runtime without Akarin or VSZip and
  passed 220 tests with zero skips plus real L-SMASH, FFMS2, vs-placebo, Vulkan, HDR,
  VFR, interlaced, provenance, render, and mounted-artifact proof.
- A fresh `gui-linux` image (`sha256:a1bcc48dde2b3476362836f48c68bf3e6a0195b852cd8756f5488d61ac5fdef9`)
  passed the in-container offscreen proof: production tooling absent, VSView CLI,
  `QApplication`, BestSource, doctor/availability, real media, named outputs, frame-zero
  rendering for both outputs, L-SMASH indexes, generated-session execution, and
  temporary cleanup.
- The built wheel exposes only the `vsview` extra and contains the new package; wheel
  and sdist path audits found no retired viewer module or removed Akarin/VSZip payload.
- The repository-wide stale scan was empty outside the explicitly permitted changelog
  and this plan; the locked production tree contains only the VSView dependency graph.
- A fresh independent final review found no remaining actionable issues and confirmed
  closure of the orphan-plugin, cache-v1-special-case, and executable Docker-proof
  findings.

The macOS host wrapper for `tools/verify_docker_gui.sh` remains documented-only. The
inside-container offscreen run proves the packaged Qt/VSView startup and generated
session/render path, but it is not a visible native Linux X11 usability test.

The Windows gates use `docs/media-runtime-windows-validation.md` plus the additional
VSView/Qt and visible-alignment checks above. Every skipped, unavailable, failed, or
deferred item needs an owner, reason, evidence, and revisiting condition.

## Zero-stale audit

Before calling the Mac cutover complete:

- no tracked runtime, test, package, lock, workflow, Docker, Windows, active-doc, image,
  config, event, or provenance surface may contain the retired distribution or its
  compatibility symbols;
- `uv tree` must contain no distribution named `vspreview`;
- no `prepare_vspreview_compatibility`, restored `vs_object`, patched `set_output`, or
  `DitherType.is_fmtc` mutation may remain;
- active generated-session paths must use `vsview_sessions` and `vsview_*` names;
- historical `CHANGELOG.md` (including its explicit upgrade guidance) and this active
  migration plan are the only expected textual references to VSPreview. Git history and
  user-generated workspaces are out of scope.

## Acceptance criteria

- A clean base installation launches VSView and loads the generated script using only
  documented public APIs.
- Multi-comparison output names/order and confirmation-derived offsets match the current
  functional contract.
- `manual_overrides.toml` v1 round-trips equivalent data from its new neutral owner.
- Alignment cache v1 is safely ignored; v2 preserves cache identity, precedence,
  embedded computed results, deterministic ordering, and atomic writes while storing
  only neutral interactive origins.
- JSON stdout remains clean and every intentional identifier break is documented and
  contract-tested.
- The Windows bundle contains the exact VSView/Qt graph and complete license/source
  inventory, with native preload before Qt/VSView.
- All Mac, Docker, hosted-Windows, and physical-Windows evidence is recorded.
- A fresh independent reviewer approves the alignment, doctor, VSView runtime/session,
  Docker, and Windows packaging hotspots or every finding is adjudicated with evidence.

No physical-Windows evidence means **Mac implementation complete; release blocked**,
not migration complete.

## Stop conditions

Stop before or during cutover if:

- base VSView needs an undeclared extra;
- only private APIs can satisfy named multi-output behavior;
- essential output ordering, alignment confirmation, or subprocess behavior cannot be
  retained;
- package or native dependency licensing/provenance is incomplete;
- Mac full/container proof fails or current tracked files retain nonhistorical stale
  implementation;
- the public contract and authority documentation cannot be updated together.

Stop before merge/release if:

- managed-Windows preload, Qt, VSView, BestSource, or native extensions fail;
- the bundle inventory, license/source notices, or wheel hashes are incomplete;
- an old VSPreview-era bundle accepts a code-only update instead of failing closed;
- physical GUI, GPU/HDR, real-media, or alignment behavior differs materially without
  an explicit product decision.

## Rollback

Rollback is the whole migration: revert the cutover to the last supported VSPreview
release. Do not add a compatibility fallback. Existing manual overrides remain valid;
alignment cache v1/v2 data may be ignored and recomputed after rollback. Preserve the
failed candidate's logs, inventory, screenshots, hashes, and review evidence before
reverting so the cause remains diagnosable.
