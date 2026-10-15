---
search:
  exclude: true
---

Status: Active
Scope: Implementation plan for the twenty supported code-quality change groups (CQ1–CQ6, CQ8–CQ13, CQ15–CQ22, including all four CQ21 subparts) from the 2026-10-15 planning handoff. CQ7 and CQ14 are excluded investigations. This plan does not itself authorize implementation, release, or publication.
Owner: Maintainer (Tristan Zine); plan prepared by a Claude Code planning session
Source: `v0.7.0` at `53d0a2ce` (documentation-only report commit on top of reviewed product revision `e036bc348431c948314019318d40f642c0923784`; `git diff e036bc3 53d0a2c` touches only the two review reports)

# Code quality remediation plan

## 1. How to use this plan

This is the canonical, durable implementation plan for the supported scope of
[the planning handoff](../reviews/2026-10-15-code-quality-planning-handoff.md)
(“the report”). Read the repository-root `AGENTS.md` and `.agents/project.md` (outside
the documentation site) and the runbook sections cited per package before starting a
package. Use
`develop-code` for implementation and `design-code`/`review-code`/`verify-code`
where those responsibilities arise; this plan supplies the decisions those skills
would otherwise have to re-derive.

Line anchors are from the planning checkout. Symbols and call paths are the durable
locators; re-resolve anchors at implementation time.

Terminology:

- **Package (P0–P11)**: one coherent, reviewable change (normally one PR or one
  commit series) with its own acceptance gates and rollback scope.
- **Confirmed defect / inferred risk / maintainability improvement**: the report's
  classifications, preserved here. A package that fixes a maintainability concern
  must not be described as fixing a defect.
- **Acceptance requirement**: evidence that must be obtained before the package is
  called complete. A requirement unavailable in a given environment stays open; it
  is never reported as passed.

## 2. Inputs, source identity, and planning evidence

The report was prepared against `e036bc34`. The task checkout is `53d0a2ce`, which
adds only the two report files, so every report claim applies to current source.
This plan re-verified the consequential claims below rather than re-auditing the
repository. Seven bounded, read-only design investigations (Windows install/update,
viewer transitions/fixtures, alignment resolution, render/tonemap/geometry,
selection/metric/warning, config/doctor/docs, and persisted decode/test support)
each answered named design questions; their conclusions were reconciled against
source by the plan owner and are incorporated below.

| Observation during planning | Result | Claim scope |
| --- | --- | --- |
| `uv sync --group dev --extra vsview --frozen` | Succeeded | Locked contributor environment exists in the cloud checkout |
| Report's focused baseline selection (`pytest -o addopts='' -q tests/services/test_alignment_decision.py tests/orchestration/test_execution_phase_plan.py tests/orchestration/test_phase_output_integration.py tests/services/test_report_viewer_state.py tests/services/test_report_viewer_viewport.py`) | 46 passed | Same baseline as the report; no implementation exercised |
| Appendix A viewer probe | Reproduced: Diff and Blink restore pair `0:1` with current `(0,0)` and persisted `0:1` overwritten to neutral | State/persistence through the Node fixture |
| Variant of Appendix A (3 clips; set `(2,2)` on same-source `0:0` before leaving Slider) | **New manifestation:** destination `0:1` becomes `(2,2)` in state and storage | Same mechanism as CQ1; folded into CQ1 |
| Appendix B metric enum probe (needs `PYTHONPATH=.` to import `tests`) | Reproduced: list/dict values escape as `TypeError`; invalid string recovers as `corrupted` | Actual reader with memory delivery |
| Appendix C decoder/timeout probe | Reproduced on Python 3.13.16 (int limit 4300) for VSView, metrics, TMDB, history; all four timeouts accept `inf` | Actual decoders/models |
| **New** config-loader probe (real temporary files) | `load_config` and `load_raw_config` raise raw `RecursionError` (deep inline tables) and `ValueError` (5,000-digit int); ordinary malformed TOML raises typed `ConfigParseError` | Confirms a CQ10 sibling at the user-config owner |
| Appendix D fixture probe | Reproduced `{"firstDocumentOwnsFocus":false,"secondDocumentOwnsForeignFocus":true}` | Test-support defect |
| Source read: `build_portable.ps1` `Main` | `Remove-Item -Recurse -Force -LiteralPath $OutDir` precedes `Get-Manifest` | CQ15 mechanism; no Windows execution |
| Source read: `build_update.ps1` payload | Code-only update ZIPs contain only `app/src/frame_compare`; the installed updater lives in `%LOCALAPPDATA%\Programs\FrameCompare\bin` and is replaced only by a bundle `install.ps1` | Determines how CQ16/CQ17 fixes reach users |
| Source read: updater `Invoke-SmokeCheck` | Target verification uses `-match [regex]::Escape($ExpectedVersion)`, a substring test (`0.8.0` matches `0.8.0rc1`; `1.0.1` matches `1.0.10`) | Additional exact-target defect inside CQ16 scope |
| Browser smoke with `REPORT_BROWSER=/opt/pw-browsers/chromium-1194/chrome-linux/chrome` | 18 failed, 3 passed: harness reports `Chrome never became ready` | **Capability gap** in this container (browser launch), not a product signal |
| `uv run --no-sync zensical build --clean --strict` (docs group installed) | Aborted: all warnings originate in the two review reports' host-absolute links; none from this plan | Existing docs-gate blocker, handled as P0 step 0 |
| `docker info` | Daemon unavailable | **Capability gap**: Docker media gate not runnable here |
| `pwsh`/`powershell` | Not installed | **Capability gap**: no PowerShell or Windows observation |

No product code, tests, or configuration were changed while planning. No Docker,
Windows, real-browser, native-media, or visible-Qt acceptance was obtained; every
such item below is an open acceptance requirement.

## 3. Repository obligations every package preserves

These are restated once; packages reference them as **O1–O10**.

- **O1** Runtime-free `--help`/`version`; no eager native-media import in CLI paths (`tests/cli/test_help_and_import.py`, `tests/test_runner_import_smoke.py`).
- **O2** Machine-clean JSON stdout, diagnostics on stderr, typed sanitized errors with documented codes and exit behavior.
- **O3** Fresh computed alignment stays a candidate until the audio/video decision owner authorizes it; provisional/unavailable evidence never becomes trim or computed-cache authority; valid zero ≠ unavailable.
- **O4** Original evidence survives manual confirmation; fresh estimator time, frame offsets, manual reference-FPS time, and historical cache evidence keep distinct meanings.
- **O5** Source freshness (path/size/mtime) is rechecked at acceptance, early-reuse return, and locked publication; frozen records do not replace those checks.
- **O6** Computed-cache authority and both required metric-cache reads (preflight before reservation; execution reacquisition) remain separate lifecycle checks.
- **O7** Deterministic artifacts: stable ordering, physical screenshot naming, report identity rules, atomic writes, explicit persistence boundaries; existing serialized formats unless this plan records an explicit migration.
- **O8** Owned cleanup and cancellation: batch stop admission, native draining, subprocess reaping, lock ownership, caller-owned injected loaders/HTTP clients.
- **O9** Import contracts (`importlinter.ini`): orchestration above {analysis | render | services}, which stay mutually independent, above vsview > vs > config > utils.
- **O10** Different evidence routes prove different claims: static/Node/mocked Python, real browser, native media/Docker, Windows PowerShell 5.1/7 and physical Windows, and visible Qt are not interchangeable.

Test-design rules for every package: preserve distinct behavioral proof; change
implementation-coupled assertions only when the obligation they protect is kept
elsewhere; no test-count targets; new tests are parallel-safe (`tmp_path`,
`monkeypatch`, no fixed ports/paths); reject unexpected HTTP.

## 4. Final architecture and behavior goals

When all packages are complete:

1. **Windows source installation never destroys an existing bundle.** The builder
   builds into disposable staging and refuses occupied or unsafe destinations; the
   source installer activates a freshly built, verified bundle only after success
   and handles user data by an explicit, reversible policy (P1).
2. **The updater owns one stable/RC version grammar** for extraction, signed range
   admission, and exact target verification, and **every source-tree replacement
   (apply and rollback) runs through one stage → verify → promote → smoke → commit
   transaction** with recovery that never leaves a missing or mixed tree (P2).
3. **The report viewer has one authority for pair offsets**: the current offset is
   derived from the selected pair, and one selection function owns pair repair and
   Blink active-source validity. Node fixtures own their documents, and Node
   harnesses assert each obligation once, with focused scenario execution (P3).
4. **Malformed persisted input recovers through each owner's existing policy**, and
   operation timeouts are finite (P4).
5. **Each run acquires configuration once.** Admission, callbacks, preview,
   preparation, execution, and post-actions read one `AcquiredRunConfig`; preview
   has no second override policy; `doctor` uses the same selected-config policy as
   run, including the installed shim's selection (P5).
6. **Each comparison's alignment resolution is one immutable record**, manual
   confirmation is a pure replacement, the V6 gates are evaluated once, and a
   prepared reusable-source-set candidate makes the cache publication decision
   readable in one place (P6).
7. **Selection is a coherent value read at phase execution**, its prepared domain is
   one replaceable value, recovery eligibility branches on a typed failure kind, and
   metric requests stay intact into analysis with one required-cache acquisition
   operation used at both lifecycle points (P7).
8. **Rendered artifacts disclose the actual applied tonemap per clip**, and render
   geometry consumes resolved active-picture facts with no dormant inference (P8).
9. **Rendering carries clip/frame structure end to end**: selected screenshots →
   prepared clip jobs → rendered clips, with no label-range reconstruction (P9).
10. **Producer-owned collection-policy warnings reach the final run outcome** (P10).
11. **U4 acceptance media has a focused recipe owner and a recipe-derived cache
    identity** with demand generation and full-matrix generation for the complete
    gate (P11).
12. **Public reference and acceptance documentation match current behavior** (P0,
    and same-pass updates inside P5–P9).

Explicitly not goals: a shared image loader or resampling pipeline (CQ14), a
request-slot/image-lifetime owner (CQ7), a global run-state hierarchy, a generic
policy/state/DI framework, an async render rewrite, a universal cache or codec
abstraction, dependency upgrades, CI/workflow redesign, and release publication.

## 5. Coverage matrix

Every supported finding and subpart maps to exactly one owning package (CQ22 has
distinct sub-items with distinct owners).

| ID | Classification | Package | Outcome that closes it |
| --- | --- | --- | --- |
| CQ1 | Confirmed defect (S2) | P3 | Derived pair offset; one `selectPair` transition; Appendix A and `0:0`-leak regressions pass in Node and real browser |
| CQ2 | Maintainability (S3) | P6 | `ComparisonResolution` single map; pure `confirm_manual`; `prepare_reusable_source_set`; parallel maps/repair deleted; on-disk publication proof |
| CQ3 | Maintainability (S3) | P9 | `SelectedScreenshot`/`PreparedClipRender`/`RenderedClip`; range plumbing, `RenderedBatchResult`, duplicate validators deleted |
| CQ4 | Maintainability (S3) | P7 | Execution-time selection reads; `SelectionSnapshot`; `PreparedSelectionDomain`; list-identity dependency gone |
| CQ5 | Maintainability (S3) | P6 (step 1) | `is_trusted_automatic` deleted; trust derived from empty `v6_failure_reasons`; dead fallback removed |
| CQ6 | Maintainability (S3) | P7 (step 1) | `SelectionFailureKind`; recovery branches on kind; serialized error unchanged |
| CQ8 | Confirmed defect (S2) | P5 | `AcquiredRunConfig` carried by `RunRequest`; runtime reacquisition and preview override policy deleted |
| CQ9 | Maintainability (S3) | P7 (step 2) | `calculate_metrics(request, …)`; `acquire_required_metrics` used by both reads; identity derived from sampling constants |
| CQ10 | Confirmed defect (S2 enum / S3 decoder) | P4 | Owner-specific recovery for enum shape, recursion, and integer-limit failures in metric, review-result, TMDB, history, probe, manual-override, reuse-cache, and user-config/preset readers |
| CQ11 | Confirmed defect (S2) | P8 | `AppliedTonemap` per clip through overlay/report; payload 1.3; identity from applied facts |
| CQ12 | Maintainability (S3) | P8 | Render geometry consumes resolved facts; inference modes/helpers deleted; stale architecture claim corrected |
| CQ13 | Maintainability/observability (S3) | P10 | Policy warning in `PublishPhaseOutput.warnings`; one final warning in result, summary, and record |
| CQ15 | Confirmed defect (S1) | P1 | Builder staging + occupied/unsafe refusal; source installer fresh target + post-verification activation + explicit user-data policy |
| CQ16 | Confirmed defect (S2) | P2 | Shared stable/RC grammar/ordering; range semantics; exact target verification |
| CQ17 | Inferred risk (S2) | P2 | `Invoke-SourceTreeReplacement` for apply and rollback; `backup.json` completeness record; `Restore-FromBackup` deleted |
| CQ18 | Confirmed defect (S3) | P5 | Doctor uses run's selection owner; shim injects selected config for doctor |
| CQ19 | Confirmed defect (S3) | P4 | `allow_inf_nan=False` on the four operation timeouts |
| CQ20 | Confirmed test-support defect (S3) | P3 (step 1) | Per-fixture element factories in viewer and lens harnesses; two-fixture isolation regression |
| CQ21a Node assertion mirrors | Maintainability (S3) | P3 (step 2) | Shared scenario runner; (c)-class fields moved into JS assertions; Python mirrors reduced to execution/completion checks |
| CQ21b U4 media recipes | Maintainability (S3) | P11 | Recipe support module; recipe-derived key; demand + full-matrix generation; measurements recorded |
| CQ21c Alignment scenario support | Maintainability (S3) | P6 (step 2) | Evidence/scenario support modules; literal presentation fixtures; producer→projection parity tests stay in services |
| CQ21d Windows spelling checks | Maintainability (S3) | P1 and P2 | Incidental spelling assertions near touched owners replaced by executable fixtures or artifact observations; structural checks kept |
| CQ22 doctor reference | Confirmed doc defect (S3) | P0 | `docs/reference/commands.md` doctor section matches no-HTTP contract |
| CQ22 no-cache reference + Windows acceptance text | Confirmed doc defect (S3) | P0 | `commands.md` `--no-cache` and `docs/media-runtime-windows-validation.md` describe scoped refresh |
| CQ22 geometry architecture claim | Confirmed doc defect (S3) | P8 | `docs/current-architecture.md` direct-call inference claim removed with CQ12 |
| CQ22 ownership/payload/disclosure docs | Same-pass documentation | P5, P6, P7, P8, P9 | Architecture/CLI-contract sections updated in the package that changes them |

CQ7 and CQ14 do not appear in this matrix by design (see §11).

## 6. Package overview, dependencies, and parallel execution

| Package | Title | CQ IDs | Priority | Hard prerequisites |
| --- | --- | --- | --- | --- |
| P0 | Public documentation corrections | CQ22 (doctor, no-cache, Windows acceptance) | Low risk, land early | none |
| P1 | Preserve installations during Windows source builds | CQ15, CQ21d (builder/installer tests) | **Highest (S1 safety)** | none |
| P2 | Updater version grammar and safe source replacement | CQ16, CQ17, CQ21d (updater tests) | High | P1's `build_portable.ps1` change merged (shared file) |
| P3 | Viewer fixture ownership, harness assertions, pair transitions | CQ20, CQ21a, CQ1 | High (S2 defect) | none |
| P4 | Persisted-input recovery and finite timeouts | CQ10, CQ19 | High (S2 enum defect) | none |
| P5 | One acquired run configuration and doctor selection | CQ8, CQ18 | High (S2 defect) | none |
| P6 | Alignment decision and resolution ownership | CQ5, CQ21c, CQ2 | Medium | none |
| P7 | Selection domain, failure kinds, metric acquisition | CQ6, CQ9, CQ4 | Medium | P5 and P10 merged; P4 merged (soft: `cache_io.py`) |
| P8 | Applied tonemap facts and render geometry | CQ11, CQ12 | High (S2 defect) | none (coordinate `render/prepare.py` with P5) |
| P9 | Structured render pipeline | CQ3 | Medium | P7, P8, P10 merged |
| P10 | Collection-policy warning propagation | CQ13 | Low risk, land early | none |
| P11 | U4 media recipe ownership | CQ21b | Medium | none (coordinate U4 module edits with P7) |

### 6.1 Shared files and conflict rules

| Shared file or resource | Packages | Rule |
| --- | --- | --- |
| `tools/windows_portable/build_portable.ps1` | P1 (`Main`, output staging), P2 (`Write-BundleInfo` version validation) | P1 merges first; P2 rebases |
| `tests/windows_portable/test_windows_portable_build_scripts.py` | P1, P2 | Same order as above |
| `src/frame_compare/orchestration/preparation.py`, `coordinator.py`, `tools/alignment_benchmark.py` | P5 (acquisition), P7 (domain, required read) | P5 first |
| `orchestration/execution_types.py`, `phase_output_application.py`, `phase_post_render.py` | P10, P7, P9 (and P8 for `phase_post_render.py` tonemap summary) | P10 first (smallest); then P7/P8 in either order; P9 last |
| `render/prepare.py` | P5 (delete `cli_overrides` branch), P8 (applied facts) | Either order; second rebases a small hunk |
| `render/batch/expansion.py` | P8 (geometry), P9 (jobs) | P8 first |
| `analysis/cache_io.py` | P4 (decode), P7 (`acquire_required_metrics`) | P4 first (small) |
| `tests/services/test_alignment_frozen_strings.py`, `tests/vsview/test_alignment_review_panel.py` | P6 (CQ21c and review-map signature) | Same package; CQ21c step precedes CQ2 step |
| `tests/integration/test_alignment_u4_acceptance.py` | P11 (recipes), P7 (`RunContext`/`PrepState` constructors at ~808, ~1118) | Either order; second rebases; never run two Docker verifiers concurrently in one checkout |
| `tests/orchestration/test_phase_tasks.py` | P7 only (CQ4/6/9) | One owner |
| Docker verifier media cache (`generated/test-media-cache`) | P5–P9, P11 gates | One verifier at a time per checkout |
| `docs/current-architecture.md`, `docs/current-cli-contract.md` | P0, P5–P9 | Each package edits only its sections; integration owner resolves textual conflicts |

### 6.2 Execution waves

- **Wave A (start immediately, in parallel):** P1 (priority reviewer attention), P0,
  P3, P4, P5, P6, P8, P10, P11. Parallel writers use isolated worktrees with one
  integration owner; disjoint file ownership is listed above.
- **Wave B:** P2 (after P1 merges; updater-only work may start in Wave A and rebase),
  P7 (after P5 and P10 merge; its CQ6 step may start in Wave A in a worktree).
- **Wave C:** P9 (after P7, P8, P10 merge).
- **Closeout:** integrated full native gate, Docker gate, browser smoke, Windows
  hosted verification, and the completion checklist in §13.

No package depends on CQ7 or CQ14.

## 7. Package specifications

Each package lists scope, exclusions, design (with the rejected smaller
alternative), ordered steps, caller migration and deletions, tests, gates,
compatibility, rollback, and exit criteria.

---

### P0 Public documentation corrections (CQ22: doctor, no-cache, Windows acceptance)

**Problem.** Three public passages contradict source and the canonical contract:

- `docs/reference/commands.md` Doctor section (~295–298) lists “the optional
  slow.pics and TMDB integrations” and says “The slow.pics check contacts the
  service.” Source and `docs/current-cli-contract.md` § “`doctor` Command Contract”
  (~2055–2061) say doctor makes no HTTP requests, has no `slowpics` check, and the
  `tmdb_api_key` check validates local configuration only.
- `commands.md` `--no-cache` (~225) says “Do not read or write the analysis cache.”
  Help (`cli/entry.py:298`) and the contract (~938–943) define scoped refresh: the
  matching shared entry is deleted during preparation, analysis recomputes, and the
  replacement persists; unrelated entries, alignment reuse, and TMDB caches are kept.
- `docs/media-runtime-windows-validation.md:322` expects “`--no-cache` does not read
  or persist reusable cache data.”

**Design.** Edit prose only, pointing to the canonical contract rather than restating
it. No mandatory documentation framework.

**Steps.**
0. Prerequisite for this package's docs gate: the strict site build currently aborts
   at `53d0a2ce` because the two 2026-10-15 review reports under `docs/reviews/` use
   host-absolute `/Users/tristan/...` links (22 “page does not exist” warnings; this
   plan contributes none). Convert those links to repository-relative links or code
   spans without changing report content, so the strict build can serve as evidence.
1. Rewrite the doctor paragraph: list runtime checks; state that TMDB is checked
   from local configuration and credential format only, that doctor makes no network
   requests, and that slow.pics connectivity is exercised only by publishing.
2. Rewrite the `--no-cache` description to the scoped-refresh behavior and the
   preserved caches.
3. Rewrite the Windows acceptance bullet: “`--no-cache` removes the matching analysis
   entry, recomputes, and persists a fresh entry; repeated runs without it then hit.”
4. Run `uv run --no-sync pytest -q tests/test_cli_contract_docs.py`,
   `git diff --check`, and the documentation site build
   (`uv sync --group dev --group docs --extra vsview --locked` then
   `uv run --no-sync zensical build --clean --strict`).

**Exclusions.** CQ18's new doctor options are documented in P5, not here.

**Compatibility/rollback.** Docs only; revert the commit.

**Exit criteria.** The three passages match source/contract; docs build strictly;
existing media cache E2E already covers regeneration, so no media run is required.

---

### P1 Preserve installations during Windows source builds (CQ15, CQ21d part)

**Problem (confirmed, S1).** `install.cmd` → root `install.ps1` →
`tools/windows_portable/install-from-source.ps1` defaults `-OutDir` to
`dist\frame-compare-portable-win-x64` (~154) and calls `build_portable.ps1`. Builder
`Main` (~1140–1149) recursively deletes an existing `$OutDir` before reading the
manifest, downloading, building, or verifying. That directory is the documented
installed bundle root (`tools/windows_portable/README.txt:22–43`,
`docs/getting-started/windows-portable.md:255–275`) holding `config\config.toml`,
`comparison_videos\`, `generated\`, and `app\.update_backups`. A rerun deletes them;
a malformed manifest or build failure leaves nothing. Any `-OutDir` reaches the same
deletion with no relationship checks.

Supporting facts used by the design:

- The active-install pointer already exists: `%LOCALAPPDATA%\Programs\FrameCompare\state\config.json`
  (`{schema_version, install_type, bundle_path}`), written atomically by the bundle
  `install.ps1` (~54–61). Readers: `shim/frame-compare.ps1`,
  `shim/frame-compare-update.ps1` (~279–304), `verify_extracted_bundle.ps1`.
- The AppData state `config.toml` written by `install.ps1` (~63–77) uses
  bundle-relative `comparison_videos`/`generated` paths; the shim runs from the
  active bundle directory. A newly activated bundle therefore does not see data left
  in the previous bundle.
- `write_bundle_inventory.py` `_assert_safe_bundle` (~298–321) rejects files under
  `config/` or `comparison_videos/`, so in-place preservation of user data inside the
  output root would fail the build's own inventory check, and overlaying a runtime
  onto old files is documented as unsupported.
- CI (`windows-portable-build.yml` ~92–104) passes `-OutDir dist/frame-compare-portable-win-x64`
  on a fresh checkout and never relies on overwriting.

**Chosen design.**

*Builder (`build_portable.ps1`): refuse occupied or unsafe output; build in staging.*

1. Before any filesystem mutation: resolve paths; read and validate the manifest and
   `artifacts`; validate relationships:
   - `OutDir` must not exist (a file, a directory, or a reparse point). There is no
     overwrite flag: maintainers delete disposable output explicitly.
   - `OutDir` must not be a drive root, the current directory, `RepoRoot`,
     `CacheDir`, `$PSScriptRoot`, or the manifest's directory, and must neither
     contain nor be contained by any of them, except that `OutDir` beneath
     `RepoRoot\dist` is allowed. `CacheDir` and `OutDir` must not nest either way.
   - Reuse the existing containment helper (`Test-PathWithin`,
     `verify_extracted_bundle.ps1` ~38–44) by moving it into a dot-sourced helper the
     builder can share, rather than writing a second copy.
2. Reserve `<OutDir>.staging-<guid>` as a sibling using the existing atomic
   reservation pattern (`New-AtomicallyReservedDirectory`, ~270–283; error 183 is a
   refusal). Run every existing build, runtime-smoke, and inventory step against
   staging.
3. Promote with `[IO.Directory]::Move(staging, OutDir)`; a destination that appeared
   meanwhile makes the move fail and the build fail without touching it.
4. On any failure remove only the staging directory (existing `finally` cleanup
   pattern). Never remove `OutDir`.
5. Relocation after build is safe: `._pth` entries are relative (~487–493) and the
   extracted-ZIP verifier already proves relocatability.

*Source installer (`install-from-source.ps1`, root `install.ps1`): fresh target,
activation after verification, explicit user-data policy.*

1. Default `-OutDir` becomes a fresh sibling under `dist\`:
   `frame-compare-portable-win-x64-<app_version>-<yyyyMMddHHmmss>`; an explicit
   `-OutDir` that exists is refused by the builder before mutation.
2. Read the current pointer's `bundle_path` (if any) as the previous bundle. The
   installer never deletes or rewrites the previous bundle's runtime or code.
3. Build and verify; only then handle user data, then run the new bundle's
   `install.ps1` (which atomically switches the pointer and replaces `bin` shims).
4. User data: new parameter `-UserData Move|Leave` on `install-from-source.ps1`,
   forwarded by root `install.ps1` (which today forwards only `-SkipSync`;
   `install.cmd` already forwards `%*`). Only the documented user locations
   `config\`, `comparison_videos\`, and `generated\` are considered; no other file is
   inferred to be user-owned or disposable.
   - `Move`: same-volume rename of each existing documented folder from the previous
     bundle into the new bundle (the new bundle never contains `config\` or
     `comparison_videos\` content, by inventory). All-or-nothing: if any rename fails,
     reverse completed renames and do not activate. Absolute paths written inside the
     user's config are not rewritten; the completion message names the old path.
   - `Leave`: activate without moving; the message lists the folders left behind.
   - Default when the previous bundle holds any of those folders and `-UserData` is
     absent: **see decision D1** (recommended: `Move`).
   - If no previous bundle or no user data exists, activate directly.
5. Old bundles are never deleted by the installer. Print the previous bundle path and
   state that it can be removed manually once the new one is accepted.

*Rejected alternatives.*
- **In-place preservation** (keep user folders in the output root while rebuilding):
  conflicts with the inventory's forbidden-content check and the documented
  “never overlay a runtime” rule, and requires inferring which files are disposable.
- **Refuse-only installer** (smaller: refuse the occupied default output and tell the
  user to delete/rename it): safe, but breaks the documented “rerun `install.cmd`”
  source-update path and pushes data handling onto users at the exact moment the
  report found data loss. It remains the fallback if D1 rejects any automated move:
  the builder's refusal alone already removes the destructive path.
- **Shared transaction code with the updater (P2):** the builder produces a whole
  user-owned root activated by a pointer under PowerShell 7; the updater swaps only
  `app\src\frame_compare` under a lock on Windows PowerShell 5.1. They share the
  stage → validate → commit principle, not code.

**Ordered steps.**
1. Add the shared path-relationship helper (moved, not copied) and builder
   pre-mutation validation; reorder `Main` so manifest validation precedes any
   mutation.
2. Implement staging reservation, promotion, and staging-only cleanup.
3. Update the source installer defaults, pointer read, `-UserData` handling with
   reversal, activation ordering, and messages; thread `-UserData` through root
   `install.ps1`.
4. Update docs: `tools/windows_portable/README.txt` (source builds now produce a
   versioned folder; the shim always uses the active bundle; user-data choices),
   `docs/getting-started/windows-portable.md` (~255–275), `INSTALL-WINDOWS.md` if it
   names the fixed folder, and the runbook's Windows section (maintainer rebuilds
   must remove disposable output first; builder refuses occupied output).
5. Tests (below), replacing incidental spelling assertions near the touched owners.

**Caller migration and deletions.** Delete the unconditional `Remove-Item -Recurse
-Force -LiteralPath $OutDir` and recreate step. CI invocation keeps working
unchanged (fresh checkout). No compatibility path keeps the old destructive behavior.

**Tests (CQ15 and CQ21d).**
- Flip `test_windows_portable_build_scripts.py` ~62–108 (currently asserts that a
  relative output directory is created even when the manifest is missing) to assert
  that nothing is created or removed when the manifest is missing or malformed.
- New Windows-executed builder fixtures (gated like existing ones: `os.name == "nt"`
  plus PowerShell discovery): occupied `OutDir` refused with sentinel files
  byte-identical; unsafe relationships (drive root, repo root, ancestor of repo,
  cache nesting, manifest directory) refused before mutation; injected failure after
  staging leaves no staging directory and no `OutDir`.
- Source-install fixture with a stubbed builder (existing entrypoint test style in
  `test_windows_portable_install_entrypoints.py`): previous bundle with
  `config\config.toml`, `comparison_videos\x.mkv`, `generated\run\…` sentinels and a
  pointer; assert repeat invocation builds a new folder, previous runtime/code
  untouched, `Move` relocates exactly the three folders and switches the pointer,
  `Leave` switches the pointer without moving, injected build failure leaves the
  pointer and previous bundle byte-identical, and an injected rename failure reverses
  completed moves and does not activate.
- CQ21d replacements in this package's owners (keep structural checks): replace
  `install_entrypoints` ~39–41 invocation-spelling assertions, `build_scripts`
  ~114/117 (`$bundleConfigDir` spelling), ~706 (`Get-AppVersionFromSource … $OutDir`
  spelling, which staging breaks while the obligation remains), and ~2442–2463 helper
  names with executable fixtures or bundle-inventory observations. Retain public-key
  gate, `git archive HEAD` committed source, `--require-clean-repo`, PowerShell 7
  prerequisite, CMD absolute-path fallbacks, and forbidden inventory content checks.

**Gates.**
- Linux/static: `uv run --no-sync pytest -q tests/windows_portable` (inspect skips:
  most PowerShell cases skip without PowerShell), `ruff`, `pyright`.
- **Acceptance requirement (Windows, PowerShell 7):** run the new builder and
  installer fixtures on Windows; run the runbook's “Windows Portable / Release-Path
  Verification” steps 3–4 for a built bundle; record a hosted `windows-portable.yml`
  `operation=verify` run at the package SHA (maintainer-dispatched).
- **Acceptance requirement (manual Windows):** populated-bundle rerun with real
  config/media/generated sentinels, both `-UserData` values, and an injected manifest
  failure; observe the previous bundle unchanged and the shim launching the new one.

**Compatibility.** Users invoking the builder on an existing output now get a refusal
instead of deletion (intended). Existing installs pointed at
`dist\frame-compare-portable-win-x64` keep working; the next source install creates a
sibling. Disk usage grows until users delete old bundles (documented).

**Rollback.** Revert P1. Bundles created with versioned names stay valid because the
pointer stores an absolute path.

**Exit criteria.** No code path removes an existing output root; manifest/build
failure leaves existing state byte-identical; repeat source installation preserves
user data per D1's chosen policy; Windows acceptance recorded or explicitly open.

---

### P2 Updater version grammar and safe source replacement (CQ16, CQ17, CQ21d part)

**Problems.**
- **CQ16 (confirmed, S2):** `frame-compare-update.ps1` extracts versions with
  `^frame-compare\s+([0-9]+(?:\.[0-9]+){1,3})$` (~584–599), falling back to raw
  `__version__` (~614–621); `Test-StringInRange` (~564–582) uses
  `[System.Version]::Parse`, so installed RC versions (`0.8.0rc1`) always fail
  admission. Release inputs support RC versions (`.github/workflows/release.yml`,
  `scripts/validate_release_contract.py:15–19`). `build_update.ps1` (~258–278) writes
  raw `to_app_version`, numeric `from_app_version_min = "<MAJOR>.<MINOR>.0"`, and
  `from_app_version_max = $null`. Additionally `Invoke-SmokeCheck` (~458–486)
  verifies the target by substring match.
- **CQ17 (inferred risk, S2):** `Restore-FromBackup` (~631–636) deletes the current
  source tree and copies the backup into place; explicit rollback (~638–674) uses it
  with no staging, completeness check, smoke check, or recovery. Apply (~676–1006)
  already stages `.new`, keeps `.old`, renames, smoke-checks, and recovers, but its
  final recovery fallback also uses `Restore-FromBackup`.

**Distribution fact.** Code-only updates carry only `app/src/frame_compare`; the
updater in `%LOCALAPPDATA%\Programs\FrameCompare\bin` changes only when a full
bundle's `install.ps1` runs. The P2 updater therefore reaches users through full
bundle installation, which always targets a fresh directory with no backups.
Installations already on an RC with the old updater cannot repair themselves through
a code-only update; release notes must direct them to a one-time full bundle install.

**Chosen design.**

*Version grammar (one PowerShell owner, one Python owner, one shared vector table).*
- New `tools/windows_portable/shim/frame-compare-version.ps1`, dot-sourced by the
  updater, `build_update.ps1`, and `build_portable.ps1`; installed into `bin` by
  bundle `install.ps1` and removed by `uninstall.ps1` (`Copy-InstallerFiles` already
  copies `shim\`). Functions: `ConvertTo-FrameCompareVersion` (parse or `$null`),
  `Compare-FrameCompareVersion`, `Test-FrameCompareVersionInRange`.
- Grammar (Windows PowerShell 5.1 compatible, `-cmatch`, ASCII `[0-9]` because .NET
  `\d` matches Unicode digits, component length capped so `[int]::Parse(...,
  InvariantCulture)` cannot overflow):
  `^(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})(?:rc([1-9][0-9]{0,8}))?$`.
  This is exactly the release contract's stable/RC grammar
  (`STABLE_VERSION_RE`/`RC_VERSION_RE`) with an overflow cap.
- Ordering: `(major, minor, patch, rc)` with the final release ordered after every
  `rcN` of the same base.
- Range semantics (decision D2): `max` inclusive; an RC `min` uses strict order; a
  stable `min` `X.Y.Z` also admits that base's release candidates (behaves as
  `X.Y.Zrc1`). The generator keeps emitting numeric `X.Y.0`, so updaters already in
  users' `bin` still parse stable bounds with `System.Version` and keep their
  stable→stable path.
- Malformed installed, bound, or target versions fail closed with a typed message.
- `Invoke-SmokeCheck` parses the reported version with the same grammar and compares
  exactly (`-ceq` on normalized strings, or `Compare-FrameCompareVersion -eq 0`).
- Audit every other version comparison in the updater (no-downgrade or same-version
  checks if present) and route it through `Compare-FrameCompareVersion`.
- Python remains authoritative in `scripts/validate_release_contract.py`. Add a JSON
  vector file (e.g. `tests/windows_portable/version_vectors.json`) consumed by a
  Python test against `validate_release_contract` and by a PowerShell-executed test
  against the PowerShell owner, so the two implementations cannot drift silently.
- Manifest format: unchanged fields and `schema_version`. Optionally add the grammar
  as a JSON-schema `pattern` on `to_app_version`/`from_app_version_*` in
  `update_manifest.schema.json`; this is validation tightening, not a format change.

*Source-tree replacement transaction (updater-only).*
- `Invoke-SourceTreeReplacement -BundlePath -TargetDir -CandidateDir -ExpectedInventory -ExpectedVersion`,
  called with the update lock held:
  1. Repair an interrupted prior run: target missing and `.old` present → rename
     `.old` back before anything else; stale `.new` removed.
  2. Stage the candidate into `.new` (copy).
  3. Verify `.new` against `ExpectedInventory` (exact relative path set, byte sizes,
     SHA-256).
  4. Rename target → `.old`, then `.new` → target (`Invoke-WithRetry` as today).
  5. Smoke-check with exact version.
  6. Commit by removing `.old`.
  On any failure: restore `.old` by rename. If recovery itself fails, keep `.old` and
  `.new`, and report both paths and the manual recovery step. Never delete-then-copy.
- Apply passes its authenticated, extracted, hash-checked payload directory and the
  signed manifest's file list as the inventory. Rollback passes the backup directory
  and the backup's own inventory.
- Signed archive authentication/extraction and backup identity/selection remain with
  their callers.
- Backup completeness record: after copying the current tree to
  `.update_backups\<id>\frame_compare`, write `backup.json`
  `{schema_version, app_version, media_runtime_fingerprint, requirements_lock_sha256, files:[{path, sha256, bytes}]}`
  last, via temporary file and move, as the commit marker. Hash from the source tree
  and verify the copy against it. Refuse an existing backup ID directory (IDs have
  one-second resolution and `Ensure-Directory` would merge).
- `list-backups` and `rollback` treat a backup without a valid `backup.json` as
  unavailable (“completeness record missing”), extending the documented policy that
  identity-less legacy backups are not migrated. In practice the P2 updater never
  coexists with pre-P2 backups, because it arrives only through a fresh full-bundle
  directory.

*Rejected alternatives.* Stripping suffixes or mapping `rcN` into a fourth numeric
component (silently misorders and breaks exact verification); an inlined grammar copy
in each script plus a parity test (drifts; three scripts need it); a general
versioning library (new dependency, not needed); keeping `Restore-FromBackup` as a
“simple” rollback (it is the risk).

**Ordered steps.**
1. Add `frame-compare-version.ps1`, vectors, and Python/PowerShell vector tests.
2. Migrate extraction, Python fallback, range admission, and smoke verification;
   migrate `build_update.ps1` validation and `min` derivation; validate
   `Write-BundleInfo` `app_version` in `build_portable.ps1` (after P1 merges);
   install/uninstall the helper in `bin`.
3. Add `backup.json` creation/verification and backup-ID refusal.
4. Implement `Invoke-SourceTreeReplacement`; migrate apply (promotion, smoke,
   recovery) and rollback to it.
5. Delete `Restore-FromBackup` and every fallback call to it.
6. Update the runbook Windows section (version grammar, backup completeness record,
   transaction recovery material), `README.txt` update/rollback text, and the
   changelog/release-note guidance for RC users needing one full reinstall.

**Tests.**
- Signed apply E2E (`test_windows_portable_update_apply_e2e.py`, currently numeric
  `1.0.0`/`1.0.1` fixtures): add RC→RC, RC→stable, stable→RC within a line (per D2),
  stable→next-minor RC refused, inclusive `max`, malformed installed/bound/target
  values refused before mutation, exact target mismatch (`0.8.0` vs reported
  `0.8.0rc1`; `1.0.1` vs `1.0.10`) triggering recovery.
- Rollback/transaction failure injection, comparing `_snapshot_bytes` of the current
  tree: unreadable backup file, truncated backup (inventory mismatch), copy failure,
  rename failure, smoke failure, and an interrupted state (`target` missing, `.old`
  present) repaired on the next invocation. Retain successful rollback,
  invalid/incompatible-backup refusal before lock creation, lock ownership, and purge
  serialization.
- `list-backups`: missing/invalid `backup.json` listed unavailable.
- Parametrize apply/rollback E2E over `powershell.exe` and `pwsh` on Windows; today
  the helper prefers `pwsh`, so Windows PowerShell 5.1 is not exercised for the
  updater.
- CQ21d replacements: `update_scripts` ~680 (`"Get-BundleAppVersion" in updater`;
  behavior covered at `apply_e2e` ~389–400), ~731–732, ~740–742, ~766–771 (ordering
  against the deleted `Restore-FromBackup`), and re-anchor ~646–649's no-bypass intent
  on behavior. Keep PKCS1/SHA256, signature-before-parse ordering (~685), schema
  constants, and no-interactive-bypass structural checks.

**Gates.**
- Linux: `uv run --no-sync pytest -q tests/windows_portable tests/workflows`
  (Python vector test runs; PowerShell cases skip—inspect skips).
- **Acceptance requirement (Windows, PowerShell 5.1 and 7):** updater E2E above.
- **Acceptance requirement (runbook step 5–6):** build the code-only update ZIP,
  prove matching-runtime apply/rollback and mismatched-runtime refusal, sign it, and
  record the hosted `windows-portable.yml` run; if signing cannot run, mark signing
  documented-only and require maintainer confirmation.

**Compatibility.** Manifest fields unchanged. Old installed updaters keep working for
stable numeric installations. RC installations need one full bundle install to obtain
the new updater (documented). Backups gain `backup.json`; older updaters ignore it.

**Rollback.** Revert P2; bundles installed with the P2 helper in `bin` are replaced by
the next bundle install. Backups with `backup.json` remain usable by older updaters
(extra file ignored).

**Exit criteria.** One grammar owner used by extraction, range, generator, bundle
info, and smoke; exact target verification; no delete-then-copy restoration remains;
every replacement goes through the transaction; failure injections leave the current
tree intact or recoverable with reported material; Windows 5.1/7 evidence recorded or
explicitly open.

---

### P3 Viewer fixture ownership, harness assertions, and pair transitions (CQ20, CQ21a, CQ1)

**Problems.**
- **CQ20 (confirmed test-support defect):** `tests/services/viewer_state_harness.js`
  keeps module-level `activeDocument` (~30); `fakeElement` (~94) builds
  `domMechanics(() => activeDocument)`; `loadViewer` reassigns it (~274), so
  `focus`/`remove`/`replaceChildren` (`dom_fixture.js` ~45–66) act on the latest
  fixture's document. `lens_harness.js` has the same defect (`focusDocument` ~20,
  reassigned ~176; scenarios at ~428–513 use an older environment after
  `coarseMouse` ~402 replaced the document). Async groups run under `Promise.all`
  (~2134).
- **CQ21a (maintainability):** harness summaries mirror JS assertions into Python
  expectations; some mirrored fields are the only check of a behavior.
- **CQ1 (confirmed, S2):** `state.alignmentPreset/alignX/alignY` (viewer.js ~90–92)
  are a second mutable copy of `pairAlignments[key]`. `setLeftClip` (~982),
  `setRightClip` (~992), `swapPairClips` (~1005) store → mutate → repair → load;
  `setMode` (~1645) repairs the pair with no store/load; `persistViewerState`
  (~1092–1095) stores the current fields into the newly selected pair on every
  persist. Result: Appendix A overwrite, and the planning-time variant in which a
  same-source `0:0` offset leaks into the restored pair.

**Chosen design for CQ1: derive the committed offset; one selection function.**
- `viewport.js`: `currentAlignment()` returns a normalized copy of
  `pairAlignments[currentPairAlignmentKey()]` or the neutral default. A private
  `writeCurrentAlignment(a)` normalizes, applies the existing clip-count/key guards,
  clears raw drafts, and writes the map entry. `setManualAlignment` (~558) and
  `setAlignmentPreset` (~546, `custom` keeps current x/y) write through it, then
  `applyAlignment` and persist. `commitRawAlignmentInput` (~603), `applyAlignment`
  (~611–618), and `alignmentStatusValue` (~642–649) read `currentAlignment()`.
  `rawAlignX/rawAlignY` stay as transient drafts.
- `viewer.js`: `selectPair({left, right, mode, activate} = {}, {render = true} = {})`:
  resolve indexes, set mode, repair a distinct pair when the mode requires it
  (Slider same-source stays valid), resolve `activate` after repair, apply Blink
  keep-in-pair, clear raw drafts if the pair key changed, and render (render
  persists).
- `inspector.js` (~378–380) reads `currentAlignment()`.
- Rejected: (1) adding `loadCurrentPairAlignment()` in `setMode` (fixes the reported
  symptom, misses the `0:0` leak path through persist, and keeps the protocol in
  every caller); (2) a transition function that still stores/loads internally (leaves
  two authorities; any future direct left/right writer reintroduces the bug); (3) a
  new selection-model module (about 30 lines of logic; adds an asset-assembly
  ordering constraint without removing more coordination than (chosen)).

**Chosen design for CQ20.** Replace `fakeElement` with
`createElementFactory(documentFor)`; `loadViewer` creates the document, then
`const element = createElementFactory(() => document)`, sets `document.body =
element()`, and returns `element` on the fixture. Scenario-level `fakeElement()`
calls (~489, 497, 776, 898–899, 939, 958, 960, 1145, 1201, 1207, 1463–1465,
1721–1723) become `fixture.element()`. Delete the global so a stray use throws.
Apply the same per-environment closure to `lens_harness.js`. `grid_view_harness`,
viewport, inspector, and review harnesses do not use the shared mechanics and need
no change. Run async scenario groups sequentially for clear failure attribution.

**Chosen design for CQ21a.**
- Shared `tests/services/harness_runner.js`: each harness exports named scenario
  functions; the runner executes them sequentially, selects names from argv or
  `FC_NODE_SCENARIOS`, supports `--list`, exits 2 for unknown names, prints
  `scenario <name> failed` with the stack to stderr, prints `{"ran":[…],"failed":[…]}`
  as the last stdout line, and exits non-zero on any failure.
- `tests/services/node_harness.py`: `run_node_harness(harness, *, args=(), timeout)`
  plus a helper asserting exit code and that `ran` equals the requested (or listed)
  names. Keep the locked `nodejs_wheel` runtime, timeouts (10 s default, 30 s
  review), and exit checking.
- One pytest invocation per harness (recommended over per-scenario parametrization:
  avoids ~45 Node startups and a Python mirror of scenario names). Focused execution
  is `FC_NODE_SCENARIOS=<name> uv run --no-sync pytest -q <bridge test>` or running
  the harness under Node directly.
- Summary-field disposition (from the planning classification):
  - **(c) only Python checks it → move into a JS assertion first**: viewer
    `inspectorFrameSources`, `modalKeyboardAccessibility` (Tab/Shift-Tab/Escape
    `defaultPrevented`), `paletteOrientationState.savedOrientation`,
    `restoredWidthFitNoVisibleRadio` (zoom, unchecked radios, single tab stop),
    `gridShortcut`, `proximityStateMachine`, all `paletteProximityWiring` fields,
    `singleModeAlignment.mode`, final `inspectorBlinkKeyboardState` values; grid
    `desktopPageLimit`/`mobilePageLimit` (or confirm `visibleIndexes` already
    asserts them); review_state `records`; viewport `storageDelegated`.
  - **(a) restates a JS assertion → delete the Python mirror** (e.g.
    `viewerStorageKey`, `restoreFourClip`, `pairSwitchFourClip`, filmstrip and
    keyboard groups, `directionalFourClip.swappedAlignment`, Blink interval/labels,
    escape-order handler, `alignmentStatus.reset`, `deferredDiffGridNavigation`,
    `mainImageUnavailable` retry label/recovered).
  - **(b) fixed success markers → delete** (lens: all 42; review_controller: all 6;
    grid `layouts`/`desktopPages`/flags; review_state other fields; viewer flags such
    as `blinkGesturePause`, `rovingTabWrapped`, `reversePairAlignment`,
    `gridModeBoundary`, `lazyReviewController`).
  - **Emitted but never checked → delete** (`defaultPairRule`, `*.alignmentStatus`
    strings, `canvasAlignX/Y`, `swappedPair`, `blinkControls.status`, badge text,
    inspector `currentFrameIdx`/`blinkIntervalMs`).
  The implementer re-verifies each field's class against the harness at
  implementation time; a field whose JS assertion cannot be located is class (c).

**Ordered steps.**
1. CQ20 fix in viewer and lens harnesses; add the two-fixture isolation scenario
   (focus, remove, replaceChildren affect only the owning document). Commit.
2. CQ21a runner/bridge; migrate viewer, lens, grid, review_state,
   review_controller, and viewport harnesses; move (c) fields into JS assertions,
   then remove mirrors. Prove focused execution and failure reporting with a
   deliberate, uncommitted assertion break in one scenario, then restore. Commit.
3. CQ1: implement `currentAlignment`/`writeCurrentAlignment`, `selectPair`; migrate
   callers; delete the old protocol. Add regressions. Commit.

**Caller migration (CQ1).**
`setLeftClip(i)` → `selectPair({left:i})`; `setRightClip(i)` →
`selectPair({right:i, activate: blink ? 'right' : undefined})`; `swapPairClips`
keeps its overlay/grid/single-clip guard then `selectPair({left:R, right:L})`;
`setMode` keeps Grid pan conversion in/out, calls `selectPair({mode}, {render:false})`,
then timer/DOM/render as today; `applyDefaultSelection` →
`selectPair({left, right, activate:'left'}, {render:false})`; `restorePersistedState`
sets active then `selectPair({mode, left, right}, {render:false})` then normalizes
the map; `resetCurrentPairAlignment` deletes the key, clears drafts, applies, and
persists (the key stays absent); `resetAllPairAlignments` clears the map. Keyboard
shortcuts, digit keys, `cycleClip`, and select/button events keep calling the
wrappers.

**Deletions (CQ1).** `storeCurrentPairAlignment`, `loadCurrentPairAlignment`,
`applyAlignmentState`, `currentAlignmentState`, `applyAlignmentPresetOffsets` (folded
into the writer); the store call in `persistViewerState`; the store/load lines in
selectors and restore; scattered repair/Blink calls replaced by `selectPair`;
`applyAlignmentState(neutral)` in resets; the three `state` alignment fields. Harness
fixture initializations of those fields (viewer_state ~295–297, viewport ~72–73,
inspector ~196–197) and viewport-harness stubs (~110, ~190) migrate to the new
interface; ~40 `viewer.state.alignX` reads become `currentAlignment()`.

**Preserved behavior.** Directional pair keys, valid same-source Slider, single-clip
`0:0`, storage key `frame-compare:report-viewer:${report_id}:viewport` and
`pairAlignments` schema, malformed-state normalization, restored width-fit, keyboard
and focus behavior, Blink pause intent, Grid pan-unit conversion, and stale Diff
image rejection. One intentional difference: visiting a pair without editing it no
longer writes a neutral entry (absent already means neutral on restore).

**Tests.**
- Node regressions (viewer harness): Slider same-source → Diff and → Blink, with a
  preexisting `(7,3)` destination offset and with none; the `0:0` `(2,2)` variant;
  assert `currentAlignment()` and the persisted map, then `restorePersistedState()`.
  Retain reverse-pair and restore semantics cases.
- Browser (`tests/browser/test_report_browser_smoke.py`): add
  `_append_pair_offset_mode_transition_probe` in the existing `--dump-dom` style
  (like `_append_width_fit_restore_probe` ~955): clear storage; Slider; type 7/3 into
  `#align-x`/`#align-y` with `input` and `blur`; set `#right-select` to 0; click Diff;
  record pair, `getComputedStyle(.rv-right).transform` (`matrix(1, 0, 0, 1, 7, 3)`),
  `#alignment-status`, and persisted `pairAlignments['0:1']`; repeat for Blink and an
  unset destination; record into one `data-` JSON attribute and assert all cases.
- Retain all Node suites in the report's viewer verification table and the four
  browser cases listed there.

**Gates.**
- `uv run --no-sync pytest -q tests/services/test_report_viewer_state.py tests/services/test_report_viewer_viewport.py tests/services/test_report_grid_view_state.py tests/services/test_report_lens_state.py` plus the review-state/inspector bridges.
- **Acceptance requirement (real browser):** `uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py` with a launchable Chrome/Chromium (`REPORT_BROWSER`), inspecting skips; or the CI `report-browser` job result at the package SHA. (Not obtainable in the planning container.)
- Logic verification (`pyright`, `ruff`) for the Python bridge changes. No native media.

**Compatibility/rollback.** No payload or storage-schema change; revert P3 commits
independently (fixture, runner, transition are separate commits).

**Exit criteria.** Every selection-changing entry point goes through `selectPair`;
no code stores or loads pair offsets as part of a selection change; both
reproductions fail before and pass after; fixtures cannot touch another fixture's
document; every Node obligation is asserted once in JS and the bridge checks
execution/completion; real-browser case recorded.

---

### P4 Persisted-input recovery and finite timeouts (CQ10, CQ19)

**Problems.**
- **CQ10 (confirmed):** enum decode checks set membership before type
  (`analysis/cache_io.py` `_parse_active_rect_source` ~546–556,
  `_parse_active_rect_detection_mode` ~559–562), so list/dict escape as `TypeError`
  past `load_cached_metrics`'s `_CacheParseError` handling (~226). Decoders leak
  `RecursionError` (deep nesting) and integer-limit `ValueError` at several owners.
  Planning confirmed the same leak in user config and found a sibling at
  `_parse_algorithm_identity_json` (~571–576, `json.loads` of a nested string, run
  before the hash check).
- **CQ19 (confirmed):** `ScreenshotsConfig.ffmpeg_timeout_seconds` (~209),
  `SlowpicsConfig.timeout_seconds` (~273), `image_upload_timeout_seconds` (~282), and
  `TmdbConfig.timeout_seconds` (~323) accept `inf` (NaN is already rejected by `ge`).

**Chosen design.**
- `src/frame_compare/utils/serialized_decode.py` exporting one documented constant
  `SERIALIZED_DECODE_FAILURES: Final = (RecursionError, ValueError)`, explaining that
  `JSONDecodeError`, `TOMLDecodeError`, `UnicodeDecodeError`, and the integer-digit
  limit error are `ValueError` subclasses. `utils` is importable from every affected
  layer (O9). Each owner wraps **only its decode statement** and maps the failure to
  its existing policy, preserving its own branch order (`FileNotFoundError`/`OSError`
  first; typed hook errors re-raised first).
- Rejected: wrapper functions that decode and classify (they would rewrap
  duplicate-key hook errors as “unreadable” and hide the `OSError`-versus-parse
  distinction the probe and TMDB owners rely on); broad `except Exception` or
  `TypeError` swallowing (hides programmer errors); arbitrary byte caps on metric
  caches (duration-scaled arrays).
- Optional bounded hardening that the implementer may include only with a test:
  refuse a TMDB cache file larger than the existing writer bound
  (`TMDB_CACHE_MAX_BYTES`, `tmdb_cache.py` ~34).
- CQ19: add `allow_inf_nan=False` to the four fields, matching the existing pattern
  at `schema_models.py` ~83–84 and ~118. No new timeout framework. Cancellation
  remains the interrupt for bounded external operations; the documented distinction
  from uninterruptible already-admitted native work is unchanged.

**Per-owner changes.**

| Owner | Change | Resulting policy |
| --- | --- | --- |
| `analysis/cache_io.py` enum parsers | `if not isinstance(value, str) or value not in _ALLOWED: raise _CacheParseError` | `corrupted` → normal acquisition recomputes; cache-only raises `CacheCorruptionError` |
| `cache_io.py` JSON read (~212–216) | add `SERIALIZED_DECODE_FAILURES` beside `OSError` | `corrupted` |
| `cache_io.py` `_parse_algorithm_identity_json` (~571–576) | catch decode tuple → `_CacheParseError` | `corrupted` |
| `cache_io.py` `read_cache_version` (~181–191) | widen | returns `None` (“unknown”) |
| `vsview/alignment_review_contract.py` result read (~289–300) | `except AlignmentReviewContractError: raise` then `(OSError, *SERIALIZED_DECODE_FAILURES)` → existing “unreadable” error | optional review: `rejected_result` with retained authority (`services/alignment_vsview.py` ~420–422); forced review: `AudioAlignmentError` (~309–312) |
| `services/tmdb_cache.py` load (~272–285) | widen | cache miss; next store rewrites (today a long-int file is never repaired) |
| `services/run_result_record.py` `read_run_result` (~530–533) | convert `RecursionError` to `ValueError` around `tomllib.load` only | `_history_entry` isolates an unavailable entry; `resolve_history_report` raises `HistoryOpenError` |
| `orchestration/probing/probe_cache.py` (~223–237) | add decode tuple to the parse branch | read mode `{}` with warning; update mode still raises `_ProbeCacheReadError` and does not overwrite |
| `services/alignment_manual_overrides.py` (~77–92, ~157–172) | widen both | `None` / `corrupt_on_write` (existing) |
| `services/alignment_reuse_cache.py` (~119–133) | widen | cache ignored; write starts fresh |
| `config/schema_sources.py` `_read_file` (~21–24) | re-raise `TOMLDecodeError`/`UnicodeDecodeError` unchanged; map `(RecursionError, ValueError)` to `ConfigParseError(path, "configuration exceeds TOML parser limits")` | typed `FC-1002`-family config failure, exit 2 (O2); never silent defaults |
| `config/loader.py` `load_raw_config` (~153–163) | same mapping | typed config error for wizard paths |
| `config/presets.py` (~52–63) | same mapping to the preset owner's existing typed parse error | typed preset failure |

Not changed: `tmdb_cache.py` ~106/~183 membership-before-type (already contained per
entry); `run_result_record.py` tuple membership (does not hash); subprocess JSON
(ffprobe) is not persisted state.

**Ordered steps.** (1) Add the constant and its contract test; (2) per-owner changes
in the table; (3) CQ19 field constraints; (4) tests; (5) note finite timeout bounds in
the configuration reference only if it documents bounds today.

**Tests (real temporary files; assert the policy result, not the exception type).**
- `tests/utils/test_serialized_decode.py`: deep JSON (`'['*10000`), deep TOML (1,500
  nested inline tables), 5,000-digit JSON/TOML integers, invalid UTF-8 → each an
  instance of the tuple (guards interpreter drift).
- `tests/analysis/test_cache_validation.py` (pattern ~103, helpers
  `_cache_io_test_helpers.py`): valid control hits; `[]`/`{}` for both enum fields,
  deep file, long integer, deep `algorithm_identity_json` → `corrupted`; recompute in
  `tests/analysis/test_metrics.py` (~245); cache-only refusal in
  `tests/orchestration/test_phase_tasks.py` (~525/565) and
  `test_execute_run_cache_modes.py` (~272) raises `CacheCorruptionError` without
  computing.
- `tests/vsview/test_alignment_review_contract.py` (~819): deep/long-int params; the
  duplicate-field message is unchanged. `tests/services/test_alignment_vsview.py`
  (~381): `rejected_result`, no persisted override, retained computed offset, forced
  review error.
- `tests/services/test_tmdb_cache.py` (~209): miss, then a store repairs the file.
- `tests/services/test_run_result_record.py` (~239/260): one deep record among valid
  ones is an isolated unavailable entry; `resolve_history_report` raises
  `HistoryOpenError`.
- `tests/orchestration/test_probe_cache_load.py` (~123): read miss; merge refuses and
  leaves the shared file unchanged.
- `tests/services/test_alignment_manual_overrides.py` (~45/158),
  `test_alignment_reuse_cache.py` (~673).
- `tests/config/test_loader.py` (~85): `load_config`/`load_raw_config` raise
  `ConfigParseError`; CLI-level JSON error test in `tests/cli/test_run_json_errors.py`
  observes a single typed error object; `tests/config/test_presets.py` (~63).
- CQ19: extend `tests/config/test_schema.py` (~66–70 non-finite pattern, ~252–256),
  `tests/config/test_slowpics.py` (~103–107), and `tests/config/test_loader.py` for
  `inf` from TOML and from `FRAME_COMPARE_TMDB__TIMEOUT_SECONDS=inf`, expecting
  `ConfigValidationError`; minimum-value tests unchanged.

**Gates.** Logic verification plus full native suite (config loading is in the full
verification list). VSView change is pure result validation: focused Python proof
(runbook) — no GUI proof. No Docker gate (no native execution contract change).

**Compatibility/rollback.** No format change. Behavior change only for malformed or
pathological inputs and explicit `inf` timeouts (now rejected with a typed error).
Revert P4 to roll back.

**Exit criteria.** Every listed owner returns its documented policy for wrong-shape,
deep, and long-integer inputs, with a valid control; no new broad catches; the four
timeouts reject non-finite values with typed errors.

---

### P5 One acquired run configuration and doctor selection (CQ8, CQ18)

**Problems.**
- **CQ8 (confirmed, S2):** `cli/run_command.py` admission validates the selected
  path (~263) but loads from unexpanded `args.config_path` (~271), validates contracts,
  configures logging, builds callbacks (~307–313; slow.pics visibility ~372; retry
  consent ~393–407) and preview from that snapshot. `RunRequest`
  (`orchestration/types.py` ~24–44) carries `root`, `config_path`,
  `config_overrides`; `orchestration/preparation.py` (~541–550) calls
  `prepare_preflight` (`preflight.py` ~382–424), which reselects, reloads, revalidates,
  lists inputs, and reapplies overrides (`resolve_effective_config`). Post-upload
  actions (~336) and report-open suppression (~353) use the cached admission load.
  Admission and runtime can disagree (reproduced in the report). Preview
  (`cli/output.py` `print_at_a_glance` ~181–260, `_resolve_preview_tonemap_settings`
  ~169–177) reapplies override policy on already-effective config;
  `TonemapCliOverrides` (`config/overrides.py` ~17–20) and the render resolver's
  `cli_overrides` branch (`render/prepare.py` ~30–53) exist for preview.
- **CQ18 (confirmed, S3):** `doctor_checks.py` (~620–645) resolves TMDB config by an
  upward workspace search from the current directory, else defaults+environment. Run
  uses `--root` (default `.`) and `--config` (`cli_helpers.py` ~142–152,
  `preflight.resolve_selected_config_path` ~260–280 with the portable state-config
  exception ~249–257). The installed shim (`shim/frame-compare.ps1` ~28–67, ~170–187)
  injects the selected bundle or AppData config for run/wizard/preset/history, not
  doctor. Doctor accepts only `--json` (`cli/entry.py` ~430–441).

**Chosen design (CQ8).** New dependency-light module
`src/frame_compare/orchestration/run_inputs.py` (imports config and
`orchestration.preflight`, which the CLI already imports at module level; must not
import `orchestration.types`, which pulls httpx and the VS loader — O1):

```python
@dataclass(frozen=True, slots=True)
class AcquiredRunConfig:
    root: Path            # resolved workspace root
    config_path: Path     # resolved selected config (incl. portable state exception)
    config: ConfigSchema  # TOML + env once, CLI overrides applied, contained paths validated

def select_run_config_path(config_path: Path | None, root: Path | None) -> tuple[Path, Path]
def acquire_run_config(*, root, config_path, overrides: CLIConfigOverrides,
                       load_config_fn=load_config) -> AcquiredRunConfig
def resolve_run_workspace(inputs: AcquiredRunConfig) -> WorkspacePaths
def build_run_request(*, root, config_path=None, overrides=CLIConfigOverrides(), **controls) -> RunRequest
def refresh_report_auto_open_preference(inputs: AcquiredRunConfig, load_config_fn=load_config) -> bool | None
```

- `RunRequest` carries `inputs: AcquiredRunConfig` (required) plus the existing
  run-only controls (`no_cache`, `from_cache_only`, `skip_analysis`,
  `skip_metadata`, `no_upload`, etc.). `root`, `config_path`, and
  `config_overrides` are removed: there is no optional path beside optional settings.
  (`build_run_request` imports `RunRequest` lazily to keep `run_inputs` light.)
- `resolve_run_workspace` recomputes path facts and containment from the admitted
  config **at each use**; it is a use-boundary check against the current
  filesystem, not a second config read. (Decided over caching `WorkspacePaths` in the
  acquired value because containment and input existence are external state.)
- Path selection runs before `parse_run_options` so path-escape errors keep their
  precedence; environment expansion happens once inside acquisition (fixing the
  unexpanded-path admission load).
- `execute_prep` consumes `request.inputs.config` and `resolve_run_workspace`, still
  checks the input directory and lists sources once (source freshness at use, O5).
  `prepare_preflight`, its duplicate input listing, `build_preflight_input_dir_override`,
  and the `resolve_effective_config` call are deleted (decided: `prepare_preflight`
  has no production caller after migration; tests compose through
  `build_run_request`).
- CLI `handle_run` acquires once; dry-run, logging, diagnose-paths, write-config
  (`write_config_to(inputs.config_path, inputs.config)` through the existing
  secret-safe persistence), `validate_run_contracts`, callbacks, preview,
  clipboard/browser actions, and upload suppression read `inputs`.
  `build_effective_config_loaders` is deleted.
- The intentional post-run auto-open refresh (`docs/current-cli-contract.md`
  § “Report Auto-Open Ownership”) remains as `refresh_report_auto_open_preference`:
  rereads `inputs.config_path`, returns `report.auto_open`, or `None` on failure
  (report opens, matching ~982–983). Used by `maybe_open_report_path` (~715–735) for
  the pre-prompt confirmation check and the post-run open.
- Preserved boundaries: runtime-free simple commands (O1); dry-run exits before any
  request or side effect; wizard raw edits keep `load_raw_config` and are untouched;
  secret-safe persistence; source freshness and containment rechecked where sources
  and paths are used, not frozen at admission.
- Rejected smaller alternative: recheck selected flags at runtime against a second
  load (leaves two snapshots and a reconciliation policy). Rejected alternative:
  move admission after runtime acquisition through preparation (pulls runtime
  imports into admission, risking O1, and still leaves callbacks needing the value).

**Preview (CQ8 second half).** `print_at_a_glance(console, *, inputs, run_controls,
no_upload_flag: bool, verbose)`; every displayed setting reads `inputs.config`;
`run_controls` supplies run-only flags; `no_upload_flag` exists only for the
“disabled by --no-upload” label (~330). Visible change: the `input` row shows the
resolved input directory rather than the raw `--input` string. Delete
`TonemapCliOverrides`, `resolve_tonemap_settings`'s `cli_overrides` parameter and
branch, `_resolve_preview_tonemap_settings`, and the override fallbacks
(~192–259). The CLI pre-run tonemap line continues to show **requested** settings
(it is a plan, not an applied-transform disclosure; see P8).

**Conditional cleanup (bounded, decided rule).** `_restore_explicit_fields` and
`_replace_model_fields_set` (`config/overrides.py` ~100–127) appear unnecessary:
`dump_config_with_explicit_color` (`persistence.py` ~23–41) already drops unset color
placeholders and presets pass the roundtrip suite without restoration. Remove them in
P5 **only if** `tests/config/test_color_roundtrip.py` and the override/persistence
suites pass unchanged except relaxing `tests/config/test_overrides.py` ~137/142
(`== {"preset"}`) to “contains no placeholder field”; otherwise keep them and record
why. No authored/resolved color hierarchy is introduced.

**Chosen design (CQ18) — see decision D4.** Add `--root/-r` and `--config/-c` to
`doctor`, resolved by the same `resolve_root_and_config`/`resolve_selected_config_path`
used by run (one selection owner, including the exact portable state-file exception).
Pass `DoctorConfigSelection(root, config_path, explicit)` through `RunDoctorFn`,
`run_doctor`, and `collect_checks` to the TMDB check. Add `doctor` to the shim's
injection (`Get-ConfigInjectionIndex`). Doctor remains tolerant: default config
missing → defaults+environment; explicit config missing/invalid → reported in the
TMDB check's details, not a top-level failure; no HTTP; JSON schema unchanged.
Doctor drops the upward root search to match run. Preserved: environment-variable
precedence, local-only/no-HTTP behavior, the exact portable state-file containment
exception (no sibling LocalAppData files), and runtime-free option parsing (doctor's
selection must not import native media before checks run).
Rejected: a Python copy of the shim's bundle-then-state rule (two fallback owners); a
hidden environment variable (an unsupported second selection mechanism).

**Ordered steps.**
1. Add `run_inputs.py`; migrate CLI admission and `RunRequest`; migrate
   `execute_prep`; delete reacquisition helpers.
2. Migrate preview; delete `TonemapCliOverrides` and the resolver branch (coordinate
   the `render/prepare.py` hunk with P8).
3. Migrate `tools/alignment_benchmark.py` (~265–272) to `build_run_request`; migrate
   test builders (`tests/cli/test_cli_output.py` ~125,
   `tests/orchestration/test_execute_run_result_record.py` ~48) and the ~122
   `RunRequest(...)` constructions across 23 test files through a shared
   test-support helper wrapping `build_run_request`.
4. Conditional explicit-field cleanup per the rule above.
5. Doctor selection, CLI options, shim injection.
6. Docs: `docs/current-architecture.md` § Runtime Flow and Configuration persistence
   (single acquisition owner); `docs/current-cli-contract.md` § Shared Path Resolution
   Rules (add `doctor`), the shim paragraph (~151–163), `doctor` contract (options,
   no upward search), and Config Validation/Logging (single acquisition);
   `docs/reference/commands.md` doctor options. Decide in-package whether the wizard
   “Next steps” text should mention `doctor --root/--config` (only if it currently
   names doctor without context; keep wizard tests aligned).

**Tests.**
- Rewrite rather than delete: `test_run_request_config.py` (~97, ~147) asserts the
  acquired config; `test_run_command.py` (~404, ~436) asserts `inputs.config_path`;
  `test_preflight.py` (~528–654) becomes the acquisition suite;
  `test_execute_run_lifecycle.py` (~465) observes `ConfigNotFoundError` from
  acquisition; remove `test_execution_phase_plan.py` (~144) only after confirming its
  sole obligation (overrides survive on the request) is replaced by the acquisition
  suite.
- **New CLI regression (config changed after admission):** initial config
  `use_vsview=false`, `ignore_lead_seconds=5`, `auto_upload=false`,
  `report.auto_open=true`; a fake `runner.run` rewrites the file to `use_vsview=true`,
  `ignore_lead_seconds=0`, `auto_upload=true`, `confirm_upload_after_report=true`,
  `auto_open=false`; inside the fake assert
  `request.inputs.config.audio_alignment.use_vsview is False`, retry consent present,
  slow.pics confirmation callback absent; after the run assert the report was not
  opened (refresh sees the later edit). `--json` variant: exactly one JSON object on
  stdout, exit 0.
- **New orchestration regression:** acquire; rewrite the file; patch
  `config.loader.load_config` to fail; `execute_prep` uses admitted settings. Delete a
  source file after acquisition: `NoVideosFoundError` still raised.
- Preview: `tests/render/test_tonemap_wiring.py` (~106–131) rewritten to pass an
  effective `ColorConfig`; CLI preview tests assert values come from effective
  config.
- Retain: dry-run, logging precedence, report-open (`tests/cli/test_run_report_open.py`),
  color roundtrip, preparation/cache/lifecycle, benchmark, and import suites; O1 tests.
- Doctor: `tests/orchestration/test_doctor_network.py` (~128) and
  `tests/cli/test_doctor_command.py` with disabled/enabled/invalid configs selected by
  `--config`, compare doctor's TMDB settings with run acquisition for the same
  selection; no-HTTP assertion retained. Shim routing matrix
  (`tests/windows_portable/test_windows_portable_shim_e2e.py` ~34): doctor with only
  the AppData state config present receives it.

**Gates.** Full verification (CLI and config behavior). Docker gate at the package
head (every media E2E passes through the restructured preparation path; no observed
output should change). **Acceptance requirement (Windows):** the installed shim with
only an AppData config containing `[tmdb] enabled=false` produces a doctor TMDB result
consistent with run's selected config.

**Compatibility.** `RunRequest` is internal (no supported import API); no shim kept.
New public doctor options (D4). Preview `input` row text changes. JSON outputs
unchanged.

**Rollback.** Revert P5 as a unit (internal callers migrate atomically).

**Exit criteria.** Exactly one config acquisition per run (assert by counting
`load_config` calls in the regression); no runtime reapplication of overrides; preview
has no override logic; benchmark and tests use the acquisition owner; doctor and run
select the same config for the same arguments and under the shim.

---

### P6 Alignment decision and resolution ownership (CQ5, CQ21c, CQ2)

**Problems.**
- **CQ5:** `v6_failure_reasons` (`services/alignment_decision.py` ~287) and
  `is_trusted_automatic` (~326) encode the same five gates; `decide_after_video`
  (~595–633) calls both and keeps a now-unreachable `"no_single_offset"` fallback
  (~628) and `reasons or (primary_reason,)` (~633). Sole production caller:
  `decide_after_video`; also exported in `__all__` (~828) and used by three tests.
- **CQ21c:** `tests/vsview/test_alignment_review_panel.py` (~56–67) imports builders
  from collected modules `tests/services/test_alignment_evidence.py` and
  `test_alignment_frozen_strings.py`; producer fixtures (~595, ~743) call private
  `alignment_video` helpers (`_chunks`, `_build_targets`, `_lag_to_frame`,
  `_hypothesis_winner`, `_target_resolution`, `_check_points`).
- **CQ2:** `align_clips_from_request` (`services/alignment.py` ~1206) keeps parallel
  `results_map` and `provenances`. Writers: manual overrides (~291–297), shared reuse
  (`alignment_previous_offsets.py` ~100–106), computation (~938–952, in a worker
  thread), confirmation `_apply_confirmed_vsview_offsets` (~233–243, result only)
  then `_record_interactive_provenance` (~1108–1129, reads the old result to keep the
  fallback). `AlignmentProvenance.evidence_availability` is always derivable from the
  result. Cache eligibility is split across `shared_write_is_service_eligible`
  (~204–226), `_is_write_eligible` (~472–486, repeating the allowed-origin set at
  ~464), and `save_reusable_offsets` (~545–605).

**Chosen design (CQ5).** `trusted = not reasons`; `primary_reason = reasons[0]`;
`failed_gates = reasons`; delete `is_trusted_automatic`, its `__all__` entry, and the
dead fallback. Keep `V6_PRIMARY_REASON_ORDER`, the authority-status reason appended
last, search-edge refusal, unavailable/inconclusive early returns, candidate
construction, recount, and A4b regrouping. No generic policy engine.

**Chosen design (CQ21c).**
- `tests/services/alignment_evidence_test_support.py`: move `DIGEST`,
  `OTHER_DIGEST`, `POLICY`, `stream`, `retimed_comparison_stream`, `collection`,
  `attempt_with_chunks` out of `test_alignment_evidence.py` (~37–178). Importers:
  `test_alignment_evidence.py`, `test_alignment_frozen_strings.py` (~65),
  `test_alignment_policy.py` (~18), `test_alignment_video.py` (~38),
  `test_alignment_video_freshness.py` (~22), the panel test (~56). Do not merge with
  `tests/alignment_review_test_support.py`'s different `stream` (digests differ).
- `tests/alignment_review_scenarios.py`: public literal presentation fixtures —
  moved as-is: `review_attempt`, `boundary_video_inconclusive_attempt`,
  `singleton_chunk_target_attempt`, `production_nested_targets_attempt`,
  `multi_context_attempt`, `audio_failed_video_confirmed_attempt`; new literal
  records for `target_context_attempt(credible, resolution)`,
  `resolved_run_context_attempt(shape, resolutions)`, `established_counts_attempt(...)`
  built from `VideoTargetEvidence`, check points, decision, recount, and stability
  directly.
- Producer builders (`_producer_target_context_attempt`,
  `_producer_run_context_attempt`, `_producer_count_attempt`) stay in
  `test_alignment_frozen_strings.py` as producer→projection integration cases, plus
  new parity tests asserting each literal scenario equals producer output across the
  panel matrices (8 target cases, 3 run shapes, 4 count cases).
- Retain literal actionable text, zero/unavailable authority, evidence identity,
  ordering, compact/full projection, and persistence assertions.

**Chosen design (CQ2): consolidate into one record (report's “smallest coherent
option”), no accepted/unresolved variant types.**

```text
ComparisonResolution (frozen; services/types.py; replaces AlignmentProvenance)
  comparison_cache_key: str
  result: AlignmentResult            # current authority; result.audio_attempt = original current-run attempt
  origin: AlignmentWriteProvenance   # the existing five literals (renamed from `provenance`)
  computed_fallback: AlignmentResult | None = None
  evidence_availability (property): "current_attempt" if result.audio_attempt else "historical_details_unavailable"
  accepted_offset (property): result.frame_offset if result.applied else None
  __post_init__:
    origin != "computed_this_run"  ⇒ result.applied
    computed_fallback is not None  ⇒ origin == "interactive_confirmed_this_run"
                                      and computed_fallback.applied
                                      and computed_fallback.algorithm == "cross_correlation"
```

Decisive tradeoff: about 13 real call sites branch on `applied`; `AlignmentResult`'s
existing `__post_init__` already makes applied-without-offsets unrepresentable, and
phase/`ClipState` consumers need `AlignmentResult` unchanged. Variant types would
remove only ~5 redundant rechecks while forcing a split representation. The invariants
not enforced today are cross-field (origin vs applied, fallback vs origin,
availability vs attempt), which one record's validation expresses directly. No
origin→`result.source` invariant (existing fixtures legitimately pair
`shared_computed_offsets` with `source="computed"`). Keep `"not_computed"` in the
services literal only if a consumer still needs it; the VSView wire contract keeps its
own literal (`alignment_review_contract.py` ~68).

Pure operations in new `services/alignment_resolution.py`:
`resolution_from_override`, `resolution_from_reuse`, `resolution_from_computation`,
`confirm_manual(resolution, *, frame_offset, fps_reference, reference_clip,
comparison_clip)`, and `ordered_results(request, resolutions) -> tuple[AlignmentResult, ...]`.
`confirm_manual` builds a `"manual"` result with `frame_offset / fps_reference`
(existing reference-FPS conversion), keeps the previous `stability` and the same
`audio_attempt` object, sets origin `interactive_confirmed_this_run`, and sets
`computed_fallback` to the previous result only when it was applied and
`cross_correlation`. Acceptance cases:

| Starting evidence | Decision | Resulting record |
| --- | --- | --- |
| Provisional +12 | Confirm 0 | manual 0 applied; identical attempt object/digest; no fallback |
| Trusted +42 | Confirm +47 | manual +47; attempt still trusted +42; fallback +42 |
| Shared computed with stability, no attempt | Reuse | origin `shared_computed_offsets`; availability historical |
| Unavailable | Keep current / missing optional review | `confirm_manual` not called; record unchanged |

**Cache candidate.** `prepare_reusable_source_set(request, resolutions) ->
ReusableSourceSetCandidate | None` in `services/alignment_reuse_cache.py` (it owns the
origin mapping and serialization prerequisites; placing it in
`alignment_previous_offsets` would create an import cycle). It unions today's rules:
complete requested set by `comparison_cache_key` (unrelated items ignored), applied,
allowed origins, at least one current-run origin, `computed_this_run` requires a
`trusted_automatic` attempt plus stability, `shared_computed` requires stability,
interactive requires no fallback or a fallback with stability.
`save_reusable_offsets(request, candidate, *, accepted_at=None)` accepts only a
candidate and keeps the entry source-currentness check, a
`candidate.source_set_key == source_set_cache_key(request)` guard, the lock, merge,
source recheck under the lock, atomic publication, and `OSError` warning (O5, O7).
Cache schema `CACHE_VERSION = "2"` and entry bytes unchanged (`_entry_from_provenance`
renamed `_entry_from_resolution`, same dict). Existing behavior retained and asserted,
not silently changed: a mixed publication rewrites the source set with one fresh
`accepted_at`. Direct `save` with only shared-computed entries no longer publishes
(tightening with no production path).

**Ordered steps.**
1. CQ5 (independent commit).
2. CQ21c support modules and parity tests (independent commit; touches the panel and
   frozen-string tests before CQ2 changes them).
3. Add `ComparisonResolution`, `alignment_resolution.py`, and the candidate API with
   unit tests.
4. Migrate `align_clips_from_request` to `resolutions: dict[str, ComparisonResolution]`:
   overrides, shared reuse (`apply_shared_reuse` returns new resolutions and its
   completion flag; keep `require_current_alignment_sources` inside each application,
   previous_offsets ~97), computation (worker returns `(fps, dict)` instead of
   mutating shared maps; cancellation/cleanup precedence at ~993–1005 unchanged),
   confirmation loop (`resolutions[key] = confirm_manual(...)`).
5. Migrate presentation (`alignment_presentation.py` `print_pre_review_summary`
   ~263, `present_alignment_evidence` ~313–314, `_normal_evidence_rows` ~73–114),
   diagnostics (`alignment_diagnostics.py` ~81–127), offsets map, review map
   (`_build_audio_review_map`; wire payload unchanged), and progress to take
   resolutions.
6. Replace the publication call with `prepare_reusable_source_set` + `save`.
7. Delete `AlignmentProvenance` and its stored availability field, every
   `results_map` parameter, `_apply_confirmed_vsview_offsets`,
   `_record_interactive_provenance`, `shared_write_is_service_eligible` and its
   `__all__` entry, `_is_write_eligible`, the duplicate origin set, and the
   completeness logic inside `save`.
8. Keep every `require_current_alignment_sources` call (alignment.py ~1217, ~1272,
   ~1305, ~1337, ~1366, ~1393).
9. Update `docs/current-architecture.md` § Alignment evidence, reuse, and native review
   (~651–657) for the record and candidate owners.

`AlignmentOperationOutcome` (types.py ~122–127) and the ordered `AlignmentResult`
tuple consumed by `orchestration/phase_alignment.py` (~116–146) are unchanged, so P6
does not depend on P7.

**Tests.**
- CQ5: `test_v6_trusted_predicate_requires_each_conjunct` becomes
  `test_v6_failure_reasons_require_each_gate` asserting exact tuples (`()`,
  `("no_single_offset",)` via `_authority(passed=False, status="no_single_offset")`,
  `("video_check_unavailable",)`, `("competing_offset",)`,
  `("unresolved_audio_disagreement",)`, `("competing_offset_confirmed_by_video",)`);
  the A4b test (~445–459) asserts `()` and `("competing_offset",)`; ordering tests
  (~509, ~529) and `test_decide_after_video_trusts_the_recounted_authority` unchanged.
- CQ21c: verify by temporarily breaking `alignment_video._build_targets` (uncommitted):
  only services producer/parity tests fail; panel tests pass.
- CQ2 new observations with a real temporary shared cache:
  - **A (mixed published):** seed at T0 via prepare+save with an interactive entry
    and a computed entry; decline prompt; real writer with `_accepted_at_now` → T1;
    on disk exactly both keys with expected origins/offsets/correlation/stability and
    `accepted_at == T1`.
  - **B (all-historical, nothing published):** remove the writer patch in the test at
    ~227 (~275); assert cache bytes, `accepted_at`, and `mtime_ns` unchanged; add a
    parametrized `keep_current` review outcome.
  - **C (reconfirmed override on disk):** replace the mock at ~856–873; on disk
    interactive entry (offset 5, time 5/24, no `computed_result`) and computed entry.
  - **D (acceptance cases end to end, `cache_results=True`):** trusted +42 → +47
    writes interactive entry with `computed_result.frame_offset == 42`; provisional →
    0 writes no `computed_result`; extend
    `test_manual_zero_preserves_rejected_attempt_and_diagnostic_digest`
    (`test_alignment_workflow_vsview.py` ~134).
  - **E:** `tests/services/test_alignment_resolution.py` unit tests for the table and
    invariants; candidate unit tests for each eligibility rule.
- Replace the patched-writer assertion in
  `test_align_clips_from_request_mixed_cached_computed_and_new_computed_write_back`
  (~541, ~603) with A's on-disk observation.
- Fixture churn (~35 sites in `test_alignment_reuse_cache.py`,
  `test_alignment_previous_offsets.py`, `test_phase_alignment_contract.py` ~336,
  review-map callers in diagnostics/evidence/panel/contract tests, frozen strings
  ~147/~1198–1214, cancellation ~156/~285) goes through one `_resolution` test helper.
- Retain every row of the report's “Alignment authority and persistence” table.

**Gates.** Full verification. Docker gate at the package head
(`tests/integration/test_alignment_u4_acceptance.py::test_real_phase_v6_cache_matrix`
and alignment E2E must pass — real audio/video → phase → cache). No VSView GUI proof
(wire payload unchanged); run `tests/vsview` focused suites. Do not touch
whole-track memory bounds or streaming cleanup (no resource proof needed).

**Compatibility.** Cache schema v2 and bytes unchanged
(`test_repeated_accepted_cache_writes_have_identical_bytes` ~801 guards it); review
wire payload unchanged; internal APIs change atomically.

**Rollback.** Revert CQ2 commits; CQ5 and CQ21c commits can stay.

**Exit criteria.** One map of complete records; confirmation is one pure replacement;
no caller sequences result-then-provenance updates; one candidate decision feeds
publication; V6 trust has one source; on-disk publication proofs A–D pass.

---

### P7 Selection domain, failure kinds, and metric acquisition (CQ6, CQ9, CQ4)

**Problems.**
- **CQ6:** `SelectionError` (`analysis/errors.py` ~6–36) serializes code `FC-4012`,
  message `"Frame selection failed: {reason}"`, `hint`, and
  `details={reason, requested, found, ...}`. Recovery matches exact reason strings
  (`full_window_retry.py` `_ELIGIBLE_REASONS` ~47–51, `_EMPTY_EXCLUSION_WINDOW_REASON`
  ~52/~85, `_eligible_for_recovery` ~262).
- **CQ9:** `metric_cache_request_for_clip` (`orchestration/active_rect.py`
  ~125–145) builds `MetricCacheRequest` (`analysis/types.py` ~71–79); Analyze
  (`phase_selection.py` ~324–339) decomposes it; `calculate_metrics`
  (`analysis/metrics.py` ~168–196) rebuilds it; `_build_metrics` (~95–146) flattens
  it; identity fields are re-enumerated in `cache_io._metric_cache_request_token`
  (~105–128), `_metrics_metadata_matches_request` (~252–277), and `compute_cache_key`
  (~62–96). Required-cache classification is duplicated in `preparation.py`
  (~296–321) and `phase_selection.py` (~304–322, ~366–385). `metric_identity.py`
  (~79–80) hardcodes `1/4` and `8` while `sampling.py` (~8–9) owns the constants.
- **CQ4:** `execution.py` binds `state.selected_frames` into `partial`s (~216, ~300);
  `phase_output_application.py` mutates it by slice assignment (~26, ~37, ~49) and
  writes related metadata to `RunContext` separately (~27–28, ~42–44, ~52–57).
  The prepared selection domain (window, analysis clip, token, override, metric
  request) is rebuilt in `preparation.py` (~624–667 cache-only, ~707–756 normal) and
  `full_window_retry.py` (~194–215, assigning seven fields ~217–223), copied
  field-by-field in `coordinator.py` (~164–176), `tools/alignment_benchmark.py`
  (~286–293), and the U4 test (~1118).

**Chosen design (CQ6).** `class SelectionFailureKind(Enum)` in `analysis/errors.py`
(orchestration may import analysis, O9). `SelectionError(..., kind=SelectionFailureKind.UNCLASSIFIED)`
stores `self.kind`; **not** added to `details`, so message and JSON are byte-identical.

| Producer | Kind | Recoverable |
| --- | --- | --- |
| `analysis/selection.py` ~64 `empty_metrics` | `EMPTY_METRICS` | no |
| `analysis/selection.py` ~131 `insufficient_candidates` | `INSUFFICIENT_METRIC_CANDIDATES` | yes |
| `analysis/window.py` ~43 | `NO_CLIPS` | no |
| `analysis/window.py` ~57 ignore windows leave none | `EMPTY_SELECTION_WINDOW` | window-recovery path only |
| `analysis/window.py` ~71 fps | `INVALID_CLIP_FPS` | no |
| `phase_selection.py` ~94 random after user frames | `INSUFFICIENT_RANDOM_CANDIDATES` | yes |
| `phase_selection.py` ~120 no user/random frames | `NO_INITIAL_FRAMES` | yes |
| `phase_selection.py` ~402 reference trims | `EMPTY_REFERENCE_DOMAIN` | no |
| `phase_alignment.py` ~505/~613/~623 aligned reselection | `INSUFFICIENT_ALIGNED_CANDIDATES` | no |
| `full_window_retry.py` ~254 runtime wrapper; ~349 `ExclusionRecoverySelectionError` | `UNCLASSIFIED` | no (fatal after accepted recovery) |

`_RECOVERABLE_KINDS = frozenset({INSUFFICIENT_METRIC_CANDIDATES, INSUFFICIENT_RANDOM_CANDIDATES, NO_INITIAL_FRAMES})`;
the empty-window check is `error.kind is EMPTY_SELECTION_WINDOW`. Default
`UNCLASSIFIED` is explicitly nonrecoverable. Rejected: a literal-string set with a
lint rule (still couples prose to policy); a repository-wide error taxonomy.

**Chosen design (CQ9).**
```python
# analysis/metrics.py
def calculate_metrics(request: MetricCacheRequest, *, video_paths: list[Path],
    config: AnalysisConfig, cache_dir: Path, selection_domain: str | None = None,
    reporter=None, vs_loader=None, timing_recorder=None,
    memory_limit_mb: int | None = None) -> MetricsAcquisition
# analysis/cache_io.py (preparation imports cache_io, not metrics/VS)
def acquire_required_metrics(request: MetricCacheRequest, *, video_paths: list[Path],
    config: AnalysisConfig, cache_dir: Path, selection_domain: str | None) -> FrameMetrics
```
- `acquire_required_metrics` raises the existing typed failures: `corrupted` →
  `CacheCorruptionError` (FC-4006); `version_mismatch` → `CacheVersionMismatchError`
  (FC-4007); `not_found`/`mismatched_inputs` → `MetricsCalculationError("Cached metrics
  missing or mismatched ({reason}).")` (FC-4002). Path selection via
  `find_metrics_cache_file` with `metrics_cache_filename` fallback, as today.
- **Both reads kept (O6):** preflight (`preparation._validate_cache_state`) before
  output reservation, and Analyze's cache-only reacquisition that fails without
  computing. No memoization of the first read; no predictive read for normal
  compute-or-hit.
- Fingerprint bytes: a private `_keyed_request(request, video_paths)` fills only an
  absent `analysis_source_path` with `video_paths[0]` (today's `metrics.py` ~187).
  `metric_frame_range` and `effective_fps` stay unresolved for keying (absent →
  `full_source`/`source`; explicit full range and explicit FPS equal to source FPS
  still key differently). Resolution happens only at computation
  (`_resolved_metric_frame_range`, new `_resolved_fps`); `_build_metrics` writes
  concrete observed values to v8 metadata as today; request matching unchanged.
  Schema v8 and explicit persisted validation unchanged.
- Identity constants: derive `fraction` and `max_bursts` from
  `sampling.PERFORMANCE_SAMPLING_FRACTION`/`PERFORMANCE_BURST_COUNT`; keep the semantic
  label and `_ALGORITHM_VERSION`; add a test pinning the constants to 1/4 and 8 so a
  sampling change forces a deliberate algorithm-version decision.
- Rejected: merging probe and metric caches (different lifetimes/failure contracts);
  forcing sliced sparse metrics to equal a canonical sample map.

**Chosen design (CQ4): execution-time reads plus two focused values.**
- (a) Replace the align/render `partial`s with closures that read
  `ctx.selection.frames` at execution (as publish/report already do). Phase functions
  keep explicit `selected_frames`/`frames` parameters, so their many direct test calls
  remain valid.
- (b1) `SelectionSnapshot` (frozen, `orchestration/context.py`, `RunContext.selection`,
  default empty):

  | Field | Coordinates |
  | --- | --- |
  | `frames: tuple[int, ...]` | comparison/reference-relative (offset from current reference trim start; mapped by `map_aligned_to_source_frame`) |
  | `breakdown: SelectionBreakdown \| None` | reference source frames |
  | `details_by_source_frame: SelectionDetailsByFrame \| None` | reference source frames |
  | `analysis_metrics: FrameMetrics \| None` | analysis-source metric coordinates (`metric_source_start`, `sampled_source_frames`) |

  Removes `ExecutionState.selected_frames` and `RunContext.selection_breakdown`,
  `selection_details_by_source_frame`, `analysis_metrics`. Only `apply_phase_output`
  assigns it: FramePlan builds a new snapshot with `analysis_metrics=None`; Analyze
  builds one with metrics; Align uses `replace(...)` **and** updates
  `ctx.reference`/`ctx.comparisons` in the same branch because frames are relative to
  the reference trim Align changes. `frame_plan_warnings` stays on `ExecutionState`.
- (b2) `PreparedSelectionDomain` (frozen, `orchestration/selection_domain.py`, which
  owns the token builder ~237): `selection_window` (per-clip trim-relative — a fourth
  vocabulary, kept out of the snapshot), `analysis_clip: ClipState | None`
  (pre-alignment prepared clip), `token: str` (`""` when no analysis clip),
  `metric_request: MetricCacheRequest`, `full_window_retry_override`. Built by
  `build_prepared_selection_domain(*, clips, config, analysis_clip, selection_window,
  override)`, which always calls `metric_cache_request_for_clip`. It carries neither
  clips (Align replaces them; a second authority) nor config (`ctx.config` remains the
  one effective config). Recovery becomes three coherent assignments
  (`ctx.config`, `ctx.reference/comparisons`, `ctx.selection_domain`) plus the
  existing preflight-warning filter.
- Rejected: a universal immutable run-state hierarchy; carrying clips in the domain;
  keeping the list-identity contract with a comment.
- Recovery and warning obligations preserved unchanged: authored versus effective
  config separation; explicit interactive consent; no retry offer in JSON, quiet,
  cache-only, or disabled-analysis modes; exactly one accepted retry; fatal failure
  after an accepted retry; active-rectangle refinement/recomputation;
  selection-domain/cache-key recomputation; no uniform fallback after failed accepted
  recovery; replacement of superseded frame-plan warnings with unrelated warnings
  retained; preflight active-rectangle warning updates. The snapshot must never
  conflate reference source-frame details with trimmed comparison-frame selection.

**Ordered steps.**
1. CQ6 (independent commit; can start before P5/P10 merge).
2. CQ9 analysis-side signatures, `acquire_required_metrics`, identity constants;
   migrate preparation and Analyze to the shared read; migrate callers:
   `phase_selection.py` (~324), `tools/benchmark_analysis_tiers.py` (~408, and the
   hand-built request ~930), tests (`tests/analysis/test_metrics.py` 16 calls,
   `test_metrics_loader_seam.py` ~43, `tests/integration/test_loadsources_probe_cache.py`
   ~257, fakes in `test_phase_tasks.py`, `test_execute_run_cache_modes.py`,
   `test_execute_run_run_folders.py`). Delete the keyword decomposition,
   reconstruction, and duplicated classification.
3. CQ4: `PreparedSelectionDomain` and builder; migrate preparation branches,
   `PrepState` (five fields → `selection_domain`), coordinator copy, recovery,
   `phase_selection.py` (~298–303, ~277–278, ~206–210), `phase_alignment.py`
   (~167, ~183–185), `full_window_retry.py` (~128, ~137, ~200, ~244), benchmark (~286),
   and test constructors (`phase_task_helpers.py` ~208, `execute_run_helpers.py` ~403,
   `test_phases.py` ~55, overlay tests, `test_ffmpeg_overlay_application.py` ~57,
   U4 ~808/~1118).
4. CQ4: `SelectionSnapshot`; execution-time closures; `apply_phase_output` writer;
   readers (`phase_alignment.py` ~204/~213, `phase_render.py` ~49/~53,
   `phase_post_render.py` ~424–440, `coordinator.py` ~59–93 and ~218–262). Introduce
   one orchestration helper producing selection rows (frame, reference source frame,
   label/detail/category) from the snapshot, used by report frame details now and by
   P9's render request construction later (removes the duplicate label derivation in
   `phase_render.py` ~44–55 and `phase_post_render.py` ~428–441).
5. Delete the removed fields and slice assignments.
6. Docs: `docs/current-architecture.md` § Runtime Flow (selection ownership,
   execution-time reads), § Shared caches (single required-read owner, two lifecycle
   reads), and the CLI contract § Run-Only Full-Window Selection Recovery only if
   wording references reason strings.

**Tests.**
- CQ6: migrate `test_phase_tasks.py` (~385, ~430) direct constructions to pass
  `kind=`; add: rewording a qualifying reason keeps consent/retry; an `UNCLASSIFIED`
  error carrying an old eligible string gets no offer; each producer sets its kind;
  JSON error output byte-identical (`tests/cli/test_run_json_errors.py` ~372/~413).
- CQ9: byte-identical cache keys and equal v8 metadata, pre- versus post-migration,
  for absent range, explicit full range, absent FPS, explicit FPS equal to source FPS,
  absent source path (capture expected keys from the pre-migration code as literal
  fixtures in the same PR, not by calling the new code); retain
  `tests/analysis/test_cache_identity.py`, `test_cache_serialization.py`, cache-mode
  tests (`test_execute_run_cache_modes.py` ~256 no compute), and cache-only tests
  (`test_phase_tasks.py` ~507/537/575); corruption still fails before reservation and
  the second-read failure does not compute.
- CQ4: new regression building the phase plan before selection, replacing
  `ctx.selection` after FramePlan and after Analyze, asserting the frames and labels
  **consumed** by align, render, report, and publish are the latest (no identity
  assertions). Retain the report's orchestration rows (`test_phase_tasks.py` ~107,
  291, 359, 392, 439, 472, 507, 705; `test_phase_output_integration.py`;
  `test_execution_phase_plan.py` warning replacement; `test_active_rect_content.py`).

**Gates.** Full verification; Docker gate at the package head (selection/metrics/cache
reach media-tier observations).

**Compatibility.** No serialized change (cache v8 bytes, error JSON). Internal types
change atomically.

**Rollback.** CQ6, CQ9, CQ4 are separate commits; revert CQ4 alone if needed (CQ9 and
CQ6 do not depend on it).

**Exit criteria.** Replacing the selection with a new value cannot make later phases
consume stale frames; selection metadata and domain are replaced as units; rewording
a diagnostic cannot change recovery; one required-read owner used at both lifecycle
points; one request object from orchestration to metadata; identity derived from
sampling constants.

---

### P8 Applied tonemap facts and render geometry (CQ11, CQ12, CQ22 geometry claim)

**Problems.**
- **CQ11 (confirmed, S2):** `vs/tonemap.py` `apply_tonemap` (~33–56) returns only a
  clip and silently falls back for three causes (plugin missing; runtime unusable or
  `FRAME_COMPARE_DISABLE_LIBPLACEBO`; libplacebo call failure, `tonemap_libplacebo.py`
  ~144–150). `tonemap_fallback.py` (~37–56) always applies its peak-scaled rational
  expression using only source peak, target nits, and gamma lift. Requested
  `TonemapSettings` (mutable, `vs/types.py` ~43) flow as “effective” facts:
  `render/prepare.py` (~92–94) → `PreparedRenderSource.tonemap_settings` →
  `RenderedClipFacts.tonemap_settings` → overlay (`overlay_text.py` ~136–142) →
  `ClipInfo.tonemap_settings` → payload presentation (`payload.py` ~595) and shared
  `ReportRenderingInfo.tonemap_settings` (mixed values raise at
  `phase_post_render.py` ~379–385).
- **CQ12 (maintainability):** `render/geometry.py` `plan_render_geometry` (~157)
  supports `provided|dimension|aspect_ratio|auto` (default `aspect_ratio`) and
  candidate inference; the sole production caller (`render/batch/expansion.py` ~248)
  always passes `provided`, and `ScreenshotBatchRequest.active_picture` is required.
  `docs/current-architecture.md` (~1143–1145) claims direct calls can still infer.

**Layering.** Render and services are independent (O9); the applied record lives in
`vs/types.py` (beside `TonemapSettings`) so render, orchestration, and the report
service can all import it.

**Chosen design (CQ11).**
```python
class TonemapFallbackCause(StrEnum): PLUGIN_UNAVAILABLE; RUNTIME_UNUSABLE; RUNTIME_CALL_FAILED
@dataclass(frozen=True, slots=True)
class ResolvedSourcePeak: nits: int; origin: Literal["configured", "max_cll", "default"]
@dataclass(frozen=True, slots=True)
class LibplaceboTonemap: curve: ToneCurve; settings: TonemapSettings; source_peak: ResolvedSourcePeak
@dataclass(frozen=True, slots=True)
class FallbackTonemap:
    algorithm: Literal["frame_compare_peak_scaled_rational_v1"]
    target_nits: int; gamma_lift: bool; source_peak: ResolvedSourcePeak; cause: TonemapFallbackCause
@dataclass(frozen=True, slots=True)
class AppliedTonemap: requested: TonemapSettings; transform: LibplaceboTonemap | FallbackTonemap
@dataclass(frozen=True, slots=True)
class TonemapResult: clip: vs.VideoNode; applied: AppliedTonemap | None   # None when disabled
```
- `apply_tonemap` returns `TonemapResult`; `apply_libplacebo` reports a failure cause
  instead of bare `None`; one `resolve_source_peak` in `tonemap_conversion` replaces
  the duplicated peak rule (`tonemap_libplacebo.py` ~68–71 and fallback). Freeze
  `TonemapSettings` (existing code uses `replace()`; audit and migrate any mutation).
- The fallback has its own truthful identity
  (`frame_compare_peak_scaled_rational_v1`); it is not labeled `REINHARD`.
- Per-clip flow: `prepare._apply_vs_tonemap_and_labeling` →
  `PreparedRenderSource.tonemap: AppliedTonemap | None` →
  `RenderedClipFacts.tonemap` → `OverlayConfig.tonemap` (diagnostic overlay text e.g.
  `Tonemap: fallback (peak-scaled) → 203 nits`; libplacebo text unchanged) →
  orchestration `ClipInfo.tonemap` → payload per-clip presentation.
- Shared summary: delete `ReportRenderingInfo.tonemap_settings` and the mixed-settings
  `ValueError`; the payload service derives `shared` only when every tonemapped
  clip's applied transform is equal.
- Fallback policy (decision D3a, recommended default): keep the permitted runtime
  fallback, disclose it per clip, and add one `RunWarning("render", …)` naming the
  clips that fell back and the cause class. Preserve fatal configuration/signature
  errors, source-prop precedence, range-expansion restrictions, cancellation
  admission, and native-review preview defaults.
- CLI pre-run preview keeps showing requested settings (a plan). Applied facts appear
  in overlay, report, and the warning.

**Serialized compatibility and identity (decision D3b, recommended default).** Bump
report payload `REPORT_VERSION` (`payload.py` ~29) from `1.2` to `1.3`:
- `clips[].presentation.tonemap`: `{implementation, algorithm, target_nits,
  source_peak_nits, source_peak_origin, effective_controls, fallback_cause} | null`.
- `rendering.tonemap`: `{applied, requested: settings | null, shared: <applied> | null}`.
- `build_report_id` (`payload.py` ~497–523) hashes output-affecting applied facts
  (implementation, algorithm, effective controls, resolved peak); excludes `requested`
  and `fallback_cause` (as `display` is excluded). Two runs with identical output via
  different failure causes share identity.
- Rationale: adding fields to 1.2 still changes `report_id` (the whole `rendering`
  dict is hashed), the contract already established 1.1 → 1.2 as a version change
  without review migration (`current-cli-contract.md` ~1013–1017), and the report
  forbids presenting a changed payload as unchanged.
- Consequences: regenerated reports get new IDs, so browser-local viewer/review/lens
  state keyed by report ID starts fresh and exported review JSON from 1.2 is rejected
  by 1.3 reports; existing HTML reports remain self-contained and viewable.
- Consumers to migrate together: `review_state.js` (~182 version check, ~135–141 id
  and version match), `viewer_format.js` (`formatPresentation` ~121–134,
  `formatTonemapSummary` ~176–185), `renderer.py` (`_render_tonemap_summary/_details`
  ~266–360), `report_viewer_contracts.py`, Node harness fixtures,
  `tests/browser/test_report_browser_smoke.py`, `tests/e2e/test_media_tonemap.py`
  (~36 reads `report["rendering"]["tonemap"]["settings"]`), rename
  `test_report_payload_v12.py`.

**Chosen design (CQ12).** Render geometry consumes resolved facts only:
- `SourceGeometry` takes a required active rectangle plus canonical
  `ActivePictureProvenance`; `RenderGeometryPlan` carries canonical provenance.
- Delete `ActiveRectDetectionMode`, `active_rect_detection` and its validation
  (`_validate_options` ~240–243), `_resolve_active_rects`,
  `_dimension_derived_active_rects`, `_mod_safe_contained_vertical_rect`,
  `_aspect_ratio_derived_active_rects`, `_select_aspect_ratio_candidate`,
  `_aspect_ratio_candidates`, `_aspect_candidate_support_count`, `_rect_ratio`,
  `_ratio_matches`, `_ratio_relative_delta`, `_AspectCandidate`, the three
  `ASPECT_RATIO_*` constants, `ActiveRectSource`/`ProvidedActiveRectSource`, both
  provenance converters (~34–71); replace `_is_safe_active_rect`'s silent full-frame
  fallback with a `ValueError` (the request contract already guarantees validity).
  `source_overlay_origin` has no production reader: delete it unless a retained test
  proves an obligation.
- `expansion.py`: simplify `_geometry_facts`; remove the dead dimension-widening
  branch (~228–233; `validate_batch_requests` already requires positive dimensions).
- `phase_render.py` (~16, ~239): replace the render-owned converter with an
  orchestration-owned `ClipActiveRectSource → ActivePictureProvenance` mapping in
  `orchestration/active_rect.py`; keep the `ClipActiveRectSource` spelling (feeds
  `active_rect_identity` and cache identity).
- Render keeps projection, mod-safe crop, scale/canvas choice, padding, overlay
  origins; orchestration keeps the single live inference authority (O7 cache identity).

**Ordered steps.** (1) CQ11 types and dispatch; (2) prepare/overlay/clip facts;
(3) payload 1.3, identity, Python renderer, JS consumers; (4) fallback warning;
(5) CQ12 geometry deletion and orchestration mapping; (6) docs: CLI contract §
Report And Overlay Metadata Contract (~1002–1059: version 1.3, per-clip applied
disclosure, identity facts, fallback disclosure), `docs/current-architecture.md`
(~967 payload references; ~1136–1154 geometry ownership, removing the stale
direct-call inference claim — the CQ22 geometry item), and user report/HDR guides
that describe the tonemap disclosure.

**Tests.**
- Retain `tests/vs/test_tonemap_apply.py` (fallback when plugin missing ~51; ~181),
  `test_tonemap_extracted_modules.py` (~97, ~114, ~280), `tests/render/test_tonemap_wiring.py`,
  overlay composer, actual-preparation expansion, report-output, and report-identity
  tests (`tests/services/test_report.py` ~284–427), updating expectations from
  requested to applied facts.
- Add: dispatch returns each fallback cause; two clips with identical requested
  settings, one libplacebo and one fallback → independent per-clip disclosure,
  `shared` null, one render warning, `report_id` differs from the all-libplacebo case
  but not between fallback causes; JS review state rejects 1.2 documents in a 1.3
  report; payload 1.3 shape tests.
- CQ12 mapping before retiring render inference tests: axis cases
  (`test_geometry.py` ~240–341) and invalid-rect fallback (~135, ~148) →
  `tests/orchestration/test_active_rect.py::test_dimension_detection[...]`; ratio
  cases (~595–769) → `test_aspect_ratio_detection[...]` and
  `test_post_refinement_ratio_*`; check the three-source ultrawide outlier against
  the existing `…-extreme` case and add an orchestration case if not equivalent;
  rewrite `fight_club_shape` and `smallest_active_downscales_aspect_crop` with
  provided rectangles to keep scale-policy proof; move converter tests
  (`test_expansion_geometry.py` ~42–67) to orchestration. Retain crop/scale/pad,
  odd/mod-safe bounds, native preservation, backend application, and overlay
  placement suites (`test_geometry.py`, `test_expansion_geometry.py`,
  `test_ffmpeg_frame.py`, `test_encoders.py`).

**Gates.** Full verification; Docker gate including `tests/e2e/test_media_tonemap.py`
and `test_media_render.py` (graph unchanged for libplacebo; facts and fallback overlay
text change). If implementation changes any fallback graph, frame props, or range
handling, real-media pixel proof on both libplacebo and
`FRAME_COMPARE_DISABLE_LIBPLACEBO=1` paths becomes required. Viewer JS changes: Node
suites plus real-browser smoke (acceptance requirement). Windows portable runtime
smoke invokes the application tonemap path; a hosted Windows verify run at the package
SHA is an acceptance requirement because `vs/` changed.

**Compatibility.** Payload 1.3 and new report IDs per D3b; overlay text changes only in
diagnostic mode on fallback; no cache-format change.

**Rollback.** Revert P8; already-generated 1.3 reports remain self-contained.

**Exit criteria.** No artifact identifies a requested curve as applied when a fallback
ran; per-clip applied facts are authoritative, the shared summary is derived; identity
reflects applied output-affecting facts; render geometry has no inference; one live
inference authority remains in orchestration.

---

### P9 Structured render pipeline (CQ3)

**Problem.** Phase rendering builds parallel `source_frames`/`comparison_frames`/
`selection_labels` lists (`phase_render.py` ~57–81) and `expected_frames`; expansion
validates lengths (~64–73) and returns flat requests plus label→range and
label→clip-facts maps (~98); the orchestrator reconstructs work units from ranges
(~61–81) and splits results back (~403–433); `RenderedBatchResult.__post_init__`
(`render/types.py` ~102–113), `RenderArtifacts.__post_init__`
(`execution_types.py` ~42–53), `phase_render.py` (~95–98), and report composition
(`phase_post_render.py` ~326–346) revalidate. The production scheduler already treats
each clip as an indivisible unit.

**Chosen design (types in `render/types.py`; render cannot import orchestration or
services, O9).**
```python
@dataclass(frozen=True, slots=True)
class SelectedScreenshot: comparison_frame: int; source_frame: int; selection_label: str | None
# ScreenshotBatchRequest.frames: tuple[SelectedScreenshot, ...]  (replaces three lists)
@dataclass(frozen=True, slots=True)
class PreparedClipRender:  # one indivisible scheduling unit
    label: str; clip_facts: RenderedClipFacts
    frames: tuple[SelectedScreenshot, ...]; requests: tuple[RenderRequest, ...]
    # __post_init__: equal lengths; request.frame_number == frame.source_frame
@dataclass(frozen=True, slots=True)
class RenderedScreenshot:
    selection: SelectedScreenshot; result: RenderedFrameResult
    # __post_init__: result.facts.source_frame == selection.source_frame (backend trust boundary;
    # the FFmpeg batch path does not check this today)
@dataclass(frozen=True, slots=True)
class RenderedClip: label: str; clip_facts: RenderedClipFacts; screenshots: tuple[RenderedScreenshot, ...]
```
- `expand_batch_render_requests(...) -> tuple[PreparedClipRender, ...]`; global output
  path generation and collision refusal stay first, before any native preparation.
- `render_clip_jobs(jobs, *, parallelism, reporter) -> tuple[RenderedClip, ...]`;
  `render_screenshots_from_batch_detailed` returns `tuple[RenderedClip, ...]`.
- Orchestration `RenderArtifacts(clips: tuple[RenderedClip, ...], screenshot_dir,
  warnings)` with no `__post_init__`. Report composition zips context clips with
  rendered clips (`strict=True`) and checks labels, using P7's selection-row helper
  for frame details. Publish derives `{label: [paths]}` at its boundary
  (`services/slowpics_upload_plan.build_slowpics_upload_plan`); services receive
  plain service inputs, never render types. `RenderedClipFacts` carries P8's
  `tonemap` facts unchanged.
- **Ungrouped `render_batch_detailed` mode is deleted (decided).** It has no
  production, plugin, or tool caller (entry points are the CLI and the VSView panel;
  `render/__init__` and `render/batch/__init__` export nothing; production always
  passes `work_unit_ranges`). Its distinct production-relevant obligations are ported
  to job form: lowest-index failure precedence, FFmpeg grouping within a unit
  (`_ffmpeg_batch_end`, `is_ffmpeg_batch_compatible`), partial progress and admission,
  and SIGINT admission. The ordered-prefix progress (`_record_ready_progress`,
  `_render_description`, “Rendering” label) exists only on that path; production uses
  count-only `advance` under a lock, so deleting it removes no product behavior.
- Rejected: consolidating only the result containers first and leaving request
  lists/ranges (the report's smaller slice; keeps the reconstruction protocol);
  cached mutable compatibility dictionaries; a generalized async scheduler.

**Preserved invariants (O7, O8).** Lowest job index failure wins (`orchestrator.py`
~269–277); per-clip sequential rendering within one worker (~123–132) and FFmpeg
batching only for fully compatible units (~109–111); cross-clip overlap via
`ThreadPoolExecutor(max_workers=parallelism)` with parallelism 2; batch-owned `Event`,
50 ms poll, per-frame `stop.is_set()`, FFmpeg `abort=stop.is_set`, cancellation of
unstarted futures, ignored sibling `CancelledError`, final `raise_if_cancelling`;
expansion's per-clip checks before/after preparation; “Screenshots” phase with
request-count total, count-only advance, FFmpeg units advance by length,
`complete_phase(FAILED)` on exceptions; one result per request and no empty slot,
now per job; deterministic source/result/progress order; physical screenshot naming
(`naming.generate_screenshot_path`, `"{comparison_frame} - {stem}.png"` with hashed
long-path suffix) unchanged.

**Ordered steps.** (1) Add types; (2) expansion returns jobs; (3) scheduler consumes
jobs and returns rendered clips; port ungrouped-mode tests; (4) phase render builds
`SelectedScreenshot`s from P7's selection rows; (5) `RenderArtifacts` and report/
publish boundaries; (6) delete superseded code; (7) docs: architecture § render
scheduling (~1149–1154) and hotspots disposition.

**Deletions.** `RenderedBatchResult` and validator (+ `tests/render/test_types.py`
~77–96), `render_batch_results_by_label` (`expansion.py` ~201–211), the range/
clip-facts tuple return and length check, `work_unit_ranges` and range validation
(`orchestrator.py` ~61–81, ~321, ~330, ~338–348, ~416–428), the ungrouped scheduling
mode, `RenderArtifacts.__post_init__`, `expected_frames` and the identity loop in
`phase_render.py` (~58, ~64, ~95–98; the picture-type warning stays), and the
count/mapping re-checks in `phase_post_render.py` (~328–344). Keep `ReportData`,
`_validate_report_cardinality`, and slow.pics count checks (separate input contracts).

**Caller migration (tests).** `tests/orchestration/phase_task_helpers.py`,
`test_phase_post_render_outputs.py`, `test_phase_output_integration.py`,
`test_phase_tasks_outputs.py`, `test_execute_run_*`, `test_overlay_frame_number.py`,
`test_ffmpeg_overlay_application.py`, `test_phase_alignment_contract.py`,
`test_execution_phase_plan.py`, `tests/services/test_slowpics_upload_plan.py`,
`tests/render/test_orchestrator.py` (~10 ungrouped tests ported),
`tests/render/test_orchestrator_batch_screenshots.py`,
`tests/integration/test_render_orchestrator.py`, `tests/integration/test_render_pipeline.py`
(~98, ~110), `tests/orchestration/test_execute_run_lifecycle.py` (~777).

**Tests.** Retain every “Rendering and orchestration” row in the report (including
`test_real_sigint_stops_frame_admission_within_150ms`,
`test_ffmpeg_batch_stop_reaps_child_without_publishing_partial_results`, and unequal
clip-count fact association). Add: FFmpeg-batch fact identity mismatch rejected at
`RenderedScreenshot`; job-index failure precedence; unresolved comparison membership
remains in render/report/slow.pics (`test_unresolved_comparison_remains_in_render_report_and_slowpics_membership`).

**Gates.** Full verification; Docker gate (render scheduling, native/FFmpeg execution).
Windows hosted verify at the package SHA (render path inside the portable runtime
smoke) is an acceptance requirement.

**Compatibility.** No serialized change (payload, run record, screenshot names).
Internal APIs change atomically.

**Rollback.** Revert P9 as a unit.

**Exit criteria.** Clip/frame structure carried end to end; no label-range plumbing or
result-by-label reconstruction; one cardinality/identity check at the backend trust
boundary; ordering, failure, cancellation, and native-fact contracts proved by
retained tests and the Docker gate.

---

### P10 Collection-policy warning propagation (CQ13)

**Problem.** `orchestration/slowpics_metadata.py` (~68–79) produces a typed
`RunWarning("slow.pics", …)` on an explicit/resolved TMDB mismatch;
`phase_post_render.py` (~177–178) logs it; `PublishPhaseOutput`
(`execution_types.py` ~107–112) has no warnings field; `apply_phase_output`
(~63–71) adds only post-upload action warnings; result, summary
(`cli/output.py` ~489–503, de-duplicated), and record (`run_result_record.py`
~272/~289, `warning_count = len(warnings)`) lose it.

**Design.** Add `warnings: tuple[RunWarning, ...] = ()` to `PublishPhaseOutput` holding
only collection-policy warnings; `run_publish_phase` returns
`warnings=tuple(collection_resolution.warnings)` and keeps the log line;
`apply_phase_output` extends `state.warnings` once. Post-action warnings stay on their
existing path (no double counting). Accepted limitation: if `publish_to_slowpics`
raises, the policy warning remains log-only and the warn-only failure warning is
recorded. Rejected: publishing state-machine rewrite; adding warnings to successful
JSON (explicit contract: omitted).

**Tests.** New joined `execute_run` test (mocked transport, unexpected HTTP rejected):
exactly one mismatch warning in `result.warnings`; record `warning_count == 1` and
status `completed_with_warnings`; terminal summary shows one warning; uploaded URL
preserved; explicit association and title isolation retained; successful JSON output
unchanged. Retain `test_slowpics_metadata.py` (~148), `test_phase_post_render_outputs.py`
(~522), `test_execution_phase_plan.py` (~290–311), `test_execute_run_lifecycle.py`
(~287).

**Gates.** Full verification. No Docker (no media observation changes).

**Compatibility.** Runs with the mismatch now record `completed_with_warnings`
(existing status, intended outcome); JSON unchanged.

**Rollback.** Revert P10.

**Exit criteria.** Producer-owned warning appears once in result, summary, and record.

---

### P11 U4 media recipe ownership (CQ21b)

**Problem.** `tests/integration/test_alignment_u4_acceptance.py` `_write_media_set`
(~444–577) eagerly builds 6 references and 31 comparisons; the cache key
(~588–589) hashes the whole test module plus `ffmpeg -version`, so assertion-only
edits invalidate all media, and a focused selection still builds the full matrix
cold. Lock `.verifier.lock` (~592), temp-dir rename publication (~595–597), pruning
(~598–600), symlinks (~601–602), `xdist_group("alignment-u4")` (~57), lock-overlap test
(~606–651).

**Design.**
- `tests/integration/alignment_u4_media_test_support.py` (no VapourSynth import):
  constants, graph builders, writers (~74–441), `RECIPES: Mapping[str,
  MediaRecipe(writer, requires)]`, `PAIRS`, and
  `open_u4_media(tmp_root, *, cache_root, full_matrix, ffmpeg_version=…, recipes=RECIPES)`
  yielding a lazy `U4MediaStore` (`pair(name)`, `path(recipe)`, `materialize_all()`,
  `stats`). Absorbs pair selection in `_align_pair` (~659–663), `_phase_context`
  (~776–778), `_configured_prep_alignment` (~1105).
- Key: `sha256(b"u4-media-v1\0" + support-module source + b"\0" + ffmpeg -version)`.
  Recipe parameters are declared data inside the module; per-recipe digests are not
  added unless measurements show frequent recipe edits.
- Demand generation under the session lock: generate a recipe on first access after
  its `requires` (`retimed-25` → `reference`; NTSC variants → NTSC reference;
  `retimed-insert` stages its own insert); publish each file by temp file +
  `os.replace` inside the key directory; file existence means complete; on acquire
  prune sibling keys, `.tmp-*` directories, and dot-prefixed temp files; symlink each
  materialized file into the session root (indexes stay outside the cache). Cache
  disabled → lazy generation in tmp.
- Full matrix: `FRAME_COMPARE_U4_MEDIA_FULL=1` calls `materialize_all()` up front;
  `tools/verify_docker_integration.sh` sets it on the default (complete) path so the
  full gate still builds every recipe. Generator directory name stays
  `test_alignment_u4_acceptance` so the first run prunes the old key.
- Lock-overlap test moves to `tests/integration/test_alignment_u4_media_cache.py` with
  injected fake version reader and recipes (runs without VapourSynth, no xdist group).
  The acceptance module keeps its xdist group.

**Tests.** Key stable under test-module edits and changed by support-source edits;
demand generation builds only requested recipes plus prerequisites; full-matrix
completeness; pruning isolation; no partial file after a writer exception; lock overlap.

**Measurements (record before claiming a speedup)** in
`tests/integration/NOTES-u4-media-preparation.md` (style of
`NOTES-u4-video-check-cost.md`), via `U4MediaStore.stats` and a
`pytest_terminal_summary` hook plus `--durations=0`, in the Docker runtime:

| Run | Expected files created |
| --- | --- |
| Baseline cold, focused `-k replacement-4` | 37 |
| New cold, focused | 2 (record actual) |
| Warm after assertion-only edit (baseline / new) | 37 / 0 |
| After a real recipe edit, focused / full | 2 / 37 |
| Cold full gate (duration comparable to baseline) | 37 |

**Docs.** Runbook (~317–325) and `CONTRIBUTING.md` (~159–164): key = exact U4 recipe
module source + complete `ffmpeg -version`; assertion-only edits keep the cache;
per-file atomic replace; demand generation; `FRAME_COMPARE_U4_MEDIA_FULL` for the
complete gate.

**Gates.** Focused pytest for the cache tests; Docker full gate (U4 runs only there).
Never overlap verifier runs in one checkout.

**Compatibility/rollback.** Test infrastructure only; revert P11 (old key directory is
pruned either way).

**Exit criteria.** Focused U4 runs generate only needed media; assertion-only edits keep
the cache; full gate still generates and runs the complete matrix; measurements
recorded.

## 8. Verification matrix

| Package | Static / Python logic | Full native suite | Node harness | Real browser | Docker media gate | Windows PowerShell / portable | Visible Qt |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | docs build, CLI-doc test | — | — | — | — | — | — |
| P1 | ruff/pyright; Linux skips inspected | — | — | — | — | **Required** (PS7 builder/installer fixtures; runbook steps 3–4; hosted verify) | — |
| P2 | ruff/pyright; Python vectors | — | — | — | — | **Required** (PS5.1 + PS7 updater E2E; runbook steps 5–6; signing or documented-only) | — |
| P3 | pyright/ruff for bridge | — | **Required** | **Required** | — | — | — |
| P4 | Logic | **Required** | — | — | — | — | — |
| P5 | Logic | **Required** | — | — | **Required** (regression) | **Required** (shim doctor selection) | — |
| P6 | Logic | **Required** | — | — | **Required** (U4 phase/cache matrix) | — | — |
| P7 | Logic, lint-imports | **Required** | — | — | **Required** | — | — |
| P8 | Logic, lint-imports | **Required** | **Required** (payload consumers) | **Required** | **Required** (+ pixel proof if graph changes) | **Required** (hosted verify; `vs/` changed) | — |
| P9 | Logic, lint-imports | **Required** | — | — | **Required** | **Required** (hosted verify; render path) | — |
| P10 | Logic | **Required** | — | — | — | — | — |
| P11 | ruff/pyright | focused cache tests | — | — | **Required** + measurements | — | — |

No package changes VSView plugin discovery, launch, Qt callbacks, or generated native
sessions, so no Linux GUI verifier or visible-Qt acceptance is required; P4's VSView
change is pure result validation. No package changes whole-track memory bounds or
streaming cleanup, so the separate alignment resource proof is not required.

Commands (runbook authority):

```sh
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q -n4 --dist loadgroup
uv run --no-sync lint-imports --config importlinter.ini
uv run --no-sync pytest -q tests/services/test_report_viewer_state.py tests/services/test_report_viewer_viewport.py tests/services/test_report_grid_view_state.py tests/services/test_report_lens_state.py
REPORT_BROWSER=<chrome> uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py
bash tools/verify_docker_integration.sh
```

Hosted evidence counts only with the recorded SHA and job result; an absent or skipped
job is not a pass.

## 9. Compatibility matrix

| Surface | Package | Change | Compatibility handling | Temporary mechanism / removal condition |
| --- | --- | --- | --- | --- |
| Report payload | P8 | 1.2 → 1.3; per-clip applied tonemap | Old HTML reports unaffected; no review migration (existing precedent) | none |
| Report identity | P8 | Hash applied output-affecting tonemap facts | New IDs for regenerated reports; browser-local state starts fresh | none |
| Overlay text (diagnostic) | P8 | Fallback disclosed truthfully | Baked pixels change only for fallback + diagnostic overlay | none |
| Run warnings / record status | P8, P10 | Fallback warning; policy warning recorded | Records may become `completed_with_warnings` (existing status); success JSON unchanged | none |
| Metric cache v8 | P4, P7 | Decode recovery; request intact | Bytes and keys byte-identical (tested) | none |
| Alignment reuse cache v2 | P6 | Candidate preparation | Bytes unchanged (tested) | none |
| VSView result contract v1 | P4, P6 | Decode recovery; services refactor | Unchanged wire format | none |
| Run records / history | P4 | Recursion isolation | Unchanged format | none |
| Viewer storage | P3 | Derived offset | Same key/schema; no neutral writes on visit | none |
| CLI `doctor` | P5 | `--root/--config`; no upward search | New options; JSON unchanged | none |
| CLI preview | P5 | Values from effective config | `input` row shows resolved path | none |
| Config validation | P4 | `inf` timeouts and parser-limit TOML rejected | Typed config errors | none |
| `RunRequest` / internal APIs | P5–P9 | Reshaped | Internal; atomic caller migration | none |
| Windows builder | P1 | Refuses occupied output | Maintainers delete disposable output | none |
| Windows source installer | P1 | Versioned bundle folder; user-data policy | Existing pointer remains valid | none |
| Windows updater | P2 | Grammar; transaction; `backup.json` | Manifest fields unchanged; stable `min` stays numeric for old updaters; RC installs need one full reinstall | none |
| U4 test media cache | P11 | New key | Old key pruned automatically | none |

No package introduces a temporary compatibility layer; every internal migration
replaces callers atomically. If an implementer finds an unlisted real consumer of a
removed internal API, they must stop and add it to this plan with a removal condition
before adding any shim.

## 10. Decisions

### Decisions made by this plan (with the rejected alternative recorded in each package)

CQ1 derived offset + `selectPair` (P3); CQ2 record consolidation without variant types,
candidate in `alignment_reuse_cache.py` (P6); CQ3 job/clip types and deletion of the
ungrouped scheduler mode (P9); CQ4 execution-time reads + `SelectionSnapshot` +
`PreparedSelectionDomain` (P7); CQ5 delete the duplicate predicate (P6); CQ6 enum kind
not serialized (P7); CQ8 `AcquiredRunConfig` in `orchestration/run_inputs.py`,
workspace recomputed per use, `prepare_preflight` deleted (P5); CQ9 signatures and
`acquire_required_metrics` in `cache_io.py` (P7); CQ10 constant helper, per-owner
policy, typed config/preset errors (P4); CQ12 deletion list (P8); CQ17 transaction and
`backup.json` with strict legacy policy (P2); CQ19 four fields only (P4); CQ20/CQ21
fixture, runner, support-module boundaries (P3, P6, P11, P1/P2).

### Decisions that need maintainer input (independent work proceeds with the recommended default)

| ID | Question | Options and consequences | Recommended default |
| --- | --- | --- | --- |
| **D1** (CQ15, P1) | When a source reinstall finds user data (`config\`, `comparison_videos\`, `generated\`) in the previous active bundle and no `-UserData` choice was given, what happens? | **Move** (rename the three folders into the new bundle, all-or-nothing, then activate): keeps the documented “rerun install.cmd” workflow; data follows the AppData state config's bundle-relative paths. **Refuse to activate** (build, verify, print instructions, exit non-zero): no automatic data handling, but every rerun needs a flag. **Leave**: activates while data stays invisible in the old folder. | **Move**, with `-UserData Leave` as opt-out. The builder's refusal of occupied output is independent of D1 and ships regardless. |
| **D2** (CQ16, P2) | Stable↔RC admission semantics | Allow RC→RC, RC→stable, stable→RC within one `major.minor` line (stable `min` admits its RCs) vs. forbid stable→RC code updates (RC requires full bundle) | Allow within the line, as specified in P2 |
| **D3a** (CQ11, P8) | Unavailable requested tonemap: fail or disclosed fallback? | Keep fallback disclosed per clip + one run warning (current tested behavior, now truthful) vs. a new `color.tonemap_fallback = "allow" \| "refuse"` setting with a typed `FC-` error on any cause (schema, wizard, docs, doctor implications) | Keep disclosed fallback + warning; do not add a setting now |
| **D3b** (CQ11, P8) | Payload/identity compatibility | Bump to 1.3 with applied-fact identity (regenerated reports get new IDs; browser state starts fresh) vs. additive 1.2 fields (still changes IDs; misrepresents the contract) | Bump to 1.3 |
| **D4** (CQ18, P5) | Public `doctor` CLI change | Add `--root/--config`, shim injects for doctor, drop upward search (consistent with run) vs. keep upward search when `--root` is absent (two root policies) | Add options; match run's selection exactly |

If D1 is answered “refuse”, P1 replaces the Move step with the refusal message; all
other P1 work is unchanged. If D3a selects strict mode, add the config field, typed
error, and tests to P8 before its payload work merges. If D4 is rejected, CQ18 cannot
be completed without a second fallback owner; record that explicitly rather than
shipping a copy of the shim rule.

## 11. Excluded scope

- **CQ7 (image request lifetime) and CQ14 (resampling ownership)** remain in
  [the investigation report](../reviews/2026-10-15-code-quality-investigations.md).
  They are neither accepted refactor scope nor prerequisites. This plan adds no shared
  image loader, request-slot owner, or resampling/writer change. P3 and P8/P9 keep
  the boundaries those investigations reference (main/Grid/Lens loaders unchanged;
  `RenderedClipFacts` can later carry resampler facts if CQ14 decides so).
- Observations made while planning that are **not promoted** (each needs its own
  evidence before scheduling): `AnalysisConfig.min_window_seconds` accepts `inf`
  (not an operation timeout; consequence not traced); the tonemap fallback does not
  set `_Tonemapped`/`_FrameCompareExpandRange` props that `encoders.py` (~83–86)
  checks, so PNG range handling may differ from the libplacebo path (unmeasured pixel
  concern; P8 must describe the fallback truthfully but does not change its graph);
  mixed alignment publications refresh `accepted_at` for reused entries (existing
  behavior, asserted not changed); other test modules importing from collected test
  modules (`test_alignment_vsview.py` ~45, `test_alignment_workflow_vsview.py` ~36,
  `test_alignment_video_wiring.py` ~18) outside CQ21c's named seam.
- Workflow/skill maintenance, CI redesign, dependency upgrades, signing-key operations,
  deployment, and release publication.

## 12. Risks and failure behavior (cross-package)

- **Windows filesystem semantics (P1, P2):** rename atomicity, locked files from
  running shims, and antivirus interference are only observable on Windows; designs
  keep the old tree until commit and report recovery material on failure.
- **Silent identity drift (P6, P7, P8):** guarded by byte-identical cache key/metadata
  fixtures and existing identity tests captured from pre-migration code.
- **Authority regressions (P6):** guarded by the retained authority table and new
  on-disk publication observations; any test that weakens O3/O4 is a blocker.
- **Cancellation regressions (P9):** guarded by real-SIGINT, FFmpeg reaping, and
  partial-progress tests plus the Docker gate.
- **Scope creep:** any newly discovered issue gets its own caller trace and evidence
  before joining this plan.

## 13. Integrated completion checklist

The supported scope is complete only when every item is checked with recorded evidence
(SHA, command, result) or explicitly recorded as an open acceptance requirement with
the reason it could not be obtained.

- [ ] P0: three public passages corrected; strict docs build.
- [ ] P1: no code removes an existing output root; failure leaves state byte-identical;
      D1 policy implemented; Windows PS7 fixtures and hosted verify recorded.
- [ ] P2: one version grammar owner across extraction/range/generator/bundle info/smoke;
      exact target check; `Restore-FromBackup` deleted; transaction used by apply and
      rollback; PS5.1 and PS7 updater E2E and signed/documented-only status recorded.
- [ ] P3: `selectPair` is the only pair-changing path; Appendix A and `0:0` variants fixed
      in Node and real browser; fixtures own documents; JS asserts each obligation
      once; focused scenario run and deliberate-failure proof recorded.
- [ ] P4: owner-specific recovery for every reader in the table, including config and
      presets; four timeouts finite.
- [ ] P5: one config acquisition per run; preview override policy and
      `TonemapCliOverrides` deleted; benchmark migrated; doctor and shim selection
      aligned (D4); Windows shim observation recorded.
- [ ] P6: V6 gates evaluated once; scenario support separated; `ComparisonResolution`
      map with pure confirmation; candidate-based publication; on-disk proofs A–D;
      Docker gate.
- [ ] P7: typed failure kinds; intact metric request and shared required read with both
      lifecycle reads kept; execution-time selection reads; snapshot and domain values;
      byte-identical key fixtures; Docker gate.
- [ ] P8: per-clip applied tonemap facts in overlay/report/warning; payload 1.3 and
      identity per D3b; render inference deleted with mapped proof; stale geometry
      claim removed; Docker, browser, and Windows hosted evidence.
- [ ] P9: structured jobs/results end to end; range plumbing and duplicate validators
      deleted; ungrouped mode removed with obligations ported; Docker and Windows
      hosted evidence.
- [ ] P10: one policy warning in result, summary, and record.
- [ ] P11: recipe module, key, demand/full-matrix generation; measurements recorded.
- [ ] Integrated head: full native suite, `lint-imports`, Docker gate, browser smoke,
      and Windows hosted verify at the final SHA (reuse package evidence only where the
      relevant code is unchanged).
- [ ] `docs/current-architecture.md` and `docs/current-cli-contract.md` reflect every
      ownership/contract change listed in packages P5–P9; runbook, README.txt,
      windows-portable guide, and CONTRIBUTING updated per P1, P2, P11.
- [ ] Final review against the report: no supported finding or CQ21 subpart open, no
      implicit caller migration or deletion, no temporary compatibility layer, CQ7/CQ14
      untouched, no runtime acceptance claimed without evidence.
- [ ] This plan's marker changed to `Status: Historical` with an outcome line.
