"""Integration tests for VapourSynth module."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Skip if VapourSynth is not installed
vs = pytest.importorskip("vapoursynth")

# Skip if VapourSynth is mocked (e.g. by test_exports.py running first in a no-VS env)
if isinstance(vs, MagicMock) or hasattr(vs, "_mock_methods"):
    pytest.skip("VapourSynth is mocked, skipping integration test", allow_module_level=True)

from frame_compare.vs import (  # noqa: E402
    is_vapoursynth_available,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_vs_script(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=_REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _assert_vs_process_ok(result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode == 0:
        stdout_lines = [line for line in result.stdout.splitlines() if line.strip()]
        assert stdout_lines and stdout_lines[-1] == "OK"
        return

    output = []
    if result.stdout:
        output.append(f"stdout:\n{result.stdout.strip()}")
    if result.stderr:
        output.append(f"stderr:\n{result.stderr.strip()}")
    details = "\n\n".join(output)

    if result.returncode in (-11, 139):
        pytest.fail(f"VapourSynth subprocess segfaulted.\n\n{details}")
    pytest.fail(f"VapourSynth subprocess failed with exit {result.returncode}.\n\n{details}")


@pytest.mark.vs_required
def test_vs_integration_smoke():
    """Real VapourSynth test (not mocked)."""
    if not is_vapoursynth_available():
        pytest.skip("VapourSynth not available")

    result = _run_vs_script(
        """
        import vapoursynth as vs

        from frame_compare.vs import TonemapSettings, ensure_vs_environment, apply_tonemap

        core = ensure_vs_environment()
        clip = core.std.BlankClip(width=16, height=16, format=vs.RGBS, length=1)
        out = apply_tonemap(clip, TonemapSettings(enabled=True), hdr_metadata=None)
        frame = out.get_frame(0)

        assert out.width == 16
        assert out.height == 16
        assert out.format.id == vs.RGBS
        assert frame.width == 16
        assert frame.height == 16
        print("OK")
        """
    )
    _assert_vs_process_ok(result)


@pytest.mark.vs_required
def test_libplacebo_tonemap_succeeds_in_docker():
    """Exercise tonemap in Docker; require libplacebo only when configured.

    By default, Docker Desktop environments (macOS/Windows) may not have a usable
    Vulkan device. In that case, `_apply_libplacebo` may return None and
    `apply_tonemap` must fall back without raising.

    Set `FRAME_COMPARE_REQUIRE_LIBPLACEBO=1` to require libplacebo to succeed.
    """
    result = _run_vs_script(
        """
        import os

        import vapoursynth as vs

        from frame_compare.vs import HDRMetadata, TonemapSettings, apply_tonemap
        from frame_compare.vs.tonemap import _apply_libplacebo, detect_plugins

        core = vs.core
        require_libplacebo = os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1"

        libplacebo_available = bool(detect_plugins(core).get("libplacebo"))
        if require_libplacebo:
            assert libplacebo_available, (
                "FRAME_COMPARE_REQUIRE_LIBPLACEBO=1 but libplacebo is unavailable"
            )
        else:
            assert libplacebo_available, "libplacebo plugin missing in Docker image (unexpected)"

        clip = core.std.BlankClip(
            width=16,
            height=16,
            format=vs.RGBS,
            length=1,
            color=[0.5, 0.5, 0.5],
        )
        settings = TonemapSettings(
            enabled=True,
            preset="reference",
            tone_curve="bt2390",
            target_nits=203,
        )
        hdr_metadata = HDRMetadata(
            mastering_display=None,
            max_cll=1000,
            max_fall=400,
            color_primaries=9,
            transfer=16,
            matrix=9,
        )

        if require_libplacebo:
            libplacebo_out = _apply_libplacebo(clip, settings, core, hdr_metadata)
            assert libplacebo_out is not None, (
                "_apply_libplacebo returned None while FRAME_COMPARE_REQUIRE_LIBPLACEBO=1; "
                "Vulkan/libplacebo backend is not usable in this environment."
            )
            _ = libplacebo_out.get_frame(0)

        out = apply_tonemap(clip, settings, hdr_metadata)
        frame = out.get_frame(0)

        assert out.format.id == vs.RGBS
        assert frame.width == 16
        assert frame.height == 16
        print("OK")
        """
    )
    _assert_vs_process_ok(result)
