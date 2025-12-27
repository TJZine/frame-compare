# ADR-001: Language and Runtime

## Status

Accepted

## Date

2025-12-16

## Context

Frame Compare is being rebuilt from the ground up. We need to select a programming language and runtime that:

- Integrates well with VapourSynth (the core video processing engine)
- Has strong ecosystem for CLI tools, networking, and data processing
- Supports modern development practices (type checking, testing)
- Enables containerization for zero-config deployment

## Decision

**Use Python 3.13+ as the sole runtime.**

## Considered Alternatives

### Alternative 1: Python 3.11/3.12

- Pros: Wider compatibility, more stable
- Cons: `librosa`/`numba` issues on 3.14 anyway, 3.13 performance improvements

### Alternative 2: Rust with Python bindings

- Pros: Performance, memory safety
- Cons: VapourSynth bindings less mature, team expertise, build complexity

### Alternative 3: TypeScript/Node.js

- Pros: Modern tooling, async-first
- Cons: No VapourSynth binding, NumPy/Librosa unavailable

## Rationale

- VapourSynth has first-class Python bindings
- NumPy, Librosa, and other audio processing libraries require Python
- Python 3.13 offers improved performance and better typing support
- The existing v0.0.14 codebase is Python, minimizing rewrite scope
- `uv` provides modern, fast package management

## Consequences

### Positive

- Native VapourSynth integration
- Rich ecosystem for all required functionality
- Familiar to video encoding community
- Strong typing with Pyright strict mode

### Negative

- Single-threaded GIL limitations (mitigated by VapourSynth's threading)
- Performance ceiling lower than compiled languages
- Python 3.13 only limits deployment to modern environments

### Risks

- Python 3.14 may break dependencies (mitigated: pin to 3.13.x)

## References

- VapourSynth Python documentation
- Python 3.13 release notes
