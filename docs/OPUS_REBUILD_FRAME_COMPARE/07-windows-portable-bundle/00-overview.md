# Windows Portable Bundle (Baseline Distribution)

> **Module:** Distribution
> **Version:** 1.0
> **Status:** SSOT for Windows portable baseline expectations

---

## 1. Goal

Provide a **tested, pinned Windows portable bundle** for Frame Compare 2.0 that:

- Runs without Docker.
- Includes a known-good baseline of VapourSynth + required plugins + FFmpeg.
- Supports HDR→SDR tonemapping via libplacebo **when available**, and uses deterministic fallback otherwise.
- Allows users to bring their own VapourSynth install (best-effort), while only the bundle baseline is supported/CI-tested.

**Baseline target:** Windows 10/11 x86_64 (amd64) portable folder with embedded Python runtime.

Execution playbook:

- `docs/OPUS_REBUILD_FRAME_COMPARE/07-windows-portable-bundle/05-agent-playbook.md`

---

## 2. Key Principles

1. **Baseline is pinned and reproducible** (bundle manifest includes versions + hashes).
2. **Runtime is capability-driven**:
   - If libplacebo tonemap is usable → use it.
   - If libplacebo exists but cannot initialize device (Vulkan/context) → fall back silently.
3. **No “Docker Desktop GPU” assumptions**:
   - Docker Desktop on macOS/Windows is not a reliable GPU/Vulkan baseline.
4. **Separation of concerns**:
   - “Shipping artifacts” (bundle) is distinct from “Python library correctness” (pip install).

---

## 3. Non-Goals

- Guaranteeing GPU acceleration in *every* environment (drivers differ).
- Supporting arbitrary VapourSynth/plugin versions (BYO VS is best-effort).
- Replacing Docker as a dev/test environment (Docker remains a baseline for real-deps tests, but not the only distribution path).
