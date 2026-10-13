---
search:
  exclude: true
---

Status: Historical
Scope: Implement, independently review, verify, and commit the accepted 2026-10-13 audit findings.
Owner: Codex controller chat `01a1336b-f4db-77e3-9577-c63c15d7a77b` on local.
Baseline: `d81652c5b469a9857c1af10563b8b351aaa6f2ec`, branch `v0.7.0`.

# Audit remediation plan

## Authorization and constraints

The human authorized planning, implementation through separate chats using GPT-6.1
Sol, verification, independent review-role agents, and proper commits. Authorization
is parent turn `01a13396-d0e6-7693-a714-14b3dc154a66`, user item
`01a13396-d11f-7280-8475-9da3b088d174`. Children must retrieve this actual human
message before their one terminal callback to the controller. A copied quotation
is a pointer, not independent evidence of consent.

Preserve behavior, meaningful coverage, runtime-free help/version, typed errors,
machine-clean JSON, deterministic artifacts, alignment authority and valid zero,
owned cleanup, persisted compatibility, and separate platform evidence. No new UI
direction, dependency update, push, PR, release, signing, or deployment is requested.

The controller owns Git and this plan. Workers use disjoint files in the existing
checkout; no branch switches, worktrees, stashes, resets, staging, or commits.
Do not edit unrelated documentation redesign files, including initially dirty:

- `docs/plans/2026-10-08-documentation-refresh-assets/capture-spec.md`
- `docs/plans/2026-10-08-documentation-refresh-assets/pages-reference.md`
- `docs/plans/2026-10-12-documentation-site-redesign-assets/theme.md`
- `docs/plans/2026-10-12-documentation-site-redesign.md`
- `docs/stylesheets/extra.css`
- the three untracked `docs/prompts/2026-10-08-*.md` files.

Other chats may advance these files or HEAD. Record actual source state and never
stage unrelated work. Controller-owned contract/navigation edits are narrowly part
of this remediation, not authorization to redesign user documentation.

## Accepted findings and priorities

| Package | Finding / priority | Goal | Owner and primary files | Required evidence |
| --- | --- | --- | --- | --- |
| P1 | Render preparation cancellation / S2 | Stop new source/native preparation after interruption | Runtime worker: `render/batch/expansion.py`, `render/prepare.py`, narrowly required VS admission owner, associated render/source tests | Production preparation regression, existing cleanup/error tests, full native, Docker media |
| P2 | Unit misclassification, duplicate CI, incidental source assertions / S3 | Keep all distinct proof while running and maintaining it once | Verification worker: browser markers only, `ci.yml`, `windows-portable-build.yml`, associated workflow/Windows tests | Collected nodeid union, focused workflow tests, retained browser/Windows process obligations |
| P3 | Generated VSView executable Python / S3 | Typed runtime owner and deterministic data/bootstrap | Runtime worker: `vsview/session_script.py`, new local runtime owner, session tests, affected GUI verifier/runtime-smoke consumer assertions | Generated execution/determinism, normal Python gates, distribution inclusion, real offscreen session proof |
| P4 | Docker Python inside Bash / S3 | Python owns runtime assertions; shell owns lifecycle | Verification worker: `verify_docker_integration.sh`, extracted Python, Docker trigger/context and fixture consumers | Extraction equivalence, lint, shell routing/artifact tests, canonical Docker gate |
| P5 | Inert metadata policy / S3; mutable review telemetry / optional low priority | Remove hidden internal policy/state plumbing while retaining external behavior | Services worker: `services/types.py`, metadata façade, alignment/VSView outcome return, relevant phase adapters and tests | Selected/ambiguous/missing metadata; requested/unrequested/rejected/confirmed review; phase status/timing |
| P6 | Duplicate Help/Info dialog lifecycle / S3 | One local focus/keyboard owner | Viewer worker: `services/report/assets/viewer.js`, narrowly necessary report assets/support | Existing modal/escape/focus scenarios and real browser module |
| P7 | Coarse contract navigation / S3 | Find owner, contract section, and focused proof directly | Controller: `.agents/project.md`, current architecture/CLI contract, runbook updates required by extracted proof | Resolve all pointers, retain contracts/anchors, existing docs checks and strict site build |

## Decisions and implementation contracts

### P1 — Cancellation admission

The audit reproduced `expand_batch_render_requests` preparing a second source with
`task.cancelling() == 1`. Guard before each source and between independently
admitted native operations. Use the existing cancellation owner; ambient asyncio
inspection must not become a worker-thread stop mechanism. Preserve in-flight
native drain, typed errors, lowest-index real failure ordering, and owned cleanup.
Extend meaningful existing fixtures rather than creating a demonstration-only test.
Rollback source guards and regression together if needed; never weaken the promise.

### P2 — Verification efficiency

Only two real-browser functions are accidentally unit-classified; three fake
browser-helper unit cases are valid. Correct markers without deleting scenarios.
The Windows full-suite invocation already includes the later synthetic updater
selection. Remove the duplicate invocation while retaining full-suite coverage.
Keep the required browser job with executable preflight and remove duplicate browser
execution from the general CI lane; verify the retained nodeid union.

Relax only source assertions whose private helper/local spelling is incidental.
Retain distinct absent/empty/failure restoration cases and Windows PowerShell 5.1
proof. Runtime tests in `test_windows_portable_shim_e2e.py` observe nonempty environment
restoration; do not assume they prove every branch. No blanket static-test deletion.
Rollback workflow selection and its expectations together. Windows execution remains
an explicit acceptance gap if no Windows host is available; static checks are not it.

### P3 — VSView execution owner

Move executable helpers/main out of strings into a typed package module. Generate
only deterministic input data and a small bootstrap; pass memory configuration as
data rather than exact-text replacement. The generated script already depends on
the installed package, so no speculative standalone compatibility layer is needed.
Preserve preview defaults, source/index fallback distinctions, output registration,
metadata/result sidecars, safe child imports, log suppression, and script identity.
Migrate actual verifier consumers that assume inline implementation; keep their
behavioral observations. Do not merge parent and preview loading policy blindly.
Rollback runtime module, generator, and consumers together. Offscreen Linux proof
does not establish visible X11 or native Windows acceptance.

### P4 — Docker runtime proof owner

Extract the actual Python body faithfully to a repository-owned file. Bash retains
Compose/build, container environment, cleanup, log/artifact paths, and exit handling.
Keep proof markers and native/fixture assertions. Ensure the file enters build
context, source provenance, workflow path selection, and fake-Docker fixtures where
required. Use the existing Windows extraction as a local precedent, not a generic
cross-platform framework. Rollback producer/path/filter consumers as one change.

### P5 — Service outcomes

Preserve acceptance and serialization of the public `tmdb.unattended` key: behavior
preservation does not authorize rejecting existing config. Document that both values
currently use noninteractive selection. Remove redundant internal branches and
transport fields when no consumer needs them. Do not add a metadata chooser.

Replace the mutable alignment review output parameter with a typed returned
operation outcome containing results and immutable review telemetry. Derive telemetry
from the native review outcome. Preserve not-requested versus unresolved review,
counts, duration, summaries, and no new persisted/JSON fields. Migrate all internal
callers/tests atomically. Keep canonical evidence and existing phase-output owners.
Rollback service result and caller migration together. This low-priority item is
included because the user authorized remediation of the reported findings.

### P6 — Dialog ownership

Consolidate only Help and Info's repeated open/close/focus/Tab/Escape lifecycle in a
small local owner. Preserve escape precedence, fallback focus, ARIA state, and public
viewer behavior. Inspector interaction remains separate. No new framework or visual
direction. Reuse existing Node/browser assertions; rollback owner and its callers
together if behavior differs.

### P7 — Contract and proof navigation

Add subsystem headings/anchors within existing authority documents and compact
source/contract/focused-test routes. Preserve existing anchors used by callers and
all substantive requirements. Reflect P1/P3/P4/P5/P6 ownership only after those units
settle. Keep user-site theme/assets/plans out of scope. No duplicate manuals, scanner,
new mandatory ceremony, global skill changes, or weakening of verification gates.
Token/time savings are expected, not measured; use concrete retrieval spans rather
than invented percentages. Rollback routing/anchor changes together if links break.

## Execution, review, and verification

Independent runtime, verification, services, and viewer workers can run in parallel.
Runtime owns P1/P3, verification owns P2/P4, services owns P5, viewer owns P6. The
controller owns P7, integration, shared documentation, Git, and heavy checks.
Workers run focused tests and lint only owned files; no global formatting, full
suite, Docker, browser, environment sync, or shared builds without resource transfer.
Runtime worker may update `tools/verify_docker_gui.sh` and Windows runtime-smoke
consumers for P3; verification worker must not edit those overlapping surfaces.
Verification owns browser marker edits; viewer must not edit that file without transfer.

Executors: GPT-6.1 Sol, high reasoning for runtime/tooling cross-boundary extractions;
medium for bounded services/viewer implementation. Reviewers: GPT-6.1 Sol/high,
applying `.codex/agents/reviewer.toml` and `review-code`, read-only and independent
from the author. Existing audit chats may be reused for review to retain useful context.

After each completed worker, inspect actual diff and run independent review of the
owned change against the plan. Adjudicate findings and return focused fixes to its
author. Reviewers report evidence and limits; they do not commit. Once stable, run
full native/static/import gates once, reuse actual browser results in that suite,
then canonical Docker and applicable VSView offscreen/distribution/docs proof.
Serialize heavy runtimes. Repair regressions before committing reviewed packages.

Commit coherent conventional units using explicit paths; inspect staged diff before
each commit. No `git add .`, push, release, or unrelated docs inclusion. Record actual
commits, commands/results, skips and acceptance gaps below. A commit is not a claim
that unavailable Windows/physical-host proof passed.

## Parking lot

The proposed TMDB cache cancellation defect was rejected: the current CLI contract
explicitly permits in-flight shared response-cache publication and executor drain.
Do not implement it. No broad architectural rewrite, generic test purge, framework
migration, or dependency/format change is included.

## Dispatch and completion ledger

| Worker | Chat ID | Model/effort | Scope | Status |
| --- | --- | --- | --- | --- |
| Runtime | `01a13399-b75e-7083-94a2-6b4bcb50c780` | GPT-6.1 Sol/high | P1, P3 | Complete; reviewed and locally verified |
| Verification | `01a13399-bfdf-7480-8060-79f7c803c72a` | GPT-6.1 Sol/high | P2, P4 | Complete; reviewed and locally verified |
| Services | `01a13399-c81f-7ca3-b3a5-97b30769915c` | GPT-6.1 Sol/medium | P5 | Complete; reviewed and locally verified |
| Viewer | `01a13399-d3b1-7941-87b9-c0831b7f0bac` | GPT-6.1 Sol/medium | P6 | Complete; reviewed and locally verified |

All workers use this checkout on local and callback to the controller above.
Controller updates reviewed changes, verification evidence, commits, and final limits here.

Controller preparation: Docker server 29.8.2 is available; no local PowerShell
executable was found. P7 initial routing/heading edits preserve all existing
non-heading contract text in order. Source/test paths and linked heading anchors
were checked directly; `uv run --no-sync pytest -q tests/test_cli_contract_docs.py`
passed (five cases). Ownership additions and final docs proof await worker results.

P6 worker reports 50 focused viewer-state/Inspector/markup cases passing and an
owned-path diff check. Changed only `viewer.js` and `viewer_state_harness.js`.
Reviewer chat `01a1336d-fb79-76e0-815c-387aa553aff4` (Sol/high, reviewer role) is
reviewing P6 plus initial P7 navigation/contract edits. Real-browser proof is pending.
Unrelated documentation commit `4a04f7f9` advanced HEAD during implementation; it
does not modify these code units and is not a remediation commit.

P6 and initial P7 reviewer reported no material actionable findings, independently
checked callers/focus behavior, and resolved source/test/anchor routes. Final
ownership prose and real-browser/strict-site proof remain controller work.

P5 worker reports 277 focused cases then 96 final selected cases passing, plus
scoped Ruff/format/Pyright. The public metadata key is retained; internal redundant
transport is removed. Alignment returns immutable results/review telemetry.
Reviewer `01a1336d-f45c-7893-b562-d5f9a736d6c3` (Sol/high, reviewer role) is checking
the 23-file P5 change against actual callers and baseline behavior.

P5 reviewer reported no material findings after checking all six production and
17 test diffs, both return paths, callers, phase status/timing, and public metadata
compatibility. Final scoped diff hash was
`023c33fd79f73bc96bdc48c88e266900b2af36ace16966ca1483d9f5b9cdea39`.

P2/P4 worker completed 10 paths with no heavy-runtime run. Reported final collected
coverage: 3,502 full cases = 3,481 general + 21 browser, no overlap; all 46 updater
cases remain in the full selection. Two private-spelling tests were replaced by
six Windows process cases for absent/empty/set restoration after failure, retaining
existing success and Windows 5.1 proof. Focused evidence: 115 pass / 38 platform
skips / one P3-dependent deselection; final Docker contract selection 17 pass;
mocked browser unit selection 3 pass. Windows process execution remains unavailable.
Reviewer `01a1336e-04b0-7833-8057-30dafdf58985` is checking P2/P4 independently.

P7 now also clarifies the existing `tmdb.unattended` reference description with
the same compatibility decision as the CLI contract; this isolated related edit
does not change user-site design or the concurrent documentation work.

P2/P4 reviewer reported no material findings. Independently confirmed the extracted
Python AST matches the original heredoc modulo explicit `zip(strict=False)`, and
the shell matches exactly after replacing only that heredoc with the invocation.
Inspected actual Windows generated launcher and runtime-validator failure paths:
the six cases observe real post-admission process state, not a copied implementation.

P1/P3 reviewer reported no material P3 findings, but reproduced a remaining P1 gap:
cancellation during the libplacebo capability probe still admitted a new frame-zero
read inside tonemap preparation. Returned this confirmed S2 finding to the runtime
worker for guards at the real native-operation boundaries and a dispatch-level
regression. The existing expansion/source fixes remain valid.

Integrated verification before that focused correction: Ruff check and format
(510 files), configured Pyright (zero errors/warnings), import-linter (both
contracts), and Bandit medium/high gate passed. Full native pytest
(`-q -n4 --dist loadgroup`) exited zero in 101 seconds, including the browser module.
Native dependency, opt-in resource/live/media, and Windows skips remain distinct
from passes. Twelve shell workflow checks also skipped after five-second Bash
probe timeouts under that run; a serial workflow rerun is required to resolve those
incidental host-load skips. The correction will receive focused verification and
canonical Docker proof rather than repeating unrelated native tests.

Strict documentation build passed using an isolated copy under ignored `.tmp/`,
with the repository's unchanged relative config and installed Zensical binary.
No original site output, theme, or unrelated documentation was mutated by that check.

Native progress tally: 3,389 passed and 113 skipped out of 3,502 collected cases.
The serial `pytest -o addopts='' -q tests/workflows tests/test_cli_contract_docs.py`
rerun passed all 131 cases in 65 seconds, resolving the incidental Bash probe skips.
Browser execution in the full native run had no skips; no separate duplicate browser
run is needed for the unchanged viewer change.

F1 correction is complete in the four tonemap owners plus the existing render wiring
and conversion tests. Runtime worker reports 171 affected cases passing; disabling
only the new tonemap guards in memory makes all 12 new regression cases fail.
Scoped Ruff/format/Pyright passed. Controller repeated affected Ruff and the full
import contracts (182 files, 781 dependencies): pass. Original reviewer is checking
the correction and matching final architecture wording independently.

Final P7 five-document review reported no material findings; all 16 profile links
and actual rendered heading anchors resolve. The final tonemap clause is included
in the separate F1 review. No original authority anchor or gate was removed.

F1 re-review reproduced True/False probe interruption and native-placebo failure
through production dispatch and found no further admission. It also inspected the
four direct conversion regression cases and final architecture clause: no material
findings. All implementation and contract edits now have independent review.

Distribution proof: the populated-checkout `uv build` exceeded its 240-second bound
while traversing/building the sdist. Retried from a clean current-source snapshot of
tracked files plus the three new remediation files, retaining byte hashes. `uv build`,
the existing distribution verifier, fresh-environment wheel installation, installed
help/version, and importing the new runtime without importing native VS/VSView all
passed. The new runtime's wheel bytes match the checkout; all source/test/tool
snapshot hashes still match. This proves current-source packaging without claiming
the original populated-checkout build completed. No packaging configuration changed.

Canonical `bash tools/verify_docker_integration.sh` passed against the corrected
source: 288 tests passed, zero skips, in 451 seconds (489 seconds including builds
and proofs). Native L-SMASH/FFMS2/libplacebo, software Vulkan, codec fixture matrix,
frame rendering, source provenance, and doctor checks passed. The separate production
image excluded test/build tooling and generated the expected application artifacts.
This includes the changed service outcome in real alignment integrations and the
new direct conversion admission cases with the packaged native runtime.

Rebuilt `gui-linux` image and ran
`tools/verify_docker_gui.sh --inside-container` with `QT_QPA_PLATFORM=offscreen`:
passed in 27 seconds including build. Proof covered production tooling absence,
VSView/Qt/BestSource availability, exact panel entry point, three named L-SMASH
outputs, frame zero, owned indexes, positions/keep-current actions, metadata
topology, result round-trip/malformed rejection, and temporary cleanup.

## Completion and limits

All seven accepted packages are implemented and independently reviewed. Review F1
was corrected and re-reviewed before committing. Final changed production source
matches the verified clean distribution snapshot. Applicable commit hooks passed.

| Package | Conventional commit |
| --- | --- |
| P1 | `1d903498` — `fix(render): stop native preparation after interruption` |
| P3 | `5ae7bc9f` — `refactor(vsview): move session execution into typed runtime` |
| P2 | `d47a081d` — `test(ci): retain behavioral proof without duplicate runs` |
| P4 | `b4fbcc26` — `refactor(tools): extract Docker runtime proof into Python` |
| P5 | `e48fc551` — `refactor(services): return immutable alignment outcomes` |
| P6 | `4d948bc1` — `refactor(report): share help and info dialog lifecycle` |
| P7 | This document's commit — `docs(architecture): map contracts and remediation evidence` |

Verification logs and snapshot fingerprints are retained under ignored
`.tmp/audit-remediation-2026-10-13/`; detailed commands/results are recorded above.
The native full suite preceded F1; focused 171-case proof, affected static/import
checks, and the subsequent canonical Docker gate cover that correction. The final
tonemap contract wording also passed the strict site rebuild.

Remaining acceptance limits: Windows process/portable execution and Windows 5.1
cases could not run on this Mac; Linux-container offscreen proof does not establish
visible X11 or physical Windows behavior. No signing, release, push, or hosted CI
run was performed. The separate three-hour streaming resource proof was not required
by these changes; no streaming collector/memory/lag contract was changed. The
configured Pyright gate covers `src` and `tests`; the extracted Docker tool retains
its predecessor's native typing debt outside that gate, while passing Ruff and
real execution. No typing suppression or weakened gate was introduced.

The initial populated-checkout distribution timeout is recorded above; a clean
current-source build and fresh installation passed. Runtime behavior and meaningful
coverage are preserved except the intended cancellation-admission correction.
Instruction retrieval and CI duplication are improved, but token savings were not
measured. Unrelated documentation changes and prompts are excluded from these commits.
