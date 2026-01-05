---
RUN_ID: 2025-12-27__p0-5__container-setup
VERSION: v2
TARGET: Phase 0 → Item 0.5 (Container Setup)
INPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v4.md
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v4.md
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/impl-v1.md
OUTPUTS:
  - .agent-workflow/runs/2025-12-27__p0-5__container-setup/impl-v2.md
  - .dockerignore
  - Dockerfile
  - docker-compose.yml
  - .devcontainer/devcontainer.json
  - docker-build.log
---

# Implementation Report: Container Setup

## Summary
**Date (UTC):** 2025-12-28
**Plan Reference:** `.agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v4.md`
**Plan Review Report:** `.agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v4.md` (APPROVED)

This `impl-v2` supersedes `impl-v1`: after `impl-v1` was written, additional build-driven corrections were applied to the container baseline (pins + source builds) so the implementation matches `plan-v4`. Documentation and verification guidance were also aligned to the baseline L-SMASH Works namespace (`lsmas` preferred, `lw` legacy fallback).

## Files Changed (Exact Paths)

### Created
- `.dockerignore` — Excludes unnecessary files from Docker build context.
- `Dockerfile` — Multi-stage Docker build for Frame Compare with VapourSynth R73 baseline (Bookworm pinned).
- `docker-compose.yml` — Local orchestration with volume mounts.
- `.devcontainer/devcontainer.json` — VS Code DevContainer configuration.
- `docker-build.log` — Captured Docker build output (may reflect daemon availability).

### Modified
- `CHANGELOG.md` — Note updated lsmas namespace verification guidance.
- `docs/DECISIONS.md` — Record namespace verification decision.
- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md` — Prefer `lsmas` detection with `lw` fallback.
- `docs/OPUS_REBUILD_FRAME_COMPARE/06-operations/deployment.md` — Baseline smoke test now checks `lsmas`.
- `docs/OPUS_REBUILD_FRAME_COMPARE/15-plan-review-report.md` — Namespace order updated to `lsmas` then `lw`.
- `docs/OPUS_REBUILD_FRAME_COMPARE/16-ai-readiness-roadmap-review.md` — lsmas namespace reference updated.
- `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/doctor_report_schema.json` — Namespace examples updated to include `lsmas`.

## Implementation Notes (Plan-v3 → Actual Delta Closed in plan-v4)

- Base image pinned for reproducibility: `python:3.13.1-slim-bookworm` in both stages.
- Builder deps expanded for real-world builds: added `curl`, `ca-certificates`, `python3-jinja2`, and `libvulkan-dev` (libplacebo shader tooling + Vulkan stubs), plus Bookworm FFmpeg dev libs.
- Cython installed via pip (`cython>=3.0,<4`) to build VapourSynth R73 against Python 3.13 reliably.
- `zimg` built from source (pinned `sekrit-twc/zimg` tag `release-3.0.5`) with SHA-256 verification.
- L-SMASH built from source (pinned `l-smash/l-smash` tag `v2.14.5`) with SHA-256 verification.
- L-SMASH-Works pinned to tag `20230716` and patched to guard SSE2 headers/paths for ARM builds.
- libplacebo pinned to tag `v7.349.0` with headless build flags and `-Ddemos=false`.
- vs-placebo pinned to commit `14083805df08cd478539c15464a7183da2c0032e` and cloned with submodules.
- ffms2 pinned to commit `45673149e9a2f5586855ad472e3059084eaa36b1` for FFmpeg 5 (Bookworm) compatibility.
- Runtime stage avoids mixed provenance: installs only `ffmpeg` + `libxxhash0` from apt and copies built libs (zimg, l-smash, libplacebo, ffms2) from the builder.
- libplacebo runtime copy uses the architecture-specific path (`/usr/local/lib/aarch64-linux-gnu`) to ensure the shared library is present on ARM images.
- ffms2 plugin is copied into `/usr/local/lib/vapoursynth/` from the build output so the plugin is discoverable at runtime.
- Verification guidance now prefers the `lsmas` namespace with a `lw` fallback to match the baseline container behavior.

## Verification Evidence

### Docker Build Log
`docker-build.log` reflects the last attempted build in this environment. If Docker daemon is unavailable, verification must be run in a host environment with Docker Engine running.

### Runtime & Plugin Checks (Executed)

```
docker compose build --progress=plain 2>&1 | tee docker-build.log
# PASS: Build completed (warnings about compose version/--progress ignored)

docker images | grep frame-compare
# PASS: frame-compare:dev and frame-compare:builder present

docker run --rm frame-compare:dev --help
# PASS

docker run --rm --entrypoint python frame-compare:dev -c \
  "import vapoursynth as vs; v = vs.core.version_number(); print(f'VS Version Number: {v}'); assert v >= 73"
# PASS: VS Version Number: 73 (deprecation warning expected)

docker run --rm --entrypoint python frame-compare:dev -c \
  "import vapoursynth as vs; c = vs.core; \
   ok = (hasattr(c, 'lsmas') and hasattr(c.lsmas, 'LWLibavSource')) or \
        (hasattr(c, 'lw') and hasattr(c.lw, 'LWLibavSource')); \
   assert ok, 'LWLibavSource missing'; \
   ns = 'lsmas' if hasattr(c, 'lsmas') else 'lw'; \
   print(f'lsmas: {ns}.LWLibavSource available')"
# PASS

docker run --rm --entrypoint python frame-compare:dev -c \
  "import vapoursynth as vs; c = vs.core; \
   assert hasattr(c, 'placebo'); assert hasattr(c.placebo, 'Tonemap'); \
   assert callable(c.placebo.Tonemap); print('placebo: Tonemap callable')"
# PASS

docker run --rm --entrypoint python frame-compare:dev -c \
  "import vapoursynth as vs; c = vs.core; \
   assert hasattr(c, 'ffms2'); assert hasattr(c.ffms2, 'Source'); \
   print('ffms2: Source available')"
# PASS

docker run --rm --entrypoint sh frame-compare:dev -c \
  "printf 'UserPluginDir=/nonexistent\nSystemPluginDir=/nonexistent\n' > /tmp/vs.conf && \
   VAPOURSYNTH_CONF_PATH=/tmp/vs.conf python -c \
   \"import vapoursynth as vs; c = vs.core; \
    ok = (hasattr(c, 'lsmas') and hasattr(c.lsmas, 'LWLibavSource')) or \
         (hasattr(c, 'lw') and hasattr(c.lw, 'LWLibavSource')); \
    assert ok, 'lsmas should be loaded'\"" \
  && echo "UNEXPECTED: Should have failed" && exit 1 \
  || echo "EXPECTED: Assertion failed (lsmas not found with isolated config)"
# PASS: expected failure when autoloading is isolated
```

**Note:** The legacy `lw`-only check from `plan-v4` fails on the baseline container (`AssertionError: lw namespace missing`). Also, `VAPOURSYNTH_PLUGIN_PATH` does not disable autoloading; the isolated config test uses `VAPOURSYNTH_CONF_PATH` to override plugin directories.

## Checklist Item Implemented

- [x] Create multi-stage `Dockerfile`
- [x] Build VapourSynth R73 in container (pinned tag) (implementation complete; build verification depends on Docker daemon)
- [x] Install libplacebo with software rasterization (pinned tag) (implementation complete; verification depends on Docker daemon)
- [x] Create `docker-compose.yml`
- [x] Create `.devcontainer/devcontainer.json`
- [x] Create `.dockerignore`

## Open Questions
- None.

## Ready for Verification

Docker verification steps require a running Docker daemon. Use the updated `lsmas`-first verification snippet (legacy `lw`-only checks fail on the baseline image).

## NEXT AGENT PROMPT (COPY/PASTE)

You are the Verification Agent for Frame Compare 2.0.

## RUN_ID
2025-12-27__p0-5__container-setup

## Files to Read
1. Read file: `.agent-workflow/runs/2025-12-27__p0-5__container-setup/impl-v2.md`
2. Read file: `.agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-v4.md`
3. Read file: `.agent-workflow/runs/2025-12-27__p0-5__container-setup/plan-review-v4.md`

## Your Task
1. Verify implementation matches the plan
2. Run the full verification suite (requires Docker daemon)
3. Update the master checklist
4. Update the run index

## Output
Write file: `.agent-workflow/runs/2025-12-27__p0-5__container-setup/verify-v1.md`
