Status: Active
Scope: Restore slow.pics legacy post-upload UX for clipboard copy, browser open, .url shortcut, and webhook delivery
Owner: Next Codex feature-loop session

# slow.pics Legacy UX Parity Plan

## Purpose

This plan freezes the approved workflow and product decisions for restoring the
deferred slow.pics legacy post-upload UX recorded in
`docs/plans/2026-06-01-slowpics-legacy-ux-followup-handoff.md`.

The target is to restore user-facing convenience behavior after a successful
slow.pics upload without changing the current slow.pics upload protocol,
rewriting report generation, or expanding the `run --json` machine contract.

The next implementation session must start with adversarial plan review before
any code changes, then execute one approved unit at a time through the Frame
Compare feature workflow.

## Workflow Entry

Use `frame-compare-cleanup-loop` as the controller pattern because there is no
separate feature-loop controller skill. Use the feature skills in each
controller slot:

- plan/refine: `frame-compare-feature-plan`
- review: `frame-compare-feature-review` plus `review-request`
- implementation: `frame-compare-feature-implement`
- findings: `review-adjudication`
- closeout: `closeout-verification`

Expected loop entry:

1. Load this active plan file.
2. Keep authoritative live state in `update_plan`.
3. Request adversarial review of this plan with `frame-compare-feature-review`
   plus `review-request`.
4. Adjudicate plan findings before implementation.
5. Execute one approved implementation unit at a time.
6. Review each implementation unit before moving to the next unit.
7. Use `closeout-verification` before marking this plan historical.

Initial review packet for the next session:

```text
REVIEW_REQUEST
TASK: slow.pics legacy post-upload UX parity
TASK_FAMILY: feature/public CLI-config-runtime integration
RISK_TIER: high
REVIEW_TARGET: active tracked plan
PLAN_OR_ARTIFACT: docs/plans/2026-06-01-slowpics-legacy-ux-parity-plan.md
REFERENCE_HANDOFF: docs/plans/2026-06-01-slowpics-legacy-ux-followup-handoff.md
FILES_IN_SCOPE: src/frame_compare/config/schema_models.py; src/frame_compare/config/defaults.py; src/frame_compare/config/schema.py; src/frame_compare/cli/entry.py; src/frame_compare/cli/run_command.py; src/frame_compare/cli/output.py; src/frame_compare/orchestration/types.py; src/frame_compare/orchestration/execution.py; src/frame_compare/orchestration/coordinator.py; src/frame_compare/orchestration/phase_tasks.py; src/frame_compare/services/publishers.py or focused sibling service modules; pyproject.toml; uv.lock; tests/config/test_schema.py; tests/cli/test_run_slowpics_options.py; tests/cli/test_run_command.py; tests/cli/test_run_output.py; tests/cli/test_run_report_open.py; tests/services/test_publishers.py or focused sibling service tests; tests/orchestration/test_phase_tasks_outputs.py; tests/test_cli_contract_docs.py; docs/current-cli-contract.md; docs/current-architecture.md
FILES_OUT_OF_SCOPE: src/frame_compare/render/**; src/frame_compare/vs/**; src/frame_compare/analysis/**; tools/windows_portable/**; Dockerfile; docker-compose.yml; live mutating slow.pics tests; generated HTML report upload controls except the reference-only starter spec named in Unit 7
KEY_INVARIANTS: no new run flags; no wizard prompt expansion; run --json stdout remains one JSON object with slowpics_url as the only machine-readable slow.pics result field; post-upload side-effect failures are warning-only; browser/report opening stays CLI-owned; webhook delivery is Frame Compare-owned outbound integration with strict external HTTPS and redaction; shortcut creation is deterministic filesystem output and is not part of uploaded-file cleanup
VERIFICATION_RUN: plan review only; implementation units must run focused tests plus the runbook full verification gate before closeout
KNOWN_RISKS: CLI/config contract drift; unexpected browser or clipboard side effects in automation; shortcut path ambiguity with run folders disabled; webhook SSRF/DNS rebinding gaps; JSON stdout contamination; dependency lockfile churn; report auto-open behavior conflict
```

## Task Family And Risk Tier

- Task family: feature/public CLI-config-runtime integration
- Runbook tier: High

Why high risk:

- The work changes the documented `[slowpics]` config surface.
- The work adds a runtime dependency for clipboard integration.
- The work adds OS/browser side effects, filesystem output, and outbound webhook
  behavior after upload.
- The work touches CLI output, JSON-mode guardrails, browser-opening behavior,
  and slow.pics integration ownership.
- Authority docs must be updated in the same pass as the public behavior.

## Frozen Product Decisions

These decisions are approved and must not be reinvented during implementation.

1. Restore all four deferred legacy UX features:
   - copy the slow.pics URL to the clipboard
   - open the slow.pics URL in a browser
   - create a `.url` shortcut for the slow.pics comparison
   - post the slow.pics URL to a configured webhook
2. Keep the feature surface config-only.
3. Do not add new `run` flags.
4. Do not expand `wizard` prompts.
5. Add these `[slowpics]` config fields:
   - `copy_url_to_clipboard = true`
   - `open_in_browser = true`
   - `create_url_shortcut = true`
   - `webhook_url = null`
6. Add `pyperclip` as a runtime dependency for clipboard support.
7. Keep `run --json` unchanged:
   - stdout remains a single JSON object
   - `slowpics_url` remains the only machine-readable slow.pics result field
   - no copy/open/shortcut/webhook telemetry fields are added
8. Treat post-upload side-effect failures as warning-only.
9. Clipboard copy and slow.pics browser opening run only in interactive CLI mode:
   not `--json`, not `--quiet`, and stdout is a TTY.
10. Shortcut creation and webhook delivery run whenever configured after a
    successful slow.pics upload, including `--json` and `--quiet`; warnings must
    stay off JSON stdout.
11. If slow.pics browser-open and report auto-open both apply, prefer opening
    slow.pics for this plan and suppress report auto-open for that run.
12. Human output should show enabled outcomes only, using the existing organized
    Rich result-summary style. Do not list disabled states by default.
13. CLI-owned clipboard copy and slow.pics browser-open actions must execute
    after a successful run result is available and before the human result
    summary is printed, so enabled outcomes and warning-only failures can be
    rendered with the summary. These action results are local CLI presentation
    state only and must not be added to `run --json`.
14. In `--quiet`, enabled success outcomes for copy/open/shortcut/webhook remain
    suppressed with the rest of the rich summary. Warning-only side-effect
    failures must be emitted only on stderr/log channels, never on stdout.
    In `--json`, no side-effect outcome or warning text may be written to
    stdout; stdout remains the single JSON object.

## Owner Seams

- Config schema/defaults: `frame_compare.config.*`.
- CLI command routing, interactive gating, browser-opening, JSON cleanliness,
  and human result formatting: `frame_compare.cli.*`.
- slow.pics upload remains owned by `frame_compare.services.publishers`.
- New webhook and shortcut behavior should live in a focused service owner or a
  narrow sibling of `publishers`, not inside report generation or render code.
- Webhook delivery must be owned by a focused service module that does not reuse
  the slow.pics upload `httpx.AsyncClient`, cookies, headers, or transport state.
  The service may own a short-lived isolated HTTP/TLS request path or an
  injected testable client/factory, but the implementation contract must keep
  cookies empty, redirects disabled, proxies/environment trust disabled, and
  slow.pics request headers unavailable to webhook delivery.
- Orchestration may carry typed post-upload status and warnings, but must not
  become the owner of clipboard, browser, shortcut, or webhook policy.
- Generated HTML reports remain static offline artifacts under
  `frame_compare.services.report`; report-triggered upload is not implemented in
  this workstream.

## Unit 1 Review Adjudication

Adversarial plan review found three blockers. All are accepted and resolved in
this plan before implementation may begin:

- Webhook DNS/SSRF policy is tightened so hostname targets are rejected when any
  resolved address is non-public, and webhook connection code must avoid the
  validation-to-connect DNS rebinding gap by either connecting to a pinned
  prevalidated address while preserving HTTPS certificate verification for the
  original hostname, or by stopping and replanning before Unit 6.
- Webhook HTTP ownership is frozen as an isolated Frame Compare-owned service
  path. Reusing the slow.pics upload client, cookies, headers, redirect policy,
  proxy/environment trust, or transport state is out of scope and invalid.
- CLI copy/open actions must run before the human result summary so enabled
  outcomes and warning-only failures have a defined presentation path. They
  remain interactive-only and local to CLI presentation, with no JSON fields.

The accepted verification additions are included in the affected implementation
units below.

## Implementation Units

### Unit 1: Plan Review And Contract Freeze

- Run adversarial review of this active plan.
- Adjudicate all findings before implementation.
- Stop if review finds unresolved product decisions, unclear owner seams, or
  insufficient webhook security policy.

### Unit 2: Config And Dependency Surface

- Add the approved `[slowpics]` config fields and defaults.
- Add `pyperclip` to runtime dependencies and update the lockfile.
- Update config schema/default tests and current CLI contract docs.
- Preserve the current root config `extra="ignore"` behavior unless explicitly
  replanned.

### Unit 3: Post-Upload Result Plumbing

- Add typed internal status and warning plumbing for post-upload actions.
- Include the narrow coordinator assembly handoff that carries retained
  post-upload action results from `RunArtifacts` into `RunResult`.
- Do not add JSON output keys.
- Preserve import-layer contracts and lazy CLI import behavior.
- Keep side-effect results stable enough for CLI output and tests, but do not
  expose them as a public import-level API.

### Unit 4: Clipboard And Browser UX

- Implement clipboard copy through `pyperclip.copy` at the approved CLI-owned
  interactive seam.
- Implement slow.pics browser opening at the CLI-owned interactive seam.
- Execute copy/open before printing the human result summary, collect enabled
  action outcomes and warning-only failures as CLI-local presentation state, and
  pass that state into the summary/warning renderer without changing `RunResult`
  JSON serialization.
- Do not launch real browsers or mutate the real clipboard in tests.
- Preserve report-generation ownership and keep report browser auto-open
  separate from slow.pics URL opening.
- Add tests for summary ordering, clipboard/browser warning placement,
  interactive-only gating, and report auto-open suppression when slow.pics open
  applies.

### Unit 5: Shortcut Filesystem Behavior

- Create a deterministic `.url` shortcut after successful upload when
  `slowpics.create_url_shortcut = true`.
- Write the shortcut at the run-level output parent:
  - `workspace.run_dir` when run folders are enabled
  - otherwise the common parent for the resolved screenshots/generated output
    when they share one
  - stop and replan if legacy-mode screenshots/generated paths do not have a
    safe common parent
- Treat a legacy-mode common parent as unsafe when it resolves to a drive root,
  filesystem anchor, UNC/share root, home directory, or any parent that is not
  under the resolved workspace root. Treat paths on different drives or anchors
  as having no safe common parent.
- Derive a filesystem-safe filename from current run metadata or upload title,
  with a stable fallback from the slow.pics URL key.
- Overwrite the same deterministic shortcut path on repeated writes.
- Do not delete the shortcut during `slowpics.delete_after_upload` cleanup.
- Surface write failures as warnings only.

### Unit 6: Webhook Delivery

- Add Frame Compare-owned webhook delivery after successful slow.pics upload
  when `slowpics.webhook_url` is set.
- Use payload shape `{"content": "<slowpics_url>"}`.
- Use fixed webhook policy for v1:
  - timeout: 10 seconds
  - attempts: 3
  - no redirects
  - isolated cookie-free request
  - no reuse of slow.pics cookies or headers
  - no proxy/environment trust
- Require strict external HTTPS:
  - reject non-HTTPS URLs
  - reject localhost, loopback, private, link-local, multicast, reserved, and
    otherwise non-public IP literal targets
  - reject DNS targets when any resolved address is disallowed or when resolution
    fails, returns no usable addresses, or mixes public and non-public addresses
  - prevent DNS rebinding between validation and connection by pinning the
    connection to a prevalidated public address while preserving HTTPS
    certificate verification and SNI for the original hostname
  - stop and replan before implementation if the chosen HTTP owner cannot
    implement pinned-address HTTPS correctly without a larger network-policy
    owner
- Redact webhook URL details in logs, warnings, and errors.
- Treat delivery failures as warnings only.
- Add tests for mixed allowed/disallowed DNS answers, all-disallowed answers,
  IP literal rejection, pinned-address connection behavior, slow.pics
  cookie/header isolation, redirect refusal, timeout/retry behavior, payload
  shape, redaction, and `--quiet`/`--json` warning placement.

### Unit 7: Human Output, Authority Docs, And Future Starter Spec

- Show only enabled action outcomes in the human result summary.
- Keep disabled/skipped states out of normal output unless needed as warnings.
- Keep `--json` stdout parseable as one JSON object.
- Update `docs/current-cli-contract.md` for config fields, defaults, JSON
  non-change, no new flags, no wizard prompts, warning-only behavior, and
  browser-open precedence.
- Update `docs/current-architecture.md` for the new post-upload UX owner seam,
  shortcut filesystem output, webhook external boundary, and CLI-owned browser
  opening behavior.
- Update `tests/test_cli_contract_docs.py` to lock docs to the live surface.
- The reference-only starter spec exists at
  `docs/plans/2026-06-01-report-confirmed-slowpics-upload-starter-spec.md`.
- Keep that spec non-active and not implemented by this plan.
- Preserve these starter intentions:
  - when local report review and slow.pics upload are both desired, the user can
    inspect the generated report before uploading
  - the CLI may wait for confirmation in that future workflow
  - report-triggered upload after CLI exit would require a separate design,
    such as a local service, protocol handler, or other explicit runtime owner
- Do not implement report UI upload controls, background services, or protocol
  handlers in this workstream.

## Verification Strategy

Primary verification modes:

- `contract-first` for CLI/config/JSON/docs behavior.
- `integration-ops` for OS/browser, filesystem shortcut, and outbound webhook
  boundaries.
- `manual-runtime` only for proof that cannot be automated without launching a
  real browser or mutating a real clipboard; default automated tests must mock
  those boundaries.

Required focused tests:

- Config schema/default tests for the new `[slowpics]` fields.
- CLI option tests proving no new slow.pics `run` flags.
- Wizard tests proving no prompt expansion.
- CLI JSON tests proving stdout remains a single JSON object and no new
  slow.pics telemetry fields appear.
- CLI/browser-open tests proving slow.pics open is interactive-only and wins
  over report auto-open when both apply.
- Clipboard tests with mocked `pyperclip.copy`.
- Shortcut tests for directory selection, filename sanitization, deterministic
  overwrite, write failure warnings, and cleanup interaction.
- Webhook tests for URL validation, disallowed hosts/IPs, DNS resolution policy,
  redirect refusal, timeout/retry behavior, payload shape, cookie isolation,
  redaction, and warning-only failure semantics.
- Human output tests for enabled outcomes only and warning placement.
- Explicit quiet/json warning-placement tests for shortcut and webhook
  side-effect failures.
- Authority doc lockstep tests.

Full runbook verification before closeout:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

On Windows, equivalent `uv run --no-sync ...` commands are acceptable when the
direct `.venv/bin/*` paths are unavailable, but the proof surface must remain
the same.

## Stop And Replan Triggers

Stop and return to planning if any of these occur:

- Implementation requires new `run` flags or wizard prompts.
- `run --json` needs copy/open/shortcut/webhook telemetry fields.
- Clipboard support cannot be implemented with `pyperclip` without breaking
  supported packaging or import-time behavior.
- Slow.pics browser opening cannot remain CLI-owned.
- Shortcut directory selection is ambiguous for legacy-mode paths.
- Webhook SSRF, DNS rebinding, redirect, timeout, retry, or redaction policy
  cannot be implemented safely in the chosen owner.
- Post-upload side-effect failures need to become fail-fast.
- Report-confirmed upload starts requiring report UI, a local service,
  background process, or protocol handler in this workstream.
- Authority docs conflict with observed code in a way that cannot be resolved in
  the same pass.

## Closeout

Before closing this workstream:

- Run the full verification gate or record exact documented-only gaps.
- Confirm authority docs match implemented behavior.
- Confirm no live network, real browser launch, or real clipboard mutation is
  required by default tests.
- Change this plan to `Status: Historical` in the same pass as closeout.
