# Non-Functional Requirements

> **Module:** Requirements Specification  
> **Version:** 1.0

---

## 1. Performance Requirements

### NFR-PERF-001: CLI Response Time

```yaml
Requirement: CLI must respond within 500ms for cached operations
Measurement: Time from command invocation to first output
Priority: High
Rationale: Responsive CLI improves developer experience
Verification: Performance test suite with timing assertions
```

### NFR-PERF-002: Frame Analysis Throughput

```yaml
Requirement: Process minimum 10 fps for frame metrics calculation
Measurement: Frames analyzed per second
Priority: Medium
Rationale: Large video files need reasonable processing time
Verification: Benchmark suite with sample videos
```

### NFR-PERF-003: Memory Usage

```yaml
Requirement: Peak memory usage under 2GB for typical workflows
Measurement: RSS memory during processing
Priority: Medium
Rationale: Enable use on standard workstations
Verification: Memory profiling with py-spy or memray
```

### NFR-PERF-004: Screenshot Rendering

```yaml
Requirement: Render single screenshot in under 5 seconds
Measurement: Wall clock time per frame
Priority: High
Rationale: Batch processing scalability
Verification: Rendering benchmark
```

---

## 2. Scalability Requirements

### NFR-SCALE-001: File Count

```yaml
Requirement: Support up to 20 video files per comparison
Measurement: Successful completion with N files
Priority: Medium
Rationale: Complex multi-encode comparisons
Verification: Integration test with 20 files
```

### NFR-SCALE-002: Frame Count

```yaml
Requirement: Support up to 100 frames per comparison
Measurement: Successful selection and rendering
Priority: Medium
Rationale: Comprehensive comparison sets
Verification: Large frame count test
```

### NFR-SCALE-003: Video Duration

```yaml
Requirement: Handle videos up to 4 hours in length
Measurement: Successful processing of long-form content
Priority: Low
Rationale: Feature film and concert video support
Verification: Long video integration test
```

---

## 3. Reliability Requirements

### NFR-REL-001: Graceful Degradation

```yaml
Requirement: Fall back to FFmpeg when VapourSynth unavailable
Measurement: Successful completion with degraded renderer
Priority: High
Rationale: Reduce critical dependency chain
Verification: Integration test with VS disabled
```

### NFR-REL-002: Network Resilience

```yaml
Requirement: Retry failed uploads with exponential backoff
Measurement: Successful recovery from transient failures
Priority: High
Rationale: Unreliable network conditions
Verification: Mock server with failure injection
```

### NFR-REL-003: Cache Robustness

```yaml
Requirement: Treat corrupt cache as cache miss (not error)
Measurement: Recovery from malformed cache files
Priority: High
Rationale: Avoid workflow interruption
Verification: Corruption injection tests
```

### NFR-REL-004: Error Recovery

```yaml
Requirement: Partial failures must not lose completed work
Measurement: Screenshots preserved on publish failure
Priority: High
Rationale: Large batch processing investment
Verification: Fault injection testing
```

---

## 4. Security Requirements

### NFR-SEC-001: API Key Protection

```yaml
Requirement: API keys (TMDB, etc.) stored securely
Measurement: Keys not logged, not in error messages
Priority: High
Rationale: Credential protection
Verification: Log audit, error message review
```

### NFR-SEC-002: Path Traversal Prevention

```yaml
Requirement: Workspace containment enforced for all file operations
Measurement: Cannot write outside configured directories
Priority: Critical
Rationale: Prevent malicious path manipulation
Verification: Path traversal test suite
```

### NFR-SEC-003: Input Sanitization

```yaml
Requirement: User input sanitized for console output
Measurement: No ANSI escape injection, XSS in HTML
Priority: Medium
Rationale: Safe handling of arbitrary filenames
Verification: Malicious filename tests
```

### NFR-SEC-004: Subprocess Security

```yaml
Requirement: All subprocess calls use shell=False
Measurement: No shell injection vectors
Priority: Critical
Rationale: Command injection prevention
Verification: Code audit, subprocess wrapper
```

---

## 5. Maintainability Requirements

### NFR-MAINT-001: Code Coverage

```yaml
Requirement: Minimum 80% line coverage
Measurement: pytest-cov reports
Priority: High
Rationale: Regression prevention
Verification: CI coverage gate
```

### NFR-MAINT-002: Type Safety

```yaml
Requirement: 100% pyright strict compliance
Measurement: Zero pyright errors
Priority: High
Rationale: Early bug detection, IDE support
Verification: CI pyright check
```

### NFR-MAINT-003: Lint Compliance

```yaml
Requirement: Zero ruff errors
Measurement: Ruff check passes
Priority: High
Rationale: Consistent code style
Verification: CI and pre-commit hooks
```

### NFR-MAINT-004: Import Contracts

```yaml
Requirement: All import-linter contracts kept
Measurement: Zero broken contracts
Priority: High
Rationale: Architectural boundary enforcement
Verification: CI lint-imports check
```

### NFR-MAINT-005: Documentation

```yaml
Requirement: All public APIs have docstrings
Measurement: Documentation coverage tool
Priority: Medium
Rationale: Developer onboarding, API stability
Verification: Docstring linting
```

---

## 6. Usability Requirements

### NFR-USE-001: Zero-Config Startup

```yaml
Requirement: Docker Compose starts complete environment
Measurement: Single command deployment
Priority: Critical
Rationale: Eliminate installation friction
Verification: Fresh environment test
```

### NFR-USE-002: Helpful Error Messages

```yaml
Requirement: Errors include actionable guidance
Measurement: User can resolve issue from message
Priority: High
Rationale: Self-service troubleshooting
Verification: Error message review
```

### NFR-USE-003: Progress Feedback

```yaml
Requirement: Long operations show progress indication
Measurement: Visual feedback for >2 second operations
Priority: Medium
Rationale: User confidence during processing
Verification: UI review
```

### NFR-USE-004: Configuration Discovery

```yaml
Requirement: wizard command guides initial setup
Measurement: New user can configure in <5 minutes
Priority: Medium
Rationale: Onboarding experience
Verification: User testing
```

---

## 7. Compatibility Requirements

### NFR-COMPAT-001: Platform Support

```yaml
Requirement: Support Linux and Windows 64-bit
Measurement: CI passes on both platforms
Priority: Critical
Rationale: Primary user platforms
Verification: Multi-platform CI
Note: macOS support deferred to Phase 2
```

### NFR-COMPAT-002: Python Version

```yaml
Requirement: Support Python 3.13+
Measurement: CI tests on Python 3.13
Priority: Critical
Rationale: Modern language features, dependency requirements
Verification: CI matrix
```

### NFR-COMPAT-003: VapourSynth Version

```yaml
Requirement: Support VapourSynth R72+
Measurement: API compatibility tests
Priority: Critical
Rationale: Core dependency version
Verification: VS version check in doctor
```

### NFR-COMPAT-004: Config Migration

```yaml
Requirement: Existing v0.0.14 configs load successfully
Measurement: Migration test suite
Priority: High
Rationale: Upgrade path for existing users
Verification: Legacy config tests
```

---

## 8. Observability Requirements

### NFR-OBS-001: Structured Logging

```yaml
Requirement: All operations emit structured log records
Measurement: JSON-parseable log output available
Priority: Medium
Rationale: Debug support, monitoring integration
Verification: Log format tests
```

### NFR-OBS-002: JSON Telemetry

```yaml
Requirement: Run results available as JSON
Measurement: Programmatic access to results
Priority: High
Rationale: Automation integration
Verification: JSON output tests
```

### NFR-OBS-003: Progress Tracking

```yaml
Requirement: Each pipeline stage reports progress
Measurement: Rich progress bars for long operations
Priority: Medium
Rationale: User experience
Verification: Console output review
```

---

## 9. Deployment Requirements

### NFR-DEPLOY-001: Container Image

```yaml
Requirement: Official Docker image with all dependencies
Measurement: docker pull and run succeeds
Priority: Critical
Rationale: Zero-config deployment goal
Verification: Container build CI
```

### NFR-DEPLOY-002: DevContainer Support

```yaml
Requirement: VS Code DevContainer for development
Measurement: Click-to-code developer experience
Priority: High
Rationale: Developer onboarding
Verification: DevContainer test
```

### NFR-DEPLOY-003: PyPI Package

```yaml
Requirement: pip-installable package
Measurement: pip install frame-compare succeeds
Priority: High
Rationale: Standard Python distribution
Verification: TestPyPI publish
```

---

## 10. NFR Summary Matrix

| Category | Critical | High | Medium | Low |
|----------|----------|------|--------|-----|
| Performance | 0 | 2 | 2 | 0 |
| Scalability | 0 | 0 | 2 | 1 |
| Reliability | 0 | 4 | 0 | 0 |
| Security | 2 | 1 | 1 | 0 |
| Maintainability | 0 | 4 | 1 | 0 |
| Usability | 1 | 2 | 2 | 0 |
| Compatibility | 2 | 1 | 0 | 0 |
| Observability | 0 | 1 | 2 | 0 |
| Deployment | 1 | 2 | 0 | 0 |
| **Total** | **6** | **17** | **10** | **1** |
