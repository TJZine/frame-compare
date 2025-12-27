# Operational Runbooks

> **Module:** Operations  
> **Version:** 1.0

---

## 1. Runbook Index

| ID | Runbook | Trigger |
|----|---------|---------|
| RB-001 | First-Time Setup | New installation |
| RB-002 | Container Deployment | Docker deployment |
| RB-003 | Troubleshooting Common Errors | Error codes |
| RB-004 | Cache Management | Cache issues |
| RB-005 | Network Issues | Upload failures |
| RB-006 | VapourSynth Issues | VS errors |
| RB-007 | Performance Optimization | Slow runs |
| RB-008 | Data Recovery | Lost data |

---

## 2. RB-001: First-Time Setup

### Trigger

New Frame Compare installation or fresh clone.

### Prerequisites

- Docker Desktop (recommended) OR
- Python 3.13+ with manual VapourSynth installation

### Steps

#### Option A: Docker (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/TJZine/frame-compare.git
cd frame-compare

# 2. Create directories
mkdir -p comparison_videos config screenshots generated

# 3. Copy config template
cp src/data/config.toml.template config/config.toml

# 4. Edit configuration
$EDITOR config/config.toml

# 5. Place videos
cp /path/to/your/videos/*.mkv comparison_videos/

# 6. Run
docker compose up
```

#### Option B: Manual Installation

```bash
# 1. Install Python 3.13+
# (Use pyenv, brew, or system package manager)

# 2. Install VapourSynth R72+
# See: https://www.vapoursynth.com/doc/installation.html

# 3. Clone and install
git clone https://github.com/TJZine/frame-compare.git
cd frame-compare
pip install uv
uv sync

# 4. Verify installation
uv run frame-compare doctor

# 5. Configure
uv run frame-compare wizard
```

### Verification

```bash
# Check all dependencies
frame-compare doctor

# Expected output:
# ✓ Python 3.13.x
# ✓ VapourSynth R72+
# ✓ libplacebo
# ✓ FFmpeg 6.x
```

---

## 3. RB-002: Container Deployment

### Trigger

Deploying Frame Compare using Docker.

### Prerequisites

- Docker Engine 24.0+
- Docker Compose v2

### Steps

#### Basic Deployment

```bash
# Build image
docker build -t frame-compare:latest .

# Or use pre-built
docker compose up
```

#### Custom Configuration

```yaml
# docker-compose.override.yml
version: "3.8"

services:
  frame-compare:
    environment:
      - FRAME_COMPARE_CONFIG=/workspace/config/custom.toml
      - FRAME_COMPARE_TMDB__API_KEY=${TMDB_API_KEY}  # canonical (TMDB_API_KEY also supported as alias)
    volumes:
      - /nas/videos:/workspace/comparison_videos:ro
      - ./output:/workspace/screenshots
```

#### GPU Support (Optional)

```yaml
# docker-compose.override.yml
services:
  frame-compare:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Verification

```bash
# Check container health
docker compose ps

# View logs
docker compose logs -f

# Interactive shell
docker compose exec frame-compare bash
```

---

## 4. RB-003: Troubleshooting Common Errors

### FC-1001 (CONFIG_NOT_FOUND) — Exit Code 2

**Symptom:** `Error: Configuration file not found: config/config.toml`

**Cause:** Config file missing or wrong path

**Resolution:**

```bash
# Create from template
cp src/data/config.toml.template config/config.toml

# Or use wizard
frame-compare wizard

# Or specify path
frame-compare --config /path/to/config.toml run
```

### FC-2001 (VAPOURSYNTH_NOT_FOUND) — Exit Code 3

**Symptom:** `Error: VapourSynth not available`

**Cause:** VapourSynth not installed or not in Python path

**Resolution:**

```bash
# Check VapourSynth
python -c "import vapoursynth; print(vapoursynth.core.version())"

# If missing, use Docker
docker compose up

# Or install manually
# Linux: apt install vapoursynth
# Windows: Download from vsrepo
```

### FC-3001 (NO_VIDEOS_FOUND) — Exit Code 4

**Symptom:** `Error: No video files found in comparison_videos`

**Cause:** No videos in input directory

**Resolution:**

```bash
# Check directory
ls -la comparison_videos/

# Check supported formats
# .mkv, .mp4, .avi, .m2ts, .ts

# Check path override
frame-compare --input /path/to/videos run
```

### FC-5002 (SLOWPICS_ERROR) — Exit Code 6

**Symptom:** `Error: Failed to upload to slow.pics`

**Cause:** Network issue or slow.pics down

**Resolution:**

```bash
# Check connectivity
curl -I https://slow.pics

# Run without upload
frame-compare run --no-upload

# Or use local report only
# In config.toml:
# [slowpics]
# auto_upload = false
```

---

## 5. RB-004: Cache Management

### Trigger

Cache-related issues like stale data or corruption.

### Cache Locations

| Cache | Location | Content |
|-------|----------|---------|
| Metrics | `generated/cache.compframes` | Frame metrics |
| Audio | `generated/audio_offsets.toml` | Audio alignment |
| Run | `.frame_compare.run.json` | Last run snapshot |

### Clear All Caches

```bash
rm -rf generated/*
rm -f .frame_compare.run.json
```

### Force Recompute

```bash
# Ignore cache, recompute everything
frame-compare run --no-cache
```

### Cache Cleanup Script

```bash
#!/bin/bash
# cleanup-cache.sh

# Remove caches older than 7 days
find generated/ -type f -mtime +7 -delete

# Remove orphaned cache entries
frame-compare cache clean  # (if implemented)
```

---

## 6. RB-005: Network Issues

### Trigger

Upload failures or metadata fetch errors.

### Diagnose Network

```bash
# Test slow.pics
curl -w "%{http_code}" -o /dev/null -s https://slow.pics

# Test TMDB
curl -H "Authorization: Bearer $TMDB_API_KEY" \
  https://api.themoviedb.org/3/configuration

# Check DNS
nslookup slow.pics
```

### Retry with Backoff

```bash
# Retry upload manually
frame-compare upload --retry 3 screenshots/
```

### Offline Mode

```toml
# config/config.toml
[slowpics]
auto_upload = false

[tmdb]
enabled = false

[report]
enable = true  # Generate local HTML instead
```

---

## 7. RB-006: VapourSynth Issues

### Trigger

VapourSynth or plugin errors.

### Diagnose Plugins

```bash
# List loaded plugins
python -c "
import vapoursynth as vs
core = vs.core
for p in dir(core):
    if not p.startswith('_'):
        print(p)
"
```

### libplacebo Issues

```bash
# Check libplacebo
python -c "
import vapoursynth as vs
core = vs.core
print(hasattr(core, 'placebo'))
"

# If missing, tonemapping won't work
# Use FFmpeg fallback:
# [screenshots]
# use_ffmpeg = true
```

### Memory Issues

```bash
# Increase VapourSynth cache
export VS_BUFFER_SIZE=2048  # MB

# Or in Python
vs.core.max_cache_size = 2048
```

---

## 8. RB-007: Performance Optimization

### Trigger

Slow runs or resource exhaustion.

### Profile Run

```bash
# Verbose mode shows timing
frame-compare --verbose run

# Check stage durations in logs
jq '.stages' logs/performance.json
```

### Reduce Frame Count

```toml
# config/config.toml
[analysis]
frame_count = 5  # Reduce from default 10
```

### Disable Expensive Operations

```toml
# config/config.toml
[audio_alignment]
enable = false  # Skip audio alignment

[diagnostics]
per_frame_nits = false  # Skip HDR metrics
```

### Use Caching Aggressively

```bash
# First run computes, second uses cache
frame-compare run  # Slow
frame-compare run  # Fast (cache hit)
```

---

## 9. RB-008: Data Recovery

### Trigger

Lost screenshots, interrupted runs.

### Recover from Cache

```bash
# If run was interrupted, screenshots may exist
ls screenshots/

# Retry from cache (no recompute)
frame-compare run --from-cache-only
```

### Recover Comparison URL

```bash
# Check run snapshot
cat .frame_compare.run.json | jq '.slowpics_url'

# Check logs
grep "upload_completed" logs/frame-compare.log | jq '.url'
```

### Manual Upload

```bash
# If screenshots exist but weren't uploaded
# Use slow.pics web interface to upload manually
# Or retry:
frame-compare upload screenshots/
```

---

## 10. Emergency Procedures

### Complete Reset

```bash
# Nuclear option - reset everything
rm -rf generated/ screenshots/ .frame_compare.run.json
cp src/data/config.toml.template config/config.toml
frame-compare wizard
```

### Container Recovery

```bash
# Rebuild container from scratch
docker compose down
docker system prune -f
docker compose build --no-cache
docker compose up
```

### Report Bug

When reporting issues:

1. Run with verbose logging: `frame-compare --verbose run`
2. Include log file: `logs/frame-compare.log`
3. Include config (redact API keys): `config/config.toml`
4. Include doctor output: `frame-compare doctor --json`
5. Include `--diagnose-paths` output
