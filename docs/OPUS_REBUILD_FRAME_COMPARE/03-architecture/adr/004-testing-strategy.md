# ADR-004: Testing Strategy

## Status

Accepted

## Date

2025-12-16

## Context

Frame Compare has external dependencies (VapourSynth, FFmpeg, network services) that complicate testing. We need a strategy that:

- Enables fast, reliable CI
- Supports testing without VapourSynth installed
- Provides confidence in critical paths
- Enables TDD workflow

## Decision

**Adopt a layered testing strategy with pytest, extensive mocking, and marker-based test categorization.**

## Test Layers

### 1. Unit Tests (`@pytest.mark.unit`)

- Fast, isolated, no external dependencies
- Mock all I/O and external calls
- Target: 80%+ of test volume

### 2. Integration Tests (`@pytest.mark.integration`)

- Test component interactions
- Use test fixtures (sample videos)
- Slower, run on PR

### 3. VapourSynth Tests (`@pytest.mark.vs_required`)

- Require VapourSynth runtime
- Skipped in environments without VS
- Run in container CI

### 4. Network Tests (`@pytest.mark.network`)

- Require network access
- Mock by default, real calls optional
- Sandboxed API testing

## Implementation

### Pytest Configuration

```ini
[tool.pytest.ini_options]
pythonpath = [".", "src"]
addopts = "-p no:vsengine"
markers = [
    "vs_required: Requires VapourSynth",
    "integration: E2E tests",
    "unit: Fast isolated tests",
    "slow: Long-running tests",
    "network: Requires network"
]
```

### Shared Fixtures

```python
# tests/conftest.py
@pytest.fixture
def cli_runner_env():
    """Provides isolated CLI test environment"""
    ...

@pytest.fixture
def runner_vs_core_stub(monkeypatch):
    """Stubs VapourSynth for runner tests"""
    ...

@pytest.fixture
def dummy_progress():
    """Stubs Rich progress for output tests"""
    ...
```

### Import-Linter Integration

```ini
# importlinter.ini
[importlinter:contract:layers]
name = Core must not import CLI
type = layers
layers =
    cli_layer
    orchestration_layer
    service_layer
    domain_layer
```

## Consequences

### Positive

- Fast CI (unit tests in seconds)
- Tests run without VapourSynth
- Clear test organization
- Shared fixtures reduce duplication

### Negative

- Mocking overhead
- Mock/real behavior drift risk
- Container CI needed for full coverage

### Risks

- VapourSynth stub diverges from real behavior
- Network mock doesn't catch API changes

## References

- pytest documentation
- pytest-mock documentation
