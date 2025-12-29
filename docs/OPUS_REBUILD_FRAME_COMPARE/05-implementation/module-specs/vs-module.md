# VapourSynth Module Implementation Spec

> **Module:** `frame_compare.vs`
> **Version:** 1.0
> **Priority:** P0

---

## 1. Module Overview

The VS module provides the VapourSynth abstraction layer, handling video source loading, color space transformations, and HDR tonemapping.

### 1.1 Responsibilities

- Initialize VapourSynth environment
- Load video sources with proper color handling
- Extract frame properties and HDR metadata
- Apply HDR to SDR tonemapping via libplacebo
- Manage VapourSynth plugin configuration

### 1.2 Module Structure

```text
src/frame_compare/vs/
├── __init__.py          # Public exports
├── env.py               # VS environment setup
├── source.py            # Video source loading
├── props.py             # Frame property extraction
├── color.py             # Color space operations
└── tonemap.py           # HDR tonemapping
```

### 1.3 VSLoader Protocol

> [!IMPORTANT]
> `VSLoader` is the canonical interface for loading VapourSynth clips.
> This protocol is defined here and imported by cli, analysis, and other modules.

```python
from typing import Protocol

class VSLoader(Protocol):
    """Protocol for loading VapourSynth clips."""

    def load(self, path: Path) -> SourceInfo:
        """Load a video source, returning clip and metadata."""
        ...  # pseudocode: protocol method, see DefaultVSLoader below

    def ensure_core(self) -> vs.Core:
        """Get or create a VapourSynth core."""
        ...  # pseudocode: protocol method, see DefaultVSLoader below

class DefaultVSLoader:
    """Default VapourSynth loader implementation using LWLibavSource."""

    _core: vs.Core | None = None  # Singleton pattern

    def load(self, path: Path) -> SourceInfo:
        core = self.ensure_core()
        return load_source(path, core)

    def ensure_core(self) -> vs.Core:
        """Get or create a VapourSynth core (singleton).

        Note: VapourSynth cores are expensive to create. This method
        caches the core at class level, reusing it across all load()
        calls within a process. This is the expected pattern.
        """
        if self._core is None:
            self._core = ensure_vs_environment()
        return self._core
```

> [!IMPORTANT]
> **For AI Agents:** The VapourSynth Core MUST be a singleton per process.
> Creating a new Core on each load() call is expensive and error-prone.
> Use the `_core` class variable pattern shown above.

### 1.4 Plugin Detection

> [!IMPORTANT]
> VapourSynth plugin namespaces vary. Use these verified detection patterns:

```python
def detect_plugins(core: vs.Core) -> dict[str, bool]:
    """Detect available VapourSynth plugins.

    Returns dict of plugin_name -> is_available.
    """
    return {
        # L-SMASH Works (lsmas) - source loading
        "lsmas": (
            hasattr(core, 'lsmas') and hasattr(core.lsmas, 'LWLibavSource')
        ) or (
            hasattr(core, 'lw') and hasattr(core.lw, 'LWLibavSource')
        ),

        # libplacebo - tonemapping
        "libplacebo": hasattr(core, 'placebo') and hasattr(core.placebo, 'Tonemap'),

        # BestSource (fallback loader)
        "bestsource": hasattr(core, 'bs') and hasattr(core.bs, 'VideoSource'),

        # ffms2 (alternative loader)
        "ffms2": hasattr(core, 'ffms2') and hasattr(core.ffms2, 'Source'),
    }

def require_plugin(core: vs.Core, plugin: str) -> None:
    """Ensure plugin is available, raising PluginNotFoundError if not."""
    available = detect_plugins(core)
    if not available.get(plugin, False):
        from frame_compare.errors import PluginNotFoundError
        raise PluginNotFoundError(plugin)
```

| Plugin | Namespace | Detection | Required For |
|:-------|:----------|:----------|:-------------|
| lsmas | `core.lsmas.LWLibavSource` (alias `core.lw.LWLibavSource`) | `hasattr(core, 'lsmas')` (fallback `lw`) | Video source loading |
| libplacebo | `core.placebo.Tonemap` | `hasattr(core, 'placebo')` | HDR tonemapping |
| bestsource | `core.bs.VideoSource` | `hasattr(core, 'bs')` | Fallback source |
| ffms2 | `core.ffms2.Source` | `hasattr(core, 'ffms2')` | Alternative source |

> [!IMPORTANT]
> **Verification Baseline:** All plugin detection patterns above are verified against the **R73 baseline image**.
> Outside the baseline, namespaces may vary (e.g., different plugin builds, older VS versions).
>
> **Baseline Reference:**
>
> - VapourSynth: R73
> - L-SMASH Works: `HomeOfAviSynthPlusEvolution/L-SMASH-Works@20230716` → namespace `lsmas` (alias `lw` in some builds)
> - libplacebo: `haasn/libplacebo@v7.349.0` (headless build) → namespace `placebo` (provided via vs-placebo)
> - vs-placebo: `Lypheo/vs-placebo@14083805df08cd478539c15464a7183da2c0032e` → namespace `placebo`
> - ffms2: `FFMS/ffms2@45673149e9a2f5586855ad472e3059084eaa36b1` → namespace `ffms2`
> - bestsource: optional (not part of the baseline image) → namespace `bs`
>
> Run `frame-compare doctor --json` to see discovered namespaces on your system.
> See [deployment.md](../../../06-operations/deployment.md#baseline-verification-environment) for baseline setup.

---

### 2.1 SourceInfo

```python
@dataclass
class SourceInfo:
    """Video source metadata"""
    clip: vs.VideoNode
    width: int
    height: int
    num_frames: int
    fps: Fraction
    format: vs.VideoFormat
    frame_props: Mapping[str, object]
    is_hdr: bool
    hdr_metadata: HDRMetadata | None

@dataclass
class HDRMetadata:
    mastering_display: str | None
    max_cll: int | None
    max_fall: int | None
    color_primaries: int
    transfer: int
    matrix: int
```

### 2.2 TonemapSettings

```python
@dataclass
class TonemapSettings:
    """Resolved tonemap settings for VS operations.

    Note: Field names align with ColorConfig in config-module.md.
    """
    enabled: bool = True
    preset: str = "reference"
    tone_curve: str = "bt2390"  # Aligned with config.tone_curve
    target_nits: int = 203
    source_peak: int | None = None
    contrast_recovery: float = 0.0  # Aligned with config.contrast_recovery
    gamma_lift: bool = False
```

### 2.3 ColorProps

```python
@dataclass
class ColorProps:
    """Color space properties extracted from frame.

    All fields use VapourSynth integer constants.
    Defaults to 2 (unspecified) for missing properties.
    """
    primaries: int    # _Primaries (e.g., 1=BT.709, 9=BT.2020)
    transfer: int     # _Transfer (e.g., 1=BT.709, 16=PQ, 18=HLG)
    matrix: int       # _Matrix (e.g., 1=BT.709, 9=BT.2020nc)
    color_range: int  # _ColorRange (0=full, 1=limited)
```

**ColorProps Field Mapping (SSOT):**

| ColorProps field | frame_props key | Type | Default |
|------------------|-----------------|------|---------|
| `primaries`      | `_Primaries`    | int  | 2       |
| `transfer`       | `_Transfer`     | int  | 2       |
| `matrix`         | `_Matrix`       | int  | 2       |
| `color_range`    | `_ColorRange`   | int  | 0       |

**Type Coercion:** `int(value)` if value is not None, else default.

---

## 3. Public API

### 3.1 Environment

```python
def ensure_vs_environment() -> vs.Core:
    """
    Initialize VapourSynth core with plugins.

    Returns:
        Configured vs.Core instance

    Raises:
        VapourSynthNotFoundError: If vapoursynth import fails (FC-2001)
        VapourSynthError: If VS core initialization fails (FC-2002)
    """

def is_vapoursynth_available() -> bool:
    """Check if VapourSynth is usable (import + core creation)."""
```

### 3.2 Source Loading

```python
def load_source(
    path: Path,
    core: vs.Core | None = None,
) -> SourceInfo:
    """
    Load video source with automatic format detection.

    Uses LWLibavSource for most formats.
    Extracts HDR metadata from first frame.

    Args:
        path: Video file path
        core: Optional VS core (creates if not provided)

    Returns:
        SourceInfo with clip and metadata

    Raises:
        PluginNotFoundError: If lsmas plugin is not available (FC-2003, propagates)
        SourceLoadError: If file cannot be opened or is corrupt (FC-4015)

    Note:
        PluginNotFoundError is NOT wrapped; it propagates directly to allow
        callers to distinguish missing dependency from corrupt file.
    """

def apply_trim(
    source: SourceInfo,
    start: int,
    end: int | None = None,
) -> vs.VideoNode:
    """Apply frame trim to clip.

    Args:
        source: Source info containing clip
        start: First frame to include (0-indexed, inclusive)
        end: Last frame to include (0-indexed, inclusive).
             If None, trims to end of clip (num_frames - 1).

    Returns:
        Trimmed clip with frames [start, end] inclusive.

    Implementation:
        Uses `source.clip[start:end+1]` (VS slice is exclusive on right).
        If end is None: `source.clip[start:]`
    """
```

### 3.3 Tonemapping

```python
def apply_tonemap(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    hdr_metadata: HDRMetadata | None = None,
) -> vs.VideoNode:
    """
    Apply HDR to SDR tonemapping.

    Uses libplacebo for tone curve application.

    Args:
        clip: HDR video clip
        settings: Tonemap configuration
        hdr_metadata: Source HDR metadata (detected if not provided)

    Returns:
        SDR video clip

    Raises:
        TonemapError: If tonemapping fails
    """

def get_preset_settings(preset: str) -> TonemapSettings:
    """Get settings for named preset."""
```

### 3.4 Frame Properties

```python
def get_color_props(clip: vs.VideoNode) -> ColorProps:
    """
    Extract color space properties from frame 0.

    Args:
        clip: VapourSynth clip to extract properties from

    Returns:
        ColorProps with primaries, transfer, matrix, color_range

    Note:
        Always reads frame 0 for consistency with load_source().
        Missing properties default per ColorProps Field Mapping table.
    """

def is_hdr(clip: vs.VideoNode) -> bool:
    """
    Determine if clip is HDR based on frame 0 properties.

    HDR Detection Rule:
        is_hdr = _Transfer in (16, 18) AND _Primaries == 9

    Where:
        - _Transfer == 16: PQ (Perceptual Quantizer)
        - _Transfer == 18: HLG (Hybrid Log-Gamma)
        - _Primaries == 9: BT.2020

    Args:
        clip: VapourSynth clip to check

    Returns:
        True if clip is HDR (PQ or HLG with BT.2020 primaries)

    Note:
        Uses frame 0 properties. Consistent with _detect_hdr() in source.py.
    """
```

---

## 4. Tonemap Presets

| Preset | Curve | Target Nits | Description |
|--------|-------|-------------|-------------|
| `reference` | bt2390 | 203 | BT.2390 reference |
| `filmic` | spline | 203 | Film-like rolloff |
| `contrast` | reinhard | 203 | Higher contrast |
| `bt2390_spec` | bt2390 | 100 | Strict spec compliance |
| `spline` | spline | 203 | Smooth curve |
| `bright_lift` | bt2390 | 250 | Lifted shadows |
| `highlight_guard` | spline | 180 | Preserve highlights |

---

## 5. Implementation Details

### 5.1 HDR Detection

```python
def _detect_hdr(frame_props: Mapping[str, object]) -> tuple[bool, HDRMetadata | None]:
    """
    Detect HDR from frame properties and extract metadata.

    HDR Detection Rules:
        is_hdr = True if _Transfer in (16, 18) AND _Primaries == 9
        - _Transfer == 16: PQ (Perceptual Quantizer)
        - _Transfer == 18: HLG (Hybrid Log-Gamma)
        - _Primaries == 9: BT.2020

    HDRMetadata Field Mapping:
        | HDRMetadata field    | frame_props key             | Type     | Default   |
        |----------------------|-----------------------------|----------|-----------|
        | mastering_display    | MasteringDisplayPrimaries   | str      | None      |
        | max_cll              | ContentLightLevelMax        | int      | None      |
        | max_fall             | ContentLightLevelAverage    | int      | None      |
        | color_primaries      | _Primaries                  | int      | 2 (unspec)|
        | transfer             | _Transfer                   | int      | 2 (unspec)|
        | matrix               | _Matrix                     | int      | 2 (unspec)|

    Type Coercion:
        - int fields: int(value) if value is not None, else default
        - str fields: str(value) if value is not None, else None

    Returns:
        (is_hdr, hdr_metadata) where:
        - is_hdr is True only if HDR detection criteria are met
        - hdr_metadata is HDRMetadata if is_hdr is True, else None
    """
```

### 5.2 libplacebo Integration

```python
def _apply_libplacebo(
    clip: vs.VideoNode,
    settings: TonemapSettings,
    core: vs.Core,
) -> vs.VideoNode:
    """
    Apply libplacebo tonemapping.

    Pipeline:
    1. Convert to floating point RGB
    2. Apply vs.placebo.Tonemap()
    3. Apply optional post-processing
    4. Convert to output format
    """
```

### 5.3 Fallback Handling

```python
def _fallback_tonemap(
    clip: vs.VideoNode,
    settings: TonemapSettings,
) -> vs.VideoNode:
    """
    Simple fallback when libplacebo unavailable.

    Uses basic Reinhard curve via core.std operations.
    Quality is degraded but functional.
    """
```

---

## 6. Error Handling

> [!NOTE]
> All error classes are defined centrally in `frame_compare.errors` (see [errors-module.md](errors-module.md)).

**Error classes used by this module:**

| Error Class | Code | Usage |
|-------------|------|-------|
| `VapourSynthNotFoundError` | FC-2001 | VapourSynth module not installed |
| `VapourSynthError` | FC-2002 | VS core initialization failed |
| `PluginNotFoundError` | FC-2003 | Required plugin not available |
| `SourceLoadError` | FC-4015 | Failed to load video source |
| `TonemapError` | FC-4003 | Tonemapping operation failed |

```python
from frame_compare.errors import (
    VapourSynthNotFoundError,
    VapourSynthError,
    PluginNotFoundError,
    SourceLoadError,
    TonemapError,
)
```

---

## 7. Testing Strategy

### 7.1 Unit Tests (Mocked)

| Test Case | Mock | Expected |
|-----------|------|----------|
| HDR detection | Frame props dict | Correct is_hdr |
| Preset loading | None | Valid settings |
| Availability check | vs module | True/False |

### 7.2 VS-Required Tests

| Test Case | Input | Expected |
|-----------|-------|----------|
| Source loading | Sample HDR MKV | SourceInfo populated |
| Tonemapping | HDR clip | SDR output |
| Format detection | Various codecs | Correct format |

---

## 8. AI Agent Implementation Prompt

```markdown
# Task: Implement VapourSynth Module

## Context
Implement the VapourSynth abstraction layer for Frame Compare 2.0.
This module handles video source loading, HDR detection, and tonemapping.

## Files to Create
1. `src/frame_compare/vs/__init__.py` - Public exports
2. `src/frame_compare/vs/env.py` - Environment setup
3. `src/frame_compare/vs/source.py` - Source loading
4. `src/frame_compare/vs/props.py` - Property extraction
5. `src/frame_compare/vs/color.py` - Color operations
6. `src/frame_compare/vs/tonemap.py` - Tonemapping

## Public Exports (vs/__init__.py)
The following MUST be exported from `__init__.py` for use by other modules:
- `VSLoader` (Protocol)
- `DefaultVSLoader` (implementation)
- `SourceInfo`, `HDRMetadata`, `TonemapSettings` (types)
- `ensure_vs_environment`, `load_source`, `tonemap` (functions)

## Key Requirements
- Use LWLibavSource for file loading
- Detect HDR via _Transfer, _Primaries frame props
- Implement libplacebo tonemapping with presets
- Provide fallback for missing libplacebo
- Handle plugin path configuration

## Presets to Implement
- reference, filmic, contrast, bt2390_spec
- spline, bright_lift, highlight_guard

## Testing
- Use @pytest.mark.vs_required marker
- Mock vs module for unit tests
- Test each preset on sample clip

## Dependencies
- vapoursynth (vs)
- vs-tools if available
- numpy for array conversion

## Acceptance Criteria
- HDR detection accurate
- All presets produce distinct output
- Fallback works without libplacebo
- VapourSynth errors wrapped properly
```
