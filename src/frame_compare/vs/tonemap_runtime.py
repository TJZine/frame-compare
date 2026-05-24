"""libplacebo runtime probe helpers for HDR tonemapping."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from collections.abc import Callable
from dataclasses import dataclass

import structlog

log = structlog.get_logger()

_REQUIRE_LIBPLACEBO_ENV = "FRAME_COMPARE_REQUIRE_LIBPLACEBO"
_DISABLE_LIBPLACEBO_ENV = "FRAME_COMPARE_DISABLE_LIBPLACEBO"
_LIBPLACEBO_PROBE_ENV = "FRAME_COMPARE_LIBPLACEBO_PROBE"
_LIBPLACEBO_PROBE_TIMEOUT_SECONDS = 5.0


@dataclass(slots=True)
class LibplaceboRuntimeState:
    """Process-owned state for the libplacebo runtime probe."""

    probe_result: bool | None = None


def probe_libplacebo_runtime() -> bool:
    """Run the subprocess probe to check if libplacebo is usable."""
    probe_script = textwrap.dedent(
        """
        import vapoursynth as vs

        core = vs.core
        if not hasattr(core, "placebo") or not hasattr(core.placebo, "Tonemap"):
            raise SystemExit(2)

        clip = core.std.BlankClip(
            width=16,
            height=16,
            format=vs.RGB48,
            length=1,
            color=[32768, 32768, 32768],
        )
        clip = clip.std.SetFrameProps(
            _Matrix=0,
            _ColorRange=0,
            _Transfer=16,
            _Primaries=9,
        )
        out = core.placebo.Tonemap(
            clip,
            src_max=1000,
            dst_max=203,
            tone_mapping_function=2,
            dst_csp=0,
            dst_prim=1,
            src_csp=1,
        )
        _ = out.get_frame(0)
        """
    )
    env = os.environ.copy()
    env[_LIBPLACEBO_PROBE_ENV] = "1"

    try:
        # argv uses sys.executable and a static probe script; shell=True is never used.
        result = subprocess.run(  # nosec B603
            [sys.executable, "-c", probe_script],
            env=env,
            capture_output=True,
            text=True,
            timeout=_LIBPLACEBO_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning(
            "libplacebo_probe_failed_disabling",
            error=f"{type(exc).__name__}: {exc}",
        )
        return False

    if result.returncode == 0:
        return True

    log.warning(
        "libplacebo_probe_unusable_disabling",
        returncode=result.returncode,
        stdout=result.stdout.strip()[-400:],
        stderr=result.stderr.strip()[-400:],
    )
    return False


def libplacebo_runtime_override() -> bool | None:
    """Return a per-call runtime override, if one is set."""
    if os.environ.get(_REQUIRE_LIBPLACEBO_ENV) == "1":
        return True
    if os.environ.get(_DISABLE_LIBPLACEBO_ENV) == "1":
        return False
    if os.environ.get(_LIBPLACEBO_PROBE_ENV) == "1":
        return True
    return None


def cached_libplacebo_runtime_probe(
    state: LibplaceboRuntimeState,
    probe: Callable[[], bool],
) -> bool:
    """Return the cached subprocess probe result for this process lifetime."""
    cached_result = state.probe_result
    if cached_result is not None:
        return cached_result

    probe_result = probe()
    state.probe_result = probe_result
    return probe_result


def libplacebo_runtime_usable(
    state: LibplaceboRuntimeState,
    probe: Callable[[], bool],
) -> bool:
    """Return whether libplacebo is safe to call in this process.

    Plugin presence is not sufficient on all Docker/Vulkan setups: some
    environments expose `core.placebo.Tonemap` but crash the process when it is
    invoked. We probe that path in a child Python process once, cache the
    result, and keep the main process on the deterministic fallback path when
    the probe fails.

    Env overrides are re-evaluated on every call and do not mutate the cached
    subprocess probe result. The probe result itself is cached for the process
    lifetime so repeated tonemap decisions stay deterministic after the first
    probe.
    """
    override = libplacebo_runtime_override()
    if override is not None:
        return override

    return cached_libplacebo_runtime_probe(state, probe)
