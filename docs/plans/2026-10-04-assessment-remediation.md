---
search:
  exclude: true
---

Status: Historical
Outcome: Implementation and host verification complete; physical Windows acceptance remains open.
Scope: Implement the accepted shared-workflow assessment corrections. The subsequent human request authorizes local commits; pushes, release, and workflow redesign remain outside scope.
Source: `agent/e2e-test-strategy` at `3f2fdf9c` with a clean working tree at execution start.

# Assessment remediation

The parent chat owns design, integration, documentation, and acceptance. The human
authorized execution of the prior implementation plan with this chat as orchestrator
in parent `01a1049b-8a24-70e0-babf-089a9241725f`, host `local`, turn
`01a108aa-0c06-7033-9dca-afc1ae983143`: “execute the plan with you as orchestrator”.
The prior plan uses separate implementation chats and scoped terminal callbacks.
Children must verify that original human turn before sending a callback; otherwise
finish locally and let the parent retrieve results. This does not authorize messages
to other chats or services.

Read AGENTS.md and .agents/project.md. Use develop-code for implementation,
design-code for consequential ownership choices, review-code for independent review,
and verify-code for evidence. These skills remain the procedure owners. Preserve
existing test-slimming decisions and distinct proof; add only meaningful missing
regressions. The former task's no-new-test-cases restriction is not global.

## Constraints and design contracts

- Preserve CLI imports/help/version, typed sanitized errors, clean JSON, deterministic
  artifacts, current persisted schemas/sign conventions, valid zero offsets,
  audio/video authority, confirmation provenance, and owned-resource cleanup.
- The former seven dirty workflow-follow-up files are committed in 3f2fdf9c. Keep
  those changes. Another chat completed their commit; it has no assignment here.
- Work locally in this checkout. No branch, commit, staging, push, release, package
  publication, new worktree, dependency synchronization, or recursive delegation.
- Children own only their source/test group. Shared docs and this plan belong to the
  parent. No full-suite, Docker, portable, or shared browser runs in child chats.
  Focused checks use isolated temporary outputs and identified stable inputs.
- G1 precedes G2 and G3 because they share cache source files. G2 and G3 then have
  disjoint domain ownership. G4, G5, and G6 can run independently of those groups.
- Alignment: validate frozen source identity at cached acceptance; drift cannot
  authorize trims or new cache writes. Do not silently refresh the fingerprint.
  Keep the documented same-path/size/mtime policy. Request facts are the sole source
  of computation/cache identity (settings, selected streams, reuse policy); separate
  execution/UI preferences remain config. Strengthen existing result invariants
  without conflating historical cached evidence with fresh computed authority.
- Metrics: one owner returns metrics with the actual acquisition disposition.
  Preparation's cache-only validation remains before output reservation. Migrate
  all callers; remove the ignored reader clips argument, not serialized clip facts.
- Webhook: default DNS resolution must have an owned, terminable lifetime. Prefer a
  current-interpreter stdlib-only subprocess using fixed resolver code and a bounded
  hostname/port input/result protocol. Never send webhook URL/body/credentials to
  it. Validate all returned addresses in the existing parent policy. Poll deadline
  and cancellation, terminate/kill/reap on every exit. Avoid multiprocessing spawn
  reimports, abandoning threads, external resolver tools, or new dependencies.
  Preserve injected-resource ownership, pinning/TLS/no redirects, retry distinctions,
  and uncertain delivery behavior. Validate the default process boundary as well
  as pure/simulated behavior. Portable interpreter acceptance remains separate.

## Units and write ownership

| Unit | Preset | Scope and owned production files | Required observation |
| --- | --- | --- | --- |
| G1 | worker_luna | analysis/cache_io.py; orchestration/probing/probe_cache.py; services/alignment_reuse_cache.py and alignment_manual_overrides.py; their focused tests | Invalid UTF-8 recovers at cache owners, including merge-on-write. Invalid probe facts/identity are discarded; valid snapshots round-trip. Cache-only errors stay typed. |
| G2 | worker | services/alignment.py, types.py, alignment_previous_offsets.py and alignment_reuse_cache.py; necessary adjacent alignment service callers; orchestration/phase_alignment.py; utils/types.py; focused alignment tests | Primed cache plus changed source refuses authority; zero offsets and manual/cached provenance remain valid. Caller guards/duplicated settings disappear coherently. |
| G3 | worker | analysis/metrics.py, types.py, cache_io.py; orchestration/phase_selection.py and preparation.py; focused metrics/cache/orchestration tests | Actual acquisition drives hit/miss reporting, without duplicate reads; cache-only prevalidation remains. |
| G4 | worker_luna | services/report/assets/viewer.js; focused viewer/grid harness and tests; browser regression only if required | Deferred Diff load cannot commit after Grid transition/navigation; atomic pair swaps remain. |
| G5 | worker_luna | vsview/adapter.py; tests/vsview/test_adapter.py | Real child is reaped after interruption and timeout, original exception preserved, normal exit unchanged. |
| G6 | worker | services/slowpics_webhook.py and narrowly necessary resolver implementation; tests/services/test_slowpics_webhook.py | Blocked default resolver is bounded and reaped under timeout/repeated cancellation; no transport starts after cancellation. |
| G7 | parent | Profile/runbook/contributor/architecture/CLI/API documentation as affected, this plan, integrated checks | Documentation describes actual scope; combined verification and outstanding acceptance are truthful. |

Resolve routine local uncertainty. Return consequential changes to these contracts
with evidence before expanding scope. Do not edit another unit's source without a
parent ownership transfer. Report completion only after focused checks and repairs;
include child ID, source/diff identity, files, commands/results, and limits. Do not
edit after terminal completion until the parent requests a focused correction.

## Evidence and acceptance

Each child first validates its source trace and, where practical, observes a
distinguishing baseline failure. Extend meaningful existing coverage instead of
duplicating harnesses or asserting incidental implementation shape.

Parent integration uses one independent read-only review of authority/lifetime and
composition, adjudicates findings, and reruns affected proof after corrections.
Run required Pyright, Ruff/lint/format, Bandit, import contracts, and native suite
once on stable integrated inputs; focused work comes first. Run the canonical Docker
media gate once for alignment/metrics changes, serially with any other verifier.
The separate long-running streaming-resource proof is required only if its lifecycle
or resource obligation changed. Document its explicit exclusion from the default gate.
Run real-browser report proof for G4, and fresh distribution proof when packaged
resolver execution or package contents change. Do not infer Windows acceptance from
hosted/offscreen/native checks.

Physical Windows remains open: exact portable bundle; visible VSView callbacks and
focus; positive/negative/zero confirmation and keep-current; interruption/child
cleanup; stdlib resolver startup/timeout/reaping; applicable real-media/GPU HDR10/DV,
range/timing/index/cache/update migration scenarios from the existing runbook.
No private media, credentials, token-bearing URLs, or personal diagnostics in reports.

## Dispatch and progress

| Unit | Child chat (local) | Model / effort | State |
| --- | --- | --- | --- |
| G1 | `01a108ab-fa72-7fd1-ba97-4a313f59a4d6` | gpt-5.6-luna / xhigh | Focused checks passed; handed to G2/G3 |
| G2 | `01a108b3-04f5-7280-ad13-cb6748bd8719` | gpt-6.1-sol / medium | 559 focused tests, 83 final-guard checks, and scoped static checks passed |
| G3 | `01a108b3-1102-7320-bf12-47446afe4ac5` | gpt-6.1-sol / medium | 107 focused tests and scoped static checks passed |
| G4 | `01a108ac-3b9d-7d00-a23c-233bf7b125b0` | gpt-5.6-luna / xhigh | Focused checks passed |
| G5 | `01a108ac-75de-7342-b4b6-2e96f20a06eb` | gpt-5.6-luna / xhigh | Focused checks passed |
| G6 | `01a108ac-c2c4-7a60-bc0a-a3c1b0dc6c19` | gpt-6.1-sol / medium | 75 focused tests and scoped static checks passed after correction |
| Review | `01a108b4-d13f-7962-b535-8d7bc02f1020` | gpt-6.1-sol / high | Final composition reviewed; no remaining material findings |

The parent owns all broad checks. G1's 110-test focused cache selection, G4's two
production-method JavaScript harnesses, and G5's 29 adapter tests passed; their
integrated results are recorded below. Physical Windows acceptance remains open.

Review adjudication: portable `._pth` enables `site` despite `-S`. No shipped
startup hook was established, and changing the bundle's startup globally would
affect separate obligations. Trust the configured interpreter/startup while
keeping the resolver script stdlib-only, reject startup output that violates the
address protocol, and observe bounded startup under the actual `._pth` mechanism.
Explicitly exclude application credentials/configuration from the resolver
environment. Exact portable Windows startup remains a physical acceptance gate.

## Integrated evidence

Verification used HEAD `3f2fdf9c2d28a899dc0197a1cc0052c9a3306408` plus the working
diff; no Git mutations were made during implementation and verification. The subsequent
human request on 2026-10-04 authorizes a coherent local commit series. The verified
production/test diff plus the then-untracked
`alignment_sources.py` content has SHA256
`e44f8f8666b68aca01e02e5d8b82255fec1df94bd8748f1a19765d7182651be7`
(tracked `git diff -- src tests`, then NUL, new path, NUL, new file bytes).

- Required Pyright, Ruff lint/format, medium-severity Bandit, and import contracts
  passed on the completed production/test diff. API generation/check had no drift.
- Native `pytest -q -n4 --dist loadgroup` rerun passed: 3,126 passed, 90 skipped.
  The first run had one Chrome process failure; its isolated case passed, followed
  by the successful full rerun. Skips include physical Windows/PowerShell, live
  service opt-ins, the long streaming-resource opt-in, and unavailable local
  libplacebo proof; none are target-runtime passes.
- Real Chrome report smoke passed, as did production-method deferred Diff/Grid
  currentness and Grid mounting harnesses. CLI-contract documentation checks and
  strict Zensical build passed. Site-build failures were repaired by retaining
  out-of-site source paths and deleted historical-plan names as literal references;
  historical decisions were not changed.
- Fresh wheel and sdist passed `scripts/verify_distribution.py`. A separate fresh
  install outside the checkout passed help/version, package-owner imports, numeric
  default resolver startup, explicit secret exclusion, real-child deadline,
  repeated cancellation, zero connector calls, and reaping. Its initial package
  location assertion was corrected to resolve both sides of macOS's temporary-path
  symlink; this was a probe error rather than a distribution defect.
- Canonical Docker media/runtime/production-image gate passed: 276 tests, zero
  skips, plus runtime and production-image application/artifact proofs. The
  long streaming-resource proof was not rerun: collector ownership, whole-track
  memory bounds, admitted-lag behavior, and its transport implementation did not
  change. VSView/resolver process changes have separate real-child evidence.

Outstanding physical Windows acceptance uses the exact portable bundle and
visible VSView: exercise review confirmation for positive, negative, and zero
offsets plus keep-current, verify callbacks and accessible focus, interrupt an
active review and observe the child gone, and change a source after preparation or
during confirmation to verify no stale trims/manual/shared offsets are committed.
With the portable interpreter, observe default local resolution under the
SystemRoot-only environment, startup-output rejection, deadline and repeated
cancellation with child reaping and no HTTP attempt. Existing GPU/HDR10/DV,
range/timing/index/cache/update migration acceptance remains separate and open.
