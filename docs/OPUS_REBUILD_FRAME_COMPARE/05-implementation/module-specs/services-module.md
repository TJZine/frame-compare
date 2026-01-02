# Services Module Implementation Spec

> **Module:** `frame_compare.services`
> **Version:** 1.0
> **Priority:** P0

---

## 1. Module Overview

The Services module contains domain services that coordinate external systems and cross-cutting concerns.

### 1.1 Responsibilities

- Audio alignment between video clips
- Metadata extraction and TMDB lookup
- Publishing to slow.pics
- Dolby Vision probing (dovi_tool)
- Report generation

### 1.2 Module Structure

```text
src/frame_compare/services/
├── __init__.py
├── alignment.py        # Audio alignment service
├── dovi.py             # Dolby Vision handling (dovi_tool)
├── metadata.py         # Metadata extraction & TMDB
├── publishers.py       # slow.pics publishing
├── report.py           # HTML report generation
└── types.py            # Service-specific types
```

> [!NOTE]
> **Async behaviors** (timeouts, retries, cancellation) are defined in [async-semantics.md](../async-semantics.md).
> This module implements those patterns for all network-bound operations.

---

## 2. Audio Alignment Service

### 2.1 Types

```python
@dataclass(frozen=True)
class AlignmentResult:
    """Result of aligning two clips."""
    reference_clip: str
    comparison_clip: str
    frame_offset: int           # Frames to adjust comparison
    time_offset_seconds: float  # Time difference
    correlation_score: float    # Confidence (0-1)
    method: str                 # "cross_correlation" | "manual"

@dataclass(frozen=True)
class AlignmentConfig:
    """Configuration for audio alignment."""
    enable: bool = True
    sample_rate: int = 8000     # Hz, lower = faster
    max_offset_seconds: float = 30.0
    use_vspreview: bool = False
    cache_results: bool = True
```

### 2.2 Public API

> **ProgressReporter** is imported from `frame_compare.utils.progress` (see [utils-module.md](utils-module.md) Section 4.2).

```python
async def align_clips(
    reference: Path,
    comparisons: list[Path],
    config: AlignmentConfig,
    cache_dir: Path,
    progress: ProgressReporter | None = None,
) -> list[AlignmentResult]:
    """
    Align comparison clips to reference using audio cross-correlation.

    Algorithm:
    1. Extract audio from all clips (via FFmpeg)
    2. Resample to common sample_rate
    3. For each comparison:
       a. Cross-correlate with reference
       b. Find correlation peak
       c. Convert sample offset to frame offset
    4. Cache results

    Args:
        reference: Reference video file
        comparisons: List of comparison video files
        config: Alignment configuration
        cache_dir: Directory for cached offsets
        progress: Optional progress reporter

    Returns:
        List of AlignmentResult for each comparison, in the same order
        as the input `comparisons` list.

    Output ordering:
        The returned list[AlignmentResult] maintains 1:1 correspondence
        with `comparisons`: result[i] corresponds to comparisons[i].

    Cache behavior (when config.cache_results is True):
        - Full cache hit: If all requested keys are present in cache,
          return cached results without calling ffprobe/ffmpeg.
        - Partial hit: Compute only missing comparisons, then return
          combined results in `comparisons` order.
        - Cache miss: Compute all comparisons and cache results.

    Raises:
        FFmpegNotFoundError: FFmpeg binary not found in PATH
        FFmpegError: FFmpeg extraction failed (non-zero exit)
        AudioAlignmentError: Alignment failed due to empty audio,
            zero-norm signals, or cross-correlation failure
        CacheCorruptionError: Cache file exists but is not valid TOML
        CacheVersionMismatchError: Cache version does not match CACHE_VERSION
    """

def load_cached_offsets(
    cache_dir: Path,
    clips: list[Path],
) -> dict[str, AlignmentResult] | None:
    """Load previously calculated offsets from cache.

    Args:
        cache_dir: Directory containing audio_offsets.toml
        clips: List of clip paths where clips[0] is the reference clip
               and clips[1:] are comparison clips

    Clip ordering:
        - clips[0]: reference clip
        - clips[1:]: comparison clips

    Matching semantics:
        Only keys matching `f"{clips[0].stem}:{comparison.stem}"` where
        `comparison` is each element in `clips[1:]` are considered "requested".
        Extra entries in the cache file are ignored.

    Returns:
        - None: cache file does not exist
        - {}: cache file exists and is valid, but no requested keys found
        - dict: requested keys that were found, mapped to AlignmentResult

    Cache key format: `f"{reference.stem}:{comparison.stem}"`

    Behavior on error:
        - File missing: return None (cache miss)
        - TOML parse failure: raise CacheCorruptionError
        - Version mismatch: raise CacheVersionMismatchError
    """

def save_offsets_cache(
    cache_dir: Path,
    results: list[AlignmentResult],
) -> None:
    """Persist alignment results to cache."""
```

### 2.3 Implementation Details

#### FPS Sourcing

`align_clips` obtains FPS from the reference video using FFprobe (via `frame_compare.utils.subproc.run_subprocess`). This avoids importing `frame_compare.render` or `frame_compare.vs`.

```python
def _probe_fps(video_path: Path) -> Fraction:
    """Probe video FPS using FFprobe.

    Command: ffprobe -v quiet -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 {video}

    Returns:
        Fraction representing frames per second (e.g., Fraction(24000, 1001))

    Raises:
        FFmpegNotFoundError: ffprobe not found
        FFmpegError: ffprobe failed
    """
```

#### Audio Extraction

```python
def _extract_audio(video_path: Path, sample_rate: int) -> np.ndarray:
    """
    Extract audio using FFmpeg.

    Command:
    ffmpeg -i {video} -vn -ac 1 -ar {sample_rate} -f f32le -

    Returns mono float32 audio samples as np.ndarray.

    Raises:
        FFmpegNotFoundError: ffmpeg binary not found
        FFmpegError: ffmpeg exited non-zero
        AudioAlignmentError: audio track empty (reason: "empty audio track in {video_path.name}")
    """
```

#### Cross-Correlation

```python
def _cross_correlate(
    reference: np.ndarray,
    comparison: np.ndarray,
) -> tuple[int, float]:
    """
    Find offset using cross-correlation.

    Returns: (sample_offset, correlation_score)

    Algorithm:
    1. correlation = np.correlate(reference, comparison, mode='full')
    2. peak_idx = np.argmax(correlation)
    3. offset = len(reference) - 1 - peak_idx
    4. norm_ref = np.linalg.norm(reference)
    5. norm_comp = np.linalg.norm(comparison)
    6. If norm_ref == 0 or norm_comp == 0:
       raise AudioAlignmentError("zero-norm audio signal prevents correlation")
    7. score = correlation[peak_idx] / (norm_ref * norm_comp)

    Offset sign convention:
    - Positive offset: comparison audio starts AFTER reference
    - Negative offset: comparison audio starts BEFORE reference
    """
```

#### Frame Conversion

```python
def _samples_to_frames(
    sample_offset: int,
    sample_rate: int,
    fps: Fraction,
) -> int:
    """Convert sample offset to frame offset."""
    time_offset = sample_offset / sample_rate
    return round(time_offset * float(fps))
```

#### Cache Schema

Cache file: `{cache_dir}/audio_offsets.toml`

```toml
# Cache schema version (required)
version = "1"

# Entries keyed by "{reference_stem}:{comparison_stem}"
["reference:comparison_a"]
reference_clip = "reference.mkv"
comparison_clip = "comparison_a.mkv"
frame_offset = 42
time_offset_seconds = 1.751
correlation_score = 0.987
method = "cross_correlation"

["reference:comparison_b"]
# ... additional entries
```

- **CACHE_VERSION** = `"1"` (string, for future schema migrations)
- **Key format**: `f"{reference.stem}:{comparison.stem}"`
- If `version` field is missing or does not match `CACHE_VERSION`, raise `CacheVersionMismatchError`

---

## 3. Metadata Service

### 3.1 Types

```python
@dataclass(frozen=True)
class ParsedMetadata:
    """Metadata extracted from filename."""
    title: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    release_group: str | None = None
    source: str | None = None  # BluRay, WEB-DL, etc.
    resolution: str | None = None

@dataclass(frozen=True)
class TmdbMetadata:
    """Metadata from TMDB API."""
    tmdb_id: int
    title: str
    original_title: str
    year: int
    media_type: str  # "movie" | "tv"
    poster_url: str | None = None
    backdrop_url: str | None = None

@dataclass(frozen=True)
class MetadataConfig:
    """Configuration for metadata service."""
    api_key: str | None = None
    unattended: bool = False  # Auto-select first match
    timeout_seconds: float = 10.0
```

### 3.2 Public API

```python
def parse_filename(filename: str) -> ParsedMetadata:
    """
    Extract metadata from filename using GuessIt + Anitopy.

    Priority:
    1. Try GuessIt for western media
    2. Fall back to Anitopy for anime

    Args:
        filename: Video filename (not full path)

    Returns:
        ParsedMetadata with extracted fields
    """

async def lookup_tmdb(
    parsed: ParsedMetadata,
    config: MetadataConfig,
) -> TmdbMetadata | None:
    """
    Look up media on TMDB.

    Args:
        parsed: Metadata from filename parsing
        config: TMDB configuration

    Returns:
        TmdbMetadata if found, None otherwise

    Raises:
        TmdbError: If API call fails
    """

async def resolve_metadata(
    filenames: list[str],
    config: MetadataConfig,
    prompt_callback: Callable[[list[TmdbMetadata]], int] | None = None,
) -> TmdbMetadata | None:
    """
    Full metadata resolution workflow.

    Steps:
    1. Parse first filename
    2. Search TMDB
    3. If multiple results and not unattended, call prompt_callback
    4. Return selected metadata
    """
```

---

## 4. Publishers Service

### 4.1 Types

```python
@dataclass(frozen=True)
class PublishResult:
    """Result of publishing screenshots."""
    url: str                    # Comparison URL
    screenshot_count: int
    upload_duration_seconds: float

# SlowpicsConfig is imported from frame_compare.config
# See config-module.md for canonical definition (Pydantic BaseModel)
from frame_compare.config import SlowpicsConfig
```

### 4.2 Public API

```python
async def publish_to_slowpics(
    screenshot_dir: Path,
    config: SlowpicsConfig,
    metadata: TmdbMetadata | None = None,
    progress: ProgressReporter | None = None,
) -> PublishResult:
    """
    Upload screenshots to slow.pics.

    Steps:
    1. Collect all PNG files from directory
    2. Read files and prepare multipart upload
    3. POST to slow.pics API with retry
    4. Parse response for comparison URL
    5. Optionally delete local files

    Args:
        screenshot_dir: Directory containing screenshots
        config: Upload configuration
        metadata: Optional metadata for title
        progress: Optional progress reporter

    Returns:
        PublishResult with URL

    Raises:
        SlowpicsError: If upload fails after retries
    """

class SlowpicsPublisher:
    """Async publisher with connection pooling."""

    def __init__(self, config: SlowpicsConfig):
        self.config = config
        # Use distinct timeouts: fast connection, slow upload
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,  # Connection establishment
                read=config.timeout_seconds,  # Response wait
                write=config.timeout_seconds,  # Upload time
            )
        )

    async def upload(
        self,
        files: list[Path],
        title: str | None = None,
    ) -> str:
        """Upload files and return comparison URL."""

    async def close(self) -> None:
        """Close HTTP client."""
```

### 4.3 Implementation Details

```python
SLOWPICS_UPLOAD_URL = "https://slow.pics/api/comparison"

async def _prepare_upload(
    files: list[Path],
    title: str | None,
    visibility: str,
) -> dict:
    """Prepare multipart form data for upload."""

async def _upload_with_retry(
    client: httpx.AsyncClient,
    data: dict,
    max_retries: int,
) -> httpx.Response:
    """Upload with exponential backoff retry."""
```

---

## 5. Dolby Vision Service (P1)

Frame Compare 2.0 supports Dolby Vision workflows via the external `dovi_tool` binary. This is used to detect and (optionally) extract Dolby Vision RPU metadata for HDR pipelines.

### 5.1 Types

```python
from dataclasses import dataclass
from pathlib import Path

from frame_compare.errors import JSONValue

@dataclass(frozen=True)
class DoviFrameStats:
    """Per-frame Dolby Vision L1 metadata (nits values)."""
    l1_min_nits: float | None = None
    l1_max_nits: float | None = None
    l1_avg_nits: float | None = None
    l2_target_nits: float | None = None
    l6_max_cll: int | None = None
    l6_max_fall: int | None = None
    # L5 active area offsets
    l5_left: int | None = None
    l5_right: int | None = None
    l5_top: int | None = None
    l5_bottom: int | None = None

@dataclass(frozen=True)
class DoviMetadata:
    """Dolby Vision metadata extracted from a video."""
    frames: list[DoviFrameStats]
    profile: int | None = None
    level: int | None = None
    rpu_present: bool = False
    el_present: bool = False

# Import DoviConfig from config module (canonical definition)
from frame_compare.config import DoviConfig
```

### 5.2 Public API

```python
class DoviToolService:
    """Service wrapper for dovi_tool CLI to extract L1 metadata.

    Implements caching to avoid re-running expensive extraction.
    Uses subprocess with shell=False for security.
    """

    def __init__(self, config: DoviConfig | None = None) -> None:
        self.config = config or DoviConfig()
        self.binary_path = self._resolve_binary()

    def is_available(self) -> bool:
        """Check if dovi_tool binary is available."""
        return self.binary_path is not None and self.binary_path.exists()

    def extract_rpu_metadata(
        self,
        video_path: Path,
    ) -> list[dict[str, JSONValue]]:
        """
        Extract RPU metadata from video using dovi_tool.

        Algorithm:
        1. Check cache (.dovi_info.json) for existing metadata
        2. If cache miss:
           a. Run: dovi_tool extract-rpu -i <video> -o <temp.bin>
           b. Run: dovi_tool export -i <temp.bin> -d all=<temp.json>
           c. Parse JSON for L1/L2/L5/L6 metadata blocks
           d. Convert PQ values to nits using ST2084 EOTF
           e. Save to cache
        3. Return list of per-frame stats dicts

        Args:
            video_path: Path to video file (Dolby Vision stream)

        Returns:
            List of dicts with l1_min_nits, l1_max_nits, l1_avg_nits, etc.
            Empty list if no Dolby Vision data or extraction fails.

        Security:
            Uses subprocess with shell=False
            Treats video_path as untrusted input
        """

    def _resolve_binary(self) -> Path | None:
        """Resolve platform-specific dovi_tool binary path.

        Search order:
        1. config.dovi_tool_path if specified
        2. tools/dovi_tool.exe (Windows) or tools/dovi_tool (Unix)
        3. PATH lookup
        """

    def _pq_to_nits(self, pq_val: int | float) -> float:
        """Convert PQ value (0-4095 or 0-1) to nits using ST2084 EOTF."""

    def _parse_dovi_json(
        self, data: dict[str, object]
    ) -> list[dict[str, float | int | str | None]]:
        """Parse raw JSON from dovi_tool into simplified frame stats.

        Handles multiple dovi_tool output formats:
        - Direct level1 in vdr_dm_data
        - cmv29_metadata.ext_metadata_blocks (v2.9)
        - cmv40_metadata.ext_metadata_blocks (v4.0)
        """

# Singleton instance for convenience
dovi_tool: DoviToolService
```

### 5.3 Implementation Details

```python
# ST2084 EOTF constants for PQ-to-nits conversion
M1 = 2610.0 / 4096.0 / 4.0
M2 = 2523.0 / 4096.0 * 128.0
C1 = 3424.0 / 4096.0
C2 = 2413.0 / 4096.0 * 32.0
C3 = 2392.0 / 4096.0 * 32.0

def _pq_to_nits(pq_val: int | float) -> float:
    """
    Convert PQ value to nits.

    Formula: L = ((max[(N^(1/m2) - c1) / (c2 - c3 * N^(1/m2)), 0])^(1/m1)) * 10000
    """
    val = float(pq_val)
    if val > 1.0:  # 12-bit integer
        val = val / 4095.0
    if val <= 0.0:
        return 0.0

    pow_val = val ** (1.0 / M2)
    num = max(pow_val - C1, 0.0)
    den = C2 - C3 * pow_val
    if den == 0:
        return 10000.0

    linear_val = (num / den) ** (1.0 / M1)
    return linear_val * 10000.0
```

### 5.4 Caching Strategy

| Cache File | Location | Contents |
|------------|----------|----------|
| `.dovi_info.json` | Same directory as video | JSON array of per-frame stats |

Cache invalidation: Manual only (delete cache file to force re-extraction).

### 5.5 Error Handling

```python
class DoviError(ServiceError):
    """Dolby Vision extraction failed."""

class DoviToolNotFoundError(DependencyError):
    """dovi_tool binary not found (FC-2007)."""
```

---

## 6. Report Service

### 6.1 Types

```python
@dataclass(frozen=True)
class ClipInfo:
    """Information about a video clip for report generation."""
    name: str           # Display name (filename or title)
    path: Path          # Source video path
    frame_count: int
    resolution: tuple[int, int]
    fps: float
    hdr: bool
    label: str | None = None  # Custom label for comparison

@dataclass(frozen=True)
class ReportConfig:
    """Configuration for HTML report generation."""
    enable: bool = True
    output_dir: Path | None = None
    default_mode: str = "slider"  # slider, overlay, diff, blink
    include_filmstrip: bool = True

@dataclass(frozen=True)
class ReportData:
    """Data for report generation."""
    clips: list[ClipInfo]
    frames: list[int]
    screenshots: dict[str, list[Path]]  # clip_name -> [screenshot_paths]
    metadata: TmdbMetadata | None = None
```

### 6.2 Public API

```python
def generate_report(
    data: ReportData,
    config: ReportConfig,
    output_path: Path | None = None,
) -> Path:
    """
    Generate offline HTML comparison report.

    Steps:
    1. Load report template
    2. Embed screenshots as base64 or relative paths
    3. Generate JavaScript for viewer modes
    4. Write HTML file

    Args:
        data: Report content data
        config: Report configuration
        output_path: Optional output path override

    Returns:
        Path to generated report
    """
```

---

## 7. Error Handling

> [!NOTE]
> All error classes are defined centrally in `frame_compare.errors` (see [errors-module.md](errors-module.md)).
> This module should import and use these classes, not define its own.

**Error classes used by this module:**

| Error Class | Code | Usage |
|-------------|------|-------|
| `ServiceError` | (base) | Base for all service errors |
| `AudioAlignmentError` | FC-4005 | Audio alignment failed |
| `MetadataError` | FC-4016 | Metadata extraction failed |
| `TmdbError` | FC-5005 | TMDB API error |
| `PublishError` | FC-5002 | Publishing base error |
| `SlowpicsError` | FC-5002 | slow.pics upload failed |
| `ReportError` | FC-4017 | Report generation failed |
| `DoviError` | FC-4018 | Dolby Vision extraction failed |

```python
# Import from central module
from frame_compare.errors import (
    ServiceError,
    AudioAlignmentError,
    MetadataError,
    TmdbError,
    PublishError,
    SlowpicsError,
    ReportError,
    DoviError,
)
```

---

## 8. Testing Strategy

### 7.1 Unit Tests

| Test Case | Input | Expected |
|-----------|-------|----------|
| Cross-correlation | Known offset audio | Correct offset detected |
| Filename parsing | "Movie.2024.BluRay.mkv" | ParsedMetadata with title, year |
| Anitopy parsing | "[Group] Anime - 01.mkv" | ParsedMetadata with group, episode |
| Report generation | Sample data | Valid HTML output |

### 7.2 Integration Tests

- Full alignment pipeline with sample audio files
- TMDB lookup with mocked API responses
- slow.pics upload with mocked endpoint

### 7.3 Mocking Strategy

```python
@pytest.fixture
def mock_ffmpeg(mocker):
    """Mock FFmpeg audio extraction."""
    return mocker.patch(
        "frame_compare.services.alignment._run_ffmpeg",
        return_value=np.zeros(8000 * 10, dtype=np.float32),
    )

@pytest.fixture
def mock_slowpics(respx_mock):
    """Mock slow.pics API."""
    respx_mock.post("https://slow.pics/api/comparison").mock(
        return_value=httpx.Response(200, json={"url": "https://slow.pics/c/test"})
    )
```

---

## 9. AI Agent Implementation Prompt

```markdown
# Task: Implement Services Module

## Context
Implement the services module for Frame Compare 2.0.
This module contains domain services for alignment, metadata, publishing, and reports.

## Files to Create
1. `src/frame_compare/services/__init__.py` - Public exports
2. `src/frame_compare/services/types.py` - Service types
3. `src/frame_compare/services/alignment.py` - Audio alignment
4. `src/frame_compare/services/dovi.py` - Dolby Vision probing/extraction
5. `src/frame_compare/services/metadata.py` - Filename parsing + TMDB
6. `src/frame_compare/services/publishers.py` - slow.pics upload
7. `src/frame_compare/services/report.py` - HTML report generation

## Key Requirements
- Async HTTP with httpx for network calls
- FFmpeg subprocess for audio extraction
- GuessIt + Anitopy for filename parsing
- Retry logic with exponential backoff for uploads
- Caching for alignment results

## Dependencies
- httpx for async HTTP
- numpy for audio correlation
- guessit for filename parsing
- anitopy for anime filename parsing

## Acceptance Criteria
- Audio alignment detects known offsets within 1 frame
- Filename parsing handles western and anime formats
- slow.pics upload succeeds with retry
- Report generates valid HTML
```
