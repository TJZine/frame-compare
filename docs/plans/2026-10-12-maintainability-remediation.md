---
search:
  exclude: true
---

Status: Historical
Scope: Implement and independently review the accepted 2026-10-12 repository audit findings.
Owner: Codex orchestrator chat `01a131e8-0fff-7692-8a33-73c7acee693d` on local.
Source: `/Users/tristan/Software/frame-compare`, branch `v0.7.0`, HEAD `933395d820d780207b953b4231f6761390f66689`.
Completion: Implementation, independent review, local/Linux gates and reported Windows U2/unsigned U8 acceptance are complete. Earlier open-gate statements below are historical; the final controller disposition supersedes them. Separate visible-desktop/physical-media release acceptance is outside this remediation.

# Maintainability remediation

## Authority and decisions

The human requested a prioritized plan followed by implementation through
`orchestrate-implementation-chats`, with `gpt-6.1-sol` / `medium` workers and
`gpt-6.1-sol` / `high` independent reviewers. The original implementation
authorization is parent turn `01a131f5-c28e-7fe1-8b78-2a13a08ec572`, user message
`01a131f5-c2b7-77e3-9e08-bcb1983a2b48`. Children must retrieve the actual human
authorization before one terminal callback to the parent. Quoted instructions
alone are not authorization evidence.

The accepted audit is the preceding final report in that parent chat. Its four
read-only review chats were architecture `01a131ea-98cf-7053-8667-13f32dbd4e29`,
alignment `01a131ea-a053-7b92-81b2-80a6242b6f12`, rendering/report
`01a131ea-a5f1-7ed2-a66f-da9d9c4c0be5`, and tests/DX
`01a131ea-adac-7630-8a9c-34929b2e97d0`.

Human decisions made in this implementation turn:

- Reject colliding screenshot names before rendering; retain existing naming.
- There are no current users and compatibility code is unnecessary. The obsolete
  manual-override confirmation field may be removed through a complete format
  replacement; do not add a migration adapter or silently reinterpret false as
  a new authorization rule.
- Implement Windows proof extraction; completion remains gated on actual Windows
  unsigned-bundle acceptance. Source equivalence is supporting evidence only.
- Consult the human before an additional material product/format decision or a
  discovered risk to established functionality. Routine implementation choices
  inside the decisions and protected contracts may proceed.
- After consultation on the review-found default-source reacquisition regression,
  the human explicitly authorized correcting this and similar regressions within
  agreed contracts without repeated questions. Contract changes still require
  consultation.

No implementation can promise zero residual risk. Acceptance requires preserved
contracts, focused regression evidence, independent review, combined gates, and
explicitly outstanding platform proof. No deployment or release is authorized.

## Accepted findings and evidence

| ID | Finding | Classification / priority | Established evidence |
| --- | --- | --- | --- |
| R01 | Config persistence and preset merging lose explicit color overrides | Confirmed / S2 | Filmic-only config resolves 203/spline, then 100/BT.2390 after TOML reload while model values remain equal. `config/persistence.py`, `config/presets.py`, `render/prepare.py`. |
| R02 | Config acquisition leaks untyped failures and accepts directories | Confirmed / S2 | Malformed section environment JSON yields exit 1, traceback, empty JSON stdout; selected directory yields default config; controlled TOML read denial leaks PermissionError. `config/loader.py`, `schema_sources.py`. |
| R03 | Output-name collision ignores filesystem case equivalence | Confirmed mechanism / S2 | Movie.mkv/movie.mp4 pass source and batch validation, producing case aliases for one frame. `render/batch/expansion.py`, `render/naming.py`. Actual Windows writes unverified. |
| R04 | Video scoring admits reads after cancellation | Confirmed / S2 | Production motion/base scoring with an instrumented node admits 7/5 additional reads after the first sets cancellation. `services/alignment_video.py`. Native drain timing unverified. |
| R05 | Cache-only second-read failure can report partial success | Confirmed / S2 | Existing orchestration fixtures: valid cache yields 2 frames/4 screenshots; deletion before second read yields success, 1 frame/2 screenshots, cache status skipped. `orchestration/execution.py`. |
| R06 | Native note limit counts code units, model counts scalars | Confirmed contract mismatch / S3 | `report/renderer.py` emits maxlength=1000; `review_state.js` accepts 1000 Unicode scalars. Native-input symptom needs browser proof. |
| R07 | Immutable evidence projection is rebuilt on preview callbacks | Inferred performance risk / S2 | `vsview/alignment_review_panel.py` repeats full presentation builds; `utils/alignment_review_projection.py` rescans intervals per segment. Runtime impact unmeasured. |
| R08 | CLI persistent overrides have repeated DTO/projection copies | Maintenance / S3 | `cli/entry.py`, `run_command.py`, `orchestration/types.py`, `config/overrides.py` require matching copies. |
| R09 | Python Windows runtime proof is embedded in PowerShell | Maintenance / S3 | 549-line Python string at `build_portable.ps1:932`; textual tests freeze local names/indentation. Real bundle execution must remain. |
| R10 | Viewer/lens/grid tests own divergent DOM fakes | Maintenance / S3 | Three harnesses differ in once listeners, tree containment, focus, and dispatch semantics. |
| R11 | ManualOverride.confirmed has no application semantics | Maintenance / S3 | Parser retains false; application ignores it; current native writer always true. |
| R12 | --no-cache help disagrees with scoped-refresh behavior | Documentation / S3 | CLI help claims disabled reads/writes; implementation and CLI contract delete/recompute only the current scoped entry. |
| R13 | EncoderSettings exposes unused format/bit_depth knobs | Informational maintenance / S4 | No production reads; actual PNG/RGB writer behavior is fixed. Verify all consumers before removing. |

Do not promote file size, test count, or optional tool absence into new findings.
Keep the useful domain boundaries, typed phase outputs, alignment authority,
canonical evidence parser, and source-routing instructions.

## Protected behavior and shared ownership

- Work in the active checkout. Workers must not switch branches, create worktrees,
  stash, reset, stage, commit, push, open PRs, or publish. The controller owns Git.
  The human subsequently authorized proper commits for all remediation changes;
  the controller will create coherent conventional commits after applicable checks,
  excluding unrelated work. The human subsequently authorized pushing committed
  changes to `origin/v0.7.0` for a Windows-machine pull and requested a Windows Codex
  handoff. PR creation and release remain unauthorized.
- Preserve the unrelated dirty documentation-refresh capture-spec/pages-reference,
  untracked documentation redesign assets/plans/prompts, and `.claude/launch.json`.
- Preserve runtime-free help/version, typed sanitized errors and documented exits,
  JSON-clean stdout, deterministic names/artifacts, source identity, frame signs,
  valid zero offsets, bounded authority, cleanup, injected-resource ownership,
  secret stripping, atomic persistence, and supported platform profiles.
- Workers edit only their assigned files and associated focused tests. Ask the
  controller before crossing ownership or changing a public/persisted contract
  beyond the decisions above. No compatibility scaffolding without a real consumer.
- The controller owns this plan, `docs/current-architecture.md`,
  `docs/current-cli-contract.md`, `docs/ENGINEERING_RUNBOOK.md`, `docs/api.md`,
  CHANGELOG, global configuration, and all combined/native/Docker gates. Workers
  return exact documentation proposals rather than editing shared documents.
- Run scoped tests and format only owned files. No full-suite, global formatter,
  dependency sync, Docker verifier, Windows build, or common browser-profile run
  in a child without explicit resource assignment. Do not mutate shared caches.
- Shared source state is not an enforced sandbox. Ownership and final stable
  verification prevent conflicting writes; review must identify the actual diff.

## Prioritized packages

| Package | Findings | Write ownership | Dependencies and acceptance |
| --- | --- | --- | --- |
| U1 Config semantics/acquisition | R01, R02 | config persistence/presets/loader/schema_sources and focused config tests; required secret/error normalization callers only by transfer | First priority; pure resolver roundtrip, typed CLI boundaries. U7 waits for U1. |
| U2 Screenshot output identity | R03, R13 | render naming/batch expansion/types/errors and focused render/source-selection/error tests | Human chose typed refusal. Controller transferred render/errors.py for a dedicated actionable ProcessingError subtype; no other error/registry owner transfer implicit. Independent of U1. |
| U3 Video cancellation admission | R04 | alignment_video and its scoring/freshness tests | Before EACH get_frame, preserve numerical scoring and existing cancellation result semantics. |
| U4 Required cache-only analysis | R05 | orchestration execution and focused cache-mode/phase tests | Fatal required-cache acquisition, ordinary degradation preserved. |
| U5 Report editor and harness ownership | R06, R10 | report renderer/review_state, three DOM harnesses, narrow test fixture, report tests and native-input browser scenario | Preserve schema and browser interaction; narrow shared fixture, no broad DOM framework. Browser ownership exclusive to U5 until returned. |
| U6 Static native review presentation | R07 | vsview alignment_review_panel and panel tests | Derive once per immutable comparison/workspace lifecycle. U3/U6 may share one worker with disjoint files. No projection algorithm rewrite without measured need. |
| U7 CLI override transport | R08, R12 | cli entry/run_command/output/dry_run/contracts, orchestration types/preparation and real request callers, config overrides and associated CLI/config/orchestration tests | After U1/U4 ownership returns. One typed override value plus run-mode controls; no reflection/framework migration. Correct help only, preserve cache semantics. |
| U8 Python-native Windows proof | R09 | build_portable.ps1, new Python proof source, focused portable/workflow tests, portable source inclusion if needed | Human allows implementation; actual unsigned Windows bundle, generated VSView and lifetime proof required for acceptance. No signing/release. |
| U9 Manual override format replacement | R11 | alignment_manual_overrides, native writer alignment_vsview, related override/workflow tests | Remove obsolete field and replace format deliberately, no legacy migration. Preserve confirmed native result authority and valid zero/manual precedence. May share native worker after U3/U6. |

### U1 design and proof

Preserve explicit color semantics through write/reload and partial preset apply.
Full persisted defaults elsewhere and secret-stripping remain intentional; do not
blindly apply exclude_unset to every serializer. Use a coherent config-owned
explicitness merge policy where it avoids duplication. Compare all presets,
explicit values equal to defaults, unrelated overrides, and persisted reload.
Translate source SettingsError/OSError at acquisition; require selected readable
regular-file input while retaining intended symlink behavior. Do not expose raw
environment/secret values in error chains or JSON. Verify missing/invalid UTF8/TOML,
directory, read failure, section/list environment JSON, correct exit/stream routes.

### U2 design and proof

One owner validates final generated output identity before native preparation or
render admission, including shortened names and ASCII case aliases. Keep display
labels and selector semantics unchanged. Refuse with a typed actionable error;
do not rename screenshots. Preserve valid naming on all supported output profiles.
Use existing meaningful collision tests plus source-to-render regression. Actual
case-insensitive Windows output proof remains distinct. Remove unused encoder
fields only after proving no real caller; preserve actual PNG/bit-depth behavior.

### U3/U6/U9 design and proof

Cancellation guards must operate before each get_frame, including hypotheses;
only already-in-flight native calls may lack a finite drain bound. Preserve
decision authority, result/freshness, scores, offsets, retained frames and cleanup.
Use admission-count negatives and retained algorithm/freshness tests.

Cache immutable review presentations per comparison at workspace activation;
invalidate on workspace identity/change and keep dynamic frame draft/marker state
separate. Verify callback computation counts, workspace replacement, and existing
panel behavior on large evidence. Avoid adding generic caches or changing output.

For manual overrides, remove confirmed from the record/writer/parser/tests and
declare a new canonical persisted version if format identity needs it. Retain
timestamp/offset/name semantics, manual precedence, no decoding, zero, atomic merge,
and failure distinctions. Old-version input follows existing recoverable-cache
rejection; no migration/shim. Return exact format documentation to controller.

### U4 design and proof

Required cache-only analysis cannot fall back to an initial random/user plan on
second-read missing/corrupt/version-mismatch. Use a required-phase policy or an
authoritative acquisition; preserve cache-only no-compute semantics and ordinary
optional analysis fallback. Verify valid-first/invalid-second execution and no
render/publish, not only direct phase exceptions. Preserve prevalidation before
output reservation and selection-exclusion fatal behavior.

### U5 design and proof

Keep review export schema at 1000 Unicode scalars; controller owns scalar-aware
editing. Fix native maxlength interaction without changing UI direction, import
atomicity, bounds, normalization, focus, storage or exports. Prove native insertion
of mixed/BMP/supplementary text with real browser input, not .value assignment alone.
Share only repeated DOM mechanics used by current harnesses. Retain delayed-image,
stale-generation, once-listener, focus, capture/cleanup and storage-failure proof;
do not replace focused tests with broad E2E or reimplement feature algorithms.

### U7 design and proof

Retain raw-string parsing for typed JSON-aware errors. Carry a single typed set of
persistent overrides into both effective configuration and runtime requests rather
than flattening and re-projecting matching fields. Keep run-mode controls separate,
avoid import inversion, and delete superseded internal paths/copies. Verify public
flags through runtime/effective/write-config, absent versus empty values, parsing,
interactive JSON rejection and runtime-free help/version. Internal constructors
are revisable; product config/CLI contracts remain protected.

### U8 design and proof

Extract equivalent Python proof into repository-owned source and copy/execute it
under the same bundled interpreter/environment/phase interface and cleanup.
Preserve preload-before-Qt, native plugin topology, exact markers, media validation,
whole-set result roundtrip, offscreen VSView launch, required exit codes, artifact
and license/provenance rules. Ruff/syntax checks should see the new Python source.
Replace incidental text/indentation assertions with proof contract tests while
preserving distinct ordering and actual runtime requirements. Compare original and
extracted semantic source as supporting evidence, then require real Windows build.

## Verification and review gates

Workers select focused existing tests plus genuinely missing regressions under
develop-code/verify-code. The audit baseline at the source SHA passed Ruff,
formatting, Pyright, Bandit medium/high, import contracts, and native pytest.
That baseline does not validate the changes.

Independent `gpt-6.1-sol` / `high` reviewers apply review-code to identified package
diffs, test obligation retention, maintenance burden reduction and adjacent callers.
Reviewers are read-only; reports are claims for controller adjudication. Reuse the
responsible worker for accepted corrections. A reviewer pass is not runtime proof.

Once changes are stable, run the documented full native/static/import gate once.
Run the canonical Docker verifier once for changed media-observable behavior;
Docker is available locally. No concurrent verifier runs. Full suite browser smoke
may be reused if it actually ran; U5 also needs native-input proof. Do not run the
whole-track resource module unless its actual obligation changes.

Windows/PowerShell are unavailable here. U8 remains acceptance-open until an actual
unsigned Windows bundle passes the complete applicable runbook procedure. Static
source/tests, Docker, signing and physical-host proof are different claims. Consult
the human if fulfilling the acceptance requires additional host or publication
authority; do not dispatch a signed build or publish. No residual risk is concealed.

Controller updates current architecture/CLI contract where ownership/format/error
behavior changes, and runs appropriate doc/API drift checks. Avoid unrelated docs
site redesign changes. Runtime-free generated API docs are convenience documentation,
not a reason to preserve old internal DTO constructors.

## Safety and rollback

Keep one integration owner and bounded package diffs. No releases or persistent
user-data migrations. For rollback, reverse only the package's scoped changes after
checking dependent packages; never reset the dirty checkout. U7 depends on U1/U4
semantics; U9 changes manual cache format deliberately under the no-users decision.
If a regression or review finding demonstrates an unresolved functionality risk,
hold the affected package, return evidence to the controller and consult the human
before changing the agreed contract. Continue independent work.

## Execution record

Initial dispatch and evidence will be recorded here by the controller. Numbering
prioritizes outcomes; it does not require sequential work where ownership is disjoint.

| Assignment | Chat | Model / effort | Status |
| --- | --- | --- | --- |
| Config worker U1 | `01a131fa-d84b-7b82-86d0-8bd33e191ab2` | gpt-6.1-sol / medium | Corrected source-free merges accepted by high reviewer |
| Native worker U3/U6/U9 | `01a131fa-df1f-7403-8ccc-a25620da4816` | gpt-6.1-sol / medium | High review accepted; Linux offscreen native proof passed |
| Pipeline worker U4 then U7 | `01a131fa-e742-7ba3-9e2a-f47ed2d854d7` | gpt-6.1-sol / medium | U4 accepted; corrected U7 accepted by high reviewer |
| Report worker U5 | `01a131fa-efb9-7e73-b420-d4a26520cc25` | gpt-6.1-sol / medium | High review and exclusive browser/serial full native gates passed |
| Render worker U2 | `01a131fa-f733-72c0-8366-6a3c2683dde5` | gpt-6.1-sol / medium | High review, local/Linux/Windows filesystem and combined gates accepted |
| Windows worker U8 | `01a131fa-ffaf-76e0-a0e9-b1cd11b81d00` | gpt-6.1-sol / medium | High source review and reported actual unsigned Windows bundle acceptance complete |

Do not mark this plan Historical or implementation accepted until required work
and evidence are complete. Record platform-open status explicitly if source work
finishes before Windows acceptance.

### U4 implementation evidence

Two-file scoped diff SHA256: `7746d8e8521c0ad2881f73bffd2ce1f61a59516392f7b4f73cd3583bb8ed307e`.
Analyze uses `warn_only=not request.from_cache_only`. Before the fix, the real
cache reread regressions continued render/publish and failed expected-raise checks;
afterward missing/corrupt/version-mismatch fail before render/publish/compute.
Valid cache and ordinary optional analysis controls pass. Worker observed 67
focused orchestration tests, scoped Ruff/format/Pyright, and diff check pass.
This is simulated media/orchestration admission proof, not native runtime acceptance.
Independent reviewer: `01a131fd-99e6-72f3-817f-0e98bbad4fce`, gpt-6.1-sol/high,
reviewing U4 now; reusable for U1/U7 after their source is ready.
U4 reviewer accepted the unchanged scoped diff with no material findings; observed
40 focused orchestration tests and diff check pass. Combined acceptance still pending.

U8 provenance tests may create/commit an isolated Git repository under their test
temporary directory. This is fixture setup only; shared checkout Git remains unchanged.

### U3/U6/U9 implementation evidence

Eight-file scoped diff SHA256: `b5cef9805653ee8aec345f547ee262310583b4819d88abfab4c17b981901a049`.
Every video get_frame now receives the cancellation Event admission guard. Native
panel presentation/summary/details are stored at activation and cleared on workspace
replacement/inactivity. Manual override canonical version is now "2", without the
obsolete confirmed field or migration code; native result sidecar stays v1.
Worker observed 214 focused tests without skips (offscreen Qt included), scoped
Pyright/Ruff/format and diff checks pass. Real native timing/visible GUI/Windows
acceptance remains distinct. A high reviewer was dispatched by the controller.
Native reviewer: `01a131fe-c2b1-71f3-916a-df6e31a58244`, gpt-6.1-sol/high.
Native reviewer accepted the unchanged scoped package without material findings;
observed 214 focused tests, 19 adjacent freshness/wiring tests, an instrumented
offscreen callback/dynamic draft/workspace lifecycle probe and diff check pass.
Compatible-host media/GUI and combined acceptance remain open.

### U2 implementation evidence

Seven-file scoped diff SHA256: `9a39c85a922cba2435fd1d2c88c4579559fcb6f954aa5da297580697ebd05589`.
Final paths allocated once and checked before preparation. A target-directory
temporary probe currently handles potential ASCII aliases; exact sanitized/shortened
collisions also refuse. Typed collision error is FC-4021. Unused EncoderSettings
format/bit_depth removed. Worker observed 170 focused render/error tests and scoped
Pyright/Ruff/format/diff checks pass; local volume case-insensitive behavior observed,
case-sensitive behavior simulated, actual Windows proof open. Controller must
validate Unicode filename aliases before acceptance, not assume ASCII coverage is
complete filesystem identity proof.
Controller reproduced an actual local Ç/ç samefile alias that the initial guard
accepted. U2 is reopened for accurate Unicode alias handling with filesystem-distinct
positive controls; no ASCII-only product policy is approved.
Corrected U2 supersedes the initial guard with actual exclusive final-name reservations
and physical file identities, preserving existing files and cleaning owned zero-byte
entries before preparation. New scoped diff SHA256:
`5446b2c266199081abfea1de78e4b2020582257d5605405592cff109404c7a91`.
Worker observed 180 focused tests/static checks pass, actual local Unicode alias and
distinct-name branches plus cancellation/fstat/I/O/existing/replaced-file cleanup.
Report/render high reviewer now reviews corrected U2; Windows/Linux target proof open.
High reviewer accepted corrected U2 with no material findings, observed 50 focused
filesystem/expansion/type tests without skips and a controlled cleanup-failure probe.
Final-path identity and existing-file preservation verified at source/local volume;
target-platform/native acceptance remains separate.

### U5 implementation evidence

Tracked scoped diff SHA256: `6525270d1e863660fac1b9a5cd0d597b8d9d66c169b5dd2878eef615695c0164`.
New `tests/services/dom_fixture.js` SHA256:
`43456a9da3b78d20136f05397a9c09da892a78044d65b889f028d26eace4978d`.
Textarea native maxlength removed; existing scalar controller remains authority.
Real Chrome CDP insertion proof covers mixed/BMP/supplementary/selection/overflow,
with original-maxlength negative control. Narrow common DOM mechanics extracted
from three harnesses. Worker observed 71 focused tests incl 19 browser cases without
skips, then native-insertion rerun after final helper refinement and scoped static
checks pass. High report/render reviewer dispatched; actual Windows remains distinct.
Report/render reviewer: `01a13200-6b31-77a3-b1c4-e83afc79f51b`, gpt-6.1-sol/high,
reviews U5 first; U2 review waits for corrected Unicode handling.
U5 reviewer found an actual Chrome orphan on Node outer timeout. Worker reopened
browser helper ownership: Python must terminate/reap owned Chrome across the outer
timeout, retaining trusted native input proof. Browser resource returned to U5 until
corrected terminal report; production editor/schema/DOM extraction had no other
material reviewer findings.
Corrected U5 keeps Chrome Popen ownership in Python, with finally terminate/reap
and kill fallback across Node timeout/nonzero client paths. Updated six-file diff
SHA256: `29a4e1ae3411157db4813c6910de9d0f2d1da892d1b1623280829cd82907c1c9`;
browser content SHA256: `6d326e03437d43306ad7406cda741d09e6252d52393541ce92152af2216aa231`.
Worker observed real-Chrome native input and two failure cleanup regressions pass,
plus scoped static checks and controlled SIGTERM-ignore kill/reap fallback proof.
Report/render reviewer has both corrected U2 and bounded U5 rereview packets.
High reviewer accepted corrected U5 helper, resolving the Chrome lifetime finding;
observed all three native-input/real-Chrome failure cleanup cases pass without skips.
Other U5 production/harness source is unchanged from its original reviewed identity.

### U8 implementation evidence

Tracked scoped diff SHA256: `57ef9544344e50f853f05637ff630ad7c7f6119474d63a533e66bc5a4e4c531f`.
New `tools/windows_portable/runtime_smoke.py` SHA256:
`87895932f77fe3bf30e96f5d5e135d72de6e85c864ace94babc8d58d6fae423e`.
Extracted formatted Python has exact original AST equivalence; builder copies it
into the same temporary path, preserving phase calls/environment/cleanup. Source
inventory and extracted required scripts include it. Temporary committed test source
fixtures retain actual git-cat-file provenance policy and missing-source negatives.
Worker focused build/workflow tests pass with 32 platform skips, scoped static checks
pass. Windows reviewer dispatched; no Windows/PowerShell/runtime/signing execution.
Windows reviewer: `01a13201-3049-7a40-9a36-429cf3035993`, gpt-6.1-sol/high.
Windows reviewer accepted source readiness without material findings, independently
verified exact AST/PowerShell replacement equivalence and production provenance
authority, observed focused portable/workflow/static checks with 32 platform skips.
Actual unsigned Windows bundle acceptance is still required.

### U1 implementation evidence

Tracked scoped diff SHA256: `4670e7421ad9630a861f99fe99659006c6c997fe19eb6e6f1a3b01868e8a8672`.
New color-roundtrip test SHA256:
`0f917e3c4fdeb65ba430afc0e60565b3a3e3b9ddfd2d5309c06ab4dc44c74413`;
new CLI acquisition test SHA256:
`bb087a1c0032d747a3014bda27d2e34ceff5acccd7231e16f2793e05d13e8f3f`.
Config-owned dump preserves authoredness of four preset-controlled color fields
through persistence/merge, full unrelated defaults and secret policies retained.
Regular-file config/preset acquisition follows intended symlinks and translates
source decoding/read/stat failures into sanitized typed configuration/preset errors.
Worker focused config/CLI/JSON proof and scoped static checks pass. Config reviewer
now reviews U1; U7 stays held until review and ownership return.
Reviewer reproduced an introduced partial-preset regression: omission of color
placeholder fields permits BaseSettings to reacquire unrelated default TOML values.
Human consulted and authorized source-free merged-data validation using the existing
config owner, plus conflicting default/environment regressions. U7 remains held.
Corrected U1 tracked diff SHA256:
`136fb05cb880497b53040cfcc0ec8976105775aa0a001f94f5aacf383a142885`;
new color test SHA256 `10ada231c2467a19ad99678b82c32ca11640cfadb1a226cfc6335da7c1795dca`;
CLI acquisition test SHA256 `7f62d3363b7f3340cd082839e151c4d04d95213f6e232961d3af73a41f5a5b76`.
Both merge paths now reuse source-free loader validation, preserving raw/wizard
redaction and runtime values. Worker negative controls failed eight cases before
correction; focused config/CLI/wizard/static proof passed afterward, including actual
selected-file CLI write/reload, ambient source isolation and validation input policies.
Config high reviewer performs a bounded rereview before U7 source ownership release.
Bounded U1 high rereview accepted the correction with no new material findings;
independently reran both original source-conflict cases and observed 60 focused
color/acquisition/preset tests plus four loader precedence/redaction/isolation cases
pass. U7 implementation ownership released; config merge semantics remain protected.

### U7 implementation evidence

Twenty-one-file scoped diff SHA256:
`7bcd909d34b1d84e3974c1496dc2a8fee614b3af2806dff523d5cd60736ba4cb`.
Parsed CLI options/runtime requests now carry the same typed CLIConfigOverrides,
constructed once. Redundant flat fields, structural source protocol/projector and
request projection method removed; actual callers/tests migrated without aliases or
reflection. U1 merge semantics/U4phase policy retained; --no-cache help now reflects
scoped refresh without changing runtime behavior. Worker observed 430 focused tests
plus eight help checks, one native lsmas module collection skip, scoped static/diff
checks clean. High config/pipeline reviewer now reviews U7; full combined/native/media
acceptance remains controller-owned.

## Integrated source verification

U7 high review found one omitted real caller in `tools/alignment_benchmark.py`.
The worker migrated it to the canonical carrier, retained all assertions, and
observed all 35 benchmark tests pass. The high reviewer reran its two original
failures successfully and accepted U7. The expanded source scan included tools and
scripts; no obsolete persistent constructor arguments remained.

The first full native run found two failures: a manual-precedence test fixture still
used the intentionally unsupported v1 format, and one unchanged Chrome dump invocation
exited 2. The native worker migrated both live canonical fixtures in
`test_alignment_previous_offsets.py`, retaining assertions; its 16 tests and the high
reviewer's two affected cases passed. The browser worker reran the original failing
case and a diagnostic invocation successfully. The original captured Chrome stderr
was unavailable, so no cause or speculative harness change is claimed. A combined
native rerun follows the correction.

The corrected native rerun observed 3403 passed, 99 skipped, and one Chrome dump
exit-2 failure at a different viewport parameter. The stale fixture failure is
resolved. U5 is reopened for captured diagnostics and evidence-based harness
correction; a passing isolated rerun does not close the repeated combined failure.
The canonical Docker gate passed 281 tests with zero skips in 251.41 seconds,
then the production image passed installed CLI/generated-artifact proof. Actual
Linux filesystem naming/expansion/type tests passed all 50 cases. The controller
may commit the accepted nonbrowser packages while U5 correction runs; full local
acceptance and the final documentation commit remain held.

U5 added bounded captured stderr as a note on the original Chrome
`CalledProcessError`, preserving its type, identity, exit code, single attempt,
and timeout policy. The retained non-timeout regression proves those properties.
The full browser module passed 21 cases without skips; the recurrent combined
failure's cause is not established. Diagnostic-only high review and a final
combined rerun follow on frozen source. Commit hooks temporarily stash tracked
unstaged files; subsequent commits are serialized after worker/reviewer freeze
and runtime checks to avoid conflicting edits or unstable proof inputs.

Global Ruff, format, Pyright, Bandit medium/high, both import contracts, API-reference
drift and strict documentation build passed. Bandit reports 27 low-severity issues;
the selected gate has zero medium/high findings. Linux production-image offscreen
VSView proof passed every marker: tooling absence, entry point, PySide6/BestSource,
generated three-source L-SMASH session, panel, frame zero, complete offsets/keep-current,
metadata/result validation and cleanup. This is Linux-container offscreen evidence
on macOS Docker Desktop, not visible X11 or Windows acceptance.

## Git integration record

The human authorized commits. The controller created these scoped conventional
commits with repository pre-commit hooks passing; unrelated work is excluded:

| Commit | Scope |
| --- | --- |
| `34fa0ea828a149d9f3c59faee40d9b9a65be497d` | U1/U4/U7 configuration authority, typed acquisition, single override transport, required cache-only analysis, migrated benchmark |
| `c56e2613172f99632fa8869837553645dafab894` | U2 actual-filesystem screenshot identity and encoder cleanup |
| `8c9c686f17c79b206dd708abef66944c8befd2fd` | U3/U6/U9 cancellation admission, immutable panel presentation, explicit breaking manual format v2 |
| `72033c53ed45c20264c5efc27c68de0f1e8d43e7` | U8 lintable equivalent Windows proof and committed-source inclusion |
| `51cce114abb5bdceefe0c050c3c77231b4035357` | U5 Unicode note input, common DOM fixture, Chrome ownership and bounded failure diagnostics |

The companion `docs: record remediation contracts and acceptance evidence` commit
contains this plan and the four current contract/runbook/runtime documents. All
remediation changes are committed; unrelated local work is excluded. The human
subsequently authorized the branch push and Windows handoff. No PR, signing,
release or publication is authorized by that instruction.

The diagnostic high reviewer accepted the bounded note, independently proving
the retained non-timeout failure behavior. An extra child browser run overlapped
the third full native run after a queued coordination message; its browser
acceptance is discarded. That run observed 3400 passed, 99 skipped and four Chrome
exit-2 failures. Captured stderr identifies `Teardown watchdog expired; recording
dump and terminating`, alongside macOS display/allocator diagnostics also observed
on successful launches. It does not establish a report or profile defect. Parent
verification now runs the same browser module exclusively after all other checks
and child browser work stop; no assertions, exit requirements or timeouts are relaxed.

Parent-exclusive browser verification on frozen source passed all 21 cases in
29.90 seconds with zero skips. A complete native suite now runs serially (`-n0`)
with the same strict marker/configuration flags and every retained test. This
preserves behavioral coverage while isolating browser work from parallel suite
activity; it is not a claimed fix for Chrome's parallel macOS shutdown behavior.
The strict docs build also passed after the supported-runtime format correction.

Final full native suite passed on frozen source: **3404 passed, 99 skipped in
191.17 seconds**, using `uv run --no-sync pytest -q -n0 -o addopts='-ra
--strict-markers --strict-config'`. Skips retain unavailable native-media plugins,
media/whole-track/live opt-ins and Windows/PowerShell requirements; the canonical
Docker media gate separately passed with zero skips. All source packages have
independent high review and applicable local verification. Parallel macOS Chrome
teardown failures remain recorded as a verification-environment limitation; no
runtime success or root-cause fix is claimed for that failed command. Serial
acceptance retains every test and assertion without changing repository CI policy.
Plan remains Active solely for actual Windows unsigned-bundle and filesystem proof.

## Windows acceptance handoff

The human will pull `v0.7.0` on a Windows machine and give Codex the self-contained
[`Windows acceptance prompt`](../prompts/2026-10-12-maintainability-windows-acceptance-codex.md).
The controller will commit that handoff separately and fast-forward push this branch;
runtime acceptance remains open pending the Windows report.

This gate stays open. Use a Windows checkout at the final remediation commit with
the extracted Python source committed; inventory generation verifies source bytes
against Git. Use fresh output and extraction directories, retain build/proof logs,
and follow the applicable portable procedure in `docs/ENGINEERING_RUNBOOK.md`.
The local unsigned command sequence is:

```powershell
$candidateSha = (git rev-parse HEAD).Trim()
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir dist/frame-compare-portable-win-x64 -CacheDir .portable_cache
if ($LASTEXITCODE -ne 0) { throw "Unsigned portable build failed" }
Compress-Archive -Path dist/frame-compare-portable-win-x64 -DestinationPath dist/frame-compare-portable-win-x64.zip
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/verify_extracted_bundle.ps1 -ZipPath dist/frame-compare-portable-win-x64.zip -ExtractRoot dist/zip_extract_check -DoctorStdoutPath dist/extracted-doctor.json -DoctorStderrPath dist/extracted-doctor.stderr.txt -ExpectedCommitSha $candidateSha -CommandTimeoutSeconds 300
if ($LASTEXITCODE -ne 0) { throw "Extracted portable proof failed" }
```

Acceptance requires the eight bundled Python phases, generated-media/native
topology, tonemap path, VSView entry point/panel/result validation, offscreen launch
and process cleanup, deterministic ZIP/license inventory and exact source provenance.
An allowed Vulkan-unavailable result does not establish physical GPU acceptance.
Exercise screenshot alias rejection/preservation on the actual Windows output
volume as the remaining U2 platform branch. Record exact SHA and observed results.
No signing key, release/publication, manual signed-workflow dispatch or source-policy
bypass is authorized. The existing unsigned PR workflow is another acceptance route
only after the human authorizes pushing and opening the PR.

### Windows acceptance record, 2026-10-12

The local U2/U8 Windows gates passed. This supersedes the gate-open observations
above; retain Active for the Mac controller's integration/acceptance disposition.
Separate physical-display/media-runtime release limits remain open in the
dependency-refresh handoff.

- Pulled clean `v0.7.0` HEAD/local `origin/v0.7.0`:
  `6d5fca4d4a7482029d612881d67c69eccabcd3bc`, containing `b5df8a4d`; later changes
  were documentation only. Final tested source:
  `929c076ac7fb570f28cb0ef7a641beb2a51843cb` (`test: make Windows acceptance
  fixtures portable`), changing two tests and no production source. GPT-6.1-Sol
  medium implementation/high independent review passed 47 affected cases without
  skips. `review-code` was unavailable after discovery; review used repository
  contracts and develop-code's fallback. Scoped Ruff lint/format, Pyright and
  diff checks passed.
- Initial failure evidence retains ten failures: seven from the controller's
  in-repository pytest basetemp correctly triggering private-key containment
  refusal; two Windows fixture defects (open-file deletion and oversized native
  environment value), plus one subsequent leaked-handle warning. Corrections
  retain independent physical replacement/ownership and oversized refusal,
  sanitization and no-write assertions. Fresh outside-repository C: basetemp:
  **358 passed, 25 skipped in 215.02s**, exit 0. All 208 Windows portable and
  50 U2 cases passed with zero skips; 16 workflow skips lack jq, nine require POSIX.
- Windows 10 Home build 19045 x64; PowerShell 7.6.4; Git 2.56.0.windows.1;
  uv 0.8.17; source Python 3.13.7; embedded Python 3.13.16; frozen dev/VSView sync
  passed. C: NTFS, 4096-byte allocation units, case sensitivity disabled on both
  pytest and screenshot output directories.
- Both unsigned builds passed; the correction was rebuilt into a fresh directory.
  All eight phases reported ordered start/ok exactly once: package_imports,
  runtime_contract, vapoursynth_environment, lwlibavsource_frame,
  placebo_tonemap_api, apply_tonemap_frame, placebo_tonemap_frame, vsview_runtime.
  Managed R81/API4.3, L-SMASH 1310, placebo 2.0.4, VSView 0.12.1, PySide6 6.11.2,
  BestSource 22, vspackrgb 2.0 and pinned LGPL FFmpeg loaded. Preload-before-Qt,
  generated L-SMASH media, panel entrypoint, whole-set metadata, confirmed/keep-current
  sidecars, malformed rejection and offscreen launch/cleanup passed. FFMS2 and
  deployed Qt WebEngine remained absent. Actual application tonemap: RGBS/32-bit;
  direct Vulkan tonemap: RGB48/16-bit; no Vulkan-unavailable skip. Vulkan enumeration:
  loader 1.4.341, one RTX 5080, device API 1.4.351, driver 617.14. Stale host overlay
  warnings were retained; libplacebo did not separately log a selected-adapter ID.
- Extracted verifier exit 0, exact `WINDOWS_EXTRACTED_PROOF result=ok`:
  help/version/JSON-clean doctor and installed shim commands, exact source SHA,
  runtime fingerprints, ZIP layout and 105 verified license records. Supplemental
  comparison proved all 196 source files equal committed Git archive bytes; an
  initial raw-blob comparison correctly differed on Git's configured CRLF export.
  Disposable LOCALAPPDATA installs preserved all eight existing installation files
  and restored the exact user PATH. PowerShell 5.1.19041.7725 additionally passed
  install/shim help/version from a fresh non-ASCII bundle path with BOM-less UTF-8
  state. No candidate processes remained after proof.
- Extracted-interpreter actual-volume naming probe: Movie/movie and Ç/ç physically
  alias and refuse with FC-4021 / SCREENSHOT_OUTPUT_COLLISION; NFC/NFD,
  Straße/Strasse, Ç/c and straße/strasze remain distinct and valid. Existing bytes,
  hard links, exact duplicates, reservations, failed creation and cancellation
  admission cleanup passed. Retained tests also proved refusal before native
  preparation/render admission and cleanup after cancellation of a reservation.

Absolute Windows evidence roots:

- Initial failure, corrected pytest/JUnit, implementation/review and host/Vulkan
  logs: `C:\Software\video\frame-compare\dist\maintainability-acceptance-20261012T220412295Z`.
- Final build/evidence, extracted proof/doctor JSON/stderr, packaged naming,
  Windows 5.1, process/isolation logs, extracted bundle and ZIP:
  `C:\Software\video\frame-compare\dist\maintainability-acceptance-20261012T221123904Z`.
- Final ZIP SHA-256:
  `56fff2f5ada57ee8b883c2f8c47d83aa3774283cdac8387aa87f4beb34cdaf9b`.

Visible VSView interaction, real HDR10/Dolby Vision/perceptual acceptance, exact
predecessor migration and other physical-media cases remain unverified; native
desktop automation is unavailable in this chat. No signing, publishing, release
tags, PRs, push, hosted dispatch or live slow.pics/webhook calls occurred.

### Controller integration and disposition, 2026-10-12

The human supplied the Windows report and requested pulling its changes. The Mac
controller fetched `origin/v0.7.0` and fast-forwarded from `6d5fca4d` to
`36a8ff901fa0b9b860d4c76b9c617aeb2ac07353`, integrating correction `929c076a`
and the Windows evidence record. The correction changes only two test fixtures;
production source and protected contracts are unchanged. Source inspection found
the replacement-file test retains independently distinct physical identities and
owned cleanup protection, and the oversized-key test retains sanitized fail-closed
refusal without relying on an impossible native Windows environment value.
No material findings were established. On the integrated Mac checkout, the two
affected modules passed **47 tests without skips**, Ruff lint/format and diff
checks passed. The prior full native/Docker/media proof remains applicable to
unchanged production code; redundant full reruns were unnecessary.

The controller accepts the human-provided Windows evidence at tested source
`929c076ac7fb570f28cb0ef7a641beb2a51843cb` for U2 and unsigned U8: actual NTFS
identity/preservation/cleanup, all required bundled phases, managed native/plugin
and generated-frame proof, extracted provenance/license/ZIP/doctor proof, and
offscreen process lifetime. Reported Windows regression results are 358 passed,
25 workflow-capability skips, with every portable and U2 test passing without
skips. The report and committed record identify logs and the exact ZIP hash;
those Windows artifacts were not independently rerun or read on this Mac.

All required remediation work and acceptance are complete; this plan is Historical.
Visible VSView interaction and broader physical-media, predecessor migration,
signing/legal release disposition and hosted-CI acceptance remain distinct limits
of the existing platform/release work, not claims established by this remediation.
Unrelated local work was preserved. The previously authorized branch push permits
publishing this documentation closure to `v0.7.0`; it does not authorize a release.
