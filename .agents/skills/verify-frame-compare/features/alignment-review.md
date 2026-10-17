# Confirm alignment and resume the comparison

## Sub-features

- Reach the generated VSView session and its **Frame Compare Alignment Review**
  panel, with a reference and all comparison outputs.
- Visit each output, capture a matching moment and confirm the complete lineup;
  alternatively enter known offsets or keep the current alignment.
- Save one session-bound whole-set result, close VSView and resume the comparison
  with the correct manual/applied authority and retained original evidence.

Authority: [VSView review guide](../../../../docs/guides/vsview-review.md) and
[alignment evidence/native review contract](../../../../docs/current-architecture.md#alignment-evidence-reuse-and-native-review).
Owners: `src/frame_compare/vsview/`, `services/alignment_vsview.py` and
`orchestration/phase_alignment.py`; follow current imports for exact ownership.

## How to get to it (user POV)

With suitable media in a disposable root, set `audio_alignment.use_vsview = true`
or run `frame-compare run --root <owned-media-root>
--force-interactive-alignment --skip-metadata --no-upload`. Disable report auto-open
and metadata/publishing in that root's config as in the CLI harness; use copied or
generated media, a private output/cache, and no user credentials. Actual media is
required here: the CLI plan fixtures are empty and cannot launch decoding.

Run this actual review from an interactive desktop terminal with usable stdin and
stdout. The workflow checks TTY availability; an ordinary captured subprocess is
not a substitute for a visible review session. Capture evidence alongside the
interaction without suppressing that prerequisite.

When the generated VSView session opens, choose **Tool Panel → Frame Compare
Alignment Review**, unlink playheads, visit every source and leave each at the
same visible moment. Observe the `positions captured — ready to confirm` state,
then select **Confirm these aligned positions**. For known offsets, expand **Enter
alignment manually...**, choose **Known offsets**, enter every comparison using
`reference − comparison`, and select **Confirm these known offsets**. **Keep
current alignment** preserves current authority without accepting a provisional
candidate.

After saving, require **Alignment choices saved** and **Close VSView to resume
Frame Compare.** Close the owned viewer and observe the resumed comparison and
resulting applied authority. Closing without saving is a different path; optional
review keeps current alignment, whereas forced missing review fails closed.

## Driving it with Qt controls and the native runbook

Choose and label the proof level before driving. For the component route, doctor
checks the packages, not a decoder or a visible desktop:

```sh
uv run --no-sync python -c "import importlib.metadata as m; import PySide6,vsview; print('PySide6',m.version('PySide6')); print('vsview',m.version('vsview'))" > "$verifyRun/evidence/alignment-component-doctor.log" 2>&1
```

Set `QT_QPA_PLATFORM=offscreen` only for the component drive: POSIX
`export QT_QPA_PLATFORM=offscreen`; PowerShell `$env:QT_QPA_PLATFORM = 'offscreen'`.
Save the previous value so it can be restored before a visible review. Then:

```sh
uv run --no-sync pytest -q tests/vsview/test_alignment_review_package.py tests/vsview/test_alignment_review_panel.py::test_provisional_zero_is_visible_but_never_seeds_manual_authority tests/services/test_alignment_workflow_vsview.py::test_manual_zero_preserves_rejected_attempt_and_diagnostic_digest tests/orchestration/test_phase_alignment_contract.py::test_provisional_audio_candidate_cannot_reach_trim_authority tests/services/test_alignment_reuse_cache.py::test_computed_this_run_provisional_result_is_not_write_eligible --basetemp "$verifyRun/scratch/alignment-components" --junitxml "$verifyRun/evidence/alignment-component-results.xml" > "$verifyRun/evidence/alignment-component-run.log" 2>&1
```

Record exit status and inspect skips. These existing tests load plugin registration,
drive real offscreen Qt widgets with synthetic viewer metadata, and check authority
with fixture workflow responses. They show provisional zero does not seed manual
authority, manual zero retains the rejected attempt/digest, and provisional results
cannot acquire trim or computed-cache authority. They do not decode source media,
launch a real review child, exercise every panel action, or observe resumed native
execution. Retain useful sidecars from basetemp before cleanup.

For the real journey, first restore the normal Qt platform and inspect
`frame-compare doctor --json` in the intended native environment. Establish the
actual desktop/session and decoder, including `core.lsmas` for the generated
L-SMASH session, rather than assuming VSView or BestSource availability supplies
it. Use the complete
[Docker/runtime procedure](../../../../docs/ENGINEERING_RUNBOOK.md#docker-runtime-verification)
for its supported host, or the separate
[Windows portable/release-path procedure](../../../../docs/ENGINEERING_RUNBOOK.md#windows-portable-release-path-verification).
Those procedures own runtime setup and specialized proof; do not copy abbreviated
build commands here.

`tools/verify_docker_gui.sh` has an offscreen generated three-source/session/sidecar
contract under its Linux X11 host wrapper prerequisites. That is different from
the visible user interaction above. Native manual proof must additionally observe
the actual panel actions, saved session-bound sidecar, close/resume and resulting
alignment. Capture command/doctor, relevant UI states and bounded sanitized
run/result artifacts; preserve the original attempt provenance alongside confirmed
zero/nonzero offsets. Do not infer confirmation from an existing cache entry.

## Gotchas

- The current Mac pilot exposed `core.bs`, but no `core.lsmas`. This is an explicit
  native-media prerequisite gap. Offscreen Qt success cannot close it. Recheck on
  the actual host; a historical absence is not a permanent capability verdict.
- Full visible-native review, Linux X11 visible launch and physical Windows
  acceptance are unverified by this skill's seed evidence. A Linux-container
  offscreen result or hosted Windows packaging pass proves a narrower claim.
- The panel is inactive in ordinary or hand-written VSView sessions. Use the
  production-generated session; session identity and complete source-set validation
  matter. Missing/stale/mixed/incomplete results fail closed.
- Valid zero, provisional zero and unavailable evidence are distinct. A visible
  audio candidate does not authorize trims or computed-cache reuse.
- Session result sidecars, persisted manual overrides and decoder indexes have
  different lifetimes. L-SMASH may write indexes beside source files. Keep all of
  them in the disposable media/root/cache; preserve useful evidence before deleting
  scratch, and never remove original user media or shared caches.
- Without a compatible runtime and desktop, record the real journey as blocked
  with the doctor/prerequisite evidence and route attempted. Report component
  results separately; do not call the full feature live-verified.
