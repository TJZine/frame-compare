# ADR-002: Containerization Strategy

## Status

Accepted

## Date

2025-12-16

## Context

VapourSynth installation is notoriously complex, requiring:

- Platform-specific compilation steps
- Multiple plugin dependencies (libplacebo, etc.)
- Correct Python binding configuration
- Environment variables for plugin paths

This complexity is the primary adoption barrier for Frame Compare.

## Decision

**Adopt a container-first deployment strategy using Docker with multi-stage builds.**

Provide:

1. Production image with all dependencies pre-built
2. DevContainer for VS Code development
3. Docker Compose for local orchestration
4. PyPI package as secondary distribution (VapourSynth not bundled)

## Considered Alternatives

### Alternative 1: Native installation only

- Pros: No container overhead, familiar to Python users
- Cons: VapourSynth installation remains painful

### Alternative 2: Flatpak/Snap

- Pros: Linux-native packaging
- Cons: Windows support poor, less control

### Alternative 3: Pre-built Python wheels with bundled VS

- Pros: pip-installable
- Cons: Wheel size, platform matrix complexity

## Rationale

- Docker provides reproducible environments across platforms
- Multi-stage builds minimize image size
- DevContainers enable immediate developer onboarding
- Container runtime is widely available on target platforms
- FFmpeg fallback remains available for non-container users

## Consequences

### Positive

- Zero-config deployment achieved
- Reproducible builds across platforms
- Developer onboarding reduced to "click container"
- CI/CD consistency

### Negative

- Docker runtime required
- Image size larger than native install (~1GB+)
- Volume mounting adds complexity for large files
- Windows Docker has performance overhead

### Risks

- libplacebo software rasterization may limit tonemap quality
- GPU passthrough not available in container

## Implementation

### Dockerfile Structure

```dockerfile
# Stage 1: Build VapourSynth + plugins
FROM python:3.13.1-slim-bookworm AS builder
# NOTE: This is illustrative. The repo-root `Dockerfile` is the authoritative baseline for exact pins and build steps.
# - Install Bookworm build deps (includes curl/ca-certificates/python3-jinja2/libvulkan-dev)
# - Build zimg + L-SMASH from pinned tarballs (SHA-256 verified)
# - Build VapourSynth R73
# - Build L-SMASH-Works (tag 20230716; ARM SSE2 guard)
# - Build libplacebo (v7.349.0; headless flags)
# - Build vs-placebo (commit + submodules)
# - Build ffms2 (FFmpeg 5-compatible commit)

# Stage 2: Runtime
FROM python:3.13.1-slim-bookworm AS runtime
# Install runtime deps (ffmpeg + libxxhash0) and copy built libs/plugins from builder
ENTRYPOINT ["frame-compare"]
```

### Docker Compose

```yaml
version: "3.8"
services:
  frame-compare:
    image: ghcr.io/tjzine/frame-compare:latest
    volumes:
      - ./videos:/workspace/comparison_videos
      - ./config:/workspace/config
      - ./output:/workspace/screenshots
    working_dir: /workspace
```

## References

- Docker multi-stage builds documentation
- VS Code DevContainers specification
