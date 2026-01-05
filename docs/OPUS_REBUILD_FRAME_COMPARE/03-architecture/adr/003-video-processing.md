# ADR-003: Video Processing Architecture

## Status

Accepted

## Date

2025-12-16

## Context

Frame Compare requires:

- Frame-accurate video seeking
- HDR metadata extraction
- Color space transformations
- HDR to SDR tonemapping
- High-quality image output

Two primary options exist: VapourSynth (frame-server) or FFmpeg (command-line).

## Decision

**Use VapourSynth as primary rendering engine with FFmpeg as fallback.**

## Considered Alternatives

### Alternative 1: FFmpeg only

- Pros: Simpler installation, widely available
- Cons: Limited HDR control, no libplacebo integration, scripting limitations

### Alternative 2: VapourSynth only

- Pros: Full control, best quality
- Cons: Complex installation, reduces accessibility

### Alternative 3: OpenCV

- Pros: Python-native, well-documented
- Cons: Poor video format support, no HDR pipeline

## Rationale

- VapourSynth provides frame-accurate scripting essential for comparisons
- libplacebo plugin offers state-of-the-art tonemapping
- FFmpeg fallback ensures basic functionality without VS
- The encoding community expects VapourSynth quality

## Consequences

### Positive

- Best-in-class HDR handling
- Frame-accurate operations
- Rich plugin ecosystem
- Reproducible frame rendering

### Negative

- Installation complexity (mitigated by containers)
- Memory usage higher than streaming
- Learning curve for customization

### Risks

- VapourSynth API changes (mitigated: pin R72+)
- libplacebo plugin compatibility

## Implementation

### Renderer Interface

```python
class FrameRenderer(Protocol):
    def render_frame(self, path: Path, frame: int, output: Path) -> None: ...
    def is_available(self) -> bool: ...

class VapourSynthRenderer(FrameRenderer):
    """Primary renderer using VS"""
    ...

class FFmpegRenderer(FrameRenderer):
    """Fallback renderer using FFmpeg"""
    ...

def get_renderer(config: ScreenshotConfig) -> FrameRenderer:
    if config.use_ffmpeg or not VapourSynthRenderer().is_available():
        return FFmpegRenderer()
    return VapourSynthRenderer()
```

## References

- VapourSynth R72 documentation
- libplacebo tonemapping documentation
