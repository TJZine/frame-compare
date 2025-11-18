"""Service layer exports for frame_compare."""

from __future__ import annotations

from .alignment import AlignmentRequest, AlignmentResult, AlignmentWorkflow
from .metadata import (
    CliPromptProtocol,
    FilesystemProbeProtocol,
    MetadataResolver,
    MetadataResolveRequest,
    MetadataResolveResult,
    TMDBClientProtocol,
)

__all__ = [
    "AlignmentRequest",
    "AlignmentResult",
    "AlignmentWorkflow",
    "CliPromptProtocol",
    "FilesystemProbeProtocol",
    "MetadataResolveRequest",
    "MetadataResolveResult",
    "MetadataResolver",
    "TMDBClientProtocol",
]
