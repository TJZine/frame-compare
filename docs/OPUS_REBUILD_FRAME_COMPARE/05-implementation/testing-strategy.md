# Testing Strategy

> **Module:** Implementation
> **Version:** 1.0

---

## 1. Testing Philosophy

### 1.1 Guiding Principles

1. **Test behavior, not implementation** — focus on public APIs
2. **Fast feedback loops** — unit tests < 100ms each
3. **Deterministic tests** — no flaky tests allowed
4. **Comprehensive coverage** — 80%+ line coverage target
5. **Clear failure messages** — tests should tell you what's wrong

### 1.2 Test Pyramid

```text
          ╱╲
         ╱E2E╲         Few, slow, high confidence
        ╱──────╲
       ╱Integra-╲      Some, moderate speed
      ╱───tion───╲
     ╱────────────╲
    ╱  Unit Tests  ╲   Many, fast, low risk
   ╱────────────────╲
```

| Level | Count | Speed | Scope |
|-------|-------|-------|-------|
| Unit | Many | <100ms | Single function/class |
| Integration | Some | <1s | Module interactions |
| E2E | Few | <30s | Full CLI workflows |

---

## 2. Test Types

### 2.1 Unit Tests

**Purpose:** Test individual functions and classes in isolation

**Location:** `tests/<module>/test_<file>.py`

**Characteristics:**

- No external dependencies (mocked)
- No disk I/O (use fixtures)
- No network calls
- Deterministic and fast

**Example:**

```python
# tests/analysis/test_metrics.py
import pytest
import numpy as np
from frame_compare.analysis.metrics import calculate_luminance

def test_calculate_luminance_returns_normalized_values():
    # Arrange
    frames = [np.zeros((100, 100), dtype=np.uint8)]

    # Act
    result = calculate_luminance(frames)

    # Assert
    assert result == [0.0]

def test_calculate_luminance_white_frame():
    frames = [np.full((100, 100), 255, dtype=np.uint8)]
    result = calculate_luminance(frames)
    assert result == [1.0]
```

### 2.2 Integration Tests

**Purpose:** Test module interactions and data flow

**Location:** `tests/integration/`

**Markers:** `@pytest.mark.integration`

**Characteristics:**

- May use real files (from fixtures)
- May access local cache
- External APIs mocked
- Slower than unit tests

**Example:**

```python
# tests/integration/test_analysis_pipeline.py
import pytest
from pathlib import Path
from frame_compare.analysis import calculate_metrics, select_frames

@pytest.mark.integration
def test_analysis_pipeline_end_to_end(sample_video_clip):
    # Calculate metrics
    metrics = calculate_metrics(sample_video_clip)

    # Select frames
    selection = select_frames(metrics, frame_count=10, seed=42)

    # Verify
    assert len(selection.frames) == 10
    assert selection.breakdown.quantile_count > 0
    assert selection.breakdown.random_count > 0
```

### 2.3 E2E Tests

**Purpose:** Test complete CLI workflows

**Location:** `tests/e2e/`

**Markers:** `@pytest.mark.e2e`

**Characteristics:**

- Uses CLI runner
- May use Docker
- External APIs mocked or sandboxed
- Full disk I/O

**Example:**

```python
# tests/e2e/test_cli_run.py
import pytest
from typer.testing import CliRunner
from frame_compare.cli_entry import app

@pytest.mark.e2e
def test_cli_run_produces_screenshots(tmp_path, sample_videos):
    runner = CliRunner()
    result = runner.invoke(app, [
        "run",
        "--root", str(tmp_path),
        "--no-upload",
    ])

    assert result.exit_code == 0
    screenshots = list((tmp_path / "screenshots").glob("*.png"))
    assert len(screenshots) > 0
```

### 2.4 VapourSynth Tests

**Purpose:** Test VapourSynth-dependent functionality

**Markers:** `@pytest.mark.vs_required`

**Characteristics:**

- Skipped if VapourSynth not available
- Slower due to video processing
- Use small test clips

**Example:**

```python
# tests/vs/test_tonemap.py
import pytest

@pytest.mark.vs_required
def test_tonemap_hdr_to_sdr(hdr_test_clip):
    from frame_compare.vs.tonemap import tonemap

    result = tonemap(hdr_test_clip, preset="reference")

    # Verify output is SDR
    assert result.get_frame(0).props["_ColorRange"] == 0
```

---

## 3. Test Infrastructure

### 3.1 Pytest Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "-ra",
    "-q",
    "--strict-markers",
    "--strict-config",
]
markers = [
    "unit: Fast isolated tests",
    "integration: Module interaction tests",
    "e2e: End-to-end CLI tests",
    "vs_required: Requires VapourSynth runtime",
    "slow: Long-running tests",
    "network: Requires network access",
    "tier_a: Contract/security tests (no VS, no network)",
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:vapoursynth",
]
# anyio includes its own pytest plugin (anyio.pytest_plugin)
anyio_mode = "auto"
```

> [!NOTE]
> For async tests (e.g., `services/` module with httpx), use anyio's built-in pytest plugin:
>
> ```python
> import pytest
>
> @pytest.mark.anyio
> async def test_upload_async():
>     async with httpx.AsyncClient() as client:
>         # test async operations
>         ...
> ```
>
> No separate `pytest-anyio` package is needed — `anyio>=4.0` includes the plugin.

### 3.2 Conftest Organization

```python
# tests/conftest.py
import pytest
from pathlib import Path

# ─── Markers ───────────────────────────────────────────────

def pytest_configure(config):
    """Register custom markers."""
    # Markers defined in pyproject.toml

# ─── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def sample_video_path() -> Path:
    """Path to test video file."""
    return Path(__file__).parent / "fixtures" / "sample.mkv"

@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Temporary workspace with standard structure."""
    (tmp_path / "comparison_videos").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "generated").mkdir()
    return tmp_path

# ─── VapourSynth Stubs ─────────────────────────────────────

@pytest.fixture
def mock_vs(mocker):
    """Mock VapourSynth for unit tests."""
    mock = mocker.MagicMock()
    mocker.patch.dict("sys.modules", {"vapoursynth": mock})
    return mock

# ─── Progress Stubs ────────────────────────────────────────

@pytest.fixture
def dummy_progress():
    """No-op progress reporter."""
    from frame_compare.utils.progress import NullProgress
    return NullProgress()
```

### 3.3 Fixtures Directory

```text
tests/
├── fixtures/
│   ├── sample.mkv          # 1-second test video
│   ├── sample_hdr.mkv      # HDR test video
│   ├── sample_audio.wav    # Audio test file
│   ├── config.toml         # Test configuration
│   └── expected/           # Expected output files
│       ├── metrics.json
│       └── selection.json
```

---

## 4. Mocking Strategy

### 4.1 Mock Boundaries

| Component | Mock Strategy |
|-----------|---------------|
| VapourSynth | Full mock for unit tests; real for `vs_required` |
| FFmpeg | Mock subprocess calls |
| HTTP (slow.pics, TMDB) | `responses` or `httpx.MockTransport` |
| File system | `tmp_path` fixture |
| Time/Clock | Inject `clock` callable |

### 4.2 External API Mocking

```python
# tests/services/test_publishers.py
import pytest
import httpx
from frame_compare.services.publishers import upload_to_slowpics

@pytest.fixture
def mock_slowpics(respx_mock):
    respx_mock.post("https://slow.pics/api/comparison").mock(
        return_value=httpx.Response(200, json={"url": "https://slow.pics/c/abc123"})
    )
    return respx_mock

def test_upload_returns_url(mock_slowpics, screenshot_dir):
    result = upload_to_slowpics(screenshot_dir)
    assert result.url == "https://slow.pics/c/abc123"
```

### 4.3 Dependency Injection Testing

```python
# tests/runner/test_runner.py
from frame_compare.runner import run
from frame_compare.types import RunDependencies

def test_run_uses_injected_vs_loader(mock_vs_loader):
    deps = RunDependencies(
        vs_loader=mock_vs_loader,
        ffmpeg_runner=mock_ffmpeg,
        http_client=mock_http,
        progress=NullProgress(),
        clock=lambda: datetime(2024, 1, 1),
    )

    result = run(request, dependencies=deps)

    mock_vs_loader.load.assert_called_once()
```

---

## 5. Coverage Requirements

### 5.1 Coverage Targets

| Module | Minimum | Target |
|--------|---------|--------|
| `analysis/` | 85% | 90% |
| `vs/` | 75% | 80% |
| `render/` | 80% | 85% |
| `services/` | 80% | 85% |
| `cli_entry.py` | 70% | 80% |
| Overall | 80% | 85% |

### 5.2 Coverage Configuration

```toml
# pyproject.toml
[tool.coverage.run]
source = ["src/frame_compare"]
branch = true
omit = [
    "*/__main__.py",
    "*/types.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
    "@overload",
]
fail_under = 80
show_missing = true
```

---

## 6. CI Integration

### 6.1 Test Stages

**SSOT:** `.github/workflows/ci.yml`

> [!IMPORTANT]
> Treat any CI snippets in this document as illustrative only. The authoritative CI commands and job layout live in `.github/workflows/ci.yml`.

### 6.2 E2E in Docker

```yaml
  e2e:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4

      - name: Build container
        run: docker build -t frame-compare:test .

      - name: Run E2E tests
        run: |
          docker run --rm \
            -v ./tests/fixtures:/workspace/comparison_videos \
            frame-compare:test \
            pytest -m "e2e"
```

---

## 7. Test Naming Conventions

### 7.1 Naming Pattern

```text
test_<function>_<scenario>_<expected_behavior>
```

### 7.2 Examples

```python
# Good
def test_calculate_luminance_empty_frames_returns_empty_list(): ...
def test_select_frames_same_seed_produces_same_result(): ...
def test_upload_network_error_raises_publish_error(): ...

# Bad
def test_luminance(): ...  # Too vague
def test_it_works(): ...   # Not descriptive
def test_function(): ...   # What function?
```

---

## 8. Snapshot Testing

### 8.1 When to Use

- Complex JSON/TOML output
- CLI help text
- Generated filenames
- Error messages

### 8.2 Implementation

```python
# tests/test_output.py
import pytest
from syrupy.assertion import SnapshotAssertion

def test_selection_breakdown_json(snapshot: SnapshotAssertion):
    breakdown = SelectionBreakdown(
        quantile_count=3,
        motion_count=2,
        random_count=5,
    )

    assert breakdown.to_json() == snapshot
```

---

## 9. Performance Testing

### 9.1 Benchmarks

```python
# tests/benchmarks/test_perf.py
import pytest

@pytest.mark.slow
def test_metrics_calculation_performance(benchmark, large_video):
    result = benchmark(calculate_metrics, large_video)
    assert result is not None

@pytest.mark.slow
def test_selection_1000_frames_under_100ms(benchmark):
    metrics = generate_mock_metrics(1000)

    result = benchmark(select_frames, metrics, frame_count=50)

    assert benchmark.stats.median < 0.1  # 100ms
```

### 9.2 Memory Profiling

```python
@pytest.mark.slow
def test_large_video_memory_usage(memory_profile):
    # Process 10GB video
    result = process_large_video(Path("fixtures/large.mkv"))

    # Should not exceed 2GB RAM
    assert memory_profile.peak_mb < 2048
```
