"""Integration tests for VapourSynth module."""

import os
from unittest.mock import MagicMock

import pytest

# Skip if VapourSynth is not installed
vs = pytest.importorskip("vapoursynth")

# Skip if VapourSynth is mocked (e.g. by test_exports.py running first in a no-VS env)
if isinstance(vs, MagicMock) or hasattr(vs, "_mock_methods"):
    pytest.skip("VapourSynth is mocked, skipping integration test", allow_module_level=True)

from frame_compare.vs import (  # noqa: E402
    TonemapSettings,
    ensure_vs_environment,
    is_vapoursynth_available,
    tonemap,
)


@pytest.mark.vs_required
def test_vs_integration_smoke():
    """Real VapourSynth test (not mocked)."""
    if not is_vapoursynth_available():
        pytest.skip("VapourSynth not available")

    # 1. Initialize core
    core = ensure_vs_environment()

    # 2. Create blank clip (1 frame, RGBS)
    # Note: VS requires dimensions divisible by subsampling if YUV, but RGBS is safe.
    clip = core.std.BlankClip(width=1920, height=1080, format=vs.RGBS, length=1)

    # 3. Call tonemap (alias)
    # Using defaults: enabled=True, preset="reference"
    settings = TonemapSettings(enabled=True)
    out = tonemap(clip, settings, hdr_metadata=None)

    # 4. Verify output
    assert isinstance(out, vs.VideoNode)
    assert out.width == 1920
    assert out.height == 1080
    assert out.format.id == vs.RGBS


@pytest.mark.vs_required
def test_libplacebo_tonemap_succeeds_in_docker():
    """Exercise tonemap in Docker; require libplacebo only when configured.

    By default, Docker Desktop environments (macOS/Windows) may not have a usable
    Vulkan device. In that case, `_apply_libplacebo` may return None and
    `apply_tonemap` must fall back without raising.

    Set `FRAME_COMPARE_REQUIRE_LIBPLACEBO=1` to require libplacebo to succeed.
    """
    import vapoursynth as vs

    from frame_compare.vs import HDRMetadata, TonemapSettings
    from frame_compare.vs.tonemap import _apply_libplacebo, detect_plugins

    core = vs.core

    require_libplacebo = os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1"

    libplacebo_available = bool(detect_plugins(core).get("libplacebo"))
    if require_libplacebo:
        assert (
            libplacebo_available
        ), "FRAME_COMPARE_REQUIRE_LIBPLACEBO=1 but libplacebo is unavailable"
    else:
        assert libplacebo_available, "libplacebo plugin missing in Docker image (unexpected)"

    # Create a minimal HDR test clip (RGBS, 1920x1080, 1 frame)
    clip = core.std.BlankClip(
        width=1920,
        height=1080,
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

    # Call _apply_libplacebo directly and assert it succeeds
    result = _apply_libplacebo(clip, settings, core, hdr_metadata)

    if require_libplacebo:
        assert result is not None, (
            "_apply_libplacebo returned None while FRAME_COMPARE_REQUIRE_LIBPLACEBO=1; "
            "Vulkan/libplacebo backend is not usable in this environment."
        )
        assert isinstance(result, vs.VideoNode)

    # Regardless of libplacebo device availability, tonemap must not raise.
    out = tonemap(clip, settings, hdr_metadata)
    assert isinstance(out, vs.VideoNode)
    assert out.format.id == vs.RGBS
