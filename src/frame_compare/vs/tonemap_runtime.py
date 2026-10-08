"""libplacebo runtime probe helpers for HDR tonemapping."""

from __future__ import annotations

import os
import subprocess  # nosec B404
import sys
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import structlog

log = structlog.get_logger()

_REQUIRE_LIBPLACEBO_ENV = "FRAME_COMPARE_REQUIRE_LIBPLACEBO"
_DISABLE_LIBPLACEBO_ENV = "FRAME_COMPARE_DISABLE_LIBPLACEBO"
_LIBPLACEBO_PROBE_ENV = "FRAME_COMPARE_LIBPLACEBO_PROBE"
_LIBPLACEBO_PROBE_TIMEOUT_SECONDS = 5.0
_CHILD_PROCESS_CWD = Path(sys.executable).resolve().parent
_PYTHON_INJECTION_ENV_KEYS = (
    "PYTHONHOME",
    "PYTHONINSPECT",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
)


@dataclass(slots=True)
class LibplaceboRuntimeState:
    """Process-owned state for the libplacebo runtime probe."""

    probe_result: bool | None = None


def _build_probe_env() -> dict[str, str]:
    """Build the probe environment without caller-controlled Python imports."""
    env = os.environ.copy()
    for key in _PYTHON_INJECTION_ENV_KEYS:
        env.pop(key, None)
    env["PYTHONSAFEPATH"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env[_LIBPLACEBO_PROBE_ENV] = "1"
    return env


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
            _Range=1,
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
    env = _build_probe_env()

    try:
        # -I excludes the cwd, PYTHONPATH, and user site from imports. The safe
        # cwd is also explicit so this remains true if the interpreter flags
        # change. The copied environment retains native runtime/plugin paths.
        result = subprocess.run(  # nosec B603
            [sys.executable, "-I", "-c", probe_script],
            env=env,
            cwd=_CHILD_PROCESS_CWD,
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
