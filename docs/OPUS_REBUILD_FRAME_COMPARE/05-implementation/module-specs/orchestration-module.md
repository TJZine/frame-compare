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

### 3.5 Runtime Context Types (SSOT)

The orchestration layer MUST maintain a canonical, per-clip state object (2.0 analogue of legacy `ClipPlan`) so that
all phases consume the same view of:

- input identity + labels
- probe snapshot metadata (fps/frames/HDR, etc.)
- trim/alignment state (including trim-first normalization invariants)
- hydrated render sources (VS clip, ffmpeg fallback decisions)

This prevents drift where individual modules invent their own partial “clip model”.

```python
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

from frame_compare.vs.types import HDRMetadata


@dataclass(frozen=True)
class ClipFingerprint:
    """Stable fingerprint for cache invalidation.

    This is intentionally simple to compute without opening VS.
    """

    path: Path
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True)
class ClipProbeSnapshot:
    """Cached, expensive-to-derive metadata about a clip (pre-trim).

    Invariants:
    - `num_frames` and `fps` refer to the untrimmed source.
    - HDR detection uses *untrimmed* frame props (frame 0 snapshot).
    - Persisted props are a *filtered subset* needed for downstream correctness.
      Do not attempt to persist arbitrary VapourSynth prop types.
    """

    fingerprint: ClipFingerprint
    width: int
    height: int
    num_frames: int
    fps: Fraction
    is_hdr: bool
    hdr_metadata: HDRMetadata | None = None

    # Minimal, portable prop snapshot for HDR/tonemap parity.
    # Keys SHOULD include mastering display / content light level values if present.
    preserved_frame_props: dict[str, str | int | float] = field(default_factory=dict)
    tonemap_prop_keys: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ClipTrimState:
    """Effective temporal window for a clip in frames (applied trims only).

    `trim_start_frames` MUST be non-negative (trim-first invariant).
    """

    trim_start_frames: int = 0
    trim_end_frame_inclusive: int | None = None


@dataclass(frozen=True)
class ClipAlignmentState:
    """Alignment state expressed in signed, comparison-relative-to-reference offsets."""

    reference_stem: str
    comparison_stem: str
    relative_offset_frames: int
    source: str  # "manual" | "cached" | "computed"


@dataclass(frozen=True)
class ClipState:
    """Canonical per-clip state across orchestration phases (legacy ClipPlan analogue)."""

    path: Path
    label: str
    probe: ClipProbeSnapshot

    # FPS hierarchy (SSOT):
    # - source_fps: from probe
    # - forced_fps: user override (optional; may be added later)
    # - effective_fps: forced if set else source_fps
    source_fps: Fraction
    effective_fps: Fraction

    trim: ClipTrimState = field(default_factory=ClipTrimState)
    alignment: ClipAlignmentState | None = None

    def with_trim(self, *, trim_start_frames: int, trim_end_frame_inclusive: int | None) -> "ClipState":
        """Return a new ClipState with updated trim window (never mutates in place)."""
        if trim_start_frames < 0:
            raise ValueError("trim_start_frames must be >= 0 (trim-first invariant)")
        return replace(
            self,
            trim=ClipTrimState(
                trim_start_frames=trim_start_frames,
                trim_end_frame_inclusive=trim_end_frame_inclusive,
            ),
        )


@dataclass
class RunContext:
    """Runtime context shared across phases.

    Note: This object may carry non-deterministic resources (http clients, VS core),
    but per-clip state SHOULD remain immutable (`ClipState`).
    """

    config: ConfigSchema
    workspace: WorkspacePaths
    reference: ClipState
    comparisons: list[ClipState]
    reporter: ProgressReporter | None = None
```

**ClipState invariants (must hold at all times):**

- `ClipState.probe` describes the *untrimmed* source.
- `ClipState.trim.trim_start_frames >= 0` (no padding invariant).
- All signed alignment offsets are stored as “comparison relative to reference”, but applied trims are computed via
  the trim-first normalization algorithm (services-module.md §2.5).

**Probe caching (SSOT):**

- The orchestration layer SHOULD persist `ClipProbeSnapshot` to disk to avoid repeated expensive probing on reruns.
- Cache entries MUST be invalidated when `ClipFingerprint` changes.
- Cache write/read MUST be deterministic (stable key ordering).

**Probe cache keying (SSOT, legacy-informed):**

Legacy implementations often included mutable trim state in probe cache keys because the “probe” was performed on the
already-trimmed graph. In 2.0, `ClipProbeSnapshot` is explicitly **pre-trim**, so trim changes MUST NOT invalidate the
probe cache.

Compute a deterministic cache key from the immutable fingerprint only:

```python
def compute_probe_cache_key(fingerprint: ClipFingerprint) -> str:
    """Return a stable key for clip probe cache entries."""
    payload = {
        "path": str(fingerprint.path),
        "size_bytes": fingerprint.size_bytes,
        "mtime_ns": fingerprint.mtime_ns,
        "schema_version": 1,
    }
    # json.dumps(..., sort_keys=True, separators=(",", ":"))
    # then blake2s hex digest of UTF-8 bytes
```

**Probe cache format (SSOT):**

- File: `{workspace.generated_dir}/clip_probe.toml`
- Top-level keys:
  - `version = "1"`
  - `["<probe_cache_key>"]` tables for each clip
- Each entry MUST store: path, size_bytes, mtime_ns, width, height, num_frames, fps_num, fps_den, is_hdr
- If HDR, store: mastering_display, max_cll, max_fall (and any other fields needed by `HDRMetadata`)
- `preserved_frame_props` MUST be limited to JSON/TOML-safe primitives (`str|int|float`)

**Tonemap prop key preservation (SSOT):**

When probing, record a list of “tonemap-related” prop keys to help downstream overlay/debug output remain stable even
if later trimming/filtering strips some props. This is a parity feature from legacy ClipPlan.

- Normalize prop keys to lower-case and strip leading underscores.
- Include keys whose normalized base name matches:
  - `masteringdisplayprimaries`, `masteringdisplayluminance`
  - `contentlightlevelmax`, `contentlightlevelaverage`
- Additionally include any keys with a normalized prefix of:
  - `masteringdisplay`
  - `contentlightlevel`

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

### 4.3 Progress Reporter Selection

```python
def select_reporter(
    quiet: bool = False,
    json_output: bool = False,
    force_tty: bool | None = None,
) -> ProgressReporter:
    """
    Select the appropriate ProgressReporter based on output mode.

    Selection algorithm (priority order):
    1. If quiet=True: return NullProgressReporter()
    2. If json_output=True: return LogProgressReporter()
    3. If force_tty is not None:
       - If force_tty=True: return RichProgressReporter()
       - If force_tty=False: return LogProgressReporter()
    4. Else detect TTY via sys.stdout.isatty():
       - If TTY: return RichProgressReporter()
       - Else: return LogProgressReporter()

    Args:
        quiet: Suppress all progress output (--quiet flag)
        json_output: Machine-readable output mode (--json flag)
        force_tty: Override TTY detection (for testing or explicit control)

    Returns:
        ProgressReporter instance matching the output mode
    """
```

#### 4.3.1 Progress Reporter Tests

| Test Case | Input | Expected |
|-----------|-------|----------|
| `test_select_reporter_quiet_returns_null()` | `quiet=True` | `NullProgressReporter` |
| `test_select_reporter_json_returns_log()` | `json_output=True` | `LogProgressReporter` |
| `test_select_reporter_force_tty_true_returns_rich()` | `force_tty=True` | `RichProgressReporter` |
| `test_select_reporter_force_tty_false_returns_log()` | `force_tty=False` | `LogProgressReporter` |
| `test_select_reporter_tty_detection_interactive(monkeypatch)` | `sys.stdout.isatty()=True` | `RichProgressReporter` |
| `test_select_reporter_tty_detection_non_interactive(monkeypatch)` | `sys.stdout.isatty()=False` | `LogProgressReporter` |
| `test_select_reporter_quiet_takes_precedence_over_json()` | `quiet=True, json_output=True` | `NullProgressReporter` |
| `test_select_reporter_quiet_takes_precedence_over_force_tty()` | `quiet=True, force_tty=True` | `NullProgressReporter` |
| `test_select_reporter_json_takes_precedence_over_force_tty()` | `json_output=True, force_tty=True` | `LogProgressReporter` |

### 4.4 Run Coordination

#### 4.4.1 Request Types

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

#### 4.4.2 Result Types

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

#### 4.4.3 Execute Function

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

#### 4.4.4 Phase Ordering (SSOT)

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

> [!NOTE]
> **Align phase trim-first invariant (no padding):**
>
> Audio alignment offsets are stored and confirmed as signed **comparison-relative-to-reference** frame offsets.
> The pipeline MUST NOT pad any clip to realize a negative offset. Instead, it MUST normalize signed relative offsets
> into per-clip non-negative `trim_start_frames` by shifting the global baseline (services-module.md §2.5).

#### 4.4.5 CLI Flags → Config Overrides Mapping

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
| `--force-interactive-alignment` | `audio_alignment.force_interactive` | Replace if set (and MUST imply `audio_alignment.use_vspreview = True`) |
| `--no-upload` | `slowpics.auto_upload` | `auto_upload = False` |

**Override priority (SSOT):**

1. CLI flags (highest)
2. Config file
3. Built-in defaults (lowest)

#### 4.4.6 Input Discovery Rules

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

#### 4.4.7 Output Directory Layout

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
│   ├── clip_probe.toml        # Probe snapshot cache (fps/frames/HDR)
│   ├── audio_offsets.toml     # Alignment cache
│   ├── manual_overrides.toml  # VSPreview overrides
│   └── vspreview_sessions/    # Debug-only generated scripts (optional)
│       └── vspreview_Reference_20260104T120000Z.py
└── reports/                   # HTML reports
    └── my-set.html
```

**Cache interactions:**

| Cache File | Read On | Write On | Invalidation |
|:-----------|:--------|:---------|:-------------|
| `{name}.compframes` | Analyze phase start | Analyze phase end | `--no-cache` or config change |
| `clip_probe.toml` | LoadSources phase start | LoadSources phase end | file change |
| `audio_offsets.toml` | Align phase start | Align phase end | `--no-cache` or file change |
| `manual_overrides.toml` | Always | VSPreview session | Manual deletion only |
| `vspreview_sessions/*` | — | VSPreview session | Manual deletion only |

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
