# Windows Portable Bundle Spec (SSOT)

> **Module:** Distribution
> **Version:** 1.0

---

## 1. Supported Targets

### 1.1 Baseline (Supported / Tested)

- OS: Windows 10/11
- Architecture: x86_64 (amd64)

### 1.2 Best-Effort Targets (Not CI-Tested)

- Windows ARM64 (only if all baseline artifacts exist and pass manual validation)
- “Bring your own VapourSynth” installs

---

## 2. Bundle Layout (Normative)

The portable bundle must have a stable layout so the launcher can set paths deterministically:

```text
frame-compare-portable/
├── frame-compare.cmd
├── frame-compare.ps1
├── manifest.json
├── app/
│   └── ... (python package + dependencies)
├── python/
│   └── ... (runtime python distribution, strategy defined per release)
├── vs/
│   ├── core/                (VapourSynth runtime components)
│   └── plugins/             (VapourSynth plugins: lsmas, placebo, ffms2, etc.)
└── ffmpeg/
    └── ffmpeg.exe
```

Notes:

- `manifest.json` is required and must include versions + sha256 hashes for shipped artifacts.
- The launcher scripts are the only supported entrypoints for the portable bundle.

---

## 3. Launch Environment (Normative)

The launcher must set environment variables before importing `vapoursynth`:

- `VAPOURSYNTH_PLUGIN_PATH=<BUNDLE>/vs/plugins`
- `PATH` must include:
  - `<BUNDLE>/python` (or the chosen Python runtime bin dir)
  - `<BUNDLE>/vs/core`
  - `<BUNDLE>/vs/plugins`
  - `<BUNDLE>/ffmpeg`

Optional (if implemented later):

- `FRAME_COMPARE_VS_ROOT=<BUNDLE>/vs` (explicit “use bundle VS” override)

---

## 4. Capability Rules (Normative)

### 4.1 Tonemapping

- If libplacebo plugin is not detected: use fallback tonemap.
- If libplacebo plugin is detected but fails at runtime (device/context): use fallback tonemap.
- If libplacebo works: use libplacebo tonemap.

These rules are specified in:

- `docs/OPUS_REBUILD_FRAME_COMPARE/05-implementation/module-specs/vs-module.md`
  - `### 3.3 Tonemapping`
  - `### 5.2 libplacebo Integration`
  - `### 5.3 Fallback Handling`

---

## 5. “Bring Your Own VapourSynth” (Best-Effort)

If a user runs Frame Compare outside the portable bundle:

- The project must attempt to use the system VapourSynth installation.
- Plugin detection and fallback behavior must still work.
- Failures due to unsupported VS/plugin combinations are best-effort and documented as such.
