# Test Directory Structure

> **Purpose:** Define the expected test organization for Frame Compare 2.0

---

## Directory Layout

```
tests/
├── conftest.py           # Shared fixtures, markers, pytest configuration
├── unit/                 # Fast tests, no external dependencies
│   ├── test_errors.py    # Error hierarchy tests
│   ├── test_config.py    # Config loading/validation
│   ├── test_utils.py     # Utility functions
│   └── ...
├── integration/          # Require VapourSynth, mocked network
│   ├── test_vs_loader.py # VapourSynth integration
│   ├── test_analysis.py  # Frame metrics calculation
│   └── ...
├── e2e/                  # Full pipeline tests
│   ├── test_cli.py       # CLI invocation tests
│   └── test_pipeline.py  # End-to-end workflow
├── golden/               # Regression tests with fixtures
│   ├── test_golden.py    # Golden fixture validation
│   └── ...
└── fixtures/             # Test data (LFS for videos)
    └── golden/           # Golden test fixtures
        ├── videos/
        ├── configs/
        └── expected/
```

---

## Markers

```python
# conftest.py
import pytest

pytest.mark.unit        # Fast, isolated tests
pytest.mark.integration # Require VapourSynth/external tools
pytest.mark.e2e         # Full pipeline tests
pytest.mark.slow        # Tests taking >5s
pytest.mark.network     # Require network (mocked by default)
```

---

## Running Tests

```bash
# Unit tests only (fastest)
pytest tests/unit/ -v

# Integration (requires VS)
pytest tests/integration/ -v

# All except slow
pytest -m "not slow"

# Full suite with coverage
pytest --cov=frame_compare --cov-report=html
```
