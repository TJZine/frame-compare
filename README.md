# Frame Compare

> **Deterministic video comparison pipeline**: frame selection, HDR→SDR tonemapping, overlays/reports, and publishable outputs.

[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-3776AB?logo=python&logoColor=white)](#requirements)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![CI](https://github.com/TJZine/frame-compare/actions/workflows/ci.yml/badge.svg)](https://github.com/TJZine/frame-compare/actions/workflows/ci.yml)
[![Type Checked](https://img.shields.io/badge/type%20checked-pyright-1f6feb?logo=python&logoColor=white)](#quality--verification)
[![Linted](https://img.shields.io/badge/linted-ruff-d7ff64?logo=ruff&logoColor=black)](#quality--verification)
[![Conventional Commits](https://img.shields.io/badge/commits-conventional-fe5196?logo=conventionalcommits&logoColor=white)](CONTRIBUTING.md)

> [!NOTE]
> This repository contains Frame Compare's ground-up rebuild. The legacy implementation lives separately as `frame-compare-legacy`.

---

## ✨ Features at a Glance

| Feature | Description |
| ------- | ----------- |
| 🎯 **Deterministic Frame Selection** | Stable sorting, explicit seeds, reproducible results |
| 🎨 **HDR→SDR Tonemapping** | libplacebo-powered with 7 presets (BT.2390, Spline, Reinhard) |
| 🎵 **Audio Alignment** | Cross-correlation based synchronization for comparison clips |
| 📸 **Screenshot Rendering** | VapourSynth/FFmpeg with customizable overlays |
| 🌐 **slow.pics Publishing** | Opt-in uploads with retry logic and rate limiting |
| 📄 **HTML Reports** | Offline comparison viewer with slider, overlay, diff, and pair blink modes |
| 🔧 **Zero-Config Docker** | Complete environment with single `docker compose up` |

---

## 📑 Table of Contents

- [What It Does](#what-it-does)
- [Key Ideas](#key-ideas)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Documentation](#documentation)
- [Quality & Verification](#quality--verification)
- [Releases & Versioning](#releases--versioning)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

---

## What It Does

Frame Compare helps you produce consistent, reviewable comparisons between encodes:

- **Deterministic frame selection** — including seeded randomness where required
- **Professional overlays** — renders PNGs with stable naming and metadata
- **Dual outputs** — machine-readable (JSON/metadata) + human-readable (HTML reports)
- **Offline-first** — works locally with optional publishing integrations

---

## Key Ideas

### 🔒 Determinism by Default

Frame Compare is designed so the same inputs produce the same outputs:

- Stable sorting rules and explicit seeds
- "No guessing" contracts for CLI/config where ambiguity would cause churn
- Reproducible verification gates

### 📋 Core Docs

- [Engineering Runbook](docs/ENGINEERING_RUNBOOK.md) — workflow, verification, planning, handoff
- [Current Architecture](docs/current-architecture.md) — present-day codebase truth
- [CLI Contract](docs/current-cli-contract.md) — canonical CLI command, flag, and persistence contract
- [Decisions](docs/DECISIONS.md) — historical decisions and exceptions
- [API Reference](docs/api.md) — generated symbol reference

---

## Requirements

| Requirement | Version | Notes |
| ----------- | ------- | ----- |
| Python | 3.13+ | Required |
| uv | Latest | Recommended (or pip) |
| FFmpeg | Any recent | Must be on `PATH` |
| VapourSynth | R76 | Optional, for primary renderer |

---

## Installation

> [!TIP]
> Prefer `uv` for reproducible environments.

### With uv (Recommended)

```bash
uv sync --group dev --frozen
```

### With pip

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

# Dev tools (uv groups not supported by pip)
pip install pytest pytest-cov ruff pyright
```

### Windows Portable (No Docker)

From GitHub release zip (recommended):

```powershell
# 1) Download frame-compare-portable-win-x64-<tag>.zip from the GitHub Release
# 2) Extract it
# 3) From the extracted folder:
.\install.cmd
```

From cloned repo:

```powershell
# 1) Clone the repo
# 2) From the repo root:
.\install.cmd
```

Source installs and portable bundle builds create empty config/ and comparison_videos/ directories in the bundle root. Put an existing `config.toml` at `config/config.toml`, and drop input clips under `comparison_videos/` if you want to use defaults without passing explicit `--config` or `--input` paths. For the installed `frame-compare` command, a bundle-local `config/config.toml` takes precedence over the AppData fallback config.

When using `.\tools\windows_portable\install-from-source.cmd`, the bundle root is `dist/frame-compare-portable-win-x64` (not the repository root). Put your config at `dist/frame-compare-portable-win-x64/config/config.toml` and videos under `dist/frame-compare-portable-win-x64/comparison_videos/`.

Advanced/legacy:

```powershell
.\tools\windows_portable\install-from-source.cmd
```

> [!NOTE]
> The Windows portable **full bundle includes VSPreview + PyQt6**.
> For source-based installs, install optional dependencies with:
> - `uv sync --group dev --extra vspreview --frozen`
> - or `pip install -e ".[vspreview]"`
> Then run `frame-compare doctor` to confirm interactive alignment dependencies are available.

#### Updating a Portable Install

Apply a code-only update zip:

```powershell
frame-compare-update apply .\frame-compare-update-win-x64-0.1.1.zip
```

The updater is offline-first and verifies signature + file hashes before applying changes.
If dependency fingerprints do not match, the default action is cancel; unsafe apply requires explicit confirmation.
You can inspect/update backups with:

```powershell
frame-compare-update list-backups
frame-compare-update rollback <backup-id>
frame-compare-update purge-backups --keep 5
```

---

## Quick Start

> [!IMPORTANT]
> The full pipeline depends on external tools (FFmpeg, VapourSynth + plugins). The most reproducible way to run end-to-end commands is via **Docker**.

### 1. Build the Docker image

```bash
docker build -t frame-compare:dev .
```

### 2. Run diagnostics

```bash
docker run --rm frame-compare:dev doctor --json
```

### 3. Run the interactive wizard

```bash
docker run --rm -it \
  -v "$PWD":/workspace \
  -w /workspace \
  frame-compare:dev wizard
```

> [!NOTE]
> The wizard writes `config/config.toml` (gitignored) and may include secrets (e.g., a TMDB API key). Prefer setting
> TMDB keys via `FRAME_COMPARE_TMDB__API_KEY` instead of committing them to disk.

### 4. Run the pipeline

```bash
docker run --rm -it \
  -v "$PWD/comparison_videos":/workspace/comparison_videos:ro \
  -v "$PWD/output":/workspace/screenshots \
  -w /workspace \
  frame-compare:dev run \
    --root /workspace \
    --input /workspace/comparison_videos \
    --frame-count 10
```

> [!TIP]
> slow.pics uploads are disabled by default. Enable `slowpics.auto_upload` in config when you want to publish screenshots.

---

## Usage

### Docker (Recommended)

See [Quick Start](#quick-start) for Docker commands.

### Local Development

Local invocations may require optional dependencies (notably VapourSynth). For reproducible "real deps" verification, prefer Docker:

```bash
bash tools/verify_docker_integration.sh
```

### Reports

Generated reports are static HTML viewers. By default, report image sources point
to screenshot files by relative path next to the report; when `report.embed_images`
is enabled, screenshot bytes are embedded in the HTML payload. The viewer persists
browser-local view mode, clip selection, viewport/zoom, reveal, and alignment state
per report; it supports frame/category navigation, pan and wheel zoom controls, and
collapsed report, clip, and frame metadata panels.

### Overlays

- `screenshots.overlay_mode`: `none|minimal|standard|diagnostic`
- Overlay font rendering uses system/default fonts today; appearance can vary by OS.

## Documentation

### 📚 Core Documentation

| Document | Description |
| -------- | ----------- |
| [Engineering Runbook](docs/ENGINEERING_RUNBOOK.md) | Canonical workflow, verification, and planning policy |
| [Current Architecture](docs/current-architecture.md) | Present-day runtime flow, boundaries, and hotspots |
| [CLI Contract](docs/current-cli-contract.md) | Canonical CLI command, flag, and persistence contract |
| [Decisions](docs/DECISIONS.md) | Architectural and process decision log |
| [API Reference](docs/api.md) | Generated API documentation |

---

## Quality & Verification

The canonical command set and verification policy live in the
[Engineering Runbook](docs/ENGINEERING_RUNBOOK.md).

Use the runbook to choose the right local, Docker, Windows portable, and release-path
verification for the current change.

---

## Releases & Versioning

### Versioning Policy

- Git tags follow [SemVer](https://semver.org/) with a `v` prefix (e.g., `v0.1.0`, `v1.0.0`)
- Pre-1.0 tags expected during rebuild while the public surface stabilizes

### Release Automation

- **Conventional Commits** enforced via PR titles + squash merge
- **Release Please** automates releases from `main`

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development environment setup
- Pull request workflow
- Conventional Commit format
- Local quality checks

---

## Security

See [SECURITY.md](SECURITY.md) for:

- Supported versions
- Vulnerability reporting process
- Security considerations

---

## License

This project is licensed under the **Apache License 2.0** — see [LICENSE](LICENSE) for details.

```text
Copyright 2025-2026 Tristan <zine96@proton.me>
```
