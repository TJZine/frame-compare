# Feature Parity Matrix

> **Module:** Reference  
> **Version:** 1.0

---

## 1. Overview

This document maps all features from Frame Compare v0.0.14 to their v2.0 equivalents to ensure complete feature parity.

---

## 2. Core Features

| Feature | v0.0.14 | v2.0 | Status | Notes |
|---------|---------|------|--------|-------|
| **Video Loading** | lsmas | lsmas | ✅ Same | Via VapourSynth |
| **HDR Detection** | Frame props | Frame props | ✅ Same | _Transfer,_Primaries |
| **PQ Tonemapping** | libplacebo | libplacebo | ✅ Same | Multiple presets |
| **HLG Tonemapping** | libplacebo | libplacebo | ✅ Same | - |
| **Frame Selection** | Random + quantile | Enhanced | ✅ Enhanced | + motion detection |
| **Screenshot Render** | PNG via VS | PNG via VS/FFmpeg | ✅ Enhanced | + FFmpeg fallback |
| **Audio Alignment** | Cross-correlation | Cross-correlation | ✅ Same | - |
| **slow.pics Upload** | HTTP POST | HTTPX async POST | ✅ Enhanced | + retry logic |
| **TMDB Metadata** | GuessIt + TMDB | GuessIt + Anitopy + TMDB | ✅ Enhanced | + anime support |
| **HTML Report** | Basic viewer | Enhanced viewer | ✅ Enhanced | + slider, filmstrip |
| **Caching** | msgpack | msgspec | ✅ Same | Different format |
| **CLI Interface** | Click | Typer | ✅ Enhanced | Better help, types |
| **Config** | TOML + dataclasses | TOML + Pydantic | ✅ Enhanced | + validation |

---

## 3. CLI Commands

| Command | v0.0.14 | v2.0 | Notes |
|---------|---------|------|-------|
| `run` | ✅ | ✅ | Main comparison command |
| `wizard` | ✅ | ✅ | Interactive setup |
| `doctor` | ✅ | ✅ | Dependency check |
| `preset list` | ❌ | ✅ NEW | List available presets |
| `preset apply` | ❌ | ✅ NEW | Apply preset to config |
| `preset save` | ❌ | ✅ NEW | Save current as preset |

---

## 4. CLI Flags

| Flag | v0.0.14 | v2.0 | Notes |
|------|---------|------|-------|
| `--root` | ✅ | ✅ | Workspace root |
| `--config` | ✅ | ✅ | Config file path |
| `--input` | ✅ | ✅ | Input directory |
| `--tm-preset` | ✅ | ✅ | Tonemap preset |
| `--tm-target` | ✅ | ✅ | Target nits |
| `--tm-curve` | ❌ | ✅ NEW | Tone curve selection |
| `--frame-count` | ✅ | ✅ | Frame count |
| `--seed` | ✅ | ✅ | Random seed |
| `--no-upload` | ✅ | ✅ | Skip upload |
| `--no-cache` | ✅ | ✅ | Ignore cache |
| `--from-cache-only` | ✅ | ✅ | Use only cache |
| `--overlay` | ❌ | ✅ NEW | Overlay mode |
| `--quiet` | ✅ | ✅ | Suppress output |
| `--verbose` | ✅ | ✅ | Debug output |
| `--json` | ❌ | ✅ NEW | JSON output for doctor |

---

## 5. Configuration Options

| Section | Option | v0.0.14 | v2.0 | Notes |
|---------|--------|---------|------|-------|
| paths | input_dir | ✅ | ✅ | - |
| paths | screenshots_dir | ✅ | ✅ | - |
| paths | generated_dir | ✅ | ✅ | - |
| analysis | frame_count | ✅ | ✅ | - |
| analysis | random_seed | ✅ | ✅ | - |
| analysis | selection_mode | ❌ | ✅ NEW | quantile/motion/mixed |
| analysis | dark_quantile | ✅ | ✅ | - |
| analysis | bright_quantile | ✅ | ✅ | - |
| color | preset | ✅ | ✅ | More presets |
| color | target_nits | ✅ | ✅ | - |
| color | tone_curve | ❌ | ✅ NEW | Curve selection |
| color | gamma_lift | ✅ | ✅ | - |
| color | contrast_recovery | ❌ | ✅ NEW | - |
| slowpics | auto_upload | ✅ | ✅ | - |
| slowpics | visibility | ✅ | ✅ | - |
| slowpics | max_retries | ❌ | ✅ NEW | Retry logic |
| screenshots | overlay_mode | ❌ | ✅ NEW | - |
| report | enable | ❌ | ✅ NEW | HTML report toggle |
| logging | level | ❌ | ✅ NEW | Log level config |
| logging | format | ❌ | ✅ NEW | Console/JSON |

---

## 6. Tonemap Presets

| Preset | v0.0.14 | v2.0 | Notes |
|--------|---------|------|-------|
| reference | ✅ | ✅ | Default preset |
| filmic | ✅ | ✅ | Film-like rolloff |
| contrast | ❌ | ✅ NEW | Enhanced contrast |
| bt2390_spec | ✅ | ✅ | ITU spec |
| spline | ✅ | ✅ | Smooth curve |
| bright_lift | ✅ | ✅ | Shadow lift |
| highlight_guard | ✅ | ✅ | Protect highlights |

---

## 7. Output Formats

| Format | v0.0.14 | v2.0 | Notes |
|--------|---------|------|-------|
| PNG screenshots | ✅ | ✅ | Primary output |
| slow.pics URL | ✅ | ✅ | Cloud comparison |
| HTML report | Basic | Enhanced | ✅ NEW: slider, filmstrip |
| JSON summary | ❌ | ✅ NEW | Machine-readable output |
| Cache files | msgpack | msgspec | Different format |

---

## 8. VapourSynth Plugins

| Plugin | v0.0.14 | v2.0 | Notes |
|--------|---------|------|-------|
| lsmas | ✅ Required | ✅ Required | Video loading |
| libplacebo | ✅ Required | ✅ Required | Tonemapping |
| vstools | ✅ Optional | ✅ Optional | Helpers |
| vs-placebo | ✅ Optional | ❌ Removed | Now built-in |

---

## 9. Breaking Changes

| Change | Impact | Migration |
|--------|--------|-----------|
| Config format | Medium | Auto-migrate v1 configs |
| Cache format | Low | Cache regenerated automatically |
| CLI framework | None | Core commands unchanged (additive: `preset` subcommands) |
| Python version | Medium | Upgrade to 3.13+ |
| Plugin changes | Low | vs-placebo no longer needed |

---

## 10. Verification Checklist

To verify feature parity, test each scenario:

- [ ] Load HDR video (PQ, HLG, SDR)
- [ ] Tonemap with each preset
- [ ] Select frames (random, quantile, motion)
- [ ] Align audio between clips
- [ ] Render screenshots with overlays
- [ ] Upload to slow.pics
- [ ] Parse metadata from filename
- [ ] Generate HTML report
- [ ] Use cache for repeat runs
- [ ] Run in Docker container

---

## 11. Behavioral Parity Scenarios

> [!IMPORTANT]
> These edge-case scenarios ensure behavioral equivalence between v0.0.14 and v2.0.

### Path Resolution

| Scenario | Expected Behavior | Error Code |
|:---------|:------------------|:-----------|
| Non-existent input_dir | `FC-3006: Directory not found` | FC-3006 |
| Path escapes workspace root | `FC-3009: Path escapes root` | FC-3009 |
| Relative vs absolute paths | Both resolve to same location | - |

### Cache Invalidation

| Scenario | Expected Behavior |
|:---------|:------------------|
| Config change (frame_count) | Cache miss, recalculate |
| Video file modified (mtime) | Cache miss, reload source |
| Cache version mismatch | Auto-regenerate cache |
| Cache file corrupt | `FC-4006`, regenerate |

### Tonemapping Edge Cases

| Scenario | Expected Behavior |
|:---------|:------------------|
| SDR input with tonemap enabled | Skip tonemapping, warn |
| Unknown HDR format | Treat as PQ, warn |
| Missing color primaries | Use BT.709 default |

### Overlay Behavior

| Scenario | Expected Behavior |
|:---------|:------------------|
| No custom font path | Use bundled fallback font |
| overlay_mode=none | No text overlay rendered |
| Frame number > 999999 | Truncate display, log warning |
