# Windows Portable Bundle — User Interview (Decision Capture)

> **Module:** Distribution
> **Version:** 1.0
> **Purpose:** Template for orchestrator ↔ user decision capture

---

## 0. Decisions (Resolved)

- Supported OS range: **Windows 10 + 11**
- Supported architecture baseline: **x86_64 (amd64) only**
- Packaging strategy: **Pinned portable folder with embedded Python runtime** (not PyInstaller)
- BYO VapourSynth: **Allowed best-effort**; only the pinned bundle baseline is supported/CI-tested
- GPU expectation: **GPU optional; fallback must always work**

---

## 1. Required Decisions (Blocking)

1. **Supported OS range**
   - Windows 11 only, or Windows 10+11?
2. **Architecture**
    - x86_64 only, or x86_64 + ARM64?
3. **Packaging strategy (choose one)**
    - A) Embeddable Python distribution + preinstalled dependencies
    - B) PyInstaller single EXE (risk: DLL/plugin loading complexity)
4. **Bundled baseline vs BYO**
   - Baseline only, or baseline + best-effort BYO VS (recommended: both)
5. **GPU expectation**
   - “GPU optional, fallback always works” (recommended)
   - “GPU required” (only realistic for constrained environments)

---

## 2. Artifact Requirements (Blocking)

Collect exact upstream sources and pinning rules for:

- VapourSynth runtime (Windows distribution)
- Plugins:
  - L-SMASH Works
  - vs-placebo
  - ffms2 (if included)
- FFmpeg (Windows)

For each artifact:

- version/tag/commit
- download URL(s)
- sha256
- license note

---

## 3. Verification Expectations (Blocking)

1. What minimum “smoke run” should the portable bundle pass?
   - Example: `frame-compare doctor --json`
2. What minimum “tonemap behavior” should be validated?
   - Example: tonemap returns a `VideoNode` and does not raise (fallback allowed)
3. If you want a “GPU required” check, where should it run?
   - Recommended: Linux GPU CI only, not Windows/macOS Docker Desktop.
