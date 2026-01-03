# Orchestration Module Implementation Spec

> **Module:** `frame_compare.orchestration`
> **Version:** 1.0
> **Priority:** P0

---

## 1. Module Overview

The Orchestration module coordinates the end-to-end comparison workflow, managing preflight checks, phase execution, progress reporting, and error handling at the application level.

### 1.1 Responsibilities

- Validate configuration and resolve workspace paths
- Execute diagnostic checks (doctor command)
- Coordinate multi-phase processing pipeline
- Report progress and handle errors
- Manage resource lifecycle (async clients, vs environment)

### 1.2 Module Structure

> [!IMPORTANT]
> **This is the canonical module structure.** The `orchestration/` package owns
> all workflow coordination including preflight, doctor, phases, and progress reporters.
> `ProgressReporter` protocol is defined in `utils/progress.py`; implementations live here.

```text
src/frame_compare/orchestration/
├── __init__.py          # Public exports
├── coordinator.py       # Main run coordination
├── preflight.py         # Pre-run validation
├── doctor.py            # Diagnostic checks
├── phases.py            # Phase definitions
├── progress.py          # Progress reporter implementations
├── context.py           # Runtime context
└── runner.py            # Async run execution
```

---

## 2. Dependencies

```python
from frame_compare.config import load_config, ConfigSchema
from frame_compare.errors import (
    FrameCompareError,
    ConfigError,
    DependencyError,
    InputError,
)
from frame_compare.utils import WorkspacePaths, RunMetrics
```

---

## 3. Key Types

### 3.1 Preflight Types

```python
@dataclass(frozen=True)
class PreflightResult:
    """Result of preflight validation."""
    config: ConfigSchema
    workspace: WorkspacePaths
    warnings: list[str] = field(default_factory=list)
```

### 3.2 Doctor Types

```python
@dataclass(frozen=True)
class DoctorCheck:
    """Single diagnostic check."""
    name: str
    category: str  # "core", "optional", "network"
    check_fn: Callable[[], CheckResult]

@dataclass(frozen=True)
class CheckResult:
    """Result of a diagnostic check."""
    passed: bool
    message: str
    hint: str | None = None
    details: dict[str, JSONValue] = field(default_factory=dict)  # Imported from errors module

@dataclass(frozen=True)
class DoctorReport:
    """Complete diagnostic report."""
    checks: list[tuple[DoctorCheck, CheckResult]]
    all_passed: bool
    critical_failures: list[str]
```

### 3.3 Progress Types

> [!NOTE]
> The `ProgressReporter` protocol is canonically defined in `frame_compare.utils.progress`.
> Orchestration code MUST use that canonical protocol and MUST NOT redefine it.

```python
from typing import Protocol

# Canonical definition in utils/progress.py
class ProgressReporter(Protocol):
    """Protocol for progress reporting.

    Note: For logging, use structlog from utils.logging, not this protocol.
    The progress reporter is strictly for visual progress updates.
    """

    def start_phase(self, name: str, total: int) -> None:
        """Start a new phase with expected total steps."""

    def set_description(self, description: str) -> None:
        """Update current operation description."""

    def advance(self, delta: int = 1) -> None:
        """Advance progress by delta steps."""

    def complete_phase(self) -> None:
        """Mark current phase as complete."""

# Orchestration module MUST use the canonical implementations in `frame_compare.utils.progress`:
# - `RichProgressReporter` (TTY output)
# - `NullProgressReporter` (quiet mode)
# - `LogProgressReporter` (non-interactive / non-TTY)
#
# A JSON-lines progress reporter is PLANNED; do not reference it as required until it exists.
```

### 3.4 Phase Types

```python
from enum import Enum

class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    WARNED = "warned"
    FAILED = "failed"

@dataclass
class Phase:
    """Execution phase definition."""
    name: str
    execute: Callable[[RunContext], Awaitable[None]]
    skip_condition: Callable[[ConfigSchema], bool] | None = None
    status: PhaseStatus = PhaseStatus.PENDING
```

---

## 4. Public API

### 4.1 Preflight

```python
def prepare_preflight(
    root: Path | None = None,
    config_path: Path | None = None,
) -> PreflightResult:
    """
    Validate configuration and resolve workspace paths.

    Steps:
    1. Resolve workspace root (explicit, cwd, or search upward)
    2. Load configuration file (explicit path or discovery)
    3. Validate configuration schema
    4. Resolve all workspace paths declared in `ConfigSchema.paths`
    5. Verify input directory exists and contains videos

    Returns:
        PreflightResult with config and workspace

    Raises:
        ConfigError: Configuration invalid
        InputError: Input directory missing or empty
    """
```

### 4.2 Doctor

```python
def collect_checks() -> list[DoctorCheck]:
    """
    Collect all diagnostic checks.

    Categories:
    - core: Python version, VapourSynth, required plugins
    - optional: FFmpeg, dovi_tool, VSPreview
    - network: slow.pics reachability, TMDB API key

    Returns:
        List of check definitions
    """

def run_doctor(
    checks: list[DoctorCheck] | None = None,
    reporter: ProgressReporter | None = None,
) -> DoctorReport:
    """
    Execute diagnostic checks and report results.

    Args:
        checks: Specific checks to run (default: all)
        reporter: Progress reporter for output

    Returns:
        DoctorReport with all check results
    """
```

#### 4.2.1 Check List (Deterministic)

`collect_checks()` MUST return checks in this exact order (stable list and stable `DoctorCheck.name` strings):

1. `python_version` (core)
2. `vapoursynth` (core)
3. `lsmas` (core)
4. `ffmpeg` (optional)
5. `dovi_tool` (optional)
6. `vspreview` (optional)
7. `slowpics` (network)
8. `tmdb_api_key` (network)

#### 4.2.2 slow.pics Reachability Probe

The `slowpics` network check MUST use:

- URL: `https://slow.pics/`
- Method: `HEAD`
- Timeout: `5.0` seconds

Pass/Fail semantics:

- Pass if the request completes and the HTTP status is `< 400`.
- Fail (passed=False) if the request errors (timeout/connection/etc.) or returns status `>= 400`.

### 4.3 Run Coordination

#### 4.3.1 Request Types

```python
@dataclass(frozen=True)
class RunRequest:
    """Complete configuration for a comparison run.

    All fields map to CLI flags or config file sections.
    See cli-module.md for CLI flag → config mappings.
    """
    # Core paths
    root: Path
    config_path: Path | None = None
    input_dir: Path | None = None

    # Cache behavior
    no_cache: bool = False           # --no-cache
    from_cache_only: bool = False    # --from-cache-only

    # Skip flags
    skip_analysis: bool = False      # --skip-analysis
    skip_metadata: bool = False      # --skip-metadata
    skip_dovi: bool = False          # --skip-dovi
    no_upload: bool = False          # --no-upload

    # Tonemap overrides (highest priority)
    tm_preset: str | None = None     # --tm-preset
    tm_target_nits: int | None = None  # --tm-target
    tm_curve: str | None = None      # --tm-curve

    # Frame selection overrides
    frame_count: int | None = None   # --frame-count
    seed: int | None = None          # --seed

    # Output behavior
    overlay_mode: str | None = None  # --overlay
    no_color: bool = False           # --no-color
    quiet: bool = False              # --quiet
    verbose: bool = False            # --verbose
    json_output: bool = False        # --json
```

#### 4.3.2 Result Types

```python
@dataclass(frozen=True)
class RunResult:
    """Complete result from a comparison run."""
    success: bool
    screenshot_dir: Path | None = None
    slowpics_url: str | None = None
    report_path: Path | None = None
    frame_count: int = 0
    clips_processed: int = 0
    duration_seconds: float = 0.0
    cache_hit: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    phase_timings: dict[str, float] = field(default_factory=dict)
```

#### 4.3.3 Execute Function

```python
async def execute_run(
    request: RunRequest,
    deps: RunDependencies | None = None,
) -> RunResult:
    """
    Execute a complete comparison run.

    This is the primary entry point for the comparison pipeline.
    All phases execute in sequence; failures stop execution.

    Args:
        request: Run configuration (from CLI or programmatic call)
        deps: Injectable dependencies (for testing)

    Returns:
        RunResult with success status, outputs, and timing metrics

    Raises:
        FrameCompareError: Fatal error in any required phase
    """
```

#### 4.3.4 Phase Ordering (SSOT)

Phases execute in this exact order:

| Phase | Name | Required | Skip Condition | Failure Policy |
|:------|:-----|:---------|:---------------|:---------------|
| 1 | Preflight | ✓ Required | — | Fail fast |
| 2 | LoadSources | ✓ Required | — | Fail fast |
| 3 | FramePlan | ✓ Required | — | Fail fast |
| 4 | Analyze | Optional | `--skip-analysis` | Warn only |
| 5 | Align | Optional | No audio tracks | Warn only |
| 6 | Render | ✓ Required | — | Fail fast |
| 7 | Metadata | Optional | `--skip-metadata` | Warn only |
| 8 | Dovi | Optional | `--skip-dovi` | Warn only |
| 9 | Publish | Optional | `--no-upload` | Warn only |
| 10 | Report | Optional | `config.report.enable == False` | Warn only |

**Phase skip semantics:**

- **Skippable phases:** Log skip reason, set status to `SKIPPED`, continue
- **Warn-only failures:** Log warning, set status to `WARNED`, continue
- **Fail-fast failures:** Raise exception, stop pipeline, return `RunResult(success=False)`

> [!NOTE]
> **Tonemap phase skip/fail conditions:**
>
> Tonemapping is not a separate orchestration phase. It is part of the render pipeline and MUST be applied once per clip
> after load and before any frame extraction (see `render-module.md` §1.4).
>
> - If `source_info.is_hdr == False` OR `config.color.enable_tonemap == False`: tonemap is bypassed inside render.
> - If `source_info.is_hdr == True` AND `config.color.enable_tonemap == True` AND VapourSynth is unavailable: render MUST
>   fail fast with `RenderError(FC-4004)` (no silent FFmpeg fallback producing un-tonemapped outputs).

#### 4.3.5 CLI Flags → Config Overrides Mapping

| CLI Flag | Config Path | Override Behavior |
|:---------|:------------|:------------------|
| `--tm-preset` | `color.preset` | Replace if set |
| `--tm-target` | `color.target_nits` | Replace if set |
| `--tm-curve` | `color.tone_curve` | Replace if set |
| `--frame-count` | `analysis.frame_count` | Replace if set |
| `--seed` | `analysis.random_seed` | Replace if set |
| `--overlay` | `screenshots.overlay_mode` | Replace if set |
| `--no-cache` | — | `RunRequest.no_cache = True` |
| `--skip-analysis` | — | `RunRequest.skip_analysis = True` |
| `--no-upload` | `slowpics.auto_upload` | `auto_upload = False` |

**Override priority (SSOT):**

1. CLI flags (highest)
2. Config file
3. Built-in defaults (lowest)

#### 4.3.6 Input Discovery Rules

```python
def discover_inputs(
    input_dir: Path,
    patterns: list[str] = ["*.mkv", "*.mp4", "*.avi", "*.m2ts", "*.ts"],
) -> list[Path]:
    """
    Discover video files in input directory.

    Algorithm:
    1. Glob for all matching patterns
    2. Sort by filename (lexicographic, case-insensitive)
    3. Return sorted list

    Stable ordering guarantee:
        Same directory contents → same order, always.

    Labeling:
        First video is "Reference", subsequent are "Encode 1", "Encode 2", ... "Encode N".
        Label overrides via configuration are DEFERRED until a canonical `ConfigSchema` section exists.

    Raises:
        NoVideosFoundError (FC-3001): If no videos match patterns
    """
```

#### 4.3.7 Output Directory Layout

```text
{root}/
├── config/                    # Configuration
│   └── config.toml
├── comparison_videos/         # Input (default)
│   └── my-set/
│       ├── source.mkv
│       └── encode.mkv
├── screens/                   # Output screenshots
│   └── my-set/
│       ├── Reference_00100.png
│       ├── Reference_00500.png
│       ├── Encode_00100.png
│       └── Encode_00500.png
├── generated/                 # Cache and generated files
│   ├── my-set.compframes      # Metrics cache
│   ├── audio_offsets.toml     # Alignment cache
│   └── manual_overrides.toml  # VSPreview overrides
└── reports/                   # HTML reports
    └── my-set.html
```

**Cache interactions:**

| Cache File | Read On | Write On | Invalidation |
|:-----------|:--------|:---------|:-------------|
| `{name}.compframes` | Analyze phase start | Analyze phase end | `--no-cache` or config change |
| `audio_offsets.toml` | Align phase start | Align phase end | `--no-cache` or file change |
| `manual_overrides.toml` | Always | VSPreview session | Manual deletion only |

---

## 5. Implementation Details

### 5.1 Path Resolution

```python
def resolve_workspace(root: Path | None) -> Path:
    """
    Resolve workspace root directory.

    Priority:
    1. Explicit root parameter
    2. Current working directory if config/config.toml exists
    3. Search upward for config/config.toml
    4. Current working directory (fallback)
    """

def resolve_paths(config: ConfigSchema, root: Path) -> WorkspacePaths:
    """
    Resolve all workspace paths from config.

    Applies:
    - Path expansion (~/, env vars)
    - Relative path resolution from root
    - Default fallbacks for optional paths
    """
```

### 5.2 Phase Execution

```python
async def execute_phases(
    phases: list[Phase],
    context: RunContext,
    reporter: ProgressReporter,
) -> None:
    """
    Execute phases in sequence with error handling.

    For each phase:
    1. Check skip_condition
    2. Set status to RUNNING
    3. Execute phase with context
    4. Set status to COMPLETED/FAILED
    5. Report progress
    """
```

### 5.3 Resource Management

```python
@asynccontextmanager
async def run_context(
    config: ConfigSchema,
    deps: RunDependencies,
) -> AsyncIterator[RunContext]:
    """
    Manage resources for a run.

    Creates:
    - httpx.AsyncClient (if deps.http_client is None)
    - VapourSynth core
    - Temp directories

    Ensures cleanup on exit.
    """
```

---

## 6. Error Handling

> [!NOTE]
> All error classes are defined centrally in `frame_compare.errors` (see [errors-module.md](errors-module.md)).

**Error classes used by this module:**

| Error Class | Code | Usage |
|-------------|------|-------|
| `ConfigError` | FC-1xxx | Configuration invalid |
| `DependencyError` | FC-2xxx | Missing dependency |
| `InputError` | FC-3xxx | Invalid input |

```python
from frame_compare.errors import (
    FrameCompareError,
    ConfigError,
    DependencyError,
    InputError,
)
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

| Test Case | Input | Expected |
|-----------|-------|----------|
| Preflight success | Valid config dir | PreflightResult |
| Preflight missing config | Empty dir | ConfigNotFoundError |
| Doctor all pass | Full environment | DoctorReport(all_passed=True) |
| Phase skip | Condition met | Status.SKIPPED |

### 7.2 Integration Tests

| Test Case | Input | Expected |
|-----------|-------|----------|
| Full run | Sample videos | RunResult(success=True) |
| Run with missing VS | No VapourSynth | DependencyError |

---

## 8. AI Agent Implementation Prompt

```markdown
# Task: Implement Orchestration Module

## Context
Implement the orchestration module for Frame Compare 2.0.
This module coordinates preflight, doctor, and run execution.

## Files to Create
1. `src/frame_compare/orchestration/__init__.py` - Public exports
2. `src/frame_compare/orchestration/preflight.py` - Validation
3. `src/frame_compare/orchestration/doctor.py` - Diagnostics
4. `src/frame_compare/orchestration/phases.py` - Phase definitions
5. `src/frame_compare/orchestration/progress.py` - Reporters
6. `src/frame_compare/orchestration/runner.py` - Run execution

## Key Requirements
- Preflight validates config and resolves paths
- Doctor checks dependencies and reports status
- Runner coordinates phases with progress
- All errors use canonical error classes

## Dependencies
- Imports from config, errors, utils modules
- Uses httpx.AsyncClient for network
- Uses VapourSynth core for video

## Acceptance Criteria
- Preflight catches invalid configs
- Doctor reports pass/fail for each check
- Run executes all phases in order
- Progress reports work in quiet/json modes
```
