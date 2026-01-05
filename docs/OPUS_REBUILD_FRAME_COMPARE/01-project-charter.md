# Frame Compare 2.0 — Project Charter

> **Version:** 1.0 | **Status:** Draft

---

## 1. Project Definition

### 1.1 Project Identity

```yaml
Project Name: Frame Compare
Project Code: FC-2.0
Current Version: 0.0.14 (baseline for recreation)
Target Version: 2.0.0
License: MIT
Repository: github.com/TJZine/frame-compare
```

### 1.2 Problem Statement

The current Frame Compare implementation (v0.0.14) has accumulated technical debt through iterative development:

1. **Installation Complexity**: VapourSynth dependency chain causes friction across platforms
2. **Monolithic Growth**: Large files with mixed concerns (e.g., `screenshot.py` at 2000+ lines)
3. **Testing Gaps**: Some test suites require complex environment setup
4. **Configuration Drift**: Multiple config approaches (TOML, CLI, env vars) with inconsistent precedence
5. **Platform Fragmentation**: macOS support paused due to toolchain issues

### 1.3 Solution Overview

A ground-up rebuild that:

- **Containerizes** the entire VapourSynth toolchain for zero-config deployment
- **Modularizes** the codebase with strict layer boundaries
- **Standardizes** configuration with clear precedence rules
- **Tests** comprehensively with isolated, mockable services
- **Documents** thoroughly for AI agent and human developer consumption

---

## 2. Scope Definition

### 2.1 In-Scope Features

#### P0 — Must Have (Launch Blockers)

| Feature | Description | Source |
|---------|-------------|--------|
| Frame Selection | Luminance quantiles, motion scoring, seeded random | `analysis/` |
| HDR Tonemapping | libplacebo presets, BT.2390, Dolby Vision | `vs/tonemap.py` |
| Audio Alignment | Cross-correlation (DTW deferred), per-clip offsets | `alignment.py` |
| Screenshot Rendering | VapourSynth primary, FFmpeg fallback | `screenshot/`, `render/` |
| slow.pics Publishing | Upload with retry, shortcut creation | `publishers.py` |
| CLI Interface | Typer-based (`run`, `wizard`, `doctor`, `preset`) | `cli_entry.py` |
| Config Management | TOML loading, validation, migration | `config_loader.py` |
| Caching | Frame metrics, audio offsets, run snapshots | `cache.py`, `analysis/cache_io.py` |

#### P1 — Should Have

| Feature | Description | Source |
|---------|-------------|--------|
| TMDB Integration | Metadata resolution, title matching | `tmdb.py`, `tmdb_workflow.py` |
| HTML Report | Offline viewer with slider/overlay/diff modes | `report.py`, `data/report/` |
| Dolby Vision | DoVi metadata handling | `dovi_tool.py` |
| Preset System | Save/load/apply configuration presets | `presets.py` |

#### P2 — Nice to Have

| Feature | Description | Source |
|---------|-------------|--------|
| VSPreview Integration | Interactive alignment confirmation | `vspreview.py` |
| Clipboard Shortcuts | pyperclip integration | Optional dependency |

### 2.2 Out-of-Scope

| Item | Rationale | Future Consideration |
|------|-----------|---------------------|
| macOS Support | VapourSynth toolchain issues | Phase 2 post-launch |
| Real-time Preview | Batch processing focus | Not planned |
| Web UI / SPA | CLI-first approach | Not planned |
| GPU Acceleration | Maintain universal deployment | Phase 3+ if demand |
| Cloud Processing | Local execution model | Not planned |
| New Features | Clean recreation first | Post 2.0 releases |

---

## 3. Success Criteria

### 3.1 Functional Success

| Criterion | Metric | Verification |
|-----------|--------|--------------|
| Feature Parity | 100% of P0/P1 features working | Feature comparison matrix |
| CLI Compatibility | All existing commands/flags work | CLI test suite |
| Config Compatibility | Existing config.toml files load | Migration tests |
| API Compatibility | `RunRequest`/`RunResult` pattern | API test suite |
| Output Equivalence | Same screenshots for same inputs | Pixel-diff tests |

### 3.2 Quality Success

| Criterion | Metric | Verification |
|-----------|--------|--------------|
| Test Coverage | ≥80% line coverage | Coverage reports |
| Type Safety | 0 Pyright errors (strict mode) | CI checks |
| Lint Clean | 0 Ruff errors | CI checks |
| Import Contracts | All contracts kept | import-linter CI |
| Documentation | All public APIs documented | Doc coverage |

### 3.3 Operational Success

| Criterion | Metric | Verification |
|-----------|--------|--------------|
| Docker Startup | Single `docker compose up` | E2E test |
| CLI Response | <500ms for cached operations | Performance test |
| Memory Usage | <2GB for typical workflows | Profiling |
| Error Recovery | Graceful degradation on failures | Error handling tests |

---

## 4. Governance

### 4.1 Decision Authority

| Decision Type | Authority | Escalation |
|---------------|-----------|------------|
| Architecture | Tech Lead (AI or human) | Document as ADR |
| Feature Scope | Product Owner | Charter amendment |
| Technology Choice | Tech Lead | ADR with alternatives |
| Quality Standards | Team consensus | Quality doc update |
| Timeline Changes | Project Manager | Stakeholder notification |

### 4.2 Change Control

1. **Minor Changes**: Bug fixes, documentation — direct commit
2. **Moderate Changes**: Refactoring, performance — PR with review
3. **Major Changes**: Architecture, scope — ADR + stakeholder approval

### 4.3 Communication Cadence

| Meeting | Frequency | Purpose |
|---------|-----------|---------|
| Sprint Planning | Bi-weekly | Scope upcoming work |
| Technical Review | Weekly | Architecture decisions |
| Stakeholder Update | Monthly | Progress, risks, blockers |

---

## 5. Quality Standards

### 5.1 Code Quality

```yaml
Code Standards:
  Formatting:
    Tool: black
    Line Length: 100
    Target: py313

  Linting:
    Tool: ruff
    Rules: [E, F, I, W]
    Ignore: [E501]

  Type Checking:
    Tool: pyright
    Mode: strict
    Marker: py.typed

  Import Contracts:
    Tool: import-linter
    Layers: [CLI, Runner, Core, Modules]
    Forbidden: [CLI→Core backimports]
```

### 5.2 Testing Standards

```yaml
Testing:
  Framework: pytest
  Markers:
    - vs_required: Requires VapourSynth runtime
    - integration: End-to-end CLI tests
    - unit: Fast isolated tests
    - slow: Long-running tests
    - network: Requires network access

  Coverage:
    Minimum: 80%
    Critical Paths: 95%

  Fixtures:
    Location: tests/conftest.py, tests/helpers/
    Patterns: Factory functions, DI mocks
```

### 5.3 Documentation Standards

| Type | Location | Format |
|------|----------|--------|
| API Docs | Docstrings | Google style |
| Architecture | docs/ | Markdown + Mermaid |
| User Guide | README.md | Markdown |
| Config Reference | docs/config_reference.md | Tables |
| Decisions | docs/DECISIONS.md | Log format |

---

## 6. Risk Summary

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| VapourSynth container build fails | Medium | Critical | Multi-stage build, fallback images |
| libplacebo API changes | Low | High | Pin versions, abstraction layer |
| slow.pics API changes | Low | Medium | Adapter pattern, local fallback |
| Feature parity gaps discovered late | Medium | Medium | Early feature matrix validation |
| Performance regression | Medium | Medium | Benchmark suite, profiling |

---

## 7. Glossary

| Term | Definition |
|------|------------|
| **VapourSynth** | Video processing framework for frame-by-frame manipulation |
| **libplacebo** | GPU-accelerated video processing library (used for tonemapping) |
| **HDR** | High Dynamic Range — wider luminance and color range |
| **Tonemapping** | Converting HDR content to SDR for display |
| **slow.pics** | Image comparison hosting service |
| **TMDB** | The Movie Database — metadata source |
| **DTW** | Dynamic Time Warping — legacy/optional audio alignment algorithm (deferred in 2.0 MVP) |
| **Fansub** | Fan-produced subtitles for media |
| **QC** | Quality Control — verification of encoding quality |

---

## 8. Approvals

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Project Sponsor | | | |
| Tech Lead | | | |
| Product Owner | | | |
