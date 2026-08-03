# ─────────────────────────────────────────────────────────────────────────────
# Stage 0: Pinned Python dependency tooling
# ─────────────────────────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:0.11.31@sha256:ecd4de2f060c64bea0ff8ecb182ddf46ba3fcccdc8a60cfdbaf20d1a047d7437 AS uv

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Build supplemental VapourSynth plugins
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13.13-slim-trixie@sha256:aa938a849bcb82dce8f49480f056ab82bf5c1c3ebc294f0430f37b6820e7f286 AS builder

# Deterministic version pins (change these to update components)
ARG VAPOURSYNTH_VERSION=76
ARG VAPOURSYNTH_SOURCE_COMMIT=aa7e83a0aaf87477b5e0fc13c5b97c5aa15a06b7
ARG VAPOURSYNTH_X86_64_WHEEL_SHA256=94986f4399b3ea8ab775abfbf5986dc58b93829fbf3db2a37e3b9e6454baf898
ARG VAPOURSYNTH_AARCH64_WHEEL_SHA256=c516b04c9fde70b7075266a067b611f9d8409a20a5380ae425c21e1bada10997
ARG LSMASH_REF=v2.14.5
ARG LSMASH_SHA256=e6f7c31de684f4b89ee27e5cd6262bf96f2a5b117ba938d2d606cf6220f05935
ARG LSMASH_WORKS_COMMIT=0079a06ee384061ecdadd0de03df4e0493dd56ab
ARG FFMS2_COMMIT=7ed5e4d039ca9a6236bd2ebdfdd656c4304fbe04

RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    build-essential \
    ca-certificates \
    curl \
    git \
    libtool \
    liblzma-dev \
    libxxhash-dev \
    meson \
    nasm \
    ninja-build \
    pkg-config \
    python3-dev \
    zlib1g-dev \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

RUN printf '%s\n' \
        "vapoursynth==${VAPOURSYNTH_VERSION} --hash=sha256:${VAPOURSYNTH_X86_64_WHEEL_SHA256} --hash=sha256:${VAPOURSYNTH_AARCH64_WHEEL_SHA256}" \
        > /tmp/vapoursynth-wheel-requirements.txt && \
    python -m pip install --no-cache-dir --require-hashes --only-binary=:all: \
        -r /tmp/vapoursynth-wheel-requirements.txt && \
    checkout_source_commit() { \
        repo_url="$1"; \
        commit="$2"; \
        dest="$3"; \
        rm -rf "$dest"; \
        git init "$dest" >/dev/null; \
        cd "$dest"; \
        git remote add origin "$repo_url"; \
        git fetch --depth 1 origin "$commit"; \
        git -c advice.detachedHead=false checkout --detach FETCH_HEAD; \
        test "$(git rev-parse HEAD)" = "$commit"; \
    }; \
    vs_include_dir="$(python -c 'import vapoursynth; print(vapoursynth.get_include())')" && \
    checkout_source_commit \
        "https://github.com/vapoursynth/vapoursynth.git" \
        "${VAPOURSYNTH_SOURCE_COMMIT}" \
        /tmp/vapoursynth-src && \
    test -f /tmp/vapoursynth-src/include/VapourSynth.h && \
    test -f /tmp/vapoursynth-src/include/VSHelper.h && \
    cp /tmp/vapoursynth-src/include/VapourSynth.h "${vs_include_dir}/" && \
    cp /tmp/vapoursynth-src/include/VSHelper.h "${vs_include_dir}/" && \
    rm -rf /tmp/vapoursynth-src

ENV PKG_CONFIG_PATH=/usr/local/lib/python3.13/site-packages/vapoursynth/pkgconfig
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.13/site-packages/vapoursynth

WORKDIR /build

# Build L-SMASH from a pinned upstream tag archive.
RUN LSMASH_DIR="l-smash-${LSMASH_REF#v}" && \
    curl -fsSL "https://github.com/l-smash/l-smash/archive/refs/tags/${LSMASH_REF}.tar.gz" \
        -o l-smash.tar.gz && \
    echo "${LSMASH_SHA256}  l-smash.tar.gz" | sha256sum -c - && \
    tar -xzf l-smash.tar.gz && \
    cd "${LSMASH_DIR}" && \
    ./configure --prefix=/usr/local --disable-static && \
    make -j"$(nproc)" && \
    make install && \
    ldconfig && \
    cd /build && \
    rm -rf "${LSMASH_DIR}" l-smash.tar.gz

# Build L-SMASH-Works against the R76 wheel headers/pkg-config metadata.
RUN checkout_source_commit() { \
        repo_url="$1"; \
        commit="$2"; \
        dest="$3"; \
        rm -rf "$dest"; \
        git init "$dest" >/dev/null; \
        cd "$dest"; \
        git remote add origin "$repo_url"; \
        git fetch --depth 1 origin "$commit"; \
        git -c advice.detachedHead=false checkout --detach FETCH_HEAD; \
        test "$(git rev-parse HEAD)" = "$commit"; \
    }; \
    checkout_source_commit \
        "https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works.git" \
        "${LSMASH_WORKS_COMMIT}" \
        /build/L-SMASH-Works && \
    cd /build/L-SMASH-Works/VapourSynth && \
    perl -0pi -e "s/  install: true,\\n  install_dir: join_paths\\(vapoursynth_dep\\.get_pkgconfig_variable\\('libdir'\\), 'vapoursynth'\\),\\n/  install: false,\\n/" meson.build && \
    meson setup build && \
    ninja -C build && \
    mkdir -p /opt/vapoursynth-extra-plugins/lsmas && \
    cp build/libvslsmashsource.so /opt/vapoursynth-extra-plugins/lsmas/ && \
    printf '[VapourSynth Manifest V1]\nlibvslsmashsource\n' \
        > /opt/vapoursynth-extra-plugins/lsmas/manifest.vs

# Build ffms2 5.0 against the distro FFmpeg development libraries.
RUN checkout_source_commit() { \
        repo_url="$1"; \
        commit="$2"; \
        dest="$3"; \
        rm -rf "$dest"; \
        git init "$dest" >/dev/null; \
        cd "$dest"; \
        git remote add origin "$repo_url"; \
        git fetch --depth 1 origin "$commit"; \
        git -c advice.detachedHead=false checkout --detach FETCH_HEAD; \
        test "$(git rev-parse HEAD)" = "$commit"; \
    }; \
    checkout_source_commit \
        "https://github.com/FFMS/ffms2.git" \
        "${FFMS2_COMMIT}" \
        /build/ffms2 && \
    cd /build/ffms2 && \
    ./autogen.sh && \
    ./configure --prefix=/usr/local && \
    make -j"$(nproc)" && \
    make install && \
    ldconfig && \
    mkdir -p /opt/vapoursynth-extra-plugins/ffms2 && \
    cp src/core/.libs/libffms2.so /opt/vapoursynth-extra-plugins/ffms2/ && \
    printf '[VapourSynth Manifest V1]\nlibffms2\n' \
        > /opt/vapoursynth-extra-plugins/ffms2/manifest.vs

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13.13-slim-trixie@sha256:aa938a849bcb82dce8f49480f056ab82bf5c1c3ebc294f0430f37b6820e7f286 AS runtime

ARG VAPOURSYNTH_VERSION=76
ARG VS_PLACEBO_VERSION=2.0.2
ARG VAPOURSYNTH_X86_64_WHEEL_SHA256=94986f4399b3ea8ab775abfbf5986dc58b93829fbf3db2a37e3b9e6454baf898
ARG VAPOURSYNTH_AARCH64_WHEEL_SHA256=c516b04c9fde70b7075266a067b611f9d8409a20a5380ae425c21e1bada10997
ARG VS_PLACEBO_X86_64_WHEEL_SHA256=cb44a42df2c7e78d614b4b0415e9b4d3c40659f9d57ac18d65076101f364fa8e
ARG VS_PLACEBO_AARCH64_WHEEL_SHA256=25a94cde45bea9f2e2503040772a34a1355520a14b339a77009b233cf9457c2d

COPY --from=uv /uv /uvx /usr/local/bin/

# Runtime dependencies for Debian Trixie (do NOT add build tools here)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        libvulkan1 \
        libxxhash0 \
        mesa-vulkan-drivers \
        procps \
        vulkan-tools \
        wget \
        which \
        && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/liblsmash*.so* /usr/local/lib/
COPY --from=builder /usr/local/lib/libffms2*.so* /usr/local/lib/
COPY --from=builder /opt/vapoursynth-extra-plugins/ /opt/vapoursynth-extra-plugins/

RUN ldconfig

ENV VAPOURSYNTH_EXTRA_PLUGIN_PATH=/opt/vapoursynth-extra-plugins
ENV LIBGL_ALWAYS_SOFTWARE=1

# Create non-root user
RUN useradd --create-home --shell /bin/bash framecompare
USER framecompare
WORKDIR /home/framecompare

# Export and install lock-derived Python runtime dependencies before copying full source.
COPY --chown=framecompare:framecompare pyproject.toml uv.lock /home/framecompare/frame-compare/
WORKDIR /home/framecompare/frame-compare
RUN uv export --frozen --no-dev --no-emit-project --format requirements.txt --output-file /tmp/requirements.lock.txt && \
    python -m pip install --no-cache-dir --user --require-hashes -r /tmp/requirements.lock.txt && \
    printf '%s\n' \
        "vapoursynth==${VAPOURSYNTH_VERSION} --hash=sha256:${VAPOURSYNTH_X86_64_WHEEL_SHA256} --hash=sha256:${VAPOURSYNTH_AARCH64_WHEEL_SHA256}" \
        "vs-placebo==${VS_PLACEBO_VERSION} --hash=sha256:${VS_PLACEBO_X86_64_WHEEL_SHA256} --hash=sha256:${VS_PLACEBO_AARCH64_WHEEL_SHA256}" \
        > /tmp/docker-plugin-requirements.txt && \
    python -m pip install --no-cache-dir --user --no-deps --require-hashes --only-binary=:all: \
        -r /tmp/docker-plugin-requirements.txt

# Copy application source
COPY --chown=framecompare:framecompare . /home/framecompare/frame-compare/

# Install the project itself without dependency resolution.
RUN python -m pip install --no-cache-dir --user --no-deps -e .

# Compose may run the image as the invoking host UID/GID so bind-mounted output
# remains host-owned. Allow that numeric identity to traverse the image user's
# home to the read-only installed CLI and dependencies without granting writes.
USER root
RUN chmod 0711 /home/framecompare
USER framecompare

# Add user bin to PATH
ENV PATH="/home/framecompare/.local/bin:${PATH}"

# Set entrypoint (use --entrypoint to override for Python checks)
ENTRYPOINT ["frame-compare"]
CMD ["--help"]

# ─────────────────────────────────────────────────────────────────────────────
# Stage 3: Development container
FROM runtime AS devcontainer

USER root
RUN install -d -m 0777 -o framecompare -g framecompare /workspace/frame-compare/.venv
USER framecompare
WORKDIR /workspace/frame-compare

# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: Optional Linux X11/VSPreview GUI runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM runtime AS gui-linux

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libdbus-1-3 \
        libegl1 \
        libfontconfig1 \
        libgl1 \
        libopengl0 \
        libx11-xcb1 \
        libxcb-cursor0 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-render-util0 \
        libxcb-xinerama0 \
        libxkbcommon-x11-0 \
        && \
    rm -rf /var/lib/apt/lists/*

USER framecompare
WORKDIR /home/framecompare/frame-compare

RUN uv export --frozen --no-dev --extra vspreview --no-emit-project --format requirements.txt \
        --output-file /tmp/requirements.vspreview.lock.txt && \
    python -m pip install --no-cache-dir --user --require-hashes \
        -r /tmp/requirements.vspreview.lock.txt

# Keep the default image target headless and CI-safe. The gui-linux target above is
# opt-in via docker-compose.gui-linux.yml and should not become the implicit result
# of `docker build .` or default compose builds.
FROM runtime AS default-runtime
