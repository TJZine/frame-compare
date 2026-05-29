# CLI/TUI and Progress Reporting Audit Report

This report presents the findings of a code-level audit focused on the CLI and TUI output surfaces, interactive prompts, and progress reporting in `frame-compare`. The findings are ranked by severity, with code locations, detailed explanations, and recommended mitigations.

---

## Executive Summary

The audit has identified **9 key issues** categorized into three severity levels:
- **Critical Severity (2 issues)**: Loop conditions that cause high CPU utilization/hangs on closed stdin, and stdout stream pollution that corrupts machine-readable JSON payloads.
- **Medium Severity (4 issues)**: Misleading hint messages for non-existent CLI flags, raw tracebacks/crashes in helper commands, and mismatch between previewed configurations and actual executions.
- **Low Severity (4 issues)**: Color suppression on helper commands, and sub-optimal progress bar rendering under exceptional or nested states.

---

## 1. Critical Severity Issues

### 1.1. Stdout Pollution in JSON Mode during Interactive Alignment Prompting
*   **File**: [src/frame_compare/services/alignment_vspreview.py](file:///c:/Software/video/frame-compare/src/frame_compare/services/alignment_vspreview.py)
*   **Line Range**: [L143-L171](file:///c:/Software/video/frame-compare/src/frame_compare/services/alignment_vspreview.py#L143-L171)
*   **Description**: When interactive audio alignment verification is enabled (either via `--force-interactive-alignment` or `use_vspreview = true`) and run alongside the `--json` option, the prompting logic writes human-readable prompt messages directly to stdout using Python's built-in `print()` and `input()` functions.
*   **Justification**: Because stdout is reserved exclusively for the structured JSON results payload in `--json` mode, printing raw text to stdout pollutes the stream and corrupts the final output, causing JSON parsers downstream to crash.
*   **Recommendation**: 
    1. Direct all interactive prompt text to `sys.stderr` instead of stdout.
    2. Alternatively, raise an validation error during preflight if interactive alignment is requested concurrently with `--json`.

### 1.2. Infinite Loop Risk on EOF/Closed stdin in Wizard Prompting
*   **File**: [src/frame_compare/cli/wizard_command.py](file:///c:/Software/video/frame-compare/src/frame_compare/cli/wizard_command.py)
*   **Line Range**: [L98-L108](file:///c:/Software/video/frame-compare/src/frame_compare/cli/wizard_command.py#L98-L108)
*   **Description**: In `prompt_input_dir`, the function loops infinitely until a directory path is entered that exists on disk. If the wizard is executed in a non-interactive shell or the stdin stream is closed (EOF), `typer.prompt` immediately returns the default value without blocking. If the default path does not exist, the validation check fails, printing an error and restarting the loop immediately.
*   **Justification**: This creates an infinite loop that consumes 100% CPU and floods log files/terminal streams with error messages, causing hangs in automated scripts or CI/CD pipelines.
*   **Recommendation**: Detect when stdin is closed or when `typer.prompt` returns empty or default repeatedly without user interaction, and raise a `typer.Abort()` or exit cleanly.

---

## 2. Medium Severity Issues

### 2.1. Misleading `--verbose` Hint on Non-Verbose Commands
*   **File**: [src/frame_compare/cli/errors.py](file:///c:/Software/video/frame-compare/src/frame_compare/cli/errors.py)
*   **Line Range**: [L51-L56](file:///c:/Software/video/frame-compare/src/frame_compare/cli/errors.py#L51-L56)
*   **Description**: The CLI error-formatting adapter checks if `verbose` is enabled. If not, and additional error details are available, it appends a helper message: `For more details, run with --verbose`. However, commands like `preset list`, `preset apply`, `preset save`, and `wizard` do not accept a `--verbose` flag. Under error conditions, they call `handle_error` with hardcoded `verbose=False`, triggering this hint.
*   **Justification**: Bad UX. If users follow the hint and run the command with `--verbose` (e.g., `frame-compare preset list --verbose`), Typer crashes with `No such option: --verbose`.
*   **Recommendation**: Only append the `--verbose` hint if the currently running CLI command actually supports a verbose option, or add global support for `--verbose` across all subcommands.

### 2.2. Unhandled Exception Tracebacks in `doctor` Command
*   **File**: [src/frame_compare/cli/doctor_command.py](file:///c:/Software/video/frame-compare/src/frame_compare/cli/doctor_command.py)
*   **Line Range**: [L34-L45](file:///c:/Software/video/frame-compare/src/frame_compare/cli/doctor_command.py#L34-L45)
*   **Description**: Unlike the primary `run` command or preset commands, the `doctor` command does not run check execution within a `try/except` block catching `FrameCompareError`.
*   **Justification**: If an environment or configuration error occurs (such as an invalid TOML structure or missing workspace paths) during check initialization, the command crashes with a raw Python traceback. This breaks UX consistency and output contracts (especially in `--json` mode).
*   **Recommendation**: Wrap the `run_doctor` invocation in a try/except block, delegate errors to the standard `handle_error` function, or format them into the standard JSON error payload in JSON mode.

### 2.3. Base Path Inaccuracy in At-a-Glance Preview
*   **File**: [src/frame_compare/cli/run_command.py](file:///c:/Software/video/frame-compare/src/frame_compare/cli/run_command.py) & [src/frame_compare/cli/output.py](file:///c:/Software/video/frame-compare/src/frame_compare/cli/output.py)
*   **Line Range**: [run_command.py: L209-L212](file:///c:/Software/video/frame-compare/src/frame_compare/cli/run_command.py#L209-L212) & [output.py: L126-L132](file:///c:/Software/video/frame-compare/src/frame_compare/cli/output.py#L126-L132)
*   **Description**: The run preview is printed *before* the runtime pipeline (`runner.run`) is called. When `paths.use_run_folders = true` (default), the pipeline reserves a fresh timestamped run folder (e.g., `screenshots/20260529_014847_reference_name/`) during the preparation phase.
*   **Justification**: The At-a-Glance preview displays the base screenshots/generated paths (e.g., `screenshots/`), which does not match the actual folder paths where screenshots are written. This confuses the user by displaying inaccurate path telemetry.
*   **Recommendation**: Print the At-a-Glance preview *after* the run folder has been reserved, or indicate in the preview that the directories are base paths that will receive run-specific subfolders.

### 2.4. Missing TTY Check in Wizard Command
*   **File**: [src/frame_compare/cli/wizard_command.py](file:///c:/Software/video/frame-compare/src/frame_compare/cli/wizard_command.py)
*   **Line Range**: [L46-L78](file:///c:/Software/video/frame-compare/src/frame_compare/cli/wizard_command.py#L46-L78)
*   **Description**: The interactive configuration wizard command prompts the user for setup settings without verifying if the standard input is an interactive terminal.
*   **Justification**: Attempting to run the wizard in a non-interactive shell (such as a CI pipeline) leads to crashes or infinite loops instead of failing fast with a clean error.
*   **Recommendation**: Verify `sys.stdin.isatty()` at the entry of the `wizard` command, and raise an input/environment error if standard input is not a TTY.

---

## 3. Low Severity Issues

### 3.1. Progress Bar Jumps to 100% on Warn-Only Phase Exceptions
*   **File**: [src/frame_compare/orchestration/phases.py](file:///c:/Software/video/frame-compare/src/frame_compare/orchestration/phases.py)
*   **Line Range**: [L70-L87](file:///c:/Software/video/frame-compare/src/frame_compare/orchestration/phases.py#L70-L87)
*   **Description**: In `execute_phases`, when a phase configured with `warn_only=True` fails, the exception is caught and logged. However, because `reporter.advance(1)` is placed in the `else` block, the parent task is not advanced. The code then enters the `finally` block and calls `reporter.complete_phase()`, which forces the progress bar directly to completion (`completed=total`).
*   **Justification**: Jumpy TUI progress bar. If a phase fails halfway, the bar suddenly jumps to 100%, masking where the failure occurred.
*   **Recommendation**: Move `reporter.advance(1)` or similar status completion logic to the `finally` block or inside the warning block to reflect actual status.

### 3.2. Unconditional Color Suppression on Auxiliary Command Errors
*   **File**: [src/frame_compare/cli/preset_command.py](file:///c:/Software/video/frame-compare/src/frame_compare/cli/preset_command.py) & [src/frame_compare/cli/wizard_command.py](file:///c:/Software/video/frame-compare/src/frame_compare/cli/wizard_command.py)
*   **Line Range**: [preset_command.py: L63, L82, L99](file:///c:/Software/video/frame-compare/src/frame_compare/cli/preset_command.py#L63) & [wizard_command.py: L93, L95](file:///c:/Software/video/frame-compare/src/frame_compare/cli/wizard_command.py#L93)
*   **Description**: The `--no-color` option is not accepted on `preset` or `wizard` subcommands. Instead, when an error occurs in these subcommands, they invoke `handle_error` with a hardcoded `no_color=True`.
*   **Justification**: Errors in these commands are always printed without ANSI color codes, even if the user has a color-capable TTY and desires color cues (like red `✗` error marks). It also ignores the standard `NO_COLOR` environment variable check.
*   **Recommendation**: Check the standard `NO_COLOR` environment variable or add a global option to disable color, rather than hardcoding `no_color=True`.

### 3.3. Ignored `--config` Flag on `preset list` Subcommand
*   **File**: [src/frame_compare/cli/entry.py](file:///c:/Software/video/frame-compare/src/frame_compare/cli/entry.py)
*   **Line Range**: [L237-L247](file:///c:/Software/video/frame-compare/src/frame_compare/cli/entry.py#L237-L247)
*   **Description**: The `preset list` command accepts `--config` for consistency, but the resolved config path is discarded, and only `resolved_root` is passed down.
*   **Justification**: While not a breaking bug, it is redundant and misleading as passing `--config` has no effect on listing presets.
*   **Recommendation**: Remove the option if it is not used, or use it to locate config presets if custom preset directory overrides are supported.

### 3.4. Render Phase Progress Total Mismatch
*   **File**: [src/frame_compare/orchestration/execution.py](file:///c:/Software/video/frame-compare/src/frame_compare/orchestration/execution.py) & [src/frame_compare/render/batch/orchestrator.py](file:///c:/Software/video/frame-compare/src/frame_compare/render/batch/orchestrator.py)
*   **Line Range**: [execution.py: L205-L218](file:///c:/Software/video/frame-compare/src/frame_compare/orchestration/execution.py#L205-L218) & [orchestrator.py: L160-L172](file:///c:/Software/video/frame-compare/src/frame_compare/render/batch/orchestrator.py#L160-L172)
*   **Description**: The main `"render"` phase is defined with a default `progress_total=1`. However, during execution, `render_batch` spawns a nested progress phase titled `"Rendering"` with `total=len(requests)` (matching the screenshot count). The nested bar advances smoothly for each screenshot, while the parent `"render"` bar remains static and only advances by 1 at the end.
*   **Justification**: The parent progress bar's total is arbitrary and doesn't represent the actual work unit count (the number of frames to render).
*   **Recommendation**: Configure the parent `"render"` phase's `progress_total` dynamically to be the count of screenshots in the batch.
