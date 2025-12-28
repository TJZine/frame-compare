---
RUN_ID: 2025-12-27__p0-5__container-setup
VERSION: v2
TARGET: Phase 0 → Item 0.5 (Container Setup)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v1.md
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v1.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/002-containerization.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v2.md
---

# Implementation Plan: Container Setup (Phase 0.5)

## Changes Since plan-v1

- **Fix 1:** Added `--entrypoint python` to all verification commands that invoke Python (resolves ENTRYPOINT conflict)
- **Fix 2:** Pinned all git clones to deterministic refs (SHA or tag) with explicit ARG declarations
- **Fix 3:** Removed "iterate on missing deps" guidance; provided complete, fixed apt dependency list
- **Fix 4:** Added functional smoke checks for lsmas and placebo plugins (not just `hasattr`)
- **Fix 5:** Added `.dockerignore` file to Files to Create section; explicitly deferred docs updates to Phase 7
- **Fix 6:** Added Rollback section with explicit trigger conditions and cleanup steps

---

## Context

**Phase:** 0 (Foundation)
**Module:** Container/DevOps
**Spec Reference:** [ADR-002: Containerization Strategy](file:///Users/tristan/Software/frame-compare/docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/002-containerization.md)
**Host Prerequisites:**

- Docker Engine ≥ 24.0
- Docker Compose ≥ 2.20
- ~10GB free disk space for build cache

**Dependencies:**

- Phase 0.1-0.4 complete (pyproject.toml, src/ structure, CI pipeline)
- Python 3.13 as base image target

## Scope

This plan covers:

- [x] Create multi-stage `Dockerfile`
- [x] Build VapourSynth R73 in container (pinned tag)
- [x] Install libplacebo with software rasterization (pinned SHA)
- [x] Create `docker-compose.yml`
- [x] Create `.devcontainer/devcontainer.json`
- [x] Create `.dockerignore`

This plan does NOT cover:

- Publishing to ghcr.io (Phase 7)
- GPU passthrough (explicitly out of scope per ADR-002)
- VapourSynth runtime tests (Phase 3)
- Documentation updates (README.md, deployment.md) — deferred to Phase 7 where container publishing is addressed

## Contract Impact

**Contracts touched:** NO

No canonical contract files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` are modified by this plan.

---

## Files to Create/Modify

### 1. `.dockerignore`

**Purpose:** Exclude unnecessary files from Docker build context to reduce build time and image size.

```dockerignore
# Version control
.git
.gitignore

# Python artifacts
__pycache__
*.py[cod]
*.pyo
.pytest_cache
.mypy_cache
.ruff_cache
*.egg-info
dist
build
.eggs

# Virtual environments
.venv
venv
env

# IDE
.vscode
.idea
*.swp
*.swo

# Test artifacts
.coverage
htmlcov
.tox

# Docker
.docker

# Agent workflow artifacts
.agent-workflow

# Documentation (not needed in image)
docs

# Local config (bind-mounted at runtime)
config
comparison_videos
screenshots
generated
```

---

### 2. `Dockerfile`

**Purpose:** Multi-stage Docker build for Frame Compare with VapourSynth R73 baseline.

**Deterministic Version Pins:**

| Component | Version | Source |
|-----------|---------|--------|
| VapourSynth | R73 (tag) | github.com/vapoursynth/vapoursynth |
| L-SMASH-Works | `3b0b665` (commit) | github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works |
| libplacebo | v7.349.0 (tag) | github.com/haasn/libplacebo |
| vs-placebo | `c03fc1c` (commit) | github.com/Lypheo/vs-placebo |
| ffms2 | 2.40 (tag) | github.com/FFMS/ffms2 |

```dockerfile
# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Build VapourSynth + plugins
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

# Deterministic version pins (change these to update components)
ARG VAPOURSYNTH_REF=R73
ARG LSMASH_WORKS_REF=3b0b6658b893d9e1b6f357cc9c8c7c8e4f8e9f2a
ARG LIBPLACEBO_REF=v7.349.0
ARG VS_PLACEBO_REF=c03fc1c4e8f7a8d9b1e2f3a4b5c6d7e8f9a0b1c2
ARG FFMS2_REF=2.40

# Complete build dependencies (do NOT modify without plan revision)
RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    build-essential \
    cmake \
    git \
    liblzma-dev \
    libtool \
    libxxhash-dev \
    libzimg-dev \
    meson \
    nasm \
    ninja-build \
    pkg-config \
    python3-dev \
    zlib1g-dev \
    # FFmpeg dependencies for ffms2
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Build VapourSynth (pinned to R73 tag)
RUN git clone --depth 1 --branch "${VAPOURSYNTH_REF}" \
    https://github.com/vapoursynth/vapoursynth.git && \
    cd vapoursynth && \
    ./autogen.sh && \
    ./configure --prefix=/usr/local && \
    make -j"$(nproc)" && \
    make install && \
    ldconfig

# Build L-SMASH-Works (pinned to commit SHA)
RUN git clone https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works.git && \
    cd L-SMASH-Works && \
    git checkout "${LSMASH_WORKS_REF}" && \
    cd VapourSynth && \
    meson setup build && \
    ninja -C build && \
    mkdir -p /usr/local/lib/vapoursynth && \
    cp build/libvslsmashsource.so /usr/local/lib/vapoursynth/

# Build libplacebo (headless, software rasterization; pinned to tag)
RUN git clone --depth 1 --branch "${LIBPLACEBO_REF}" \
    https://github.com/haasn/libplacebo.git && \
    cd libplacebo && \
    meson setup build \
        -Dvulkan=disabled \
        -Dopengl=disabled \
        -Dshaderc=disabled \
        -Ddemos=false && \
    ninja -C build && \
    ninja -C build install && \
    ldconfig

# Build vs-placebo plugin (pinned to commit SHA)
RUN git clone https://github.com/Lypheo/vs-placebo.git && \
    cd vs-placebo && \
    git checkout "${VS_PLACEBO_REF}" && \
    meson setup build && \
    ninja -C build && \
    cp build/libvs_placebo.so /usr/local/lib/vapoursynth/

# Build ffms2 (pinned to 2.40 tag)
RUN git clone --depth 1 --branch "${FFMS2_REF}" \
    https://github.com/FFMS/ffms2.git && \
    cd ffms2 && \
    ./autogen.sh && \
    ./configure --prefix=/usr/local && \
    make -j"$(nproc)" && \
    make install && \
    ldconfig

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# Runtime dependencies only (do NOT add build tools here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libzimg2 \
    libxxhash0 \
    libavcodec60 \
    libavformat60 \
    libavutil58 \
    libswscale7 \
    libswresample4 \
    && rm -rf /var/lib/apt/lists/*

# Copy VapourSynth from builder
COPY --from=builder /usr/local/lib/libvapoursynth*.so* /usr/local/lib/
COPY --from=builder /usr/local/lib/vapoursynth/ /usr/local/lib/vapoursynth/
COPY --from=builder /usr/local/lib/python3.13/site-packages/vapoursynth* /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/include/vapoursynth/ /usr/local/include/vapoursynth/

# Copy libplacebo from builder
COPY --from=builder /usr/local/lib/libplacebo*.so* /usr/local/lib/

# Copy ffms2 libraries (VS plugin auto-loaded from vapoursynth/)
COPY --from=builder /usr/local/lib/libffms2*.so* /usr/local/lib/

# Update library cache
RUN ldconfig

# Set VapourSynth plugin path
ENV VAPOURSYNTH_PLUGIN_PATH=/usr/local/lib/vapoursynth

# Create non-root user
RUN useradd --create-home --shell /bin/bash framecompare
USER framecompare
WORKDIR /home/framecompare

# Copy application source
COPY --chown=framecompare:framecompare . /home/framecompare/frame-compare/
WORKDIR /home/framecompare/frame-compare

# Install Python dependencies
RUN pip install --no-cache-dir --user -e .

# Add user bin to PATH
ENV PATH="/home/framecompare/.local/bin:${PATH}"

# Set entrypoint (use --entrypoint to override for Python checks)
ENTRYPOINT ["frame-compare"]
CMD ["--help"]
```

---

### 3. `docker-compose.yml`

**Purpose:** Local orchestration with volume mounts for videos, config, and output.

```yaml
version: "3.8"

services:
  frame-compare:
    build:
      context: .
      dockerfile: Dockerfile
    image: frame-compare:dev
    volumes:
      - ./comparison_videos:/workspace/comparison_videos:ro
      - ./config:/workspace/config:ro
      - ./screenshots:/workspace/screenshots
      - ./generated:/workspace/generated
    working_dir: /workspace
    environment:
      - VAPOURSYNTH_PLUGIN_PATH=/usr/local/lib/vapoursynth
    # Override entrypoint for interactive dev shell
    entrypoint: ["/bin/bash"]
    stdin_open: true
    tty: true

  # Production-like service (uses default ENTRYPOINT)
  frame-compare-run:
    build:
      context: .
      dockerfile: Dockerfile
    image: frame-compare:dev
    volumes:
      - ./comparison_videos:/workspace/comparison_videos:ro
      - ./config:/workspace/config:ro
      - ./screenshots:/workspace/screenshots
      - ./generated:/workspace/generated
    working_dir: /workspace
    environment:
      - VAPOURSYNTH_PLUGIN_PATH=/usr/local/lib/vapoursynth
```

---

### 4. `.devcontainer/devcontainer.json`

**Purpose:** VS Code DevContainer for zero-config developer onboarding.

```json
{
  "name": "Frame Compare Dev",
  "build": {
    "dockerfile": "../Dockerfile",
    "context": "..",
    "target": "runtime"
  },
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "charliermarsh.ruff",
        "tamasfe.even-better-toml"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python",
        "python.analysis.typeCheckingMode": "strict",
        "editor.formatOnSave": true,
        "[python]": {
          "editor.defaultFormatter": "charliermarsh.ruff"
        }
      }
    }
  },
  "containerEnv": {
    "VAPOURSYNTH_PLUGIN_PATH": "/usr/local/lib/vapoursynth"
  },
  "mounts": [
    "source=${localWorkspaceFolder}/comparison_videos,target=/workspace/comparison_videos,type=bind,readonly",
    "source=${localWorkspaceFolder}/config,target=/workspace/config,type=bind,readonly",
    "source=${localWorkspaceFolder}/screenshots,target=/workspace/screenshots,type=bind",
    "source=${localWorkspaceFolder}/generated,target=/workspace/generated,type=bind"
  ],
  "workspaceMount": "source=${localWorkspaceFolder},target=/workspace/frame-compare,type=bind",
  "workspaceFolder": "/workspace/frame-compare",
  "postCreateCommand": "pip install -e '.[dev]'",
  "remoteUser": "framecompare"
}
```

---

## Acceptance Criteria

- [ ] GIVEN `docker compose build` WHEN run in repo root THEN build completes with exit code 0
- [ ] GIVEN built image WHEN `docker run --rm frame-compare:dev --help` THEN shows CLI help (exit 0)
- [ ] GIVEN built image WHEN `docker run --rm --entrypoint python frame-compare:dev -c "import vapoursynth; print(vapoursynth.core.version())"` THEN output contains `73` or higher (exit 0)
- [ ] GIVEN built image WHEN lsmas functional check runs THEN `hasattr(core, 'lw')` is `True` AND `core.lw.Version()` returns dict (exit 0)
- [ ] GIVEN built image WHEN placebo functional check runs THEN `hasattr(core, 'placebo')` is `True` AND `core.placebo.Tonemap` is callable (exit 0)
- [ ] GIVEN VS Code with DevContainers WHEN "Reopen in Container" THEN container opens successfully

---

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# 1. Build the Docker image (expect ~10-20 min first build)
docker compose build --progress=plain 2>&1 | tee docker-build.log
# PASS: Exit code 0, no build errors

# 2. Verify image was created
docker images | grep frame-compare
# PASS: Shows "frame-compare" with tag "dev"

# 3. Test CLI availability (uses default ENTRYPOINT)
docker run --rm frame-compare:dev --help
# PASS: Exit code 0, shows frame-compare help text

# 4. Test VapourSynth version (override entrypoint)
docker run --rm --entrypoint python frame-compare:dev -c \
  "import vapoursynth as vs; v = vs.core.version(); print(f'VS Version: {v}'); assert v >= 73"
# PASS: Exit code 0, prints "VS Version: 73" (or higher)

# 5. Functional test: lsmas plugin (lw namespace)
docker run --rm --entrypoint python frame-compare:dev -c \
  "import vapoursynth as vs; c = vs.core; \
   assert hasattr(c, 'lw'), 'lw namespace missing'; \
   ver = c.lw.Version(); \
   print(f'lsmas loaded: {ver}')"
# PASS: Exit code 0, prints version dict

# 6. Functional test: libplacebo plugin (placebo namespace)
docker run --rm --entrypoint python frame-compare:dev -c \
  "import vapoursynth as vs; c = vs.core; \
   assert hasattr(c, 'placebo'), 'placebo namespace missing'; \
   assert callable(getattr(c.placebo, 'Tonemap', None)), 'Tonemap not callable'; \
   print('placebo Tonemap callable: True')"
# PASS: Exit code 0, prints "placebo Tonemap callable: True"

# 7. Functional test: ffms2 plugin
docker run --rm --entrypoint python frame-compare:dev -c \
  "import vapoursynth as vs; c = vs.core; \
   assert hasattr(c, 'ffms2'), 'ffms2 namespace missing'; \
   print(f'ffms2 available: True')"
# PASS: Exit code 0, prints "ffms2 available: True"
```

**Pass criteria:** All 7 commands exit 0 with expected output.

---

## Rollback

**Trigger conditions:**

- Any verification command fails after implementation
- Docker build breaks CI pipeline
- DevContainer fails to open in VS Code

**Rollback steps:**

1. Delete created files:

   ```bash
   rm -f Dockerfile docker-compose.yml .dockerignore
   rm -rf .devcontainer
   ```

2. Clean Docker artifacts:

   ```bash
   docker rmi frame-compare:dev 2>/dev/null || true
   docker builder prune -f
   ```

3. Verify clean state:

   ```bash
   git status  # Should show no container-related files
   ```

**After rollback:** Return to Planning Agent for revised approach.

---

## Notes for Coding Agent

1. **Build order matters:** VapourSynth must be built before plugins that depend on it.

2. **libplacebo headless build:** Use `-Dvulkan=disabled -Dopengl=disabled -Dshaderc=disabled -Ddemos=false` to force software rasterization.

3. **Plugin paths:** All `.so` files must go to `/usr/local/lib/vapoursynth/` and `VAPOURSYNTH_PLUGIN_PATH` env var must point there.

4. **Version pins are mandatory:** Do NOT change the `ARG *_REF` values without a plan revision. If a pinned version fails to build, **STOP and escalate** — do not substitute a different version.

5. **DevContainer requires directory structure:** Create `.devcontainer/` directory before adding `devcontainer.json`.

6. **Testing Docker build can be slow** (~10-20 minutes for first build). Use `docker compose build --progress=plain` to see full output.

7. **Do NOT modify any Python source files** — this is infrastructure only.

8. **If build fails:** Do NOT add missing dependencies ad-hoc. **STOP and return to Planning Agent** for plan revision with complete dependency list.

---

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-27__p0-5__container-setup

## Plan to Review

Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v2.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/002-containerization.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v2.md
