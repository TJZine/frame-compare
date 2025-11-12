# Audio Alignment Pipeline

## Overview
Frame Compare can estimate per-clip trim offsets before video analysis by correlating audio onset envelopes. The pipeline picks a reference clip, extracts synchronized mono waveforms, runs onset detection, and derives frame offsets that propagate into screenshot generation and cached metrics. The feature is optional and designed to reduce manual pre-trimming when clips drift out of sync. 【F:frame_compare.py†L960-L1428】【F:src/audio_alignment.py†L291-L398】

## Requirements
### External binaries
* `ffmpeg` and `ffprobe` must be on `PATH`; alignment aborts early if either executable is missing. 【F:src/audio_alignment.py†L66-L118】

### Python extras
* The optional stack `numpy`, `librosa`, and `soundfile` is required; the module raises an `AudioAlignmentError` when an import fails or when an optional dependency errors during onset envelope calculation. 【F:src/audio_alignment.py†L76-L92】【F:src/audio_alignment.py†L240-L277】

### Configuration guard rails
* Validation rejects non-positive sample rates, hop lengths, max offsets, or negative seeds, and constrains correlation thresholds to `[0,1]`. 【F:src/config_loader.py†L190-L214】【F:src/config_loader.py†L233-L270】

## Configuration summary
Key options live under `[audio_alignment]` in `config.toml`. Defaults and intents come from `AudioAlignmentConfig`. 【F:src/datatypes.py†L210-L226】

| Key | Purpose | Default |
| --- | --- | --- |
| `enable` | Toggle the pipeline. | `false` |
| `reference` | Preferred reference clip label/index (falls back to CLI selection). | `""` |
| `sample_rate` | Waveform resample rate used during onset analysis. | `16000` |
| `hop_length` | Hop size for onset envelopes; clamped to at most 1% of the sample rate. | `512`【F:frame_compare.py†L1140-L1194】 |
| `start_seconds` | Optional window start override; defaults to `0`. | `null` |
| `duration_seconds` | Optional analysis window length; defaults to automatic span detection. | `null` |
| `correlation_threshold` | Minimum normalized correlation strength before declaring success. | `0.55` |
| `max_offset_seconds` | Absolute cap for auto-applied offsets. | `12.0` |
| `offsets_filename` | Relative path of the persisted offsets TOML. | `generated.audio_offsets.toml` |
| `confirm_with_screenshots` | Whether to pause for preview confirmation. | `true` |
| `prompt_reuse_offsets` | Prompt before recomputing cached offsets; declining reuses the saved values. | `false` |
| `random_seed` | Seed for preview and inspection frame sampling. | `2025` |
| `frame_offset_bias` | Integer bias nudging suggested frame counts toward/away from zero. | `1` |

## Workflow
1. **Reference & target selection** – `_resolve_alignment_reference` honors the config hint, CLI-provided filename/index, or falls back to the first clip. Remaining clips become targets. Existing manual trims are summarised using each plan's display label so operators can immediately see which clip the baseline applies to. 【F:src/frame_compare/alignment_runner.py†L157-L205】
2. **Audio stream discovery** – `ffprobe` metadata identifies candidate streams. Forced CLI overrides (`--audio-align-track label=index`) take precedence, then the scoring heuristic prefers default language, channel count, and forced flags. 【F:src/frame_compare/alignment_runner.py†L667-L809】
3. **Waveform extraction & onset envelopes** – `measure_offsets` extracts mono WAV snippets for the reference and each target using consistent sample-rate resampling, computes onset envelopes, and cross-correlates them to estimate lags. FPS probes translate seconds into frame counts when possible. 【F:src/audio_alignment.py†L291-L398】
4. **Bias & negative offset handling** – `frame_offset_bias` nudges computed frame counts either toward zero (positive values) or away from zero (negative values). When only one target clip exists, negative offsets are applied to the reference clip instead, with explanatory notes recorded. 【F:src/frame_compare/alignment_runner.py†L1074-L1208】
5. **Result vetting** – Offsets exceeding `max_offset_seconds`, correlation scores below threshold, missing FPS data, or extraction errors mark the measurement as manual-only. The CLI surfaces warnings and skips automatic trim adjustments for those clips. 【F:src/frame_compare/alignment_runner.py†L1209-L1338】
6. **Offsets file update** – `update_offsets_file` merges measurements into the TOML sidecar, preserving prior manual edits and recording suggested values, correlation strength, and any override notes. 【F:src/audio_alignment.py†L433-L504】
7. **Applying trims** – After writing the file, `alignment_runner.apply_audio_alignment` shifts each plan’s trim start by the selected frame offset, normalizes baselines so no clip starts before frame zero, and records the applied frame counts and statuses for the CLI layout. 【F:src/frame_compare/alignment_runner.py†L1339-L1509】
8. **CLI output & JSON tail** – The reporter prints stream selections, estimated offsets, and any warnings. The JSON tail captures reference/target descriptors, per-label offsets, correlation threshold, preview paths, and confirmation state for downstream tooling. 【F:src/frame_compare/alignment_runner.py†L2143-L2290】
9. **Visual confirmation (optional)** – When enabled, `_confirm_alignment_with_screenshots` renders preview frames, waits for an interactive confirmation, and escalates to additional samples plus manual editing if the user declines. Non-interactive sessions auto-confirm but log a warning. 【F:frame_compare.py†L1478-L1565】

## Offsets file format
`update_offsets_file` produces a TOML document with a `meta` block and one `[offsets."Clip.mkv"]` table per measurement. Manual edits marked with `status = "manual"` are preserved on subsequent runs; when a user changes `frames` without matching `suggested_frames`, the entry remains locked to manual status. Negative offsets re-applied to the opposite clip emit a `note` explaining the swap. 【F:src/audio_alignment.py†L433-L504】

Example snippet:
```toml
[meta]
reference = "ClipA.mkv"

[offsets."ClipB.mkv"]
frames = 3
seconds = 0.125000
suggested_frames = 3
suggested_seconds = 0.125000
correlation = 0.930000
target_fps = 24.000000
status = "auto"
```

## Quick start
1. Enable audio alignment in your config:
   ```toml
   [audio_alignment]
   enable = true
   confirm_with_screenshots = false
   max_offset_seconds = 5.0
   offsets_filename = "generated.audio_offsets.toml"
   ```
2. Run the CLI against a directory containing at least two clips:
   ```bash
   uv run python frame_compare.py
   ```
   The default `paths.input_dir` resolves to the bundled
   `comparison_videos/` directory beside `frame_compare.py`, which ships
   with sample clips. The run prints stream selections, estimated
   offsets, and writes `generated.audio_offsets.toml`. The JSON tail
   exposes the same data for automation. 【F:src/datatypes.py†L210-L226】【F:frame_compare.py†L1654-L1684】【F:frame_compare.py†L1985-L2065】

## VSPreview-assisted manual alignment

The optional VSPreview flow extends manual trimming without mutating clip plans until you confirm offsets.

### Prerequisites

- Set `[audio_alignment].use_vspreview = true` in `config.toml`; `[audio_alignment].enable` is recommended but not required—the prompt still appears even when correlation is disabled, and persisted VSPreview trims are reapplied even during manual-only sessions. 【F:frame_compare.py†L2056-L2085】【F:frame_compare.py†L2066-L2143】
- Install VSPreview so it is discoverable on `PATH` (`vspreview`) or importable via `python -m vspreview`. 【F:frame_compare.py†L3145-L3162】
- Run from an interactive terminal; non-interactive sessions skip launching but still write the script path for later review. 【F:frame_compare.py†L3139-L3144】

Install dependencies with platform-specific Qt bindings:

```powershell
uv add vspreview PySide6
```

```bash
uv add vspreview PyQt5
```

Project maintainers can capture the optional group so collaborators re-use it with `uv run --with .[preview]`:

```toml
[project.optional-dependencies]
preview = ["vspreview>=0.7", "PySide6>=6.6"]
# or on Linux (macOS support pending): ["vspreview>=0.7", "PyQt5>=5.15"]
```

To launch VSPreview on-demand without persisting the extras, run:

```bash
uv run --with .[preview] -- python -m vspreview path/to/vspreview_*.py
```

### Workflow overview

1. After audio alignment completes (or is skipped), the CLI summarises the measured offsets and any existing manual trims, then offers VSPreview guidance instead of auto-applying changes. 【F:frame_compare.py†L2056-L2138】【F:frame_compare.py†L2242-L2281】
2. `vspreview.write_script` mirrors the comparison pipeline, seeds the suggested offsets into an `OFFSET_MAP`, and stores the script beneath the workspace for traceability. 【F:src/frame_compare/vspreview.py†L138-L364】
3. When VSPreview is available, Frame Compare spawns it with inherited VapourSynth paths and waits for completion. Offsets are requested afterwards using `click.prompt`, and the resulting deltas adjust the clip plans plus the offsets TOML with `status="manual"` and a `note = "VSPreview"`. 【F:frame_compare.py†L3146-L3183】【F:frame_compare.py†L2914-L3083】

### Headless and fallback behaviour

- In CI/headless runs (`stdin` not a TTY) or when VSPreview binaries are missing, the CLI logs a warning, records the script path in the JSON tail, and continues with the legacy manual-edit workflow. 【F:frame_compare.py†L3139-L3173】【F:frame_compare.py†L3959-L3976】
- When VSPreview or its Qt backend cannot be imported, the CLI prints a dedicated warning panel with copy/paste install commands, records the `python -m vspreview …` invocation in the output, and appends `{ "vspreview_offered": false, "reason": "vspreview-missing" }` to the JSON tail so automations can detect the fallback path. 【F:frame_compare.py†L3528-L3570】【F:cli_layout.v1.json†L54-L76】
- Persisted VSPreview offsets take precedence on subsequent runs—even when `[audio_alignment].enable = false`; the CLI surfaces them as the new baseline and suppresses repeated prompts unless you delete or edit the offsets file. 【F:frame_compare.py†L2066-L2143】【F:frame_compare.py†L2286-L2336】【F:frame_compare.py†L3098-L3107】

## Gotchas & edge cases
- Audio alignment is skipped (with a warning) when fewer than two clips are available or when the feature is disabled. 【F:frame_compare.py†L987-L997】
- Missing dependencies or binary failures bubble up as `AudioAlignmentError`, aborting the alignment phase while leaving the rest of the run intact. 【F:src/audio_alignment.py†L66-L204】【F:frame_compare.py†L1429-L1433】
- Measurements that exceed `max_offset_seconds`, fall below `correlation_threshold`, or lack FPS information require manual review; the CLI and offsets file flag them as manual and do not adjust trims. 【F:frame_compare.py†L1306-L1349】
- Non-interactive sessions auto-confirm preview prompts but emit a warning so you remember to review the generated screenshots later. 【F:frame_compare.py†L1532-L1540】
- When `confirm_with_screenshots` is true and you decline the preview, the tool renders additional inspection frames and raises a `CLIAppError` instructing you to edit the offsets file before retrying. 【F:frame_compare.py†L1549-L1565】

## Related
- `README.md` → “Auto-align mismatched sources” quick start for user-facing guidance.
- `tests/runner/test_audio_alignment_cli.py` covers CLI output wiring for alignment JSON and previews.
