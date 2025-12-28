# Quality Standards

> **Module:** Quality Assurance
> **Version:** 1.0

---

## 1. Code Quality

### 1.1 Formatting

```toml
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py313']
```

**Enforcement:** Pre-commit hook, CI check

### 1.2 Linting

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py313"
select = ["E", "F", "I", "W"]
ignore = ["E501"]
```

**Enforcement:** Pre-commit hook, CI check

### 1.3 Type Checking

```toml
# pyproject.toml
[tool.pyright]
include = ["src"]
pythonVersion = "3.13"
typeCheckingMode = "strict"
```

**Enforcement:** CI check, blocking

### 1.4 Import Contracts

```ini
# importlinter.ini
[importlinter]
root_package = frame_compare

[importlinter:contract:layers]
name = Layered architecture
type = layers
layers =
    cli_layer
    orchestration_layer
    service_layer
    domain_layer
```

**Enforcement:** CI check, blocking

---

## 2. Testing Standards

### 2.1 Coverage Requirements

| Scope | Minimum | Target |
|-------|---------|--------|
| Overall | 80% | 90% |
| Core Domain | 90% | 95% |
| Services | 80% | 90% |
| CLI | 70% | 80% |

### 2.2 Test Categories

| Marker | Description | CI Stage |
|--------|-------------|----------|
| `@pytest.mark.unit` | Fast, isolated | All pushes |
| `@pytest.mark.integration` | Component tests | PR |
| `@pytest.mark.vs_required` | VapourSynth | Container CI |
| `@pytest.mark.slow` | Long-running | Nightly |
| `@pytest.mark.network` | External calls | Optional |

### 2.3 Test Naming

```python
# Pattern: test_{method}_{scenario}_{expected}

def test_select_frames_with_valid_metrics_returns_expected_count():
    ...

def test_load_cache_with_corrupt_file_returns_miss():
    ...
```

---

## 3. Documentation Standards

### 3.1 Docstrings

```python
def calculate_metrics(
    clips: list[ClipPlan],
    config: AnalysisConfig,
) -> FrameMetrics:
    """
    Calculate frame metrics for video clips.

    Computes luminance and motion scores for each frame,
    using cached values when available.

    Args:
        clips: Video clips to analyze.
        config: Analysis configuration parameters.

    Returns:
        FrameMetrics containing luminance and motion arrays.

    Raises:
        AnalysisError: If video cannot be analyzed.

    Example:
        >>> metrics = calculate_metrics(clips, config)
        >>> len(metrics.luminance)
        24000
    """
```

### 3.2 API Documentation

- All public functions have docstrings
- Type hints on all parameters and returns
- Examples for complex APIs

### 3.3 Architecture Documentation

- ADRs for significant decisions
- Module specs for each component
- System diagrams maintained

---

## 4. Code Review

### 4.1 Review Checklist

**Correctness**

- [ ] Logic is correct
- [ ] Edge cases handled
- [ ] Error handling appropriate

**Security**

- [ ] No credential leakage
- [ ] Input sanitized
- [ ] Subprocess calls safe

**Maintainability**

- [ ] Code is readable
- [ ] Comments explain "why"
- [ ] Tests cover changes

**Performance**

- [ ] No obvious bottlenecks
- [ ] Resource cleanup proper
- [ ] Cache usage appropriate

### 4.2 Review Requirements

| Change Type | Reviewers | Approval |
|-------------|-----------|----------|
| Bug fix | 1 | 1 approval |
| Feature | 2 | 1 approval |
| Architecture | 2 | 2 approvals |
| Security | 1 + security lead | Security approval |

---

## 5. Definition of Done

### 5.1 Feature DoD

- [ ] Implementation complete
- [ ] Unit tests written and passing
- [ ] Integration tests (if applicable)
- [ ] Documentation updated
- [ ] Code reviewed and approved
- [ ] No lint/type errors
- [ ] Coverage threshold met
- [ ] PR merged to main

### 5.2 Release DoD

- [ ] All P0 features implemented
- [ ] All P1 features implemented or documented as deferred
- [ ] Full test suite passing
- [ ] Security audit passed
- [ ] Performance acceptable
- [ ] Documentation complete
- [ ] Release notes written
- [ ] Changelog updated

---

## 6. CI/CD Pipeline

### 6.1 Pipeline Stages

```yaml
# .github/workflows/ci.yml
stages:
  - lint:       # Ruff, format check
  - typecheck:  # Pyright
  - test:       # pytest unit
  - integrate:  # pytest integration
  - container:  # Container build & test
  - publish:    # PyPI, ghcr.io (tags only)
```

### 6.2 Quality Gates

| Gate | Requirement | Blocking |
|------|-------------|----------|
| Lint | 0 errors | Yes |
| Types | 0 Pyright errors | Yes |
| Unit Tests | 100% pass | Yes |
| Coverage | ≥80% | Yes |
| Imports | Contracts kept | Yes |
| Integration | 100% pass | Yes |
| Container | Builds successfully | Yes |

---

## 7. Continuous Improvement

### 7.1 Metrics Tracking

- Test coverage over time
- Bug escape rate
- Review cycle time
- Build success rate

### 7.2 Quality Reviews

| Frequency | Scope |
|-----------|-------|
| Sprint | Test coverage review |
| Monthly | Technical debt assessment |
| Quarterly | Architecture review |
