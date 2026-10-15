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
| Appendix C decoder/timeout probe | Reproduced on Python 3.13.16 (int limit 4300): VSView result, metrics, and TMDB leak `RecursionError` (deep) and `ValueError` (long integer); history leaks `RecursionError` but already isolates the long integer as an unavailable entry; all four timeouts accept `inf` | Actual decoders/models |
| **New** config-loader probe (real temporary files) | `load_config` and `load_raw_config` raise raw `RecursionError` (deep inline tables) and `ValueError` (5,000-digit int); ordinary malformed TOML raises typed `ConfigParseError` | Confirms a CQ10 sibling at the user-config owner |
| Appendix D fixture probe | Reproduced `{"firstDocumentOwnsFocus":false,"secondDocumentOwnsForeignFocus":true}` | Test-support defect |
| Source read: `build_portable.ps1` `Main` | `Remove-Item -Recurse -Force -LiteralPath $OutDir` precedes `Get-Manifest` | CQ15 mechanism; no Windows execution |
| Source read: `build_update.ps1` payload | Code-only update ZIPs contain only `app/src/frame_compare`; the installed updater lives in `%LOCALAPPDATA%\Programs\FrameCompare\bin` and is replaced only by a bundle `install.ps1` | Determines how CQ16/CQ17 fixes reach users |
| Source read: updater `Invoke-SmokeCheck` | Target verification uses `-match [regex]::Escape($ExpectedVersion)`, a substring test (`0.8.0` matches `0.8.0rc1`; `1.0.1` matches `1.0.10`) | Additional exact-target defect inside CQ16 scope |
| Browser smoke with `REPORT_BROWSER=/opt/pw-browsers/chromium-1194/chrome-linux/chrome` | 18 failed, 3 passed: harness reports `Chrome never became ready` | **Capability gap** in this container (browser launch), not a product signal |
| `uv run --no-sync zensical build --clean --strict` (docs group installed) | First run aborted: every warning came from the two review reports' host-absolute `.md` links, none from this plan. After converting those links (P0 step 0, done during planning) the strict build passed with no warnings | Docs gate usable for P0 and later packages |
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
   validates first, atomically reserves a new output folder (refusing occupied or
   unsafe destinations), and on failure removes only what it reserved; the source
   installer activates a freshly built, verified bundle only after success and
   handles user data by an explicit, reversible policy (P1).
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

Every supported finding and CQ21 subpart maps to exactly one owning package. CQ22 is
split into distinct sub-items with distinct owners; its last row is the same-pass
documentation each behavior-changing package owns for its own sections. CQ21d is
split by owner: P1 replaces spelling checks for the builder/installer, P2 for the
updater.

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
| CQ15 | Confirmed defect (S1) | P1 | Builder validation + atomic reservation + occupied/unsafe refusal + reservation-scoped cleanup; source installer fresh target + post-verification activation + explicit, reversible user-data policy |
| CQ16 | Confirmed defect (S2) | P2 | Shared stable/RC grammar/ordering; range semantics; exact target verification |
| CQ17 | Inferred risk (S2) | P2 | Journaled `Invoke-SourceTreeReplacement` and interrupted-state repair for apply and rollback; `backup.json` completeness record beside `compatibility.json`; `Restore-FromBackup` deleted |
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
| CQ22 ownership/payload/disclosure docs | Same-pass documentation | P1, P4, P5, P6, P7, P8, P9 | Architecture/CLI-contract sections updated in the package that changes them |

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
| P6 | Alignment decision and resolution ownership | CQ5, CQ21c, CQ2 | Medium | none (soft: P4 first for `alignment_reuse_cache.py`) |
| P7 | Selection domain, failure kinds, metric acquisition | CQ6, CQ9, CQ4 | Medium | P5 and P10 merged; P4 merged (soft: `cache_io.py`) |
| P8 | Applied tonemap facts and render geometry | CQ11, CQ12 | High (S2 defect) | none (coordinate `render/prepare.py` with P5) |
| P9 | Structured render pipeline | CQ3 | Medium | P7, P8, P10 merged |
| P10 | Collection-policy warning propagation | CQ13 | Low risk, land early | none |
| P11 | U4 media recipe ownership | CQ21b | Medium | none (coordinate U4 module edits with P7) |

### 6.1 Shared files and conflict rules

| Shared file or resource | Packages | Rule |
| --- | --- | --- |
| `tools/windows_portable/build_portable.ps1`, `version_utils.ps1` | P1 (`Main`, output reservation), P2 (grammar through `version_utils.ps1`, which the builder dot-sources) | P1 merges first; P2 rebases |
| `tools/windows_portable/verify_extracted_bundle.ps1`, `write_bundle_inventory.py`, `tools/windows_portable/README.txt`, runbook Windows section | P1 (`path_safety.ps1` extraction, provenance, source-build docs), P2 (version helper entries, provenance, update/rollback docs) | P1 first; P2 rebases |
| `tests/windows_portable/test_windows_portable_build_scripts.py` | P1, P2, P8 (asserts on `runtime_smoke.py` text ~364–501, ~748) | P1 before P2; P8 (Wave A) and P1/P2 in either order, whichever lands later rebases |
| `tools/windows_portable/runtime_smoke.py`, `tools/docker_runtime_smoke.py` | P8 (`apply_tonemap` result type) | P8 only; note the build-scripts test dependency above |
| `src/frame_compare/orchestration/preparation.py`, `coordinator.py`, `tools/alignment_benchmark.py` | P5 (acquisition), P7 (domain, required read) | P5 first |
| `orchestration/execution_types.py`, `phase_output_application.py`, `phase_post_render.py` | P10, P7, P9 (and P8 for `phase_post_render.py` tonemap summary) | P10 first (smallest); then P7/P8 in either order; P9 last |
| `render/prepare.py` | P5 (delete `cli_overrides` branch), P8 (applied facts) | Either order; second rebases a small hunk |
| `render/batch/expansion.py`, `render/types.py` (`RenderedClipFacts`) | P8 (geometry, applied tonemap facts), P9 (jobs, result types) | P8 first |
| `orchestration/phase_render.py` | P7 (selection reads, selection-row helper), P8 (active-rect provenance mapping ~16/~239), P9 (rewrite to jobs) | P7 and P8 in either order; P9 last |
| `orchestration/active_rect.py` | P8 (new `ClipActiveRectSource → ActivePictureProvenance` mapping); P7 only calls the existing `metric_cache_request_for_clip` through `metric_request_for_domain` and should not need to edit it | P8 owns edits |
| `tests/orchestration/test_preparation_cache.py`, `test_preparation_active_rect.py` | P5 (`prepare_preflight` callers), P7 (domain fields) | P5 first |
| `analysis/cache_io.py` | P4 (decode), P7 (`acquire_required_metrics`) | P4 first (small) |
| `services/alignment_reuse_cache.py`, `services/alignment_manual_overrides.py` | P4 (decode catches), P6 (candidate; reuse-cache refactor) | P4 first (small); P6 rebases |
| `tests/orchestration/test_phase_tasks.py`, `tests/orchestration/test_execute_run_cache_modes.py` | P4 (cache-only corruption cases), P7 (CQ4/6/9) | P4 first; P7 rebases |
| `tests/orchestration/test_phase_alignment_contract.py` | P6 (`ComparisonResolution` fixture), P7 (`ExecutionState` construction ~449), P9 (render artifact consumer) | P6 first or rebase |
| `tests/orchestration/test_execution_phase_plan.py`, `test_execute_run_lifecycle.py` | P5 (request construction), P7 (`PrepState`, selection fields), P10 (publish output application) | P5 and P10 before P7 (already the package order) |
| `tests/services/test_alignment_frozen_strings.py`, `tests/vsview/test_alignment_review_panel.py` | P6 (CQ21c and review-map signature) | Same package; CQ21c step precedes CQ2 step |
| `tests/integration/test_alignment_u4_acceptance.py` | P11 (recipes), P7 (`RunContext`/`PrepState` constructors at ~808, ~1118), P5 (`RunRequest(root=root)` ~1113) | Either order; second rebases; never run two Docker verifiers concurrently in one checkout |
| Docker verifier media cache (`generated/test-media-cache`) | P5–P9, P11 gates | One verifier at a time per checkout |
| `docs/current-architecture.md`, `docs/current-cli-contract.md` | P0, P1 (architecture ~426), P4 (finite timeouts), P5–P9 | Each package edits only its sections; integration owner resolves textual conflicts |

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
0. **Done during planning (2026-10-15, maintainer-approved).** The strict site build
   aborted at `53d0a2ce` because the two 2026-10-15 review reports under
   `docs/reviews/` used host-absolute `/Users/tristan/...` links to `.md` files
   (22 “page does not exist” warnings; this plan contributed none). Links to docs
   pages became relative links (line-number targets mapped to the section anchors
   they pointed into), and links to files outside the site (`AGENTS.md`,
   `.agents/project.md`, host skill files) became code spans; report wording is
   unchanged, and links to source files (not checked by the build) were left as they
   were. The strict build then passed with no warnings.
1. Rewrite the doctor paragraph: list runtime checks; state that TMDB is checked
   from local configuration and credential format only, that doctor makes no network
   requests, and that slow.pics connectivity is exercised only by publishing.
2. Rewrite the `--no-cache` description to the scoped-refresh behavior and the
   preserved caches.
3. Rewrite the Windows acceptance bullet: “`--no-cache` removes the matching analysis
   entry, recomputes, and persists a fresh entry; repeated runs without it then hit.”
4. Checked and left unchanged: “Optional or network doctor warnings” in
   `tools/windows_portable/README.txt` (~56) and “Doctor reports an optional/network
   warning” in `docs/getting-started/windows-portable.md` (~292) refer to doctor's
   contract-defined “Network and credentials” section, not to network access.
5. Run `uv run --no-sync pytest -q tests/test_cli_contract_docs.py`,
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
  (`{schema_version, install_type, bundle_path}`). The bundle `install.ps1` copies the
  `bin` shims first (~43–53), then writes the pointer through a temporary file and
  move (~54–61), then updates the user `PATH`; only the pointer write is atomic.
  Readers: `shim/frame-compare.ps1`, `shim/frame-compare-update.ps1` (~279–304),
  `verify_extracted_bundle.ps1` (~1290).
- The AppData state `config.toml` written by `install.ps1` (~63–77) uses
  bundle-relative `comparison_videos`/`generated` paths; the shim runs from the
  active bundle directory. A newly activated bundle therefore does not see data left
  in the previous bundle.
- The builder always creates **empty** `config\` and `comparison_videos\` folders
  (`build_portable.ps1` ~1184–1189), which the extracted-bundle verifier requires
  (`verify_extracted_bundle.ps1` ~431–436); `write_bundle_inventory.py`
  `_assert_safe_bundle` (~298–321) rejects any file under them. In-place preservation
  of user files inside the output root would fail the build's own inventory check,
  and overlaying a runtime onto old files is documented as unsupported.
- **The build location is part of the bundle's update identity.** `uv export
  --output-file $reqFile` (`build_portable.ps1` ~599–604) writes the absolute output
  path into the header of `requirements.lock.txt` (reproduced during plan review with
  the locked `uv`); its SHA-256 becomes `bundle_info.requirements_lock_sha256`
  (~767–789), and the updater refuses any code-only update whose
  `expected_requirements_lock_sha256` differs (`frame-compare-update.ps1` ~876–883).
  CI builds at a fixed path, so the fingerprint is stable between releases today. Any
  design that builds at a varying path (for example a randomly named staging folder
  renamed afterwards) would change the fingerprint every release and make the updater
  refuse every code-only update.
- CI (`windows-portable-build.yml` ~92–104) passes `-OutDir dist/frame-compare-portable-win-x64`
  on a fresh checkout and never relies on overwriting.

**Chosen design.**

*Builder (`build_portable.ps1`): validate first, atomically reserve the final output,
build in place, and clean up only what this run reserved.*

1. Before any filesystem mutation: resolve paths; read and validate the manifest,
   including the fields today checked late (`manifest_version` and
   `bundle.runtime_fingerprints`, read in `Write-BundleInfo` ~773–782) and every
   artifact `destination` (each must be a relative path that stays strictly inside the
   bundle root; today `Install-Artifact` joins it unchecked, ~201–202, and a value such
   as `.` would make `Expand-ArchiveFile` delete and recreate the root, ~159–162);
   normalize trailing separators on every compared path; validate relationships:
   - `OutDir` must not exist (a file, a directory, or a reparse point). There is no
     overwrite flag: maintainers delete disposable output explicitly.
   - `OutDir` must not be a drive root and must not equal or contain the current
     directory, `RepoRoot`, `CacheDir`, `$PSScriptRoot`, or the manifest's directory;
     it must not lie inside `CacheDir`, `$PSScriptRoot`, or the manifest's directory;
     it may lie inside `RepoRoot` only beneath `RepoRoot\dist`. `CacheDir` and
     `OutDir` must not nest either way. (Being inside the current directory is
     allowed: the builder's own default is `$PWD\dist\…`.)
   - Relationship and occupied-path refusals name the resolved paths; the existing
     proof that relative paths resolve against the provider location moves to an
     occupied-`OutDir` refusal (the manifest-missing error names only the manifest).
2. Reserve `OutDir` itself with the existing atomic reservation
   (`New-AtomicallyReservedDirectory`, `verify_extracted_bundle.ps1` ~270–283, whose
   native create-new call refuses an existing path, Win32 error 183). Move it and
   `Test-PathWithin` (~38–44) into one dot-sourced build-time helper,
   `tools/windows_portable/path_safety.ps1`, used by both the verifier and the
   builder. Its interop type `FrameCompareNativeDirectory` (~72–78) currently shares
   one `Add-Type` block (~65–268) with `FrameCompareProcessJob` and the bounded-stream
   class, so split out only that C# type into the helper, guarded by a
   type-already-loaded check so dot-sourcing twice cannot fail; the verifier keeps its
   other types. Give the function a label parameter (its error 183 message is
   hard-coded to `ExtractRoot`, ~277). Add the helper to `SOURCE_SCRIPTS` in
   `write_bundle_inventory.py` (~30–49) and to the build-scripts provenance fixture
   (`test_windows_portable_build_scripts.py` ~1233–1251). The reservation may create
   a missing parent such as `dist\` (~271); that is the only mutation left on failure
   and touches no existing file.
3. Build in place at the final path, exactly as today, so the lock header and
   `requirements_lock_sha256` stay identical to today's CI output.
4. On any failure after a successful reservation, remove only that reserved
   directory, identified by the reservation result held in memory (never by path
   existence alone). A failure before reservation removes nothing. A process crash
   can leave a partial `OutDir`; the next run refuses it as occupied and names it, so
   it is never silently reused or deleted.
5. Rejected: build into a randomly named staging sibling and rename on success. It
   protects the final path equally, but it embeds the staging path into the lock
   header and so breaks code-only update admission (fact above). Rejected: post-hoc
   rewriting of the lock header; it hides a path dependency instead of avoiding it.
   (Making the lock path-independent with `uv export --no-header` is a separate,
   deliberate fingerprint migration and is not part of this package.)

*Source installer (`install-from-source.ps1`, root `install.ps1`): fresh target,
activation after verification, explicit user-data policy.*

1. Default `-OutDir` becomes a fresh sibling under `dist\`:
   `frame-compare-portable-win-x64-<yyyyMMdd-HHmmss>Z` (UTC, so a clock fall-back
   cannot repeat a name; the application
   version is recorded in `bundle_info.json`, so it is not needed in the name and no
   second version source is introduced). An explicit `-OutDir` that exists is refused
   by the builder before mutation.
2. Read the current pointer's `bundle_path` (if any) as the previous bundle. The
   installer never deletes or rewrites the previous bundle's runtime or code.
3. Build and verify first (“verify” is the builder completing successfully,
   including its existing runtime-smoke and bundle-inventory steps). Only then handle
   user data, then run the new bundle's `install.ps1` to activate it.
4. User data: new parameter `-UserData Move|Leave` on `install-from-source.ps1`,
   forwarded by root `install.ps1` (which today forwards only `-SkipSync`;
   `install.cmd` already forwards `%*`). Only the documented user locations
   `config\`, `comparison_videos\`, and `generated\` are considered, and a location
   counts as user data only when it is **non-empty**; no other file is inferred to be
   user-owned or disposable.
   - The previous bundle counts as absent (activate directly, no data handling) when
     the pointer is missing or malformed, its `bundle_path` does not exist, it has no
     `bundle_info.json`, or it equals the new `OutDir`. The installer refuses when the
     new bundle is inside or contains the previous one.
   - `Move`: precondition checks before any move: each non-empty source folder exists;
     each target folder in the new bundle is absent or empty. Then, for each non-empty
     source folder: remove the new bundle's empty placeholder folder (re-checking that
     it is empty) and rename the source folder into the new bundle. A rename failing
     because source and target are on different volumes (Win32 error 17; detected by
     the failed rename rather than by comparing drive roots, which misses mount points)
     means `Move` is unavailable: reverse and refuse activation with instructions.
     All-or-nothing: if any step fails, reverse completed renames and recreate removed
     empty placeholders, and do not activate.
   - Activation failure after `Move`: the bundle `install.ps1` replaces the `bin`
     shims (~49–53), then switches the pointer (~55–62), then writes the state
     `config.toml` and `PATH` (~64–99), so it can fail after switching the pointer.
     On failure, re-read `state\config.json`; if it names the new bundle, first restore
     the previous pointer (temporary file and replace), then reverse the moves so the
     data is back in the active bundle; then re-run the previous bundle's
     `install.ps1` to restore its `bin` shims. If any reversal step fails, stop and
     report exactly where every folder and the pointer now are; never delete.
   - `Leave`: activate without moving; the message lists the non-empty folders left
     behind and warns that the shim may now select an older AppData state config if
     the new bundle has no `config\config.toml`.
   - Default when the previous bundle holds non-empty user folders and `-UserData` is
     absent: **`Move`** (decision D1, accepted).
   - If there is no previous bundle or no non-empty user folder, activate directly.
   - Moving media changes absolute source paths, so path-keyed caches miss once and
     recompute; absolute paths inside the user's config are not rewritten. The
     completion message states both and names the previous bundle path.
5. Old bundles are never deleted by the installer. Print the previous bundle path and
   state that it can be removed manually once the new one is accepted.

*Rejected alternatives.*
- **In-place preservation** (keep user folders in the output root while rebuilding):
  conflicts with the inventory's forbidden-content check and the documented
  “never overlay a runtime” rule, and requires inferring which files are disposable.
- **Refuse-only installer** (smaller: refuse the occupied default output and tell the
  user to delete/rename it): safe, but breaks the documented “rerun `install.cmd`”
  source-update path and pushes data handling onto users at the exact moment the
  report found data loss. D1 chose `Move`, so this is not used; note that the
  builder's refusal alone already removes the destructive path.
- **Shared transaction code with the updater (P2):** the builder produces a whole
  user-owned root activated by a pointer under PowerShell 7; the updater swaps only
  `app\src\frame_compare` under a lock on Windows PowerShell 5.1. They share the
  validate → reserve/stage → commit principle, not code.

**Ordered steps.**
1. Move `Test-PathWithin` and `New-AtomicallyReservedDirectory` (with its interop
   type) into `path_safety.ps1`; dot-source it from the verifier and builder; update
   provenance lists. Add builder pre-mutation validation and reorder `Main` so
   manifest validation precedes any mutation.
2. Replace the delete-and-recreate step with reservation, in-place build, and
   reservation-scoped cleanup.
3. Update the source installer defaults, pointer read, `-UserData` handling with
   preconditions and reversal (including reversal on activation failure), activation
   ordering, and messages; thread `-UserData` through root `install.ps1`.
4. Update docs: `tools/windows_portable/README.txt` (source builds produce a
   timestamped folder; the shim always uses the active bundle; user-data choices),
   `docs/getting-started/windows-portable.md` (~255–275), `INSTALL-WINDOWS.md` if it
   names the fixed folder, `docs/current-architecture.md` (~426, which names the fixed
   output folder), and the runbook's Windows section (maintainer rebuilds must remove
   disposable output first; builder refuses occupied output).
5. Tests (below), replacing incidental spelling assertions near the touched owners.

**Caller migration and deletions.** Delete the unconditional `Remove-Item -Recurse
-Force -LiteralPath $OutDir` and recreate step, and the verifier's private copies of
the moved helpers. CI invocation keeps working unchanged (fresh checkout, same final
path). No compatibility path keeps the old destructive behavior.

**Tests (CQ15 and CQ21d).**
- Rework `test_windows_portable_build_scripts.py` ~62–108 (currently asserts that a
  relative output directory is created even when the manifest is missing): assert that
  nothing is created or removed when the manifest is missing or malformed, and keep
  its proof of relative-path resolution through the error message that names the
  resolved output and cache paths.
- New Windows-executed builder fixtures (gated like existing ones: `os.name == "nt"`
  plus PowerShell discovery): occupied `OutDir` refused with sentinel files
  byte-identical; unsafe relationships (drive root, repo root, ancestor of the repo or
  current directory, cache nesting, manifest directory) refused before mutation;
  `OutDir` beneath the current directory accepted; injected failure after reservation
  removes only the reserved `OutDir`; a leftover partial `OutDir` is refused, not
  deleted.
- Fingerprint stability: building the same commit twice at the same final path yields
  identical `bundle_info.requirements_lock_sha256` (Windows acceptance; guards the
  update-admission fact above).
- Source-install fixtures with a stubbed builder (existing entrypoint test style) and
  an **isolated `LOCALAPPDATA`** (every source-install test must set it to `tmp_path`;
  otherwise the pointer read and default `Move` could act on a developer's real
  installation): previous bundle with non-empty `config\config.toml`,
  `comparison_videos\x.mkv`, `generated\run\…` sentinels and a pointer; new bundle with
  empty placeholders. Assert: repeat invocation builds a new folder; previous
  runtime/code untouched; `Move` relocates exactly the non-empty folders and switches
  the pointer; `Leave` switches the pointer without moving; empty previous folders are
  not treated as user data; different-volume `Move` refuses activation; injected build
  failure leaves the pointer and previous bundle byte-identical; an injected rename
  failure reverses completed moves, restores placeholders, and does not activate; an
  injected `install.ps1` failure **before** and **after** its pointer write returns the
  data and the pointer to the previous bundle; stale, missing, self-referencing, and
  nested previous-bundle pointers follow the rules above.
- Migrate `test_root_source_installer_prerequisite_at_process_boundary`
  (`test_windows_portable_install_entrypoints.py` ~146–199): it runs the real source
  installer against the host `LOCALAPPDATA` and asserts the fixed
  `dist/frame-compare-portable-win-x64/install.ps1`; isolate `LOCALAPPDATA` and assert
  the timestamped folder instead.
- CQ21d replacements in this package's owners (keep structural checks): replace
  `install_entrypoints` ~39–41 invocation-spelling assertions, `build_scripts`
  ~114/117 (`$bundleConfigDir` spelling), ~706 (`Get-AppVersionFromSource … $OutDir`
  spelling), and ~2442–2463 helper names with executable fixtures or bundle-inventory
  observations. Retain public-key gate, `git archive HEAD` committed source,
  `--require-clean-repo`, PowerShell 7 prerequisite, CMD absolute-path fallbacks, and
  forbidden inventory content checks.

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
instead of deletion (intended). CI bundles keep the same build path and therefore the
same requirements fingerprint. Existing installs pointed at
`dist\frame-compare-portable-win-x64` keep working; the next source install creates a
timestamped sibling. Source-built bundles already have path-specific requirements
fingerprints today; that does not change. Disk usage grows until users delete old
bundles (documented).

**Rollback.** Revert P1. Bundles created with timestamped names stay valid because the
pointer stores an absolute path.

**Exit criteria.** No code path removes an existing output root; failure cleanup
removes only a directory this run reserved; manifest/build failure leaves existing
state byte-identical; the requirements fingerprint is unaffected for CI builds; repeat
source installation preserves user data per D1's chosen policy, including reversal on
activation failure; Windows acceptance recorded or explicitly open.

---

### P2 Updater version grammar and safe source replacement (CQ16, CQ17, CQ21d part)

**Problems.**
- **CQ16 (confirmed, S2):** `frame-compare-update.ps1` extracts versions with
  `^frame-compare\s+([0-9]+(?:\.[0-9]+){1,3})$` (~584–599), falling back to raw
  `__version__` (~612–622); `Test-StringInRange` (~564–582) uses
  `[System.Version]::Parse`, so installed RC versions (`0.8.0rc1`) always fail
  admission. Release inputs support RC versions (`.github/workflows/release.yml`,
  `scripts/validate_release_contract.py:15–19`). `build_update.ps1` (~69–75, ~272–285)
  writes raw `to_app_version`, numeric `from_app_version_min = "<MAJOR>.<MINOR>.0"`,
  and `from_app_version_max = $null`. Additionally `Invoke-SmokeCheck` (~458–486)
  verifies the target by substring match.
- **CQ17 (inferred risk, S2):** `Restore-FromBackup` (~631–636) deletes the current
  source tree and copies the backup into place; explicit rollback (~638–674) uses it
  with no staging, completeness check, smoke check, or recovery. Apply (~676–1006)
  already stages `.new`, keeps `.old`, renames, smoke-checks, and recovers, but its
  recovery fallbacks (~951, ~971) also use `Restore-FromBackup`. Apply also reads the
  installed version by running the bundle (~790–799), throws if the target is missing
  (~892), deletes any stale `.old` (~898–900), and creates the backup with
  `Copy-Item` into a per-second ID directory via `Ensure-Directory` (~902–910) before
  writing `compatibility.json` (backup identity) beside it.

**Distribution fact.** Code-only updates carry only `app/src/frame_compare`; the
updater in `%LOCALAPPDATA%\Programs\FrameCompare\bin` changes only when a full
bundle's `install.ps1` runs. The P2 updater therefore reaches users through full
bundle installation, which always targets a fresh directory with no backups (the
`bin` updater locates its bundle through the pointer `install.ps1` writes for its own
bundle). Installations already on an RC with the old updater cannot repair themselves
through a code-only update; release notes must direct them to a one-time full bundle
install.

**Chosen design.**

*Version grammar (one PowerShell owner, one Python owner, one shared vector table).*
- New `tools/windows_portable/shim/frame-compare-version.ps1` with
  `ConvertTo-FrameCompareVersion` (parse or `$null`), `Compare-FrameCompareVersion`,
  and `Test-FrameCompareVersionInRange`. Consumers:
  - the updater dot-sources it from its own directory and fails with a clear message
    if it is missing;
  - `tools/windows_portable/version_utils.ps1` (already dot-sourced by
    `build_portable.ps1` ~22 and `build_update.ps1` ~19) dot-sources it, and
    `Get-AppVersionFromSource` validates its result with the grammar, so the build
    scripts gain the grammar through the existing helper rather than a new import;
  - bundle `install.ps1` adds it to its file checks and copy list (~24–37, ~43–53)
    and `uninstall.ps1` to its removal list (~39);
  - `verify_extracted_bundle.ps1` adds it to `requiredEntries` (~365–379);
  - `write_bundle_inventory.py` adds it to `SOURCE_SCRIPTS` (~30–48), with the
    provenance fixture (`test_windows_portable_build_scripts.py` ~1233–1251);
  - test harnesses: the updater-only copy in `test_windows_portable_update_apply_e2e.py`
    (~70–83) copies it too, and the `managed_bin_files` list in
    `test_windows_portable_install_uninstall_e2e.py` (~93–99), used for both bundle
    shim sources and `bin` expectations, gains it.
- Grammar (Windows PowerShell 5.1 compatible, case-sensitive `-cmatch`, ASCII
  `[0-9]` because .NET `\d` matches Unicode digits, `\z` rather than `$` because .NET
  `$` also matches before a trailing newline, component length capped so
  `[int]::Parse(..., [Globalization.CultureInfo]::InvariantCulture)` cannot overflow):
  `^(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})(?:rc([1-9][0-9]{0,8}))?\z`.
  For ASCII inputs within the length cap this accepts exactly the release contract's
  stable/RC strings (`STABLE_VERSION_RE`/`RC_VERSION_RE`). The Python regexes use
  Unicode `\d` and no cap; add `re.ASCII` to them (a release-contract tightening with
  no valid-version consequence) so both sides agree on the edges.
- Ordering: `(major, minor, patch, rc)` with the final release ordered after every
  `rcN` of the same base. Python has no ordering owner, so ordering vectors are
  exercised only by the PowerShell test.
- Range semantics (decision D2): `max` inclusive; an RC `min` uses strict order; a
  stable `min` `X.Y.Z` also admits that base's release candidates (behaves as
  `X.Y.Zrc1`). The generator keeps emitting numeric `X.Y.0`, so updaters already in
  users' `bin` still parse stable bounds with `System.Version` and keep their
  stable→stable path.
- Downgrades: the updater has no downgrade check today, so a target older than the
  installed version but inside the signed range is admitted (for example installed
  `0.8.0`, target `0.8.0rc2`). P2 keeps that behavior (rollback is the supported way
  back; signed ranges bound what can be applied) and documents and tests it rather
  than adding a new refusal (part of D2).
- Malformed installed, bound, or target versions fail closed with a clear message
  before any mutation.
- `Invoke-SmokeCheck` parses the reported version with the same grammar and compares
  exactly (`Compare-FrameCompareVersion -eq 0`).
- Python remains authoritative in `scripts/validate_release_contract.py`. Add a JSON
  vector file (e.g. `tests/windows_portable/version_vectors.json`) consumed by a
  Python test against `validate_release_contract` (validity vectors) and by a
  PowerShell-executed test against the PowerShell owner (validity and ordering), so
  the two implementations cannot drift silently.
- Manifest format: unchanged fields and `schema_version`. Optionally add the grammar
  as a JSON-schema `pattern` on `to_app_version`/`from_app_version_*` in
  `update_manifest.schema.json`; this is validation tightening, not a format change.

*Source-tree replacement transaction (updater-only).*
- A small journal, `app\.frame_compare_replacement.json`
  `{schema_version, operation, state: "staging" | "promoting" | "committed", started_at}`,
  makes interrupted states unambiguous. Each state change writes a temporary file and
  then `[IO.File]::Replace` (or `[IO.File]::Move` when no journal exists yet), because
  `Move-Item -Force` over an existing file is not documented as atomic; repair ignores
  and removes a leftover journal temporary file, which never blocks the next write.
- `Repair-InterruptedReplacement -BundlePath` runs **immediately after
  `Acquire-UpdateLock` in both apply and rollback**, before apply's version read,
  target-exists check, or stale-`.old` deletion (all of which would otherwise refuse
  or destroy recovery material):
  - no journal: if `.old` or `.new` exist without a journal, refuse with their paths
    (unknown state; never guess);
  - `staging` (crash while copying into or verifying `.new`, or before any rename):
    remove `.new`, complete or partial; target untouched;
  - `promoting` (crash during or after the two renames, before commit): if `.old`
    exists, the previous tree is intact there and the current target (if any) never
    passed smoke, so move a present target aside to `.failed-<timestamp>` and rename
    `.old` back; if `.old` does not exist and the target exists, no rename happened and
    the target is untouched; if neither `.old` nor the target exists, refuse with
    paths; then remove `.new`;
  - `committed` (crash while removing `.old`): remove the leftover `.old`;
  - then delete the journal. Today's unconditional stale-`.new`/`.old` deletion at
    ~894–900 is replaced by this function. Repair is the only mutation allowed before
    version validation, and it only restores or removes transaction directories.
    `.failed-*` directories are retained for diagnosis; a successful commit removes all
    but the newest one.
- `Invoke-SourceTreeReplacement -BundlePath -TargetDir -CandidateDir -ExpectedInventory -ExpectedVersion`,
  called with the update lock held and after repair:
  1. Journal `staging`; stage the candidate into `.new` (copy).
  2. Verify `.new` against `ExpectedInventory` (exact relative path set, byte sizes,
     SHA-256).
  3. Journal `promoting`; rename target → `.old`, then `.new` → target
     (`Invoke-WithRetry` as today).
  4. Smoke-check with exact version.
  5. Journal `committed`; remove `.old`; delete the journal.
  On any failure before `committed`: move a promoted target aside to
  `.failed-<timestamp>`, rename `.old` back, delete `.new`, and delete the journal. If
  recovery itself fails, keep every directory and the journal, and report the paths
  and the manual recovery step. Never delete-then-copy.
- Apply passes its authenticated, extracted, hash-checked payload directory and the
  signed manifest's file list as the inventory, with the manifest's
  `app/src/frame_compare/` path prefix (~841) stripped to target-relative paths. Rollback passes the backup's
  `frame_compare` directory and the backup's own inventory.
- Signed archive authentication/extraction and backup identity/selection remain with
  their callers.
- Backup layout and completeness (`.update_backups\<id>\`):
  - Refuse an existing `<id>` directory instead of merging into it (IDs have
    one-second resolution and `Ensure-Directory` would merge).
  - Copy the current tree to `<id>\frame_compare` (unchanged location).
  - Keep writing `<id>\compatibility.json` exactly as today (identity checked by
    `list-backups`/`rollback`; tested at `test_windows_portable_update_scripts.py`
    ~762–773; runbook step 5).
  - Write `<id>\backup.json` **last**, via temporary file and move, as the completeness
    marker: `{schema_version, app_version, files: [{path, sha256, bytes}]}`, hashed from
    the source tree and verified against the copy. It sits beside, never inside,
    `frame_compare\`, so rollback cannot copy it into the source tree.
  - If backup creation fails, remove that partial `<id>` directory before refusing the
    update.
- `list-backups` and `rollback` require both a valid `compatibility.json` matching the
  installed identity (as today) and a valid `backup.json`; anything else is listed
  unavailable (“completeness record missing”), extending the documented policy that
  identity-less legacy backups are not migrated. In practice the P2 updater never
  coexists with pre-P2 backups, because it arrives only through a fresh full-bundle
  directory (the caveat is a manual or partially failed bundle install that rewrote
  `bin` but not the pointer; such backups are simply listed unavailable).
- `Invoke-PurgeBackups` (~488–507) keeps the newest five **complete** backups and
  removes incomplete ones, so incomplete backups can no longer displace usable ones.

*Rejected alternatives.* Stripping suffixes or mapping `rcN` into a fourth numeric
component (silently misorders and breaks exact verification); an inlined grammar copy
in each script plus a parity test (drifts; several scripts need it); a general
versioning library (new dependency, not needed); keeping `Restore-FromBackup` as a
“simple” rollback (it is the risk); inferring interrupted state from which directories
exist (ambiguous between “crashed before commit” and “crashed while committing”).

**Ordered steps.**
1. Add `frame-compare-version.ps1`, wire it through `version_utils.ps1`, the bundle
   installer/uninstaller, verifier, provenance list, and test harness copies; add
   vectors and Python/PowerShell vector tests; add `re.ASCII` to the release-contract
   regexes.
2. Migrate extraction, Python fallback, range admission, and smoke verification;
   migrate `build_update.ps1` validation and `min` derivation. `Write-BundleInfo`
   obtains `app_version` through `Get-AppVersionFromSource`, so the grammar check
   added to `version_utils.ps1` covers bundle info without a separate builder edit.
3. Add backup-ID refusal, `backup.json` creation/verification beside the existing
   `compatibility.json`, partial-backup cleanup, and purge of incomplete backups.
4. Add the journal, `Repair-InterruptedReplacement` (called right after the lock in
   apply and rollback), and `Invoke-SourceTreeReplacement`; migrate apply (promotion,
   smoke, recovery) and rollback to it.
5. Delete `Restore-FromBackup`, its fallback calls (~951, ~971), and the
   unconditional stale `.new`/`.old` deletion.
6. Update the runbook Windows section (version grammar, downgrade behavior, backup
   completeness record, journal and recovery material), `README.txt` update/rollback
   text, and the changelog/release-note guidance for RC users needing one full
   reinstall.

**Tests.**
- Signed apply E2E (`test_windows_portable_update_apply_e2e.py`, currently numeric
  `1.0.0`/`1.0.1` fixtures): add RC→RC, RC→stable, stable→RC within a line (per D2),
  stable→next-minor RC refused, inclusive `max`, a same-line downgrade admitted (per
  D2), malformed installed/bound/target values refused before mutation, and exact
  target mismatch (`0.8.0` vs reported `0.8.0rc1`; `1.0.1` vs `1.0.10`) triggering
  recovery.
- Transaction and rollback failure injection, comparing `_snapshot_bytes` of the
  current tree: unreadable backup file, truncated backup (inventory mismatch), copy
  failure, rename failure, smoke failure, and each interrupted journal state
  (`staging` with a partial `.new`;
  `promoting` after only the first rename; `promoting` after both renames;
  `committed` with a leftover `.old`)
  repaired correctly by the next apply **and** the next rollback; `.old`/`.new`
  without a journal refused with paths. Retain successful rollback,
  invalid/incompatible-backup refusal before lock creation, lock ownership, and purge
  serialization.
- Backups: existing `<id>` refused; failed backup leaves no partial `<id>`;
  `list-backups` lists missing/invalid `backup.json` or `compatibility.json` as
  unavailable; purge keeps five complete backups and removes incomplete ones.
- Parametrize apply/rollback E2E over `powershell.exe` and `pwsh` on Windows; today
  the helper prefers `pwsh`, so Windows PowerShell 5.1 is not exercised for the
  updater.
- CQ21d replacements: `update_scripts` ~680 (`"Get-BundleAppVersion" in updater`;
  behavior covered at `apply_e2e` ~389–400), ~731–732, ~740–742, ~766–771 (ordering
  against the deleted `Restore-FromBackup`; keep the `compatibility.json` obligation
  through behavior), and re-anchor ~646–649's no-bypass intent on behavior. Keep
  PKCS1/SHA256, signature-before-parse ordering (~685), schema constants, and
  no-interactive-bypass structural checks.

**Gates.**
- Linux: `uv run --no-sync pytest -q tests/windows_portable tests/workflows`
  (Python vector and release-contract tests run; PowerShell cases skip—inspect skips).
- **Acceptance requirement (Windows, PowerShell 5.1 and 7):** updater E2E above.
- **Acceptance requirement (Windows PowerShell 5.1 install/uninstall):** P2 changes
  the bundle `install.ps1`/`uninstall.ps1`, which retain 5.1 support; run the
  runbook's BOM-less UTF-8 install-state check from a non-ASCII bundle path under 5.1
  (runbook “Windows Portable / Release-Path Verification”, PowerShell paragraph).
- **Acceptance requirement (runbook steps 5–6):** build the code-only update ZIP,
  prove matching-runtime apply/rollback and mismatched-runtime refusal, sign it, and
  record the hosted `windows-portable.yml` run; if signing cannot run, mark signing
  documented-only and require maintainer confirmation.

**Compatibility.** Manifest fields unchanged. Old installed updaters keep working for
stable numeric installations. RC installations need one full bundle install to obtain
the new updater (documented). Backups keep `compatibility.json` and gain `backup.json`
beside it; older updaters ignore the extra file. The replacement journal is new
updater-private state inside `app\`.

**Rollback.** Revert P2; bundles installed with the P2 helper in `bin` are replaced by
the next bundle install. Backups with `backup.json` remain usable by older updaters
(`compatibility.json` unchanged, extra file ignored). A leftover journal is ignored by
older updaters.

**Exit criteria.** One grammar owner used by extraction, range, generator, bundle
info, and smoke; exact target verification; no delete-then-copy restoration remains;
every replacement goes through the journaled transaction; every interrupted state is
repaired or refused with paths by both apply and rollback; failure injections leave
the current tree intact or recoverable with reported material; Windows 5.1/7 evidence
recorded or explicitly open.

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
  `writeCurrentAlignment(a, {clearDrafts})` normalizes, applies the existing
  clip-count/key guards, and writes the map entry; it clears raw drafts exactly where
  today's code does (`setManualAlignment`, committed input, and non-custom presets via
  `applyAlignmentPresetOffsets` ~438–444: yes; `setAlignmentPreset('custom')`,
  ~546–556: no). `setManualAlignment` (~558) and
  `setAlignmentPreset` (~546, `custom` keeps current x/y) write through it, then
  `applyAlignment` and persist. `commitRawAlignmentInput` (~603), `applyAlignment`
  (~611–618), and `alignmentStatusValue` (~642–649) read `currentAlignment()`.
  `rawAlignX/rawAlignY` stay as transient drafts.
- `viewer.js`: `selectPair({left, right, mode, activate} = {}, {render = true} = {})`:
  resolve indexes, set mode, repair a distinct pair when the mode requires it
  (Slider same-source stays valid), resolve `activate` after repair in every mode
  (as `applyDefaultSelection` does today, ~978), apply Blink keep-in-pair **only when
  the resulting mode is `blink`** (today's condition at ~988, ~1001, ~1013, ~1089,
  ~1655; Overlay/Single and Diff deliberately allow an active source outside the pair,
  e.g. the restore case asserting `activeClipIdx === 3` in Diff with pair `0:1`,
  harness ~617), clear raw drafts on every left/right selection call (today's
  behavior through `loadCurrentPairAlignment`, even when the key is unchanged) and
  when mode-driven repair changes the pair key, and render (render persists).
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
Apply the same per-environment closure to `lens_harness.js`: `makeEnvironment`
creates elements (~87–143) before its `document` literal (~155; `focusDocument` is
assigned at ~176), and that document's `createElement` (~166) also calls
`fakeElement`, so the factory closure must resolve the document lazily from the
environment and cover `createElement` too; scenario-level `fakeElement()` calls
that become an environment's `activeElement` (`externalFocus` ~682,
`transientExternalFocus` ~719) use that environment's factory, while geometry-only
elements (~308, ~313, ~454) need no document. `grid_view_harness.js` does use
`domMechanics` (~21–23, ~74) but closes over its single module-level `context`, which
is never replaced, so it needs no change; viewport, inspector, and review harnesses do
not use the shared mechanics. Run async scenario groups sequentially for clear failure
attribution.

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
   review_controller, viewport, and inspector harnesses (the inspector bridge,
   `test_report_viewer_inspector.py` ~19–35, mirrors 15 class-(b) `True` markers); move (c) fields into JS assertions,
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
inspector ~196–197), viewport-harness stubs (~110, ~190), and the inspector
harness's two `viewport` stubs (~227, ~378, which need `currentAlignment()`) migrate
to the new interface; ~40 `viewer.state.alignX` reads become `currentAlignment()`.

**Preserved behavior.** Directional pair keys, valid same-source Slider, single-clip
`0:0`, storage key `frame-compare:report-viewer:${report_id}:viewport` and
`pairAlignments` schema, malformed-state normalization, restored width-fit, keyboard
and focus behavior, Blink pause intent, Grid pan-unit conversion, and stale Diff
image rejection. Intentional differences: (1) visiting a pair without editing it no
longer writes a neutral entry (absent already means neutral on restore); (2) when
`setMode` repairs the pair to a different key, uncommitted raw drafts are cleared, so
a draft typed for the old pair cannot commit onto the restored pair (today `setMode`
never touches drafts).

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
  the `#canvas` `--align-x`/`--align-y` custom properties (set by `applyAlignment`,
  `viewport.js` ~611–612), `#alignment-status`, and persisted `pairAlignments['0:1']`;
  repeat for Blink and an unset destination. In Blink the right layer is hidden while
  the left source is active, so assert the custom properties there (or toggle the
  active source before reading the transform); record into one `data-` JSON attribute and assert all cases.
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
| `config/schema_sources.py` `TomlConfigSettingsSourceNoBOM._read_file` (~21–24) | re-raise `TOMLDecodeError`/`UnicodeDecodeError` unchanged; map `(RecursionError, ValueError)` to `ConfigParseError(path, "configuration exceeds TOML parser limits")` | typed `FC-1002`-family config failure, exit 2 (O2); never silent defaults |
| `config/loader.py` `load_raw_config` (~153–163) | same mapping | typed config error for wizard paths |
| `config/presets.py` (~52–63) | same mapping to `PresetInvalidError(preset_path, parse_details)` | typed `FC-1005` preset failure |
| `config/schema_sources.py` `EnvironmentSettingsSource` (~27–37, complex-value decoding for `FRAME_COMPARE_*` JSON variables) | convert `RecursionError` to `ValueError` where the complex value is decoded, so pydantic-settings' existing `SettingsError` path applies (a long integer already becomes `ConfigValidationError` `FC-1003` today) | typed `FC-1003` config failure for deeply nested environment JSON (planning review reproduced a raw `RecursionError` with `FRAME_COMPARE_TMDB` set to 10,000 nested brackets) |

The existing `(RecursionError, ValueError)` handling for embedded evidence at
`alignment_review_contract.py` ~446–448 switches to the shared constant so one
documented tuple remains.

Not changed: `tmdb_cache.py` ~106/~183 membership-before-type (already contained per
entry); `run_result_record.py` tuple membership (does not hash); subprocess JSON
(ffprobe) is not persisted state.

**Ordered steps.** (1) Add the constant and its contract test; (2) per-owner changes
in the table; (3) CQ19 field constraints; (4) tests; (5) document that the four
timeouts must be finite next to their existing minimum-bound text in
`docs/current-cli-contract.md` (every timeout entry: ~1382 and ~1635 plus the
slow.pics and TMDB `timeout_seconds` entries) and `docs/reference/configuration.md`
(the four timeout entries, ~474, ~717, ~807, ~893).

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
  `ConfigParseError` for deep and long-integer TOML; `load_config` raises
  `ConfigValidationError` for a deeply nested `FRAME_COMPARE_TMDB` JSON value; CLI-level
  JSON error tests in `tests/cli/test_run_json_errors.py` observe a single typed error
  object for both; `tests/config/test_presets.py` (~63) observes `PresetInvalidError`.
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

- `RunRequest` carries `inputs: AcquiredRunConfig` (required) plus its existing
  run-only control fields (`orchestration/types.py` ~32–44, e.g. `no_cache`,
  `from_cache_only`, `skip_analysis`, `skip_metadata`). `root`, `config_path`, and
  `config_overrides` are removed: there is no optional path beside optional settings.
  `--no-upload` is not a request field; it stays a `CLIConfigOverrides.no_upload`
  override mapped into `slowpics.auto_upload` during acquisition, so no second
  authority is added.
- Callers: the CLI builds `RunRequest(inputs=…, …)` directly from the value it
  already acquired; `build_run_request` (which acquires) is only for programmatic
  callers (benchmark, tests), so the CLI never acquires twice. `build_run_request`
  imports `RunRequest` lazily to keep `run_inputs` light (verified during review:
  `orchestration.preflight` and `cli.entry` import without httpx or `vs.loader`;
  `orchestration/__init__` is lazy; `orchestration.types` pulls both).
- `resolve_run_workspace` recomputes path facts and containment from the admitted
  config **at each use**; it is a use-boundary check against the current
  filesystem, not a second config read. (Decided over caching `WorkspacePaths` in the
  acquired value because containment and input existence are external state.)
- Path selection runs before `parse_run_options` so path-escape errors keep their
  precedence; environment expansion happens once inside acquisition (fixing the
  unexpanded-path admission load).
- `execute_prep` consumes `request.inputs.config` and `resolve_run_workspace`, still
  checks the input directory and lists sources once (source freshness at use, O5).
  Deleted, after migrating every caller listed here: `prepare_preflight` and its
  re-export through `preparation`, its duplicate input listing,
  `build_preflight_input_dir_override`, `_resolve_paths_with_config_file`,
  `PreflightResult` (its `warnings`, read at `preparation.py` ~676 and ~769, move to
  the workspace resolution result), `config/effective.py`'s `load_effective_config`
  and `resolve_effective_config` (their remaining readers become
  `refresh_report_auto_open_preference`), and `resolve_workspace`'s upward search once
  doctor no longer uses it. Callers to migrate: `tests/orchestration/test_preflight.py`
  (~528–654), `test_preparation_cache.py` (~102, ~193, ~251, ~303, ~355),
  `test_execute_run_failure_cleanup.py` (~47), `test_preparation_active_rect.py`
  (~364), and `tests/config/test_effective.py` (~16). The loader parameters of
  `maybe_open_report_path` and `build_confirm_slowpics_upload_callback`
  (`run_command.py` ~720, ~433) change to take the acquired value and injected
  loader, so also migrate `tests/cli/test_run_interactive.py` (13
  `resolve_effective_config=` arguments) and `tests/utils/test_terminal.py` (~90).
- CLI `handle_run` acquires once; dry-run, logging, diagnose-paths, write-config
  (`write_config_to(inputs.config_path, inputs.config)` through the existing
  secret-safe persistence), `validate_run_contracts`, callbacks, preview,
  clipboard/browser actions, and upload suppression read `inputs`.
  `build_effective_config_loaders` is deleted.
- The intentional post-run auto-open refresh (`docs/current-cli-contract.md`
  § “Report Auto-Open Ownership”) remains as `refresh_report_auto_open_preference`:
  rereads `inputs.config_path`, returns `report.auto_open`, or `None` on failure
  (report opens, matching ~982–983). Used by `maybe_open_report_path` (~715–735) for
  the post-run open and by the slow.pics confirmation callback before its prompt
  (~441–446). The CLI passes its injected `deps.load_config`, not the module default,
  so tests that inject loaders observe these refreshes. These named refreshes are the
  only config reads besides the single acquisition.
- Preserved boundaries: runtime-free simple commands (O1); dry-run exits before any
  request or side effect; wizard raw edits keep `load_raw_config` and are untouched;
  secret-safe persistence; source freshness and containment rechecked where sources
  and paths are used, not frozen at admission.
- Rejected smaller alternative: recheck selected flags at runtime against a second
  load (leaves two snapshots and a reconciliation policy). Rejected alternative:
  move admission after runtime acquisition through preparation (pulls runtime
  imports into admission, risking O1, and still leaves callbacks needing the value).

**Preview (CQ8 second half).** `print_at_a_glance(console, *, inputs, no_cache: bool,
from_cache_only: bool, skip_analysis: bool, skip_metadata: bool, no_upload_flag: bool,
verbose)`; every displayed setting reads `inputs.config`; the explicit keyword
booleans supply run-only flags (no request object, so the preview cannot read a
second config); `no_upload_flag` exists only for the
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
injection (`Get-ConfigInjectionIndex`). Doctor resolves its selection through
`run_inputs.select_run_config_path`, the same function run uses. Failure behavior
follows where each check lives: `resolve_selected_config_path` (`preflight.py`
~259–279) only expands, syntax-checks, and contains the path, so a path that escapes
the root or is syntactically invalid is a typed top-level failure through the
standard CLI error contract, exactly as for run (the doctor contract already allows
typed top-level failures and `handle_doctor` catches `FrameCompareError`). Regular-file
and readability checks live in `load_config` (`loader.py` ~82–95, raising
`ConfigParseError`), so an explicit config that is missing (`ConfigNotFoundError`),
nonregular, unreadable, or fails to parse/validate is reported in the TMDB check's
details, not as a top-level failure; `_resolve_tmdb_config` (`doctor_checks.py`
~620–645) must catch `ConfigNotFoundError` for that explicit case, which it does not
today. An absent **default** config keeps today's behavior (passed as `None`, so
defaults+environment). No HTTP; JSON schema unchanged.
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
  acquired config; `test_run_command.py` ~404 (today asserts
  `config_overrides.input_dir`) asserts the acquired config's resolved input
  directory, and ~436 asserts `inputs.config_path`;
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
- **New orchestration regression:** acquire with a counting `load_config_fn`;
  rewrite the file; make the counting loader fail on any further call (patching
  `config.loader.load_config` alone would prove nothing, because modules bind the
  function by name at import); `execute_prep` uses the admitted settings and the
  loader count stays at one. Delete a source file after acquisition:
  `NoVideosFoundError` still raised.
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
New public doctor options (D4). Visible changes, recorded in §9: the preview `input`
row shows the resolved directory; when `--config` contains an environment variable,
`--diagnose-paths` JSON `"config"` and the `--write-config` destination now show the
expanded path (today the unexpanded argument); `phase_timings["preflight"]` shrinks
because acquisition moves out of `execute_prep` (it feeds the summary setup row and
the run record). Run JSON outputs are otherwise unchanged.

**Rollback.** Revert P5 as a unit (internal callers migrate atomically).

**Exit criteria.** Exactly one config acquisition per run (assert by counting
`acquire_run_config` calls, plus `load_config` calls equal to one acquisition plus the
named preference refreshes that actually ran; the `--json` variant has no refresh); no
runtime reapplication of overrides; preview
has no override logic; benchmark and tests use the acquisition owner; doctor and run
select the same config for the same arguments and under the shim.

---

### P6 Alignment decision and resolution ownership (CQ5, CQ21c, CQ2)

**Problems.**
- **CQ5:** `v6_failure_reasons` (`services/alignment_decision.py` ~287) and
  `is_trusted_automatic` (~326) encode the same five gates; `decide_after_video`
  (~595–633) calls both and keeps a now-unreachable `"no_single_offset"` fallback
  (~628) and `reasons or (primary_reason,)` (~633). Sole production caller:
  `decide_after_video`; also exported in `__all__` (~828) and called at three sites in
  two test functions (`test_alignment_decision.py` ~445/~451 and ~499).
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
(existing reference-FPS conversion; the caller resolves the reference FPS once, only
when confirmed offsets exist, before the loop, as `alignment.py` ~217–223 does today), keeps the previous `stability` and the same
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
ReusableSourceSetCandidate | None` in `services/alignment_reuse_cache.py`. It already
owns the origin mapping and serialization prerequisites, and `save` can then accept
only a prepared candidate; `alignment_previous_offsets` already imports
`alignment_reuse_cache`, so putting the candidate type in `previous_offsets` would
create a cycle. Key spaces: the resolutions map is keyed by `alignment_key` (as
today's service gate, `previous_offsets.py` ~213), while persistence completeness is
by `comparison_cache_key` (`reuse_cache.py` ~560–566); `prepare_reusable_source_set`
checks that every requested comparison exists under its `alignment_key` **and** that
the record's `comparison_cache_key` matches the request's. It unions today's rules:
complete requested set (unrelated items ignored), applied,
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
  only services producer/parity tests fail; panel tests pass. This counts only if the
  panel and contract suites actually collect and run: `tests/vsview/test_alignment_review_panel.py`
  uses `importorskip` for PySide6/vsview and fails to import in the planning container
  (`libEGL.so.1` missing). Run it where Qt/EGL is available (`--extra vsview`) and
  inspect skips; a skip or collection error is not a pass (AGENTS.md).
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
  ~147/~1198–1214, cancellation diagnostics patches ~156/~285 and `save` patches
  ~158/~287, and `test_alignment_video_wiring.py` ~65, which patches
  `save_reusable_offsets` with a `(request, provenances)` lambda) goes through one
  `_resolution` test helper and the new `save` signature.
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
  The prepared selection domain (window, analysis clip, token, override) is rebuilt
  in `preparation.py` (~624–667 cache-only, ~707–756 normal) and
  `full_window_retry.py` (~194–215, assigning seven fields ~217–223, including config
  and clips), held as four `PrepState` fields (`execution_types.py` ~196–199),
  copied field-by-field in `coordinator.py` (~169–174), `tools/alignment_benchmark.py`
  (~286–293), and the U4 test (~1118). The metric request is not part of that state
  today: Analyze builds it lazily (`phase_selection.py` ~299) and preparation builds
  it only on its cache-only and `no_cache` branches (~662, ~751).

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
  absent `analysis_source_path` with `video_paths[0]` (today's `metrics.py` ~187);
  `acquire_required_metrics` uses the same `_keyed_request`, so both reads key exactly
  as computation does.
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
  (pre-alignment prepared clip), `token: str` (`""` when no analysis clip), and
  `full_window_retry_override` — the same four facts `PrepState` holds today. Built by
  `build_prepared_selection_domain(*, clips, config, analysis_clip, selection_window,
  override)`. The metric request is **not stored**: one function,
  `metric_request_for_domain(domain, config)`, wraps `metric_cache_request_for_clip`
  (its inputs are the domain's `analysis_clip` and `selection_window` plus
  `config.screenshots.active_rect_detection`) and is called exactly where requests are
  built today (Analyze; preparation's cache-only and `no_cache` branches). The
  cache-only branch builds its request from `prevalidated_*` values before the final
  domain exists (`preparation.py` ~651–667); it builds a prevalidated domain there
  with the same builder. Building it eagerly for every run would move
  `MetricFrameRange` validation (`analysis/types.py` ~60–63, can raise `ValueError`)
  from the warn-only Analyze phase into fatal preparation. It carries neither
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
   `PrepState` (four fields → `selection_domain`), coordinator copy, recovery,
   `phase_selection.py` (~298–303 via `metric_request_for_domain`, ~277–278,
   ~206–210), `phase_alignment.py` (~167, ~183–185), `full_window_retry.py` (~128,
   ~137, ~200, ~244), benchmark (~286), and test constructors
   (`phase_task_helpers.py` ~208, `execute_run_helpers.py` ~403, `test_phases.py` ~55,
   overlay tests, `test_ffmpeg_overlay_application.py` ~57, U4 ~808/~1118,
   `PrepState(...)` in `test_execute_run_lifecycle.py` ~107/~150/~214/~304/~385/~713
   and `test_execution_phase_plan.py` ~59).
4. CQ4: `SelectionSnapshot`; execution-time closures; `apply_phase_output` writer;
   readers (`phase_alignment.py` ~204/~213, `phase_render.py` ~49/~53,
   `phase_post_render.py` ~424–440, `coordinator.py` ~59–93 and ~218–262). Introduce
   one orchestration helper producing selection rows (frame, reference source frame,
   label/detail/category) from the snapshot and use it in **both** current consumers
   now: report frame details (`phase_post_render.py` ~428–441) and the label list
   `phase_render.py` builds (~44–55), deleting both private derivations in P7. P9
   later builds `SelectedScreenshot`s from the same rows. Test churn from removing
   `ExecutionState.selected_frames`, the three `RunContext` selection fields, and the
   four loose domain fields. Start with a grep over `src/`, `tools/`, and `tests/` for
   `selected_frames`, `selection_breakdown`, `selection_details_by_source_frame`,
   `analysis_metrics`, `selection_window`, `analysis_clip`,
   `analysis_selection_domain`, and `full_window_retry_override`, and migrate every
   hit. Known sites: `test_phase_tasks_alignment.py` (6 `ctx.analysis_metrics =`
   assignments, ~481, ~535, ~587, …, and 4 domain-field reads), `test_phase_tasks.py`
   (about 24 `ctx.selection_window`/`ctx.analysis_clip` writes),
   `test_phase_output_integration.py` (8), `test_phase_tasks_outputs.py`,
   `test_phases.py`, `test_phase_post_render_outputs.py` (~462–463),
   `test_execution_phase_plan.py` (~206–264, ~389), `test_phase_alignment_contract.py`
   (~449, `ExecutionState(selected_frames=...)`), `test_preparation_source_selection.py`
   and its `_fastest_source`/`_fps` siblings, `test_preparation_active_rect.py` (~186,
   ~250, ~314), `test_preparation_cache.py` (~82), and `execute_run_helpers.py`
   (~200).
5. Delete the removed fields and slice assignments.
6. Docs: `docs/current-architecture.md` § Runtime Flow (selection ownership,
   execution-time reads), § Shared caches (single required-read owner, two lifecycle
   reads), and the CLI contract § Run-Only Full-Window Selection Recovery only if
   wording references reason strings.

**Tests.**
- CQ6: migrate `test_phase_tasks.py` (~385, ~430) direct constructions to pass
  `kind=`; add: rewording a qualifying reason keeps consent/retry; an `UNCLASSIFIED`
  error carrying an old eligible string gets no offer; each producer sets its kind;
  `to_dict()` output for errors raised by real producers (not hand-constructed) is
  unchanged by `kind`. The existing CLI JSON tests (`tests/cli/test_run_json_errors.py`
  ~372/~413) construct `ExclusionRecoverySelectionError` directly, so they are kept
  but are not the producer proof.
- CQ9: byte-identical cache keys and equal v8 metadata, pre- versus post-migration,
  for absent range, explicit full range, absent FPS, explicit FPS equal to source FPS,
  absent source path. Capture expected values from the pre-migration code as literal
  fixtures in the same PR (not by calling the new code), made machine-independent:
  `compute_cache_key` hashes absolute paths, file size and mtime (`cache_io.py`
  ~75–83) and `media_runtime_identity("analysis")` (`metric_identity.py` ~76), whose
  profile varies by deployment and OS (`vs/runtime_contract.py` ~121–136). So pin the
  media-runtime profile, use relative paths under a `chdir` to `tmp_path`, fix mtimes
  with `os.utime`, and also capture the pure `_metric_cache_request_token` strings as
  literals. Retain
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
  the duplicated peak rule (`tonemap_libplacebo.py` ~67–70 and `tonemap_fallback.py`
  ~33–35). Freeze `TonemapSettings`: no mutation exists in `src`, `tests`, or `tools`
  (verified during review), and freezing also protects the shared preset instances
  returned by `get_preset_settings`. The `"configured"` peak origin is reachable only
  through `TonemapSettings.source_peak`, which no config field sets today; keep it so
  the record stays truthful if a caller supplies one.
- Every caller of `apply_tonemap` migrates in the same commit:
  `render/prepare.py`; `tools/docker_runtime_smoke.py` (~447–457, run by
  `verify_docker_integration.sh`); `tools/windows_portable/runtime_smoke.py`
  (`prove_apply_tonemap_frame` ~330–354, run inside the bundle build); tests
  `tests/vs/test_integration.py` (~69–73, ~112), `tests/vs/test_tonemap.py`,
  `tests/vs/test_tonemap_apply.py` (imports and calls it directly, about 20
  references), and `tests/render/test_tonemap_wiring.py` (~182, patches it); and the
  lazy export in `vs/__init__.py` (~38, ~60). The two runtime smokes should also
  assert the applied implementation they expect (libplacebo when usable), which turns
  the smoke into evidence for CQ11. `tests/windows_portable/test_windows_portable_build_scripts.py`
  (~364–501, ~748) asserts on `runtime_smoke.py` source text; update only what the
  edit invalidates (coordinate with P1/P2, §6.1).
- The fallback has its own truthful identity
  (`frame_compare_peak_scaled_rational_v1`); it is not labeled `REINHARD`.
- Per-clip flow: `prepare._apply_vs_tonemap_and_labeling` →
  `PreparedRenderSource.tonemap: AppliedTonemap | None` →
  `RenderedClipFacts.tonemap` → `OverlayConfig.tonemap` (diagnostic overlay text e.g.
  `Tonemap: fallback (peak-scaled) → 203 nits`; libplacebo text unchanged) →
  orchestration `ClipInfo.tonemap` → payload per-clip presentation.
- Shared summary: delete `ReportRenderingInfo.tonemap_settings` and the mixed-settings
  `ValueError`. `build_rendering_payload(info)` (`payload.py` ~439) gains the per-clip
  applied facts as an explicit argument. It derives `shared` from the
  **run-level transform identity** only: implementation, algorithm, and effective
  controls. The per-clip resolved source peak and the fallback cause are excluded from
  `shared`, because production resolves the peak per clip from that clip's MaxCLL
  (or 1000) and two ordinary HDR sources would otherwise never share a summary; each
  clip's presentation shows its own resolved peak. `shared` is null only when
  implementations, algorithms, or effective controls differ across tonemapped clips.
- Fallback policy (decision D3a, accepted): keep the permitted runtime
  fallback, disclose it per clip, and add one `RunWarning("render", …)` naming the
  clips that fell back and the cause class. Preserve fatal configuration/signature
  errors, source-prop precedence, range-expansion restrictions, cancellation
  admission, and native-review preview defaults.
- CLI pre-run preview keeps showing requested settings (a plan). Applied facts appear
  in overlay, report, and the warning.

**Serialized compatibility and identity (decision D3b, accepted).** Bump
report payload `REPORT_VERSION` (`payload.py` ~29) from `1.2` to `1.3`:
- `clips[].presentation`: `{state, tonemap}` where `tonemap` is `{implementation,
  algorithm, target_nits, source_peak_nits, source_peak_origin, effective_controls,
  fallback_cause} | null`. The 1.2 flat `presentation.tone_curve` and
  `presentation.target_nits` fields (`_presentation_payload` ~595–602), which carried
  requested values, are removed.
- `rendering.tonemap`: `{ran: bool, requested: settings | null, shared: {implementation,
  algorithm, effective_controls} | null}` — `shared` is the run-level projection, never
  the full per-clip transform, so it contains no resolved peak and no fallback cause.
  This replaces 1.2's `{applied: bool, settings}`: `settings` presented requested
  values as effective, and a boolean named `applied` beside applied facts is ambiguous.
- Identity: `build_report_id` (`payload.py` ~497–523) hashes the identity clips and
  the whole `rendering` dict, so the exclusions must be implemented in both
  projections. `build_report_identity_clips` (~459–471) drops `display` (as today)
  and `presentation.tonemap.fallback_cause`; a new rendering identity projection
  drops `rendering.tonemap.requested`. `shared` already excludes the cause. Identity
  therefore covers implementation, algorithm, effective controls, and per-clip
  resolved peak, so two runs with identical output via different failure causes
  share identity.
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
  `test_report_payload_v12.py`. Payload fixtures that encode `1.2` or tonemap fields
  include `tests/services/test_report.py` (~226, ~473), `inspector_harness.js`,
  `viewer_state_harness.js`, `review_state_harness.js`, and
  `review_controller_harness.js`; about 20 test files reference `tonemap_settings`.
  Make the first migration step a grep (`'1\.2'`, `payload_version`, `tonemap_settings`,
  `tone_curve`, `"settings"` under `rendering`) across `src/`, `tests/`, `tools/`, and
  `docs/`, and migrate every hit or record why it stays.

**Chosen design (CQ12).** Render geometry consumes resolved facts only:
- `SourceGeometry` takes a required active rectangle plus canonical
  `ActivePictureProvenance`; `RenderGeometryPlan` carries canonical provenance.
- Delete `ActiveRectDetectionMode`, the `RenderGeometryOptions.active_rect_detection`
  field and its validation (`_validate_options` ~240–243; the user-facing config field
  `screenshots.active_rect_detection` in `schema_models.py` ~211 is the orchestration
  policy input and stays), `_resolve_active_rects`,
  `_dimension_derived_active_rects`, `_mod_safe_contained_vertical_rect`,
  `_aspect_ratio_derived_active_rects`, `_select_aspect_ratio_candidate`,
  `_aspect_ratio_candidates`, `_aspect_candidate_support_count`, `_rect_ratio`,
  `_ratio_matches`, `_ratio_relative_delta`, `_AspectCandidate`, the three
  `ASPECT_RATIO_*` constants, `ActiveRectSource`/`ProvidedActiveRectSource`, both
  provenance converters (~34–71); replace `_is_safe_active_rect`'s silent full-frame
  fallback with a `ValueError`. The request contract alone does not guarantee this:
  `validate_batch_requests` checks the active picture against
  `request.source_resolution` (`expansion.py` ~79–84), while geometry uses the prepared
  `source_dimensions` when positive (~221–226). Add a typed expansion check that the
  active picture lies within the prepared dimensions (or that the two resolutions
  match) before planning geometry.
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
disclosure, identity facts, fallback disclosure, and rewording “resolved tonemap
settings when tonemapping ran” at ~1026 to the shared applied transform plus per-clip
peaks), `docs/current-architecture.md`
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
  but not between fallback causes; two HDR clips with different MaxCLL through the
  same implementation → `shared` present and per-clip peaks shown; JS review state
  rejects 1.2 documents in a 1.3 report; payload 1.3 shape tests (no flat
  `presentation.tone_curve`/`target_nits`, no `rendering.tonemap.settings`).
- CQ12 mapping before retiring render inference tests: axis cases
  (`test_geometry.py` ~240–341) → `tests/orchestration/test_active_rect.py::test_dimension_detection[...]`;
  the invalid-rect cases (~135, ~148) become render tests asserting the new
  `ValueError` and the typed expansion check (they test render's own input guard, not
  inference); ratio
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
    # __post_init__: result.facts.source_frame == selection.source_frame
    # (replaces the per-label loop in phase_render.py ~95-98, which already covers
    # VapourSynth and FFmpeg results; the check moves to the pairing point)
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
  passes `work_unit_ranges`). Its production-relevant obligations are ported to job
  form: lowest-index failure precedence, all-or-serial FFmpeg batching per job (a job
  is batched only when every request is compatible, `orchestrator.py` ~109–111, using
  `is_ffmpeg_batch_compatible`), partial progress and admission, and SIGINT admission.
  The 13 ungrouped tests in `tests/render/test_orchestrator.py` are ported where
  they prove one of those obligations (for example
  `…_mixes_indivisible_ffmpeg_groups_and_singletons`, ~765–815, whose three clips
  each batch uniformly, ports directly to one job per clip). A test that splits one
  unit into several FFmpeg groups
  (`test_render_batch_sequential_splits_incompatible_ffmpeg_requests`) exercises
  behavior production never runs and is rewritten as an all-or-serial case or retired
  with that reason recorded. The ordered-prefix progress (`_record_ready_progress`,
  `_render_description`, “Rendering” label) exists only on that path; production uses
  count-only `advance` under a lock, so deleting it removes no product behavior. Its
  only input, `RenderRequest.progress_label` and `ScreenshotBatchRequest.progress_label`
  (`render/types.py` ~128, ~146; forwarded at `expansion.py` ~195) computed by
  `_render_progress_label(s)` in `phase_render.py` (~59, ~79, ~133–150), has no other
  reader and is deleted with it.
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
`phase_render.py` (~58, ~64, ~95–98; the picture-type warning stays), the
`progress_label` fields and `_render_progress_label(s)` helpers, `_render_description`,
`_record_ready_progress`, and the count/mapping re-checks in `phase_post_render.py`
(~328–344). The `not render.screenshots_by_label` emptiness test at
`phase_post_render.py` ~279 becomes an emptiness test over `render.clips`. Keep `ReportData`,
`_validate_report_cardinality`, and slow.pics count checks (separate input contracts).

**Caller migration (tests).** `tests/orchestration/phase_task_helpers.py`,
`test_phase_post_render_outputs.py`, `test_phase_output_integration.py`,
`test_phase_tasks_outputs.py`, `test_execute_run_*`, `test_overlay_frame_number.py`,
`test_ffmpeg_overlay_application.py`, `test_phase_alignment_contract.py`,
`test_execution_phase_plan.py`, `tests/services/test_slowpics_upload_plan.py`,
`tests/render/test_orchestrator.py` (13 ungrouped tests, handled as above),
`tests/render/test_orchestrator_batch_screenshots.py`, `tests/render/test_expansion.py`,
`tests/render/test_expansion_geometry.py`, `tests/render/test_expansion_overlay.py`,
`tests/orchestration/test_overlay_selection_label_domain.py`,
`tests/integration/test_render_orchestrator.py`, `tests/integration/test_render_pipeline.py`
(~98, ~110), `tests/orchestration/test_execute_run_lifecycle.py` (~777).

**Tests.** Retain every “Rendering and orchestration” row in the report (including
`test_real_sigint_stops_frame_admission_within_150ms`,
`test_ffmpeg_batch_stop_reaps_child_without_publishing_partial_results`, and unequal
clip-count fact association). Add: a result whose `facts.source_frame` differs from
its selection is rejected at `RenderedScreenshot` (the default FFmpeg runner echoes
requested frame numbers, and injected runners never batch because
`encoders.py` ~118 requires `type(runner) is DefaultFFmpegRunner`, so this test
monkeypatches `DefaultFFmpegRunner.extract_frames`; it proves bookkeeping/order
protection, not decode correctness); job-index failure precedence; unresolved comparison membership
remains in render/report/slow.pics (`test_unresolved_comparison_remains_in_render_report_and_slowpics_membership`).

**Gates.** Full verification; Docker gate (render scheduling, native/FFmpeg execution).
Windows hosted verify at the package SHA (render path inside the portable runtime
smoke) is an acceptance requirement.

**Compatibility.** No serialized change (payload, run record, screenshot names).
Internal APIs change atomically.

**Rollback.** Revert P9 as a unit.

**Exit criteria.** Clip/frame structure carried end to end; no label-range plumbing or
result-by-label reconstruction; one cardinality/identity check where results are
paired with selections; ordering, failure, cancellation, and native-fact contracts proved by
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
(existing status, intended outcome). Run success JSON is unchanged; `history list` and
`history open` JSON for such runs now show `status: completed_with_warnings`, a
`warning_count` of 1, and the warning in `warning_summaries` (intended; no schema
change). Exit codes are unaffected.

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
- Two support modules, neither importing VapourSynth:
  `tests/integration/alignment_u4_media_recipes.py` (constants, graph builders,
  writers ~74–441, `RECIPES: Mapping[str, MediaRecipe(writer, requires)]`, `PAIRS`) —
  the only keyed source — and `tests/integration/alignment_u4_media_store.py`
  (`open_u4_media(tmp_root, *, cache_root, full_matrix, ffmpeg_version=…,
  recipes=RECIPES)` yielding a lazy `U4MediaStore` with `pair(name)`,
  `path(recipe)`, `materialize_all()`, `stats`). Store edits therefore do not
  invalidate media. Pair selection from `_align_pair` (~659–663), `_phase_context`
  (~776–778), and `_configured_prep_alignment` (~1105) moves into `PAIRS`, preserving
  `_align_pair`'s multipath special case; `_configured_prep_alignment` has no
  multipath case and its current callers pass only scenario names and `insert-300`, so
  merging is behavior-preserving (re-check callers at implementation).
- Key: `sha256(b"u4-media-v1\0" + recipes-module source + b"\0" + ffmpeg -version)`.
  Recipe parameters are declared data inside that module; per-recipe digests are not
  added unless measurements show frequent recipe edits.
- Demand generation under the session lock: generate a recipe on first access after
  its `requires` (`retimed-25` → `reference`; NTSC variants → NTSC reference;
  `retimed-insert` stages its own insert); publish each file by temp file +
  `os.replace` inside the key directory; file existence means complete; on acquire
  prune sibling keys, `.tmp-*` directories, and dot-prefixed temp files **except
  `.verifier.lock`** (deleting a held lock file breaks mutual exclusion on POSIX);
  symlink each
  materialized file into the session root (indexes stay outside the cache). Cache
  disabled → lazy generation in tmp.
- Full matrix: `FRAME_COMPARE_U4_MEDIA_FULL=1` calls `materialize_all()` up front;
  `tools/verify_docker_integration.sh` adds `-e FRAME_COMPARE_U4_MEDIA_FULL=1` to
  `docker_env_args` (~150–158) only when no `--pytest-path` was given (a host export
  would not reach the container), so the full gate (which CI runs with `--no-cache`
  and no `--pytest-path`) still builds every recipe. Update
  `tests/workflows/test_docker_integration_contract.py` for the new argument. Generator directory name stays
  `test_alignment_u4_acceptance` so the first run prunes the old key.
- Lock-overlap test moves to `tests/integration/test_alignment_u4_media_cache.py` with
  injected fake version reader and recipes (runs without VapourSynth, no xdist group).
  The acceptance module keeps its xdist group.

**Tests.** Key stable under test-module and store-module edits and changed by
recipes-module edits;
demand generation builds only requested recipes plus prerequisites; full-matrix
completeness; pruning isolation; no partial file after a writer exception; lock overlap.

**Measurements (record before claiming a speedup)** in
`tests/integration/NOTES-u4-media-preparation.md` (style of
`NOTES-u4-video-check-cost.md`). Under the verifier, U4 runs inside an xdist worker,
so a controller-side `pytest_terminal_summary` hook cannot see the store's in-memory
stats: the store writes its stats as JSON (key, created and reused recipe names,
per-recipe seconds) under `FRAME_COMPARE_E2E_ARTIFACTS` when that variable is set. The
verifier accepts only `--pytest-path`, so focused rows use a direct command in the
existing notes style, for example
`docker compose run --rm frame-compare-test -lc 'export FRAME_COMPARE_TEST_MEDIA_CACHE=/workspace/generated/test-media-cache FRAME_COMPARE_E2E_ARTIFACTS=/workspace/generated/e2e/u4-measure …; pytest -q tests/integration/test_alignment_u4_acceptance.py -k replacement-4 --durations=0'`,
clearing `generated/test-media-cache/test_alignment_u4_acceptance` first for cold
rows. Rows:

| Run | Expected files created |
| --- | --- |
| Baseline cold, focused `-k replacement-4` | 37 |
| New cold, focused | 2 (record actual) |
| Warm after assertion-only edit (baseline / new) | 37 / 0 |
| After a real recipe edit, focused / full | 2 / 37 |
| Cold full gate (duration comparable to baseline) | 37 |

**Docs.** Runbook (~317–325) and `CONTRIBUTING.md` (~159–164): key = exact
`alignment_u4_media_recipes.py` source + complete `ffmpeg -version`; assertion-only and
store-only edits keep the cache;
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
| P2 | ruff/pyright; Python vectors; release-contract tests | — | — | — | — | **Required** (PS5.1 + PS7 updater E2E; PS5.1 bundle install/uninstall; runbook steps 5–6; signing or documented-only) | — |
| P3 | pyright/ruff for bridge | — | **Required** | **Required** | — | — | — |
| P4 | Logic; `tests/test_cli_contract_docs.py`; strict docs build (after P0 step 0) | **Required** | — | — | — | — | — |
| P5 | Logic | **Required** | — | — | **Required** (regression) | **Required** (shim doctor selection) | — |
| P6 | Logic; `tests/vsview` panel/contract suites must actually run (Qt/EGL available) | **Required** | — | — | **Required** (U4 phase/cache matrix) | — | — |
| P7 | Logic, lint-imports | **Required** | — | — | **Required** | — | — |
| P8 | Logic, lint-imports | **Required** | **Required** (payload consumers) | **Required** | **Required** (+ pixel proof if graph changes) | **Required** (hosted verify; `vs/` changed) | — |
| P9 | Logic, lint-imports | **Required** | — | — | **Required** | **Required** (hosted verify; render path) | — |
| P10 | Logic | **Required** | — | — | — | — | — |
| P11 | ruff/pyright; `tests/workflows/test_docker_integration_contract.py` and `tests/workflows/test_onboarding_docs.py` (verifier script edited) | focused cache tests | — | — | **Required** + measurements | — | — |

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
| Run warnings / record status | P8, P10 | Fallback warning; policy warning recorded | Records may become `completed_with_warnings` (existing status); `history list/open` JSON shows the status, count, and summary; run success JSON and exit codes unchanged | none |
| Metric cache v8 | P4, P7 | Decode recovery; request intact | Bytes and keys byte-identical (tested) | none |
| Alignment reuse cache v2 | P6 | Candidate preparation | Bytes unchanged (tested) | none |
| VSView result contract v1 | P4, P6 | Decode recovery; services refactor | Unchanged wire format | none |
| Run records / history | P4 | Recursion isolation | Unchanged format | none |
| Viewer storage | P3 | Derived offset | Same key/schema; no neutral writes on visit | none |
| CLI `doctor` | P5 | `--root/--config`; no upward search | New options; JSON unchanged | none |
| CLI preview | P5 | Values from effective config | `input` row shows resolved path | none |
| `--diagnose-paths` JSON / `--write-config` destination | P5 | Environment variables in `--config` expanded once | Shows/writes the expanded path instead of the raw argument | none |
| Run timings (`phase_timings["preflight"]`, summary setup row, run record) | P5 | Acquisition moves before `execute_prep` | Preflight timing shrinks by the config-read cost | none |
| Config validation | P4 | `inf` timeouts and parser-limit TOML rejected | Typed config errors | none |
| Selection error JSON (`FC-4012`) | P7 | Internal `kind` added | `kind` not serialized; message/details byte-identical (tested) | none |
| `RunRequest` / internal APIs | P5–P9 | Reshaped | Internal; atomic caller migration | none |
| Windows builder | P1 | Refuses occupied output; builds at the final path | Maintainers delete disposable output; CI requirements fingerprint unchanged (same build path) | none |
| Windows source installer | P1 | Timestamped bundle folder; user-data policy | Existing pointer remains valid; moved media makes path-keyed caches recompute once | none |
| Windows updater | P2 | Grammar; journaled transaction; `backup.json` beside `compatibility.json` | Manifest fields unchanged; stable `min` stays numeric for old updaters; RC installs need one full reinstall; same-line downgrades still admitted | none |
| Release-contract regexes | P2 | `re.ASCII` added | No valid version changes meaning | none |
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

### Maintainer decisions

Resolved on 2026-10-15: the maintainer accepted the recommended default for every
item below. The packages above already specify these choices; changing one later
requires updating the affected package before its implementation merges.

| ID | Question | Options and consequences | Decision (accepted recommendation) |
| --- | --- | --- | --- |
| **D1** (CQ15, P1) | When a source reinstall finds user data (non-empty `config\`, `comparison_videos\`, or `generated\`) in the previous active bundle and no `-UserData` choice was given, what happens? | **Move** (rename the non-empty folders into the new bundle on the same volume, all-or-nothing, reversed if activation fails, then activate): keeps the documented “rerun install.cmd” workflow; data follows the AppData state config's bundle-relative paths. **Refuse to activate** (build, verify, print instructions, exit non-zero): no automatic data handling, but every rerun needs a flag. **Leave**: activates while data stays invisible in the old folder. | **Move**, with `-UserData Leave` as opt-out. The builder's refusal of occupied output is independent of D1 and ships regardless. |
| **D2** (CQ16, P2) | Stable↔RC admission semantics | Allow RC→RC, RC→stable, stable→RC within one `major.minor` line (stable `min` admits its RCs) and keep today's admission of same-line downgrades vs. forbid stable→RC code updates (RC requires full bundle) and/or add a new downgrade refusal | Allow within the line and keep downgrade admission, as specified in P2 |
| **D3a** (CQ11, P8) | Unavailable requested tonemap: fail or disclosed fallback? | Keep fallback disclosed per clip + one run warning (current tested behavior, now truthful) vs. a new `color.tonemap_fallback = "allow" \| "refuse"` setting with a typed `FC-` error on any cause (schema, wizard, docs, doctor implications) | Keep disclosed fallback + warning; do not add a setting now |
| **D3b** (CQ11, P8) | Payload/identity compatibility | Bump to 1.3 with applied-fact identity (regenerated reports get new IDs; browser state starts fresh) vs. additive 1.2 fields (still changes IDs; misrepresents the contract) | Bump to 1.3 |
| **D4** (CQ18, P5) | Public `doctor` CLI change | Add `--root/--config`, shim injects for doctor, drop upward search (consistent with run) vs. keep upward search when `--root` is absent (two root policies) | Add options; match run's selection exactly |

Notes on the accepted choices: D1's builder refusal of occupied output is
independent of the user-data choice. D4 has two parts: adding `--root/--config` with
shim injection is what lets CQ18 reuse run's selection owner, and dropping the upward
search keeps doctor's selection identical to run's.

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

- [x] Decisions D1–D4: the maintainer accepted the recommended defaults on
      2026-10-15 (D1 → P1; D2 → P2; D3a/D3b → P8; D4 → P5).
- [x] P0 step 0: review-report links fixed; strict docs build passed with no warnings
      (2026-10-15).
- [ ] P0: three public passages corrected; strict docs build passes.
- [ ] P1: no code removes an existing output root; failure cleanup removes only a
      directory the run reserved; failure leaves existing state byte-identical; CI
      requirements fingerprint unchanged; D1 policy implemented with reversal on
      activation failure; source-install tests isolate `LOCALAPPDATA`; Windows PS7
      fixtures and hosted verify recorded.
- [ ] P2: one version grammar owner across extraction/range/generator/bundle info/smoke;
      exact target check; `Restore-FromBackup` deleted; journaled transaction and
      interrupted-state repair used by apply and rollback; `backup.json` beside
      `compatibility.json`; PS5.1 and PS7 updater E2E, PS5.1 install/uninstall, and
      signed/documented-only status recorded.
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
      ownership/contract change listed in packages P1, P4, and P5–P9; runbook, README.txt,
      windows-portable guide, and CONTRIBUTING updated per P1, P2, P11.
- [ ] Final review against the report: no supported finding or CQ21 subpart open, no
      implicit caller migration or deletion, no temporary compatibility layer, CQ7/CQ14
      untouched, no runtime acceptance claimed without evidence.
- [ ] This plan's marker changed to `Status: Historical` with an outcome line.


## 14. Implementation dispatch and evidence ledger

Implementation authorized by the maintainer on 2026-10-15 in orchestrator chat
`01a13ec5-b5a2-7cc3-880c-8ce92c075fac`, host `local`, human turn
`01a13ec5-c10d-7540-aada-c7fcad5ea7df`, user message
`01a13ec5-c54a-70c1-b1be-2d525121bac8` (retrieved with `read_thread`). The human
explicitly authorizes implementation/review/verification children, assignments and
follow-ups, meaningful blocker/decision/completion callbacks to this orchestrator,
isolated worktrees from current task state, scoped local commits, and integration
under one Git owner. Children must retrieve this original human turn before callbacks
unless trusted human authorization is already in context. Retrieval failure means
final-report-only fallback; the parent retrieves on its next activation.

### Initial baseline and resources

- Actual checkout: `/Users/tristan/Software/frame-compare`, branch `v0.7.0`, clean
  HEAD `9fe932ede7ea333018e60c81720e29b60a089890`. No pre-existing implementation
  edits. No historical/default-branch reset or switch performed.
- Project resolved through `list_projects`:
  `local-5fa7d782ab3f3ef0c782bc2a261e2e12`, host `local`, matching this checkout.
- Current presets read from `.codex/agents/`: worker = `gpt-6.1-sol` / medium;
  worker_luna = `gpt-5.6-luna` / xhigh; reviewer = `gpt-6.1-sol` / high;
  deep_reviewer = `gpt-6.1-sol` / xhigh. Responsibility instructions travel in each
  assignment; role files do not establish child permissions.
- Observed capabilities: macOS arm64; uv 0.12.21; Python 3.13.16; Node 24.14.0;
  Docker daemon 29.8.2 responds; native Chrome exists; Qt/VSView import successfully;
  VapourSynth R81 imports but native `lsmas` and `placebo` are absent. No `pwsh` or
  `powershell` executable found. These are capability observations, not gate passes.
- Exclusive resources: orchestrator alone mutates integration checkout/index/branch
  and this plan; workers commit only in their own worktrees. Docker verifier/image/
  media-cache runs require a controller-issued lease (none granted initially).
  Browser profiles must be worktree-local; shared native/browser acceptance and full
  integrated gates run on stable inputs under a named owner. No child edits the
  canonical plan. Children own relevant product documentation only in package sections.
- P0 step 0 remains completed planning evidence; it is not new implementation work.

### Dispatch / acceptance state

| Package | Owner / role / chat | Base and integration | State / evidence / remaining acceptance |
| --- | --- | --- | --- |
| P1 | worker / medium; `01a13ec8-367e-7e43-9c36-7e30d3cf8baa` | worker `14b599a2` → integrated `21691a97` | Implemented/integrated; deep reviewer `01a13ed5-7e47-7ea0-9201-1f47b6a097f0` active; Windows acceptance open |
| P3 | worker / medium; `01a13ec8-7014-7c63-bcf2-3cc807db28a9` | worker `7ccdb965/986abc2e/149ef433` → integrated `8e32ee40/54e80bb6/983658b8` | Implemented/integrated/independently reviewed, no findings; final-source Node/report/22-browser proof passed; full Wave A composition pending |
| P4 | worker / medium; `01a13ec8-b5f3-75b0-82b7-2eb5989cc9c6` | worker `c2b62b05` → integrated `30515500` | Implemented/integrated/independently reviewed, no findings; focused + full native at `94efe8cd` passed; final-head gate pending |
| P10 | worker_luna / xhigh; `01a13ec8-eeb0-7822-a12f-b2a8265eb3f5` | worker `f0c67e62` → integrated `94efe8cd` | Implemented/integrated/independently reviewed, no findings; full native/static integration at `94efe8cd` passed; final-head gate pending |
| P0 | Reused worker / medium; `01a13ec8-b5f3-75b0-82b7-2eb5989cc9c6` | worker `260670cc` → integrated `23d2f59f` | Implemented/integrated/independently reviewed, no findings; 5 CLI-doc tests + strict docs passed; Wave A composition pending |
| P5 | worker / medium; `01a13ecf-7fe9-7c31-a0fd-3282824918c8` | `30515500`; worktree `9676` | Active; full acquisition/doctor scope; P10 shared-file ordering tracked |
| P6 | Reused worker / medium; `01a13ec8-b5f3-75b0-82b7-2eb5989cc9c6` | assigned current integrated `44a11213`; worktree `9bdf` | Active; complete CQ5/CQ21c/CQ2; reviewed P4 prerequisite retained; native/Docker gates deferred |
| P8 | Reused worker / medium; `01a13ec8-7014-7c63-bcf2-3cc807db28a9` | assigned current integrated `21691a97`; worktree `9bb4` | Active; full applied-fact/payload1.3/geometry migration; browser/Docker/native/platform gates deferred |
| P11 | worker / medium; `01a13ed0-043c-75f0-9554-afb21690373c` | `30515500`; worktree `a638` | Active; full recipe/store/cache + before/after measurements; exclusive Docker lease granted |
| P2 | Wave B after integrated, reviewed P1 prerequisite | — | Grammar/transaction scope pending; PS5.1/7/Windows/signing acceptance open |
| P7 | Wave B after integrated, reviewed P5/P10 (and P4/P6 shared changes) | — | Full CQ6/CQ9/CQ4 scope pending |
| P9 | Wave C after integrated, reviewed P7/P8/P10 | — | Complete structured-render migration pending |

Each wave requires independent integrated review, including cross-package composition.
No package is accepted from a completion callback alone. Final cumulative review and
all applicable stable-head gates remain pending. This section records implementation
progress without altering approved design, coverage, compatibility, or exclusions.


Dispatch identities confirmed with `list_threads` plus `read_thread` assignment
retrieval; all four worktree HEADs independently observed at
`9741fcc91eb5b28f1e8689971229b39a3876959a`. Worktree roots are
`/Users/tristan/.codex/worktrees/<id>/frame-compare`. All callback routes target the
orchestrator/host recorded above; human retrieval verification is required in each
child. Pending setup client IDs have been resolved; no pending ID is used for messaging.

First-batch resource lease: P3 exclusively owns real-browser execution with unique
owned temporary profiles. P4/P10 were instructed to defer full native suites (which
include browser tests) until lease transfer or integrated verification; focused
nonbrowser checks and static gates continue. No Docker lease is active. No package
implementation, independent review, or runtime acceptance is yet recorded.

Next activation: retrieve meaningful child callbacks/completion evidence; integrate
scoped commits under parent Git ownership; assign independent review to stable
package/batch inputs, including P1 deep review. Dispatch P0 and remaining Wave A
packages in practical batches while honoring shared-file ordering. Full Wave A
composition review is required before dependent work is accepted.


### P4 integration and second dispatch

- P4 worker completion: `c2b62b055669f26bf6dc1ce77b005277af3ec414`, based on
  `9741fcc91eb5b28f1e8689971229b39a3876959a`; 32 changed files, +444/-32.
  Parent verified commit range/file list and integrated cleanly as
  `3051550054fb19050b35c7743b9b4c780675262a`. No substantive orchestrator code review.
- Worker reports all P4 decoder-table owners, typed user/env/preset failures,
  wrong-shape enums, finite constraints on exactly four operation timeouts, and
  matching timeout doc paragraphs implemented; optional TMDB byte cap omitted.
- Actual worker evidence: explicit focused pytest selection covering utils,
  analysis/cache identity/serialization/acquisition, config, CLI JSON/imports,
  VSView result contract, alignment review/workflow, TMDB/history/overrides/reuse,
  probe/cache-only orchestration and CLI-doc contract: **724 passed, no skips**.
  Preset test-only narrowing assertion then rerun: **23 passed**. Pyright 0 errors/
  warnings; ruff + format clean (513 files); bandit gate clean; lint-imports 2 kept,
  0 broken; strict Zensical build clean; diff check/hooks passed. Full native suite
  deferred under resource coordination, explicitly open. P4 needs no Docker/GUI gate.
- Independent P4 reviewer: preset reviewer, `gpt-6.1-sol` / high, chat
  `01a13ece-fcf0-7da1-afb9-c63eb44a89a8`, worktree `cec8`, exact reviewed range
  `6c047405bfb1a73e6c8b5a68e3bccefa216c05f6` → `30515500`. Complete P4
  package/test/failure-policy coverage assigned read-only; findings not yet returned.
  Package review does not replace Wave A composition review.
- P0 assigned as a new scoped commit in the existing P4 worker/chat/context; no
  amendment of P4 permitted. Product-equivalent base differs only in parent ledger
  ancestry. P0 production source is unchanged by contract.
- P5 and P11 created from current integrated task state; actual HEADs observed at
  `30515500`; chat identities and full assignments confirmed through `read_thread`.
  Their original human authorization/callback references match the ledger above.
- P3 released the browser lease after observing **22 real Chrome browser cases
  passed, no skips**, including its new full transition probe. This is preliminary
  worker evidence; P3 final source identity/static closeout and independent review
  remain pending. No browser lease currently assigned; full integrated native gate
  will use stable source under a named owner.
- P11 exclusively owns task-repository Docker verifier/compose/image/media-cache
  execution until release, including unchanged-baseline measurement before extraction.
  No global pruning or unrelated-project resource changes authorized. P5 Docker
  and full-native gates remain pending resource/stable-input coordination.
- Pending children: P1, P3, P10, P0 (reused P4), P5, P11, P4 reviewer. No findings
  dispositions yet. Next useful trigger is a meaningful callback; no idle polling.


P0 callback received and integrated: worker `260670cc8d2c813f32af4d18df77760f915cbadd`
(range after unchanged P4 `c2b62b05`) cherry-picked cleanly to
`23d2f59ff539973f4be38f586a8b069a665ad322`; exactly two documentation files,
+13/-6. Worker observed 5 CLI-doc tests passed, strict Zensical build no issues,
diff check/hooks clean. No product/browser/Docker/native gate needed for P0.
P4 reviewer additionally assigned exact P0 range `e7e05b1d..23d2f59f` using committed
source, separate conclusions required. P0 implementation complete; independent review
and full Wave A composition acceptance pending. P4/P0 worker currently idle and reusable.


Resource correction from P3: the earlier browser release was premature. Final
undefined-selector draft clearing and test/readability edits invalidated the earlier
22-case pass for final-source acceptance. P3 retains/reclaims the exclusive browser
lease for a repeat at stable final source, using owned `.tmp/p3-browser-final`
profiles; its exit/final identity is pending. P10 reminded to defer full native
(which includes browser) and report focused/static completion without waiting on
that gate. Earlier 22-case pass remains evidence only for its earlier source.


### Independent P0/P4 conclusions and P3 integration

Reviewer `01a13ece-fcf0-7da1-afb9-c63eb44a89a8` verified original human authorization
and completed read-only reviews of P4 `6c047405..30515500` and P0
`e7e05b1d..23d2f59f`: **no actionable findings or design contradictions**. All P4
per-owner table policies, typed failures, decode-only catches/hooks, four finite
timeouts, two cache reads/no-compute failure, retained deterministic schemas/bytes
and documentation inspected; P0 prose checked against actual source/contract/anchors.
Reviewer ran 71 + 49 passing test executions across overlapping focused selections
(no skips, not 120 distinct tests), read-only using worker interpreter with reviewer
source on PYTHONPATH; diff checks clean. Worker 724/static/docs evidence reused, not
misrepresented as reviewer reruns. P4 full native gate open; P0 runtime acceptance
complete for its docs scope. Wave A composition and final cumulative review pending.

P6 full package assigned to reused P4/P0 worker, same worker model/medium reasoning,
after reviewed P4 integration. Start from then-current `44a11213` in isolated `9bdf`;
scoped conventional commits only, all nine steps/CQ5/CQ21c/CQ2 and retained authority
proof specified. P5 acquisition, P11 recipes, CQ7/CQ14 excluded; full-native/browser
and Docker deferred for stable input/resource coordination.

P3 final callback froze clean worker head `149ef433fdfdc661528087a0ce32962bb170e960`.
Parent verified three-commit range/file list and cleanly cherry-picked all three to
`8e32ee40`, `54e80bb6`, `983658b865ef479b9edfcdea66c2944379d13709`, from parent
`44a11213`; 20 files +3562/-3948. Relevant code unchanged by integration. Worker
reports full fixture ownership, named-runner/assertion consolidation and derived pair
state migration/deletions complete; no CQ7/CQ14/payload/storage drift. Actual final
source proof: 9 bridge invocations pass; 84 report service tests pass; **22 native
Chrome browser cases pass/no skips** after final edits, unique owned profiles cleaned.
Focused scenario/env selector and restored deliberate-failure/unknown-name proofs
recorded; ruff/format/pyright/diff clean. No native/media gate needed for P3.
Browser lease now released at final-source completion (supersedes premature release).
P3 independent full-package review assigned to reused reviewer/high, exact stable
range `44a11213..983658b8`, including every assertion migration/selection/persistence
obligation and exclusions. Not yet accepted from worker callback alone.


### P10/P1 integration, P8 dispatch and current leases

P10 worker froze `f0c67e62301da9d3da4ed21eb45953ea35f5d910`; parent verified
range/file list and cherry-picked cleanly to `94efe8cdd2abe86caa1136849d25122cd17d5e03`.
Five files +197/-3. Joined execute_run proof observes exactly one mismatch warning in
result, terminal and persisted completed_with_warnings record, preserves URL/title/
explicit association, rejects unexpected HTTP and keeps success JSON shape. Worker
reports focused publish/phase-plan/lifecycle/metadata/record/CLI-output selections and
ruff/format/pyright/bandit/import/diff checks passed. Full native not yet passed.
Independent reviewer/high `01a13ece-fcf0-7da1-afb9-c63eb44a89a8` additionally assigned
P10 exact `9c6d0ba7..94efe8cd` and bounded composition among P0/P3/P4/P10; complete
Wave A composition review still required later.

P10 worker now owns VERIFICATION ONLY at exact integrated `94efe8cd` in existing
`b49f`, source frozen/no fixes/commits. Canonical full native gate plus integrated
static/import/security checks assigned with explicit skip/runtime accounting.
Exclusive browser lease granted to this verifier after final P3 release; Docker
lease remains P11. Subsequent P1 integration does not change this run's source
identity; do not report it as final-head proof. Evidence/lease release pending.

P1 worker froze `14b599a20287dfb96fcb18daa10066a5e2b9c5eb` from `9741fcc9`.
Parent verified single-commit range/file list and integrated cleanly as
`21691a9782b09bb98cc0ee64a7f504de3c40f3cd` (architecture auto-merge; no technical
conflict). Thirteen files +859/-127. Worker reports all P1 builder reservation,
validation, source-install Move/Leave reversal, failure fixtures, provenance and
documentation scope complete. Actual Windows-portable pytest on macOS: **122 passed,
126 skipped**; no pwsh/powershell means NO PowerShell syntax/execution/Windows
filesystem acceptance. Pyright 0/0, ruff/format, strict docs, diff/hooks passed.
Required Windows PS7 fixtures, real mounted-volume/manual populated Move/Leave/bad-
manifest rerun + shim observation, same-final-path double-build fingerprint,
runbook bundle steps3–4 and maintainer-hosted verify remain OPEN.

Independent P1 deep reviewer/xhigh `01a13ed5-7e47-7ea0-9201-1f47b6a097f0`, worktree
`4a89`, assigned exact `94efe8cd..21691a97` complete high-consequence transaction,
tests/docs/provenance scope, including bounded integration seams; reviewed findings
pending. Actual child/assignment confirmed via read_thread. Preset filename is
`.codex/agents/deep-reviewer.toml` (alias deep_reviewer); worker_luna filename is
`.codex/agents/worker-luna.toml`. Handoff spelling corrected; originally resolved
models/reasoning/responsibility text from preset glob were correct and unchanged.

P8 full package assigned to reused P3 worker/medium `01a13ec8-7014-7c63-bcf2-3cc807db28a9`
from current integrated `21691a97`, complete CQ11/CQ12/CQ22 disclosure/geometry scope,
D3a/D3b preserved. No P9/CQ7/CQ14 graph/range/resampling expansion; P5 prepare.py
boundary and P1 runtime-smoke-test overlap explicitly coordinated. Full native,
real-browser, Docker and Windows acceptance remain required; P10/P11 resource leases
prevent premature concurrent gate execution. Worker owns focused nonbrowser proof.

P11 meaningful baseline callback: exact unchanged U4 acceptance source SHA256
`d5a6cde1a9e3e98150b79ce428e5c7b235632f39cf0c423caba868f5f45b27a8`, baseline
focused run generating all37 assets; separate recipe/store implementation and seven
VS-free tests (including distinct-process lock overlap) reported passing. Dedicated
compose project `frame-compare-p11-a638`, image `frame-compare:p11-a638-test`, worktree
artifacts/cache; no global pruning. Docker lease retained for all approved baseline/
post-change measurements and full canonical gate. This is progress, not completion.

Pending active work: P5/P6/P8/P11 implementation, P3/P10 reviewer, P1 deep reviewer,
P10 integrated verifier. P1 worker idle/reusable for review fixes and eventual P2
only after reviewed prerequisite. No P2/P7/P9 dispatch yet; no pending child setup IDs.


### Independent P3/P10 review and partial Wave A composition

Reviewer/high `01a13ece-fcf0-7da1-afb9-c63eb44a89a8` completed P3 exact range
`44a112137684f1c5d878d6ae22d51f1083a19149..983658b865ef479b9edfcdea66c2944379d13709`
and P10 exact range
`9c6d0ba717a7cc7c6e39b45894dd1aa4072d6294..94efe8cdd2abe86caa1136849d25122cd17d5e03`:
**no actionable findings or decisions required**. All20 P3 files and all5 P10 files
inspected against complete approved package obligations.

P3 reviewer compared prior/new JS assertions and traced every plan-named sole-Python
observation before mirror deletion; reviewed fixture document closure, seven harness
runner contracts, map-only offset authority/all selection and persistence cases,
retained loader proof/exclusions, browser probe and architecture. Reviewer ran9 bridge
invocations/no skips at exact983658b8, plus in-memory runner unknown-name/async-order/
named-stack/continue-and-summary failure controls, and diff check. Reviewer verified
worker149ef433 vs integrated983658b8 have no differences in relevant report assets,
browser, harness/runner or report tests, validating reuse of worker84 report passes,
22 actual Chrome passes/no skips and static evidence. No browser/Docker reviewer run;
no P3 runtime gap identified. This does not establish final Wave A composition.

P10 reviewer traced actual producer/execution/application/warning/result/summary/
persistence/JSON owners and all keyword constructor callers; joined transport proof
retains URL/title/explicit association and one warning in result/record/terminal,
post-action warning independence, accepted publish-failure limitation and success
JSON omission. Existing docs accurate. Reviewer ran61 passing/no-skip lifecycle,
phase-plan, metadata and phase-post-render tests at exact94efe8cd; diff check clean.
Full native acceptance remains pending separate verifier.

Bounded composition at94efe8cd covers P0/P3/P4/P10: P0 prose agrees, P3 schema/test
infrastructure unchanged by decode/warning integration, P4 production files identical
to reviewed30515500, P10 joined proof exercises P4 persisted record reader with new
warning metadata. No interaction findings. Explicit uncovered Wave A union:
P1/P5/P6/P8/P11 and final combined interactions; delegate full Wave A review later.
Reviewer remained clean/read-only at94efe8cd, now idle/reusable for focused rechecks
or later wave work. Pending callbacks: P1 deep review; P5/P6/P8/P11 implementation;
P10 stable-input native verifier. No useful independent integration or dispatch is
ready until those prerequisites/results arrive; no idle polling.


### Stable integrated native verification at94efe8cd

Verifier worker_luna/xhigh `01a13ec8-eeb0-7822-a12f-b2a8265eb3f5` completed assigned
verification-only work on exact
`94efe8cdd2abe86caa1136849d25122cd17d5e03` (P0/P3/P4/P10; before P1 integration).
Clean permitted detached switch in isolated b49f; no source/test/docs/plan edits or
commits. Original human authorization re-retrieved before callback.

Actual canonical command:
`REPORT_BROWSER="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" uv run --no-sync pytest -q -n4 --dist loadgroup`.
Verifier reports completed100%, collection3611, explicit skipped105, therefore
**3506 passed,105 skipped,0 failures/xfails**. Chrome coverage actually ran, with no
browser skips. Skip breakdown:5 absent native plugins (4lsmas,1placebo),6 opt-in media
E2E,3 opt-in continuous-alignment resource,2 opt-in live slow.pics,89 Windows/
PowerShell/CMD semantics. Serial windows_portable confirmation also passed with same
89 platform skips (this source predates P1's additional preservation fixtures).
Neither those skips nor native suite pass establish Docker/media/Windows acceptance.

Integrated pyright0/0/0, ruff/check format513, bandit0 medium/high, lint-imports2 kept
(183files/791dependencies) and diff check all passed at same exact SHA. No Docker
used; P11 lease retained. Browser owned-profile/process cleanup checked with no
remaining matching Chrome processes; browser lease RELEASED. Verifier now idle and
reusable for later source-bound integrated gates.

This closes P4/P10 full-native requirements at the reviewed relevant source and
supports P0/P3/P4/P10 composition; it is not final-head verification for P1/P5/P6/P8/
P11 or later waves. Reuse while relevant source/environment remain unchanged; rerun
applicable invalidated gates on final stable integrated inputs. Pending callbacks:
P1 deep review, P5/P6/P8/P11 implementation. No current browser owner; P11 retains
exclusive Docker ownership. P2/P7/P9 remain dependency-gated and undispatched.
