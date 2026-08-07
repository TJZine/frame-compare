# ─────────────────────────────────────────────────────────────────────────────
# Stage 0: Pinned Python dependency tooling
# ─────────────────────────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:0.12.2@sha256:069a51314a7bb6031777a9273205fe1b0b19e914ef418207d1338b268df641dd AS uv

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Build supplemental VapourSynth plugins
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13.14-slim-trixie@sha256:bf503bb2243c5aad0aa951544dd60d165f992646441d35dea90893703fc26251 AS builder

# Deterministic media-runtime pins. Every source archive is immutable and verified.
ARG VAPOURSYNTH_VERSION=78
ARG VAPOURSYNTH_SOURCE_COMMIT=c2f5751a412347f306eb7f6a5985dd9a719f3896
ARG VAPOURSYNTH_SOURCE_SHA256=fbf7986d96495abd106c714b01768671a8cab1d0c6a48feba0aa127bf5672753
ARG VAPOURSYNTH_SOURCE_BYTES=637989
ARG VAPOURSYNTH_X86_64_WHEEL_SHA256=8e70b98c40ac69477a15f8ae0c551c2a4e182281986b5996853c7a01477ed477
ARG VAPOURSYNTH_AARCH64_WHEEL_SHA256=5368661393622fe9fa267409a5fbf7143d561b55dafdf6a500ef0fe38b285386
ARG LSMASH_COMMIT=84740c5d960ab622f4c08b971dc59192bc27ef74
ARG LSMASH_SHA256=003d20595a3e66220a906c6bb351b8de973f2141fc24613db7701191f7219d5b
ARG LSMASH_BYTES=503390
ARG LSMASH_WORKS_COMMIT=a83318210c183c8ebbe703d975ffc76fb499ef07
ARG LSMASH_WORKS_SHA256=6a135d7258376b461fdcabf5573c3a09eda5e3784f55fd0e8a1c3fac37a2a819
ARG LSMASH_WORKS_BYTES=308701
ARG FFMS2_COMMIT=7ed5e4d039ca9a6236bd2ebdfdd656c4304fbe04
ARG FFMS2_SHA256=711e2330163700739c954c4f300d0dbbaed0c2360e0dc6debb29757640454d02
ARG FFMS2_BYTES=168105
ARG VS_PLACEBO_SOURCE_COMMIT=3cfd23f257ecb62b0cbd81eaaca092e18ae8e579
ARG VS_PLACEBO_SOURCE_SHA256=b1c3e6eab7e7c722aa1e5706aef70b5365f4a4c881b4573a6121e4c9572a8fbe
ARG VS_PLACEBO_SOURCE_BYTES=37902
ARG LIBPLACEBO_SOURCE_COMMIT=a7a18af88ff0a17c04840dcb3246047bb6b46df3
ARG LIBPLACEBO_SOURCE_SHA256=ba0c8c011c19cb74bcee26646d2d6070447151da89a9abdd01c9034e768de8b2
ARG LIBPLACEBO_SOURCE_BYTES=873993
ARG LIBDOVI_SOURCE_COMMIT=4fd2b2235c9f93582dd4a00e65ee34a07800afd7
ARG LIBDOVI_SOURCE_SHA256=8ccb1922d7dbb57bc4f2c15c10b90c462f7a5f292efe317c116db923728dd3f1
ARG LIBDOVI_SOURCE_BYTES=489628
ARG DEBIAN_FFMPEG_PACKAGE_VERSION=7:7.1.5-0+deb13u1

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
    && for package in \
        libavcodec-dev \
        libavformat-dev \
        libavutil-dev \
        libswscale-dev \
        libswresample-dev; do \
        test "$(dpkg-query -W -f='${Version}' "$package")" = "${DEBIAN_FFMPEG_PACKAGE_VERSION}"; \
    done \
    && rm -rf /var/lib/apt/lists/*

RUN printf '%s\n' \
        "vapoursynth==${VAPOURSYNTH_VERSION} --hash=sha256:${VAPOURSYNTH_X86_64_WHEEL_SHA256} --hash=sha256:${VAPOURSYNTH_AARCH64_WHEEL_SHA256}" \
        > /tmp/vapoursynth-wheel-requirements.txt && \
    python -m pip install --no-cache-dir --require-hashes --only-binary=:all: \
        -r /tmp/vapoursynth-wheel-requirements.txt && \
    curl -fsSL \
        "https://codeload.github.com/vapoursynth/vapoursynth/tar.gz/${VAPOURSYNTH_SOURCE_COMMIT}" \
        -o /tmp/vapoursynth-src.tar.gz && \
    test "$(wc -c < /tmp/vapoursynth-src.tar.gz | tr -d ' ')" = "${VAPOURSYNTH_SOURCE_BYTES}" && \
    echo "${VAPOURSYNTH_SOURCE_SHA256}  /tmp/vapoursynth-src.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/vapoursynth-src.tar.gz -C /tmp && \
    vs_include_dir="$(python -c 'import vapoursynth; print(vapoursynth.get_include())')" && \
    test -f "/tmp/vapoursynth-${VAPOURSYNTH_SOURCE_COMMIT}/include/VapourSynth.h" && \
    test -f "/tmp/vapoursynth-${VAPOURSYNTH_SOURCE_COMMIT}/include/VSHelper.h" && \
    test -f "/tmp/vapoursynth-${VAPOURSYNTH_SOURCE_COMMIT}/include/VapourSynth4.h" && \
    test -f "/tmp/vapoursynth-${VAPOURSYNTH_SOURCE_COMMIT}/include/VSHelper4.h" && \
    cp "/tmp/vapoursynth-${VAPOURSYNTH_SOURCE_COMMIT}/include/VapourSynth.h" "${vs_include_dir}/" && \
    cp "/tmp/vapoursynth-${VAPOURSYNTH_SOURCE_COMMIT}/include/VSHelper.h" "${vs_include_dir}/" && \
    cp "/tmp/vapoursynth-${VAPOURSYNTH_SOURCE_COMMIT}/include/VapourSynth4.h" "${vs_include_dir}/" && \
    cp "/tmp/vapoursynth-${VAPOURSYNTH_SOURCE_COMMIT}/include/VSHelper4.h" "${vs_include_dir}/" && \
    mkdir -p /opt/media-runtime-licenses && \
    cp "/tmp/vapoursynth-${VAPOURSYNTH_SOURCE_COMMIT}/COPYING.LESSER" \
        /opt/media-runtime-licenses/VapourSynth-LGPL-2.1.txt && \
    rm -rf "/tmp/vapoursynth-${VAPOURSYNTH_SOURCE_COMMIT}" /tmp/vapoursynth-src.tar.gz

ENV PKG_CONFIG_PATH=/usr/local/lib/python3.13/site-packages/vapoursynth/pkgconfig
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.13/site-packages/vapoursynth

WORKDIR /build

# Build the exact L-SMASH commit tested by L-SMASH-Works 1296.
# This commit is intentionally not described as a formal L-SMASH release.
RUN curl -fsSL \
        "https://codeload.github.com/l-smash/l-smash/tar.gz/${LSMASH_COMMIT}" \
        -o l-smash.tar.gz && \
    test "$(wc -c < l-smash.tar.gz | tr -d ' ')" = "${LSMASH_BYTES}" && \
    echo "${LSMASH_SHA256}  l-smash.tar.gz" | sha256sum -c - && \
    tar -xzf l-smash.tar.gz && \
    cd "l-smash-${LSMASH_COMMIT}" && \
    ./configure --prefix=/usr/local --disable-static && \
    make -j"$(nproc)" && \
    make install && \
    mkdir -p /opt/media-runtime-licenses && \
    cp LICENSE /opt/media-runtime-licenses/L-SMASH-LICENSE.txt && \
    ldconfig && \
    cd /build && \
    rm -rf "l-smash-${LSMASH_COMMIT}" l-smash.tar.gz

# Build L-SMASH-Works 1296 against the R78 API 4 wheel headers and
# Debian Trixie's runtime-matched FFmpeg development libraries. Upstream's
# Meson path is deprecated, but remains the narrow VapourSynth-only build and
# avoids pulling unrelated optional dependencies into the runtime baseline.
RUN curl -fsSL \
        "https://codeload.github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works/tar.gz/${LSMASH_WORKS_COMMIT}" \
        -o l-smash-works.tar.gz && \
    test "$(wc -c < l-smash-works.tar.gz | tr -d ' ')" = "${LSMASH_WORKS_BYTES}" && \
    echo "${LSMASH_WORKS_SHA256}  l-smash-works.tar.gz" | sha256sum -c - && \
    tar -xzf l-smash-works.tar.gz && \
    cd "L-SMASH-Works-${LSMASH_WORKS_COMMIT}/VapourSynth" && \
    perl -0pi -e "s/  install: true,\n  install_dir: join_paths\(vapoursynth_dep\.get_pkgconfig_variable\('libdir'\), 'vapoursynth'\),\n/  install: false,\n/" meson.build && \
    meson setup build --buildtype=release && \
    ninja -C build && \
    mkdir -p /opt/vapoursynth-extra-plugins/lsmas && \
    cp build/libvslsmashsource.so /opt/vapoursynth-extra-plugins/lsmas/ && \
    printf '[VapourSynth Manifest V1]\nlibvslsmashsource\n' \
        > /opt/vapoursynth-extra-plugins/lsmas/manifest.vs && \
    cp LICENSE /opt/media-runtime-licenses/L-SMASH-Works-VapourSynth-LICENSE.txt && \
    cd /build && \
    rm -rf "L-SMASH-Works-${LSMASH_WORKS_COMMIT}" l-smash-works.tar.gz

# Rebuild the latest stable FFMS2 release against the selected VapourSynth
# headers and the same Debian FFmpeg ABI used by the runtime image.
RUN curl -fsSL \
        "https://codeload.github.com/FFMS/ffms2/tar.gz/${FFMS2_COMMIT}" \
        -o ffms2.tar.gz && \
    test "$(wc -c < ffms2.tar.gz | tr -d ' ')" = "${FFMS2_BYTES}" && \
    echo "${FFMS2_SHA256}  ffms2.tar.gz" | sha256sum -c - && \
    tar -xzf ffms2.tar.gz && \
    cd "ffms2-${FFMS2_COMMIT}" && \
    ./autogen.sh && \
    ./configure --prefix=/usr/local && \
    make -j"$(nproc)" && \
    make install && \
    ldconfig && \
    mkdir -p /opt/vapoursynth-extra-plugins/ffms2 && \
    cp src/core/.libs/libffms2.so /opt/vapoursynth-extra-plugins/ffms2/ && \
    printf '[VapourSynth Manifest V1]\nlibffms2\n' \
        > /opt/vapoursynth-extra-plugins/ffms2/manifest.vs && \
    cp COPYING /opt/media-runtime-licenses/FFMS2-COPYING.txt && \
    cd /build && \
    rm -rf "ffms2-${FFMS2_COMMIT}" ffms2.tar.gz

# Preserve corresponding-source and license provenance for wheel-bundled
# vs-placebo dependencies. These archives are not used to build the wheels;
# they document the immutable sources selected by the upstream 2.0.4 release.
RUN fetch_source() { \
        name="$1"; \
        url="$2"; \
        expected_bytes="$3"; \
        expected_sha256="$4"; \
        archive="/tmp/${name}.tar.gz"; \
        curl -fsSL "$url" -o "$archive"; \
        test "$(wc -c < "$archive" | tr -d ' ')" = "$expected_bytes"; \
        echo "${expected_sha256}  ${archive}" | sha256sum -c -; \
        tar -xzf "$archive" -C /tmp; \
    }; \
    fetch_source \
        vs-placebo \
        "https://codeload.github.com/Lypheo/vs-placebo/tar.gz/${VS_PLACEBO_SOURCE_COMMIT}" \
        "${VS_PLACEBO_SOURCE_BYTES}" \
        "${VS_PLACEBO_SOURCE_SHA256}" && \
    fetch_source \
        libplacebo \
        "https://codeload.github.com/haasn/libplacebo/tar.gz/${LIBPLACEBO_SOURCE_COMMIT}" \
        "${LIBPLACEBO_SOURCE_BYTES}" \
        "${LIBPLACEBO_SOURCE_SHA256}" && \
    fetch_source \
        libdovi \
        "https://codeload.github.com/quietvoid/dovi_tool/tar.gz/refs/tags/libdovi-3.3.2" \
        "${LIBDOVI_SOURCE_BYTES}" \
        "${LIBDOVI_SOURCE_SHA256}" && \
    cp "/tmp/vs-placebo-${VS_PLACEBO_SOURCE_COMMIT}/COPYING" \
        /opt/media-runtime-licenses/vs-placebo-LGPL-2.1.txt && \
    cp "/tmp/libplacebo-${LIBPLACEBO_SOURCE_COMMIT}/LICENSE" \
        /opt/media-runtime-licenses/libplacebo-LGPL-2.1.txt && \
    cp "/tmp/dovi_tool-libdovi-3.3.2/LICENSE" \
        /opt/media-runtime-licenses/libdovi-MIT.txt && \
    mkdir -p /opt/media-runtime-libs /opt/media-runtime-provenance && \
    cp -a /usr/local/lib/liblsmash.so* /opt/media-runtime-libs/ && \
    cp -a /usr/local/lib/libffms2.so* /opt/media-runtime-libs/ && \
    printf '%s\n' \
        '{' \
        '  "schema_version": 1,' \
        '  "components": [' \
        '    {"name":"VapourSynth","version":"R78","source_commit":"c2f5751a412347f306eb7f6a5985dd9a719f3896","source_url":"https://codeload.github.com/vapoursynth/vapoursynth/tar.gz/c2f5751a412347f306eb7f6a5985dd9a719f3896","source_sha256":"fbf7986d96495abd106c714b01768671a8cab1d0c6a48feba0aa127bf5672753","source_bytes":637989,"license":"LGPL-2.1-or-later"},' \
        '    {"name":"L-SMASH","version":"commit 84740c5d960ab622f4c08b971dc59192bc27ef74","source_commit":"84740c5d960ab622f4c08b971dc59192bc27ef74","source_url":"https://codeload.github.com/l-smash/l-smash/tar.gz/84740c5d960ab622f4c08b971dc59192bc27ef74","source_sha256":"003d20595a3e66220a906c6bb351b8de973f2141fc24613db7701191f7219d5b","source_bytes":503390,"license":"ISC","selection_kind":"commit"},' \
        '    {"name":"L-SMASH-Works","version":"1296.0.0.0","source_commit":"a83318210c183c8ebbe703d975ffc76fb499ef07","source_url":"https://codeload.github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works/tar.gz/a83318210c183c8ebbe703d975ffc76fb499ef07","source_sha256":"6a135d7258376b461fdcabf5573c3a09eda5e3784f55fd0e8a1c3fac37a2a819","source_bytes":308701,"license":"ISC AND LGPL-2.1-or-later"},' \
        '    {"name":"FFMS2","version":"5.0","source_commit":"7ed5e4d039ca9a6236bd2ebdfdd656c4304fbe04","source_url":"https://codeload.github.com/FFMS/ffms2/tar.gz/7ed5e4d039ca9a6236bd2ebdfdd656c4304fbe04","source_sha256":"711e2330163700739c954c4f300d0dbbaed0c2360e0dc6debb29757640454d02","source_bytes":168105,"license":"MIT"},' \
        '    {"name":"Debian FFmpeg","version":"7:7.1.5-0+deb13u1","distribution":"trixie","selection_kind":"debian-package","license":"Debian-supported"},' \
        '    {"name":"vs-placebo","version":"2.0.4","source_ref":"2.0.4","source_commit":"3cfd23f257ecb62b0cbd81eaaca092e18ae8e579","source_url":"https://codeload.github.com/Lypheo/vs-placebo/tar.gz/3cfd23f257ecb62b0cbd81eaaca092e18ae8e579","source_sha256":"b1c3e6eab7e7c722aa1e5706aef70b5365f4a4c881b4573a6121e4c9572a8fbe","source_bytes":37902,"license":"LGPL-2.1-only","selection_kind":"tag"},' \
        '    {"name":"libplacebo","version":"commit a7a18af88ff0a17c04840dcb3246047bb6b46df3","source_commit":"a7a18af88ff0a17c04840dcb3246047bb6b46df3","source_url":"https://codeload.github.com/haasn/libplacebo/tar.gz/a7a18af88ff0a17c04840dcb3246047bb6b46df3","source_sha256":"ba0c8c011c19cb74bcee26646d2d6070447151da89a9abdd01c9034e768de8b2","source_bytes":873993,"license":"LGPL-2.1-or-later","selection_kind":"commit"},' \
        '    {"name":"libdovi","version":"3.3.2","source_ref":"libdovi-3.3.2","source_commit":"4fd2b2235c9f93582dd4a00e65ee34a07800afd7","source_url":"https://codeload.github.com/quietvoid/dovi_tool/tar.gz/refs/tags/libdovi-3.3.2","source_sha256":"8ccb1922d7dbb57bc4f2c15c10b90c462f7a5f292efe317c116db923728dd3f1","source_bytes":489628,"license":"MIT","selection_kind":"tag"}' \
        '  ]' \
        '}' \
        > /opt/media-runtime-provenance/SOURCES.json && \
    rm -rf \
        "/tmp/vs-placebo-${VS_PLACEBO_SOURCE_COMMIT}" \
        "/tmp/libplacebo-${LIBPLACEBO_SOURCE_COMMIT}" \
        /tmp/dovi_tool-libdovi-3.3.2 \
        /tmp/vs-placebo.tar.gz \
        /tmp/libplacebo.tar.gz \
        /tmp/libdovi.tar.gz

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13.14-slim-trixie@sha256:bf503bb2243c5aad0aa951544dd60d165f992646441d35dea90893703fc26251 AS runtime

ARG VAPOURSYNTH_VERSION=78
ARG VS_PLACEBO_VERSION=2.0.4
ARG VAPOURSYNTH_X86_64_WHEEL_SHA256=8e70b98c40ac69477a15f8ae0c551c2a4e182281986b5996853c7a01477ed477
ARG VAPOURSYNTH_AARCH64_WHEEL_SHA256=5368661393622fe9fa267409a5fbf7143d561b55dafdf6a500ef0fe38b285386
ARG VS_PLACEBO_X86_64_WHEEL_SHA256=d38796b739ae231e12e7b4f9449b3cb29cc4a5fa9cd50e8147fdd9a202797fff
ARG VS_PLACEBO_AARCH64_WHEEL_SHA256=eb025cb3f8d723eeaa64dc19b26fa1a0a05b948eb0cedeb8645680d9695ba97d
ARG DEBIAN_FFMPEG_PACKAGE_VERSION=7:7.1.5-0+deb13u1

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
    test "$(dpkg-query -W -f='${Version}' ffmpeg)" = "${DEBIAN_FFMPEG_PACKAGE_VERSION}" && \
    rm -rf /var/lib/apt/lists/*

# Copy staged native libraries as one directory so symbolic-link identity is
# preserved. Direct wildcard COPY turns versioned FFMS2 symlinks into duplicate
# regular files and makes ldconfig unable to verify the expected SONAME layout.
COPY --from=builder /opt/media-runtime-libs/ /usr/local/lib/
COPY --from=builder /opt/vapoursynth-extra-plugins/ /opt/vapoursynth-extra-plugins/
COPY --from=builder /opt/media-runtime-licenses/ /usr/local/share/licenses/frame-compare-media-runtime/
COPY --from=builder /opt/media-runtime-provenance/ /usr/local/share/frame-compare/media-runtime/

RUN ldconfig && \
    test -L /usr/local/lib/liblsmash.so && \
    test -L /usr/local/lib/libffms2.so && \
    python -m json.tool /usr/local/share/frame-compare/media-runtime/SOURCES.json >/dev/null

ENV VAPOURSYNTH_EXTRA_PLUGIN_PATH=/opt/vapoursynth-extra-plugins \
    LIBGL_ALWAYS_SOFTWARE=1 \
    FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT=18458c0987b2235d5db32638fb8ecebd0de7e050f0300636e3324b0eb7ac3dac \
    FRAME_COMPARE_RUNTIME_KIND=docker \
    FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED=1 \
    FRAME_COMPARE_FFMPEG_EXECUTABLE=/usr/bin/ffmpeg \
    FRAME_COMPARE_FFPROBE_EXECUTABLE=/usr/bin/ffprobe

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
