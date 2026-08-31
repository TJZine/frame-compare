# Native source

Native source installation is for advanced users who manage their own media runtime.
Install these host prerequisites first:

- Python 3.13 or newer;
- FFmpeg available on `PATH`;
- VapourSynth R79;
- L-SMASH-Works 1310 available to the VapourSynth runtime;
- vs-placebo 2.0.4 and a compatible Vulkan implementation for HDR tonemapping;
- `uv` (recommended for the repository's locked environment) or pip;
- optionally VSView 0.10.3 for interactive manual alignment.

VapourSynth is not optional for the default renderer. Setting
`screenshots.use_ffmpeg = true` selects the FFmpeg screenshot path, but HDR frames
that require tonemapping still need VapourSynth.

The supported reference stack, exact source revisions, and platform policies are
listed in [Supported Media Runtime](../supported-media-runtime.md). Native installs
may resolve distribution-managed FFmpeg and Vulkan components differently, so
`frame-compare doctor --json` and a generated-fixture smoke test are required after
any runtime change. Unmanaged Windows, Linux, and macOS use OS-scoped selected-contract
identities rather than verified native binary hashes. After replacing native FFmpeg,
VapourSynth, or source-plugin binaries, clear generated caches and Frame Compare-owned
indexes before reuse.

## Install with uv

From a clone of the repository:

```bash
uv sync --no-dev --extra vsview --frozen
```

The `vsview` extra pins VSView 0.10.3 and the repository-managed VapourSynth Python
package to R79. It uses VSView's base dependency graph, including its documented
PySide6 backend; the upstream `recommended` and `full` extras are intentionally not
selected. Its current resolution includes vsjetengine 1.7.0, BestSource, vspackrgb,
and jetpytools 3.1.1.
On Windows it also installs the selected `vapoursynth-lsmas 1310.0.0.0` and
`vs-placebo 2.0.4` plugin wheels so the locked environment matches the supported native
media stack. Linux and macOS still require host-managed L-SMASH-Works and vs-placebo
installations. If you do not need interactive alignment, omit `--extra vsview` while
retaining the required native renderer dependencies. BestSource is owned by VSView's
UI workspace; generated Frame Compare sessions continue to load sources through
L-SMASH-Works and its Frame Compare-owned index paths.

When upgrading an existing Windows checkout from the R78 stack, recreate `.venv`
before syncing if its VapourSynth plugin directory contains manually installed or
untracked DLLs. An old `libvslsmashsource.dll` can otherwise load before the selected
wheel-owned `LSMASHSource.dll` and produce the deprecated API3 warning.

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
python -m pip install ".[vsview]"
```

For a pip-managed installation, run `frame-compare wizard`, `doctor`, and `run`
directly, without the `uv run --no-sync` prefix. The pip installation still relies
on your native FFmpeg, VapourSynth R79, and L-SMASH-Works 1310 setup.

Put at least two supported clips in `comparison_videos/`, then follow
[Your First Comparison](../guides/first-comparison.md).
