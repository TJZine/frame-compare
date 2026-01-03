# Master Checklist Phase Proposal: Windows Portable Bundle

> **Module:** Distribution
> **Version:** 1.0
> **Owner Note:** `10-agent-master-checklist.md` is owned by the Verification Agent; this file is the proposal to be merged.

---

## Proposed: Phase 8 — Distribution (Windows Portable Bundle)

### 8.1 Bundle Spec + Manifest

- [ ] Approve bundle layout + env var rules (SSOT: `07-windows-portable-bundle/01-bundle-spec.md`)
- [ ] Define `manifest.json` schema (versions + sha256 + license notes)
- [ ] Document BYO VS policy (supported vs best-effort)

### 8.2 Windows Portable Build

- [ ] Add build scripts (PowerShell) to assemble portable bundle
- [ ] Bundle includes: Python runtime, frame-compare deps, VS runtime, plugins, ffmpeg
- [ ] Bundle launcher sets PATH + plugin path deterministically

### 8.3 Windows Verification

- [ ] Add Windows CI job to build bundle and run smoke checks
- [ ] Smoke checks:
  - [ ] `frame-compare doctor --json` exits 0
  - [ ] Basic VS clip operations work
  - [ ] Tonemap does not raise (fallback allowed)
- [ ] Optional GPU-required CI job (Linux GPU runner only) validates libplacebo success

### Phase 8 Quality Gate ✓

- [ ] Portable bundle builds deterministically from pinned artifacts
- [ ] Windows CI smoke checks pass
- [ ] Documentation published: install/run instructions + support matrix
