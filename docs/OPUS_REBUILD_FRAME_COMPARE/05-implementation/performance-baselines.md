# Performance Baselines

> **Module:** Testing  
> **Version:** 1.0

---

## 1. Overview

This document defines measurable performance targets for Frame Compare 2.0 operations.

---

## 2. Performance Targets

### 2.1 End-to-End Pipeline

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| **Full run (10 frames, 2 clips)** | < 30s | > 45s | > 60s |
| **Cached run** | < 5s | > 10s | > 15s |
| **Memory peak** | < 2GB | > 3GB | > 4GB |
| **Docker cold start** | < 10s | > 20s | > 30s |

### 2.2 Per-Operation Targets

| Operation | Target | Warning | Critical |
|-----------|--------|---------|----------|
| **Config load** | < 50ms | > 100ms | > 200ms |
| **Video open** | < 500ms | > 1s | > 2s |
| **Frame extraction (per frame)** | < 200ms | > 400ms | > 800ms |
| **Luminance calc (all frames)** | < 2s | > 4s | > 8s |
| **Motion calc (all frames)** | < 3s | > 6s | > 10s |
| **Frame selection** | < 10ms | > 50ms | > 100ms |
| **Audio alignment (2 clips)** | < 5s | > 10s | > 20s |
| **Screenshot render (per frame)** | < 500ms | > 1s | > 2s |
| **Tonemapping (per frame)** | < 300ms | > 600ms | > 1s |
| **slow.pics upload (10 images)** | < 10s | > 20s | > 30s |
| **HTML report generation** | < 1s | > 2s | > 5s |

### 2.3 Cache Operations

| Operation | Target | Warning | Critical |
|-----------|--------|---------|----------|
| **Cache read** | < 50ms | > 100ms | > 200ms |
| **Cache write** | < 100ms | > 200ms | > 500ms |
| **Cache key computation** | < 5ms | > 10ms | > 20ms |

---

## 3. Benchmark Specifications

### 3.1 Reference Hardware

```yaml
CPU: AMD Ryzen 7 5800X (8 cores)
RAM: 32GB DDR4
Storage: NVMe SSD
GPU: Not required (CPU-only testing)
OS: Ubuntu 22.04 / Docker
```

### 3.2 Reference Videos

| Name | Resolution | Duration | Format |
|------|------------|----------|--------|
| `reference_4k_hdr.mkv` | 3840x2160 | 60s | HEVC, HDR10 |
| `reference_1080p_sdr.mkv` | 1920x1080 | 60s | H.264, SDR |
| `short_test.mkv` | 1920x1080 | 10s | H.264, SDR |

### 3.3 Benchmark Script

```python
# tests/perf/benchmark.py

import time
from dataclasses import dataclass
from statistics import mean, stdev

@dataclass
class BenchmarkResult:
    name: str
    samples: list[float]
    
    @property
    def mean_ms(self) -> float:
        return mean(self.samples) * 1000
    
    @property
    def stdev_ms(self) -> float:
        return stdev(self.samples) * 1000 if len(self.samples) > 1 else 0
    
    @property
    def status(self) -> str:
        # Compare against targets
        targets = TARGETS.get(self.name, (float('inf'), float('inf')))
        if self.mean_ms < targets[0]:
            return "✅ PASS"
        elif self.mean_ms < targets[1]:
            return "⚠️ WARN"
        else:
            return "❌ FAIL"

TARGETS = {
    "config_load": (50, 100),
    "video_open": (500, 1000),
    "frame_extraction": (200, 400),
    "frame_selection": (10, 50),
    "cache_read": (50, 100),
}

def benchmark(name: str, fn, iterations: int = 10) -> BenchmarkResult:
    """Run benchmark with multiple iterations."""
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return BenchmarkResult(name=name, samples=samples)

def run_all_benchmarks():
    """Run all benchmarks and report results."""
    results = [
        benchmark("config_load", lambda: load_config(config_path)),
        benchmark("video_open", lambda: load_video(video_path)),
        benchmark("frame_extraction", lambda: extract_frame(clip, 100)),
        benchmark("frame_selection", lambda: select_frames(metrics, config)),
        benchmark("cache_read", lambda: load_cached_metrics(cache_dir, key)),
    ]
    
    print("\n=== Performance Benchmark Results ===\n")
    for r in results:
        print(f"{r.name:30} {r.mean_ms:8.2f}ms ± {r.stdev_ms:.2f}ms  {r.status}")
```

---

## 4. Memory Profiling

### 4.1 Memory Targets

| Scenario | Peak RAM | VapourSynth Cache |
|----------|----------|-------------------|
| 1080p, 2 clips | < 1GB | 512MB |
| 4K, 2 clips | < 2GB | 1GB |
| 4K, 4 clips | < 3GB | 1.5GB |
| Maximum allowed | < 4GB | 2GB |

### 4.2 Memory Profiling Script

```python
# tests/perf/memory_profile.py

import tracemalloc
from memory_profiler import profile

@profile
def measure_run_memory():
    """Profile memory usage during a run."""
    request = RunRequest(root=workspace)
    result = run(request)
    return result

def track_memory():
    """Track memory allocations."""
    tracemalloc.start()
    
    # Run pipeline
    result = run(request)
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print(f"Current: {current / 1024 / 1024:.2f} MB")
    print(f"Peak: {peak / 1024 / 1024:.2f} MB")
```

---

## 5. CI Performance Testing

### 5.1 GitHub Actions Configuration

```yaml
# .github/workflows/benchmark.yml

name: Performance Benchmarks

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup
        run: uv sync --extra bench
      
      - name: Download test videos
        run: |
          curl -o tests/fixtures/short_test.mkv $VIDEO_URL
      
      - name: Run benchmarks
        run: uv run --no-sync python tests/perf/benchmark.py
      
      - name: Check for regressions
        run: uv run --no-sync python tests/perf/check_regression.py
      
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results
          path: benchmark-results.json
```

### 5.2 Regression Detection

```python
# tests/perf/check_regression.py

import json

REGRESSION_THRESHOLD = 1.2  # 20% slower = regression

def check_regression():
    """Compare against baseline and fail if regression detected."""
    current = load_results("benchmark-results.json")
    baseline = load_results("baseline.json")
    
    regressions = []
    for name, result in current.items():
        if name in baseline:
            ratio = result["mean"] / baseline[name]["mean"]
            if ratio > REGRESSION_THRESHOLD:
                regressions.append((name, ratio))
    
    if regressions:
        print("❌ Performance regressions detected:")
        for name, ratio in regressions:
            print(f"  {name}: {ratio:.2f}x slower")
        sys.exit(1)
    
    print("✅ No performance regressions")
```

---

## 6. Optimization Guidelines

### 6.1 Common Bottlenecks

| Bottleneck | Symptom | Solution |
|------------|---------|----------|
| Frame extraction | Slow per-frame | Batch frame requests |
| Memory spikes | OOM errors | Reduce VS cache size |
| Audio alignment | Slow correlation | Lower sample rate |
| Upload | Slow transfer | Parallel upload |
| Cache misses | Full recompute | Verify cache keys |

### 6.2 VapourSynth Tuning

```python
# Optimal cache settings
import vapoursynth as vs
core = vs.core
core.max_cache_size = 1024  # MB, adjust based on RAM
core.num_threads = 4  # Match CPU cores
```

### 6.3 Async Optimization

```python
# Parallel operations where possible
async def optimized_pipeline():
    # Audio alignment and metadata lookup can run in parallel
    alignment_task = asyncio.create_task(align_clips(...))
    metadata_task = asyncio.create_task(lookup_tmdb(...))
    
    alignment, metadata = await asyncio.gather(alignment_task, metadata_task)
```
