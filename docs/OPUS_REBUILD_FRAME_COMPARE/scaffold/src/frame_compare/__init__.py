"""Frame Compare - Video frame comparison and HDR tonemapping tool.

This package provides tools for comparing video frames across different
encodes, with support for HDR tonemapping and automatic frame selection.

Example:
    from frame_compare import run, RunRequest

    request = RunRequest(root=Path("/workspace"))
    result = run(request)
    print(result.slowpics_url)

"""

from importlib.metadata import version

__version__ = version("frame-compare")
__all__ = [
    "__version__",
]
