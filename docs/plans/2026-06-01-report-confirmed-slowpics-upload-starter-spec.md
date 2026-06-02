Status: Historical
Scope: Reference-only starter spec for a future report-confirmed slow.pics upload workflow
Owner: Historical slow.pics UX planning session

# Report-Confirmed slow.pics Upload Starter Spec

This is not an active implementation plan. It records a future product idea that
was raised while planning slow.pics legacy UX parity:

- generate the local HTML report first
- keep the CLI waiting when local report review and slow.pics upload are both
  desired
- let the user inspect the local report
- then let the user confirm in the CLI whether the comparison should be
  uploaded to slow.pics

The active slow.pics legacy UX parity plan is
`docs/plans/2026-06-01-slowpics-legacy-ux-parity-plan.md`. That plan must not
implement this workflow unless it is explicitly replanned.

This current workstream does not implement report UI controls, report-owned
upload services, local services, background processes, custom protocol handlers,
browser extensions, or any other mechanism for triggering slow.pics upload from
the generated report.

## Product Intent

The intent is to avoid uploading an unwanted comparison before the user has seen
the generated local report. This is different from simple post-upload browser
opening: it changes the runtime order from "upload, then report/output UX" to a
review gate where the user can decide after inspecting local artifacts.

The minimum future workflow should be:

1. Run renders screenshots and generates the local report.
2. The CLI opens or prints the local report path according to the existing
   report auto-open rules.
3. The CLI waits for explicit user confirmation before slow.pics upload.
4. If confirmed, the CLI uploads the already-rendered artifacts to slow.pics and
   runs any approved post-upload UX.
5. If declined, the run completes successfully without slow.pics upload.

## Deliberate Non-Goals

- Do not add report UI upload controls in the legacy UX parity workstream.
- Do not add report-owned upload services in the legacy UX parity workstream.
- Do not add a local web service, background process, custom protocol handler,
  or browser extension in the legacy UX parity workstream.
- Do not make the static HTML report responsible for reading local screenshot
  files and uploading them after the CLI exits.
- Do not change the current `run --json` contract without a separate plan.

## Future Design Questions

- Is this a config-only behavior, a runtime-only CLI flag, or both?
- How should it interact with unattended runs, `--json`, `--quiet`, and non-TTY
  execution?
- Does report auto-open become mandatory for the confirmation flow, or can the
  CLI print the path and wait?
- What timeout or cancellation behavior should apply while the CLI waits?
- Should decline be silent success, a warning, or a distinct output state?
- Should confirmed upload reuse the existing slow.pics publish phase, or should
  orchestration split report and publish ordering behind a new explicit phase
  plan?
- How should this interact with `slowpics.delete_after_upload` and reports that
  reference local screenshot files?

## Required Future Planning

A future implementation must start with a separate active tracked plan and
adversarial review. It should treat this as a high-risk CLI/runtime workflow
change because it can affect phase ordering, report auto-open behavior,
interactive prompting, JSON mode, upload timing, and cleanup semantics.
