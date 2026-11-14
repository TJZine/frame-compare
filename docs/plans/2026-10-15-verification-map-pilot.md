---
search:
  exclude: true
---

Status: Historical; superseded by the accepted repository-local application skill.
Outcome: The maintainer approved shared creation/maintenance skills and
`verify-frame-compare`. The canonical map now lives under
`.agents/skills/verify-frame-compare/features/` (outside the documentation site).
The discussion below records the pilot's earlier conclusions, not current routing
or new pass claims. Native, transfer and physical Windows gaps remain explicit.
Source: `236ec9de46cef1276085cb14ea276e5405d1da3f`, 2026-10-15.
Scope: Three journeys using existing tests and runbooks. This is a navigation
experiment, not a new required gate, complete coverage inventory, or release proof.

# Verification map pilot

Start with the user action below, follow its existing proof, and report the claim
that proof actually establishes. Product authority stays in the architecture and
CLI documents; specialist gates stay in the
[engineering runbook](../ENGINEERING_RUNBOOK.md#verification-policy). A future
behavior change still needs its applicable runbook gates. These selections do not
replace them.

| User action | Existing proof | Important boundary |
| --- | --- | --- |
| Plan a comparison and consume a typed JSON failure | [Installed CLI and dry-run side effects](#installed-cli-planning-and-failures) | Empty media names establish planning, not decoding or packaging |
| Open an offline report, change views and edit review notes | [Generated report in Chrome](#offline-report-browser-and-review-controls) | Synthetic report images; selected browser interactions, not a complete cross-machine review transfer |
| Review alignment, confirm the whole set, resume comparison | [Qt panel and authority contracts](#native-alignment-review-controls-and-authority) | Offscreen controls and simulated launch; real native media acceptance remains separate |

## Running and retaining evidence

Run from the repository root in the existing contributor environment. See the
repository profile for locked environment setup; do not sync a docs-only
environment before Python checks. Check the capability needed by the selected
journey rather than requiring the entire application runtime for every check.

These POSIX examples add evidence options to existing commands. Create one unique
directory for this run; keep it outside the checkout and outside subsequent test
cleanup. On Windows, use equivalent PowerShell paths/environment assignments.
This pilot does not validate Windows execution.

```bash
pilot_dir=$(mktemp -d "${TMPDIR:-/tmp}/frame-compare-verification.XXXXXX")
mkdir -p "$pilot_dir/evidence" "$pilot_dir/scratch"
git rev-parse HEAD > "$pilot_dir/evidence/source.txt"
git status --short > "$pilot_dir/evidence/worktree-status.txt"
git diff HEAD --binary > "$pilot_dir/evidence/worktree.diff"
uv run --no-sync python --version
```

The diff includes staged and unstaged tracked changes. Separately preserve any
relevant untracked code, fixtures or configuration after checking for secrets;
status alone records names, not the input bytes. HEAD alone cannot identify a
dirty checkout's tested behavior.

Record the actual command, Python/relevant package versions, OS, selected browser
or Qt platform, and exit status with the results. Inspect JUnit failures, errors
and skips; exit zero with a skipped browser or panel is not proof of that surface.
Keep console output on failure. Do not reuse an old result after relevant code,
fixtures, dependencies, or runtime assumptions change.

After inspection, copy any useful generated report or sidecar from `scratch` to
`evidence` before deleting only this run's scratch directory. Preserve JUnit and
CLI artifacts there. No screenshot, DOM dump or actual native session is retained
automatically by these commands. Archive the evidence somewhere durable before
removing the whole temporary run directory. Never delete another process's
profile, shared media cache, or user's application data.

## Installed CLI planning and failures

User goal: obtain a deterministic plan without doing the run, and handle invalid
input as typed, machine-readable failure.
Authority: [dry-run planning](../current-cli-contract.md#dry-run-planning).

Capability check: the contributor Python environment has pytest and the installed
`frame-compare` console next to its Python executable (the E2E resolver otherwise
falls back to PATH). Record the console selected by
`tests.e2e.harness.resolve_entry_point()`; a PATH fallback may belong to another
installation. Native source plugins, Chrome, credentials and media E2E
opt-in are unnecessary for this selection.

```bash
FRAME_COMPARE_E2E_ARTIFACTS="$pilot_dir/evidence/cli" \
uv run --no-sync pytest -q \
  tests/e2e/test_cli_dry_run.py \
  tests/e2e/test_cli_errors.py::test_cli_errors_are_typed_and_json_only \
  tests/cli/test_run_dry_run.py::test_run_dry_run_does_not_import_or_call_runtime_side_effect_owners \
  --basetemp "$pilot_dir/scratch/cli" \
  --junitxml "$pilot_dir/evidence/cli-results.xml"
```

The existing E2E harness creates isolated config/input/output roots, disables
metadata lookup, publishing and report auto-open, and bounds console subprocesses.
It executes `run --json --dry-run --skip-metadata --no-upload` against two empty
`.mkv` files. Assertions cover plan shape/source ordering and unchanged paths;
the error cases require the documented exit/error codes, JSON stdout and empty
stderr. The separate fresh-process test checks file contents as well as paths and
blocks runtime imports and side-effect owners. Keep those distinct proof claims.

Inspect the scenario command, stdout, stderr and summary under `evidence/cli`.
Each scenario replaces its matching artifact directory, so use a fresh run root.
This does not establish real media decoding, wheel installation, portable launch,
or all CLI/JSON edge cases. The E2E asserts selected deterministic fields, not
complete stdout equality across repeated runs. For a schema/secrecy change,
inspect `tests/cli/test_run_dry_run.py::test_run_dry_run_json_has_exact_allowlisted_shape_and_no_secrets`
and `tests/cli/test_run_json_errors.py`; those additional cases were not run in this
pilot. A CLI behavior change still requires the runbook's
[full verification](../ENGINEERING_RUNBOOK.md#full-verification).
A missing console is an environment gap; a mismatch
with the documented plan/error behavior needs investigation as a possible product
failure, without changing expectations to obtain a pass.

## Offline report browser and review controls

User goal: open the generated offline report, operate view controls and enter
review notes. Owners: [report viewer architecture](../current-architecture.md#report-viewer),
[user guide](../guides/reports-and-overlays.md), and
[browser verification](../ENGINEERING_RUNBOOK.md#report-viewer-verification).

Capability check: Chrome/Chromium is discoverable on PATH or at native macOS
Chrome's standard path; otherwise set `REPORT_BROWSER` to its executable. The
trusted-input helper uses the locked `nodejs-wheel-binaries` runtime, not PATH
Node. Inspect missing-browser/package skips before claiming a browser pass.

```bash
uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py \
  --basetemp "$pilot_dir/scratch/browser" \
  --junitxml "$pilot_dir/evidence/browser-results.xml"
```

The production report generator makes offline HTML with synthetic one-pixel PNG
images, two source descriptors, geometry and long labels. Real headless Chrome
loads percent-encoded paths and checks initialization, mode/ARIA state across
viewport/scale cases, focus, fit controls, offsets, labels and Unicode note input.
Most probes use injected DOM instrumentation; note insertion additionally uses
Chrome's trusted input events. The module also has mocked helper retry/cleanup
tests: its total case count is not a count of real browser journeys.

JUnit and console results are the retained assertions; generated HTML/images stay
in the chosen browser basetemp until copied or cleaned. Temporary Chrome profiles
used for DOM dumps are removed by their helper; trusted-input profiles remain in
basetemp, and owned Chrome children are terminated/reaped by the input helper.
A passing result
does not establish visual quality beyond the asserted checks, another browser,
real media rendering, or download/import/reload of a review moved to another
machine. Existing `tests/services/test_report_viewer_state.py` and
`test_report_review_state.py` cover additional state semantics through the Node
harness; they are not browser transfer acceptance. Relocation identity also has
focused proof at `tests/services/test_report.py::test_report_id_identity_excludes_paths_and_timestamps`
(not run here). The complete transfer journey remains unobserved: follow the
runbook's browser/manual route to observe Export producing a file, copy the
report/assets and exported review to the destination, import through the UI with
fresh storage, apply the chosen merge/replace, and reload. Respect matching report
ID/payload version and storage availability. This is an acceptance gap for that
promise, rather than a demonstrated product defect.

## Native alignment review controls and authority

User goal: enable `audio_alignment.use_vsview` or
`--force-interactive-alignment`, open **Tool Panel → Frame Compare Alignment
Review**, visit each source at the matching moment, confirm the whole set or keep
current alignment, then close the viewer to resume. Follow the
[user guide](../guides/vsview-review.md) and
[authority contract](../current-architecture.md#alignment-evidence-reuse-and-native-review).

Capability check for the selection below: importable PySide6 and VSView plus an
offscreen Qt platform. For real generated-session media proof, also establish the
appropriate native runtime and `core.lsmas`; BestSource being present does not
establish L-SMASH capability. Use the existing
[runtime capability/GUI recipe](../ENGINEERING_RUNBOOK.md#docker-runtime-verification)
for its supported host: `tools/verify_docker_gui.sh` owns the generated three-source
offscreen session proof under its Linux X11 wrapper requirements. For the Windows
target, follow the separate
[portable/release-path procedure](../ENGINEERING_RUNBOOK.md#windows-portable-release-path-verification).
Offscreen Linux-container proof, visible X11 launch and physical Windows acceptance
remain different claims.

```bash
QT_QPA_PLATFORM=offscreen uv run --no-sync pytest -q \
  tests/vsview/test_alignment_review_package.py \
  tests/vsview/test_alignment_review_panel.py::test_provisional_zero_is_visible_but_never_seeds_manual_authority \
  tests/vsview/test_alignment_review_panel.py::test_mixed_states_save_authority_labels_and_preserve_evidence \
  tests/vsview/test_alignment_review_panel.py::test_one_primary_action_saves_complete_viewer_positions \
  tests/vsview/test_alignment_review_panel.py::test_known_offsets_are_whole_set_and_serialize_canonical_pairs \
  tests/services/test_alignment_workflow_vsview.py::test_manual_zero_preserves_rejected_attempt_and_diagnostic_digest \
  tests/services/test_alignment_workflow_vsview.py::test_optional_native_review_retains_computed_offset \
  tests/services/test_alignment_workflow_vsview.py::test_forced_missing_result_stops_alignment \
  tests/orchestration/test_phase_alignment_contract.py::test_provisional_audio_candidate_cannot_reach_trim_authority \
  tests/services/test_alignment_reuse_cache.py::test_computed_this_run_provisional_result_is_not_write_eligible \
  tests/services/test_alignment_reuse_cache.py::test_computed_this_run_without_trusted_attempt_is_not_write_eligible \
  --basetemp "$pilot_dir/scratch/native" \
  --junitxml "$pilot_dir/evidence/native-results.xml"
```

These checks load the installed plugin registration, drive real offscreen Qt
widgets with synthetic viewer metadata, and use fixture audio/launch responses for
workflow assertions. They distinguish accepted zero, provisional zero, unavailable
and manual authority; require complete decisions; retain original evidence/digest;
reject provisional trim/cache authority; and distinguish optional from forced
missing results. Test-owned media placeholders, sidecars and override files live
under basetemp. They do not launch an actual review child or decode native media.

For future live proof, supply a disposable root/cache and copied or generated
media. Session sidecars and persisted manual overrides are different owners;
L-SMASH may also write indexes beside source media. Preserve useful evidence before
the existing verifier cleans its owned resources. Do not overlap full Docker
verifiers in one checkout because their generated-media cache/pruning is shared.

## Pilot observations and decision boundary

At the source above on macOS, the CLI selection passed **8 cases**, browser module
passed **22 cases**, and offscreen alignment selection passed **14 cases**; no
selected cases skipped. These totals include helper and simulated-contract tests.
Chrome was 155.0.8059.82, Python 3.13.16, VSView 0.13.0 and PySide6 6.11.2.
VapourSynth R81 exposed `core.bs` but not `core.lsmas`; the complete native journey
was **not run**. No Docker, packaging, physical Windows or visible-native result
is claimed. Detailed logs, JUnit, environment, commands and retained synthetic
artifacts accompany the maintainer's pilot report outside the repository.
They are in the companion `frame-compare-verification-pilot.zip`, under `evidence/`
(including `results.json`, invocation JSON, JUnit and environment). The checkout
alone does not retain those run receipts.

No stale recipe or product defect was established in these three routes. The
increment is the user-action index and the joined proof boundaries; the existing
runbook already distinguishes browser, synthetic Qt, native and platform evidence.
The shared `verify-code` skill already requires controlled inputs, exact recipes,
skip semantics, capability limits and evidence outside cleanup. This pilot does
not establish a need to duplicate those rules or create a separate global skill.

Discuss whether this local index earns its upkeep, should be folded into the
existing profile/runbook, or should be removed after the experiment. A thin
optional global reference could describe mapping a few important journeys when
navigation is demonstrably difficult; a separate discoverable skill would offer
an explicit maintenance trigger but add overlap and another entry point. No
global change, recurring maintenance requirement or repository-wide adoption is
authorized by this pilot's results. There is no controlled evidence of time/token
savings or reliability improvement.
