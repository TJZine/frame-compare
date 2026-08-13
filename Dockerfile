# ─────────────────────────────────────────────────────────────────────────────
# Stage 0: Pinned Python dependency tooling
# ─────────────────────────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:0.12.2@sha256:069a51314a7bb6031777a9273205fe1b0b19e914ef418207d1338b268df641dd AS uv

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Build supplemental VapourSynth plugins
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13.14-slim-trixie@sha256:bf503bb2243c5aad0aa951544dd60d165f992646441d35dea90893703fc26251 AS builder

# Deterministic media-runtime pins. Every Git checkout verifies both the exact
# commit and a content-derived digest of the complete tracked source tree.
ARG VAPOURSYNTH_VERSION=79
ARG VAPOURSYNTH_SOURCE_COMMIT=acabf605b2205b32d65859bb2736405719d2fafd
ARG VAPOURSYNTH_SOURCE_TREE_SHA256=f7c7081a875dbb07487ed94a819385228794ef106d042949313a9ed71a655527
ARG VAPOURSYNTH_X86_64_WHEEL_SHA256=6f1e37f0ed8eb73e61c3c231fd7f7a0f7acfa893e98d026686e9c81e52c9ce06
ARG VAPOURSYNTH_AARCH64_WHEEL_SHA256=50d031d07b1839ba362cf314e212edb0760c7ca2a7625a051a0bcbf22aaf9d1c
ARG LSMASH_COMMIT=84740c5d960ab622f4c08b971dc59192bc27ef74
ARG LSMASH_SOURCE_TREE_SHA256=b1553e40907e57240fd19a08642b3bc548dbdeda3750948ebbc1c5634af901b7
ARG OBUPARSE_COMMIT=a67fcab9cd9d56c866a7a860f8c4aeb91b8817e8
ARG OBUPARSE_SOURCE_TREE_SHA256=f82de7a5f007a4e89441e7ff4b470a00eddc4dfedb22faa46f633acfeefde178
ARG LSMASH_WORKS_COMMIT=a83318210c183c8ebbe703d975ffc76fb499ef07
ARG LSMASH_WORKS_SOURCE_TREE_SHA256=7845a6a6d823046c6b0bbe617ae88e304ee117f466961aabceea931831d8f9e3
ARG FFMS2_COMMIT=7ed5e4d039ca9a6236bd2ebdfdd656c4304fbe04
ARG FFMS2_SOURCE_TREE_SHA256=5be86d5f8f103f8e0b25aaed0b69b7afc06f1b6cd548a6c81160fcd14ea6e8d7
ARG VS_PLACEBO_SOURCE_COMMIT=3cfd23f257ecb62b0cbd81eaaca092e18ae8e579
ARG VS_PLACEBO_SOURCE_TREE_SHA256=beb830744f1fa1702eb64cfe8bdaf5780bb3501f9c48901df24ab112a406a30a
ARG LIBPLACEBO_SOURCE_COMMIT=a7a18af88ff0a17c04840dcb3246047bb6b46df3
ARG LIBPLACEBO_SOURCE_TREE_SHA256=bdbe17582c081e107e1a66c44d5f01aa856a157aa124660d662221848e88eda7
ARG LIBDOVI_SOURCE_COMMIT=4fd2b2235c9f93582dd4a00e65ee34a07800afd7
ARG LIBDOVI_SOURCE_TREE_SHA256=e16dfb68270fc5b8610e2f1ae38b0b1051d8e7d03dd4b98a2f22f0e1fd09de26
ARG DEBIAN_FFMPEG_PACKAGE_VERSION=7:7.1.5-0+deb13u1

RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    build-essential \
    ca-certificates \
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
        test "$(dpkg-query -W -f='${Version}' "$package")" = "${DEBIAN_FFMPEG_PACKAGE_VERSION}" \
            || { echo "unexpected $package version" >&2; exit 1; }; \
    done \
    && rm -rf /var/lib/apt/lists/*

COPY tools/checkout_source_commit.sh /usr/local/bin/checkout_source_commit.sh

RUN printf '%s\n' \
        "vapoursynth==${VAPOURSYNTH_VERSION} --hash=sha256:${VAPOURSYNTH_X86_64_WHEEL_SHA256} --hash=sha256:${VAPOURSYNTH_AARCH64_WHEEL_SHA256}" \
        > /tmp/vapoursynth-wheel-requirements.txt && \
    python -m pip install --no-cache-dir --require-hashes --only-binary=:all: \
        -r /tmp/vapoursynth-wheel-requirements.txt && \
    bash /usr/local/bin/checkout_source_commit.sh \
        https://github.com/vapoursynth/vapoursynth.git \
        "${VAPOURSYNTH_SOURCE_COMMIT}" \
        "${VAPOURSYNTH_SOURCE_TREE_SHA256}" \
        /tmp/vapoursynth-src && \
    vs_include_dir="$(python -c 'import vapoursynth; print(vapoursynth.get_include())')" && \
    test -f /tmp/vapoursynth-src/include/VapourSynth.h && \
    test -f /tmp/vapoursynth-src/include/VSHelper.h && \
    test -f /tmp/vapoursynth-src/include/VapourSynth4.h && \
    test -f /tmp/vapoursynth-src/include/VSHelper4.h && \
    cp /tmp/vapoursynth-src/include/VapourSynth.h "${vs_include_dir}/" && \
    cp /tmp/vapoursynth-src/include/VSHelper.h "${vs_include_dir}/" && \
    cp /tmp/vapoursynth-src/include/VapourSynth4.h "${vs_include_dir}/" && \
    cp /tmp/vapoursynth-src/include/VSHelper4.h "${vs_include_dir}/" && \
    mkdir -p /opt/media-runtime-licenses && \
    cp /tmp/vapoursynth-src/COPYING.LESSER \
        /opt/media-runtime-licenses/VapourSynth-LGPL-2.1.txt && \
    rm -rf /tmp/vapoursynth-src

ENV PKG_CONFIG_PATH=/usr/local/lib/python3.13/site-packages/vapoursynth/pkgconfig
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.13/site-packages/vapoursynth

WORKDIR /build

# The selected L-SMASH commit includes obuparse.h and links -lobuparse. Build
# only OBUParse's shared library so the runtime carries its SONAME and symlink,
# without an unused static archive.
RUN bash /usr/local/bin/checkout_source_commit.sh \
        https://github.com/HomeOfAviSynthPlusEvolution/obuparse.git \
        "${OBUPARSE_COMMIT}" \
        "${OBUPARSE_SOURCE_TREE_SHA256}" \
        /build/obuparse && \
    cd /build/obuparse && \
    make -j"$(nproc)" libobuparse.so && \
    make install-shared && \
    test -f /usr/local/lib/libobuparse.so.2 && \
    test -L /usr/local/lib/libobuparse.so && \
    cp LICENSE /opt/media-runtime-licenses/OBUParse-LICENSE.txt && \
    ldconfig && \
    cd /build && \
    rm -rf /build/obuparse

# Build the exact L-SMASH commit tested by L-SMASH-Works 1296.
# This commit is intentionally not described as a formal L-SMASH release.
RUN bash /usr/local/bin/checkout_source_commit.sh \
        https://github.com/l-smash/l-smash.git \
        "${LSMASH_COMMIT}" \
        "${LSMASH_SOURCE_TREE_SHA256}" \
        /build/l-smash && \
    cd /build/l-smash && \
    ./configure --prefix=/usr/local --disable-static && \
    make -j"$(nproc)" && \
    make install && \
    mkdir -p /opt/media-runtime-licenses && \
    cp LICENSE /opt/media-runtime-licenses/L-SMASH-LICENSE.txt && \
    ldconfig && \
    cd /build && \
    rm -rf /build/l-smash

# Build L-SMASH-Works 1296 against the R79 API R4.2 wheel headers and
# Debian Trixie's runtime-matched FFmpeg development libraries. Upstream's
# Meson path is deprecated, but remains the narrow VapourSynth-only build and
# avoids pulling unrelated optional dependencies into the runtime baseline.
RUN bash /usr/local/bin/checkout_source_commit.sh \
        https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works.git \
        "${LSMASH_WORKS_COMMIT}" \
        "${LSMASH_WORKS_SOURCE_TREE_SHA256}" \
        /build/l-smash-works && \
    cd /build/l-smash-works/VapourSynth && \
    perl -0pi -e '\
        my $count = s/  install: true,\n  install_dir: join_paths\(vapoursynth_dep\.get_pkgconfig_variable\(\x27libdir\x27\), \x27vapoursynth\x27\),\n/  install: false,\n/g; \
        die "expected L-SMASH-Works Meson install block exactly once\\n" unless $count == 1; \
    ' meson.build && \
    meson setup build --buildtype=release && \
    ninja -C build && \
    mkdir -p /opt/vapoursynth-extra-plugins/lsmas && \
    cp build/libvslsmashsource.so /opt/vapoursynth-extra-plugins/lsmas/ && \
    printf '[VapourSynth Manifest V1]\nlibvslsmashsource\n' \
        > /opt/vapoursynth-extra-plugins/lsmas/manifest.vs && \
    cp LICENSE /opt/media-runtime-licenses/L-SMASH-Works-VapourSynth-LICENSE.txt && \
    cd /build && \
    rm -rf /build/l-smash-works

# Rebuild the latest stable FFMS2 release against the selected VapourSynth
# headers and the same Debian FFmpeg ABI used by the runtime image.
RUN bash /usr/local/bin/checkout_source_commit.sh \
        https://github.com/FFMS/ffms2.git \
        "${FFMS2_COMMIT}" \
        "${FFMS2_SOURCE_TREE_SHA256}" \
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
        > /opt/vapoursynth-extra-plugins/ffms2/manifest.vs && \
    cp COPYING /opt/media-runtime-licenses/FFMS2-COPYING.txt && \
    cd /build && \
    rm -rf /build/ffms2

# Preserve corresponding-source and license provenance for wheel-bundled
# vs-placebo dependencies. These trees are not used to build the wheels; they
# document the exact tracked sources selected by the upstream 2.0.4 release.
RUN bash /usr/local/bin/checkout_source_commit.sh \
        https://github.com/Lypheo/vs-placebo.git \
        "${VS_PLACEBO_SOURCE_COMMIT}" \
        "${VS_PLACEBO_SOURCE_TREE_SHA256}" \
        /tmp/vs-placebo-src && \
    bash /usr/local/bin/checkout_source_commit.sh \
        https://github.com/haasn/libplacebo.git \
        "${LIBPLACEBO_SOURCE_COMMIT}" \
        "${LIBPLACEBO_SOURCE_TREE_SHA256}" \
        /tmp/libplacebo-src && \
    bash /usr/local/bin/checkout_source_commit.sh \
        https://github.com/quietvoid/dovi_tool.git \
        "${LIBDOVI_SOURCE_COMMIT}" \
        "${LIBDOVI_SOURCE_TREE_SHA256}" \
        /tmp/libdovi-src && \
    cp /tmp/vs-placebo-src/COPYING \
        /opt/media-runtime-licenses/vs-placebo-LGPL-2.1.txt && \
    cp /tmp/libplacebo-src/LICENSE \
        /opt/media-runtime-licenses/libplacebo-LGPL-2.1.txt && \
    cp /tmp/libdovi-src/LICENSE \
        /opt/media-runtime-licenses/libdovi-MIT.txt && \
    mkdir -p /opt/media-runtime-libs /opt/media-runtime-provenance && \
    cp -a /usr/local/lib/libobuparse.so* /opt/media-runtime-libs/ && \
    cp -a /usr/local/lib/liblsmash.so* /opt/media-runtime-libs/ && \
    cp -a /usr/local/lib/libffms2.so* /opt/media-runtime-libs/ && \
    printf '%s\n' \
        '{' \
        '  "schema_version": 2,' \
        '  "components": [' \
        "    {\"name\":\"VapourSynth\",\"version\":\"R${VAPOURSYNTH_VERSION}\",\"source_commit\":\"${VAPOURSYNTH_SOURCE_COMMIT}\",\"source_url\":\"https://github.com/vapoursynth/vapoursynth.git\",\"source_tree_sha256\":\"${VAPOURSYNTH_SOURCE_TREE_SHA256}\",\"license\":\"LGPL-2.1-or-later\"}," \
        "    {\"name\":\"OBUParse\",\"version\":\"commit ${OBUPARSE_COMMIT}\",\"source_commit\":\"${OBUPARSE_COMMIT}\",\"source_url\":\"https://github.com/HomeOfAviSynthPlusEvolution/obuparse.git\",\"source_tree_sha256\":\"${OBUPARSE_SOURCE_TREE_SHA256}\",\"license\":\"ISC\",\"selection_kind\":\"commit\",\"linkage\":\"shared\",\"soname\":\"libobuparse.so.2\"}," \
        "    {\"name\":\"L-SMASH\",\"version\":\"commit ${LSMASH_COMMIT}\",\"source_commit\":\"${LSMASH_COMMIT}\",\"source_url\":\"https://github.com/l-smash/l-smash.git\",\"source_tree_sha256\":\"${LSMASH_SOURCE_TREE_SHA256}\",\"license\":\"ISC\",\"selection_kind\":\"commit\"}," \
        "    {\"name\":\"L-SMASH-Works\",\"version\":\"1296.0.0.0\",\"source_commit\":\"${LSMASH_WORKS_COMMIT}\",\"source_url\":\"https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works.git\",\"source_tree_sha256\":\"${LSMASH_WORKS_SOURCE_TREE_SHA256}\",\"license\":\"ISC AND LGPL-2.1-or-later\"}," \
        "    {\"name\":\"FFMS2\",\"version\":\"5.0\",\"source_commit\":\"${FFMS2_COMMIT}\",\"source_url\":\"https://github.com/FFMS/ffms2.git\",\"source_tree_sha256\":\"${FFMS2_SOURCE_TREE_SHA256}\",\"license\":\"MIT\"}," \
        "    {\"name\":\"Debian FFmpeg\",\"version\":\"${DEBIAN_FFMPEG_PACKAGE_VERSION}\",\"distribution\":\"trixie\",\"selection_kind\":\"debian-package\",\"license\":\"GPL-2.0-or-later\",\"license_path\":\"/usr/local/share/licenses/frame-compare-media-runtime/Debian-FFmpeg-copyright\"}," \
        "    {\"name\":\"vs-placebo\",\"version\":\"2.0.4\",\"source_ref\":\"2.0.4\",\"source_commit\":\"${VS_PLACEBO_SOURCE_COMMIT}\",\"source_url\":\"https://github.com/Lypheo/vs-placebo.git\",\"source_tree_sha256\":\"${VS_PLACEBO_SOURCE_TREE_SHA256}\",\"license\":\"LGPL-2.1-only\",\"selection_kind\":\"tag\"}," \
        "    {\"name\":\"libplacebo\",\"version\":\"commit ${LIBPLACEBO_SOURCE_COMMIT}\",\"source_commit\":\"${LIBPLACEBO_SOURCE_COMMIT}\",\"source_url\":\"https://github.com/haasn/libplacebo.git\",\"source_tree_sha256\":\"${LIBPLACEBO_SOURCE_TREE_SHA256}\",\"license\":\"LGPL-2.1-or-later\",\"selection_kind\":\"commit\"}," \
        "    {\"name\":\"libdovi\",\"version\":\"3.3.2\",\"source_ref\":\"libdovi-3.3.2\",\"source_commit\":\"${LIBDOVI_SOURCE_COMMIT}\",\"source_url\":\"https://github.com/quietvoid/dovi_tool.git\",\"source_tree_sha256\":\"${LIBDOVI_SOURCE_TREE_SHA256}\",\"license\":\"MIT\",\"selection_kind\":\"tag\"}" \
        '  ]' \
        '}' \
        > /opt/media-runtime-provenance/SOURCES.json && \
    rm -rf \
        /tmp/vs-placebo-src \
        /tmp/libplacebo-src \
        /tmp/libdovi-src

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.13.14-slim-trixie@sha256:bf503bb2243c5aad0aa951544dd60d165f992646441d35dea90893703fc26251 AS runtime

ARG VAPOURSYNTH_VERSION=79
ARG VS_PLACEBO_VERSION=2.0.4
ARG VAPOURSYNTH_X86_64_WHEEL_SHA256=6f1e37f0ed8eb73e61c3c231fd7f7a0f7acfa893e98d026686e9c81e52c9ce06
ARG VAPOURSYNTH_AARCH64_WHEEL_SHA256=50d031d07b1839ba362cf314e212edb0760c7ca2a7625a051a0bcbf22aaf9d1c
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
    mkdir -p /usr/local/share/licenses/frame-compare-media-runtime && \
    cp /usr/share/doc/ffmpeg/copyright \
        /usr/local/share/licenses/frame-compare-media-runtime/Debian-FFmpeg-copyright && \
    rm -rf /var/lib/apt/lists/*

# Copy staged native libraries as one directory so symbolic-link identity is
# preserved. Direct wildcard COPY turns versioned FFMS2 symlinks into duplicate
# regular files and makes ldconfig unable to verify the expected SONAME layout.
COPY --from=builder /opt/media-runtime-libs/ /usr/local/lib/
COPY --from=builder /opt/vapoursynth-extra-plugins/ /opt/vapoursynth-extra-plugins/
COPY --from=builder /opt/media-runtime-licenses/ /usr/local/share/licenses/frame-compare-media-runtime/
COPY --from=builder /opt/media-runtime-provenance/ /usr/local/share/frame-compare/media-runtime/

RUN ldconfig && \
    test -L /usr/local/lib/libobuparse.so && \
    test -f /usr/local/lib/libobuparse.so.2 && \
    test -L /usr/local/lib/liblsmash.so && \
    test -L /usr/local/lib/libffms2.so && \
    python -m json.tool /usr/local/share/frame-compare/media-runtime/SOURCES.json >/dev/null

ENV VAPOURSYNTH_EXTRA_PLUGIN_PATH=/opt/vapoursynth-extra-plugins \
    LD_LIBRARY_PATH=/home/framecompare/.local/lib/python3.13/site-packages/vapoursynth:/usr/local/lib \
    LIBGL_ALWAYS_SOFTWARE=1 \
    FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT=84311d579727ab34a84ebedeb598e3a7abd599cae9f6d8d51f888aa61ea7580a \
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
# Stage 3: Hash-locked integration-test runner
FROM runtime AS test-runtime

RUN uv export --frozen --only-group docker-test --no-emit-project --format requirements.txt \
        --output-file /tmp/requirements.docker-test.lock.txt && \
    python -m pip install --no-cache-dir --user --require-hashes \
        -r /tmp/requirements.docker-test.lock.txt

# ─────────────────────────────────────────────────────────────────────────────
# Stage 4: Development container
FROM runtime AS devcontainer

USER root
RUN install -d -m 0777 -o framecompare -g framecompare /workspace/frame-compare/.venv
USER framecompare
WORKDIR /workspace/frame-compare

# ─────────────────────────────────────────────────────────────────────────────
# Stage 5: Optional Linux X11/VSPreview GUI runtime
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

USER root
RUN rm -f /usr/local/bin/uv /usr/local/bin/uvx
USER framecompare

# Keep the default image target headless and CI-safe. The gui-linux target above is
# opt-in via docker-compose.gui-linux.yml and should not become the implicit result
# of `docker build .` or default compose builds.
FROM runtime AS default-runtime

USER root
RUN rm -f /usr/local/bin/uv /usr/local/bin/uvx
USER framecompare
