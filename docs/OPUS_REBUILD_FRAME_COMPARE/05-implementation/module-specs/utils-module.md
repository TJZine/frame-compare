# Utils Module Implementation Spec

> **Module:** `frame_compare.utils`
> **Version:** 1.0
> **Priority:** P0

---

## 1. Module Overview

The Utils module contains cross-cutting, low-level utilities shared by all layers.

### 1.1 Responsibilities

- Provide `Result` types for explicit error handling
- Provide `WorkspacePaths` dataclass for resolved workspace paths
- Provide `RunMetrics` dataclass for runtime timing collection
- Provide structured logging setup (structlog) + correlation IDs
- Provide progress-reporting protocol + implementations (Null, Rich, Log)
- Provide safe filesystem/path helpers (workspace containment)
- Provide subprocess wrappers enforcing `shell=False`

### 1.2 Import Constraints

`frame_compare.utils` must remain a **leaf** in the import graph:

- ✅ May import: `frame_compare.errors` and Python stdlib
- ❌ Must not import: `config`, `vs`, `analysis`, `render`, `services`, `runner`, `cli_entry`

---

## 2. Module Structure

```text
src/frame_compare/utils/
├── __init__.py      # Re-exports all public types
├── result.py        # Ok/Err/Result
├── types.py         # WorkspacePaths, RunMetrics
├── logging.py       # structlog configuration + correlation IDs
├── progress.py      # ProgressReporter protocol + implementations
├── paths.py         # Workspace-safe path helpers
└── subproc.py       # subprocess wrapper (shell=False)
```

---

## 3. Key Types

### 3.1 WorkspacePaths

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    """Resolved absolute paths for a workspace.

    These paths are computed once during preflight and passed through
    the execution context. All paths are guaranteed to be absolute
    and (for output paths) writable.

    Attributes:
        root: Workspace root directory (contains sentinel like .frame-compare)
        input_dir: Video input directory (may be same as root or subdir)
        screenshots_dir: Screenshot output directory
        generated_dir: Cache and generated files directory
        config_dir: Config and presets directory
        config_file: Path to config.toml (or None if using defaults)
    """
    root: Path
    input_dir: Path
    screenshots_dir: Path
    generated_dir: Path
    config_dir: Path
    config_file: Path | None

    @property
    def cache_dir(self) -> Path:
        """Directory for analysis cache files."""
        return self.generated_dir / "cache"

    @property
    def probe_cache_dir(self) -> Path:
        """Directory for video probe cache."""
        return self.generated_dir / "probe"
```

### 3.2 RunMetrics

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class RunMetrics:
    """Runtime metrics collection for tracking execution performance.

    Used by the orchestration layer to track phase timings and provide
    summary statistics at run completion.

    Attributes:
        start_time: When the run started
        phase_timings: Mapping of phase names to duration in seconds
        video_count: Number of videos processed
        frame_count: Total frames rendered
        cache_hit: Whether analysis cache was used
    """
    start_time: datetime = field(default_factory=datetime.now)
    phase_timings: dict[str, float] = field(default_factory=dict)
    video_count: int = 0
    frame_count: int = 0
    cache_hit: bool = False

    def record_phase(self, name: str, duration_seconds: float) -> None:
        """Record timing for a completed phase."""
        self.phase_timings[name] = duration_seconds

    @property
    def total_duration_seconds(self) -> float:
        """Total elapsed time from start."""
        return (datetime.now() - self.start_time).total_seconds()

    def to_dict(self) -> dict[str, object]:
        """Convert to JSON-serializable dictionary."""
        return {
            "start_time": self.start_time.isoformat(),
            "total_seconds": self.total_duration_seconds,
            "phase_timings": self.phase_timings,
            "video_count": self.video_count,
            "frame_count": self.frame_count,
            "cache_hit": self.cache_hit,
        }
```

---

## 4. Public API

### 4.1 Result Types

```python
from typing import TypeVar, Generic, Never
from dataclasses import dataclass

T = TypeVar("T")
E = TypeVar("E")

@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    """Successful result containing a value."""
    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        """Return the contained value."""
        return self.value

@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    """Failed result containing an error."""
    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> Never:
        """Raise the contained error."""
        if isinstance(self.error, Exception):
            raise self.error
        raise ValueError(self.error)

Result = Ok[T] | Err[E]
```

### 4.2 Progress Reporting

```python
from typing import Protocol
from contextlib import contextmanager

class ProgressReporter(Protocol):
    """Protocol for progress reporting across execution phases.

    Implementations can range from no-op (quiet mode) to rich
    terminal progress bars to simple log messages.
    """
    def start_phase(self, name: str, total: int) -> None:
        """Begin a new phase with expected item count."""
        ...  # pseudocode: protocol method, see implementations below

    def advance(self, amount: int = 1) -> None:
        """Update progress by specified amount."""
        ...  # pseudocode: protocol method, see implementations below

    def set_description(self, desc: str) -> None:
        """Update the current status description."""
        ...  # pseudocode: protocol method, see implementations below

    def complete_phase(self) -> None:
        """Mark current phase as complete."""
        ...  # pseudocode: protocol method, see implementations below

class NullProgressReporter:
    """No-op reporter for quiet/non-interactive runs."""

    def start_phase(self, name: str, total: int) -> None:
        pass

    def advance(self, amount: int = 1) -> None:
        pass

    def set_description(self, desc: str) -> None:
        pass

    def complete_phase(self) -> None:
        pass

class RichProgressReporter:
    """Rich-based progress bars for interactive terminals.

    Uses rich.progress.Progress with custom columns for phase name,
    progress bar, percentage, and ETA.
    """

    def __init__(self) -> None:
        from rich.progress import (
            Progress, SpinnerColumn, BarColumn,
            TaskProgressColumn, TimeRemainingColumn, TextColumn,
        )
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        )
        self._current_task: int | None = None

    def start_phase(self, name: str, total: int) -> None:
        if self._current_task is not None:
            self._progress.remove_task(self._current_task)
        self._progress.start()
        self._current_task = self._progress.add_task(name, total=total)

    def advance(self, amount: int = 1) -> None:
        if self._current_task is not None:
            self._progress.update(self._current_task, advance=amount)

    def set_description(self, desc: str) -> None:
        if self._current_task is not None:
            self._progress.update(self._current_task, description=desc)

    def complete_phase(self) -> None:
        if self._current_task is not None:
            self._progress.remove_task(self._current_task)
            self._current_task = None
        self._progress.stop()

class LogProgressReporter:
    """Log-based progress for non-interactive (CI) environments.

    Logs phase start/complete with structlog. Logs progress at
    10%, 25%, 50%, 75%, 100% milestones.
    """

    _MILESTONES = (0.10, 0.25, 0.50, 0.75, 1.00)

    def __init__(self) -> None:
        import structlog
        self._log = structlog.get_logger()
        self._name: str = ""
        self._total: int = 0
        self._current: int = 0
        self._next_milestone_idx: int = 0

    def start_phase(self, name: str, total: int) -> None:
        self._name = name
        self._total = max(total, 1)
        self._current = 0
        self._next_milestone_idx = 0
        self._log.info("phase_started", phase=name, total=total)

    def advance(self, amount: int = 1) -> None:
        self._current += amount
        progress = self._current / self._total

        while (self._next_milestone_idx < len(self._MILESTONES) and
               progress >= self._MILESTONES[self._next_milestone_idx]):
            pct = int(self._MILESTONES[self._next_milestone_idx] * 100)
            self._log.info("phase_progress", phase=self._name, percent=pct)
            self._next_milestone_idx += 1

    def set_description(self, desc: str) -> None:
        pass  # No-op for log-based output

    def complete_phase(self) -> None:
        self._log.info("phase_completed", phase=self._name)
```

### 4.3 Logging + Correlation IDs

```python
import logging
import structlog
from pathlib import Path
from uuid import uuid4
from contextvars import ContextVar

_run_id: ContextVar[str] = ContextVar("run_id", default="")

def new_run_id() -> str:
    """Generate and set a correlation ID for the current run.

    Returns the generated ID (format: first 8 chars of UUID4).
    Also binds the run_id into structlog contextvars so it appears in all logs.
    """
    run_id = uuid4().hex[:8]
    _run_id.set(run_id)
    structlog.contextvars.bind_contextvars(run_id=run_id)
    return run_id

def get_run_id() -> str:
    """Get the current run's correlation ID."""
    return _run_id.get() or "unknown"

def configure_logging(
    level: str = "INFO",
    format: str = "console",
    log_file: Path | None = None,
) -> None:
    """Configure structlog with either console or JSON output.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Case-insensitive. Unknown values fall back to INFO.
        format: "console" for human-readable, "json" for structured.
               Unknown values fall back to "console".
        log_file: Optional file path for logging output (not yet implemented).

    Notes:
        - Level filtering uses stdlib logging level constants (10, 20, 30, 40, 50).
        - Unknown level strings silently fall back to INFO (20).
        - Unknown format strings silently fall back to console renderer.
        - Safe to call multiple times; later calls reconfigure structlog globally.
    """
    # Map level string to logging constant; fallback to INFO for unknown
    level_num = getattr(logging, level.upper(), logging.INFO)

    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level_num),
    )
```

### 4.4 Path Safety

```python
from pathlib import Path
from frame_compare.errors import PathEscapesRootError

def resolve_within_root(root: Path, candidate: Path) -> Path:
    """Resolve `candidate` and ensure it is within `root`.

    Handles both relative and absolute paths. Relative paths are
    resolved relative to `root`.

    Args:
        root: Workspace root directory (must be absolute)
        candidate: Path to validate (may be relative or absolute)

    Returns:
        Resolved absolute path guaranteed to be under root

    Raises:
        PathEscapesRootError: when the resolved path escapes the root
    """
    if not root.is_absolute():
        root = root.resolve()

    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (root / candidate).resolve()

    try:
        resolved.relative_to(root)
    except ValueError:
        raise PathEscapesRootError(root, candidate)

    return resolved

def ensure_directory(path: Path, *, parents: bool = True) -> Path:
    """Ensure directory exists, creating if necessary.

    Returns the path for fluent usage.
    """
    path.mkdir(parents=parents, exist_ok=True)
    return path
```

### 4.5 Subprocess Wrapper

```python
import subprocess
from collections.abc import Sequence
from pathlib import Path
from frame_compare.errors import FFmpegError, DependencyError

def run_subprocess(
    argv: Sequence[str],
    *,
    timeout_seconds: float | None = None,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    """Run a subprocess with `shell=False` and bytes capture.

    Security:
    - Never pass user data through a shell
    - Require argv list form

    Args:
        argv: Command and arguments as list
        timeout_seconds: Optional timeout
        cwd: Working directory
        check: If True (default), raise on non-zero exit

    Returns:
        CompletedProcess with stdout/stderr as bytes

    Raises:
        DependencyError: If check=True and process returns non-zero
        subprocess.TimeoutExpired: On timeout
    """
    try:
        result = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            timeout=timeout_seconds,
            cwd=cwd,
        )
    except FileNotFoundError:
        cmd = argv[0] if argv else "unknown"
        raise DependencyError(f"Command not found: {cmd}")

    if check and result.returncode != 0:
        cmd = argv[0] if argv else "unknown"
        stderr_text = result.stderr.decode("utf-8", errors="replace")[:500]
        raise DependencyError(f"{cmd} failed: {stderr_text}")

    return result
```

---

## 5. Error Handling

Utils should raise typed errors from `frame_compare.errors`:

| Scenario | Error Type | Code |
|----------|------------|------|
| Path escapes root | `PathEscapesRootError` | FC-3009 |
| Command not found | `DependencyError` | FC-2xxx |
| Subprocess failure | `DependencyError` or `ProcessingError` | Context-dependent |

---

## 6. Testing Strategy

### 6.1 Unit Tests

```python
def test_result_ok_unwrap():
    result: Result[int, str] = Ok(42)
    assert result.unwrap() == 42

def test_result_err_unwrap_raises():
    result: Result[int, ValueError] = Err(ValueError("oops"))
    with pytest.raises(ValueError):
        result.unwrap()

def test_resolve_within_root_relative_path(tmp_path):
    result = resolve_within_root(tmp_path, Path("subdir/file.txt"))
    assert result == tmp_path / "subdir" / "file.txt"

def test_resolve_within_root_traversal_rejected(tmp_path):
    with pytest.raises(PathEscapesRootError):
        resolve_within_root(tmp_path, Path("../escape"))

def test_run_subprocess_shell_false():
    result = run_subprocess(["echo", "hello"], check=False)
    assert result.returncode == 0

def test_run_metrics_phase_timing():
    metrics = RunMetrics()
    metrics.record_phase("analysis", 1.5)
    assert metrics.phase_timings["analysis"] == 1.5

def test_workspace_paths_cache_dir():
    paths = WorkspacePaths(
        root=Path("/workspace"),
        input_dir=Path("/workspace/videos"),
        screenshots_dir=Path("/workspace/screenshots"),
        generated_dir=Path("/workspace/generated"),
        config_dir=Path("/workspace/config"),
        config_file=Path("/workspace/config/config.toml"),
    )
    assert paths.cache_dir == Path("/workspace/generated/cache")
```

---

## 7. AI Agent Implementation Prompt

```markdown
# Task: Implement Utils Module

## Context
Implement the utils module for Frame Compare 2.0.
This is a foundation module paired with errors.

## Files to Create
1. `src/frame_compare/utils/__init__.py` - Re-exports
2. `src/frame_compare/utils/result.py` - Ok/Err/Result
3. `src/frame_compare/utils/types.py` - WorkspacePaths, RunMetrics
4. `src/frame_compare/utils/logging.py` - structlog config
5. `src/frame_compare/utils/progress.py` - ProgressReporter + implementations
6. `src/frame_compare/utils/paths.py` - resolve_within_root, ensure_directory
7. `src/frame_compare/utils/subproc.py` - run_subprocess

## Key Requirements
- Result types with is_ok/is_err/unwrap methods
- WorkspacePaths frozen dataclass with cache_dir property
- RunMetrics mutable dataclass for timing
- ProgressReporter Protocol with 3 implementations
- Path safety with traversal rejection
- Subprocess with shell=False enforcement

## Import Constraints
- May import: frame_compare.errors, Python stdlib, structlog, rich
- Must NOT import any other frame_compare modules

## Acceptance Criteria
- `.venv/bin/pyright --warnings src/frame_compare/utils/` passes
- All unit tests pass
- Path traversal attacks are rejected
```
