# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Build VapourSynth + plugins
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13.1-slim-bookworm AS builder

# Deterministic version pins (change these to update components)
ARG VAPOURSYNTH_REF=R73
ARG ZIMG_REF=release-3.0.5
ARG ZIMG_SHA256=a9a0226bf85e0d83c41a8ebe4e3e690e1348682f6a2a7838f1b8cbff1b799bcf
ARG LSMASH_REF=v2.14.5
ARG LSMASH_SHA256=e6f7c31de684f4b89ee27e5cd6262bf96f2a5b117ba938d2d606cf6220f05935
ARG LSMASH_WORKS_REF=20230716
ARG LIBPLACEBO_REF=v7.349.0
ARG VS_PLACEBO_REF=14083805df08cd478539c15464a7183da2c0032e
ARG FFMS2_REF=45673149e9a2f5586855ad472e3059084eaa36b1

# Complete build dependencies for Debian Bookworm (do NOT modify without plan revision)
RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    git \
    liblzma-dev \
    libtool \
    libvulkan-dev \
    libxxhash-dev \
    meson \
    nasm \
    ninja-build \
    pkg-config \
    python3-dev \
    python3-jinja2 \
    zlib1g-dev \
    # FFmpeg development libraries (Bookworm versions)
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

# Ensure Python tooling for native builds (Cython for VapourSynth bindings).
RUN python -m pip install --no-cache-dir "cython>=3.0,<4"

WORKDIR /build

# Build zimg (pinned tag + checksum)
RUN curl -fsSL "https://github.com/sekrit-twc/zimg/archive/refs/tags/${ZIMG_REF}.tar.gz" \
        -o zimg.tar.gz && \
    echo "${ZIMG_SHA256}  zimg.tar.gz" | sha256sum -c - && \
    tar -xzf zimg.tar.gz && \
    cd "zimg-${ZIMG_REF}" && \
    ./autogen.sh && \
    ./configure --prefix=/usr/local && \
    make -j"$(nproc)" && \
    make install && \
    ldconfig && \
    cd /build && \
    rm -rf "zimg-${ZIMG_REF}" zimg.tar.gz

# Build VapourSynth (pinned to R73 tag)
RUN git clone --depth 1 --branch "${VAPOURSYNTH_REF}" \
    https://github.com/vapoursynth/vapoursynth.git && \
    cd vapoursynth && \
    ./autogen.sh && \
    ./configure --prefix=/usr/local && \
    make -j"$(nproc)" && \
    make install && \
    ldconfig

# Build L-SMASH (pinned tag)
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

# Build L-SMASH-Works (pinned tag)
RUN git clone --depth 1 --branch "${LSMASH_WORKS_REF}" \
    https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works.git && \
    cd L-SMASH-Works && \
    perl -0777 -i -pe 's/#include <emmintrin.h>/#if defined(__SSE2__) || defined(__x86_64__) || defined(__i386__)\n#include <emmintrin.h>\n#endif/' VapourSynth/video_output.c && \
    perl -0777 -i -pe 's/(static inline __m128i _MM_PACKUS_EPI32[\s\S]*?\n}\n)/#if defined(__SSE2__) || defined(__x86_64__) || defined(__i386__)\n$1#endif\n/' VapourSynth/video_output.c && \
    perl -0777 -i -pe 's/(\n\s*if\( vshp->input_pixel_format == AV_PIX_FMT_P010LE[\s\S]*?\n\s*else\n)(\s*sws_scale\([^;]+\);)/\n#if defined(__SSE2__) || defined(__x86_64__) || defined(__i386__)$1$2\n#else\n$2\n#endif/s' VapourSynth/video_output.c && \
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
RUN git clone --depth 1 --recurse-submodules --shallow-submodules \
    https://github.com/Lypheo/vs-placebo.git && \
    cd vs-placebo && \
    git checkout "${VS_PLACEBO_REF}" && \
    meson setup build && \
    ninja -C build && \
    cp build/libvs_placebo.so /usr/local/lib/vapoursynth/

# Build ffms2 (pinned to commit SHA for FFmpeg 5 compatibility)
RUN git clone https://github.com/FFMS/ffms2.git && \
    cd ffms2 && \
    git checkout "${FFMS2_REF}" && \
    ./autogen.sh && \
    ./configure --prefix=/usr/local && \
    make -j"$(nproc)" && \
    make install && \
    ldconfig && \
    cp src/core/.libs/libffms2.so /usr/local/lib/vapoursynth/

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13.1-slim-bookworm AS runtime

# Runtime dependencies for Debian Bookworm (do NOT add build tools here)
# Use ffmpeg meta-package for AV libs to avoid version-specific package names
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        libxxhash0 \
        wget \
        which \
        && \
    rm -rf /var/lib/apt/lists/*

# Copy VapourSynth from builder
COPY --from=builder /usr/local/lib/libvapoursynth*.so* /usr/local/lib/
COPY --from=builder /usr/local/lib/vapoursynth/ /usr/local/lib/vapoursynth/
COPY --from=builder /usr/local/lib/python3.13/site-packages/vapoursynth* /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/include/vapoursynth/ /usr/local/include/vapoursynth/

# Copy zimg from builder
COPY --from=builder /usr/local/lib/libzimg*.so* /usr/local/lib/

# Copy L-SMASH from builder
COPY --from=builder /usr/local/lib/liblsmash*.so* /usr/local/lib/

# Copy libplacebo from builder (Debian multiarch install path)
COPY --from=builder /usr/local/lib/aarch64-linux-gnu/libplacebo*.so* /usr/local/lib/

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
