# Deployment Guide

> **Module:** Operations
> **Version:** 1.0

---

## 1. Deployment Options

### 1.1 Option Matrix

| Method | Skill Level | VapourSynth | Best For |
|--------|-------------|-------------|----------|
| Docker Compose | Beginner | Included | Most users |
| Docker CLI | Beginner | Included | Single-command runs |
| Windows Portable Bundle | Beginner | Included | Windows users who want native performance |
| pip + Manual VS | Advanced | Manual | Custom setups |
| DevContainer | Developer | Included | Contributors |

---

## 2. Docker Compose (Recommended)

### 2.1 Quick Start

```bash
# Clone and start
git clone https://github.com/TJZine/frame-compare.git
cd frame-compare

# Place videos in comparison_videos/
cp /path/to/my/videos/*.mkv comparison_videos/

# Start with Docker Compose
docker compose up
```

### 2.2 Docker Compose Configuration

```yaml
# docker-compose.yml
version: "3.8"

services:
  frame-compare:
    image: ghcr.io/tjzine/frame-compare:latest
    volumes:
      - ./comparison_videos:/workspace/comparison_videos
      - ./config:/workspace/config
      - ./screenshots:/workspace/screenshots
      - ./generated:/workspace/generated
    working_dir: /workspace
    environment:
      - FRAME_COMPARE_LOG_LEVEL=INFO
    tty: true
    stdin_open: true
```

### 2.3 Volume Mounts

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./comparison_videos` | `/workspace/comparison_videos` | Input videos |
| `./config` | `/workspace/config` | Configuration |
| `./screenshots` | `/workspace/screenshots` | Output images |
| `./generated` | `/workspace/generated` | Cache files |

---

## 3. Docker CLI

### 3.1 Single Command Run

```bash
docker run --rm \
  -v "$(pwd)/videos:/workspace/comparison_videos" \
  -v "$(pwd)/output:/workspace/screenshots" \
  ghcr.io/tjzine/frame-compare:latest \
  run
```

### 3.2 Interactive Mode

```bash
docker run -it --rm \
  -v "$(pwd):/workspace" \
  ghcr.io/tjzine/frame-compare:latest \
  wizard
```

---

## 4. pip Installation

### 4.1 Prerequisites

```bash
# Python 3.13+
python --version

# VapourSynth R72+ (manual installation)
# See: https://www.vapoursynth.com/doc/installation.html

# FFmpeg (for fallback)
ffmpeg -version
```

### 4.2 Install

```bash
# Create virtual environment
uv venv
source .venv/bin/activate

# Install frame-compare
pip install frame-compare

# Or with extras
pip install "frame-compare[vspreview,clipboard]"
```

### 4.3 Verify

```bash
frame-compare doctor
```

---

## 4.5 Windows Portable Bundle (Recommended for Windows)

The Windows portable bundle provides a **pinned, tested baseline** (VapourSynth + plugins + FFmpeg) without Docker.

SSOT:

- `docs/OPUS_REBUILD_FRAME_COMPARE/07-windows-portable-bundle/00-overview.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/07-windows-portable-bundle/01-bundle-spec.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/07-windows-portable-bundle/02-support-matrix.md`

---

## 5. DevContainer (Development)

### 5.1 Prerequisites

- VS Code with Remote - Containers extension
- Docker Desktop

### 5.2 Open in Container

1. Clone repository
2. Open in VS Code
3. Click "Reopen in Container" when prompted
4. Wait for container build

### 5.3 DevContainer Features

- Python 3.13 with uv
- VapourSynth with plugins
- Pre-configured extensions
- Pyright, Ruff enabled

---

## 6. Configuration

### 6.1 Configuration File

```toml
# config/config.toml

[paths]
input_dir = "comparison_videos"

[analysis]
frame_count = 10
random_seed = 42

[screenshots]
directory_name = "screenshots"

[slowpics]
auto_upload = true
visibility = "unlisted"
```

### 6.2 Environment Variables

| Variable | Description |
|----------|-------------|
| `FRAME_COMPARE_CONFIG` | Path to config file |
| `FRAME_COMPARE_ROOT` | Workspace root override |
| `FRAME_COMPARE_LOG_LEVEL` | DEBUG, INFO, WARNING, ERROR |
| `TMDB_API_KEY` | TMDB API key |

---

## 7. Health Checks

### 7.1 Doctor Command

```bash
frame-compare doctor

# Output:
# ✓ VapourSynth R73 detected
# ✓ libplacebo loaded
# ✓ FFmpeg available
# ✓ Config directory exists
# ⚠ VSPreview not installed (optional)
```

### 7.2 Container Health

```bash
docker compose ps
docker logs frame-compare
```

---

## 8. Baseline Verification Environment

The **authoritative baseline** for VapourSynth plugin detection is the pinned Docker image.
All "verified" claims in module specs (see [vs-module.md](../05-implementation/module-specs/vs-module.md)) refer to this baseline.

### 8.1 Baseline Specification

| Component | Version | Source | Namespace |
|:----------|:--------|:-------|:----------|
| VapourSynth | R73 | github.com/vapoursynth/vapoursynth | — |
| zimg | `release-3.0.5` | github.com/sekrit-twc/zimg | — |
| L-SMASH | `v2.14.5` | github.com/l-smash/l-smash | — |
| L-SMASH Works | `20230716` | github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works | `lsmas` (alias `lw`) |
| libplacebo | `v7.349.0` | github.com/haasn/libplacebo | `placebo` |
| vs-placebo | `14083805df08cd478539c15464a7183da2c0032e` | github.com/Lypheo/vs-placebo | `placebo` |
| ffms2 | `45673149e9a2f5586855ad472e3059084eaa36b1` | github.com/FFMS/ffms2 | `ffms2` |
| Python | 3.13.1 | Docker base image (`python:3.13.1-slim-bookworm`) | — |
| FFmpeg | Debian Bookworm (FFmpeg 5.x) | Debian Bookworm packages | — |

### 8.2 Building the Baseline Image

```bash
# Build from project root
docker build -t frame-compare-baseline .

# Verify labels
docker inspect frame-compare-baseline --format '{{json .Config.Labels}}' | jq
```

### 8.3 Running Baseline Smoke Test

```bash
# Run doctor inside baseline
docker run --rm frame-compare-baseline frame-compare doctor --json

# Verify plugin namespaces directly
docker run --rm frame-compare-baseline python3 -c "
import vapoursynth as vs
core = vs.core
plugins = {p.namespace: p.name for p in core.plugins()}
print('Discovered namespaces:', list(plugins.keys()))
assert 'lsmas' in plugins, 'L-SMASH Works (lsmas) not found'
print('Baseline OK')
"
```

### 8.4 Namespace Verification

The `doctor --json` output includes `discovered_namespace` for each plugin check:

```json
{
  "id": "lsmash",
  "status": "pass",
  "discovered_namespace": "lsmas",
  "expected_namespace": "lsmas",
  "install_hint": null
}
```

If a plugin is missing, the output includes an `install_hint` pointing users to
the baseline container or installation instructions.

---

## 9. Troubleshooting

### 9.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "VapourSynth not found" | VS not installed/configured | Use Docker or install VS |
| "Permission denied" | File permissions | Check volume mount permissions |
| "No videos found" | Wrong path | Verify input directory |
| "libplacebo error" | Plugin missing | Rebuild container or install plugin |

### 9.2 Logs

```bash
# Docker logs
docker compose logs -f

# CLI verbose mode
frame-compare --verbose run
```
