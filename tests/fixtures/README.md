# Media fixtures

This directory hosts lightweight placeholder media that exercises the CLI and
alignment flows without requiring large binary samples. The layout is:

- `../comparison_videos/` (repository root) – seed input tree used by
  quick-start examples and configuration defaults.
- `media/cli/` and `media/cli_check/` – paired MKVs used by CLI regression
  scripts.
- `media/audio/` and `media/audio_check/` – audio-alignment placeholders used by
  manual smoke tests.

Each MKV is a tiny stub file checked into the repository so tests and docs can
reference them consistently. Add new fixtures next to these folders and keep the
files extremely small to avoid bloating the repository.
