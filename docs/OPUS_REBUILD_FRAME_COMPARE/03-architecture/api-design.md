# API Design Specification

> **Module:** Architecture
> **Version:** 1.0

> [!NOTE]
> **See [cli-flags-canonical.md](../05-implementation/cli-flags-canonical.md) for the single source of truth on CLI flags.**
> This document provides API overview and design context. For exact flag definitions,
> defaults, and config key mappings, reference the canonical CLI flags document.
---

## 1. API Overview

Frame Compare provides two primary interfaces:

| Interface | Purpose | Target |
|-----------|---------|--------|
| **CLI** | Human-driven comparison workflows | End users |
| **Programmatic API** | Automation and integration | Scripts, CI/CD |

---

## 2. CLI Interface Design

### 2.1 Command Structure

```
frame-compare [GLOBAL OPTIONS] COMMAND [COMMAND OPTIONS]
```

### 2.2 Commands

| Command | Description | Arguments |
|---------|-------------|-----------|
| `run` | Execute full comparison pipeline | `--root`, `--config`, `--no-cache` |
| `wizard` | Interactive guided setup | None |
| `doctor` | Check system dependencies | `--json` |
| `preset list` | List available presets | None |
| `preset apply` | Apply a preset | `NAME` |
| `preset save` | Save current config as preset | `NAME` |

### 2.3 Global Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--root` | PATH | CWD | Workspace root directory |
| `--config` | PATH | `config/config.toml` | Configuration file path |
| `--quiet` | FLAG | false | Suppress non-essential output |
| `--verbose` | FLAG | false | Enable debug logging |
| `--no-color` | FLAG | false | Disable colored output |

### 2.4 Run Command Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--input` | PATH | config value | Input video directory |
| `--no-cache` | FLAG | false | Recompute all metrics |
| `--from-cache-only` | FLAG | false | Use cached snapshot only |
| `--no-upload` | FLAG | false | Skip slow.pics upload |
| `--write-config` | FLAG | false | Write config and exit |
| `--diagnose-paths` | FLAG | false | Print path diagnostics as JSON |
| `--tm-preset` | CHOICE | config value | Tonemap preset |
| `--tm-target` | INT | config value | Target nits |
| `--tm-curve` | CHOICE | config value | Tone curve (bt2390, spline, reinhard, mobius, linear) |
| `--frame-count` | INT | config value | Number of frames to capture |
| `--seed` | INT | config value | Random seed for reproducibility |
| `--overlay` | CHOICE | none | Overlay mode (none, minimal, standard, diagnostic) |
| `--json` | FLAG | false | Output results as JSON |

### 2.5 Exit Codes

| Code | Meaning | Recovery |
|------|---------|----------|
| `0` | Success | None |
| `1` | General/internal error | Check logs, report bug |
| `2` | Configuration error | Fix config file |
| `3` | Dependency missing | Run `doctor` |
| `4` | Input error | Check input path |
| `5` | Processing error | Check video integrity |
| `6` | Network error | Check connection |
| `130` | User interrupt (Ctrl+C) | None |

---

## 3. Programmatic API

### 3.1 Public Exports

```python
# Main entry point
from frame_compare import run, RunRequest, RunResult, CLIAppError

# Diagnostics
from frame_compare import doctor, preflight

# Configuration
from frame_compare import config_writer, presets
```

### 3.2 Core Interfaces

#### RunRequest

```python
@dataclass(frozen=True)
class RunRequest:
    """Configuration for a comparison run."""

    root: Path
    """Workspace root directory."""

    config_path: Path | None = None
    """Optional override for config file location."""

    input_dir: Path | None = None
    """Optional override for input directory."""

    no_cache: bool = False
    """If True, ignore cached metrics."""

    from_cache_only: bool = False
    """If True, use only cached snapshot."""

    tm_preset: str | None = None
    """Optional tonemap preset override."""

    tm_target_nits: int | None = None
    """Optional target nits override."""

    quiet: bool = False
    """Suppress non-essential output."""

    verbose: bool = False
    """Enable debug logging."""
```

#### RunResult

```python
@dataclass(frozen=True)
class RunResult:
    """Result of a comparison run."""

    success: bool
    """Whether the run completed successfully."""

    screenshot_dir: Path | None
    """Directory containing screenshots, if generated."""

    slowpics_url: str | None
    """URL to slow.pics comparison, if uploaded."""

    report_path: Path | None
    """Path to HTML report, if generated."""

    frame_count: int
    """Number of frames processed."""

    clips_processed: int
    """Number of video clips processed."""

    duration_seconds: float
    """Total processing time."""

    cache_hit: bool
    """Whether cached metrics were used."""

    errors: list[str]
    """Non-fatal errors encountered."""
```

### 3.3 Usage Examples

#### Basic Run

```python
from frame_compare import run, RunRequest
from pathlib import Path

request = RunRequest(root=Path("/workspace"))
result = run(request)

if result.success:
    print(f"Published: {result.slowpics_url}")
else:
    for error in result.errors:
        print(f"Error: {error}")
```

#### JSON Output (`--json` flag)

When `--json` is passed to CLI commands, output follows this schema:

```json
{
  "success": true,
  "screenshots_dir": "/workspace/screenshots/",
  "slowpics_url": "https://slow.pics/c/abc123",
  "report_path": "/workspace/screenshots/report.html",
  "frame_count": 10,
  "clips_processed": 3,
  "duration_seconds": 45.2,
  "cache_hit": false,
  "errors": []
}
```

On error:

```json
{
  "success": false,
  "error": {
    "code": "FC-3001",
    "name": "NO_VIDEOS_FOUND",
    "message": "No video files found in comparison_videos",
    "hint": "Place *.mkv, *.mp4 files in the input directory"
  }
}
```

#### Custom Configuration

```python
from frame_compare import run, RunRequest
from pathlib import Path

request = RunRequest(
    root=Path("/workspace"),
    tm_preset="filmic",
    tm_target_nits=250,
    no_cache=True,
)

result = run(request)
```

#### Doctor Check

```python
from frame_compare import doctor

checks = doctor.collect_checks()
results = doctor.evaluate(checks)

for result in results:
    status = "✓" if result.passed else "✗"
    print(f"{status} {result.name}: {result.message}")
```

### 3.4 Dependency Injection

```python
@dataclass
class RunDependencies:
    """Injectable dependencies for testability."""

    vs_loader: VSLoader
    """VapourSynth video loading."""

    ffmpeg_runner: FFmpegRunner
    """FFmpeg command execution."""

    http_client: httpx.AsyncClient
    """HTTP client for API calls."""

    progress: ProgressReporter
    """Progress bar/output."""

    clock: Callable[[], datetime]
    """Time provider (for testing)."""
```

---

## 4. Configuration API

### 4.1 Config Loading

```python
from frame_compare.config import load_config, ConfigSchema

config = load_config(Path("config/config.toml"))

# Type-safe access
frame_count: int = config.analysis.frame_count
preset: str = config.color.preset
```

### 4.2 Config Schema (Pydantic)

```python
class AnalysisConfig(BaseModel):
    frame_count: int = Field(default=10, ge=1, le=100)
    random_seed: int = 42
    save_frames_data: bool = True

class ColorConfig(BaseModel):
    preset: Literal["reference", "filmic", "contrast", "bt2390_spec", "spline", "bright_lift", "highlight_guard"] = "reference"
    enable_tonemap: bool = True
    target_nits: int = Field(default=203, ge=100, le=1000)

class ConfigSchema(BaseSettings):
    """Root configuration schema.

    Note: Uses pydantic-settings (BaseSettings) for:
    - TOML file loading
    - Environment variable overrides (FRAME_COMPARE_ prefix)
    - CLI argument overrides

    See config-module.md for full implementation details.
    """
    paths: PathsConfig = PathsConfig()
    analysis: AnalysisConfig = AnalysisConfig()
    color: ColorConfig = ColorConfig()
    screenshots: ScreenshotsConfig = ScreenshotsConfig()
    slowpics: SlowpicsConfig = SlowpicsConfig()
    tmdb: TmdbConfig = TmdbConfig()
    audio_alignment: AudioAlignmentConfig = AudioAlignmentConfig()
    report: ReportConfig = ReportConfig()
    dovi: DoviConfig = DoviConfig()
    diagnostics: DiagnosticsConfig = DiagnosticsConfig()
    logging: LoggingConfig = LoggingConfig()
```

---

## 5. Error Handling

### 5.1 Exception Hierarchy

```text
FrameCompareError (base)
├── ConfigError
│   ├── ConfigNotFoundError
│   └── ConfigValidationError
├── DependencyError
│   ├── VapourSynthError
│   ├── FFmpegError
│   └── PluginNotFoundError
├── ProcessingError
│   ├── NoVideosFoundError
│   ├── FrameExtractionError
│   └── TonemapError
└── NetworkError
    ├── PublishError
    │   └── SlowpicsError
    └── TmdbError
```

### 5.2 Result Types (Preferred for Internal)

```python
from typing import TypeVar, Generic

T = TypeVar("T")
E = TypeVar("E")

@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T

@dataclass(frozen=True)
class Err(Generic[E]):
    error: E

Result = Ok[T] | Err[E]
```

---

## 6. Events / Hooks (Future)

### 6.1 Event Types

```python
class Event:
    """Base event class."""
    pass

@dataclass
class FrameProcessed(Event):
    frame_number: int
    clip_name: str
    metrics: FrameMetrics

@dataclass
class UploadComplete(Event):
    url: str
    screenshot_count: int
```

### 6.2 Hook Registration (Design)

```python
from frame_compare import run, RunRequest
from frame_compare.events import on_frame_processed

@on_frame_processed
def handle_frame(event: FrameProcessed):
    print(f"Processed frame {event.frame_number}")

result = run(RunRequest(root=Path("/workspace")))
```

---

## 7. Versioning

### 7.1 API Stability

| Component | Stability | Policy |
|-----------|-----------|--------|
| `run()`, `RunRequest`, `RunResult` | Stable | Semantic versioning |
| `doctor`, `preflight` | Stable | Semantic versioning |
| Internal modules | Unstable | May change without notice |
| Configuration schema | Stable | Backward compatible |

### 7.2 Deprecation Policy

1. Deprecated items marked with `@deprecated` decorator
2. Deprecation warnings for 2 minor versions
3. Removal only in major versions
4. Migration guide provided
