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
| 🌐 **slow.pics Publishing** | Automatic uploads with retry logic and rate limiting |
| 📄 **HTML Reports** | Offline-friendly comparison viewer with 4 modes |
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

### 📋 Contract-First Documentation

Canonical truth is stored as YAML/JSON contracts, with generated derived views:

- **Canonical**: [`docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`](docs/OPUS_REBUILD_FRAME_COMPARE/contracts/)
- **Derived views generator**: [`scripts/generate_contract_views.py`](scripts/generate_contract_views.py)
- **Readiness gate SSOT**: [`docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`](docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json)

### 🔄 Workflow Discipline (Optional)

This repo includes an operator-minimal, file-based run system for phased implementation:

- Run artifacts live under `.agent-workflow/runs/<RUN_ID>/`
- Each artifact ends with a `## NEXT AGENT PROMPT (COPY/PASTE)` block for deterministic handoffs

See: [`docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`](docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md)

---

## Requirements

| Requirement | Version | Notes |
| ----------- | ------- | ----- |
| Python | 3.13+ | Required |
| uv | Latest | Recommended (or pip) |
| FFmpeg | Any recent | Must be on `PATH` |
| VapourSynth | R72+ | Optional, for primary renderer |

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
> TMDB keys via `FRAME_COMPARE_TMDB__API_KEY` (or legacy `TMDB_API_KEY`) instead of committing them to disk.

### 4. Run the pipeline

```bash
docker run --rm -it \
  -v "$PWD/comparison_videos":/workspace/comparison_videos:ro \
  -v "$PWD/output":/workspace/screenshots \
  -w /workspace \
  frame-compare:dev run \
    --root /workspace \
    --input /workspace/comparison_videos \
    --no-upload \
    --frame-count 10
```

> [!TIP]
> For slow.pics uploads, omit `--no-upload` and ensure your config contains visibility settings.

---

## Usage

### Docker (Recommended)

See [Quick Start](#quick-start) for Docker commands.

### Local Development

Local invocations may require optional dependencies (notably VapourSynth). For reproducible "real deps" verification, prefer Docker:

```bash
bash tools/verify_docker_integration.sh
```

### Readiness Gates

```bash
# One-command check
./scripts/check-all-gates.sh

# Or individual gates
bash scripts/reverify_ai_readiness.sh --update-roadmap
```

---

## Documentation

### 📚 Core Documentation

| Document | Description |
| -------- | ----------- |
| [Executive Summary](docs/OPUS_REBUILD_FRAME_COMPARE/00-executive-summary.md) | Project overview and objectives |
| [Agent Workflow](docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md) | Multi-agent workflow (SSOT) |
| [Quick Reference](docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md) | Workflow quick reference |
| [Master Checklist](docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md) | Implementation tracking |
| [API Reference](docs/api.md) | Generated API documentation |

### 📜 Contracts (SSOT)

- [`docs/OPUS_REBUILD_FRAME_COMPARE/contracts/README.md`](docs/OPUS_REBUILD_FRAME_COMPARE/contracts/README.md)
- [`docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`](docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json)

---

## Quality & Verification

### Command Canon

This repo uses a two-lane approach for deterministic commands:

**1. Repo scripts/validators** — use `uv run --no-sync`:

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

**2. Tooling** — prefer `.venv/bin/*`:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
```

### Docker Integration

For "real external deps work" verification (VapourSynth + FFmpeg):

```bash
bash tools/verify_docker_integration.sh
```

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
