# Code Structure

Top‑Level
- `frame_compare.py` — CLI shim (Click group, options, delegates to runner.run, doctor/wizard/preset commands).
- `src/` — source tree root; packaged via setuptools (package-dir configured for `src` and `src.frame_compare`).
- `tests/` — pytest suites, with subfolders:
  - `tests/runner/` — runner orchestration, CLI entry behavior
  - `tests/cli/` — CLI-focused (wizard, doctor, help, layout)
  - `tests/helpers/` — shared fixtures and test utilities

Core Package Modules (under `src/frame_compare/`)
- `runner.py` — orchestration logic, `RunRequest` dataclass, `RunResult` dataclass, `run()` implementation.
- `cli_runtime.py` — shared TypedDicts (`JsonTail`, slow.pics blocks, trims), `_ClipPlan`, `CliOutputManager`.
- `preflight.py` — workspace resolution, config path rules, writability checks, `PreflightResult`, diagnostics.
- `wizard.py` — interactive prompts for workspace/config.
- `vspreview.py` — VSPreview script rendering/persistence/launch; manual offsets; CLI command resolution.
- `alignment_runner.py` — audio alignment orchestration, summaries/display data helpers.
- `selection.py` — clip initialisation (`init_clips`) + selection-window helpers.
- `metadata.py` — filename metadata parsing/dedup; override mapping helpers.
- `planner.py` — plan construction for clips (trims/FPS overrides).
- `layout_utils.py` — Rich/text formatting helpers, label utilities.
- `runtime_utils.py` — FPS/time formatting, sequence folding, rule evaluation, legacy summary builder.
- `config_writer.py` — config template load/render/write, diffs.
- `presets.py` — preset discovery, descriptions, TOML loader.
- `doctor.py` — dependency checks (`collect_checks`, `emit_results`).
- `core.py` — remaining legacy surface + compatibility exports (shrinking; most logic extracted).

Other Project Files
- `src/data/` — packaged assets (config template, report HTML/CSS/JS).
- `pyproject.toml` — build configuration, dependencies, tooling.
- `pyrightconfig.json` — type checking configuration (strict for library modules).
- `MANIFEST.in` — packaging data includes.
- `typings/` — additional stubs for third‑party libraries and top‑level `frame_compare`.
