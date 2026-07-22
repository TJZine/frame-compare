# Native source

Native source installation is for advanced users who manage their own media runtime.
Install these host prerequisites first:

- Python 3.13 or newer;
- FFmpeg available on `PATH`;
- VapourSynth R76;
- L-SMASH-Works available to the VapourSynth runtime;
- `uv` (recommended for the repository's locked environment) or pip;
- optionally VSPreview for interactive manual alignment.

VapourSynth is not optional for the default renderer. Setting
`screenshots.use_ffmpeg = true` selects the FFmpeg screenshot path, but HDR frames
that require tonemapping still need VapourSynth.

## Install with uv

From a clone of the repository:

```bash
uv sync --no-dev --extra vspreview --frozen
```

The `vspreview` extra supplies the repository-managed VapourSynth Python and
VSPreview dependencies. It does not install the native L-SMASH-Works plugin for you.
If you do not need VSPreview, omit `--extra vspreview` while retaining the required
native renderer dependencies.

Use the managed entry point for every command:

```bash
uv run --no-sync frame-compare wizard
uv run --no-sync frame-compare doctor
uv run --no-sync frame-compare run --root . --dry-run
uv run --no-sync frame-compare run --root .
```

## Install with pip

Create and activate a Python 3.13+ virtual environment, then install from the clone:

```bash
python -m pip install ".[vspreview]"
```

For a pip-managed installation, run `frame-compare wizard`, `doctor`, and `run`
directly, without the `uv run --no-sync` prefix. The pip installation still relies
on your native FFmpeg, VapourSynth R76, and L-SMASH-Works setup.

Put at least two supported clips in `comparison_videos/`, then follow
[Your First Comparison](../guides/first-comparison.md).
