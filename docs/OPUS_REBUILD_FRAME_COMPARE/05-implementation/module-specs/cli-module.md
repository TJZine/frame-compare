# CLI & Orchestration Module Implementation Spec

> **Module:** `frame_compare.cli`, `frame_compare.runner`
> **Version:** 1.0
> **Priority:** P0

---

## 1. Module Overview

The CLI & Orchestration module provides the command-line interface and coordinates the execution pipeline.

### 1.1 Responsibilities

- Parse command-line arguments
- Load and validate configuration
- Orchestrate the comparison pipeline
- Report progress and results
- Handle errors gracefully

### 1.2 Module Structure

> [!IMPORTANT]
> **Canonical ownership:** `cli_entry.py` and `runner.py` live at package root.
> All preflight/doctor/phases/context components live inside `orchestration/`.
> `ProgressReporter` protocol is defined in `utils/progress.py`.

```text
src/frame_compare/
├── cli_entry.py           # Typer CLI commands
├── runner.py              # High-level run() entry point
└── orchestration/         # All workflow coordination
    ├── __init__.py        # Public exports
    ├── coordinator.py     # Workflow coordinator + execute_run()
    ├── preflight.py       # Pre-run validation
    ├── doctor.py          # Diagnostic checks
    ├── phases.py          # Pipeline phases
    ├── context.py         # Runtime context
    ├── probe_cache.py     # Clip probe snapshot cache I/O + keying
    ├── probe_props.py     # Clip probe prop preservation helpers
    └── progress.py        # Progress reporter implementations
```

---

## 2. CLI Entry Point

### 2.1 Command Structure

```python
"""CLI commands using Typer for type-hint-native interface."""

import typer
from pathlib import Path

app = typer.Typer(
    name="frame-compare",
    help="Video frame comparison and HDR tonemapping tool",
    no_args_is_help=True,
)

@app.command()
def run(
    root: Path = typer.Option(
        ".", "--root", "-r",
        help="Workspace root directory",
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c",
        help="Configuration file path",
    ),
    input_dir: Path | None = typer.Option(
        None, "--input", "-i",
        help="Input video directory",
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache",
        help="Ignore cached metrics",
    ),
    from_cache_only: bool = typer.Option(
        False, "--from-cache-only",
        help="Use only cached snapshot",
    ),
    no_upload: bool = typer.Option(
        False, "--no-upload",
        help="Skip slow.pics upload",
    ),
    tm_preset: str | None = typer.Option(
        None, "--tm-preset",
        help="Tonemap preset override",
    ),
    tm_target: int | None = typer.Option(
        None, "--tm-target",
        help="Target nits for tonemapping (e.g., 203)",
    ),
    tm_curve: str | None = typer.Option(
        None, "--tm-curve",
        help="Tone curve selection (bt2390, reinhard, spline)",
    ),
    frame_count: int | None = typer.Option(
        None, "--frame-count", "-n",
        help="Number of frames to select",
    ),
    seed: int | None = typer.Option(
        None, "--seed",
        help="Random seed for frame selection",
    ),
    overlay: str | None = typer.Option(
        None, "--overlay",
        help="Overlay mode (none, minimal, standard, diagnostic)",
    ),
    skip_analysis: bool = typer.Option(
        False, "--skip-analysis",
        help="Skip frame analysis; use uniform sampling with seed",
    ),
    skip_metadata: bool = typer.Option(
        False, "--skip-metadata",
        help="Skip TMDB metadata lookup",
    ),
    skip_dovi: bool = typer.Option(
        False, "--skip-dovi",
        help="Skip Dolby Vision extraction",
    ),
    force_interactive_alignment: bool = typer.Option(
        False, "--force-interactive-alignment",
        help="Recompute audio offsets and re-run interactive VSPreview confirmation for each comparison clip",
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="Output results as JSON",
    ),
    no_color: bool = typer.Option(
        False, "--no-color",
        help="Disable colored output",
    ),
    write_config: bool = typer.Option(
        False, "--write-config",
        help="Write resolved config to file and exit",
    ),
    diagnose_paths: bool = typer.Option(
        False, "--diagnose-paths",
        help="Print path diagnostics as JSON and exit",
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q",
        help="Suppress non-essential output",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Enable debug logging",
    ),
) -> None:
    """Execute the comparison pipeline."""
    # REQUIRED STEPS (normative):
    # 1. Build a RunRequest from CLI args (no implicit defaults beyond Typer defaults).
    # 1.1 If `--force-interactive-alignment` is set, it MUST enable interactive alignment:
    #     - Set `audio_alignment.use_vspreview = True` (even if config disabled it)
    #     - Set `audio_alignment.force_interactive = True`
    # 2. Call `frame_compare.runner.run(request, dependencies=None) -> RunResult`.
    # 3. If a `FrameCompareError` is raised, map to exit code via `handle_error()` and exit.
    # 4. If `RunResult.success` is False, exit with `ExitCode.PROCESSING_ERROR`.
    raise NotImplementedError

@app.command()
def wizard() -> None:
    """Interactive configuration setup."""
    # REQUIRED STEPS (normative):
    # 1. Prompt user for minimal config inputs (paths + core options).
    # 2. Write config to `{root}/config/config.toml` and exit 0.
    # This command is PLANNED; do not implement partially.
    raise NotImplementedError

@app.command()
def doctor(
    json_output: bool = typer.Option(
        False, "--json",
        help="Output as JSON",
    ),
) -> None:
    """Check system dependencies."""
    # REQUIRED STEPS (normative):
    # 1. Call `frame_compare.orchestration.run_doctor(checks=None, reporter=None) -> DoctorReport`.
    # 2. If `--json` is set, print machine-readable JSON.
    # 3. Otherwise, print a human-readable report.
    # 4. Exit 0 unless a critical dependency is missing (then ExitCode.DEPENDENCY_ERROR).
    raise NotImplementedError

preset_app = typer.Typer(
    name="preset",
    help="Manage configuration presets.",
    no_args_is_help=True,
)
app.add_typer(preset_app, name="preset")

@preset_app.command("list")
def preset_list() -> None:
    """List available presets."""
    # REQUIRED STEPS (normative):
    # 1. List preset files from the canonical presets directory (SSOT path).
    # 2. Print them in deterministic order (lexicographic, case-insensitive).
    raise NotImplementedError

@preset_app.command("apply")
def preset_apply(name: str) -> None:
    """Apply a preset to configuration."""
    # REQUIRED STEPS (normative):
    # 1. Load the named preset.
    # 2. Merge into current config using deterministic precedence rules.
    # 3. Write updated config and exit 0.
    raise NotImplementedError

@preset_app.command("save")
def preset_save(name: str) -> None:
    """Save current configuration as preset."""
    # REQUIRED STEPS (normative):
    # 1. Load current config.
    # 2. Write to presets/{name}.toml with stable key ordering.
    raise NotImplementedError
```

### 2.2 Exit Codes

```python
from enum import IntEnum

class ExitCode(IntEnum):
    SUCCESS = 0
    GENERAL_ERROR = 1
    CONFIG_ERROR = 2
    DEPENDENCY_ERROR = 3
    INPUT_ERROR = 4
    PROCESSING_ERROR = 5
    NETWORK_ERROR = 6
    INTERRUPTED = 130
```

---

## 3. Runner

### 3.1 Types

```python
@dataclass(frozen=True)
class RunRequest:
    """Configuration for a comparison run."""
    root: Path
    config_path: Path | None = None
    input_dir: Path | None = None
    no_cache: bool = False
    from_cache_only: bool = False
    no_upload: bool = False
    skip_analysis: bool = False
    skip_metadata: bool = False
    skip_dovi: bool = False
    force_interactive_alignment: bool = False
    tm_preset: str | None = None
    tm_target_nits: int | None = None
    tm_curve: str | None = None
    frame_count: int | None = None
    seed: int | None = None
    overlay_mode: str | None = None
    json_output: bool = False
    no_color: bool = False
    quiet: bool = False
    verbose: bool = False

@dataclass(frozen=True)
class RunResult:
    """Result of a comparison run."""
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

@dataclass
class RunContext:
    """Runtime context for a run.

    Note: Import types from:
    - WorkspacePaths from frame_compare.utils.types
    - RunMetrics from frame_compare.utils.types
    - ProgressReporter from frame_compare.utils.progress
    - ConfigSchema from frame_compare.config.schema
    """
    request: RunRequest
    config: ConfigSchema
    workspace: WorkspacePaths
    progress: ProgressReporter
    metrics: RunMetrics
    log: structlog.BoundLogger
```

**Interactive alignment implication (SSOT):**

When `RunRequest.force_interactive_alignment` is `True`, CLI overrides MUST ensure:

- `audio_alignment.force_interactive = True`
- `audio_alignment.use_vspreview = True`

### 3.2 Public API

```python
def run(
    request: RunRequest,
    dependencies: RunDependencies | None = None,
) -> RunResult:
    """
    Execute the comparison pipeline.

    Phases:
    1. Preflight - Validate config, find videos
    2. LoadSources - Load video sources and detect HDR
    3. FramePlan - Select frames (metric-based or skip-analysis)
    4. Analyze - Calculate/load metrics (optional; skipped when request.skip_analysis)
    5. Align - Align audio (optional)
    6. Render - Generate screenshots (includes tonemap gating per render-module.md §1.4)
    7. Metadata - Extract metadata (optional; skipped when request.skip_metadata)
    8. Dovi - Extract Dolby Vision info (optional; skipped when request.skip_dovi)
    9. Publish - Upload to slow.pics (optional; skipped when request.no_upload)
    10. Report - Generate HTML report (optional; gated by config.report.enable)

    Args:
        request: Run configuration
        dependencies: Optional injected dependencies

    Returns:
        RunResult with success status and outputs
    """
```

### 3.3 Dependency Injection Protocols

> **Purpose:** These protocols define interfaces for dependency injection, enabling testability and flexibility.
>
> [!NOTE]
> `VSLoader` is canonically defined in `frame_compare.vs` (see [vs-module.md](vs-module.md)).
> It is imported here for use in `RunDependencies`.

```python
from typing import Protocol
from frame_compare.vs import VSLoader  # Import from vs module

class FFmpegRunner(Protocol):
    """Protocol for running FFmpeg commands."""

    def extract_frame(
        self,
        video: Path,
        frame_num: int,
        output: Path,
    ) -> None:
        """Extract a single frame as PNG."""
        raise NotImplementedError

    def probe_hdr(self, video: Path) -> HDRMetadata | None:
        """Probe video for HDR metadata."""
        raise NotImplementedError

class DefaultFFmpegRunner:
    """Default FFmpeg runner implementation."""
    # Default implementation MUST:
    # - raise FFmpegNotFoundError if ffmpeg/ffprobe is missing
    # - raise FFmpegError on non-zero exit
    # - never perform silent HDR->SDR conversion when tonemap is required
    pass
```

### 3.4 RunDependencies

```python
@dataclass
class RunDependencies:
    """Injectable dependencies for testability.

    Note on http_client lifecycle:
    - If provided, caller owns lifecycle (must call aclose())
    - If None, runner creates client with `async with httpx.AsyncClient()`
    - See: https://www.python-httpx.org/async/#opening-and-closing-clients
    """
    vs_loader: VSLoader | None = None
    ffmpeg_runner: FFmpegRunner | None = None
    http_client: httpx.AsyncClient | None = None
    progress: ProgressReporter | None = None
    clock: Callable[[], datetime] = field(default=datetime.now)

    def get_vs_loader(self) -> VSLoader:
        return self.vs_loader or DefaultVSLoader()

    def get_ffmpeg_runner(self) -> FFmpegRunner:
        return self.ffmpeg_runner or DefaultFFmpegRunner()
```

---

## 4. Orchestration

### 4.1 Workflow Coordinator

```python
class WorkflowCoordinator:
    """Coordinates the comparison pipeline."""

    def __init__(
        self,
        context: RunContext,
        dependencies: RunDependencies,
    ):
        self.context = context
        self.deps = dependencies
        self.phases: list[Phase] = []

    def register_phase(self, phase: Phase) -> None:
        """Register a pipeline phase."""
        self.phases.append(phase)

    async def execute(self) -> RunResult:
        """Execute all registered phases in order."""
        for phase in self.phases:
            try:
                await phase.execute(self.context)
            except PhaseError as e:
                return self._handle_phase_error(e)
        return self._build_result()
```

### 4.2 Pipeline Phases

```python
class Phase(Protocol):
    """Protocol for pipeline phases."""

    name: str

    async def execute(self, context: RunContext) -> None:
        """Execute the phase."""
        raise NotImplementedError

class PreflightPhase(Phase):
    """Validate configuration and find videos."""
    name = "preflight"

class AnalysisPhase(Phase):
    """Calculate metrics and select frames."""
    name = "analysis"

class AlignmentPhase(Phase):
    """Align audio between clips."""
    name = "alignment"

class RenderPhase(Phase):
    """Generate screenshots."""
    name = "render"

class PublishPhase(Phase):
    """Upload to slow.pics."""
    name = "publish"

class ReportPhase(Phase):
    """Generate HTML report."""
    name = "report"
```

---

## 5. Preflight

### 5.1 Public API

```python
def prepare_preflight(
    request: RunRequest,
) -> tuple[ConfigSchema, WorkspacePaths]:
    """
    Validate configuration and resolve paths.

    Steps:
    1. Resolve workspace root
    2. Load configuration file
    3. Validate configuration
    4. Resolve all paths
    5. Verify input directory exists

    Returns:
        Tuple of (config, workspace_paths)

    Raises:
        ConfigError: If configuration invalid
        InputError: If input directory missing
    """

def resolve_workspace_root(
    explicit_root: Path | None,
) -> Path:
    """
    Resolve workspace root directory.

    Priority:
    1. Explicit --root argument
    2. FRAME_COMPARE_ROOT environment variable
    3. Current working directory
    """

def find_videos(
    input_dir: Path,
    patterns: list[str] = ["*.mkv", "*.mp4", "*.avi", "*.m2ts", "*.ts"],
) -> list[Path]:
    """
    Find video files in input directory.

    Raises:
        NoVideosFoundError: If no videos found
    """
```

---

## 6. Doctor

### 6.1 Types

```python
class CheckStatus(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

@dataclass
class CheckResult:
    name: str
    category: str
    status: CheckStatus
    message: str
    details: dict[str, object] | None = None
```

### 6.2 Public API

```python
def collect_checks() -> list[Callable[[], CheckResult]]:
    """Return list of check functions."""
    return [
        check_python_version,
        check_vapoursynth,
        check_libplacebo,
        check_lsmas,
        check_ffmpeg,
        check_dovi_tool,
        check_config_exists,
        check_config_valid,
        check_input_dir,
        check_slowpics_reachable,
        check_tmdb_api_key,
    ]

def run_checks(
    checks: list[Callable[[], CheckResult]],
) -> list[CheckResult]:
    """Execute all checks and return results."""

def format_results(
    results: list[CheckResult],
    json_output: bool = False,
) -> str:
    """Format check results for display."""
```

---

## 7. Progress Reporting

> **Canonical Location:** `frame_compare.utils.progress`
>
> The CLI module imports and uses progress reporters defined in the utils module.

```python
# Import from canonical location
from frame_compare.utils.progress import (
    ProgressReporter,      # Protocol defining progress interface
    RichProgressReporter,  # Rich-based beautiful terminal output
    NullProgressReporter,  # No-op for quiet mode
    LogProgressReporter,   # Log-based for non-interactive mode
)

# Usage in runner
def create_reporter(quiet: bool, verbose: bool) -> ProgressReporter:
    """Create appropriate reporter based on CLI flags."""
    if quiet:
        return NullProgressReporter()
    if not sys.stdout.isatty():
        return LogProgressReporter()
    return RichProgressReporter()
```

---

## 8. Error Handling

> [!NOTE]
> All error classes are defined centrally in `frame_compare.errors` (see [errors-module.md](errors-module.md)).

**Error classes used by this module:**

| Error Class | Code | Usage |
|-------------|------|-------|
| `ConfigError` | FC-1xxx | Configuration and CLI argument errors |
| `InputError` | FC-3xxx | Input validation errors |
| `DependencyError` | FC-2xxx | Missing dependency errors |

> [!NOTE]
> There is no separate `CLIError` class. CLI-layer errors use existing error classes
> (`ConfigError`, `InputError`, `DependencyError`, `ProcessingError`, `NetworkError`). The exit code is determined by the error category.

```python
from frame_compare.errors import (
    FrameCompareError,
    ConfigError,
    DependencyError,
    InputError,
    ProcessingError,
    NetworkError,
)

def handle_error(error: Exception) -> int:
    """
    Convert exception to exit code and display message.

    Maps:
    - ConfigError -> ExitCode.CONFIG_ERROR
    - DependencyError -> ExitCode.DEPENDENCY_ERROR
    - InputError -> ExitCode.INPUT_ERROR
    - ProcessingError -> ExitCode.PROCESSING_ERROR
    - NetworkError -> ExitCode.NETWORK_ERROR
    - Other -> ExitCode.GENERAL_ERROR
    """
```

---

## 9. Testing Strategy

### 9.1 CLI Tests

```python
from typer.testing import CliRunner

runner = CliRunner()

def test_run_help():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "Execute the comparison pipeline" in result.output

def test_run_no_config(tmp_path):
    result = runner.invoke(app, ["run", "--root", str(tmp_path)])
    assert result.exit_code == ExitCode.CONFIG_ERROR

def test_doctor_json():
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "checks" in data
```

### 9.2 Runner Tests

```python
def test_run_full_pipeline(mock_dependencies, sample_workspace):
    request = RunRequest(root=sample_workspace)
    result = run(request, dependencies=mock_dependencies)
    assert result.success
    assert result.screenshot_dir.exists()

def test_run_cache_hit(mock_dependencies, cached_workspace):
    request = RunRequest(root=cached_workspace)
    result = run(request, dependencies=mock_dependencies)
    assert result.cache_hit
```

---

## 10. AI Agent Implementation Prompt

```markdown
# Task: Implement CLI & Orchestration Module

## Context
Implement the CLI entry point and pipeline orchestration for Frame Compare 2.0.

## Files to Create
1. `src/frame_compare/cli_entry.py` - Typer CLI commands
2. `src/frame_compare/runner.py` - Pipeline runner
3. `src/frame_compare/orchestration/__init__.py`
4. `src/frame_compare/orchestration/coordinator.py` - Workflow coordinator + `execute_run()`
5. `src/frame_compare/orchestration/preflight.py` - Preflight validation
6. `src/frame_compare/orchestration/doctor.py` - Dependency diagnostics
7. `src/frame_compare/orchestration/phases.py` - Phase definitions
8. `src/frame_compare/orchestration/context.py` - Runtime context
9. `src/frame_compare/orchestration/progress.py` - Progress reporter implementations
10. `src/frame_compare/orchestration/probe_cache.py` - Probe snapshot cache helpers
11. `src/frame_compare/orchestration/probe_props.py` - Probe prop preservation helpers

## Key Requirements
- Typer for CLI (not Click)
- Dependency injection for testability
- Phase-based pipeline execution
- Rich progress reporting
- Structured error handling with exit codes

## Testing
- Use CliRunner for CLI tests
- Mock all dependencies for unit tests
- Full integration test with sample workspace

## Acceptance Criteria
- `frame-compare run --help` shows all options
- `frame-compare doctor` detects missing dependencies
- Pipeline executes all phases in order
- Errors map to correct exit codes
```
