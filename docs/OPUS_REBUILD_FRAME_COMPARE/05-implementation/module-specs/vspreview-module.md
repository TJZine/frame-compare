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

### 3.2 Launch for Verification

```python
def launch_alignment_verification(
    reference: Path,
    comparison: Path,
    computed_offset: int,
    config: VSPreviewConfig,
) -> ManualOverride | None:
    """
    Launch VSPreview for user to verify/adjust alignment.

    Behavior:
    1. Generate temporary VPY script loading both clips
    2. Apply computed_offset to comparison clip
    3. Launch VSPreview with script
    4. Wait for user interaction (confirm/adjust/cancel)
    5. Capture final offset from user
    6. Return ManualOverride or None if cancelled

    Args:
        reference: Path to reference video
        comparison: Path to comparison video
        computed_offset: Computed frame offset from align_clips
        config: VSPreview configuration

    Returns:
        ManualOverride if user confirmed/adjusted
        None if user cancelled or timeout

    Raises:
        VSPreviewNotFoundError: If vspreview is not importable/launchable when this function is invoked
        VSPreviewError: If launch or communication fails after vspreview is available

    Note:
        This function blocks until user interaction completes or timeout.
        Callers MUST treat VSPreview failures as warn-only and continue with the computed/cached offset (see §6.2).
    """
```

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

```python
# In services/alignment.py align_clips()

async def align_clips(
    reference: Path,
    comparisons: list[Path],
    config: AlignmentConfig,
    cache_dir: Path,
    progress: ProgressReporter | None = None,
) -> list[AlignmentResult]:
    results: list[AlignmentResult] = []

    for comparison in comparisons:
        # Check for existing manual override first
        manual_overrides = load_manual_overrides(cache_dir)
        key = f"{reference.stem}:{comparison.stem}"

        if key in manual_overrides:
            # Use persisted manual override
            override = manual_overrides[key]
            result = AlignmentResult(
                reference_clip=str(reference),
                comparison_clip=str(comparison),
                frame_offset=override.frame_offset,
                time_offset_seconds=offset_to_seconds(override.frame_offset, fps),
                correlation_score=1.0,  # Manual = full confidence
                method="manual",
            )
        else:
            # Compute alignment programmatically
            result = await _compute_alignment(reference, comparison, config)

            # Optionally verify with VSPreview
            if config.use_vspreview and is_vspreview_available():
                vspreview_config = VSPreviewConfig(enabled=True)
                override = launch_alignment_verification(
                    reference, comparison, result.frame_offset, vspreview_config
                )
                if override is not None:
                    save_manual_override(cache_dir, override)
                    result = replace(result, frame_offset=override.frame_offset, method="manual")

        results.append(result)

    return results
```

### 4.2 Merge Semantics

When a manual override exists:

| Priority | Source | Behavior |
|:---------|:-------|:---------|
| 1 (Highest) | `manual_overrides.toml` | Always used if present |
| 2 | Computed alignment | Used if no manual override |
| 3 | Cached alignment | Used if cache hit and no manual override |

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
- Use `@pytest.mark.vspreview_required` for GUI tests
- Mock all VSPreview interactions in unit tests

## Acceptance Criteria
- `is_vspreview_available()` works correctly
- Override persistence round-trips
- Missing VSPreview logs warning, doesn't fail
- Doctor reports VSPreview status
```
