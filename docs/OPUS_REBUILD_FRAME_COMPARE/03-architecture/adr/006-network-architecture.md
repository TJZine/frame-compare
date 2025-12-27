# ADR-006: Network Architecture (Async-First)

## Status

Accepted

## Date

2025-12-16

## Context

Frame Compare makes network calls to:

- slow.pics (image upload, potentially slow)
- TMDB API (metadata resolution)
- Potential future integrations

For a ground-up rebuild, we should architect network operations optimally.

## Decision

**Use async httpx with structured concurrency for all network operations.**

### HTTP Client: httpx (async mode)

```python
import httpx
import anyio

class SlowpicsClient:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None
    
    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=10),
        )
        return self
    
    async def upload_images(
        self,
        images: list[Path],
        title: str,
    ) -> str:
        """Upload images in parallel with progress."""
        async with anyio.create_task_group() as tg:
            results = []
            for image in images:
                tg.start_soon(self._upload_single, image, results)
        return await self._finalize_comparison(results, title)
```

### Structured Concurrency: anyio

**Use anyio** for async primitives (instead of raw asyncio).

**Rationale:**

- Backend-agnostic (asyncio or trio)
- Better structured concurrency with task groups
- Cleaner cancellation semantics
- Works well with httpx

### Sync/Async Bridge

Since VapourSynth is synchronous, we need a bridge pattern:

```python
import anyio

def run_network_operations(coro):
    """Run async network code from sync context."""
    return anyio.from_thread.run(coro)

# In sync pipeline
def publish_comparison(screenshots: list[Path]) -> str:
    async def _publish():
        async with SlowpicsClient() as client:
            return await client.upload_images(screenshots, title)
    
    return run_network_operations(_publish())
```

### Retry Strategy

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class NetworkClient:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        response = await self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response
```

## Consequences

### Positive

- Parallel uploads improve throughput
- Clean timeout and cancellation handling
- Retry logic standardized
- Progress reporting cleaner with async

### Negative

- Async/sync bridge adds complexity
- Debugging async code harder
- Team needs async Python experience

### Affected Modules

- `services/publishers.py` — Async slow.pics client
- `services/metadata.py` — Async TMDB client
- `net.py` — Shared async HTTP utilities

## References

- httpx async: <https://www.python-httpx.org/async/>
- anyio: <https://anyio.readthedocs.io/>
- tenacity: <https://tenacity.readthedocs.io/>
