# Async Semantics (Cancellation, Timeout, Retry)

> **Module:** Reference
> **Purpose:** Define async behavior for external services

---

## 1. Timeout Policy

| Service | Default Timeout | Config Key | Retry |
|:--------|:----------------|:-----------|:------|
| slow.pics upload | 60s | `slowpics.timeout_seconds` | Yes |
| TMDB API | 10s | `tmdb.timeout_seconds` | Yes |
| FFmpeg frame extraction | 30s | `screenshots.ffmpeg_timeout_seconds` | No |

---

## 2. Retry Configuration

```python
@dataclass
class RetryConfig:
    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 30.0  # seconds
    exponential_base: float = 2.0
    jitter: float = 0.1  # ±10% randomization
```

### Retry Timeline Example

| Attempt | Delay | Total Elapsed |
|:--------|:------|:--------------|
| 1 | 0s | 0s |
| 2 | 1s | 1s |
| 3 | 2s | 3s |
| FAIL | - | 3s |

---

## 3. Error Propagation

### 3.1 Partial Failure Handling

| Scenario | Behavior | Exit Code |
|:---------|:---------|:----------|
| Upload succeeds, TMDB fails | Continue, warn | 0 |
| Upload fails after retries | Fail run | 6 |
| Render fails mid-batch | Abort, report partial | 5 |

### 3.2 Exit Code Mapping

```python
def map_error_to_exit_code(error: FrameCompareError) -> int:
    """Map exception to exit code."""
    match error:
        case ConfigError(): return 2
        case DependencyError(): return 3
        case InputError(): return 4
        case ProcessingError(): return 5
        case NetworkError(): return 6
        case _: return 1
```

---

## 4. Cancellation Semantics

### 4.1 Signal Handling

```python
async def run_with_cancellation(request: RunRequest) -> RunResult:
    """Run with graceful cancellation support."""

    def handle_sigint(sig, frame):
        raise KeyboardInterrupt("User cancelled")

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        return await execute_run(request)
    except KeyboardInterrupt:
        # Cleanup partial state
        await cleanup_partial_run()
        raise
```

### 4.2 Cleanup on Cancel

| Resource | Cleanup Action |
|:---------|:---------------|
| Temp files | Delete |
| HTTP connections | Close gracefully |
| VapourSynth core | Release |
| Partial screenshots | Keep (user may want) |

---

## 5. slow.pics Specifics

### 5.1 Rate Limiting

```python
async def upload_to_slowpics(images: list[bytes]) -> SlowpicsResponse:
    """Upload with rate limit handling."""

    for attempt in range(config.max_attempts):
        try:
            response = await client.post(SLOWPICS_URL, ...)

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise SlowpicsRateLimitedError(retry_after=retry_after)

            return parse_response(response)

        except SlowpicsRateLimitedError as e:
            if attempt < config.max_attempts - 1:
                await asyncio.sleep(e.retry_after)
                continue
            raise
```

### 5.2 Partial Upload Failure

If upload fails after some images sent:

- Log which images succeeded
- Include partial URL in error message
- Display recovery instructions to user

---

## 6. TMDB Specifics

### 6.1 Non-Critical Failure

TMDB lookup is optional metadata enrichment:

```python
async def enrich_metadata(info: VideoInfo) -> VideoInfo:
    """Add TMDB metadata if available."""

    try:
        tmdb_data = await lookup_tmdb(info.title, info.year)
        return info.with_tmdb(tmdb_data)
    except TmdbError as e:
        logger.warning(f"TMDB lookup failed: {e}, continuing without")
        return info
```

### 6.2 API Key Validation

- Validate key format before request (32 hex chars)
- Specific error for invalid key vs rate limit vs network

---

## 7. HTTP Client Lifecycle Rules

### 7.1 Ownership Patterns

| Pattern | When to Use | Code Shape |
|:--------|:------------|:-----------|
| Per-run `async with` | Default for CLI runs | `async with httpx.AsyncClient() as client:` |
| Injected (testing) | Unit tests, DI | `async def execute_run(client: httpx.AsyncClient)` |

> [!IMPORTANT]
> **Golden Rule:** Services MUST NOT create their own `AsyncClient`.
> They receive it from orchestration via dependency injection.

### 7.2 Context Manager Pattern

```python
@asynccontextmanager
async def service_context() -> AsyncIterator[Services]:
    """Manage async service lifecycle.

    This is the ONLY place where httpx.AsyncClient is created.
    Services receive it via dependency injection.
    """
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=60.0, write=60.0),
        follow_redirects=True,
    ) as client:
        services = Services(http_client=client)
        yield services
        # No explicit close() needed - context manager handles it
```

### 7.3 Service Constructor Pattern

Services accept the client as a constructor parameter:

```python
class SlowpicsPublisher:
    """Async publisher using injected HTTP client."""

    def __init__(self, config: SlowpicsConfig, client: httpx.AsyncClient):
        """Initialize with injected client.

        Args:
            config: Upload configuration
            client: HTTP client (managed by orchestration, NOT owned)
        """
        self.config = config
        self._client = client  # Injected, not owned

    # No close() method - client is managed externally
```

---

## 8. Ctrl+C / Cancellation Semantics

### 8.1 Signal Handling

| Signal | Exit Code | Behavior |
|:-------|:----------|:---------|
| SIGINT (Ctrl+C) | 130 | Graceful cancellation |
| SIGTERM | 143 | Same as SIGINT |

### 8.2 Cleanup Policy

| Resource | On Cancel | Rationale |
|:---------|:----------|:----------|
| Temp files | Delete | Clean slate for retry |
| Partial screenshots | Keep | User may want partial output |
| HTTP connections | Close gracefully | Resource hygiene |
| Cache files | Keep | Reusable on retry |
| Partial uploads | Abort | No half-uploaded comparisons |

### 8.3 Implementation Pattern

```python
async def run_with_cancellation(request: RunRequest) -> RunResult:
    """Run with Ctrl+C handling and proper cleanup."""
    try:
        return await execute_run(request)
    except KeyboardInterrupt:
        logger.info("Received Ctrl+C, cleaning up...")
        await cleanup_temp_files()
        sys.exit(130)
    except asyncio.CancelledError:
        logger.info("Task cancelled, cleaning up...")
        await cleanup_temp_files()
        sys.exit(130)


async def cleanup_temp_files() -> None:
    """Delete temporary files on cancellation."""
    temp_dir = Path(tempfile.gettempdir()) / "frame-compare"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
```

### 8.4 Timeout Escalation

For slow.pics uploads that may hang:

```python
async def upload_with_timeout(client: httpx.AsyncClient, ...) -> str:
    """Upload with graceful timeout handling."""
    try:
        return await asyncio.wait_for(
            client.post(...),
            timeout=config.timeout_seconds
        )
    except asyncio.TimeoutError:
        raise SlowpicsError(
            code="FC-5004",
            message="Upload timed out",
            details={"timeout_seconds": config.timeout_seconds}
        )
```
