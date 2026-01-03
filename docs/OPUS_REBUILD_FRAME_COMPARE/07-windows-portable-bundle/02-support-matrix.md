# Windows Portable Bundle — Support Matrix

> **Module:** Distribution
> **Version:** 1.0

---

## 1. Runtime Modes

| Mode | Tonemap GPU expectation | Notes |
|------|--------------------------|------|
| Windows portable bundle (native) | Possible (depends on Vulkan + drivers) | Supported/tested baseline for distribution. |
| Windows “BYO VS” (native) | Possible (depends on install) | Best-effort only. |
| Linux native | Likely | Depends on GPU drivers; not a portable bundle target in v1. |
| Linux Docker (GPU passthrough) | Likely if configured | Requires explicit host setup (NVIDIA/DRI). |
| Docker Desktop macOS/Windows | Not reliable | Must accept fallback tonemap. |

---

## 2. Baseline Commitments

- The portable bundle must work without Docker.
- The Docker integration gate must validate “real deps work” and accept fallback tonemap when Vulkan device is unavailable.
- GPU/libplacebo success can be enforced only in environments where a Vulkan device is expected (Linux GPU runners), via an explicit opt-in switch (e.g. env var).
