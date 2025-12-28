# Golden Test Fixtures

> **Module:** Reference
> **Purpose:** Define deterministic test fixtures for regression verification

---

## 1. Fixture Location

```
tests/fixtures/golden/
├── videos/
│   ├── sample_pq_1080p.mkv     # 10-second PQ HDR clip
│   ├── sample_hlg_1080p.mkv    # 10-second HLG clip
│   └── sample_sdr_1080p.mkv    # 10-second SDR clip
├── configs/
│   ├── default.toml            # Default config
│   └── all_options.toml        # All options specified
├── expected/
│   ├── metrics.json            # Expected metrics output
│   ├── selection.json          # Expected frame selection
│   └── report_structure.json   # Expected report keys
└── manifests/
    └── golden_v2.0.json        # Checksum manifest
```

---

## 2. Video Fixtures

### 2.1 Generation

```bash
# Generate reproducible test videos
ffmpeg -f lavfi -i testsrc2=size=1920x1080:rate=24:duration=10 \
       -c:v libx265 -crf 18 \
       -x265-params "colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc" \
       tests/fixtures/golden/videos/sample_pq_1080p.mkv
```

### 2.2 Properties

| Fixture | Duration | Resolution | HDR | Frames |
|:--------|:---------|:-----------|:----|:-------|
| sample_pq_1080p.mkv | 10s | 1920x1080 | PQ | 240 |
| sample_hlg_1080p.mkv | 10s | 1920x1080 | HLG | 240 |
| sample_sdr_1080p.mkv | 10s | 1920x1080 | No | 240 |

---

## 3. Expected Outputs

### 3.1 Metrics

```json
{
  "frame_count": 240,
  "avg_luminance": 0.42,
  "peak_luminance": 0.95,
  "motion_score_avg": 0.15,
  "selection_frames": [12, 48, 96, 144, 192]
}
```

### 3.2 Structural Checks

For outputs that vary slightly, use structural validation:

```python
def validate_report_structure(report: dict) -> None:
    """Validate report has expected structure."""
    assert "version" in report
    assert report["version"].startswith("2.")
    assert "frames" in report
    assert len(report["frames"]) == 5
    assert all("frame_number" in f for f in report["frames"])
```

---

## 4. Checksum Manifest

`manifests/golden_v2.0.json`:

```json
{
  "version": "2.0",
  "created": "2025-12-19",
  "fixtures": {
    "videos/sample_pq_1080p.mkv": {
      "sha256": "abc123...",
      "size_bytes": 12345678
    }
  },
  "expected_outputs": {
    "metrics/sample_pq_metrics.json": {
      "sha256": "def456..."
    }
  }
}
```

---

## 5. Test Workflow

```python
@pytest.fixture
def golden_pq_video() -> Path:
    """Return path to golden PQ fixture."""
    return FIXTURES / "videos" / "sample_pq_1080p.mkv"

def test_e2e_golden_pipeline(golden_pq_video, tmp_path):
    """
    Full pipeline test against golden fixture.

    Validates:
    - Frame count matches
    - Selection reproducible with seed
    - Report structure correct
    """
    result = run(RunRequest(
        input_dir=golden_pq_video.parent,
        frame_count=5,
        random_seed=42,
    ))

    assert result.success
    assert len(result.frames) == 5
    assert result.frames == [12, 48, 96, 144, 192]  # Reproducible with seed
```

---

## 6. CI Integration

```yaml
# .github/workflows/golden.yml
golden-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
      with:
        lfs: true  # Fetch video fixtures

    - name: Run golden tests
      run: pytest tests/golden/ -v --tb=short
```

---

## 7. Fixture Updates

When intentionally changing output:

1. Run `pytest tests/golden/ --update-golden`
2. Review diffs in PR
3. Update manifest with new checksums
4. Document reason in commit message
