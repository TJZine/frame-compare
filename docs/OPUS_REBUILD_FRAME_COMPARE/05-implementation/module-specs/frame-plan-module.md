# FramePlan Module Implementation Spec

> **Module:** `frame_compare.analysis.frame_plan`
> **Version:** 1.0
> **Priority:** P0

---

## 1. Module Overview

The FramePlan module provides deterministic frame selection for the `--skip-analysis` path. When analysis is skipped, frames are selected using a seeded uniform distribution instead of metric-based selection.

### 1.1 Responsibilities

- Generate deterministic frame indices without computing metrics
- Provide stable ordering for reproducibility
- Support the `--skip-analysis` CLI flag
- Produce identical output given identical inputs

### 1.2 Module Structure

```text
src/frame_compare/analysis/
├── frame_plan.py       # FramePlan implementation (this spec)
├── selection.py        # Metric-based selection (existing)
└── (other existing analysis modules)
```

---

## 2. Key Types

### 2.1 FramePlan

```python
@dataclass(frozen=True)
class FramePlan:
    """Deterministic frame selection result.

    Invariants:
    - len(frames) == count (always exactly count frames)
    - all(0 <= f < num_frames for f in frames)
    - frames are sorted ascending
    - frames are unique
    """
    frames: list[int]      # Selected frame indices, sorted ascending
    num_frames: int        # Total frames in source video
    count: int             # Requested frame count
    seed: int              # Seed used for selection (see §6.4)
    method: str = "uniform_seeded"  # Selection method identifier
```

**Example construction:**

```python
plan = FramePlan(
    frames=[100, 500, 900, 1300, 1700],
    num_frames=2000,
    count=5,
    seed=42,
)
```

---

## 3. Public API

### 3.1 Frame Selection

```python
def select_uniform_seeded_frames(
    num_frames: int,
    count: int,
    seed: int,
) -> FramePlan:
    """
    Select frames using deterministic uniform distribution.

    Algorithm:
    1. Validate inputs (count <= num_frames)
    2. Divide frame range into `count` equal bins
    3. For each bin, select one frame using blake2s hash
    4. Return sorted, unique frame indices

    Args:
        num_frames: Total frames in video (exclusive upper bound)
        count: Number of frames to select
        seed: Integer seed for reproducibility (see §6.4)

    Returns:
        FramePlan with exactly `count` frames

    Raises:
        InsufficientFramesError (FC-3004): If count > num_frames

    Determinism guarantee:
        Same (num_frames, count, seed) → same frames, always.
    """
```

### 3.2 FramePlan Creation Helper

```python
def create_frame_plan(
    num_frames: int,
    count: int,
    seed: int | None = None,
) -> FramePlan:
    """
    Create a FramePlan with optional auto-generated seed.

    Args:
        num_frames: Total frames in video
        count: Number of frames to select
        seed: Optional seed; if None, uses the SSOT default seed (42)

    Returns:
        FramePlan from select_uniform_seeded_frames()
    """
```

---

## 4. Algorithm Specification

### 4.1 Bin Partitioning

Divide the frame range `[0, num_frames)` into `count` equal bins:

```python
bin_size = num_frames / count  # float division for even bins
bins = [
    (int(i * bin_size), int((i + 1) * bin_size))
    for i in range(count)
]
# Each bin is [start, end) range
```

### 4.2 Frame Selection Per Bin

For each bin, select one frame using blake2s hash:

```python
import hashlib

def _select_from_bin(bin_start: int, bin_end: int, seed: int, bin_index: int) -> int:
    """Select one frame from a bin using blake2s hash.

    Args:
        bin_start: Inclusive start of bin
        bin_end: Exclusive end of bin
        seed: User-provided seed integer
        bin_index: Index of this bin (0-based)

    Returns:
        Frame index in [bin_start, bin_end)
    """
    bin_size = bin_end - bin_start
    if bin_size <= 0:
        raise ValueError("Empty bin")

    # Create deterministic hash from seed + bin index
    hash_input = f"{seed}:{bin_index}".encode("utf-8")
    digest = hashlib.blake2s(hash_input, digest_size=8).digest()

    # Convert to integer and map to bin range
    hash_int = int.from_bytes(digest, "little")
    offset = hash_int % bin_size

    return bin_start + offset
```

### 4.3 Complete Algorithm

```python
def select_uniform_seeded_frames(
    num_frames: int,
    count: int,
    seed: int,
) -> FramePlan:
    """Select frames using deterministic uniform distribution."""
    from frame_compare.errors import InsufficientFramesError

    # Validate
    if count > num_frames:
        raise InsufficientFramesError(
            count=count,
            available=num_frames,
        )

    if count == 0:
        return FramePlan(
            frames=[],
            num_frames=num_frames,
            count=0,
            seed=seed,
        )

    # Calculate bins
    bin_size = num_frames / count
    frames: list[int] = []

    for i in range(count):
        bin_start = int(i * bin_size)
        bin_end = int((i + 1) * bin_size)
        # Clamp end to num_frames for last bin
        if i == count - 1:
            bin_end = num_frames

        frame = _select_from_bin(bin_start, bin_end, seed, i)
        frames.append(frame)

    # Sort for stable output (required by contract)
    frames.sort()

    return FramePlan(
        frames=frames,
        num_frames=num_frames,
        count=count,
        seed=seed,
    )
```

---

## 5. Error Handling

> [!NOTE]
> All error classes are defined centrally in `frame_compare.errors` (see [errors-module.md](errors-module.md)).

**Error classes used by this module:**

| Error Class | Code | Usage |
|-------------|------|-------|
| `InsufficientFramesError` | FC-3004 | count > num_frames |

```python
from frame_compare.errors import InsufficientFramesError

# Raised when requested count exceeds available frames
raise InsufficientFramesError(
    count=10,
    available=5,
)
# Message: "Requested 10 frames but video only has 5"
# Hint: "Reduce frame_count or use a longer video"
```

---

## 6. Invariants and Guarantees

### 6.1 Determinism

**CRITICAL:** The algorithm MUST be deterministic.

Given:

- Same `num_frames`
- Same `count`
- Same `seed`

The output `frames` list MUST be byte-identical across:

- Different Python sessions
- Different machines
- Different operating systems

### 6.2 Stable Ordering

Output frames are always sorted ascending. The `frames` list is a Python `list[int]`, not a set or generator.

### 6.3 Uniqueness

All frame indices in `frames` are unique. No duplicates.

### 6.4 Seed Handling

| Seed Value | Behavior |
|:-----------|:---------|
| `seed` is an integer | Use directly |
| `None` (via helper) | Use `42` |

**SSOT default seed:** `42` (must remain consistent with `ConfigSchema.analysis.random_seed`).

---

## 7. Integration with Render Module

The render module uses FramePlan when `--skip-analysis` is specified:

```python
# In orchestration or render phase
if config.skip_analysis:
    from frame_compare.analysis.frame_plan import create_frame_plan

    plan = create_frame_plan(
        num_frames=source_info.num_frames,
        count=config.analysis.frame_count,
        seed=config.analysis.random_seed,
    )
    frames = plan.frames
else:
    # Use metric-based selection
    metrics = calculate_metrics(clip)
    selection = select_frames(metrics, config.analysis.frame_count)
    frames = selection.frames
```

**Contract:** `FramePlan.frames` is always a concrete `list[int]`. The render phase MUST NOT reselect or modify these frames.

---

## 8. Testing Strategy

**Test File:** `tests/analysis/test_frame_plan.py`

### 8.1 Unit Tests

| Test Function | Input | Expected |
|:--------------|:------|:---------|
| `test_select_uniform_seeded_frames_deterministic` | Same inputs twice | Identical frames |
| `test_select_uniform_seeded_frames_cross_session` | Run in subprocess | Same frames |
| `test_select_uniform_seeded_frames_single_frame` | count=1 | Valid frame in range |
| `test_select_uniform_seeded_frames_all_frames` | count=num_frames | All indices 0 to n-1 |
| `test_select_uniform_seeded_frames_count_exceeds_available` | 10 frames from 5-frame video | InsufficientFramesError |
| `test_select_uniform_seeded_frames_zero_count` | count=0 | Empty list |
| `test_create_frame_plan_uses_default_seed_when_none` | seed=None | Uses 42 |
| `test_create_frame_plan_uses_default_seed_when_omitted` | seed omitted (default arg) | Uses 42 |

**Note (seed type):** `seed` is an `int | None` in this module. There is no valid “empty string” seed input at the type boundary; seed parsing/validation (if ever needed) belongs in CLI/config loading, not in `frame_plan`.

### 8.2 Property-Based Tests

```python
from hypothesis import given, strategies as st

@given(
    num_frames=st.integers(min_value=1, max_value=10000),
    count=st.integers(min_value=0, max_value=100),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_frame_plan_invariants(num_frames, count, seed):
    if count > num_frames:
        with pytest.raises(InsufficientFramesError):
            select_uniform_seeded_frames(num_frames, count, seed)
    else:
        plan = select_uniform_seeded_frames(num_frames, count, seed)

        # Invariants
        assert len(plan.frames) == count
        assert all(0 <= f < num_frames for f in plan.frames)
        assert len(set(plan.frames)) == len(plan.frames)  # Unique
        assert plan.frames == sorted(plan.frames)  # Sorted
```

### 8.3 Pytest Markers

No special markers required. All tests are pure Python, no VS/Docker needed.

---

## 9. AI Agent Implementation Prompt

```markdown
# Task: Implement FramePlan Module

## Context
Implement the deterministic frame selection module for Frame Compare 2.0.
This module provides the `--skip-analysis` path for selecting frames without computing metrics.

## Files to Create/Modify
1. `src/frame_compare/analysis/frame_plan.py` - Main implementation
2. `tests/analysis/test_frame_plan.py` - Unit tests

## Key Requirements
- blake2s hash for deterministic selection
- Bin-based uniform distribution
- Exact algorithm per spec
- Property-based tests for invariants

## Public Exports (analysis/__init__.py)
Add to existing exports:
- `FramePlan`
- `select_uniform_seeded_frames`
- `create_frame_plan`

## Acceptance Criteria
- Determinism verified (same inputs → same outputs)
- InsufficientFramesError raised correctly
- All invariants hold (unique, sorted, in-range)
- Tests pass without VS/Docker
```
