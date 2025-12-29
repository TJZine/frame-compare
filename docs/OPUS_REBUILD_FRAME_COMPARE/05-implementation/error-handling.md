# Error Handling Specification

> **Module:** Implementation
> **Version:** 1.0

---

## 1. Error Handling Philosophy

### 1.1 Core Principles

1. **Explicit over implicit** — Never hide errors silently
2. **Structured errors** — All errors have a code, message, and context
3. **Recoverable by default** — Provide recovery hints where possible
4. **Log for debugging** — Every error logged with correlation ID
5. **User-friendly messages** — Technical details in logs, not in output

### 1.2 Error Categories

| Category | Recovery | User Action | Example |
|----------|----------|-------------|---------|
| **Configuration** | Fix config file | Edit TOML | Invalid TOML syntax |
| **Dependency** | Install/fix tool | Run `doctor` | VapourSynth missing |
| **Input** | Fix input data | Check files | No videos found |
| **Processing** | Retry or skip | Check logs | Frame extraction failed |
| **Network** | Retry | Check connectivity | slow.pics timeout |
| **Internal** | Report bug | None | Assertion failed |

---

## 2. Exception Hierarchy

### 2.1 Base Classes

```python
# src/frame_compare/errors.py
# Note: The canonical ErrorContext is defined in errors-module.md

from dataclasses import dataclass

# JSONValue is defined in frame_compare.errors
JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
ErrorDetails = dict[str, JSONValue]

@dataclass(frozen=True)
class ErrorContext:
    """Structured error context."""
    code: str
    name: str
    message: str
    details: ErrorDetails | None = None
    hint: str | None = None
    cause: BaseException | None = None

class FrameCompareError(Exception):
    """Base exception for all Frame Compare errors."""

    def __init__(self, context: ErrorContext):
        self.context = context
        super().__init__(context.message)

    @property
    def code(self) -> str:
        return self.context.code

    @property
    def hint(self) -> str | None:
        return self.context.hint
```

### 2.2 Exception Tree

```
FrameCompareError (base)
│
├── ConfigError
│   ├── ConfigNotFoundError
│   │   code: "FC-1001"
│   │   name: "CONFIG_NOT_FOUND"
│   │   hint: "Run 'frame-compare wizard' or create config/config.toml"
│   │
│   ├── ConfigParseError
│   │   code: "FC-1002"
│   │   name: "CONFIG_PARSE_ERROR"
│   │   hint: "Check TOML syntax at line {line}"
│   │
│   └── ConfigValidationError
│       code: "FC-1003"
│       name: "CONFIG_VALIDATION_ERROR"
│       hint: "Field '{field}' {validation_message}"
│
├── DependencyError
│   ├── VapourSynthError
│   │   code: "FC-2002"
│   │   name: "VAPOURSYNTH_ERROR"
│   │   hint: "Run 'frame-compare doctor' for diagnostics"
│   │
│   ├── FFmpegError
│   │   code: "FC-2006"
│   │   name: "FFMPEG_ERROR"
│   │   hint: "Ensure FFmpeg is in PATH"
│   │
│   └── PluginNotFoundError
│       code: "FC-2003"
│       name: "PLUGIN_NOT_FOUND"
│       hint: "Install {plugin} or use Docker deployment"
│
├── InputError
│   ├── NoVideosFoundError
│   │   code: "FC-3001"
│   │   name: "NO_VIDEOS_FOUND"
│   │   hint: "Place video files in {input_dir}"
│   │
│   ├── InvalidVideoError
│   │   code: "FC-3002"
│   │   name: "VIDEO_OPEN_ERROR"
│   │   hint: "File '{path}' could not be opened"
│   │
│   └── InsufficientFramesError
│       code: "FC-3004"
│       name: "INSUFFICIENT_FRAMES"
│       hint: "Video has fewer frames than requested"
│
├── ProcessingError
│   ├── FrameExtractionError
│   │   code: "FC-4001"
│   │   name: "FRAME_EXTRACTION_ERROR"
│   │   hint: "Frame {frame} could not be extracted"
│   │
│   ├── TonemapError
│   │   code: "FC-4003"
│   │   name: "TONEMAP_ERROR"
│   │   hint: "Tonemapping failed: {reason}"
│   │
│   ├── RenderError
│   │   code: "FC-4004"
│   │   name: "RENDER_ERROR"
│   │   hint: "Screenshot rendering failed"
│   │
│   └── AudioAlignmentError
│       code: "FC-4005"
│       name: "AUDIO_ALIGNMENT_ERROR"
│       hint: "Could not align audio tracks"
│
├── NetworkError
│   ├── SlowpicsError
│   │   code: "FC-5002"
│   │   name: "SLOWPICS_ERROR"
│   │   hint: "Check internet connection or try --no-upload"
│   │
│   ├── TmdbError
│   │   code: "FC-5005"
│   │   name: "TMDB_ERROR"
│   │   hint: "Check TMDB API key or use --skip-metadata"
│   │
│   └── NetworkTimeoutError
│       code: "FC-5007"
│       name: "NETWORK_TIMEOUT"
│       hint: "Request timed out, retrying may help"
│
└── InternalError
    code: "FC-9001"
    name: "INTERNAL_ERROR"
    hint: "Please report this bug with the log file"
```

### 2.3 Implementation Example

```python
# src/frame_compare/errors.py

class ConfigNotFoundError(ConfigError):
    """Configuration file not found."""

    def __init__(self, path: Path):
        super().__init__(ErrorContext(
            code="FC-1001",
            name="CONFIG_NOT_FOUND",
            message=f"Configuration file not found: {path}",
            details={"path": str(path)},
            hint="Run 'frame-compare wizard' or create config/config.toml",
        ))

class NoVideosFoundError(InputError):
    """No video files found in input directory."""

    def __init__(self, input_dir: Path, patterns: list[str]):
        super().__init__(ErrorContext(
            code="FC-3001",
            name="NO_VIDEOS_FOUND",
            message=f"No video files found in {input_dir}",
            details={
                "input_dir": str(input_dir),
                "patterns": patterns,
            },
            hint=f"Place video files (*.mkv, *.mp4, etc.) in {input_dir}",
        ))
```

---

## 3. Result Types (Internal Use)

### 3.1 Result Pattern

For internal APIs where exceptions are too heavy-handed:

```python
# src/frame_compare/utils/result.py

from typing import TypeVar, Generic
from dataclasses import dataclass

T = TypeVar("T")
E = TypeVar("E")

@dataclass(frozen=True)
class Ok(Generic[T]):
    """Success result."""
    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

@dataclass(frozen=True)
class Err(Generic[E]):
    """Error result."""
    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> Never:
        raise ValueError(f"Called unwrap on Err: {self.error}")

Result = Ok[T] | Err[E]
```

### 3.2 Usage Example

```python
from frame_compare.utils.result import Result, Ok, Err

def load_video(path: Path) -> Result[VideoClip, str]:
    """Load a video file, returning Result instead of raising."""
    if not path.exists():
        return Err(f"File not found: {path}")

    try:
        clip = vs.core.lsmas.LWLibavSource(str(path))
        return Ok(clip)
    except Exception as e:
        return Err(f"Failed to load: {e}")

# Usage
match load_video(path):
    case Ok(clip):
        process(clip)
    case Err(msg):
        log.warning(f"Skipping {path}: {msg}")
```

---

## 4. Error Handling Patterns

### 4.1 CLI Layer

```python
"""CLI layer error handling - src/frame_compare/cli_entry.py"""

import typer
from rich.console import Console
from frame_compare.errors import FrameCompareError, get_exit_code

console = Console(stderr=True)

def handle_error(error: FrameCompareError) -> int:
    """Convert exception to user-friendly output and exit code."""

    console.print(f"[red]Error[/red] [{error.code}]: {error.context.message}")

    if error.hint:
        console.print(f"[yellow]Hint:[/yellow] {error.hint}")

    return int(get_exit_code(error))

def run():
    try:
        result = runner.run(request)
    except FrameCompareError as e:
        raise typer.Exit(code=handle_error(e)) from e
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(code=130)
    except Exception as e:
        # Unexpected error - log full traceback
        log.exception("Unexpected error")
        console.print(f"[red]Unexpected error:[/red] {e}")
        console.print("[dim]See log file for details[/dim]")
        raise typer.Exit(code=1)
```

### 4.2 Service Layer

```python
# src/frame_compare/services/publishers.py

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class SlowpicsPublisher:

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def upload(self, screenshots: list[Path]) -> str:
        """Upload screenshots with retry logic."""
        try:
            response = await self.client.post(...)
            response.raise_for_status()
            return response.json()["url"]
        except httpx.TimeoutException as e:
            raise NetworkTimeoutError(
                service="slow.pics",
                timeout=self.timeout,
            ) from e
        except httpx.HTTPStatusError as e:
            raise SlowpicsError(
                status_code=e.response.status_code,
                response=e.response.text,
            ) from e
```

### 4.3 Domain Layer

```python
# src/frame_compare/analysis/selection.py

def select_frames(
    metrics: FrameMetrics,
    count: int,
    seed: int,
) -> Result[FrameSelection, SelectionError]:
    """Select frames, returning Result for graceful handling."""

    if count > len(metrics.frames):
        return Err(SelectionError(
            code="INSUFFICIENT_FRAMES",
            message=f"Requested {count} frames but only {len(metrics.frames)} available",
        ))

    # ... selection logic ...

    return Ok(FrameSelection(...))
```

---

## 5. Logging Strategy

### 5.1 Log Levels

| Level | Purpose | Example |
|-------|---------|---------|
| `DEBUG` | Internal detail | "Frame 42 luminance: 0.523" |
| `INFO` | Progress info | "Processing clip: reference.mkv" |
| `WARNING` | Recoverable issue | "Cache miss, recomputing metrics" |
| `ERROR` | Operation failed | "Failed to upload: timeout" |
| `CRITICAL` | Fatal, stopping | "VapourSynth initialization failed" |

### 5.2 Structured Logging

```python
import structlog

log = structlog.get_logger()

# Good - structured context
log.info(
    "frame_processed",
    clip_name="reference.mkv",
    frame_number=42,
    luminance=0.523,
    duration_ms=12.5,
)

# Bad - unstructured string interpolation
log.info(f"Processed frame 42 of reference.mkv with luminance 0.523")
```

### 5.3 Correlation IDs

```python
import uuid
from contextvars import ContextVar

correlation_id: ContextVar[str] = ContextVar("correlation_id")

def run_with_correlation():
    """Wrap each run with a correlation ID."""
    run_id = str(uuid.uuid4())[:8]
    correlation_id.set(run_id)

    log.info("run_started", run_id=run_id)
    try:
        result = execute_run()
        log.info("run_completed", run_id=run_id, success=True)
    except Exception as e:
        log.error("run_failed", run_id=run_id, error=str(e))
        raise
```

---

## 6. User-Facing Messages

### 6.1 Message Guidelines

| Type | Format | Example |
|------|--------|---------|
| **Success** | Action completed | "✓ Published to slow.pics" |
| **Progress** | Activity indicator | "Processing frame 42/100..." |
| **Warning** | Recoverable issue | "⚠ Cache outdated, recomputing" |
| **Error** | Problem + hint | "✗ VapourSynth not found\n  Hint: Run doctor" |

### 6.2 Rich Console Output

```python
from rich.console import Console
from rich.panel import Panel

console = Console()

def show_error(error: FrameCompareError):
    """Display error with rich formatting."""

    content = f"[red bold]{error.code}[/red bold]\n\n{error.context.message}"

    if error.hint:
        content += f"\n\n[yellow]Hint:[/yellow] {error.hint}"

    console.print(Panel(
        content,
        title="[red]Error[/red]",
        border_style="red",
    ))
```

---

## 7. Exit Code Reference

| Code | Name | Meaning | Recovery |
|------|------|---------|----------|
| `0` | SUCCESS | Completed successfully | None |
| `1` | GENERAL_ERROR | Unexpected error | Check logs |
| `2` | CONFIG_ERROR | Configuration invalid | Fix config |
| `3` | DEPENDENCY_ERROR | Missing dependency | Run doctor |
| `4` | INPUT_ERROR | Bad input data | Check files |
| `5` | PROCESSING_ERROR | Processing failed | Check logs |
| `6` | NETWORK_ERROR | Network failed | Check connection |
| `130` | INTERRUPTED | User cancelled | None |

---

## 8. Error Handling Checklist for Agents

When implementing a new module:

- [ ] Define module-specific exceptions extending base hierarchy
- [ ] Use `ErrorContext` for structured error information
- [ ] Include actionable `hint` in all user-facing errors
- [ ] Log errors with structured context before raising
- [ ] Map exceptions to exit codes in CLI layer
- [ ] Write tests for error paths (not just happy paths)
- [ ] Document error codes in module docstring
