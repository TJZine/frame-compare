---
search:
  exclude: true
---

# Frame Compare comprehensive production review

Reviewed 2026-10-08 at `58e50a6d48c0004b63f60b9b3ba53c1ac4b31537`, branch `agent/e2e-test-strategy`. This is a read-only assessment and an unapproved remediation proposal. No product, test, configuration, dependency, workflow, Git reference, or release change was made.

The strongest findings concern first-SIGINT cancellation crossing synchronous phase boundaries, a child interpreter importing workspace code, malformed configuration escaping typed CLI errors, corrupted persisted numerics escaping recovery, and the Docker verifier deleting previous evidence. Platform-dependent Windows compatibility findings remain source-supported inferences. No S0 or S1 defect was established. Finding counts and final gate results are recorded in the verification section below; hypotheses are separated in `NEEDS-OBSERVATION.md`.

## Scope, baseline, and method

The complete human prompt, root `AGENTS.md`, `CLAUDE.md`, `.agents/project.md`, architecture, CLI contract, runbook, import rules, manifest/lock configuration, and workflow surfaces governed the review. Shared review-code, design-code and verify-code supplied the correctness, ownership and evidence standards; develop-code was assessed as a workflow standard, without implementation. repo-production-review supplied the census and specialist dimensions; evidence-calibration rejected unsupported candidates; remediation-plan supplied the draft packages. maintain-workflow was neither run nor modified.

Initial Git status was already `?? docs/prompts/`. This contradicts the prompt's clean-start premise; the user-supplied prompt was preserved. The final status must therefore include that existing directory as well as the new review folder. Tracked source remained unchanged. Scratch was confirmed ignored by `.gitignore:10` before writes. Source identity was rechecked throughout; no old profile branch or historical plan selected the revision.

Tools: uv 0.12.21; CPython 3.13.16; Docker 29.8.0 client/server; native macOS/aarch64; installed Chrome; locked nodejs-wheel available. Native doctor exited 3: VapourSynth R81/API4.3 and VSView passed, L-SMASH and placebo were absent, FFMS2 absence was permitted for unmanaged native, FFmpeg/ffprobe 9.0.2 passed, TMDB was unconfigured. Doctor also made an unauthenticated slow.pics request (controller HTTP520; preliminary child HTTP403). This side effect is disclosed: no credentials were used, and doctor was not repeatedly invoked for review discovery. No secret-bearing local config was read. Later synthetic/fixture probes used scratch workspaces and rejected unexpected HTTP; managed-runtime verification has its own doctor boundary.

Review dimensions were split into alignment, lifecycle, configuration/persistence, viewer, Windows, CI/Docker/distribution/release, user documentation, network/privacy, architecture/workflow, summary provenance and independent rollback calibration. Each reviewer scanned broadly and read representative runtime paths deeply. This is not a claim that every source line or every test assertion was read. Vendored binaries, opaque media, generated/site outputs and caches were excluded from qualitative review, except where producer/artifact behavior directly involved them. Optional Codanna was not necessary.

### Repository census

The selected tracked source/test/docs/tool/workflow inventory has 604 files: 195 under `src`, 277 under `tests`, 62 under `docs`, 48 under `tools`, eight under `scripts`, and 14 under `.github`. Counts are investigation clues. Large owners include viewer.js (~2,219 lines), alignment.py (~1,361), alignment_streaming.py (~1,162), alignment evidence/panel (~1,009 each), Windows builder (~1,749) and updater (~1,039). Large test carriers include frozen alignment strings, builder contracts, viewer harness and U4 acceptance. None is a finding merely because of size.

The application is Python 3.13+ and CLI-first, with browser JavaScript for offline reports, native VapourSynth/FFmpeg media boundaries, HTTP publishing/metadata services, Docker-managed runtimes and a Windows embedded portable distribution. Runtime trace: installed `cli.entry:app` → lazy runner → coordinator preparation → typed phases → rendering/publishing/report → durable run result. Simple help/version remains runtime-free. Layer rules keep analysis/render/services independent and direct lower dependencies through VSView/VS/config/utils/errors; no ignore-import suppression was found.

Nine workflow files cover native lint/type/security/import/tests/browser/package aggregation, Docker media/resource proof, strict docs, release preparation/publication, reusable Windows build/signing, title and staging synchronization. Distribution verification, source checkout integrity, Windows inventory/signature/update verification and release byte/asset guards were deeply sampled. Benchmark tools, API AST generation and optional Codanna bootstrap were inventoried and sampled for actual consumers, authority and claimed evidence; no further material defect was established.

### Dispatch and model correction

The prompt initially suggested explorer presets. R1–R5 began using the local explorer model, gpt-5.6-luna/xhigh. The user rejected that choice and required rereview of finished scopes. Model overrides on an already running turn did not retroactively change its sampler. Fresh gpt-6.1-sol/high reviewer turns supersede those conclusions; no accepted finding relies on Luna consensus.

| Authoritative unit | Chat ID | Preset/model/effort | Scope and outcome |
| --- | --- | --- | --- |
| V1 | `01a11a55-22ce-7991-9da9-80907815bf58` | reviewer / gpt-6.1-sol / high | Alignment authority, identity, domains; initial authority/FPS candidates rejected; 136 focused passes |
| V2 | `01a11a55-2bb7-79c2-9847-5ce95eaf6826` | reviewer / gpt-6.1-sol / high | Real SIGINT/process/import boundaries; two S2 groups; 34 probe/retained passes |
| V3 | `01a11a55-37c1-7020-8b38-231964cc025c` | reviewer / gpt-6.1-sol / high | Config/CLI/persisted parsing; four S2 groups; 297 fresh and 101 reused passes |
| V4 | `01a11a55-44f0-7f11-b1e9-9d99daccd7f7` | reviewer / gpt-6.1-sol / high | Viewer/transfer/gesture owners; two S3 groups; 84 reused passes plus fresh JS reproduction |
| V5W | `01a11a55-50a1-7173-9560-cbf2dfa03c58` | reviewer / gpt-6.1-sol / high | Narrow Windows lane; two accepted S2 inferences; 64 distinct contracts ultimately passing, no Windows runtime pass |
| R7 | `01a11a55-5b8a-7000-9889-cb51a46fa660` | reviewer / gpt-6.1-sol / high | Architecture/shared workflow; warning policy and orphan color debt; 50 focused passes |
| R7P | `01a11a56-7f1d-7f60-bb17-d4712aaadcb3` | reviewer / gpt-6.1-sol / high | Bounded human-summary provenance supplement; one S3 |
| V5C + supplement | `01a11a61-1d18-7292-a970-3d97813f663f` | reviewer / gpt-6.1-sol / high | CI/Docker/distribution/release, then scratch-context inclusion; 69 focused passes |
| V6D | `01a11a62-0b48-7372-8bbc-00370f233342` | reviewer / gpt-6.1-sol / high | Full user-doc scan/journey proof; 24 passes, 13 help/version calls, 33 schema-valid TOML snippets and real PTY wizard |
| V2N | `01a11a62-da3a-7903-95e2-82981f312560` | reviewer / gpt-6.1-sol / high | Separate network/privacy lane; 275 focused passes; no material accepted network finding |
| VW3 | V1 chat reused | reviewer / gpt-6.1-sol / high | Independent disputed rollback review; downgraded to conditional hypothesis; no tests claimed |

Initial R1 and R5 mistakenly created nested duplicate chats despite the packet's no-nested instruction. R1 archived its duplicates; completed R5 duplicates were superseded by the fresh scoped reviewers. R7P was retained for a narrow supplement. This was a coordination deviation, not evidence. Ten authoritative chats carried eleven named units plus one focused supplement. The controller independently checked all S2 candidates and high-risk no-finding claims, reran the bounded production probes, and retained resource/authority mitigations even when they disproved a candidate.

## History-derived defect classes and sibling hunts

The controller read the fix/test/revert subjects and bodies across current ancestry, CHANGELOG Fixed/Security/Upgrade notes, DECISIONS/TODO, release-evidence records and relevant plans, including the 10-04 remediation, 10-07 dependency/Windows handoff and 09-30 test strategy. Historical records supply mechanisms, not standing instructions or current acceptance. The following table names derivation examples and the actual sibling search; fixed instances are not re-reported.

| ID / class | Derivation checked | Whole-codebase sibling search and result |
| --- | --- | --- |
| K1 Alignment authority/provenance/zero | `f46752ce`, `2bbe7900`, `6acebb99`, `5e75900c`, `d7fbb2b8`, `80598c86`; changelog authority/cache migration | Decision, constructors, phase trims, previous/manual reuse, cache writers and VSView result acceptance. Trusted audio+video conjunction and valid zero retained. No surviving authority leak; manual false flag rejected as an authorization claim. F-015 is presentation only. |
| K2 Source identity TOCTOU | `2bbe7900`, `bfa369ad` | Audio pre/post collection, video pre/post scoring, manual/cache acceptance, locked cache writes, prepared/render/report sources. No new defect established within documented path/size/mtime identity. Same-stat replacement is expressly outside stronger guarantees. |
| K3 Authoritative presentation | `459865ea`, `9aae9f52`, `c0fb947d`, `a37ddbba`, 09-26/27 target fixes | CLI warnings/summaries, JSON/run records, shared panel projection, report source frames, labels and actual render facts. F-012–015 and F-018; no universal projection rewrite proposed. |
| K4 Boundary validation / config vs recovery | `0348e825`, `2bbe7900`, changelog schema hardening | Config/raw loader/presets, all path fields, history/analysis/TMDB/probe/alignment caches, manual/IPC sidecars, browser storage/import. F-003–006, F-013. Preset symlink policy is a decision, not a vulnerability. |
| K5 Actual-operation status | `0348e825` | Acquisition-derived cache disposition, dry-run unknowns, doctor presence/function, progress/completion, documentary proof status. F-001 and F-019; otherwise searched, no new prediction-based defect. |
| K6 Child/handle lifetime | `78c38b6e`, `1c99e4b4`, `94464b85`, `71d5bd8b`, `b9919607` | Every subprocess family: shared runner, FFmpeg/probe, doctor, tonemap, VSView, DNS, paired streaming, Windows jobs/updater. Real reaping/reader ordering retained. F-001 overlaps cancellation; fabricated never-exiting-child claim rejected. Windows native hang/locking parked. |
| K7 Cancellation / first failure | `32c60a24`, `79f25999`, `635c14e3`, `233b8c6c` | Main runner, synchronous phases, render admission, audio stop/drain, TaskGroup, webhook repeated cancellation, thread/cache ownership. F-001. Successful cache writes after coroutine cancel are not material absent a discard promise; CLI executor drains before exit. |
| K8 Time/memory/size bounds | `3ee93554`, `c8c03a96`, `aeb67e4d`, `474f8870` | Process deadlines, audio queues/windows/lag, HTTP/DNS/planner concurrency, JSON reads, archive bounds. No new supported-workload exhaustion established. Infinite timeout and abnormal service body budgets parked; finite report Promise cache is not unbounded amplification. |
| K9 Secret leakage | `e7b457dd`, `681ea6b3`, `569b81c9`, `6d8fb99e` | Recursive config redaction, generated/preset persistence, chained HTTP/navigation/image exceptions, doctor, resolver env, run records/report/webhook/TMDB. Executed transport/decode redaction controls passed. No new leak; wizard's stronger redaction is explicit policy. |
| K10 Interpreter isolation | `40ef773d`, `e04aa81b`, `0a1dd975`, portable `._pth` | All child Python launches and their cwd/PYTHONPATH/user-site handling. F-002; VSView and isolated DNS child policy retained. Portable startup remains platform observation. |
| K11 Option combinations / timing | `33dbc6e7` | Early-exit/cache pairs, JSON prompts, dry-run/write-config, metadata/upload/open legality and reservation ordering. F-004 input path boundary, F-020 conditional guide wording. Other inspected combinations retain useful early validation. |
| K12 Producer/consumer drift | `2bbbb403`, `5fc065a4`, 10-07 stale `vsview.main` incident | Tools/scripts/Docker/Compose/workflows, coordinated runtime markers, Windows builder/shims, API docs, copied panel text and source checkout helper. F-008–011, F-016–017; modern VSView/vspackrgb references agree. |
| K13 Viewer races / interpolation | `5c9c3de1`, `d1bf9d8c`, `286ef388`, `ae7ad892` | All report assets' deferred loads/tokens/timers, raw sinks, labels/URLs, state imports and local storage. F-012–013; Diff/Grid atomic commits, Lens cancellation and escaping retained. Missing later image files parked. |
| K14 Sign/frame/retiming domains | changelog v0.5 sign correction, `5e75900c`, `853a5e21` | Raw/base/aligned/source translation, negative/zero trims, configured effective FPS, slow.pics/report mappings. No surviving production-domain finding. Omitted-FPS convenience route does not meet documented reachability. |
| K15 Exception/numeric taxonomy | `7bfed695`, DECISIONS FC-2009/FC-2001 distinction | Float conversion/finite checks, durations/window math, cache/history parsers, typed category→exit and HDR failure. F-003–006. Infinite minimum window is not included in crash claim. |
| K16 Platform behavior | `57d24df5`, `982e7e27`, `9401f471`, naming limits | PowerShell encoding/API versions, Windows locks/rename/PATH/long paths, native signals, case collisions, portable startup. F-010–011; rollback/locked leaf need supported-path/Windows observation. |
| K17 Partial sibling failure | changelog v0.6 TMDB variant preservation, `6d8fb99e`, render first-failure fix | TMDB partial successes, metadata merges, publisher file deletion/resource ownership, render ordering/drain. Focused negative controls pass; no further defect established. |
| K18 Verification blind spots | `2aed9636`, `681ea6b3`, `9c1fbc59`, `2835f74d` | CI selection/aggregate, mock/native/media skips, docs assertions vs recipes, browser and source-only Windows proof. F-008, F-016, F-019, F-021. Actual runtime acceptance kept distinct. |
| K19 Release/update integrity | `474f8870`, v0.6 release-body fix | Signature before parse/extract, archive bounds, runtime/dependency refusal, release identity/notes/assets/checksums/remote bytes, backup restoration. No accepted signature/publication bypass; rollback hypothesis independently downgraded. |
| K20 Lost guards in slimming | 10-02 restores `94a943cd`, `4d351721`, `01a1786d`, `f969157f`, `42464da6`, `4c6ab6ab`, `7f650849`, `860c5866`, `cfca3318`, `17db3c4b`, `a8a1f12e` | Retained authority/evidence, cache-source refusal, phase/report/config facts, rendered labels, post-actions, UID/mount/frame/index, numeric/lifecycle and update tamper controls sampled. No new proven deletion-caused loss. F-001/012/013 are present gaps, not attributed to slimming without deletion evidence. |
| **K21 Verifier/fixture output ownership** | **New:** `7c57ffff` body explicitly records deletion of developer E2E artifacts; `54d07b2b` repairs writable proof cache | Recursive cleanup and output consumers across all verifier scripts, E2E harness/media/cache and artifact uploads. F-007 and scratch producer F-009. Separate from child lifetime: the burden is filesystem/output authority. |
| **K22 Decoder seek/sample-grid fidelity** | **New:** `4f571649` cross-version audio seeks; `7f342a62` continuous oracle; `2eb46a4e` packetization/offset proof | Sampling, whole-track collector, decoder source/metrics, retiming extraction, continuous oracle and exact-frame media tests. No new defect established; real codec/platform acceptance remains limited. Separate from K14: fidelity can fail before a correct domain translation. |

## Journey matrix and documentation contract

“Existing proof” identifies inspected carriers; it does not mean every platform recipe was executed. The final gate ledger distinguishes actual runs.

| Journey | Runtime trace / existing proof | Findings and remaining limits |
| --- | --- | --- |
| J1 First comparison | wizard→doctor→config/preflight/dry-run→runner→report; first-use/no-op wizard, E3 dry-run, M1/M2 render, browser file loading, Docker/Windows runbook | F-003–005/F-017. Real PTY wizard executed. Native media incomplete; Docker managed proof separate; Windows configure/install/visible report absent. |
| J2 Repeat | preparation/acquisition→cache/history/preset owners; E4/E5 non-media console, M3 warm/cache-only/no-cache/corruption/history | F-003/F-006/F-020. Dry-run/history/preset console and parser controls executed. Docker M3 is actual generated-media evidence; physical browser opening is separate. |
| J3 Variants | schema→source/domain/window/metrics→VS/FFmpeg/HDR; source/FPS/active-rect/performance/memory tests and media E2E | F-002/F-004/F-005. 33 valid TOML examples prove schema only. Docker fixture/runtime paths do not exhaust 3+ sources, all retiming/HDR/preset/device combinations. |
| J4 Alignment | decision/evidence→result→trim; previous/manual/review/source-freshness; U4/phase/video/cache/IPC and M5/M6 decoded-pattern proof | F-001/F-014/F-015/F-019. No surviving authority leak. Native panel/physical gestures/signals require real host; mocked scoring is not decoder acceptance. |
| J5 Retry | explicit run consent→effective config/window/domain→selection; full_window_retry, phase tasks and JSON refusal/fatal-once tests | No new defect. Source/focused evidence preserves no authored config write, recomputation and fatal second failure. No additional terminal-to-real-media retry acceptance claimed. |
| J6 Publishing | report-confirm ordering→publisher/shortcut/webhook; isolated transport/DNS→TMDB/cache; publisher/webhook/resolution tests | F-017 stale wizard instruction. 275 network cases plus controller redaction probe passed; no authorized real-credential service request or delivery/auth acceptance. |
| J7 Streams/exits | early validation→typed adapter or pinned result/history JSON; real-console E2 and CLI error/output tests | F-003/F-004/F-006/F-014/F-015. Invalid-byte/NUL/history probes show actual empty JSON stdout/exit1 failures. Typed ordinary paths remain sound. |
| J8 Failures | config/path/runtime/media/selection/render owners; recoverable caches, doctor and HDR taxonomy | F-002–006. Full disk, unreadable real media and platform native faults not exhausted. FC-2009 vs invariant errors retained; no global catch recommended. |
| J9 Interrupt | runner→phase admission/resource owner→failure/outcome; audio/webhook repeated cancel, VSView reaping/render first-failure tests | F-001 real SIGINT + real child/coordinator probe. Actual native stuck worker, Qt/FFmpeg process-group/Windows repeated signal acceptance unresolved. |
| J10 Offline viewer | actual render facts→payload/escaped renderer→mode/viewport/Lens/Grid/Inspector/review transfer; Node state and browser smoke | F-012/F-013/F-018. Browser baseline and defect-specific actual DOM/timer/File integration ran; physical gestures/OS file picker remain distinct. Initial custom launcher timed out; existing launcher control succeeded. Later screenshot loss parked. |
| J11 Platforms | published/source install→embedded startup/update/rollback; headless/GPU/GUI Compose; profile-specific runbooks | F-007–011/F-019. Local Docker aarch64 managed evidence is not amd64/NVIDIA/X11 or Windows acceptance. W3 rollback is conditional hypothesis. |
| J12 Artifacts/release | build metadata/distribution verifier→installed CLI; guarded release/Windows signing; API/docs gates | F-008/F-009/F-016/F-021. Negative distribution/aggregate/release-note checks inspected/executed; no new artifact build/install, hosted signing/publication or legal acceptance claimed. |

All root/leaf help and version routes compared successfully with the actual installed command. The docs guard checks selected family headings, live override pairs, generated-data and history cutover phrases. It does **not** prove all narrative behavior, links, JSON schema, native support or PTY interactions. The stale wizard/date/conditional mode claims escaped those guards. F-017–020 classify the mismatches as documentation corrections; F-010–011 are code/entrypoint compatibility risks. No new wizard feature or timezone product change is proposed.

## Architecture and maintainability against the shared workflow

### Owner map

| Policy / subsystem | Owner and representative caller trace | Assessment |
| --- | --- | --- |
| CLI composition and runtime-free commands | entry lazy boundary→runner→coordinator | **Sound — retain:** import timing has a real public obligation. |
| Config/environment and persistence | schema/loader/effective; wizard patch/persistence and preset owners→preflight | **Retain** policy ownership and secret omission; F-003–005 close real input gaps, not every internal caller. |
| Preparation/reservation | coordinator→execute_prep→discovery/probe/source domain→PrepState | **Retain:** cache-only rejection before run reservation earns its distinct sequence. Optional staging fields alone are not a burden finding. |
| Run cancellation/admission/commit | runner→execution/phases→resource owners→coordinator result record | **Burden F-001:** synchronous callers can continue while owning task is cancelling; cancellation owner must coordinate admission and stop/drain. |
| Alignment authority | frozen request→alignment orchestration→alignment_decision→validated AlignmentResult→phase trim composition | **Sound — retain:** one decision owner; IPC, cache and final application checks guard distinct trust/freshness boundaries. |
| Alignment presentation | terminal/panel→shared audio review projection; phase/pre-review short summaries; warning text→CLI | **Retain** shared evidence projection; F-014/015 are concrete remaining text-policy bypasses. No universal presentation framework needed. |
| Render facts and frame domains | phase→typed requests→batch/encoder→observed artifacts→report/publish source-frame mapping | **Sound — retain:** actual encoder facts and explicit translations prevent prediction/units drift. |
| Child environments/lifetimes | subprocess utility, VSView adapter, DNS child, tonemap probe | **Retain** earned resource-specific seams; F-002 closes a sibling isolation gap without an upward vs→vsview import. |
| Publishing and metadata | plan→publisher→result/post-actions; metadata facade to phase/doctor/run folder | **Sound — retain:** facade and wrapper own timing/progress/lifetime and have real consumers. Injected HTTP clients remain caller-owned. |
| Persisted data | record/cache/IPC parser→typed representation→consumer | **Retain** trust checks and atomic writer/lock boundaries; F-006 normalizes numeric conversion at each parser. |
| Report composition | phase artifact validation→ReportData→entry/payload/renderer→explicit atomic output | **Sound — retain:** service owns report facts, CLI owns browser launch; distinct cardinality/path checks remain needed. |
| Viewer mechanics/state | root viewer transitions; Viewport coordinates; Lens/Grid/Inspector focused controllers; ReviewState validated transfer | **Retain** focused controllers; F-012 separates pause intent from gesture suspension, F-013 unifies chosen candidate and preview. |
| Color/range conversion | active encoders/tonemap_conversion/props; unused vs.color family | **Burden F-016:** second unused policy owner is exported, documented and mock-tested despite runtime drift. Remove it after real-consumer audit. |
| Errors | leaf typed errors→shared context/categories→CLI exit/persisted safe presentation | **Sound — retain:** categories align; expected boundary errors should be translated locally, not globally swallowed. |
| Docker outputs/context/CI | verifier→Compose mounts→workflow artifact consumer; context→Dockerfile retained tree→path filter | **Burden F-007–009:** fixed cleanup/output assumptions and producer-input drift cross callers. Correct producer and consumer together. |
| Windows install/update | atomic state writer→fallback readers; source wrapper→builder; signed apply→backup/restore | **Retain** signature/runtime guards; F-010/011 reconcile actual fallback interpreter obligations. Backup migration policy remains a decision. |

### Concrete burdens, invalid states, and earned complexity

Pause intent and gesture suspension share one boolean written by two owners (F-012); the resulting impossible presentation is an actual timer running while controls say paused. Import preview and apply repeat conflict policy (F-013); a candidate computed once can remove that disagreement. Warnings mix trusted semantic status with user text (F-014); a label should not change severity. Two short summaries rederive applied status as audio provenance (F-015); neutral wording fixes the current need without a new projection hierarchy.

Frame/time offsets, native/effective FPS and raw/base/aligned/source frames have distinct meanings even where represented by integers/floats. Current named translations and authority validation are materially useful. The omitted-FPS convenience call is not a supported production defect: the CLI supplies effective FPS. An explicit manual file is manual authority; its historical `confirmed` flag documents confirming a computed offset, not an unaccepted draft. Neither field name justifies inventing a missing product rule.

The orphan color subsystem is the concrete dead-code finding. Metadata facade, publishing wrapper, phase result unions, lazy runtime facades, typed collector policy and IPC checks have current consumers or actual lifetime/import/trust obligations. No speculative extension-point or compatibility scaffold was promoted merely from narrow usage. Large modules were traced through representative operations, not judged by counts. Ignored `tools/old_consensus.py` and `tools/old_corr.py` are untracked local residue with no build/CI/package references; deleting them is outside this review.

### Verification quality and workflow-artifact drift

The color mock sets RGB to 0 while actual R81 uses 2 (F-016). The import harness asserts Change 1 together with preservation of the local note (F-013). These are behavior/proof mismatches, rather than complaints about test location or count. First-SIGINT runner proof is distinct from directly raising KeyboardInterrupt inside the wait adapter (F-001). F-021 records an environment-sensitive terminal assertion. Retained K20 samples still carry distinct authority, ordering, source-frame, cleanup, tamper and nonroot/mount obligations; no blanket test-pruning proposal is warranted.

CI import invocation, native aggregate negative cases, Docker nonpassing rejection and release-note positive/negative controls were checked. Installed/static/source checks are identified as such; hosted jobs, signing and runtime/device acceptance are not inferred from configuration. The real import gate kept both contracts for production source; an isolated source copy with one config→CLI edge exited1 and reported Layered Architecture BROKEN for that exact edge, while Domain Independence remained KEPT. This proves sensitivity to that violation, not every possible edge. Documentation “verified”/“parity” claims were checked against their recorded identity and proof tier; historical offscreen evidence is not a current visible-desktop pass (F-019).

Workflow drift list: **no material tracked workflow-authority drift promoted.** Root CLAUDE imports AGENTS; root/profile/rules point to canonical shared skill bodies; no tracked repo-local SKILL.md duplicates were found. Sixteen referenced repository files resolve, four shared bodies are present, eight executor presets and two runtime configs parse. Profile provenance is explicitly historical. Old plans are not activated as standing instructions. Optional Codanna is required=false. Claude permission maps remain preserved. Empty local skill directories and ignored old experiment tools are residue, not active competing workflows. Existence/parsing does not prove Claude discovery, Codanna service availability or hosted gate execution. No maintain-workflow action was taken.

## Calibrated findings

Severity: S0 critical, S1 high, S2 medium, S3 low, S4 informational. CONFIRMED means an executed failure observation, not that all environments fail. LIKELY requires a documented reachable source trace with no preventing guard. The commands in the probe index establish each cited observation; process exit0 for an observation probe can intentionally print a failed invariant. Hypotheses and policy questions are excluded from provisionally accepted remediation.

Source abbreviations in the findings resolve beneath `src/frame_compare/`; report asset abbreviations resolve beneath `src/frame_compare/services/report/assets/`. Named workflow files resolve beneath `.github/workflows/`. Tool and document paths retain their explicit repository prefixes. These are literal source references, not site-breaking Markdown file links.

### F-001 — First SIGINT permits later work and a completed run record

**CONFIRMED · confirmed defect · S2 · high confidence · K5/K7 · J4/J9.** `runner.py:36` uses asyncio.run; `orchestration/execution.py:88–98`, `phases.py:82–147` and `coordinator.py:243–257` can run synchronously without delivering pending task cancellation. Render admission at `render/batch/orchestrator.py:215–258` continues; native wait is `vsview/adapter.py:359`.

P-02 used the real runner signal handler, bounded real child, actual batch scheduler and actual coordinator/record writer with synthetic media/preparation boundaries. Output: `VSVIEW interrupt_latency=.401 post_work=[('post_review',1)] child_reaped=True`; later render units ran with cancellation pending and next phase `report` ran; `COORDINATOR pending_cancellation=[1] persisted_status=completed exit=KeyboardInterrupt`. An interrupted CLI can therefore do more work and record success before exit130. Actual uploads/manual/cache writes were not executed. [Python 3.13 runner documentation](https://docs.python.org/3.13/library/asyncio-runner.html) confirms first SIGINT cancels the main task cooperatively.

Correction: execution owner observes cancellation before output application, next phase and completed commit; synchronous resource owners get stop/drain and stop new admission. A post-call checkpoint alone does not bound the blocked wait; to_thread alone abandons work. Verify first SIGINT through runner plus failure record, no later work, and real owned cleanup. Counterpoints: real child was reaped, second signal may interrupt, deterministic first-failure/drain tests pass; no orphan/stuck-thread claim.

### F-002 — Tonemap capability child imports workspace code

**CONFIRMED · confirmed defect · S2 · high · K10 · J3/J8/J11.** `vs/tonemap_runtime.py:33,64–75` launches Python `-c` with copied environment and inherited cwd. `render/batch/expansion.py:105–114`→`render/prepare.py:118–122`→`vs/tonemap.py:23–51` reaches it for detected libplacebo and uncached capability. P-02: `TONEMAP cwd_shadow_imported=True probe_result=False`, with a marker vapoursynth.py in cwd and no PYTHONPATH. The real child/import boundary executed; no full HDR render claimed. [Python command-line semantics](https://docs.python.org/3.13/using/cmdline.html) explains cwd import and isolated/safe-path controls.

Impact: native HDR preparation can execute a workspace module or falsely select fallback. Isolate cwd/import policy while preserving required plugin/runtime variables; reuse policy without upward vs→vsview coupling. Verify hostile cwd/PYTHONPATH negative controls and real installed capability. Portable ._pth and PYTHONSAFEPATH mitigate some environments; the trigger requires the actual probe path/cache miss.

### F-003 — Invalid UTF-8 config/preset bypasses typed errors

**CONFIRMED · confirmed defect · S2 · high · K4/K15 · J1/J2/J7/J8.** `config/schema_sources.py:20–23` decodes; `loader.py:109–118` and `presets.py:54–57` omit UnicodeDecodeError translation. Run/preset CLI catch typed errors at `cli/run_command.py:337–345`/`preset_command.py:89–97`. P-03 installed console: both invalid-byte cases exit1 with empty stdout and UnicodeDecodeError traceback; run used dry-run JSON. Expected config failure is typed exit2/structured JSON. Preset has no JSON option, so only its taxonomy/traceback is implicated.

Translate decode/read failure at the file owner into existing sanitized config/preset errors. Verify JSON/human streams, selected config bytes unchanged and preset apply. No global Exception catch. Missing/BOM/TOML/schema cases and raw wizard invalid encoding already have useful guards.

### F-004 — Legal TOML NUL paths crash preflight

**CONFIRMED · confirmed defect · S2 · high · K4/K11/K15 · J1/J3/J7/J8.** `config/schema_models.py:40–48` accepts strings; `orchestration/preflight.py:140–159,176–186,239` resolves paths without translating embedded-NUL ValueError. P-03 writes legal TOML `"\u0000"` separately into input/generated/config path fields: each dry-run JSON exits1, stdout empty, `ValueError: lstat: embedded null character in path` traceback.

Reject filesystem-unrepresentable paths at the path/schema boundary and translate appropriate normalization errors before reservation/writes. Verify all fields plus expanded invalid values and affected consumers. Retain permitted external input/generated roots and existing selected-config/managed-descendant containment; this is not justification for blanket root containment.

### F-005 — Infinite lead/trail exclusion crashes window calculation

**CONFIRMED · confirmed defect · S2 · high · K4/K15 · J1/J3/J8.** `schema_models.py:70–72` lacks finite duration constraints; `selection_domain.py:215–228`→`analysis/window.py:34–98` converts seconds×FPS using ceil. Normal preparation invokes it at `preparation.py:615–621,698–705`. P-03 real TOML inf and dry-run are accepted (exit0), then the production window owner with 2,400 frames/24FPS raises `OverflowError: cannot convert float infinity to integer` for lead and trail.

Reject nonfinite configured exclusions at schema owner; preserve finite/empty/short-window typed behavior. Suggested proof: TOML/env validation before native work, existing window contracts. This is a production-owner reproduction plus reachable trace, not a real-media run. Infinite minimum window returned full range and is excluded; timeout infinity consequences are parked separately.

### F-006 — Oversized persisted integers defeat history/cache recovery

**CONFIRMED · confirmed defect · S2 · high · K4/K15 · J2/J7/J8.** `services/run_result_record.py:169–175` float-converts before finite validation; history recovery `:612,:727` omits OverflowError. `analysis/cache_io.py:341–353,595–614` has the same gap; loader `:217–226` only handles its parser error. Acquisition callers are `analysis/metrics.py:68–89`, preparation `:289–320`, phase selection `:298–314`.

P-03 valid controls succeed; replacing duration/phase timing, luminance or clip mtime with `10**400` raises `OverflowError: int too large to convert to float`. Public history list JSON exits1/traceback rather than isolating the unavailable entry. Cache consumer recovery cannot occur. Normalize conversion inside each parser, retain valid history siblings, normal cache miss/recompute and cache-only typed rejection. Other type/boolean/version/path/nonfinite guards remain valuable; no generic global catch or removal of boundary checks.

### F-007 — Canonical Docker verifier deletes previous evidence before work

**CONFIRMED · confirmed defect · S2 · high · K21 · J11/J12.** `tools/verify_docker_integration.sh:77,100,146–147,773–776` fixes generated/e2e, ignores host artifact override and recursively removes it before test invocation. P-04 executes an unchanged copied script with fake Docker failing exit17: `normal previous_deleted=True override_used=False`; linked generated ancestor also deletes the external scratch e2e sentinel.

Impact is bounded previous E2E/debugging evidence, including through an ancestor symlink; arbitrary comparison-media loss is not demonstrated. Allocate invocation-owned output, pass its mount path and update workflow artifact consumer/retention together. Verify existing normal/linked sentinels survive and failures preserve new evidence; then canonical Docker gate proves mount/nonroot behavior. Cleaning test artifacts intentionally avoids stale uploads, but does not require destroying an unowned preexisting subtree. `7c57ffff` fixed the test caller by copying the script, leaving public behavior intact.

### F-008 — Docker CI path filter misses actual build inputs

**LIKELY · inferred risk · S2 · high · K12/K18 · J11/J12.** Workflow `docker-integration.yml:4–13` omits `tools/checkout_source_commit.sh` and `.dockerignore`. Dockerfile `:65` copies/uses the checkout helper for native sources; `:297` copies filtered context. P-05 matches Dockerfile/Compose/verifier=True, those two paths=False. [GitHub paths-filter semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushpull_requestpull_request_targetpathspaths-ignore) supports the inference; no hosted job was observed.

A sole build-input change can merge without automatic managed-runtime proof. Include real producer inputs and meaningful positive/negative selection proof. Keep docs-only exclusion/all-base-branch behavior. Existing tests freeze the incomplete list; accompanying matched edits or manual dispatch mitigate. No broken artifact or actual hosted failure claimed.

### F-009 — Local Docker context retains ignored scratch in runtime images

**CONFIRMED · confirmed defect (artifact content) · S3 · high · K12/K18/K21 · J11/J12.** `.gitignore:10` ignores .tmp but `.dockerignore:1–47` does not. Compose contexts are `.`; Dockerfile `:297–300` copies and editably installs the retained tree, inherited by final stages `:318–377`. No scratch consumer/removal is present. P-06 simple rule negative control found no exclusion; metadata-only snapshot was ~68.7MiB regular-file logical scratch, not measured image size/time. During the canonical build from an owned HEAD archive, the controller added only a harmless `.tmp/review-output.bin` sentinel. A network-disabled production-image invocation without any source bind printed `production_scratch_sentinel_present=True` (.243s). This upgrades source inference to observed artifact content. [Docker context exclusion](https://docs.docker.com/build/concepts/context/#dockerignore-files) and [COPY semantics](https://docs.docker.com/reference/dockerfile/#copying-from-the-build-context) support the trace.

Exclude .tmp at the producer and protect necessary source inclusion. After correction the same harmless sentinel must be absent from the production image while required installed/runtime proof still passes. Fresh CI/git archives normally mitigate; here the sentinel intentionally supplied the otherwise absent scratch input. No secret exposure, code execution, exhaustion or build-time regression claimed. Do not delete useful scratch or blindly copy all Git exclusions into Docker rules.

### F-010 — Windows 5.1 shims decode UTF-8 state as ANSI

**LIKELY · inferred risk · S2 · high · K12/K16 · J11.** `tools/windows_portable/install.ps1:55–62` writes BOM-less UTF-8 bundle path; CLI shim `:113` and updater shim `:287` Get-Content-Raw omit encoding. CMD wrappers explicitly fall back to Windows PowerShell5.1. [Microsoft's encoding contract](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-5.1) specifies ANSI reading of BOM-less content there.

A non-ASCII bundle folder on an ANSI Windows system without pwsh can become a mojibake missing path. Read explicitly UTF-8 at both consumers; preserve atomic writer and supported published-bundle fallback. Exact Windows5.1 non-ASCII version/list-backups observation is O-01. ASCII, PS7 and UTF-8 locale mitigate. Source assertions and PS7/ASCII tests are not this runtime proof.

### F-011 — Source install offers 5.1 but builder needs newer .NET API

**LIKELY · inferred risk · S2 · high · K12/K16/K18 · J11.** Root install.cmd `:9,:15`→install.ps1 `:9`→source installer `:174`→builder `:30–33` uses GetFullPath(path,basePath) in the same fallback interpreter. The [Microsoft .NET Framework Path source](https://github.com/microsoft/referencesource/blob/main/mscorlib/system/io/path.cs) supplies only the one-string overload; source docs `windows-portable.md:88–101` say PowerShell and prescribe CMD, without requiring7.

Source bootstrap may occur before a raw method error. Choose early PS7 requirement or faithfully support5.1 (D-01); preserve published-bundle5.1 separately. Verify real root CMD -SkipSync and early prerequisites with no bootstrap mutation on refusal. Hosted/physical recipes using PS7 are sound but do not settle this fallback. No Windows execution was possible here.

### F-012 — Gestures lose Blink pause intent and leave dishonest controls

**CONFIRMED · confirmed defect · S3 · high · K3/K13 · J10.** viewer `:634,:659,:1345,:1665,:1705` and viewport `:126,:202,:222` share blinkPaused for explicit/reduced-motion pause and temporary gesture suspension; completion unconditionally clears it without control refresh. P-07 runs production modules/handlers/timer in existing synthetic DOM: both pause cases produce `pausedBefore=true pausedAfter=false timerAdvanced=true displayedStatus='Blink paused' displayedButton='Resume'`.

Separate user pause intent from gesture suspension and derive effective timer/control state at Blink owner. Verify initially running/paused, reduced-motion and pan/pinch/Lens completion/cancel siblings. P-16's corrected existing-launcher Chrome control also printed `pausedAfter=false timerAdvanced=true displayedStatus='Blink paused' displayedButton='Resume'` through actual DOM/timers. Physical gestures remain observation. Resuming an initially running Blink after pan is valid; optional report scope bounds impact.

### F-013 — Keep-local transfer preview claims unapplied changes

**CONFIRMED · confirmed defect · S3 · high · K3/K4 · J10.** review_state `:274–300` counts unequal incoming records before selected policy, but candidateFor keeps conflicts locally; display/announcement `:454,:461`. P-07: both policies preview change1/unchanged0; Keep local actual full-record delta=false, local note retained. Harness `:87–89` currently asserts that mismatch.

Derive the selected candidate once, compute preview deltas from it, retain validation/atomic apply/quota/identity rollback proof. Alternative input-conflict census needs a distinct label, not Change. P-16 actual Chrome File/controller control confirmed `preview='Add 0 · Change 1 · Remove 0 · Unchanged 0' actualChanged=false note='controller local note'`. Verify deltas under merge/replace/conflict choices. No data loss; apply is correct, preview is wrong; native file picker is not certified.

### F-014 — User label changes warning severity

**CONFIRMED · confirmed defect · S3 · high · K3 · J4/J7/J8.** phase_alignment `:131`→alignment `:115,:123` includes label in warning string; CLI output `:789–793` reparses any substring skipped and renders muted skip glyph `:848–851`. P-08 same unapplied result: neutral label severity=warning, `Encode skipped frames` severity=skipped.

Status should be explicit or parsed only from a bounded owner grammar, preserving public warning text/JSON and post-action deduplication. Verify identical operation with adversarial ordinary label plus genuinely skipped control. Full text/headline remain accurate and trim authority unchanged; bounded human-status defect, not alignment failure.

### F-015 — Manual alignment summaries claim audio applied

**CONFIRMED · confirmed defect · S3 · high · K3 · J4/J7.** phase_alignment `:295–303` and alignment_presentation `:260–280` classify every applied result as audio. P-09 valid manual +0/+12 without audio attempt: detailed panel says Manually confirmed alignment, both summaries say audio applied. Complete manual reuse reaches durable branch; pre-review invocation for every reused case is not claimed.

Use neutral alignment applied at both owners; retain review count/unavailable text. Verify manual zero/nonzero, computed/cache and review controls. Correct detailed projection/duration retention mitigate; no trim/cache/JSON authority defect. A new provenance projection is only warranted if product requires richer short summaries.

### F-016 — Orphan color policy drifts while mock proof stays green

**CONFIRMED · subjective maintainability concern · S3 · high · K12/K18 · J12 convenience surface.** vs/color `:131–145` assumes RGB=0; facade `vs/__init__.py:30–33` and API docs expose it. P-10 actual R81 tiny RGB24 BlankClip: RGB=2, returned same node, output(16,235,16), expected(0,255,0). `tests/vs/test_color.py:32` mocks0. Whole-repo caller search finds family/facade/tests/docs only. Active encoders `:336,:357`, tonemap_conversion and props own actual rendering.

Concrete burden: maintaining/exporting/testing a second unused conversion policy creates false confidence during runtime upgrades. Remove orphan family/unused ColorProps/exports/incidental tests and regenerate API after real-consumer audit; retain active pixel/range proof. If a real consumer exists, migrate deliberately or retain with native proof; no speculative shim. Not a demonstrated CLI screenshot defect or stable API break under the convenience-surface contract.

### F-017 — Contract offers a nonexistent wizard upload toggle

**CONFIRMED · confirmed defect (doc bug) · S3 · high · K12 · J1/J6.** contract `:1013–1015` says upload can be enabled through wizard; `cli/wizard_command.py:145–176` only prompts paths/reference/goal, first-use auto_upload=false. P-11 real PTY wizard: those prompts, review disabled publishing, saved false, exit0.

Remove stale wizard enablement claim and point to config/environment/presets, preserving current privacy-first wizard scope. No media/network test needed. Other guide/wizard paragraphs are accurate; no publishing code failure or added feature implied.

### F-018 — Report date contract disagrees with localized header

**CONFIRMED · confirmed defect (doc bug) · S3 · high · K3 · J10.** contract `:990–992` promises date-only/no timezone conversion; renderer `:459–470`→viewer `:52,:356–362`→viewer_format `:33–37` uses localized Intl date/time. P-12 TZ NewYork: UTC `2026-09-04T00:30:00+00:00` becomes `Sep 3, 2026, 8:30 PM`.

Reconcile prose to existing local date/time; verify formatter/initialization and preserved ISO tooltip/payload. No timezone product change requested. Exact recorded timestamp remains available; no persisted-time corruption or browser-layout claim.

### F-019 — Guides disagree on offscreen evidence tier

**LIKELY · inferred risk (documentary inconsistency) · S3 · high for source inconsistency · K5/K18 · J4/J11.** route-comparison `:75–77` and audio-alignment `:202–204` say static-only/unverified execution; Docker environments `:119–125`, supported runtime and 10-07 handoff `:200–228` record real generated three-source offscreen session/frame0/panel/sidecar/cleanup proof.

Reconcile exact historical identity/tier; distinguish Linux-container offscreen from unverified X11 wrapper/visible desktop. Raw historical logs were not authenticated and no current GUI gate was rerun, so LIKELY is retained. Experimental-route status and correct linked details mitigate. Do not replace conservative wording with a broad current-platform verified claim.

### F-020 — Fastest/cache-only guide omits metrics condition

**CONFIRMED · confirmed defect (minor doc overstatement) · S4 · high · K11 · J2/J3.** sources-and-labels `:38–40` states blanket incompatibility. P-13 installed dry-run JSON from scratch: fastest+cache-only random-only exits0/metrics_required=false; adding dark frame exits4/FC-3014. `cli/dry_run.py:146–150` guards validation with needs_analysis.

Add when metrics are required. No code change; existing context already discusses metrics, limiting burden. 33 TOML snippets validating does not establish their media behavior.

### F-021 — Terminal assertion depends on checkout/temp path width

**CONFIRMED · confirmed defect (verification portability) · S3 · high · K18 · J12 developer verification.** Native gate failed `tests/orchestration/test_alignment_report.py:519–520`: it searches captured Rich output for the entire contiguous tmp pathname. Renderer `orchestration/alignment_report.py:219–227,242–258` prints correct path rows through width-bounded tables; `orchestration/presentation.py:13–16` caps width180. The approved deeper basetemp makes the path wrap, so the suite fails despite retaining path text.

Use a controlled path fixture when filesystem I/O is irrelevant, or a faithful assertion that accounts for actual wrapping while retaining source-path/row-zero obligations. Verify representative narrow/wide output and long paths without merely increasing global width. The failure is observed in the once-only native baseline; the exact same test/source passed using the shorter approved `.tmp/comprehensive-review-2026-10-08/n` basetemp (.611s). This isolates path depth rather than a product-code fix. No media/output-data loss. Ordinary shorter default temporary paths mitigate, but safe output relocation and longer checkouts recur.

Additional production-renderer observation `uv run --no-sync python .tmp/comprehensive-review-2026-10-08/probes/controller/probe_path_wrapping.py` exited0 in.313s: `path_length=243 contiguous=false all_path_characters_preserved_across_table_wrap=true`. It captured actual human output and stripped only whitespace/table vertical separators to verify the synthetic path's characters survive wrapping. This is diagnostic evidence for the assertion, not a proposed general normalization rule that removes arbitrary path characters.

## Adversarial calibration / rejected candidates

| Candidate | Disposition and evidence |
| --- | --- |
| Manual confirmed=false proves unaccepted authority | Removed. Explicit manual file is authoritative; field documents confirmation of computed offset; shipped writer only emits true. Phase probe actually applies false/true/zero and rejects source drift, but no draft-producing supported path violates contract. |
| Missing reference FPS fallback is production retiming S2 | Removed. Sole production caller supplies effective FPS; convenience-only omitted value lacks documented entrypoint. No current recurring caller burden established. |
| Fake NeverExits proves unreaped VSView | Removed. Invented refusal of all waits/signals is not OS evidence; real bounded child reaped. Physical escalation remains observation. |
| Runtime/raw wizard redaction mismatch | Removed. Explicit wizard contract requires all raw Pydantic inputs redacted; general runtime keeps nonsecret diagnostics. |
| Infinite minimum window crashes | Removed from F-005. Probe returns full window. HTTP/process infinity consequences parked, not asserted. |
| Finite viewer Promise map means unbounded exhaustion | Removed. Bounded by finite payload; no retained decoder amplification, workload failure or heap degradation established. |
| TMDB cache thread writes after cancelled coroutine | Mechanism observed (~.168s); not material. Valid successful low-level response cache is independent of final-match authority, locked/atomic, and CLI asyncio.run drains executor before process exit. No discard promise, corruption, post-exit write or supported caller burden demonstrated. |
| No response-size cap means S2 service failure | Downgraded to low-confidence abnormal-service budget observation. Fixed origins/page1/planner/concurrency/finite normal responses mitigate. No real service/stress failure or agreed resource threshold. |
| Native guide promises renderer from uv sync alone | Removed. Prior explicit FFmpeg/VS/L-SMASH/placebo/Vulkan prerequisites are present. |
| Historical workflow/profile implies active old orchestration | Removed. Provenance/history is labelled; canonical shared skills govern current responsibilities. No duplicate tracked skill body found. |
| Windows incompatible rollback is LIKELY | Independent VW3 downgraded. Missing guard is traced, but supported complete B overlay retaining authentic A backup is unresolved. Source builder clears output and reinstall test uses replacement directory. D-03/O-03 settle reachability; not in accepted package count. |

## Verification ledger and limits

Final measured gate results, skips and exact controller commands follow below. Scratch logs/probes are ignored and may disappear; the excerpts and commands here are the durable evidence. No green baseline command resolves the independently reproduced defects.

## Probe index

Prefix `S` below means `.tmp/comprehensive-review-2026-10-08/probes`. Commands use existing tooling without sync, filtered application environment, no bytecode and owned temporary paths. Python import-helper probes use `PYTHONPATH=<repository root>` where required. Per-probe parent durations are wall time; child focused counts overlap native coverage and are not added to total suite counts.

| Evidence | Probe path / exact command after environment prefix | Purpose / observed result |
| --- | --- | --- |
| P-01 | `uv run --no-sync python S/R1/probe_reviewer_v1.py` | .572s, exit0; manual false/true/zero applied expected trims, drift rejected; FPS false-positive calibrated |
| P-02 | `uv run --no-sync pytest -q -s -o addopts='' -p no:cacheprovider --basetemp=S/controller/v2-tmp S/R2/test_reviewer_lifecycle.py` | 4 passed in1.25s; cwd import, first-SIGINT native wait/render/coordinator failure observations quoted above; actual signal/child/writer boundaries |
| P-03 | `uv run --no-sync python S/R3/reviewer_probe.py` | 6.431s parent, exit0; invalid encoding/NUL, inf window and oversized history/cache reproduced with valid controls |
| P-04 | `uv run --no-sync python S/V5C/probe_verifier_ownership.py` | .224s, exit0; two copied-script fakeDocker exit17 cases delete old sentinel before work |
| P-05 | `uv run --no-sync python S/V5C/probe_ci_guards.py` | <.01s parent; omitted/matched path controls, aggregate all-success/eight one-job failures, release notes fail-closed controls |
| P-06 | `uv run --no-sync python S/V5C/supplemental-context-probe.py` | exit0; simple ignore-rule negative control, no actual context/image claim; metadata-only aggregate described in F-009 |
| P-07 | `uv run --no-sync python S/R4/run_v4_state_probe.py` | .185s, exit0; production JS + synthetic DOM/timer, both Blink cases and conflicting review preview |
| P-08 | `uv run --no-sync python S/R7/warning_projection.py` | .280s, exit0; same warning changes style/status with label |
| P-09 | `uv run --no-sync python S/R7P/probe_alignment_summary.py` | .865s, exit0; manual zero/nonzero/reuse summaries, correct reviewed control |
| P-10 | `uv run --no-sync python S/R7/color_native.py` | .119s, exit0; actual R81 one-frame16×16 BlankClip range failure; no media decode |
| P-11 | `uv run --no-sync frame-compare wizard --root S/V6D/wizard-workspace` | Real PTY, Enter paths/reference/random and y confirmation; exit0, saved auto_upload=false; elapsed not captured |
| P-12 | `uv run --no-sync python S/V6D/timestamp_probe.py` | .186s parent, exit0; locked Node formatter localized prior-day date/time |
| P-13 | `uv run --no-sync python S/V6D/docs_recipe_probe.py` | .635s parent, exit0; 33 TOML schema controls, no-metrics exit0 vs metrics FC3014 |
| P-14 | `uv run --no-sync python S/V2N/privacy_probe.py` | 2.123s parent, exit0; navigation/metadata decode/image transport structured tracebacks redacted |
| P-15 | `uv run --no-sync python S/R7/workflow_structure.py` | exit0; 16 references resolve, four shared bodies, eight presets/two configs parse, no repo-local bodies |
| P-16 | `uv run --no-sync python S/controller/probe_v4_browser.py` | Initial custom-profile launcher timed out at30s (30.360s wrapper). Scratch-only control reused the existing `_run_browser_dump` launcher: exit0,2.091s, actual Chrome DOM/timer/File confirmed both F-012/F-013. Physical gestures/file picker remain unproved |

Expand `S/` to the literal prefix above when running a command. The full-suite/static/Docker/docs commands below give exact unabridged controller invocation arguments. Probe setup errors (missing helper imports, incomplete synthetic diagnostic layout/DOM stubs, initial nested basetemp, shell glob quoting) were corrected only in scratch or invocation, and never treated as product defects. V5W's initial 35pass/9setup-error run was corrected; later43pass/1skip plus all9SHA controls and20builder source contracts ultimately cover64 distinct contracts. The original skip reason was not captured, so it is not invented. V4's84 passes and V3's101 passes were reused at unchanged source with explicit collection audits, not claimed as fresh reruns.

### Final measured results

Provisionally accepted findings: **21** — **17 CONFIRMED, 4 LIKELY**; **10 S2, 10 S3, 1 S4**, no S0/S1. Types: 16 confirmed defects, four inferred risks and one subjective maintainability concern. Six HYPOTHESIS/insufficient-data mechanisms are parked (O-03–08: one conditionalS2, fourS3 ceilings, oneS4); acceptance gaps for known findings are not extra defects. Counts do not add duplicate child/probe observations.

The native baseline is **not green**: F-021 is the sole failure. A shorter-path focused control passes but does not erase the original failure. Docker is green for its managed selection and actual local architecture. The browser baseline included17 passing cases (14 actual generated-report cases and3 launcher-behavior cases). Additional Chrome control confirms F-012/F-013; no full smoke replay was needed.

All measured commands were captured by `uv run --no-sync python .tmp/comprehensive-review-2026-10-08/probes/controller/run_gate.py [--cwd <recorded cwd>] <gate> -- <command>`. Wrapper set no-bytecode, approved TMPDIR/cache/E2E/media paths, filtered product/secret-bearing application environment selectors and used Compose project frame-compare-review-20261008. Outer invocation likewise used no-bytecode/no-sync. Default cwd was repository root; Docker cwd was the fresh owned tracked-HEAD archive, import-negative cwd the isolated source copy. Wrapper source/log/JSON lives under approved scratch, not product.

| Gate | Exit | Seconds | Result |
| --- | --- | --- | --- |
| pyright | 0 | 11.674 | 0 errors/warnings |
| ruff-check | 0 | 0.139 | passed |
| ruff-format | 0 | 0.099 | 514 already formatted |
| bandit | 0 | 1.855 | medium/high gate passed; 22 low issues reported, 7 explicitly disabled potential issues |
| imports | 0 | 0.200 | 2 kept / 0 broken |
| api-docs | 0 | 0.084 | no drift |
| cli-docs | 0 | 0.669 | 3 passed |
| native | 1 | 42.563 | 3123 passed / 1 failed / 90 skipped; 2 deliberate deselections |
| path-control | 0 | 0.611 | same failed assertion passed with shorter owned basetemp |
| docker | 0 | 420.038 | 276 passed / 0 nonpassing; native/production/mount proofs |
| image-sentinel | 0 | 0.243 | present=True in production image without bind |
| container-tooling | 4 | 0.806 | collection failed: test image lacks PyYAML; no cases ran |
| container-tooling-control | 0 | 0.888 | 2 unchanged cases passed with borrowed existing pure-Python PyYAML source |
| browser-probe | 1 | 30.360 | custom-profile launch TimeoutExpired at30s |
| browser-probe-control | 0 | 2.091 | actual Chrome DOM/timer/File confirmed both viewer defects |
| imports-negative | 1 | 0.252 | expected exit1, deliberate config→CLI edge broke layering |

Exact underlying command arguments (shell-quoted representation of recorded argv; commands already executed, not a request to run):

```text
pyright: uv run --no-sync pyright --warnings
ruff-check: uv run --no-sync ruff check .
ruff-format: uv run --no-sync ruff format --check .
bandit: uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
imports: uv run --no-sync lint-imports --config importlinter.ini --no-cache
api-docs: uv run --no-sync python scripts/generate_api_docs.py --check
cli-docs: uv run --no-sync pytest -q -p no:cacheprovider --basetemp=.tmp/comprehensive-review-2026-10-08/probes/controller/cli-docs-tmp tests/test_cli_contract_docs.py
native: uv run --no-sync pytest -q -n4 --dist loadgroup -p no:cacheprovider --basetemp=.tmp/comprehensive-review-2026-10-08/probes/controller/native-tmp --junitxml=.tmp/comprehensive-review-2026-10-08/probes/controller/gates/native.xml '--deselect=tests/workflows/test_docker_gui_contract.py::test_verify_docker_gui_production_tooling_route[absent]' '--deselect=tests/workflows/test_docker_gui_contract.py::test_verify_docker_gui_production_tooling_route[uv-present]'
path-control: uv run --no-sync pytest -q -p no:cacheprovider --basetemp=.tmp/comprehensive-review-2026-10-08/n tests/orchestration/test_alignment_report.py::test_emit_frame_alignment_report_verbose_retains_row_zero_frames_and_paths
docker: bash tools/verify_docker_integration.sh
image-sentinel: docker run --rm --network none --entrypoint python frame-compare:dev -c 'from pathlib import Path; p=Path('"'"'/home/framecompare/frame-compare/.tmp/review-output.bin'"'"'); print('"'"'production_scratch_sentinel_present='"'"'+str(p.is_file()))'
container-tooling: docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e TMPDIR=/home/framecompare/frame-compare/generated/verifier-tmp -v /Users/tristan/Software/frame-compare/.tmp/comprehensive-review-2026-10-08/probes/controller/docker-source:/home/framecompare/frame-compare -w /home/framecompare/frame-compare --entrypoint python frame-compare:test -m pytest -q -p no:cacheprovider --basetemp=/home/framecompare/frame-compare/.tmp/tooling-tmp 'tests/workflows/test_docker_gui_contract.py::test_verify_docker_gui_production_tooling_route[absent]' 'tests/workflows/test_docker_gui_contract.py::test_verify_docker_gui_production_tooling_route[uv-present]'
container-tooling-control: docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/home/framecompare/frame-compare/.tmp/probe-dependencies -e TMPDIR=/home/framecompare/frame-compare/generated/verifier-tmp -v /Users/tristan/Software/frame-compare/.tmp/comprehensive-review-2026-10-08/probes/controller/docker-source:/home/framecompare/frame-compare -w /home/framecompare/frame-compare --entrypoint python frame-compare:test -m pytest -q -p no:cacheprovider --basetemp=/home/framecompare/frame-compare/.tmp/tooling-control-tmp 'tests/workflows/test_docker_gui_contract.py::test_verify_docker_gui_production_tooling_route[absent]' 'tests/workflows/test_docker_gui_contract.py::test_verify_docker_gui_production_tooling_route[uv-present]'
browser-probe: uv run --no-sync python .tmp/comprehensive-review-2026-10-08/probes/controller/probe_v4_browser.py
browser-probe-control: uv run --no-sync python .tmp/comprehensive-review-2026-10-08/probes/controller/probe_v4_browser.py
imports-negative: uv run --no-sync lint-imports --config /Users/tristan/Software/frame-compare/importlinter.ini --no-cache
```

Docker source was extracted from `git archive 58e50a6d48c0004b63f60b9b3ba53c1ac4b31537` into `.tmp/comprehensive-review-2026-10-08/probes/controller/docker-source`; no branch/worktree/index write. The harmless .tmp sentinel was the sole intentional extra context input at build time. Local build permitted cache reuse; do not claim cold rebuilding every native dependency. Actual markers: R81/API4.3, L-SMASH1310, FFMS2 5.0, placebo2.0.4, source tracked-tree provenance, shared-library/obuparse linkage, software Vulkan, h264 limited/full, VFR, interlaced, HEVC10 HDR, AV1, real frames via both decoders/placebo, production tooling absent, application run and generated mount containing report/screenshots/run info/result/generated config/analysis+probe caches. Managed test selection took400.29s of420.038s total. It rejects skipped/xfailed/xpassed. No physical device/display/amd64 acceptance follows.

Two native-deselected unchanged GUI tooling cases passed in a network-disabled disposable Linux container namespace. First collection found PyYAML absent in the intentionally minimal test image (exit4, no cases). Rather than install/sync/change image dependencies, the controller copied only the existing host PyYAML pure-Python source into approved scratch, excluded binary extensions/bytecode and set that probe PYTHONPATH. Both cases then passed (.888s). This is borrowed dependency source for a test harness, not a rebuilt managed image or GUI runtime pass. Their fixed /tmp writes belonged to the disposable container and did not touch host /tmp.

Import enforcement negative control used a copied source tree and appended one forbidden `import frame_compare.cli.entry` at config/__init__.py:9. Real lint-imports reported 180 files/721 dependencies, Layered Architecture BROKEN with that exact edge, Domain Independence KEPT. Unmodified source had720 dependencies and both contracts KEPT. Live source was never edited; scratch controls remain isolated.

Controller process deviation: the initial additional Chrome command had not completed when Docker verification was started, creating a brief overlap contrary to the requested serial-heavy rule. It ended at its30s deadline; no owned Chrome process remained. The native suite, Docker/media gate, successful browser control and docs gate otherwise ran without another review heavy gate overlapping. Focused cheap controls ran under the prompt's cheap-work exception. Earlier preliminary nested delegation and possible incidental ignored bytecode from one child command lacking no-bytecode were also disclosed; none produced a tracked source change. No current scoped gate result is presented as stronger because of these deviations.

### Native skip accounting

JUnit has3214 result entries, including four collection-level skips:3123 passed,1 failed,90 skipped. The90 skips are:

| Count | Reason / proof boundary |
| --- | --- |
| 4 | L-SMASH unavailable (collection-level integration modules) |
| 6 | media E2E opt-in unset; actual media later ran in Docker |
| 3 | continuous alignment resource opt-in unset |
| 1 | live webhook opt-in/URL absent |
| 1 | live passive slow.pics opt-in absent |
| 1 | native libplacebo unavailable; required managed proof later ran in Docker |
| 1 | PowerShell7 required for builder regression |
| 27 | Windows PowerShell process semantics required |
| 1 | Windows with PowerShell required for generated launcher |
| 3 | Windows process-tree semantics required |
| 1 | Windows user-PATH install/uninstall semantics required |
| 39 | pwsh/powershell unavailable |
| 2 | Windows portable launcher PATH process semantics required |

Two native tooling parameter cases were deliberately deselected, not skipped/pass; their separate container proof is above. No native browser skip occurred. Selected gate logs preserve exact node IDs and reasons; grouping here loses no reason category. The full-suite command first failed in zsh before execution because unquoted brackets globbed; corrected quoting started the single actual suite. Probe/control setup failures are not product findings.

### Commands intentionally not run

- Separate full browser smoke: already included once in the native suite; only the distinct defect-specific control followed initial launcher failure.
- Native media-opt-in/real generated comparison: native L-SMASH/placebo unavailable, so managed Docker supplied the actual media tier; no simulated native pass.
- Three-hour streaming-resource gate: no accepted finding concerns whole-track RSS/admitted lag/paired collector cleanup; canonical Docker explicitly excludes it and native3 resource cases skip. O-12 records exact later trigger/command.
- Docker NVIDIA/X11/visible GUI and amd64: unavailable target device/desktop/architecture; O-11/O-12.
- Physical Windows5.1/portable/GPU/visible review, authenticated full artifacts, signing and predecessor migration: no Windows/PowerShell target; O-01–05/O-14. Source contracts are not acceptance.
- New wheel/sdist build and fresh installed-environment recipe: no distribution regression candidate required it and environment mutation/install was prohibited. Existing distribution negative controls and actual installed help/version were exercised; no new artifact integrity certification.
- Dependency sync/lock/update or advisory download: expressly prohibited environment mutation and no new dependency finding; static pins/lock/release guards were reviewed, not a claim of current advisory-free dependencies.
- Hosted CI dispatch/PR, protected environment/production signing/publication, real-credential slow.pics/TMDB/webhook: unauthorized external action/live context absent; O-13. Unauthenticated doctor status is not service acceptance.
- Disk-full/exhaustive media/native fault matrix, OS accessibility/filepicker, legal release approval and every line of vendor/generated/test code: beyond executed evidence; concrete future observations above. No exhaustive correctness claim.

### Strict documentation result and final state

The installed docs group was used without sync. First scratch-config invocation failed before building because docs_dir pointed outside its project root (exit1,.259s). Moving the faithful docs copy inside that root but retaining absolute directory settings triggered a Zensical Rust RootDir invariant panic (exit1,.317s), a harness/configuration failure rather than a report-link defect. The final control used a byte-identical copy of repository `zensical.toml` with its original relative `docs`/`site` settings and a faithful owned `docs` tree including all four reports. No product configuration was edited.

Exact successful command: `uv run --no-sync zensical build --clean --strict`, cwd `.tmp/comprehensive-review-2026-10-08/probes/controller`, captured by `run_gate.py --cwd <that absolute path> --timeout 120 docs-canonical -- ...`. Exit0,1.346s wall time; output `Build started / No issues found / Build finished in 1.10s`. All four review HTML pages exist under the owned site tree. This is the sole actual canonical site build; earlier two invocations failed during setup before site construction. This final result annotation follows the built report snapshot and introduces no local Markdown source links. No docs deployment occurred.

Final source identity: `58e50a6d48c0004b63f60b9b3ba53c1ac4b31537`; tracked/staged diffs empty, `git diff --check` clean. Git status:

```text
?? docs/prompts/
?? docs/reviews/
```

`docs/prompts/` is the preexisting user-supplied prompt. The only newly authored untracked deliverables are this review's four Markdown files beneath docs/reviews/comprehensive-review-2026-10-08. Approved scratch contains the probes/logs/owned source/docs copies and generated verification outputs. No restore, commit, stash, branch, push, PR, fix or release was performed. Review is complete; remediation remains an unapproved draft.
