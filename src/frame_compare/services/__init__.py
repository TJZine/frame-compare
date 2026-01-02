"""Services module."""

from frame_compare.services.alignment import (
    align_clips,
    load_cached_offsets,
    save_offsets_cache,
)
from frame_compare.services.metadata import lookup_tmdb, parse_filename, resolve_metadata
from frame_compare.services.publishers import (
    PublishResult,
    SlowpicsPublisher,
    publish_to_slowpics,
)
from frame_compare.services.report import ClipInfo, ReportData, generate_report
from frame_compare.services.types import (
    AlignmentConfig,
    AlignmentResult,
    MetadataConfig,
    ParsedMetadata,
    TmdbMetadata,
)

__all__ = [
    "AlignmentConfig",
    "AlignmentResult",
    "ClipInfo",
    "MetadataConfig",
    "ParsedMetadata",
    "PublishResult",
    "ReportData",
    "SlowpicsPublisher",
    "TmdbMetadata",
    "align_clips",
    "generate_report",
    "load_cached_offsets",
    "lookup_tmdb",
    "parse_filename",
    "publish_to_slowpics",
    "resolve_metadata",
    "save_offsets_cache",
]
