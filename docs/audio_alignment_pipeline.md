# Audio Alignment Pipeline

## Overview
Frame Compare can estimate per-clip trim offsets before video analysis by correlating audio onset envelopes. The pipeline picks a reference clip, extracts synchronized mono waveforms, runs onset detection, and derives frame offsets that propagate into screenshot generation and cached metrics. The feature is optional and designed to reduce manual pre-trimming when clips drift out of sync. 【F:frame_compare.py†L960-L1428】【F:src/audio_alignment.py†L291-L398】

## Requirements
### External binaries
* `ffmpeg` and `ffprobe` must be on `PATH`; alignment aborts early if either executable is missing. 【F:src/audio_alignment.py†L66-L118】

### Python extras
* The optional stack `numpy`, `librosa`, and `soundfile` is required; the module raises an `AudioAlignmentError` if any import fails. 【F:src/audio_alignment.py†L76-L92】

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
| `random_seed` | Seed for preview and inspection frame sampling. | `2025` |
| `frame_offset_bias` | Integer bias nudging suggested frame counts toward/away from zero. | `1` |

## Workflow
1. **Reference & target selection** – `_resolve_alignment_reference` honors the config hint, CLI-provided filename/index, or falls back to the first clip. Remaining clips become targets. 【F:frame_compare.py†L930-L999】
2. **Audio stream discovery** – `ffprobe` metadata identifies candidate streams. Forced CLI overrides (`--audio-align-track label=index`) take precedence, then the scoring heuristic prefers default language, channel count, and forced flags. 【F:frame_compare.py†L1005-L1096】【F:frame_compare.py†L2802-L2833】
3. **Waveform extraction & onset envelopes** – `measure_offsets` extracts mono WAV snippets for the reference and each target using consistent sample-rate resampling, computes onset envelopes, and cross-correlates them to estimate lags. FPS probes translate seconds into frame counts when possible. 【F:src/audio_alignment.py†L291-L398】
4. **Bias & negative offset handling** – `frame_offset_bias` nudges computed frame counts either toward zero (positive values) or away from zero (negative values). When only one target clip exists, negative offsets are applied to the reference clip instead, with explanatory notes recorded. 【F:frame_compare.py†L1205-L1304】
5. **Result vetting** – Offsets exceeding `max_offset_seconds`, correlation scores below threshold, missing FPS data, or extraction errors mark the measurement as manual-only. The CLI surfaces warnings and skips automatic trim adjustments for those clips. 【F:frame_compare.py†L1306-L1344】
6. **Offsets file update** – `update_offsets_file` merges measurements into the TOML sidecar, preserving prior manual edits and recording suggested values, correlation strength, and any override notes. 【F:src/audio_alignment.py†L433-L504】
7. **Applying trims** – After writing the file, `_maybe_apply_audio_alignment` shifts each plan’s trim start by the selected frame offset, normalizes baselines so no clip starts before frame zero, and records the applied frame counts and statuses for the CLI layout. 【F:frame_compare.py†L1380-L1427】
8. **CLI output & JSON tail** – The reporter prints stream selections, estimated offsets, and any warnings. The JSON tail captures reference/target descriptors, per-label offsets, correlation threshold, preview paths, and confirmation state for downstream tooling. 【F:frame_compare.py†L1332-L1368】【F:frame_compare.py†L1654-L1670】【F:frame_compare.py†L2255-L2281】
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

## Gotchas & edge cases
- Audio alignment is skipped (with a warning) when fewer than two clips are available or when the feature is disabled. 【F:frame_compare.py†L987-L997】
- Missing dependencies or binary failures bubble up as `AudioAlignmentError`, aborting the alignment phase while leaving the rest of the run intact. 【F:src/audio_alignment.py†L66-L204】【F:frame_compare.py†L1429-L1433】
- Measurements that exceed `max_offset_seconds`, fall below `correlation_threshold`, or lack FPS information require manual review; the CLI and offsets file flag them as manual and do not adjust trims. 【F:frame_compare.py†L1306-L1349】
- Non-interactive sessions auto-confirm preview prompts but emit a warning so you remember to review the generated screenshots later. 【F:frame_compare.py†L1532-L1540】
- When `confirm_with_screenshots` is true and you decline the preview, the tool renders additional inspection frames and raises a `CLIAppError` instructing you to edit the offsets file before retrying. 【F:frame_compare.py†L1549-L1565】

## Related
- `README.md` → “Auto-align mismatched sources” quick start for user-facing guidance.
- `tests/test_frame_compare.py` covers CLI output wiring for alignment JSON and previews.
