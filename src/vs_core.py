from __future__ import annotations

# VapourSynth may not be present during scaffolding. Provide a tiny fallback
# so the pipeline runs without native deps.

class _FakeClip:
    def __init__(self, num_frames: int = 1000):
        self.num_frames = num_frames

def init_clip(file: str):
    """Return a clip object for analysis. Real impl uses VapourSynth (LWLibavSource).
    This placeholder returns a _FakeClip so the pipeline is runnable without VS.
    """
    try:
        import vapoursynth as vs  # type: ignore
        return vs.core.lsmas.LWLibavSource(file)
    except Exception:
        return _FakeClip()

def process_clip_for_screenshot(clip):
    """Real impl will apply tonemapping (libplacebo) and RGB conversion.
    Placeholder returns clip unchanged.
    """
    return clip
