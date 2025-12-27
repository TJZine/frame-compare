# Monitoring & Observability

> **Module:** Operations  
> **Version:** 1.0

---

## 1. Observability Overview

### 1.1 Three Pillars

| Pillar | Purpose | Implementation |
|--------|---------|----------------|
| **Logs** | Event records | Structured JSON logging |
| **Metrics** | Numeric measurements | Built-in counters/timers |
| **Traces** | Request flow | Correlation IDs |

### 1.2 Goals

1. Diagnose issues quickly from logs
2. Track performance over time
3. Identify patterns in failures
4. Support debugging without reproduction

---

## 2. Logging

### 2.1 Configuration

```toml
# config/config.toml

[logging]
level = "INFO"           # DEBUG, INFO, WARNING, ERROR
format = "json"          # json, console
file = "logs/frame-compare.log"
max_size_mb = 50
backup_count = 5
```

### 2.2 Log Format (JSON)

```json
{
  "timestamp": "2024-12-16T10:30:00.123Z",
  "level": "INFO",
  "message": "frame_processed",
  "run_id": "abc123",
  "clip_name": "reference.mkv",
  "frame_number": 42,
  "luminance": 0.523,
  "duration_ms": 12.5
}
```

### 2.3 Log Categories

| Category | Logger Name | Content |
|----------|-------------|---------|
| **CLI** | `frame_compare.cli` | Command invocation, args |
| **Runner** | `frame_compare.runner` | Workflow orchestration |
| **Analysis** | `frame_compare.analysis` | Metrics calculation |
| **VS** | `frame_compare.vs` | VapourSynth operations |
| **Render** | `frame_compare.render` | Screenshot generation |
| **Network** | `frame_compare.services` | API calls, uploads |

### 2.4 Implementation

```python
# src/frame_compare/logging.py

import structlog
from pathlib import Path

def configure_logging(
    level: str = "INFO",
    format: str = "json",
    file: Path | None = None,
) -> None:
    """Configure structured logging."""
    
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    
    if format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

### 2.5 Log Events Reference

| Event | Level | Fields | Meaning |
|-------|-------|--------|---------|
| `run_started` | INFO | run_id, config_path | New run initiated |
| `run_completed` | INFO | run_id, duration_s, frame_count | Run finished successfully |
| `run_failed` | ERROR | run_id, error_code, message | Run failed |
| `clip_loaded` | DEBUG | clip_name, frame_count, fps | Video clip opened |
| `frame_processed` | DEBUG | clip_name, frame, luminance, motion | Frame metrics computed |
| `cache_hit` | INFO | cache_file | Using cached data |
| `cache_miss` | INFO | cache_file, reason | Cache invalidated |
| `upload_started` | INFO | file_count, total_bytes | Upload beginning |
| `upload_completed` | INFO | url, duration_s | Upload successful |
| `upload_failed` | ERROR | error_code, message | Upload failed |

---

## 3. Metrics

### 3.1 Built-in Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `run_duration_seconds` | Histogram | status | Total run time |
| `frames_processed_total` | Counter | clip | Frames analyzed |
| `cache_hits_total` | Counter | type | Cache hit count |
| `cache_misses_total` | Counter | type | Cache miss count |
| `upload_bytes_total` | Counter | service | Bytes uploaded |
| `upload_duration_seconds` | Histogram | service | Upload time |
| `errors_total` | Counter | code | Error occurrences |

### 3.2 Implementation

```python
# src/frame_compare/metrics.py

from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable
from contextlib import contextmanager

@dataclass
class Metrics:
    """Simple metrics collection."""
    
    counters: dict[str, int] = field(default_factory=dict)
    timers: dict[str, list[float]] = field(default_factory=dict)
    
    def inc(self, name: str, value: int = 1) -> None:
        """Increment a counter."""
        self.counters[name] = self.counters.get(name, 0) + value
    
    @contextmanager
    def timer(self, name: str):
        """Time a block of code."""
        start = perf_counter()
        try:
            yield
        finally:
            duration = perf_counter() - start
            if name not in self.timers:
                self.timers[name] = []
            self.timers[name].append(duration)
    
    def to_dict(self) -> dict:
        """Export metrics."""
        return {
            "counters": self.counters,
            "timers": {
                k: {
                    "count": len(v),
                    "sum": sum(v),
                    "avg": sum(v) / len(v) if v else 0,
                    "max": max(v) if v else 0,
                }
                for k, v in self.timers.items()
            },
        }

# Global metrics instance
metrics = Metrics()
```

### 3.3 Usage

```python
from frame_compare.metrics import metrics

def process_frame(frame) -> None:
    with metrics.timer("frame_processing"):
        # ... processing ...
        pass
    
    metrics.inc("frames_processed")
```

### 3.4 Metrics Output

```json
{
  "counters": {
    "frames_processed": 100,
    "cache_hits": 10,
    "cache_misses": 2,
    "errors": 0
  },
  "timers": {
    "frame_processing": {
      "count": 100,
      "sum": 12.5,
      "avg": 0.125,
      "max": 0.250
    },
    "upload": {
      "count": 1,
      "sum": 3.2,
      "avg": 3.2,
      "max": 3.2
    }
  }
}
```

---

## 4. Tracing

### 4.1 Correlation IDs

Every run gets a unique correlation ID for tracing:

```python
# src/frame_compare/tracing.py

import uuid
from contextvars import ContextVar

run_id: ContextVar[str] = ContextVar("run_id", default="unknown")

def new_run_id() -> str:
    """Generate a new run ID."""
    id = uuid.uuid4().hex[:8]
    run_id.set(id)
    return id

def get_run_id() -> str:
    """Get current run ID."""
    return run_id.get()
```

### 4.2 Span Tracking

```python
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter

@dataclass
class Span:
    name: str
    run_id: str
    start_time: float
    end_time: float | None = None
    
    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0
        return (self.end_time - self.start_time) * 1000

@contextmanager
def trace_span(name: str):
    """Create a traced span."""
    span = Span(
        name=name,
        run_id=get_run_id(),
        start_time=perf_counter(),
    )
    log.debug("span_start", span=name)
    try:
        yield span
    finally:
        span.end_time = perf_counter()
        log.debug("span_end", span=name, duration_ms=span.duration_ms)
```

---

## 5. Health Checks

### 5.1 Doctor Command

```bash
$ frame-compare doctor

System Check Results
────────────────────

Runtime:
  ✓ Python 3.13.1
  ✓ VapourSynth R72

Plugins:
  ✓ libplacebo (6.338.0)
  ✓ lsmas (0.2.3)
  ⚠ vspreview (not installed, optional)

External Tools:
  ✓ FFmpeg 6.1.1
  ✓ dovi_tool 2.1.0

Configuration:
  ✓ config/config.toml exists
  ✓ Configuration valid

Directories:
  ✓ Input: comparison_videos (readable)
  ✓ Output: screenshots (writable)
  ✓ Cache: generated (writable)

Network:
  ✓ slow.pics (reachable)
  ⚠ TMDB (API key not configured)
```

### 5.2 Health Check Implementation

```python
# src/frame_compare/doctor.py

from dataclasses import dataclass
from enum import Enum

class CheckStatus(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    details: dict | None = None

def collect_checks() -> list[CheckResult]:
    """Run all health checks."""
    return [
        check_python_version(),
        check_vapoursynth(),
        check_plugins(),
        check_ffmpeg(),
        check_config(),
        check_directories(),
        check_network(),
    ]

def check_vapoursynth() -> CheckResult:
    try:
        import vapoursynth as vs
        core = vs.core
        version = core.version_number()
        return CheckResult(
            name="VapourSynth",
            status=CheckStatus.PASS,
            message=f"R{version}",
        )
    except ImportError:
        return CheckResult(
            name="VapourSynth",
            status=CheckStatus.FAIL,
            message="Not installed",
            details={"hint": "Use Docker or install manually"},
        )
```

---

## 6. Performance Monitoring

### 6.1 Key Performance Indicators

| KPI | Target | Alert Threshold |
|-----|--------|-----------------|
| Run duration (10 frames) | < 30s | > 60s |
| Frame processing | < 500ms | > 1s |
| Upload speed | > 1 MB/s | < 500 KB/s |
| Memory usage | < 2GB | > 4GB |
| Cache hit rate | > 80% | < 50% |

### 6.2 Performance Report

After each run, generate a performance summary:

```json
{
  "run_id": "abc123",
  "duration_seconds": 25.3,
  "frames_processed": 10,
  "clips_count": 2,
  "performance": {
    "avg_frame_time_ms": 125.5,
    "max_frame_time_ms": 250.0,
    "cache_hit_rate": 0.85,
    "memory_peak_mb": 1536
  },
  "stages": {
    "analysis": 5.2,
    "rendering": 15.1,
    "upload": 5.0
  }
}
```

---

## 7. Alerting (Future)

### 7.1 Alert Conditions

| Condition | Severity | Action |
|-----------|----------|--------|
| Run failed | High | Notify user, log details |
| Slow performance | Medium | Log warning |
| Cache corruption | Medium | Clear cache, retry |
| Network unreachable | Low | Retry with backoff |

### 7.2 Webhook Support

```toml
# config/config.toml

[notifications]
webhook_url = "https://hooks.slack.com/..."
on_success = false
on_failure = true
```

---

## 8. Debugging Tips

### 8.1 Verbose Mode

```bash
frame-compare --verbose run

# Enables DEBUG level logging
# Shows frame-by-frame progress
# Prints timing for each stage
```

### 8.2 Diagnose Paths

```bash
frame-compare --diagnose-paths run

# Outputs JSON with all resolved paths:
# {
#   "root": "/workspace",
#   "config": "/workspace/config/config.toml",
#   "input": "/workspace/comparison_videos",
#   "output": "/workspace/screenshots",
#   "cache": "/workspace/generated"
# }
```

### 8.3 Log Analysis

```bash
# Filter errors from log
jq 'select(.level == "ERROR")' logs/frame-compare.log

# Find slow operations
jq 'select(.duration_ms > 1000)' logs/frame-compare.log

# Track specific run
jq 'select(.run_id == "abc123")' logs/frame-compare.log
```
