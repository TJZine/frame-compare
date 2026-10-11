---
search:
  exclude: true
---

# Draft remediation packages

**Nothing in this file is approved.** This is a planning-only proposal for the calibrated CONFIRMED/LIKELY findings in REPORT.md at `58e50a6d48c0004b63f60b9b3ba53c1ac4b31537`. No implementation was dispatched or performed. Hypotheses, unsettled intent and insufficient-data claims remain parked. Future implementation must reread current instructions/source, resolve decisions and obtain the user's package authorization.

Preserve runtime-free help/version, typed sanitized errors, machine-clean JSON, explicit persistence/atomicity, source/frame authority, valid zero, original evidence/provenance, injected-resource ownership, isolated webhook transport and separate native/Docker/Windows proof. Do not sync/lock/update dependencies, deploy, sign, release or maintain workflow as a side effect of a package. No test-count target, universal E2E requirement or blanket deletion of boundary checks applies.

## Package overview

| Package | Findings | Owner / intended correction | Integration proof |
| --- | --- | --- | --- |
| P1 | F-001 | Run cancellation, phase admission/commit and synchronous resource stop/drain | Real first-SIGINT regression; native + Docker render/media; physical native/Windows acceptance |
| P2 | F-002 | Tonemap capability child import isolation | Hostile cwd/env controls + actual capability; affected managed-runtime/HDR proof |
| P3 | F-003–005 | User-config decode/path/finite boundary failures | Installed CLI JSON/human + finite window tests; static/native |
| P4 | F-006 | Persisted numeric conversion recovery | Mixed history and actual cache-consumer dispositions; native + affected Docker M3 |
| P5 | F-007 | Verifier-owned output and artifact retention | Normal/symlink sentinels + canonical Docker gate |
| P6 | F-008–009 | Docker context exclusions and actual-input CI selection | Deliberate context sentinel/selection controls + canonical Docker gate; hosted selection later |
| P7 | F-010 | Explicit UTF-8 fallback state readers | Windows5.1 ANSI/non-ASCII CLI/update proof |
| P8 | F-011 | Source PowerShell prerequisite or actual5.1 support | D-01 first; real root CMD source install/refusal |
| P9 | F-012 | Blink intent vs gesture suspension | State/timer siblings + actual browser gesture/reduced-motion proof |
| P10 | F-013 | Review candidate as preview/apply policy owner | Delta-preview equality, import safety/quota rollback, browser File integration |
| P11 | F-014 | Warning semantic status independent of user label | Neutral/adversarial label and genuine skip through human result output |
| P12 | F-015 | Truthful short alignment wording | Both summary owners, manual zero/nonzero/computed/reuse/review controls |
| P13 | F-016 | Delete orphan color policy after consumer audit | Active conversion/import proof, API regeneration/check; native + affected pixel proof |
| P14 | F-017–020 | Reconcile canonical user-documentation statements | CLI/formatter/recipe evidence and historical tier reconciliation; docs guards + strict site |
| P15 | F-021 | Portable terminal behavior assertion | Deep/short path and narrow/wide controlled output; once-only native integration |

## Packages

### P1 — Observe cancellation before admission and durable success

Goal: first Ctrl+C stops further phase/unit admission and prevents completed/review/cache commits while retaining owned cleanup. Primary files: `runner.py`, `orchestration/execution.py`, `phases.py`, `coordinator.py`, `render/batch/orchestrator.py`, `vsview/adapter.py`, and relevant alignment review/persistence boundary callers.

Scope includes the actual sync→async runner signal contract, cooperative stop propagation into blocking owners, output/phase/commit checkpoints, interruption outcome and deterministic in-flight drain. Out of scope: generalized process framework, abandoning native work through bare to_thread, altering alignment authority, new publishing features or promises to forcibly kill in-process native threads.

Approach: design one run-owned cancellation representation and admission/commit policy; resource owners implement their own stop/drain. Compare cooperative scheduler + bounded wait with an appropriate worker-isolation alternative only if actual native inability to stop requires it. Serialize state application/record commit after cancellation acknowledgement. Preserve earliest real-failure precedence and injected clients/cores. Delete superseded cancellation branches when callers migrate; no compatibility adapter without a consumer/removal condition.

Verification: reuse P-02's real runner/SIGINT/coordinator writer boundary, assert later units/phases absent, failed/interrupted reserved record and owned child drain. Preserve audio/webhook repeated cancellation and VSView direct-reaping controls as distinct obligations. Integration owner runs static/full native once after integration and the canonical Docker media gate for renderer/execution changes. Physical single/repeated Ctrl+C during actual VS/FFmpeg/VSView on native and Windows remains required acceptance (O-09). Rollback: revert the package coherently; inspect reserved records/artifacts without deleting unrelated output. Risk: stopping admission without draining resources or recording failure can trade one defect for another. Dependencies: none; coordinate file ownership with P12. Suggested owner: capable implementation worker, independent reviewer for signal/lifetime design.

### P2 — Isolate the tonemap capability interpreter

Goal: capability probing imports installed runtime, regardless of workspace Python files or inherited injection variables. Files/symbols: `vs/tonemap_runtime.py` probe launch and existing safe-path/environment policy locations, including VSView as reference only.

Scope: child cwd/import isolation, required runtime/plugin environment and bounded launch. Out of scope: dependency refresh, tonemap algorithm change, upward vs→vsview dependency or global environment stripping that breaks native loading. Use an owner-local policy or existing suitable shared utility; avoid a process framework.

Proof: real cwd marker and inherited-PYTHONPATH negative cases must remain unexecuted; real installed plugin capability unchanged. Retain fallback/error controls. Static/native gates plus actual affected Docker HDR/capability proof after integration; native/portable runtime acceptance where policy differs. Rollback is an atomic package revert; no persistent format migration. Risk: -I/environment changes can hide required embedded/native paths. No dependency; files are disjoint from P1/P3 except any deliberately shared process utility, which requires one owner.

### P3 — Translate invalid user input at configuration boundaries

Goal: invalid UTF-8, filesystem-unrepresentable paths and nonfinite lead/trail exclusions fail as typed user-config errors before reservation/runtime. Files: `config/schema_sources.py`, `loader.py`, `presets.py`, `schema_models.py`, preflight path normalization and existing config/path errors; CLI consumers only where a typed boundary needs wiring.

Scope: owner-level decoding/normalization/finite constraints with useful sanitized diagnostics. Out of scope: global Exception catch, forcing external input/generated paths inside root, changing valid finite defaults, preset-symlink policy before D-02, or fixing every accepted infinity field without tracing its semantics. Preserve stronger wizard redaction and selected-config containment.

Proof: installed console dry-run JSON/human and preset apply with invalid bytes; all three NUL fields/environment expansion; config bytes unchanged on failure; TOML/env exclusions rejected before work; finite/short/empty window behavior. Static/native after integration. Real-media run is not needed to establish schema rejection; if preflight/selection contract changes more broadly, use affected Docker E2E. Rollback: revert validation/translation together; no persisted migration. Risk: broad ValueError conversion could conceal invariant bugs. No dependency; one config owner coordinates all three mechanisms rather than scattering CLI catches.

### P4 — Normalize persisted numeric conversion into recovery policy

Goal: one malformed numeric record/cache does not escape its parser and defeat sibling/history/cache recovery. Files: `services/run_result_record.py`, `analysis/cache_io.py`, actual acquisition/history consumers and existing helpers/tests.

Scope: safe conversion at each parser and correct per-owner disposition. Out of scope: accepting huge values, silently coercing booleans, a universal schema framework, weakening cache identity or making invalid authored config recoverable. Avoid adding catches everywhere when the parser can prevent the state.

Proof: valid controls plus 10**400 duration/phase timing/series/mtime; valid history sibling remains available; open returns typed unavailable; normal analysis sees corrupt-cache miss/recompute; cache-only receives typed refusal. Retain version/path/type/finiteness/atomicity proofs. Static/native and affected Docker M3 after integration. Rollback: revert parser changes, no format upgrade or data deletion needed. Risk: overbroad recovery hides unrelated I/O/programming errors. Disjoint from P3; coordinate run-result files with P1's outcome assertions.

### P5 — Give each Docker verification run owned output

Goal: verification retains existing debugging evidence and only cleans paths allocated by its invocation. Files: `tools/verify_docker_integration.sh`, Compose artifact/mount interfaces as needed, workflow artifact upload consumers and runbook output recipe.

Scope: fresh output root, explicit container path, nonroot mount ownership, failure retention and containment/ancestor-link safety. Out of scope: deleting old user evidence, rewriting all verifiers, changing product generated-data layout or removing useful stale-artifact prevention.

Proof: unchanged preexisting normal/linked-root sentinels on success and early failure; current invocation artifacts confined and correctly retained/uploaded. Canonical Docker gate once, serialized, with real installed application/mount proof. Static/native contract suite after integration. Rollback: revert producer and workflow consumer together; preserve old and new evidence directories. Risk: upload glob accidentally picking earlier artifacts; no dependency, but P6 shares Docker workflow, so coordinate or integrate those changes serially.

### P6 — Align Docker build context and CI selection with producer inputs

Goal: .tmp stays out of runtime images and actual Docker build-input changes select the managed gate. Files: `.dockerignore`, `.github/workflows/docker-integration.yml`, relevant workflow/producer tests. Dockerfile/Compose are reference consumers; no refactor required.

Scope: .tmp exclusion, checkout-helper/ignore-file path selection and meaningful positive/negative controls. Out of scope: copying all Git ignore rules, removing legitimate source/build inputs, dependency upgrades, speculative security incidents or running hosted PRs without authorization.

Proof: harmless context sentinel absent in production image (no bind overlay), necessary source/install/help present, matched/omitted/docs-only/all-base-branch controls. Deliberately remove exclusion/selection in an isolated negative-control fixture to establish sensitivity. Canonical Docker gate serially after P5/P6 integration; actual hosted sole-file PR selection remains O-13. Rollback exclusion/CI tests together. Risk: accidentally excluding necessary verifier/tests/build helper; P5 shared workflow requires a single integration owner.

### P7 — Decode published install state explicitly as UTF-8

Goal: supported Windows5.1 fallback uses the same path bytes the installer writes. Files: published `shim/frame-compare.ps1:113`, `shim/frame-compare-update.ps1:287`, state writer and relevant launcher/update proof.

Scope: explicit read encoding in both consumers, no state schema change. Out of scope: removing published-bundle fallback or source-builder policy (P8). Proof: isolated real ANSI Windows5.1 account, no pwsh, non-ASCII extraction, installed version/list-backups; PS7/ASCII controls. Existing source tests are supporting only. Integration native/static contracts plus canonical extracted-bundle/physical Windows recipe; no false macOS acceptance. Rollback restores both reads coherently; preserve state/PATH/config. Risk: choosing an encoding API unsupported in5.1. No dependency; P8 is separate source route.

### P8 — Reconcile source-build PowerShell support

Goal: documented root CMD route works on its stated interpreter or refuses with a precise prerequisite before bootstrap. Depends on D-01. Files: root install CMD/PS, source installer, builder initial path/API calls, Windows source-install docs and faithful entrypoint tests.

Recommendation: require/find PS7 early for source builds, preserve published5.1 install/launch/update. Alternative full5.1 support must audit all relevant newer .NET calls and run the actual builder route. Scope is source prerequisites/entrypoint; out of scope unrelated runtime refresh or automatic global PowerShell installation.

Proof: no-pwsh root install.cmd -SkipSync on Windows5.1 produces explicit early refusal without sync/output mutation; PS7 route reaches supported builder; alternative5.1 design must actually build. Update docs with chosen obligation and run docs/contract gates. Rollback entrypoints/docs together. Risk: fixing only GetFullPath exposes the next unsupported API; a partial shim is insufficient. No dependency on P7, though both need the same physical acceptance host.

### P9 — Separate Blink pause intent from gesture suspension

Goal: explicit/reduced-motion pause survives gestures; timer and controls agree. Files: `services/report/assets/viewer.js`, `viewport.js`, affected gesture siblings and retained state/browser proof.

Scope: one Blink policy owner and explicit gesture suspension lifetime, pan/pinch/Lens completion/cancel. Out of scope whole-viewer redesign or changing active Blink resume behavior. Migrate direct boolean writes and delete superseded pause coordination; avoid replacing one coordinated flag set with another impossible combination.

Proof: initially paused/running and reduced-motion cases through actual production handlers/timer; cancellation paths; actual Chrome DOM and physical click/pan/touch as O-06/O-10. Browser smoke after integration plus static/native once with other UI packages. Rollback state/handlers together; browser preference schema migration only if deliberately changed, with valid prior state retained. Risk: gesture suspension never released or explicit pause accidentally reset. Disjoint from P10's review model; shared root viewer requires boundary agreement.

### P10 — Preview the selected review candidate

Goal: Change/Add/Remove/Unchanged predicts exactly the operation selected by merge/replace/conflict choice. Files: `review_state.js`, controller display/announcement and existing review model/controller proof; renderer only if wording is deliberately revised.

Approach: compute candidate once at policy owner, compare local→candidate for preview and apply that same candidate. Out of scope changing Keep local semantics, weakening report identity/key/size/UTF-8 validation, storage quota/atomic rollback, or treating all conflicts as writes.

Proof: each conflict choice changes expected delta, preview equality with full-record apply, no-change control, replace/removal, wrong-report/malformed input/quota failure preserve data. Actual File API/controller preview/apply, then browser smoke/native integration. Rollback model/controller together; no durable report schema migration required. Risk: preview candidate becomes stale between file read and apply; retain async tokens and recalculate/validate at real boundary. No dependency; coordinate browser exclusive resources with P9.

### P11 — Keep warning status out of user-controlled display text

Goal: valid labels and diagnostic wording cannot change semantic warning/skip treatment. Files: warning producers, result carrier/projection, `cli/output.py`, relevant output controls.

First compare smallest bounded grammar correction against explicit internal warning status. If the actual producer grammar is unambiguous, parse only its semantic field; otherwise migrate producer→carrier→human projection with explicit status/source and project unchanged public strings for JSON/persistence. Do not add a generic diagnostics framework or a string subclass hiding policy. Scope: identified warning-family semantics; out of scope authority or exit changes.

Proof: identical unapplied result with neutral/skipped-containing labels and reasons, genuinely skipped warnings, cap/headline/post-action deduplication, pinned public JSON strings. Static/native output gates; no media gate needed for this textual rule. Rollback carrier and consumers together if introduced. Risk: breaking public warning schemas or misclassifying other producers. Coordinate phase_alignment/coordinator ownership with P1/P12.

### P12 — Use truthful neutral applied summaries

Goal: manual authority without audio computation is never summarized as audio applied. Files: phase_alignment summary and alignment_presentation pre-review summary.

Change both applied branches to alignment applied; preserve VSView count and unavailable/needs-confirmation wording. Out of scope extra provenance DTO/trim/cache behavior unless product requests richer short summaries. Proof: both owners, valid manual0/nonzero/computed/cache, reviewed control and actual retained success-line policy. Static/focused native integration; no media rerun solely for wording. Rollback both owners coherently. No dependency, but serialize overlapping phase_alignment edits with P1/P11 or give one integration owner.

### P13 — Remove the inactive second color policy

Goal: one actual color/range conversion owner receives maintenance and faithful pixel proof. Files: `vs/color.py`, unused ColorProps definition/export, VS facade, incidental color mocks and generated API documentation. Confirm all production/plugin/persisted/direct-import consumers first.

Recommendation: delete orphan family and its exports/mock-only tests, retaining encoders/tonemap_conversion/props and their native obligations. No compatibility shim absent a real consumer. If a consumer is discovered, migrate deliberately with a deletion plan or retain a narrow operation proved on real runtime; do not merely change RGB0→2 and claim the whole obsolete family repaired.

Proof: caller/import inventory, active range/tonemap pixel cases and runtime-free imports remain; regenerate/check API; static/native gates. Docker pixel proof if active conversion code or caller is changed, rather than rerunning everything for deletion alone. Rollback deletion/exports/docs as one package. Risk: undocumented external convenience imports; profile disclaims stable API, but check user's current consumers. Independent files from viewer/Windows.

### P14 — Reconcile four documentation claims with evidence

Goal: accurate wizard publishing, localized timestamp, historical offscreen-vs-visible evidence and metrics-conditional fastest/cache-only guidance. Files: current CLI contract, sources/labels guide, route-comparison/audio-alignment guide; detailed runtime/handoff references as evidence.

Scope: F-017–020 prose only; out of scope wizard feature, timezone behavior change or broad platform verified claim. Preserve exact source/artifact/date and distinction between historical Linux-container offscreen and unavailable current physical visible acceptance.

Proof: actual PTY behavior already establishes wizard scope; formatter and CLI recipe controls establish date/mode condition. Resolve historical records before wording proof tier; don't invent raw-log authentication. Run existing docs guards and strict site after integration. Rollback prose together if underlying behavior changes; no data migration. Risk: flattening historical/physical distinctions. Coordinate contract wording with P3/P8 if those packages alter it; otherwise independently shippable.

### P15 — Make the terminal path assertion portable

Goal: verification preserves row-zero and full-path obligations without depending on incidental Rich line width or checkout depth. Files: `tests/orchestration/test_alignment_report.py` and existing terminal fixture/proof facilities; product width policy is reference, not automatically changed.

Scope: fixed semantic assertion and faithful narrow/wide/long-path proof. Out of scope widening all output to make one test pass, deleting path coverage or introducing a broad snapshot framework. Prefer deterministic path input where no filesystem I/O is involved, or normalize actual wrapped table presentation appropriately while asserting the meaningful path and row facts.

Proof: former deep-basetemp failure and shorter control both pass after correction, and deliberate omission/wrong source path still fails the retained obligation. Full native once after integration, no new Docker/media requirement. Rollback test change only; source behavior remains. Risk: normalization removing too much and allowing missing paths. Disjoint from product corrections except shared terminal fixture ownership.

## Sequencing and integration

Prioritize P1/P2/P3/P4/P5 for actual cancellation/input/output ownership; P7/P8 need Windows decision/acceptance; P6 closes producer/CI drift. P9–P15 are bounded correctness/debt/documentation follow-ups. Numbers do not impose a sequential pipeline.

Disjoint owners may work in parallel once separately authorized: config, persisted parsers, child probe, Windows readers/source prerequisites, review model, color deletion and docs. Actual overlap requires serialization or one owner: P1/P11/P12 phase_alignment/coordinator; P5/P6 Docker workflow; P3/P8/P14 contract docs; P9/P10 root viewer registration if modified. One integration owner merges and calibrates findings. Docker/media/browser heavy gates are serialized and run once after integration, not once per package. Focused regressions first; reuse valid existing baseline evidence until code/toolchain/input changes invalidate it.

Required review gate: confirm each correction eliminates its observed failure and keeps counterpoint obligations. Run selected static/import/docs checks as appropriate; once-only native after shared product integration, Docker media only for changed managed execution/producer/cache/render obligations, browser smoke for changed viewer behavior, Windows extracted/physical proof for actual Windows support. A skip or source-string check remains a gap. No release authority follows from these gates.

## Parking lot

Not provisionally accepted: incompatible rollback retained across supported full reinstall (D-03/O-03), first-rename locked-leaf recovery, local native proof hang, later missing-image UI, infinity timeout operational effect and abnormal service response budget. Rejected candidates in REPORT.md must not be silently reinstated. Preset-directory symlink policy needs D-02 before any containment change. Production signing, live delivery, GPU/X11/Windows/amd64 acceptance and legal release approval remain observations; this proposal assigns no implementation or external action for them.
