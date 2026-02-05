# Local HTML Report Viewer — Technical Reference

> **Purpose:** Offline-viewable interactive comparison viewer for video frame screenshots
> **Last Updated:** 2026-01-02

---

## 1. Overview

The **Local HTML Report Viewer** is a self-contained, offline-viewable web application for comparing video frame screenshots across multiple encodes. It consists of:

- `index.html` — Single-page application with embedded data
- `app.js` — Interactive viewer logic (~1800 lines)
- `app.css` — Dark-themed styling (~500 lines)
- `data.json` — Structured comparison data

**Key capabilities:**

- Four comparison modes (Slider, Overlay, Difference, Blink)
- Zoom & pan with fit presets
- Category-based frame filtering
- Filmstrip thumbnail navigation
- Keyboard shortcuts for power users
- Persistent user preferences via localStorage

---

## 2. Viewer Modes

### 2.1 Slider Mode (Default)

Displays two images with a draggable divider revealing left/right sides.

**Behavior:**

- Drag divider or click anywhere to set reveal position
- Left image clipped via CSS `clip-path: inset(0 {percentage}% 0 0)`
- 2px accent divider line shows current position

**Use case:** Precise pixel-level comparison at specific screen regions.

---

### 2.2 Overlay Mode

Shows a single encode at a time, cycling through available encodes.

**Behavior:**

- Click viewer or press `↑`/`↓` to cycle encodes
- Maintains independent overlay encode selection from slider selections
- Full image visibility (no clipping)

**Use case:** Viewing each encode in isolation without split-view distraction.

---

### 2.3 Difference Mode

Uses CSS blend modes to highlight pixel differences between images.

**CSS implementation:**

```css
.rc-mode-difference .rc-overlay {
  mix-blend-mode: difference;
}
```

**Behavior:**

- Identical pixels appear black
- Differences show as colored pixels (inverted delta)
- Click to cycle which encode is compared

**Use case:** Identifying subtle compression artifacts, color shifts, or encoding errors.

---

### 2.4 Blink Mode

Alternates between left and right images at 700ms intervals.

**Behavior:**

- Automatic toggling between images
- Hold mouse down to pause (shows left image)
- Release to resume blinking

**Use case:** Motion comparison and spotting temporal differences.

---

## 3. Zoom & Pan Controls

### 3.1 Zoom

| Control | Action |
|:--------|:-------|
| Slider | Drag zoom slider (25%–400%) |
| Buttons | `+`/`−` buttons (10% steps) |
| Wheel | `Ctrl/Cmd + scroll` to zoom |
| Keyboard | `R` to reset to 100% |

### 3.2 Fit Presets

| Preset | Description |
|:-------|:------------|
| **Actual size** | 100% native resolution |
| **Fit width** | Scale to fill viewer width |
| **Fit height** | Scale to fill viewer height |
| **Fill canvas** | Scale to cover entire viewer |

### 3.3 Pan

| Trigger | Condition |
|:--------|:----------|
| Drag | When image exceeds viewport |
| Space + Drag | Always (pan modifier) |

**Alignment presets:** Center, Top-left, Top-right, Bottom-left, Bottom-right

When manually panning, alignment switches to "Custom (manual)" and resets on frame change.

---

## 4. Frame Navigation

### 4.1 Filmstrip

Horizontal scrolling thumbnail strip showing all frames:

- **Thumbnail:** First encode's image (lazy-loaded)
- **Category badge:** Uppercase label (e.g., "ACTION")
- **Caption:** Frame number + optional label
- **Active state:** Highlighted border on current frame

### 4.2 Frame Selector

Dropdown showing frame numbers with optional labels (e.g., `1000 — Dark Scene`)

### 4.3 Category Filters

When frames have category labels, filter chips appear:

- **All:** Shows all frames (clears filters)
- **Individual categories:** Toggle to show/hide category
- **Count badges:** Show frames per category
- Selecting all categories clears to "All" state

---

## 5. Encode Information

### 5.1 Encode Selector

Two dropdowns for left/right encode selection:

- Overlay mode: Single "Displayed encode" dropdown
- Other modes: Separate Left/Right dropdowns

### 5.2 Encode Cards

Display encode metadata when available:

- Encode label (heading)
- Key-value metadata (codec, resolution, bitrate, etc.)

### 5.3 Frame Metadata

When `include_metadata: "full"`, displays:

- Selection score, source, timecode
- Category label, notes
- Rendered as two-column table

---

## 6. Keyboard Shortcuts

| Key | Action |
|:----|:-------|
| `←` / `→` | Previous / Next frame |
| `↑` / `↓` | Cycle encodes (Overlay/Diff/Blink) |
| `D` | Switch to Difference mode |
| `B` | Switch to Blink mode |
| `R` | Reset zoom to 100% |
| `F` | Toggle fullscreen |
| `Space` | Hold to enable pan |
| `Ctrl/Cmd + Wheel` | Zoom in/out |

---

## 7. Visual Design

### 7.1 Theme

Dark mode with accent highlights:

| Element | Color |
|:--------|:------|
| Background | `#0f1115` |
| Surface | `#1b1f2b` |
| Accent | `rgba(159, 210, 255, *)` |
| Text | `#f4f6fb` |
| Muted | `rgba(240, 244, 255, 0.6-0.85)` |

### 7.2 Layout

```
┌─────────────────────────────────────────────────┐
│ Header: Title, Subtitle, slow.pics link         │
├─────────────────────────────────────────────────┤
│ Controls: Frame | Left | Right | Reveal | Mode  │
│           Zoom toolbar | Fit presets | Alignment│
├─────────────────────────────────────────────────┤
│                                                 │
│              Viewer Stage                       │
│         (Image comparison area)                 │
│                                                 │
│         Frame info + Help text                  │
├─────────────────────────────────────────────────┤
│ Category Filters (conditional)                  │
│ Filmstrip: [Thumb] [Thumb] [Thumb] ...          │
├─────────────────────────────────────────────────┤
│ Encode Cards (metadata)                         │
│ Frame Metadata (conditional)                    │
├─────────────────────────────────────────────────┤
│ Footer: Generated date, frame/encode counts     │
└─────────────────────────────────────────────────┘
```

### 7.3 Responsive Behavior

- Fluid typography: `clamp(1.6rem, 3vw, 2.3rem)` for title
- Fluid padding: `clamp(1.5rem, 4vw, 3rem)`
- Single breakpoint at 768px reduces filmstrip padding and viewer height

---

## 8. Fullscreen Mode

Toggle via `F` key or button. In fullscreen:

- Header and footer hidden
- Viewer fills entire screen
- Controls remain accessible
- Exit returns focus to previous element

---

## 9. User Preferences

Persisted to `localStorage` (key: `frameCompareReportViewer.v3`):

| Setting | Persisted |
|:--------|:----------|
| Zoom level | ✓ |
| Fit preset | ✓ |
| Alignment | ✓ |
| Viewer mode | ✓ |
| Overlay encode | ✓ |
| Active categories | ✓ |
| Current frame | ✓ |

Preferences restore on page reload and across sessions.

---

## 10. Accessibility

- Full keyboard navigation
- ARIA labels on all controls
- `aria-pressed` on toggle buttons
- `aria-current` on active filmstrip item
- `aria-live` regions for dynamic updates
- Focus management for fullscreen transitions
- Meaningful alt text on images

---

## 11. Data Structure

The viewer expects a JSON payload with:

```typescript
interface ReportData {
  title: string;
  generated_at: string;        // ISO 8601
  viewer_mode: string;         // Default mode
  slowpics_url?: string;       // External link
  stats: { frames: number; encodes: number };
  encodes: Array<{
    label: string;
    safe_label: string;
    source: string;
    metadata?: Record<string, string>;
  }>;
  frames: Array<{
    index: number;
    files: Array<{ encode: string; path: string; safe_label: string }>;
    label?: string;
    thumbnail?: string;
    category?: string;
    category_key?: string;
  }>;
  categories: Array<{ key: string; label: string; count: number }>;
  defaults: { left?: string; right?: string };
}
```

**Loading strategy:**

1. Parse embedded `<script id="report-data">` JSON
2. Fallback: Fetch external `data.json`

---

## 12. Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Requires: ES6, CSS custom properties, `clip-path`, `mix-blend-mode`
- localStorage for preferences (graceful degradation if unavailable)
- Fullscreen API with vendor prefixes

---

## Appendix: CSS Class Reference

| Class | Purpose |
|:------|:--------|
| `.rc-header` | Top navigation bar |
| `.rc-controls` | Control toolbar |
| `.rc-viewer-stage` | Image comparison container |
| `.rc-canvas` | Zoomable image wrapper |
| `.rc-overlay` | Left image layer |
| `.rc-divider` | Slider position line |
| `.rc-filmstrip` | Thumbnail navigation |
| `.rc-frame-thumb__*` | Filmstrip components |
| `.rc-category-filter__chip` | Filter pill buttons |
| `.rc-encode-card` | Metadata display cards |
| `.rc-mode-{name}` | Mode-specific styling |
