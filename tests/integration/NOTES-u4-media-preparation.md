# U4 media preparation cost

Measured on 2026-10-15 on macOS arm64 / Docker Desktop (server 29.8.2), using
Linux arm64 FFmpeg 7.1.5, VapourSynth R81 and L-SMASH-Works 1310. Each row is one
observation, not a statistical benchmark. The workload is the deterministic
10-minute U4 media matrix and the focused `replacement-4` acceptance case.

The unchanged baseline is commit `3051550054fb19050b35c7743b9b4c780675262a`.
Its acceptance source SHA-256 is
`d5a6cde1a9e3e98150b79ce428e5c7b235632f39cf0c423caba868f5f45b27a8`.
The initial test-runtime image is
`sha256:e341b39aed3c6047146237b388b4adb75f891100a3ea441dfbfa84c8bd7db666`.
All containers use the worktree-scoped Compose project `frame-compare-p11-a638`,
unique `frame-compare:p11-a638-{test,run}` image tags, and this worktree's
`generated/` bind mount. No other checkout's media/cache/artifacts are used. Docker exposed 10 CPUs and
10,152,927,232 bytes of memory.

| Run | Created / reused | Preparation seconds | Pytest setup / call seconds | Whole command seconds |
| --- | --- | --- | --- | --- |
| Baseline cold, focused | 37 / 0 | 332.62 (fixture setup) | 332.62 / 9.00 | 348.038 |
| Baseline populated cache, assertion edit | 37 / 0 | 294.91 (fixture setup) | 294.91 / 5.26 | 302.987 |
| New cold, focused | 2 / 0 | 11.032 (recipe sum) | 0.08 / 18.92 | 20.689 |
| New populated cache, assertion edit | 0 / 2 | 0.000149 (recipe sum) | 0.11 / 4.71 | 6.727 |
| Real recipe edit, cold focused | 2 / 0 | 11.397 (recipe sum) | 0.08 / 15.35 | 17.028 |
| Real recipe edit, cold full matrix | 37 / 0 | 294.781 (recipe sum) | 294.89 / 5.47 | 301.757 |
| Restored recipes, canonical cold full gate | 37 / 0 | 355.238 (recipe sum) | Entire pytest selection: 580.38 | 624.230 |

New focused creation is exactly `reference` and `replacement-4`; the assertion edit
reuses those same two files under the same key. Lazy generation is charged inside
the focused test call, so its small setup time alone is not a preparation comparison.
The observed focused whole-command cost fell from 348.038 to 20.689 seconds; these
single observations do not establish a general runtime speedup. Full cold generation
remains a 37-file workload, with 355.238 seconds of materialization in the 10-worker
gate.

The canonical gate ran against implementation commit
`d3250f4edf817fa46b24cee7475e4695194dd8b5`: **295 passed in 580.38 seconds, zero
skips**, followed by successful production-tooling, actual application-run, and
host-generated-mount proofs. The test and production image IDs were respectively
`sha256:181a2e888df90cf41f24d518d3faee887b328a4ec8c59f7f0dc21f04819a4b53`
and `sha256:ef593b4365903413e7931a01cbb82f7d6e62b065bd50f174c8fbe5f0806f4030`.
The real U4 worker record is
`generated/e2e/run.RTJ1wD/u4-media-gw0-785750887267421694638e8b8703726b.json`.
The full gate also emits small stats records for injected cache-test sessions;
select the real matrix record by the restored recipe/FFmpeg key below. Its cache
contained exactly 37 `.mkv` files and no adjacent decoder-index or temporary files.

Rebase provenance (2026-10-15): the measured implementation commit above was
replayed as `e4f502a256b8fc5195b7ea7f4bac4cc6cd9d4bb4` onto integrated base
`698095cdbcb23ae781c898c19d4a48098271aa36`. Recipe/store/cache-test/verifier source
is byte-identical to the measured P11 implementation; all 21 extracted writer/graph
functions also match the current integrated base. The U4 acceptance module retains
P5's `make_run_request(root=root)` acquired-config builder. Its remaining executable
AST, phase/cache assertions, special-reference pairing, and scenarios match the
measured module after normalizing that builder/import migration.

The source/key/image identities and measurements below describe the **original
measurement sources**, including the original acceptance-module hash. They are not
relabeled as a run against the rebased source. The integrated base also changes P6
alignment resolution/publication and P8 applied-tonemap/report contracts; the old
295-pass Docker result does not establish those combined runtime contracts. On the
rebased source, 29 cache/workflow/onboarding cases and 74 request/phase/resolution
cases passed, as did repository lint/format/type checks and the strict docs build.
Current-source Docker/media acceptance, the full native gate, and browser acceptance
remain deferred to the integration owner; no new Docker run was performed for this
rebase. The original local media cache, images, and evidence remain retained.

Raw logs are retained locally in `generated/p11-measurements/{baseline-cold,
baseline-assertion,new-cold,new-assertion,recipe-focused,recipe-full,full-gate}.log`.
Focused row JSON lives under `generated/e2e/p11-<row>/`; these generated artifacts
are deliberately excluded from Git. The reproducible commands and source identities
are retained here.

Baseline counts come from complete `.mkv` files in the published key directory,
with a previously absent key and pruning of the prior key after publication. The
baseline has no worker stats: pytest's fixture setup duration measures preparation.
New counts and per-recipe time come from worker-emitted `u4-media-*.json` under each
row's `FRAME_COMPARE_E2E_ARTIFACTS`. Per-recipe seconds sum direct materialization
work, excluding test execution; pytest setup/call and whole-command elapsed times
are separate observations. No repeated warm-up or averaging was performed.

The temporary assertion edit appends `assert _FPS == 24` to the acceptance module.
The temporary real recipe edit changes `_write_media`'s encoder CRF from 18 to 19.
Both edits are restored before the final cold full gate. Edited focused and edited
full rows each start without that key, so their created counts are independently
comparable. The full gate also starts cold. Clearing is limited to directories
inside this worktree's `generated/test-media-cache/test_alignment_u4_acceptance`,
with no active session; `.verifier.lock` is retained.

Commands follow the existing Docker measurement route, with a local Compose
override selecting the unique image tags:

```bash
# The override contains only services.<test/run>.image; production source is unchanged.
docker compose -p frame-compare-p11-a638 \
  -f docker-compose.yml -f generated/p11-compose.yml \
  run --rm --no-deps \
  -e FRAME_COMPARE_U4_MEDIA_FULL=0 \
  -e FRAME_COMPARE_E2E_ARTIFACTS=/workspace/generated/e2e/p11-ROW \
  frame-compare-test -lc '\
    export LIBGL_ALWAYS_SOFTWARE=1 PATH="/home/framecompare/.local/bin:$PATH" \
      VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json \
      FRAME_COMPARE_TEST_MEDIA_CACHE=/workspace/generated/test-media-cache; \
    time pytest -q tests/integration/test_alignment_u4_acceptance.py \
      -k replacement-4 --durations=0'

# Independent edited-full measurement: same focused assertion, all media prepared up front.
# Use FRAME_COMPARE_U4_MEDIA_FULL=1 in the preceding command after removing its key.

# Canonical cold full gate, including image builds and runtime/production proofs:
COMPOSE_PROJECT_NAME=frame-compare-p11-a638 \
COMPOSE_FILE="$PWD/docker-compose.yml:$PWD/generated/p11-compose.yml" \
  bash tools/verify_docker_integration.sh
```

The canonical full gate passes `FRAME_COMPARE_U4_MEDIA_FULL=1` into its worker
container. A focused `--pytest-path` invocation omits it. The acceptance module
retains `xdist_group("alignment-u4")`; the independent cache tests need no native
runtime or serialization group.

| Source/input | SHA-256 |
| --- | --- |
| Baseline after assertion edit | `4f15c1d27f6d67369c19a5ecb6e8082e9ae95b47689b180b0e5eddec35f13895` |
| Migrated acceptance module (restored) | `7248fb713470c725c97c4e656dcaa4dc96451fd256dde650ba590b59195966f8` |
| Migrated acceptance after assertion edit | `2ad5ee61cb79ab04c428595c3dc5d19523debec98487de92e438528a9c3f9030` |
| Recipe module (restored) | `a50bffa02712e53bdf5e1276b22e069de748e4bd2c1a354bd87bddd6a100f2af` |
| Recipe module after CRF 18 → 19 | `9b12d090309b217588188d98b6624ddbccd05077aae405f5c133b5fcf09c5582` |
| Store module | `3504d8e29679a7a82706faddcb53973c0956d74ace3a5d8097a434047529fbec` |
| Complete FFmpeg version stdout | `e3379e95264b2189b027f0fae31698e1f6ce48dbac76548a3cb6fc65d1cc7f87` |

Cache keys:

- Baseline: `a47b0f28aa8e6701a7b0590983fdfff4ceb2b96c2ad193c58c39c148f03552e8`
- Baseline assertion edit: `3991646a06b0cd1dde31125fef2ae414838543724e8b3e651531fe0f2a6621f6`
- New cold/assertion/full: `f1578a121e841c9bbb3c5e704c1becafb390187a31fbec723feda86da2354884`
- Recipe edit focused/full: `8047afdbdba71b39230388cd206f36a2412631120bfa80666197ffec8241e84b`

Complete `ffmpeg -version` output used for every cache key in these measurements:

```text
ffmpeg version 7.1.5-0+deb13u1 Copyright (c) 2000-2026 the FFmpeg developers
built with gcc 14 (Debian 14.2.0-19)
configuration: --prefix=/usr --extra-version=0+deb13u1 --toolchain=hardened --libdir=/usr/lib/aarch64-linux-gnu --incdir=/usr/include/aarch64-linux-gnu --arch=arm64 --enable-gpl --disable-stripping --disable-libmfx --disable-omx --enable-gnutls --enable-libaom --enable-libass --enable-libbs2b --enable-libcdio --enable-libcodec2 --enable-libdav1d --enable-libflite --enable-libfontconfig --enable-libfreetype --enable-libfribidi --enable-libglslang --enable-libgme --enable-libgsm --enable-libharfbuzz --enable-libmp3lame --enable-libmysofa --enable-libopenjpeg --enable-libopenmpt --enable-libopus --enable-librubberband --enable-libshine --enable-libsnappy --enable-libsoxr --enable-libspeex --enable-libtheora --enable-libtwolame --enable-libvidstab --enable-libvorbis --enable-libvpx --enable-libwebp --enable-libx265 --enable-libxml2 --enable-libxvid --enable-libzimg --enable-openal --enable-opencl --enable-opengl --disable-sndio --disable-libvpl --enable-libdc1394 --enable-libdrm --enable-libiec61883 --enable-chromaprint --enable-frei0r --enable-ladspa --enable-libbluray --enable-libcaca --enable-libdvdnav --enable-libdvdread --enable-libjack --enable-libpulse --enable-librabbitmq --enable-librist --enable-libsrt --enable-libssh --enable-libsvtav1 --enable-libx264 --enable-libzmq --enable-libzvbi --enable-lv2 --enable-sdl2 --enable-libplacebo --enable-librav1e --enable-pocketsphinx --enable-librsvg --enable-libjxl --enable-shared
libavutil      59. 39.100 / 59. 39.100
libavcodec     61. 19.101 / 61. 19.101
libavformat    61.  7.103 / 61.  7.103
libavdevice    61.  3.100 / 61.  3.100
libavfilter    10.  5.100 / 10.  5.100
libswscale      8.  3.100 /  8.  3.100
libswresample   5.  3.100 /  5.  3.100
libpostproc    58.  3.100 / 58.  3.100
```
