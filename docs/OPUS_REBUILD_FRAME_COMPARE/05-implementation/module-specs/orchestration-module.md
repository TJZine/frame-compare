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
> This module provides orchestration-specific reporters that implement that protocol.

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

# Orchestration-specific implementations
class RichProgressReporter:
    """Rich-based terminal progress reporter."""
    ...

class QuietProgressReporter:
    """Minimal progress reporter for --quiet mode."""
    ...

class JSONProgressReporter:
    """JSON-lines progress reporter for --json mode."""
    ...
```

### 3.4 Phase Types

```python
from enum import Enum, auto

class PhaseStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    SKIPPED = auto()
    FAILED = auto()

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
    4. Resolve all paths (input_dir, screenshots_dir, etc.)
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

### 4.3 Run Coordination

```python
async def execute_run(
    request: RunRequest,
    deps: RunDependencies | None = None,
) -> RunResult:
    """
    Execute a complete comparison run.
    
    Phases (see contracts/phase_ordering.yaml for canonical ordering):
    1. Preflight - Validate config, resolve paths
    2. LoadSources - Open video sources via VapourSynth/FFmpeg
    3. FramePlan - Generate deterministic frame selection
    4. Analyze - Calculate metrics, refine selection (skippable)
    5. Render - Extract frames and save screenshots
    6. Metadata - TMDB lookup (skippable, warn-only)
    7. Dovi - Dolby Vision extraction (skippable, warn-only)
    8. Publish - Upload to slow.pics (skippable)
    9. Report - Generate HTML report (skippable, warn-only)
    
    Args:
        request: Run configuration
        deps: Injectable dependencies (for testing)
        
    Returns:
        RunResult with outputs and metrics
        
    Raises:
        FrameCompareError: Any fatal phase fails
    """
```

---

## 5. Implementation Details

### 5.1 Path Resolution

```python
def resolve_workspace(root: Path | None) -> Path:
    """
    Resolve workspace root directory.
    
    Priority:
    1. Explicit root parameter
    2. Current working directory if config.toml exists
    3. Search upward for config.toml
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
