# VSPreview Integration Module Spec

> **Module:** `frame_compare.vspreview`
> **Version:** 1.0
> **Priority:** P1 (Optional, post-MVP)

---

## 1. Module Overview

The VSPreview module provides optional interactive alignment verification and override capabilities using the VSPreview application. This is a user-facing feature that allows manual confirmation or adjustment of computed audio alignment offsets.

### 1.1 Responsibilities

- Launch VSPreview with comparison clips loaded
- Capture user-provided manual offset overrides
- Persist manual overrides to cache
- Integrate with alignment service as an optional verification step

### 1.2 Module Structure

```text
src/frame_compare/vspreview/
├── __init__.py          # Public exports
├── adapter.py           # VSPreview launch and communication
└── overrides.py         # Manual override persistence
```

### 1.3 Module Boundary

VSPreview integration is an **adapter**, not a core service:

- Core services (`alignment.py`) compute offsets programmatically
- The VSPreview adapter provides an optional UI layer
- Services call the adapter only when `config.use_vspreview = True`

---

## 2. Key Types

### 2.1 ManualOverride

```python
@dataclass(frozen=True)
class ManualOverride:
    """User-provided alignment override from VSPreview session.

    Attributes:
        reference_clip: Path stem of reference clip
        comparison_clip: Path stem of comparison clip
        frame_offset: User-confirmed frame offset
        timestamp: ISO 8601 timestamp when override was recorded
        confirmed: True if user explicitly confirmed computed offset
    """
    reference_clip: str
    comparison_clip: str
    frame_offset: int
    timestamp: str
    confirmed: bool = True
```

### 2.2 VSPreviewConfig

```python
@dataclass(frozen=True)
class VSPreviewConfig:
    """Configuration for VSPreview integration.

    Attributes:
        enabled: Whether to launch VSPreview for verification
        timeout_seconds: Max time to wait for user input
        auto_close: Close VSPreview after user confirms
    """
    enabled: bool = False
    timeout_seconds: float = 300.0  # 5 minutes
    auto_close: bool = True
```

---

## 3. Public API

### 3.1 Availability Check

```python
def is_vspreview_available() -> bool:
    """Check if VSPreview is installed and can be launched.

    Returns:
        True if vspreview is importable and functional

    Note:
        Does not require a running X server/display.
        Full launch capability is checked separately.
    """
```

### 3.2 Launch Session for Verification (All Comparisons)

```python
def launch_alignment_verification_session(
    reference: Path,
    comparisons: list[Path],
    suggested_offsets_by_key: dict[str, int],
    cache_dir: Path,
    config: VSPreviewConfig,
) -> Path:
    """
    Launch a single VSPreview session for the full comparison set.

    Behavior:
    1. Generate a self-contained Python script that loads the reference clip and all comparisons.
    2. Apply FPS harmonization so that all clips scrub at the reference FPS (see §3.2.2).
    3. Overlay labels + suggested offsets per clip (see §3.2.1).
    4. Launch VSPreview (same interpreter) via `sys.executable -m vspreview {script}`.
    5. Return the on-disk script path for debugging/replay.
    6. If `config.enabled` is `False`, the function MUST still generate and persist the script and return its path,
       but MUST NOT attempt to launch VSPreview and MUST NOT raise VSPreviewNotFoundError/VSPreviewError.

    Args:
        reference: Path to reference video
        comparisons: Paths to comparison videos
        suggested_offsets_by_key: Signed relative offsets keyed by "{ref_stem}:{comp_stem}"
        cache_dir: Directory used for generated artifacts (script output lives under `{cache_dir}/vspreview_sessions/`)
        config: VSPreview configuration

    Returns:
        Path to the generated script on disk

    Raises:
        VSPreviewNotFoundError: If vspreview is not importable/launchable when this function is invoked
        VSPreviewError: If launch fails after vspreview is available

    Note:
        VSPreview does not provide a stable programmatic API for reading user “dragged” offsets back out of the GUI.
        This module does NOT capture offsets from VSPreview.

        Confirmation is performed by the CLI after VSPreview exits: the user is prompted per comparison clip with a
        default value of the suggested signed frame offset, then `ManualOverride` entries are persisted.
    """
```

#### 3.2.1 Overlay + Confirmation Contract (Required)

The verification session MUST make it easy for a user to identify which clip they are adjusting and what offset is being proposed.

**Overlay requirements (script):**

- Reference overlay MUST include the reference clip filename (or stem) and a stable label:
  - Example: `REF: {reference.name}`
- Each comparison overlay MUST include the comparison clip filename (or stem) and a stable label:
  - Example: `CMP: {comparison.name}`
- The proposed offset MUST be displayed per comparison:
  - Example: `Suggested offset: {suggested_offset} frames`
- The sign convention MUST be displayed to prevent user confusion:
  - Example: `+N = comparison starts AFTER reference; -N = comparison starts BEFORE reference`
  - Note: negative values are valid at the *relative offset* boundary; the pipeline applies a trim-first
    normalization step so that no clip is ever padded with blank frames (see services-module.md §2.5).

**User confirmation (terminal prompt, CLI-owned):**

- After VSPreview exits, the CLI MUST obtain an explicit confirmation per comparison clip.
- The prompt MUST default to the suggested signed offset.
- If the user accepts the default without changing it, the CLI MUST persist `ManualOverride(confirmed=True)`.
- If the user changes the offset, the CLI MUST persist `ManualOverride(confirmed=False)` with the adjusted `frame_offset`.
- If the user cancels the prompt step, the CLI MUST NOT persist anything for that clip.

**Persistence boundary (manual-only):**

- This module MUST NOT write to `audio_offsets.toml`. It only persists manual values via `save_manual_override()` to `manual_overrides.toml`.
- Manual values are stored as signed **comparison-relative-to-reference** frame offsets (may be negative).

#### 3.2.2 Script Generation Requirements (Legacy-Proven)

The VSPreview session is driven by a generated Python script. This script MUST be:

- **Self-contained**: no CLI argument parsing inside the script; embed state via dictionary literals.
- **Deterministic**: same inputs → byte-identical script content (except the output filename timestamp).
- **Debuggable**: written to disk so an operator can re-run it directly.

**Output location:**

- Directory: `{cache_dir}/vspreview_sessions/` (created if missing)
- Filename: `vspreview_{reference_stem}_{timestamp}.py` (UTC timestamp)
  - `timestamp` format: `YYYYMMDDTHHMMSSZ` (UTC, seconds precision)
  - The timestamp MUST appear in the filename only; it MUST NOT appear in the script body so that script content
    remains byte-identical for the same inputs.

**Script MUST include:**

- A short header comment that states:
  - sign convention (`+ trims comparison`, `- trims reference` in preview)
  - that operator-confirmed offsets are **signed relative offsets**
  - that the pipeline will apply trim-first normalization (no padding)
- A `safe_print()` helper and UTF-8 `stdout`/`stderr` reconfigure best-effort block.
- An explicit `sys.path` bootstrap that makes imports work in “run from repo” mode:
  - Insert (in order): `PROJECT_ROOT`, `PROJECT_ROOT/src`, `WORKSPACE_ROOT`.
  - The script MUST NOT rely on the working directory being the project root.
- A stable, explicit `REFERENCE` dict and `TARGETS` mapping keyed by label.
- A stable `suggested_offsets_by_key` mapping keyed by `"{ref_stem}:{comp_stem}"`.
- A stable per-label `OFFSET_MAP` that the operator may edit (debugging convenience).

**Slot layout (operator UX):**

- Reference is repeated on even-numbered slots: 0, 2, 4, ...
- Comparisons are placed on odd-numbered slots: 1, 3, 5, ...

**FPS harmonization (preview-only):**

- VSPreview comparisons MUST scrub at a consistent FPS.
- The script MUST apply `AssumeFPS` (or equivalent) so that each comparison clip has the same FPS as the reference.
- This is for preview ergonomics; it does not change persisted offsets.

**Encoding safety:**

- The script SHOULD attempt `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` to avoid Windows console crashes.

**Overlay resilience:**

- Overlay application MUST be best-effort: if the overlay/text plugin is missing, the script must continue without overlays and print a warning.

#### 3.2.3 Launch + Telemetry Contract (Fragility Hardened)

VSPreview is optional and frequently fails due to missing GUI backends. The orchestration layer MUST surface actionable diagnostics.

**Launch requirements:**

- Only launch when `stdin` is a TTY.
- Always print:
  - the generated script path,
  - the exact copy/paste command used to launch VSPreview.
- If VSPreview exits non-zero:
  - warn and continue (do not fail the run),
  - suggest re-running with a verbose mode to capture stdout/stderr.

**Missing reason codes (SSOT):**

- `vspreview-executable-missing` — no `vspreview` binary and no importable module
- `vspreview-module-missing` — `vspreview` module not importable
- `vspreview-backend-missing` — `vspreview` module importable, but `PySide6`/`PyQt5` missing

**JSON output (when `--json`):**

- The CLI SHOULD include a `vspreview_offer` object that contains:
  - `vspreview_offered: bool`
  - `reason: str` (one of the missing reason codes or empty string)
  - `script_path: str | null`
  - `command: str`

### 3.3 Override Persistence

```python
def load_manual_overrides(cache_dir: Path) -> dict[str, ManualOverride]:
    """Load persisted manual overrides from cache.

    Args:
        cache_dir: Directory containing manual_overrides.toml

    Returns:
        Dict mapping "{ref_stem}:{comp_stem}" -> ManualOverride
        Empty dict if file does not exist or is empty
    """

def save_manual_override(
    cache_dir: Path,
    override: ManualOverride,
) -> None:
    """Persist a manual override to cache.

    Args:
        cache_dir: Directory for manual_overrides.toml
        override: Override to save

    Behavior:
        - Creates file if not exists
        - Merges with existing overrides
        - Overwrites existing entry for same key
    """
```

---

## 4. Integration with Alignment Service

### 4.1 Alignment Flow with VSPreview

This module is an adapter: it launches the VSPreview UI, but it does not compute offsets and does not capture
GUI interactions programmatically.

High-level orchestration flow:

1. Compute or load **suggested signed relative offsets** via `frame_compare.services.alignment.align_clips()`.
2. If `use_vspreview=True` and at least one comparison lacks a manual override (or `force_interactive=True`):
   - Launch a single VSPreview session for the full set via `launch_alignment_verification_session(...)`.
   - Prompt the user per comparison clip for the final signed relative offset (CLI-owned).
   - Persist `ManualOverride` entries via `save_manual_override(...)`.

### 4.2 Merge Semantics

When a manual override exists:

| Priority | Source | Behavior |
|:---------|:-------|:---------|
| 1 (Highest) | `manual_overrides.toml` | Always used if present |
| 2 | Cached computed alignment (`audio_offsets.toml`) | Used if no manual override |
| 3 | Newly computed alignment (cross-correlation) | Used if no manual override and cache miss |

**Key rule:** Manual overrides ALWAYS take precedence. Users can delete `manual_overrides.toml` to revert to computed values.

---

## 5. Cache Schema

### 5.1 Manual Overrides File

Cache file: `{cache_dir}/manual_overrides.toml`

```toml
# Manual override cache - user-provided alignment overrides
version = "1"

["reference:comparison_a"]
reference_clip = "reference"
comparison_clip = "comparison_a"
frame_offset = 42
timestamp = "2026-01-03T12:00:00Z"
confirmed = true

["reference:comparison_b"]
reference_clip = "reference"
comparison_clip = "comparison_b"
frame_offset = -10
timestamp = "2026-01-03T12:05:00Z"
confirmed = true
```

### 5.2 Cache Behavior

| Scenario | Behavior |
|:---------|:---------|
| File missing | Return empty dict, no error |
| TOML parse error | Log warning, return empty dict |
| Version mismatch | Log warning, return empty dict |

**Rationale:** Manual overrides are user-created artifacts. We never raise errors on cache issues—we just recompute or re-verify.

---

## 6. Optional Dependency Behavior

### 6.1 Doctor Reporting

When running `frame-compare doctor`:

```python
# In doctor checks
def check_vspreview() -> CheckResult:
    """Check VSPreview availability."""
    if is_vspreview_available():
        return CheckResult(
            passed=True,
            message="VSPreview is available for interactive alignment",
        )
    else:
        return CheckResult(
            passed=True,  # Not a failure, just optional
            message="VSPreview not installed (optional for manual alignment)",
            hint="Install with: pip install vspreview",
        )
```

### 6.2 Missing Dependency Behavior

| `use_vspreview` | VSPreview Available | Behavior |
|:----------------|:--------------------|:---------|
| `False` | Any | Skip VSPreview entirely |
| `True` | `True` | Launch verification |
| `True` | `False` | Log warning, skip verification, continue with computed/cached offset |

**No hard failure:** If user requests VSPreview but it is not available, the alignment service MUST log a warning and continue. This module MUST NOT be required for Runner MVP.

```python
if config.use_vspreview and not is_vspreview_available():
    log.warning(
        "vspreview_not_available",
        hint="Install vspreview for interactive alignment verification",
    )
    # Continue with computed/cached alignment
```

### 6.3 Command Resolution + Missing Reasons (Operator-Friendly)

VSPreview launch is fragile across platforms. The orchestration layer MUST surface clear missing-reason codes and a
copy/paste command for operators.

**Command resolution priority:**

1. If `vspreview` executable exists in `PATH`: run `vspreview {script_path}`
2. Else if `python -m vspreview` is available (module importable) AND a Qt backend is importable (`PySide6` or `PyQt5`):
   run `{sys.executable} -m vspreview {script_path}`
3. Otherwise: treat VSPreview as unavailable.

**Missing reason codes (SSOT):**

- `vspreview-executable-missing` — no `vspreview` binary and no importable module
- `vspreview-module-missing` — `vspreview` module not importable
- `vspreview-backend-missing` — `vspreview` module importable, but `PySide6`/`PyQt5` missing

**Operator message requirements:**

- Print the generated script path on disk
- Print a copy/paste launch command matching the internal resolution
- If missing, print install hints for the operator’s platform and the missing reason code

---

## 7. Determinism

### 7.1 Output Stability

Given the same cached manual overrides:

- Same inputs (reference, comparison, cache_dir)
- Same `manual_overrides.toml` contents

→ Same `AlignmentResult` output

**Note:** VSPreview interaction is inherently non-deterministic (depends on user input). However, once an override is persisted, subsequent runs are deterministic.

---

## 8. Testing Strategy

### 8.1 Unit Tests (No GUI Required)

**Test File:** `tests/vspreview/test_overrides.py`

| Test Function | Validates |
|:--------------|:----------|
| `test_is_vspreview_available_returns_true_when_importable` | Availability check positive |
| `test_is_vspreview_available_returns_false_when_missing` | Availability check negative (mock `find_spec` to return None) |
| `test_load_manual_overrides_parses_valid_toml` | Override loading from valid TOML |
| `test_load_manual_overrides_returns_empty_dict_on_missing_file` | Missing file handling |
| `test_load_manual_overrides_returns_empty_dict_on_parse_error` | Corrupt TOML handling |
| `test_load_manual_overrides_returns_empty_dict_on_version_mismatch` | Version migration handling |
| `test_save_manual_override_creates_file_if_missing` | Override persistence (new file) |
| `test_save_manual_override_merges_with_existing` | Merge semantics (preserves other keys) |
| `test_save_manual_override_overwrites_same_key` | Update semantics (same clip pair) |
| `test_manual_override_takes_precedence_over_computed` | Priority rule enforcement |

### 8.2 Pytest Markers

VSPreview does not have a dedicated marker in this repo. Tests MUST use existing markers from `pyproject.toml`:

- `@pytest.mark.integration` for integration-level tests
- `@pytest.mark.e2e` for end-to-end tests
- `@pytest.mark.skip` for interactive/manual tests (always skipped by default)

### 8.3 Integration Tests (Optional, Marker-Gated)

```python
@pytest.mark.integration
@pytest.mark.skip(reason="Requires interactive display")
def test_vspreview_integration():
    """Manual integration test - run interactively."""
    raise NotImplementedError("Manual/interactive test placeholder")
```

---

## 9. Error Handling

> [!NOTE]
> All error classes are defined centrally in `frame_compare.errors`.

**Error classes used by this module:**

| Error Class | Code | Usage |
|-------------|------|-------|
| `VSPreviewNotFoundError` | FC-2008 | VSPreview not installed |
| `VSPreviewError` | FC-4019 | VSPreview launch/communication failure |

```python
from frame_compare.errors import VSPreviewError, VSPreviewNotFoundError
```

---

## 10. AI Agent Implementation Prompt

```markdown
# Task: Implement VSPreview Integration Module

## Context
Implement the optional VSPreview integration for Frame Compare 2.0.
This module provides interactive alignment verification as a convenience feature.

## Files to Create
1. `src/frame_compare/vspreview/__init__.py` - Public exports
2. `src/frame_compare/vspreview/adapter.py` - VSPreview launch logic
3. `src/frame_compare/vspreview/overrides.py` - Override persistence
4. `tests/vspreview/test_overrides.py` - Unit tests (no GUI)

## Key Requirements
- Optional dependency (graceful handling when missing)
- TOML cache for manual overrides
- Integration with alignment service
- Doctor check for availability

## Testing
- Unit tests MUST NOT require VSPreview or display
- GUI/manual tests MUST be `@pytest.mark.skip` (and optionally `@pytest.mark.integration`)
- Mock all VSPreview interactions in unit tests

## Acceptance Criteria
- `is_vspreview_available()` works correctly
- Override persistence round-trips
- Missing VSPreview logs warning, doesn't fail
- Doctor reports VSPreview status
```
