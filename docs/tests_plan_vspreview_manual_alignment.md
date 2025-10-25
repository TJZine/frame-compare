# Test Plan — VSPreview Manual Alignment (Phase 4)

## Manual QA matrix
- **macOS (arm64/x86_64)**
  1. Enable `[audio_alignment].use_vspreview = true`, run interactively with VSPreview installed on `PATH`, confirm prompt summarises auto suggestion and existing manual trims (display labels should match the friendly clip labels shown elsewhere), accept delta, rerun to verify reuse.
  2. Repeat with an existing negative `trim_start` override to ensure reference padding and persisted offsets reflect `status = "manual"` with `note = "VSPreview"`.
  3. Launch from a non-interactive shell (`printf '' | frame-compare …`) to confirm the launch is skipped, warning printed, and script path recorded for manual follow-up.
- **Linux (x86_64)**
  1. Run with large auto-alignment suggestion (>200 frames) to confirm the recommended offset is surfaced before VSPreview launches and that entering a smaller manual delta updates the JSON tail.
  2. Temporarily move/rename the `vspreview` executable so discovery fails; verify the CLI records the fallback warning and leaves trims untouched while still writing the script path.
  3. Confirm persisted VSPreview offsets skip repeated prompts on subsequent runs until the offsets file is edited.
- **Windows (x86_64)**
  1. Invoke via `python -m frame_compare` with `vspreview.exe` available; ensure the generated script opens in VSPreview and Ctrl+R reloads after editing `OFFSET_MAP`.
  2. Run inside PowerShell without a GUI session (for example, over SSH) to validate the non-interactive warning and fallback behaviour without errors.
  3. With pre-existing manual trims per target clip, ensure additional deltas accumulate correctly and the offsets TOML retains the previous baseline + delta.

## Automation hooks
- Unit tests: `_launch_vspreview` happy-path invocation (`tests/test_frame_compare.py::test_launch_vspreview_generates_script`).
- Regression coverage: fallback branch without VSPreview command (`tests/test_frame_compare.py::test_launch_vspreview_warns_when_command_missing`).
- JSON tail snapshots: assertions verify `vspreview_*` fields populate once manual offsets are accepted.

## Follow-ups
- Consider a future stub package for VSPreview if we begin importing runtime helpers directly.
- Track user feedback on script ergonomics (e.g., exposing hotkeys in CLI output or template comments) for potential Phase 5 polish.
