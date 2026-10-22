"""libplacebo runtime safety and experimental native-still policy."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess  # nosec B404
import sys
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import structlog

from frame_compare.utils.subproc import prepare_python_child
from frame_compare.vs.errors import TonemapError

log = structlog.get_logger()

_REQUIRE_LIBPLACEBO_ENV = "FRAME_COMPARE_REQUIRE_LIBPLACEBO"
_DISABLE_LIBPLACEBO_ENV = "FRAME_COMPARE_DISABLE_LIBPLACEBO"
_LIBPLACEBO_PROBE_ENV = "FRAME_COMPARE_LIBPLACEBO_PROBE"
_EXPERIMENTAL_NATIVE_STILLS_ENV = "FRAME_COMPARE_EXPERIMENTAL_NATIVE_STILLS"
_LIBPLACEBO_PROBE_TIMEOUT_SECONDS = 5.0
_CHILD_PROCESS_CWD = Path(sys.executable).resolve().parent


@dataclass(frozen=True, slots=True)
class ExperimentalNativeStillBuild:
    """Reviewed diagnostic build; this does not declare production acceptance."""

    sha256: str
    vs_placebo_commit: str
    libplacebo_commit: str
    libdovi_commit: str
    native_source_sha256: tuple[str, str, str]
    target: str


# Source order: tonemap.c, vs-placebo.c, vs-placebo.h. The UCRT recipe retains
# shaderc/glslang and libdovi; an upstream 2.0.4 identity alone does not identify it.
EXPERIMENTAL_NATIVE_STILL_BUILD = ExperimentalNativeStillBuild(
    sha256="33a6ce9743e63ced306c9038263f742e339fd3eefef9460c0897b1dbc7d7fe6c",
    vs_placebo_commit="3cfd23f257ecb62b0cbd81eaaca092e18ae8e579",
    libplacebo_commit="a7a18af88ff0a17c04840dcb3246047bb6b46df3",
    libdovi_commit="4fd2b2235c9f93582dd4a00e65ee34a07800afd7",
    native_source_sha256=(
        "f46533b4084d9cdd36d52f8b985d61d8a98955f9b69c012b602e349d12297346",
        "4be415d877cf00ebdfc3b290d37e22cd9559e0367e32e2fd95bf2391576956a2",
        "81f50c0eefba37798dab2e83de5d3524c8af81fef1c854b1335d7dccddbf9e5a",
    ),
    target="x86_64-w64-mingw32ucrt",
)


@dataclass(frozen=True, slots=True)
class LibplaceboPluginIdentity:
    """Identity of the actual bound canonical plugin, not a search candidate."""

    path: str
    sha256: str


@dataclass(slots=True)
class LibplaceboRuntimeState:
    """Process-owned safety result, keyed when an experimental plugin is selected."""

    probe_result: bool | None = None
    plugin_identity: LibplaceboPluginIdentity | None = None


def experimental_native_stills_enabled() -> bool:
    """Read the default-off runtime opt-in without importing a native module."""
    value = os.environ.get(_EXPERIMENTAL_NATIVE_STILLS_ENV, "")
    if value == "":
        return False
    if value == "1":
        return True
    raise TonemapError(
        reason=f"Invalid {_EXPERIMENTAL_NATIVE_STILLS_ENV} value",
        hint=f"Unset {_EXPERIMENTAL_NATIVE_STILLS_ENV}, or set it to 1 for experimental native stills",
    )


def experimental_native_still_plugin(core: object) -> LibplaceboPluginIdentity | None:
    """Recognize only the reviewed loaded build and its actual native signature."""
    namespace = getattr(core, "placebo", None)
    function = getattr(namespace, "Tonemap", None)
    plugin = getattr(function, "plugin", None)
    signature = getattr(function, "signature", None)
    if (
        getattr(plugin, "identifier", None) != "com.vs.placebo"
        or getattr(plugin, "namespace", None) != "placebo"
        or not isinstance(signature, str)
        or "independent:int:opt" not in signature.split(";")
    ):
        return None
    path_value = getattr(plugin, "plugin_path", None)
    if not isinstance(path_value, str) or not path_value:
        return None
    try:
        path = Path(path_value)
        if not path.is_absolute() or not path.is_file():
            return None
        path = path.resolve(strict=True)
        with path.open("rb") as binary:
            digest = hashlib.file_digest(binary, "sha256").hexdigest()
    except (OSError, RuntimeError):
        return None
    if digest != EXPERIMENTAL_NATIVE_STILL_BUILD.sha256:
        return None
    return LibplaceboPluginIdentity(str(path), digest)


def probe_libplacebo_runtime(*, plugin_identity: LibplaceboPluginIdentity | None = None) -> bool:
    """Probe generic runtime safety; an experimental child must load the same DLL."""
    identity_check = ""
    identity_result = ""
    if plugin_identity is not None:
        identity_check = textwrap.dedent(
            f"""
            import hashlib
            import json
            from pathlib import Path

            function = core.placebo.Tonemap
            plugin = function.plugin
            plugin_path = Path(plugin.plugin_path).resolve(strict=True)
            with plugin_path.open("rb") as binary:
                plugin_sha256 = hashlib.file_digest(binary, "sha256").hexdigest()
            if (plugin.identifier != "com.vs.placebo" or plugin.namespace != "placebo"
                or "independent:int:opt" not in function.signature.split(";")
                or plugin_path != Path({plugin_identity.path!r})
                or plugin_sha256 != {plugin_identity.sha256!r}):
                raise SystemExit(3)
            """
        )
        identity_result = (
            '\nprint(json.dumps({"path": str(plugin_path), "sha256": plugin_sha256}))\n'
        )
    probe_script = (
        textwrap.dedent(
            """
            import vapoursynth as vs

            core = vs.core
            if not hasattr(core, "placebo") or not hasattr(core.placebo, "Tonemap"):
                raise SystemExit(2)
            """
        )
        + identity_check
        + textwrap.dedent(
            """
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
                dst_prim=3,
                src_csp=1,
            )
            _ = out.get_frame(0)
            """
        )
        + identity_result
    )
    env = os.environ.copy()
    env[_LIBPLACEBO_PROBE_ENV] = "1"
    probe_argv, env = prepare_python_child([sys.executable, "-c", probe_script], env=env)
    try:
        result = subprocess.run(  # nosec B603
            probe_argv,
            env=env,
            cwd=_CHILD_PROCESS_CWD,
            capture_output=True,
            text=True,
            timeout=_LIBPLACEBO_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("libplacebo_probe_failed_disabling", error=f"{type(exc).__name__}: {exc}")
        return False
    if result.returncode == 0:
        if plugin_identity is None:
            return True
        try:
            receipt: object = json.loads(result.stdout)
            if isinstance(receipt, dict):
                payload = cast(dict[str, object], receipt)
                receipt_path = payload.get("path")
                matched = (
                    payload.get("sha256") == plugin_identity.sha256
                    and isinstance(receipt_path, str)
                    and Path(receipt_path) == Path(plugin_identity.path)
                )
            else:
                matched = False
        except (ValueError, TypeError):
            matched = False
        if matched:
            log.debug(
                "libplacebo_probe_identity_confirmed",
                plugin_path=plugin_identity.path,
                plugin_sha256=plugin_identity.sha256,
            )
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
    *,
    plugin_identity: LibplaceboPluginIdentity | None = None,
) -> bool:
    """Cache safety for the corresponding loaded plugin; never retain its nodes."""
    if state.plugin_identity != plugin_identity:
        state.probe_result = None
        state.plugin_identity = plugin_identity
    cached_result = state.probe_result
    if cached_result is not None:
        return cached_result
    probe_result = probe()
    state.probe_result = probe_result
    return probe_result


def libplacebo_runtime_usable(
    state: LibplaceboRuntimeState,
    probe: Callable[[], bool],
    *,
    plugin_identity: LibplaceboPluginIdentity | None = None,
) -> bool:
    """Check generic safety, preserving per-call overrides and their precedence.

    Native presence alone is insufficient on some Vulkan installations, so the
    ordinary path probes a child once. Experimental selection additionally binds
    that safety result to the actual loaded plugin. This is separate from native
    independent capability/admission. Overrides bypass without rewriting cache.
    """
    override = libplacebo_runtime_override()
    if override is not None:
        return override
    return cached_libplacebo_runtime_probe(state, probe, plugin_identity=plugin_identity)
