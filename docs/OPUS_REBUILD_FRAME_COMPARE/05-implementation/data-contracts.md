# Data Contracts

> **Module:** Reference
> **Purpose:** Define versioned schemas for key artifacts to prevent silent drift

---

## 1. Version Policy

All data contracts follow semantic versioning:

- **Major**: Breaking change (incompatible schema)
- **Minor**: Additive change (new optional fields)
- **Patch**: Clarification only (no schema change)

**Backward Compatibility Rule**:

- v2.x readers MUST handle v2.0 files
- v2.0 readers SHOULD warn on v2.x fields they don't recognize
- Major version changes require explicit migration

---

## 2. Metrics Cache File

**Location**: `{generated_dir}/cache/frame_metrics.msgspec`
**Format**: msgspec binary
**Version**: 2.0

```python
@dataclass
class MetricsCacheV2:
    """Cached frame metrics for a video set."""

    # Schema version (required first field)
    version: str = "2.0"

    # Cache metadata
    created_at: str  # ISO 8601 timestamp
    frame_compare_version: str  # e.g., "2.0.0"

    # Source fingerprints (for cache invalidation)
    video_hashes: dict[str, str]  # {path: sha256_first_1mb}
    config_hash: str  # sha256 of analysis config

    # Metrics data
    frame_count: int
    luminance: list[float]  # per-frame avg luminance
    motion_scores: list[float]  # inter-frame motion

    # Selection results (if cached)
    selection: FrameSelectionV2 | None = None

@dataclass
class FrameSelectionV2:
    """Cached frame selection."""
    mode: str  # "quantile" | "motion" | "random" | "mixed"
    seed: int | None
    frames: list[int]  # 0-indexed frame numbers
    reasons: list[str]  # per-frame selection reason
```

**Validation**:

- If `version` != "2.x", raise `CacheVersionMismatchError(FC-4007)`
- If `video_hashes` don't match current files, invalidate cache
- If `config_hash` doesn't match, invalidate cache

---

## 3. Report HTML Structure

**Location**: `{output_dir}/comparison_report.html`
**Format**: Self-contained HTML5
**Version**: 2.0

```html
<!DOCTYPE html>
<html lang="en" data-report-version="2.0">
<head>
  <meta name="generator" content="frame-compare v2.0.0">
  <meta name="created" content="2025-12-19T21:00:00Z">
  <!-- Embedded CSS and JS -->
</head>
<body>
  <script type="application/json" id="report-data">
    { /* See Report JSON Payload below */ }
  </script>
  <!-- Viewer UI -->
</body>
</html>
```

---

## 4. Report JSON Payload

**Embedded in**: HTML report `#report-data`
**Standalone**: `{output_dir}/comparison_report.json`
**Version**: 2.0

```python
@dataclass
class ReportPayloadV2:
    """Report data structure."""

    # Schema
    version: str = "2.0"

    # Metadata
    title: str
    created_at: str  # ISO 8601
    frame_compare_version: str

    # Videos compared
    videos: list[VideoInfo]

    # Frames
    frames: list[FrameData]

    # Config used (JSON-safe; no Any leakage)
    config_snapshot: dict[str, JSONValue]  # from frame_compare.errors

    # slow.pics URL (if uploaded)
    slowpics_url: str | None = None

@dataclass
class VideoInfo:
    filename: str
    resolution: tuple[int, int]
    duration_seconds: float
    hdr_format: str | None  # "PQ" | "HLG" | None

@dataclass
class FrameData:
    frame_number: int
    selection_reason: str
    screenshots: dict[str, str]  # {video_name: base64_png}
```

---

## 5. slow.pics Response Shape

**Endpoint**: `https://slow.pics/api/comparison`
**Method**: POST multipart
**Version**: External API (no versioning control)

```python
@dataclass
class SlowpicsResponse:
    """Expected response from slow.pics API."""

    # Success case
    success: bool
    url: str | None  # e.g., "https://slow.pics/c/abc123"
    comparison_id: str | None

    # Error case
    error: str | None
    rate_limited: bool = False
    retry_after: int | None = None  # seconds

# Response parsing with fallback
def parse_slowpics_response(raw: dict) -> SlowpicsResponse:
    """Parse with graceful degradation for API changes."""
    # Handle known fields
    # Log unknown fields for monitoring
    # Never fail on unexpected fields (additive API changes)
```

**Resilience Rules**:

- Accept unknown fields silently (log at DEBUG)
- Require only `success` field as mandatory
- Treat missing `url` on success as `SlowpicsError(FC-5002)`

---

## 6. Schema Migration

| From | To | Migration |
|:-----|:---|:----------|
| v1.x cache | v2.0 | Delete and regenerate |
| v2.0 cache | v2.1 | Read normally, ignore new fields |
| v2.0 report | v2.1 | Viewer handles gracefully |
