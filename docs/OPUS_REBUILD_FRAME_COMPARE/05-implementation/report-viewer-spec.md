# Report Viewer Specification

> **Module:** `frame_compare.services.report`
> **Version:** 1.0
> **Last Updated:** 2026-01-02

---

## 1. Overview

The Report Viewer is a self-contained, offline-viewable HTML application for comparing video frame screenshots across multiple encodes. It consists of a single HTML file with embedded CSS and JavaScript.

### 1.1 Design Goals

1. **Offline-first** — Works without network access (no CDN dependencies)
2. **Self-contained** — Single HTML file for easy sharing
3. **Performant** — Lazy-loaded thumbnails, efficient DOM updates
4. **Accessible** — Full keyboard navigation, ARIA compliance
5. **Modern aesthetics** — Dark theme with accent highlights

### 1.2 MVP vs Future Scope

| Feature | MVP (Phase 5.4) | Future |
|:--------|:---------------:|:------:|
| Four viewer modes | ✓ | |
| Dark theme | ✓ | |
| Filmstrip navigation | ✓ | |
| Keyboard shortcuts | ✓ | |
| Basic zoom (25%-200%) | ✓ | |
| Accessibility/ARIA | ✓ | |
| Full zoom/pan with presets | | ✓ |
| Category filtering | | ✓ |
| localStorage persistence | | ✓ |
| Fullscreen mode | | ✓ |
| External data.json loading | | ✓ |

---

## 2. Data Structure

### 2.1 ReportData Interface

```python
@dataclass(frozen=True)
class ClipInfo:
    """Information about a video clip for report generation."""
    name: str              # Display name (filename or custom label)
    path: Path             # Source video path (for reference, not embedded)
    frame_count: int       # Total frames in source
    resolution: tuple[int, int]  # (width, height)
    fps: float             # Frames per second
    hdr: bool              # True if HDR source
    label: str | None = None     # Short label for UI (e.g., "REF", "ENC")

@dataclass(frozen=True)
class ReportData:
    """Data for report generation."""
    clips: list[ClipInfo]  # At least 2 clips for comparison
    frames: list[int]      # Selected frame numbers
    screenshots: dict[str, list[Path]]  # clip_name → [frame_paths] in order
    metadata: TmdbMetadata | None = None  # Optional TMDB info
    slowpics_url: str | None = None       # Link if uploaded
```

### 2.2 Internal JSON Schema

The HTML embeds JSON in a `<script type="application/json" id="report-data">` element:

```typescript
interface EmbeddedData {
  version: "1.0";
  generated_at: string;           // ISO 8601
  title: string;                  // From metadata or first clip name
  slowpics_url: string | null;
  default_mode: "slider" | "overlay" | "diff" | "blink";
  stats: {
    frame_count: number;
    clip_count: number;
  };
  clips: Array<{
    name: string;
    label: string;                // Short label for selectors
    resolution: [number, number];
    fps: number;
    hdr: boolean;
  }>;
  frames: Array<{
    number: number;               // Frame number
    images: Array<{
      clip: string;               // Clip name (matches clips[].name)
      src: string;                // Base64 data URI or relative path
    }>;
  }>;
}
```

---

## 3. Visual Design

### 3.1 Color Palette

The viewer uses a refined dark theme optimized for image comparison:

| Token | Value | Usage |
|:------|:------|:------|
| `--bg-primary` | `#0f1115` | Page background |
| `--bg-surface` | `#1a1d24` | Cards, controls, filmstrip |
| `--bg-elevated` | `#242830` | Hover states, active items |
| `--bg-overlay` | `rgba(0, 0, 0, 0.7)` | Modal overlays |
| `--accent` | `#5ba4e6` | Active states, links |
| `--accent-hover` | `#7ab8f0` | Hover accent |
| `--accent-muted` | `rgba(91, 164, 230, 0.15)` | Subtle highlights |
| `--text-primary` | `#f0f2f5` | Main text |
| `--text-secondary` | `rgba(240, 242, 245, 0.7)` | Secondary text |
| `--text-muted` | `rgba(240, 242, 245, 0.5)` | Disabled, hints |
| `--border` | `rgba(255, 255, 255, 0.08)` | Subtle borders |
| `--border-active` | `rgba(91, 164, 230, 0.5)` | Active borders |
| `--danger` | `#e55353` | Errors, destructive |
| `--success` | `#4caf50` | Success states |
| `--divider` | `#5ba4e6` | Slider divider line |

**Rationale:** Shifted from pure blue accent (`#9fd2ff`) to a warmer blue (`#5ba4e6`) for better contrast and reduced eye strain during extended comparison sessions.

### 3.2 Typography

```css
:root {
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif;
  --font-mono: "SF Mono", Monaco, "Cascadia Code", Consolas, monospace;
  --text-xs: 0.75rem;   /* 12px - badges */
  --text-sm: 0.875rem;  /* 14px - labels */
  --text-base: 1rem;    /* 16px - body */
  --text-lg: 1.125rem;  /* 18px - headings */
  --text-xl: 1.5rem;    /* 24px - title */
}
```

### 3.3 Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER                                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Title • Generated date • slow.pics link (if available) │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ CONTROLS                                                     │
│ ┌──────────┬──────────┬──────────┬─────────────┬──────────┐ │
│ │ Frame ◄► │ Left ▼   │ Right ▼  │ Mode ▼      │ Zoom ─○─ │ │
│ └──────────┴──────────┴──────────┴─────────────┴──────────┘ │
├─────────────────────────────────────────────────────────────┤
│ VIEWER STAGE                                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │                                                         │ │
│ │                    Image Comparison                     │ │
│ │                        Area                             │ │
│ │                                                         │ │
│ │                                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Frame 1234 • Left: REF • Right: ENC                     │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ FILMSTRIP                                                    │
│ ┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐   │
│ │ 01 │ 02 │ 03 │ 04 │ 05 │ 06 │ 07 │ 08 │ 09 │ 10 │ ►  │   │
│ └────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘   │
├─────────────────────────────────────────────────────────────┤
│ FOOTER                                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Frame Compare 2.0 • 10 frames • 2 encodes              │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 3.4 Responsive Behavior

| Breakpoint | Behavior |
|:-----------|:---------|
| ≥1024px | Full layout, filmstrip horizontal scroll |
| 768-1023px | Controls stack vertically, smaller filmstrip |
| <768px | Single column, filmstrip scrolls, zoom simplified |

---

## 4. Viewer Modes

### 4.1 Slider Mode (Default)

**Purpose:** Precise pixel-level comparison at specific screen regions.

**Implementation:**

```css
.viewer-left {
  position: absolute;
  inset: 0;
  clip-path: inset(0 var(--reveal-percent) 0 0);
}

.viewer-right {
  position: absolute;
  inset: 0;
}

.viewer-divider {
  position: absolute;
  top: 0;
  bottom: 0;
  left: calc(100% - var(--reveal-percent));
  width: 2px;
  background: var(--divider);
  cursor: ew-resize;
}
```

**Interaction:**

- Drag divider or click anywhere to set reveal position
- Mouse position updates `--reveal-percent` (CSS custom property)
- Default: 50% reveal

**State:**

- `revealPercent: number` (0-100)

### 4.2 Overlay Mode

**Purpose:** View each encode in isolation without split-view distraction.

**Implementation:**

- Show only one image at a time
- Display encode label overlay in corner
- Cycle through clips on click or keyboard

**Interaction:**

- Click viewer or press `↑`/`↓` to cycle
- Press `1-9` to jump to specific encode

**State:**

- `activeClipIndex: number`

### 4.3 Difference Mode

**Purpose:** Identify subtle compression artifacts, color shifts, or encoding errors.

**Implementation:**

```css
.viewer-overlay {
  mix-blend-mode: difference;
}
```

**Result:**

- Identical pixels → Black
- Different pixels → Colored (inverted delta)

**Interaction:**

- Click to cycle which encode is compared with base

**State:**

- `baseClipIndex: number`
- `compareClipIndex: number`

### 4.4 Blink Mode

**Purpose:** Motion comparison and spotting temporal differences.

**Implementation:**

```javascript
let blinkInterval = setInterval(() => {
  activeIndex = (activeIndex + 1) % clipCount;
  updateDisplay();
}, 700);
```

**Interaction:**

- Auto-toggles at 700ms interval
- Mousedown pauses (shows current image)
- Mouseup resumes blinking

**State:**

- `blinkActive: boolean`
- `blinkPaused: boolean`
- `activeClipIndex: number`

---

## 5. Controls

### 5.1 Frame Navigation

| Control | Type | Behavior |
|:--------|:-----|:---------|
| Frame selector | `<select>` | Dropdown with frame numbers |
| Previous | `<button>` | Go to previous frame |
| Next | `<button>` | Go to next frame |

**Display:**

- Frame number with optional label
- Format: `Frame 1234` or `1234 — Dark Scene` if labeled

### 5.2 Encode Selectors

| Mode | Controls |
|:-----|:---------|
| Slider | Left dropdown, Right dropdown |
| Overlay | Single "Encode" dropdown |
| Difference | Base dropdown, Compare dropdown |
| Blink | Left dropdown, Right dropdown |

### 5.3 Mode Selector

Segmented button group with icons:

| Mode | Icon | Tooltip |
|:-----|:-----|:--------|
| Slider | `⊟` | "Slider: Drag to reveal" |
| Overlay | `◐` | "Overlay: Click to cycle" |
| Difference | `◑` | "Difference: Highlight changes" |
| Blink | `◫` | "Blink: Auto-switch 700ms" |

### 5.4 Zoom Control

| Control | Behavior |
|:--------|:---------|
| Slider | Range input, 25% to 200% |
| Minus button | Decrease 10% |
| Plus button | Increase 10% |
| Reset (R key) | Return to 100% |

**Implementation:**

```css
.viewer-canvas {
  transform: scale(var(--zoom-level));
  transform-origin: center center;
}
```

---

## 6. Keyboard Shortcuts

### 6.1 Navigation

| Key | Action |
|:----|:-------|
| `←` / `ArrowLeft` | Previous frame |
| `→` / `ArrowRight` | Next frame |
| `Home` | First frame |
| `End` | Last frame |

### 6.2 Encode Cycling

| Key | Action |
|:----|:-------|
| `↑` / `ArrowUp` | Next encode (Overlay/Diff/Blink) |
| `↓` / `ArrowDown` | Previous encode |
| `1` - `9` | Jump to encode 1-9 |

### 6.3 Mode Switching

| Key | Action |
|:----|:-------|
| `S` | Slider mode |
| `O` | Overlay mode |
| `D` | Difference mode |
| `B` | Blink mode |

### 6.4 Zoom

| Key | Action |
|:----|:-------|
| `=` / `+` | Zoom in 10% |
| `-` | Zoom out 10% |
| `R` | Reset zoom to 100% |

### 6.5 General

| Key | Action |
|:----|:-------|
| `?` | Show keyboard help modal |
| `Escape` | Close modal / exit focus |

---

## 7. Filmstrip

### 7.1 Thumbnail Specification

| Property | Value |
|:---------|:------|
| Width | 80px |
| Height | Auto (aspect ratio preserved) |
| Image source | First clip's screenshot for each frame |
| Active indicator | 2px accent border |

### 7.2 Structure

```html
<nav class="filmstrip" role="navigation" aria-label="Frame thumbnails">
  <button class="filmstrip-item"
          data-frame="1234"
          aria-current="true"
          aria-label="Frame 1234">
    <img src="..." alt="" loading="lazy">
    <span class="filmstrip-label">1234</span>
  </button>
  <!-- more items -->
</nav>
```

### 7.3 Behavior

- Click thumbnail to navigate to frame
- Horizontal scroll if items exceed viewport
- Active item scrolls into view on frame change

---

## 8. Accessibility

### 8.1 ARIA Requirements

| Element | Attributes |
|:--------|:-----------|
| Viewer container | `role="img"`, `aria-label="Comparison viewer"` |
| Mode buttons | `role="radio"`, `aria-checked`, `aria-label` |
| Frame selector | `aria-label="Select frame"` |
| Zoom slider | `aria-label="Zoom level"`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax` |
| Filmstrip items | `aria-current="true"` on active, `aria-label="Frame {n}"` |

### 8.2 Focus Management

- All controls focusable via Tab
- Visible focus outline (2px accent)
- Focus trapped in modals when open
- Escape closes modals and returns focus

### 8.3 Image Alt Text

Format: `"{clip_label} - Frame {frame_number}"`

Example: `"REF - Frame 1234"`

---

## 9. Error Handling

### 9.1 Generation Errors

| Condition | Error |
|:----------|:------|
| `len(data.clips) == 0` | `ReportError("no clips provided")` |
| `len(data.clips) < 2` | `ReportError("at least 2 clips required for comparison")` |
| `len(data.frames) == 0` | `ReportError("no screenshots provided")` |
| `len(data.screenshots) == 0` | `ReportError("no screenshots provided")` |
| Any clip name missing from `data.screenshots` keys | `ReportError("no screenshots provided")` |
| Any `data.screenshots[clip]` list is empty | `ReportError("no screenshots provided")` |
| Any `data.screenshots[clip]` length ≠ `len(data.frames)` | `ReportError("no screenshots provided")` |
| Screenshot file not found during encoding | `ReportError("screenshot not found: {path}")` |
| Base64 encoding failure (`OSError`) | `ReportError("failed to encode image: {path}")` |
| HTML write failure (`OSError`) | `ReportError("failed to write report: {reason}")` |

### 9.2 Runtime Errors (JavaScript)

- Image load failure: Display placeholder, log to console
- JSON parse failure: Show error overlay with "Invalid report data"
- Missing data fields: Use sensible defaults, log warning

---

## 10. Performance

### 10.1 Lazy Loading

- Filmstrip thumbnails: `loading="lazy"` attribute
- Main images: Preload current + adjacent frames

### 10.2 Debouncing

- Slider drag: Debounce to 16ms (60fps)
- Zoom slider: Debounce to 50ms
- Resize handler: Debounce to 100ms

### 10.3 File Size

| Component | Target |
|:----------|:-------|
| CSS (minified) | < 8KB |
| JavaScript (minified) | < 20KB |
| Total HTML overhead | < 30KB (excluding images) |

---

## 11. Generation Algorithm

```text
generate_report(data: ReportData, config: ReportConfig, output_path: Path | None) -> Path:

1. VALIDATE INPUT
   a. If len(data.clips) == 0: raise ReportError("no clips provided")
   b. If len(data.clips) < 2: raise ReportError("at least 2 clips required for comparison")
   c. If len(data.frames) == 0: raise ReportError("no screenshots provided")
   d. If len(data.screenshots) == 0: raise ReportError("no screenshots provided")
   e. For each clip in data.clips:
      - If clip.name not in data.screenshots: raise ReportError("no screenshots provided")
      - If len(data.screenshots[clip.name]) == 0: raise ReportError("no screenshots provided")
      - If len(data.screenshots[clip.name]) != len(data.frames): raise ReportError("no screenshots provided")

2. DETERMINE OUTPUT PATH
   a. If output_path provided: use it
   b. Else if config.output_dir: Path(config.output_dir) / "report.html"
   c. Else: data.screenshots[data.clips[0].name][0].parent / "report.html"
      (first clip in data.clips, first frame's screenshot path's parent directory)

3. PREPARE IMAGES
   Iterate in deterministic order: for each clip in data.clips order, for each frame index:
     screenshot_path = data.screenshots[clip.name][frame_index]
     If screenshot_path does not exist: raise ReportError("screenshot not found: {path}")
     If config.embed_images:
       Try: image_src = f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}"
       On OSError: raise ReportError("failed to encode image: {path}")
     Else:
       image_src = os.path.relpath(screenshot_path, output_path.parent)

4. BUILD JSON DATA
   Construct EmbeddedData structure (see Section 2.2)
   - clips array preserves data.clips order
   - frames array preserves data.frames order
   - Each frame's images array preserves data.clips order

5. GENERATE HTML
   - Inline CSS with design tokens (Section 3.1)
   - Viewer stage with mode containers
   - Controls: frame nav, encode selectors, mode buttons, zoom
   - Filmstrip with thumbnails
   - Footer with stats
   - Inline JavaScript with viewer logic
   - Embed JSON data in <script type="application/json">

6. WRITE FILE
   output_path.parent.mkdir(parents=True, exist_ok=True)
   Try: output_path.write_text(html_content, encoding="utf-8")
   On OSError as e: raise ReportError("failed to write report: {e}")

7. RETURN output_path
```

---

## 12. Changes from Legacy Viewer

This section documents improvements over the legacy implementation for Plan Review context.

### 12.1 Retained from Legacy

✓ Four viewer modes (Slider, Overlay, Difference, Blink)
✓ Dark theme aesthetic
✓ Filmstrip thumbnail navigation
✓ Keyboard shortcuts for power users
✓ Accessible design with ARIA

### 12.2 Improved from Legacy

| Area | Legacy | 2.0 Improvement |
|:-----|:-------|:----------------|
| **Color palette** | Pure blue accent (#9fd2ff) | Warmer blue (#5ba4e6) for reduced eye strain |
| **Zoom** | Complex with fit presets, pan, alignment | Simplified: basic 25%-200% range (MVP scope) |
| **Data format** | Separate data.json file | Embedded JSON for true single-file portability |
| **Preferences** | localStorage persistence | Deferred to future (simpler MVP) |
| **Categories** | Category-based filtering | Deferred to future (simpler MVP) |
| **Fullscreen** | Fullscreen API | Deferred to future (simpler MVP) |
| **Typography** | Custom fonts | System font stack (faster load, offline-safe) |
| **File size** | ~2300 lines total | Target <1500 lines via cleaner structure |

### 12.3 Deferred to Future Phases

- Full zoom/pan with fit presets (Fit Width, Fit Height, Fill Canvas)
- Alignment presets (Center, corners)
- Category-based frame filtering
- localStorage preference persistence
- Fullscreen mode (F key)
- External data.json loading
- Frame metadata display (selection score, timecode)
- Encode metadata cards

---

## Appendix A: CSS Class Reference

| Class | Purpose |
|:------|:--------|
| `.report-viewer` | Root container |
| `.rv-header` | Top section |
| `.rv-controls` | Control toolbar |
| `.rv-viewer-stage` | Image comparison container |
| `.rv-canvas` | Zoomable wrapper |
| `.rv-left`, `.rv-right` | Image layers |
| `.rv-divider` | Slider position line |
| `.rv-filmstrip` | Thumbnail navigation |
| `.rv-filmstrip-item` | Individual thumbnail |
| `.rv-footer` | Bottom section |
| `.rv-mode-slider` | Slider mode active |
| `.rv-mode-overlay` | Overlay mode active |
| `.rv-mode-diff` | Difference mode active |
| `.rv-mode-blink` | Blink mode active |

---

## Appendix B: JavaScript Module Structure

```javascript
// Main viewer controller
const ReportViewer = {
  // State
  state: {
    currentFrame: 0,
    leftClip: 0,
    rightClip: 1,
    mode: 'slider',
    zoom: 1.0,
    revealPercent: 50,
    blinkInterval: null,
  },

  // Initialization
  init() { /* Parse data, bind events, render */ },

  // Mode handlers
  setMode(mode) { /* Update mode, re-render */ },

  // Navigation
  setFrame(index) { /* Update frame, load images */ },
  nextFrame() {},
  prevFrame() {},

  // Slider
  handleSliderDrag(e) { /* Update reveal percent */ },

  // Overlay/Diff
  cycleClip(direction) { /* Cycle through clips */ },

  // Blink
  startBlink() { /* Start interval */ },
  stopBlink() { /* Clear interval */ },

  // Zoom
  setZoom(level) { /* Update zoom */ },

  // Rendering
  render() { /* Full re-render */ },
  updateImages() { /* Update image sources only */ },
};

// Initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => ReportViewer.init());
```
