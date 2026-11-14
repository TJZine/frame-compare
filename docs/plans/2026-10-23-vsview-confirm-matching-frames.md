---
search:
  exclude: true
---

# VSView: confirm matching frames directly

Status: Historical. Implemented, independently reviewed and committed locally on 2026-10-23.
Starting source: `v0.7.0` at `ce0bd4574e95f0225bb4486cc0ad4ba796afad63`.

## Authority and outcome

The current human request is to implement the simpler workflow discussed in this
chat, including tracking source frames while the panel is closed, using a worker
and reviewer chat with working callbacks, and investigating automatic unlinking.
Authorization is in parent `01a16612-16e1-7af0-ba82-5cfea0da3233`, local host,
turn `01a167ac-2076-7e81-9eda-7f29a77f0ab3`, human message
`01a167ac-20de-73f0-b6ab-a739ad955348`. Children must retrieve that actual human
message before callbacks. This request supersedes the earlier required
Anchor/Select workflow; old plans are historical context, not new instructions.

The ordinary workflow is: browse each source to a matching moment, inspect the
automatically updated original-frame numbers, then press **Confirm matching
frames** once. Remove required Anchor, per-source Select, and separate Save actions.
No editing or navigation automatically confirms or writes alignment. The explicit
whole-set confirmation grants manual numeric intent, not proof of displayed pixels.

## Product obligations

- Retain an independent original-frame position for each source, including while
  the review panel is hidden or another tool tab is selected. Reopening must show
  current positions, not silently reused stale proposals. Track from workspace
  load; do not depend on first opening the sidebar.
- Confirm one complete, stable, in-range set, including Reference; preserve zero.
  Pending/playing/unavailable/wrong-session positions must not become confirmation.
  Respect source switching, rapid seek/switch ordering, reload, close and destruction.
  Revalidate the submitted snapshot in the handler, including after queued events.
- Successful confirmation freezes the saved set and preserves existing close/resume
  behavior. Failed writes leave the workflow editable. Keep current alignment and
  known-offset manual entry remain separate choices with their existing authority.
  Manual numeric fallback may remain under the existing advanced controls, with
  explicit ownership so passive updates cannot overwrite an edit.
- Preserve source identity, metadata-v5 session validation, complete atomic sidecar
  writes, freshness, offset sign `Reference - Comparison`, cache/manual authority,
  original audio provenance, and runtime-free CLI paths. No sidecar schema change
  is required merely to remove UI steps.
- Preserve existing live video hints and useful opening-offset provenance. Remove
  obsolete pinned-anchor wording, controls, state and tests; retain distinct proof
  obligations rather than preserving the old private structure. Avoid new layers
  or duplicate position authorities when a small explicit owner suffices.
- HDR preview settings, tone mapping, rendering and user media/config are outside
  this change. Ordinary VSView sessions remain inactive.

## VSView integration decision boundary

Installed and locked VSView is 0.13.0. Its plugin dispatcher suppresses frame/source
callbacks for hidden widgets. `PluginAPI.current_frame` exposes only the active
workspace position; `VideoOutputProxy` has no retained per-output position.
The workspace itself stores each output's `last_frame`. Playhead UNLINK is state 0;
the workspace loads it from local `synchronization.sync_playhead` settings. Public
plugin settings are copied read-only proxies, not a supported setter for that UI.

Investigate supported hooks and generated-session settings before choosing the
integration. A narrow, explicitly version-checked bridge to the pinned VSView
workspace may be justified if public hooks cannot carry the obligation; keep that
coupling in one owner, gated to validated Frame Compare sessions, with actual
installed-workspace proof and owned lifecycle cleanup. Do not scatter private
access, broadly monkeypatch VSView, edit site-packages, vendor/fork the dependency,
or pretend active-only polling is lossless per-source state. Return consequential
integration choices with evidence to the controller if a broader change is needed.

Attempt automatic unlinking only for generated review sessions using a demonstrated
session-local route. Do not change global viewer preferences or unrelated sessions.
If automatic unlinking cannot be implemented within that boundary, preserve an
honest manual-unlink instruction and report the limitation. Do not claim it worked
from a changed settings value without observing independent navigation.

### Accepted integration direction after independent source review

The first reviewer callback arrived successfully. The controller accepted a single
explicitly VSView-0.13-bound workspace bridge: read every retained output position
by validated `vs_index`, and unlink that exact owning workspace through
`tab_manager.sync_playhead_btn.set_state(state=0)` after generated-session validation.
This operates the actual control used for source switching; per-script persistence
is acceptable, global preference changes are not. No added settings artifact is
needed merely to duplicate that control. Actual installed-workspace navigation
must still establish the behavior; source review alone is not runtime acceptance.

`has_pending_frame` is not a complete readiness gate: VSView clears its queued
pending frame before an in-flight seek completes. The bridge must account for
in-flight rendering, disabled switching, playback, first load/reload, source
identity and active-position consistency, and re-read all values at confirmation.
The source notification precedes committed seek state. Use the workspace-owned
positions rather than turning notifications into authority. Initialize from the
ungated workspace-load hook, stop on reload/destroy, and avoid accumulating destroy
callbacks across reloads. Tests must distinguish these races and lifecycle states.

The reviewer established no material plan defect or persisted-schema change.
Its first phase used source inspection only, with no native/UI runtime claim.

## Ownership and execution

Worker: `worker` preset, `gpt-6.1-sol/medium`; implementation judgment and native
boundary diagnosis justify this executor. Own scoped changes under
`src/frame_compare/vsview/`, corresponding `tests/vsview/`, affected existing
alignment integration tests/tools that drive the replaced UI, and
`docs/guides/vsview-review.md`, `docs/current-cli-contract.md`,
`docs/current-architecture.md`. Update the existing alignment-review verification
feature if its concrete commands/actions become obsolete; no broad skill rewrite.
Report before expanding to packaging/dependencies or other product modules.
Orchestrator owns this plan, verification ledger, integration and commits.
Reviewer: `reviewer`, `gpt-6.1-sol/high`, read-only design/implementation review.

Dispatched local chats (explicit role model/effort arguments):

- Worker: `01a167b0-f88f-7213-a221-74e97325dbd6`, `gpt-6.1-sol/medium`.
- Reviewer: `01a167b1-5a63-7fe1-87cd-32dec388078a`, `gpt-6.1-sol/high`.
- Callback target: `01a16612-16e1-7af0-ba82-5cfea0da3233`, local.

The reviewer first independently investigates integration feasibility while the
worker works within the plan; the same reviewer later checks the finished diff.

Both children: never push, rebase, reset, stash, switch branches or amend; never
`git add -A`; do not stage or commit. Do not touch `.codex/`, `.handoff/`,
`docs/TODO.md`, the five preexisting untracked VSView plans or `generated/`.
Inside Docker use `python -m pytest`. No native/plugin/driver installation, user
settings changes, publication or messages outside the authorized child/parent route.
Local machine is Windows TristansPC; local Docker is unavailable.

## Evidence and completion

Use develop-code for implementation, verify-code to choose proof, and review-code
for the independent review. Focused behavior first; local Ruff/format/Pyright,
Bandit medium, import contracts, CLI/doc contract checks and strict tracked-docs
build as applicable. Run the full native suite once for this new public workflow,
preserving any baseline/environment failures separately; do not repeat it by phase.
Native/plugin boundary changes require compatible-host integration evidence.

Required distinguishing cases include panel never opened, hidden/reopened and
other tool selected; independent A/B positions, rapid seek/switch and paused
notification ordering; zero, bounds, playback/pending, manual drafts, failed
writes, reload/destroy; exact whole-set sidecar offsets and authority/provenance.
Use real Qt and a real installed VSView workspace with tiny generated SDR media
for hidden-tracking/unlink claims, not solely fake PluginAPI fixtures. Keep visible
desktop, offscreen integration, packaged Windows and physical-host claims separate.
Do not attach tests to or close the user's existing VSView session. Put receipts
under an owned temp root or `.tmp/vsview-confirm-2026-10-23/`, never `generated/`.

Children put complete reports in their own chats, then send only `done` or `blocked`
to the verified parent. Reports include source/diff, files, commands/exit codes,
counts/skips, limits and actual model/effort. Minimal callbacks have worked; do not
send detailed repository/environment reports in the cross-chat message. No polling
or sleeps to await children: parent resumes on arrival and retrieves the report.

No push is authorized for this new feature. Integrate and commit reviewable work,
then report the concrete result and any remaining acceptance or publication step.

## Implementation and verification record

Actual native environment: Windows TristansPC, Python 3.13.7, VSView 0.13.0,
PySide6 6.11.2. The installed Qt version differs from the portable/locked 6.12.0;
no environment, driver or plugin was changed. Source/offscreen evidence is scoped
accordingly. Full reports and JUnit receipts are under
`.tmp/vsview-confirm-2026-10-23/evidence/`.

Worker implementation removed the mandatory anchor/cohort workflow, added the
contained workspace-position bridge and 50 ms UI refresh, confirmed complete
snapshots in one action, and updated affected docs and existing proof scripts.
Worker receipts: 217 passed/1 POSIX-only SIGINT skip in the initial VSView suite;
101 passed/no skips in the final affected selection; 1 additional zero/frozen-handler
regression passed. Its installed-workspace integration used generated SDR media
and real Qt/VSView/decoder, including never-opened/hidden/other-tool navigation,
independent positions, actual Unlink, seek pending-gap rejection, exact sidecars,
manual ownership, failed writes, save freeze, reload and cleanup. This does not
establish visible desktop, packaged runtime, physical display or parent CLI resume.

Controller whole-tree Ruff lint/format, Pyright, Bandit medium and import contracts
all exited 0 on the initial finished implementation: 561 formatted files, zero type
errors/warnings, no medium/high Bandit findings, and two kept import contracts.

The single full suite command was `QT_QPA_PLATFORM=offscreen
FRAME_COMPARE_REQUIRE_LIBPLACEBO=1 uv run --no-sync pytest -o addopts='' -q -n4
--dist loadgroup --basetemp=.tmp/vsview-confirm-2026-10-23/full-suite-scratch
--junitxml=.tmp/vsview-confirm-2026-10-23/evidence/full-native.xml`, with media opt-in
unset and E2E artifacts redirected to the owned evidence tree.
**Exit 1: 4119 passed, 76 failed, 78 skipped in 395.14 s.** This is not a green
aggregate. Failure classification:

- One previously established authored-config warning mismatch in
  `test_execute_run_propagates_collection_warning_once_through_result_summary_and_record`.
  The prior same-working-directory pre-feature reproduction remains recorded in
  the fast-HDR verification ledger; no config or lifecycle changes were made.
- One obsolete four-click portable proof assertion in
  `test_windows_portable_python_vsview_proof_covers_viewer_first_whole_set`;
  the new confirmation/Keep flow correctly has two clicks. Worker scope was
  expanded to migrate that exact existing assertion while preserving its obligations.
- 72 updater E2E and two key-generation failures caused by controller test setup:
  the scratch directory was inside the repository, and the key generator correctly
  rejected private-key output there. No production bypass or guard weakening is
  appropriate. Only these 74 cases are being rerun with a unique scratch root
  outside the repository; the whole suite will not be repeated.

The final reviewer established one accepted P2: a paused background playback worker
can still commit a frame after the existing idle flags become clear. Its controlled
source-level interleaving reproduced a paused snapshot changing from 10 to 11 after
releasing the worker; this was not a native playback reproduction. The original
native proof only toggled `is_playing`, so a delayed-frame pause/drain proof is
required. The worker is correcting the pinned bridge's task-quiescence gate and
adding sensitive evidence. Fixed waiting delays are not accepted as quiescence.
Other reviewed requirements and maintainability paths cleared. Minimal callbacks
from both worker and reviewer arrived successfully; no child polling was used.

The setup-affected portable retry exited 0: **74 passed, zero skipped**. The owned
retry driver selected only those failures from the original JUnit file and used
an outside-repository temporary root; command argv, log and XML are retained as
`portable-recheck-command.json`, `portable-recheck.log`, `portable-recheck.xml`.
No key-generation guard, updater code or unrelated test was modified. This retry
does not rewrite the failed full-suite outcome into a successful aggregate.
The original full run also passed the real installed workspace test in 8.082 s.
After preserving the retry receipts, the controller verified the resolved owned
outside-repository scratch path and removed only that directory and its generated
test keys. Cleanup exited 0; the JUnit/log/argv receipts remain in the task tree.
The full run's 78 skips comprise 20 unavailable browser cases, 5 Windows filesystem
distinctions, 8 media opt-ins, 3 resource opt-ins, 2 live-service opt-ins, 21 other
platform/process cases, 1 missing-Perl case and 18 missing-jq cases.

Strict documentation build: `uv run --no-sync --with zensical==0.0.71 zensical
build --clean --strict -f <owned-tracked-docs-snapshot>/zensical.toml`, exit 0,
no issues, 2.26 s. The snapshot copied tracked docs/overrides/config plus this
task-owned new plan. The five protected unrelated untracked plans were excluded
from that snapshot and remain untouched; their previously recorded working-tree
link problems are not claimed fixed. `docs-snapshot-root.txt` records the snapshot.

### Focused review correction

The worker added an actual-executor quiescence gate to `WorkspacePositions.snapshot`:
confirmation requires the global Qt thread pool's active count to be zero, in
addition to the existing source/session/playback/seek checks. This covers the
paused dequeued worker and assigned/queued workers before their Python task
counter starts. The tradeoff is conservative: other VSView background jobs sharing
that pool may temporarily postpone confirmation. No fixed settling delay, hook
patch, dependency edit or additional private task-counter coupling was introduced.

The real installed-workspace proof now holds a native frame bundle's future after
the actual playback worker dequeues it, pauses, rejects an early snapshot/sidecar,
then releases it and observes the late frame commit before readiness returns. A
second control queues a playback task before its wrapper starts. Isolated negative
controls removing only the new gate fail at both intended assertions; their
diagnostic wrapper exited 0. Receipts are `worker-pause-negative-controls.json` and
the corresponding logs. Early prototype failure-cleanup timeouts and incomplete
decoder color metadata were corrected before final proof; they are not acceptance
evidence. The final fixture uses the generated session's existing SDR defaults,
checks for render failures, releases held work in cleanup, and terminates only its
owned child after an uncaught assertion.

The obsolete portable proof test now checks the two actual Confirm/Keep receivers,
event processing, complete lineup and complete confirmed/keep decisions. It no
longer requires the removed four-click workflow. No unrelated updater behavior or
tests were changed.

Final affected verification (`tests/vsview`, that exact portable proof case, and
CLI contract docs) exited 0: **224 passed, 1 POSIX-only SIGINT skip**, 30.548 s.
Receipt: `worker-pause-final.xml`. The delayed native case alone also passed,
exit 0. The full repository suite was not repeated after this correction; its
earlier failed aggregate and the narrowly scoped retries retain their stated scope.

Controller final whole-tree Ruff lint/format, Pyright, Bandit medium and import
checks all exited 0 again after the correction: 561 formatted files, no type
errors/warnings, no medium/high findings, two kept import contracts. `git diff
--check` exited 0. The strict tracked-docs snapshot build also passed after the
updated correction docs, exit 0 with no issues in 2.04 s. The full suite is not
repeated merely for the focused review phase. Visible native GUI, packaged Windows,
Docker and matching-head hosted CI remain **UNRUN** for this new UI change.

### Fresh adversarial UI/UX review dispatch

The focused reviewer turn failed before producing a report because the selected
model was at capacity. This is not a review clearance or a callback failure.
The user explicitly requested a fresh reviewer chat via
`orchestrate-implementation-chats`; replacement reviewer
`01a167e1-b363-7330-9dd4-2304361b5907` on host `local` uses the actual
`reviewer.toml` selection, **gpt-6.1-sol / high**, supplied explicitly at creation.
It first finishes the focused playback-quiescence re-review, then conducts the
independent task-based UI/UX walkthrough using `review-code` and `interface-design`.
The assignment covers the complete working-tree feature diff against
`ce0bd4574e95f0225bb4486cc0ad4ba796afad63`, including owned new files.

The reviewer has no source or Git write ownership. It records its full findings
in its own chat and, after verifying the actual human authorization, sends only
`done` or `blocked` to orchestrator `01a16612-16e1-7af0-ba82-5cfea0da3233` / `local`.
No polling or idle wait loop is scheduled. The controller adjudicates findings,
integrates accepted fixes, and creates Conventional Commits covering every scoped
feature change, as the user additionally requested. Protected unrelated plans
remain excluded. Publication remains a separate decision.

The original reviewer subsequently recovered and delivered its minimal `done`
callback. Its focused re-review clears the P2 correction with no new material
findings. Independent native-workspace and migrated portable-contract checks
exited 0: **2 passed, 0 skipped**, JUnit 4.748 s. Receipt:
`reviewer-pause-6d2092ba.xml`; full report is retained in the owned evidence tree
as `reviewer-focused-completion.txt`. Earlier uv-cache and shared pytest-cache
access failures remain reported separately; the clean rerun used the existing
interpreter with pytest caching disabled. No source or Git edits were made by
that reviewer. The fresh UI/UX reviewer was notified that this dependency is
complete so unchanged correctness checks need not be repeated.

### Fresh UI/UX review findings awaiting user discussion

Reviewer `01a167e1-b363-7330-9dd4-2304361b5907` delivered its `done` callback.
It cleared the focused correctness gate and reported two validated P2 findings:
focused panel buttons lose Space activation to VSView playback; and a busy
workspace can recommend manual entry, then display all frames ready while
confirmation remains disabled without explaining the remaining busy-state gate.
Recommended corrections are scoped native keyboard activation and persistent
busy-state guidance, preserving the executor-quiescence gate. No P0/P1 or material
aesthetics-only finding was reported. The ordinary mouse flow, exact source/frame
mapping, write-error recovery and saved freeze worked in its native offscreen
walkthrough. Its isolated reproductions and correction probe exited 0; no product
fix was made. Full report and evidence:
`.tmp/vsview-confirm-2026-10-23/ux-review/uxr-01/report.txt`.

The user requested discussing findings before implementing them. No fresh worker
is dispatched until that discussion selects the changes. Accepted changes will
go to a fresh worker, followed by independent review and controller-owned
Conventional Commits for the whole feature. Visible desktop, packaged runtime,
physical display, parent CLI resume, Docker and matching-head CI remain UNRUN.

### Accepted UX fixes and fresh worker dispatch

The user accepted both P2 findings and explicitly requested a fresh worker,
independent re-review, and proper commits for all scoped changes. Actual human
authorization: parent `01a16612-16e1-7af0-ba82-5cfea0da3233` / `local`, turn
`01a167ec-6852-78c2-b1b3-8d213130724f`, message
`01a167ec-68b5-7501-99dc-1d3af52e1ae3`.

Fresh worker `01a167ed-a914-78c2-903c-f668258d745f` / `local` uses the current
`worker.toml` selection **gpt-6.1-sol / medium**, explicitly supplied at creation.
It owns scoped keyboard activation and waiting-state UI corrections in the panel,
their affected panel/native tests, and directly relevant guide/feature-map wording.
It preserves the workspace quiescence guard and all existing source/persistence
authority. The independent fresh reviewer will check these fixes afterward.

The worker has exclusive owned native-test workload while active. The controller
owns this plan, integration, explicit staging and Conventional Commits covering the
whole feature; unrelated protected plans remain excluded. Full reports remain in
the child and owned evidence tree, with only `done`/`blocked` callbacks to the
verified parent. No polling or idle wait loop is scheduled.

Fresh worker implementation is complete: control-scoped unmodified-Space handling,
persistent busy-state guidance, affected native proof, and relevant guide/feature
wording. Focused selection exited 0 with **66 passed, zero skipped**. Both
correction-removal controls failed at their intended assertions. A final
save-error assertion addition encountered one 90-second native child timeout;
diagnostic and focused pytest retries of that current harness passed, but the
isolated timeout's cause is unresolved. The worker report retains all attempts at
`.tmp/vsview-confirm-2026-10-23/ux-fix/report.txt`.

The worker's literal `done` callback was rejected by automatic approval review,
which stated that retrieved transcript/tool authorization was untrusted and no
trusted user instruction authorized the callback. The worker did not retry or
bypass the rejection. The controller retrieved the completed report on the
user's next status request; automatic handoff did not occur. Earlier reviewer
callbacks succeeded, so delivery is not described as universally reliable.
Independent reviewer `01a167e1-b363-7330-9dd4-2304361b5907` has now been dispatched
to re-review both fixes, their sensitive native proof and the unresolved timeout
limit. No commits have yet been created.

### Final acceptance and local integration

The fresh reviewer completed the focused fix re-review and successfully delivered
its minimal `done` callback. Both P2 findings are resolved, with no new material
finding established. The independent current-source component/native selection
exited 0: **66 passed, zero skipped**, JUnit 11.535 s. Receipt:
`.tmp/vsview-confirm-2026-10-23/ux-review/fix-check/focused.xml`; detailed verdict
and timeout adjudication: `ux-review/fix-check/report.txt` under the same task root.
Keyboard checks establish exactly-once activation and preserved viewer playback;
busy-state checks preserve manual drafts, prevent early sidecars, recover after
drain, retain save errors and prioritize saved guidance. The controller accepted
this evidence and inspected the final staged file list and whitespace checks.

The single 90-second worker native timeout remains unexplained. Its diagnostic,
worker retry and independent reviewer run passed, but those passes do not prove
intermittent runtime reliability. No product deadlock or repeatable failure
mechanism was established. If it recurs, preserve child output on
`TimeoutExpired` and collect bounded progress/traceback evidence before changing
timing. It is not counted as a successful run.

Final controller gates on the reviewed implementation all exited 0:

| Command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m ruff check --no-cache .` | All checks passed |
| `.venv/Scripts/python.exe -m ruff format --no-cache --check .` | 561 files formatted |
| `.venv/Scripts/python.exe -m pyright --warnings` | Zero errors or warnings |
| `.venv/Scripts/python.exe -m bandit -c pyproject.toml -r src --severity-level medium` | Zero medium/high findings; 32 low findings |
| `.venv/Scripts/lint-imports.exe --config importlinter.ini` | Two contracts kept |
| `git diff --check` and `git diff --cached --check` | No whitespace errors |

The strict tracked-docs snapshot recipe above exited 0 again, no issues, 2.04 s.
The initial sandboxed attempt exited 1 before building because uv's existing cache
was inaccessible; the approved cache-access retry produced the successful build.
No dependency or settings changes were made. Protected unrelated untracked plans
remain excluded from the snapshot and unchanged.

Final source-contract selection:

```text
.venv/Scripts/python.exe -m pytest -o addopts='' -p no:cacheprovider -q tests/workflows/test_docker_gui_contract.py tests/windows_portable/test_windows_portable_docs.py tests/windows_portable/test_windows_portable_build_scripts.py::test_windows_portable_python_vsview_proof_covers_viewer_first_whole_set tests/test_cli_contract_docs.py --basetemp .tmp/vsview-confirm-2026-10-23/controller-final-contracts --junitxml .tmp/vsview-confirm-2026-10-23/evidence/controller-final-contracts.xml
```

Exit 0: **17 passed, zero skipped**, 1.18 s. These are source-contract checks,
not Docker or packaged-runtime acceptance. The earlier full-suite failed aggregate
and its scoped corrections retain their separately documented results; no full
suite was repeated after the UX fixes.

Implementation, affected proof, runtime harness migrations, guide and product
contracts are committed together as
`6b0162ea8d9c8bf28ec96ac01235ed3818d2c8ae`
(`feat(vsview): confirm matching frames in one step`), using 19 explicit paths.
This plan and verification record are committed separately with a Conventional
Commits documentation subject. All scoped feature files are included; the five
preexisting unrelated plans remain untracked and untouched. Neither child staged
or committed. No push or other publication was performed.

Final environment remains native Windows **TristansPC**, Python 3.13.7,
VSView 0.13.0 and PySide6 6.11.2. Visible desktop, packaged Windows/Qt 6.12,
physical-display, assistive-technology, parent CLI close/resume, Docker and
matching-head CI acceptance remain **UNRUN**. Callback delivery is mixed:
reviewer callbacks succeeded, but the fresh worker callback was rejected by
automatic approval review as recorded above. The controller recovered that report
on the user's next activation; no callback bypass or polling loop was introduced.
