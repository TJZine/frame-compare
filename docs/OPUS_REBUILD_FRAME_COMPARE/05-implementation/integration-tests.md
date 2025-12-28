# Integration Testing Specification

> **Module:** Testing
> **Version:** 1.0

---

## 1. Overview

This document defines integration test scenarios that verify the complete Frame Compare pipeline works correctly end-to-end.

---

## 2. Test Categories

| Category | Scope | Location |
|----------|-------|----------|
| Unit | Single function | `tests/<module>/test_*.py` |
| Integration | Multiple modules | `tests/integration/` |
| E2E | Full pipeline | `tests/e2e/` |
| VapourSynth | VS-dependent | `tests/vs/` |

---

## 3. Integration Test Scenarios

### 3.1 Config Integration

```python
# tests/integration/test_config_integration.py

def test_config_loads_with_env_overrides(monkeypatch, tmp_path):
    """Config file + env vars + CLI args merge correctly."""
    # Arrange
    config_file = tmp_path / "config.toml"
    config_file.write_text('[analysis]\nframe_count = 10')
    monkeypatch.setenv("FRAME_COMPARE_ANALYSIS__FRAME_COUNT", "20")

    # Act
    config = load_config(config_file, overrides={"analysis": {"frame_count": 30}})

    # Assert
    assert config.analysis.frame_count == 30  # CLI wins

def test_config_validation_errors_are_helpful(tmp_path):
    """Validation errors include field names and hints."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('[analysis]\nframe_count = -1')

    with pytest.raises(ConfigValidationError) as exc:
        load_config(config_file)

    assert "frame_count" in str(exc.value)
    assert exc.value.hint is not None
```

### 3.2 Analysis Integration

```python
# tests/integration/test_analysis_integration.py

@pytest.mark.vs_required
def test_full_analysis_pipeline(sample_video):
    """Complete analysis: load → metrics → select → cache."""
    # Arrange
    config = AnalysisConfig(frame_count=5, random_seed=42)
    cache_dir = sample_video.parent / "generated"
    cache_dir.mkdir(exist_ok=True)

    # Act - First run
    metrics1 = calculate_metrics([sample_video], config, cache_dir)
    selection1 = select_frames(metrics1, config)

    # Act - Second run (should hit cache)
    metrics2 = calculate_metrics([sample_video], config, cache_dir)
    selection2 = select_frames(metrics2, config)

    # Assert
    assert len(selection1.frames) == 5
    assert selection1.frames == selection2.frames  # Deterministic
    assert (cache_dir / "cache.compframes").exists()

def test_analysis_cache_invalidation(sample_video):
    """Cache invalidates when config changes."""
    config1 = AnalysisConfig(frame_count=5)
    config2 = AnalysisConfig(frame_count=10)
    cache_dir = sample_video.parent / "generated"
    cache_dir.mkdir(exist_ok=True)

    # First run
    metrics1 = calculate_metrics([sample_video], config1, cache_dir)

    # Second run with different config
    metrics2 = calculate_metrics([sample_video], config2, cache_dir)

    # Assert - different results
    assert len(select_frames(metrics1, config1).frames) == 5
    assert len(select_frames(metrics2, config2).frames) == 10
```

### 3.3 Render Integration

```python
# tests/integration/test_render_integration.py

@pytest.mark.vs_required
def test_render_screenshots_with_overlay(sample_video, tmp_path):
    """Render screenshots with text overlay."""
    # Arrange
    config = RenderConfig(overlay_mode=OverlayMode.STANDARD)
    frames = [10, 50, 100]

    # Act
    results = render_screenshots(
        clips=[load_video(sample_video)],
        frames=frames,
        config=config,
        output_dir=tmp_path,
    )

    # Assert
    assert len(results) == len(frames)
    for path in results:
        assert path.exists()
        assert path.suffix == ".png"
        # Verify PNG is valid
        from PIL import Image
        img = Image.open(path)
        assert img.format == "PNG"

@pytest.mark.vs_required
def test_render_fallback_to_ffmpeg(sample_video, tmp_path, monkeypatch):
    """Falls back to FFmpeg when VS render fails."""
    # Arrange
    config = RenderConfig(use_ffmpeg=True)

    # Act
    results = render_screenshots(
        clips=[load_video(sample_video)],
        frames=[10],
        config=config,
        output_dir=tmp_path,
    )

    # Assert
    assert len(results) == 1
    assert results[0].exists()
```

### 3.4 Services Integration

```python
# tests/integration/test_services_integration.py

def test_audio_alignment_detects_offset(sample_audio_files):
    """Audio alignment detects known offset."""
    # Arrange - audio files with known 5-frame offset
    ref, comp = sample_audio_files
    config = AlignmentConfig(sample_rate=8000)

    # Act
    result = align_clips(ref, [comp], config, cache_dir=None)

    # Assert
    assert len(result) == 1
    assert abs(result[0].frame_offset - 5) <= 1  # Within 1 frame

@respx.mock
def test_slowpics_upload_with_retry(tmp_path):
    """slow.pics upload retries on failure."""
    # Arrange
    file1 = tmp_path / "test_0001.png"
    file1.write_bytes(b"PNG...")

    # Mock first request fails, second succeeds
    respx.post("https://slow.pics/api/comparison").mock(
        side_effect=[
            httpx.ConnectError(),
            httpx.Response(200, json={"url": "https://slow.pics/c/test"}),
        ]
    )

    config = SlowpicsConfig(max_retries=3)

    # Act
    result = asyncio.run(publish_to_slowpics(tmp_path, config))

    # Assert
    assert result.url == "https://slow.pics/c/test"

def test_metadata_parsing():
    """Filename parsing handles various formats."""
    test_cases = [
        ("Movie.2024.BluRay.1080p.mkv", {"title": "Movie", "year": 2024}),
        ("[Group] Anime - 01 [1080p].mkv", {"title": "Anime", "episode": 1}),
        ("Show.S01E05.Episode.Title.mkv", {"season": 1, "episode": 5}),
    ]

    for filename, expected in test_cases:
        result = parse_filename(filename)
        for key, value in expected.items():
            assert getattr(result, key) == value
```

### 3.5 CLI Integration

```python
# tests/integration/test_cli_integration.py

from typer.testing import CliRunner
from frame_compare.cli_entry import app

runner = CliRunner()

def test_cli_run_with_config(sample_workspace):
    """CLI run command uses config file."""
    result = runner.invoke(app, [
        "run",
        "--root", str(sample_workspace),
        "--no-upload",
    ])

    assert result.exit_code == 0
    assert "screenshots" in result.output.lower()

def test_cli_doctor_json_output():
    """Doctor command outputs valid JSON."""
    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code in [0, 3]  # Success or dep error
    data = json.loads(result.output)
    assert "checks" in data

def test_cli_error_handling():
    """CLI displays helpful error messages."""
    result = runner.invoke(app, ["run", "--root", "/nonexistent"])

    assert result.exit_code != 0
    assert "Error" in result.output
    assert "Hint" in result.output
```

---

## 4. End-to-End Test Scenarios

```python
# tests/e2e/test_full_pipeline.py

@pytest.mark.e2e
@pytest.mark.vs_required
def test_complete_comparison_workflow(sample_workspace):
    """Complete workflow from videos to screenshots."""
    # Arrange
    request = RunRequest(
        root=sample_workspace,
        no_upload=True,  # Don't actually upload
    )

    # Act
    result = run(request)

    # Assert
    assert result.success
    assert result.screenshot_dir.exists()
    assert result.frame_count > 0
    assert len(list(result.screenshot_dir.glob("*.png"))) > 0

@pytest.mark.e2e
@pytest.mark.vs_required
def test_cached_second_run(sample_workspace):
    """Second run uses cache and is faster."""
    request = RunRequest(root=sample_workspace, no_upload=True)

    # First run
    result1 = run(request)

    # Second run
    result2 = run(request)

    # Assert
    assert result1.success and result2.success
    assert result2.cache_hit
    assert result2.duration_seconds < result1.duration_seconds

@pytest.mark.e2e
@pytest.mark.slow
def test_docker_deployment(docker_compose):
    """Verify Docker deployment works."""
    # This test uses docker-compose to run the container
    result = subprocess.run(
        ["docker", "compose", "run", "--rm", "frame-compare", "doctor"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "VapourSynth" in result.stdout
```

---

## 5. Test Fixtures

```python
# tests/conftest.py

import pytest
from pathlib import Path

@pytest.fixture
def sample_workspace(tmp_path):
    """Create a sample workspace with test videos."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create directories
    (workspace / "comparison_videos").mkdir()
    (workspace / "config").mkdir()
    (workspace / "screenshots").mkdir()
    (workspace / "generated").mkdir()

    # Copy test videos (from test fixtures)
    fixtures = Path(__file__).parent / "fixtures"
    for video in fixtures.glob("*.mkv"):
        shutil.copy(video, workspace / "comparison_videos" / video.name)

    # Create config
    config = workspace / "config" / "config.toml"
    config.write_text("""
[analysis]
frame_count = 3

[slowpics]
auto_upload = false
""")

    return workspace

@pytest.fixture
def sample_video(sample_workspace):
    """Get a single sample video."""
    videos = list((sample_workspace / "comparison_videos").glob("*.mkv"))
    return videos[0]

@pytest.fixture
def mock_dependencies():
    """Return mocked RunDependencies for testing."""
    return RunDependencies(
        vs_loader=MockVSLoader(),
        ffmpeg_runner=MockFFmpegRunner(),
        http_client=MockHTTPClient(),
    )
```

---

## 6. CI Configuration

**SSOT:** `.github/workflows/ci.yml`

> [!IMPORTANT]
> CI commands and job structure change over time; do not copy/paste CI YAML from this document. Use `.github/workflows/ci.yml` as the canonical source.
