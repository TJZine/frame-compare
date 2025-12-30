"""Integration tests for VapourSynth module."""

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
