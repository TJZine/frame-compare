# Project Overview — Frame Compare

Purpose
- Automate deterministic frame selection, audio alignment, HDR→SDR tonemapping, screenshot rendering, and optional slow.pics uploads for comparing multiple encodes of the same title.
- Provide a thin CLI that delegates to a reusable runner with a stable programmatic API.

Tech Stack
- Language: Python 3.13+
- CLI: Click + Rich (console UI)
- Media: VapourSynth (primary renderer), FFmpeg/ffprobe (fallback and utilities)
- Network/HTTP: httpx, requests (+ requests-toolbelt)
- Parsing/metadata: guessit, anitopy, natsort
- Type checking: Pyright (PEP 561 typed package via py.typed)
- Linting/formatting: Ruff, Black
- Test runner: Pytest (plugins disabled by default via addopts)

Key Packages (selected from pyproject.toml)
- runtime: rich, click, httpx, requests, requests-toolbelt, numpy, librosa, soundfile, tqdm, vapoursynth>=72
- optional extras: preview (vspreview, PySide6)
- dev: pytest, pytest-mock, requests-mock, ruff, black

Entrypoints
- Console script: `frame-compare` (maps to `frame_compare:main`)
- Module execution: `python -m frame_compare`

Typical Workflows
- Seed config, create input set under `comparison_videos/<name>/`, run pipeline (VS or FFmpeg), optionally upload to slow.pics, inspect JSON tail/HTML report.

External Services/Tools
- slow.pics (comparison hosting)
- TMDB (metadata resolution)
- Optional VSPreview (manual/visual alignment assistant)

OS Context
- Target OS: Darwin (macOS). Works cross‑platform but dev box is macOS.
