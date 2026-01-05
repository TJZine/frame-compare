---
RUN_ID: 2025-12-27__p0-5__container-setup
VERSION: v1
TARGET: Phase 0 → Item 0.5 (Container Setup)
INPUTS:
  - docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/002-containerization.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
  - docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v1.md
---

# Implementation Plan: Container Setup (Phase 0.5)

## Context

**Phase:** 0 (Foundation)
**Module:** Container/DevOps
**Spec Reference:** [ADR-002: Containerization Strategy](file:///Users/tristan/Software/frame-compare/docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/002-containerization.md)
**Dependencies:**

- Phase 0.1-0.4 complete (pyproject.toml, src/ structure, CI pipeline)
- Python 3.13 as base image target

## Scope

This plan covers:

- [x] Create multi-stage `Dockerfile`
- [x] Build VapourSynth R73+ in container
- [x] Install libplacebo with software rasterization
- [x] Create `docker-compose.yml`
- [x] Create `.devcontainer/devcontainer.json`

This plan does NOT cover:

- Publishing to ghcr.io (Phase 7)
- GPU passthrough (explicitly out of scope per ADR-002)
- VapourSynth runtime tests (Phase 3)

## Contract Impact

**Contracts touched:** NO

No canonical contract files under `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/` are modified by this plan.

---

## Files to Create/Modify

### 1. `Dockerfile`

**Purpose:** Multi-stage Docker build for Frame Compare with VapourSynth R73 baseline.

**Stage 1: Builder**

- Base: `python:3.13-slim`
- Install build dependencies: `meson`, `ninja-build`, `cmake`, `git`, `build-essential`
- Install VapourSynth development dependencies
- Build VapourSynth R73 from source
- Build L-SMASH-Works plugin (lsmas namespace `lw`)
- Build libplacebo headless (software rasterization, namespace `placebo`)
- Build ffms2 v2.40 (namespace `ffms2`)

**Stage 2: Runtime**

- Base: `python:3.13-slim`
- Copy compiled VapourSynth binaries and plugins from builder
- Install Python runtime dependencies
- Configure plugin paths via `VSPluginPath`
- Set entrypoint to `frame-compare`

```dockerfile
# Stage 1: Build VapourSynth + plugins
FROM python:3.13-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    meson \
    ninja-build \
    pkg-config \
    python3-dev \
    zlib1g-dev \
    libffms2-dev \
    nasm \
    autoconf \
    automake \
    libtool \
    libxxhash-dev \
    libzimg-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Build VapourSynth R73
RUN git clone --depth 1 --branch R73 https://github.com/vapoursynth/vapoursynth.git && \
    cd vapoursynth && \
    ./autogen.sh && \
    ./configure --prefix=/usr/local && \
    make -j$(nproc) && \
    make install && \
    ldconfig

# Build L-SMASH-Works (lsmas)
RUN git clone --depth 1 https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works.git && \
    cd L-SMASH-Works/VapourSynth && \
    meson setup build && \
    ninja -C build && \
    cp build/libvslsmashsource.so /usr/local/lib/vapoursynth/

# Build libplacebo (headless, software rasterization)
RUN git clone --depth 1 https://github.com/haasn/libplacebo.git && \
    cd libplacebo && \
    meson setup build -Dvulkan=disabled -Dopengl=disabled -Dshaderc=disabled && \
    ninja -C build && \
    ninja -C build install && \
    ldconfig

# Build vs-placebo plugin
RUN git clone --depth 1 https://github.com/Lypheo/vs-placebo.git && \
    cd vs-placebo && \
    meson setup build && \
    ninja -C build && \
    cp build/libvs_placebo.so /usr/local/lib/vapoursynth/

# Build ffms2
RUN git clone --depth 1 --branch 2.40 https://github.com/FFMS/ffms2.git && \
    cd ffms2 && \
    ./autogen.sh && \
    ./configure --prefix=/usr/local && \
    make -j$(nproc) && \
    make install && \
    ldconfig

# Stage 2: Runtime
FROM python:3.13-slim AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libzimg2 \
    libxxhash0 \
    libffms2-5 \
    && rm -rf /var/lib/apt/lists/*

# Copy VapourSynth from builder
COPY --from=builder /usr/local/lib/libvapoursynth*.so* /usr/local/lib/
COPY --from=builder /usr/local/lib/vapoursynth/ /usr/local/lib/vapoursynth/
COPY --from=builder /usr/local/lib/python3.13/site-packages/vapoursynth* /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/include/vapoursynth/ /usr/local/include/vapoursynth/

# Copy libplacebo from builder
COPY --from=builder /usr/local/lib/libplacebo*.so* /usr/local/lib/

# Update library cache
RUN ldconfig

# Set VapourSynth plugin path
ENV VAPOURSYNTH_PLUGIN_PATH=/usr/local/lib/vapoursynth

# Create non-root user
RUN useradd --create-home --shell /bin/bash framecompare
USER framecompare
WORKDIR /home/framecompare

# Install frame-compare (editable for dev, or from PyPI for prod)
COPY --chown=framecompare:framecompare . /home/framecompare/frame-compare/
WORKDIR /home/framecompare/frame-compare

# Install Python dependencies
RUN pip install --no-cache-dir --user -e .

# Add user bin to PATH
ENV PATH="/home/framecompare/.local/bin:${PATH}"

# Set entrypoint
ENTRYPOINT ["frame-compare"]
CMD ["--help"]
```

---

### 2. `docker-compose.yml`

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
    # Override entrypoint for interactive use
    entrypoint: ["/bin/bash"]
    stdin_open: true
    tty: true

  # Production-like service (non-interactive)
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

### 3. `.devcontainer/devcontainer.json`

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
- [ ] GIVEN built image WHEN `docker run frame-compare:dev frame-compare --help` THEN shows CLI help
- [ ] GIVEN built image WHEN `docker run frame-compare:dev python -c "import vapoursynth; print(vapoursynth.core.version())"` THEN prints R73+
- [ ] GIVEN built image WHEN `docker run frame-compare:dev python -c "import vapoursynth; c=vapoursynth.core; print(hasattr(c, 'lw'))"` THEN prints `True`
- [ ] GIVEN built image WHEN `docker run frame-compare:dev python -c "import vapoursynth; c=vapoursynth.core; print(hasattr(c, 'placebo'))"` THEN prints `True`
- [ ] GIVEN VS Code with DevContainers WHEN "Reopen in Container" THEN container opens successfully

---

## Verification Commands

Follow `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` → **Command Canon (SSOT)**.

```bash
# 1. Build the Docker image
docker compose build

# 2. Verify image was created
docker images | grep frame-compare

# 3. Test CLI availability
docker run --rm frame-compare:dev frame-compare --help

# 4. Test VapourSynth version (should be R73+)
docker run --rm frame-compare:dev python -c "import vapoursynth; print(f'VS Version: {vapoursynth.core.version()}')"

# 5. Test lsmas plugin (lw namespace)
docker run --rm frame-compare:dev python -c "import vapoursynth; c=vapoursynth.core; print(f'lsmas available: {hasattr(c, \"lw\")}')"

# 6. Test libplacebo plugin (placebo namespace)
docker run --rm frame-compare:dev python -c "import vapoursynth; c=vapoursynth.core; print(f'libplacebo available: {hasattr(c, \"placebo\")}')"

# 7. Test ffms2 plugin
docker run --rm frame-compare:dev python -c "import vapoursynth; c=vapoursynth.core; print(f'ffms2 available: {hasattr(c, \"ffms2\")}')"
```

**Pass criteria:** All commands exit 0 with expected output. VapourSynth version ≥ R73.

---

## Notes for Coding Agent

1. **Build order matters:** VapourSynth must be built before plugins that depend on it.

2. **libplacebo headless build:** Use `-Dvulkan=disabled -Dopengl=disabled` to force software rasterization (no GPU required).

3. **Plugin paths:** All `.so` files must go to `/usr/local/lib/vapoursynth/` and `VAPOURSYNTH_PLUGIN_PATH` env var must point there.

4. **The Dockerfile template above is complete** — implement it exactly as specified. No algorithm decisions needed.

5. **Dockerfile may need iteration:** If build fails due to missing dependencies, add them to the builder stage's `apt-get install` list. Common missing deps:
   - `liblzma-dev` (for L-SMASH)
   - `libass-dev` (for subtitle rendering if needed later)

6. **DevContainer requires directory structure:** Create `.devcontainer/` directory before adding `devcontainer.json`.

7. **Testing Docker build can be slow** (~10-20 minutes for first build). Use `docker compose build --progress=plain` to see full output.

8. **Do NOT modify any Python source files** — this is infrastructure only.

---

> **Proposed RUN_ID:** 2025-12-27__p0-5__container-setup
>
> Orchestrator: Please confirm with `CONFIRM RUN_ID: 2025-12-27__p0-5__container-setup` before running Plan Review Agent.

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Plan Review Agent for Frame Compare 2.0.

## RUN_ID

2025-12-27__p0-5__container-setup

## Plan to Review

Read file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v1.md

## Context Files to Read

1. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/03-architecture/adr/002-containerization.md
2. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md
3. Read file: docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md

## Your Task

Validate the plan using the 9-point checklist. Produce a Plan Review Report.

## Output

Write file: .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v1.md
