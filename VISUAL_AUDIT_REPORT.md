# Visual Audit & Critique Report: Local Report Viewer

This report presents a comprehensive critique of the updated local report viewer UI based on the visual layout, user feedback, and code inspection.

---

## Evaluation Summary

All dimension scores are compressed toward the center (3 to 7) to keep evaluations balanced.

| Dimension | Score (1-10) | Key Finding |
| :--- | :---: | :--- |
| **Thematic Consistency** | 4 / 10 | The native select dropdown options revert to standard browser light-mode colors, breaking contrast. |
| **Text Clutter & Redundancy** | 3 / 10 | Labels display duplicate category text (e.g., `Motion • Motion`) and include verbose timestamp strings. |
| **Layout & Collisions** | 3 / 10 | The top-left HTML clip label (`.rv-overlay-label`) overlaps directly with the baked-in frame metadata in all modes (Slider, Overlay, Blink). |
| **Typography & Hierarchy** | 6 / 10 | System font fallbacks are used, leading to a basic default look. |
| **Interactive Polish** | 5 / 10 | Form elements rely on basic browser controls, and bottom filters lack visual cues. |
| **Cross-Browser Consistency** | 5 / 10 | The range slider thumb lacks Firefox-specific styling, and Chrome-native number input arrows clutter the popover. |
| **Viewport rendering** | 6 / 10 | Zooming in on frames uses default bilinear scaling, introducing blur. |
| **Diff Mode Usability** | 3 / 10 | Clicking the stage in Diff mode makes the screen pure black, and bright white labels distract from dark diff detail inspections. |

---

## Detailed Audit Findings

### 1. Dropdown Options Theme Mismatch
*   **Location**: `.rv-controls select` / [viewer.css](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/assets/viewer.css)
*   **Description**: Option text color inherits `--text-primary` (almost white) but the dropdown popover background defaults to native light colors on some OSes/browsers. This renders text white-on-white.
*   **Recommendation**: Add `color-scheme: dark` to `:root` and explicitly style `select option` to use dark backgrounds.

### 2. Redundant Category Labels
*   **Location**: `.rv-filmstrip-label` / [renderer.py](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/renderer.py) & [display.py](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/display.py)
*   **Description**: If a frame belongs to the "Motion" category, the text label renders as `Motion • Motion`. Similarly, the bottom info bar displays both the label and category as duplicate strings (`Motion • MOTION`).
*   **Recommendation**: Change the default frame label to use the frame number (e.g., `Frame 3127`) instead of the category name, producing clean groupings (e.g., `Frame 3127 • Motion`).

### 3. Cluttered Timecode/Timestamp Strings
*   **Location**: `frame_detail_for_source_frame` / [display.py](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/display.py)
*   **Description**: Frame details display a detailed timecode string (`00:02:10.422`) inside parentheses. This clutters the UI and is less intuitive for comparisons than standard frame numbers.
*   **Recommendation**: Remove the timestamp details from the default frame display text, letting frame numbers serve as the primary navigator.

### 4. HTML Clip Label Overlay & Baked-in Metadata Collision (All Modes)
*   **Location**: `.rv-overlay-label` / [viewer.css](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/assets/viewer.css)
*   **Description**: The absolute-positioned left HTML label `.rv-overlay-label` (displaying e.g. "Reference") is positioned at `top: 12px; left: 12px;`. This overlaps directly with the baked-in VapourSynth frame metadata text block (e.g., `Frame 11 of 16`). This collision occurs in Slider mode, Overlay mode, and Blink mode.
*   **Recommendation**:
    - Move `.rv-overlay-label` (left) to the bottom-left (`bottom: 16px; left: 16px; top: auto;`) and `.rv-overlay-label.right` to the bottom-right (`bottom: 16px; right: 16px; top: auto; left: auto;`).
    - Recenter the stage info badge (`.rv-stage-overlay-info`) to the bottom-middle (`bottom: 16px; left: 50%; transform: translateX(-50%);`) to avoid collision and balance the UI symmetry.

### 5. Diff Mode Stage Click Bug (Black Screen)
*   **Location**: `cycleClip` & `pointerInteraction` / [viewer.js](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/assets/viewer.js)
*   **Description**: In `diff` mode, clicking on the image stage cycles the active compare clip. If there are only 2 clips, the right (compare) clip cycles to match the left (base) clip (e.g., `Reference` vs `Reference`). This renders a completely black difference screen, confusing the user.
*   **Recommendation**: Modify `cycleClip()` for split modes (`diff` and `blink`) to skip `leftClipIdx` during the cycle loop, ensuring Left and Right comparison clips are never identical.

### 6. Firefox Range Slider Thumb Styling
*   **Location**: `#zoom-range` / [viewer.css](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/assets/viewer.css)
*   **Description**: Custom range slider styling is defined only for `-webkit-slider-thumb`. On Firefox, the zoom range slider thumb defaults to an unstyled grey box.
*   **Recommendation**: Add duplicate rules targeting `::-moz-range-thumb` to ensure cross-browser styling parity.

### 7. Native Number Input Spin Buttons
*   **Location**: `.rv-number-input` / [viewer.css](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/assets/viewer.css)
*   **Description**: Browser-native increment/decrement arrows on number inputs clutter the compact manual offset fields in the alignment popover.
*   **Recommendation**: Add CSS rules to suppress `-webkit-outer-spin-button` and `-webkit-inner-spin-button`, setting `-moz-appearance: textfield` to clean up the fields.

### 8. Browser-Native Form Controls
*   **Location**: `.rv-controls select` / [viewer.css](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/assets/viewer.css)
*   **Description**: Select controls use default browser dropdown arrows, which look clunky and differ across platforms.
*   **Recommendation**: Suppress default styling using `appearance: none` and use a clean inline vector chevron SVG as a background image.

### 9. Category Filter Visual Accents
*   **Location**: `.rv-filter-chip` / [viewer.css](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/assets/viewer.css)
*   **Description**: Bottom filter chips are simple buttons that do not share the color-coded accent identifiers used by filmstrip cards.
*   **Recommendation**: Prepend a small CSS pseudo-element (`::before`) dot styled with the respective category color code.

### 10. Standard Font Fallbacks
*   **Location**: `:root { --font-sans }` / [viewer.css](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/assets/viewer.css)
*   **Description**: Using system default sans-serif fonts gives the UI a generic look.
*   **Recommendation**: Integrate a modern Google Font like `Inter` to clean up the metadata list and titles.

### 11. Zoom Interpolation Blur
*   **Location**: `.rv-image` / [viewer.css](file:///c:/Software/video/frame-compare/src/frame_compare/services/report/assets/viewer.css)
*   **Description**: Zooming in on frames uses default bilinear filtering, which blurs individual pixel boundaries.
*   **Recommendation**: Set `image-rendering: pixelated` when zoom levels increase to allow detailed pixel comparisons.

---

## Workflow Feature Suggestions

### A. Quick-Swap Clips Button & Shortcut
*   **Description**: There is currently no quick way to swap the left and right clips (`L` and `R` streams) to inspect subtle difference changes. Swapping them requires opening two separate dropdown selects.
*   **Proposal**: Add a swap button `⇄` in the controls bar between the Left and Right select elements, and bind the `X` key to toggle/swap the clip selection indices.

### B. Toggle Overlays Visibility (Hide UI overlays)
*   **Description**: In Diff mode, bright white HTML overlay text boxes distract from inspecting dark differences in the corners.
*   **Proposal**: Bind the `H` key to toggle the visibility of all HTML overlays (labels and stage info badge) on and off, allowing a clean, distraction-free view of the differences.

### C. Touch & Gesture Support
*   **Description**: Pinch-to-zoom and pan gestures are not natively integrated into the viewer stage for mobile, tablet, or trackpad users. Additionally, there is no double-click shortcut to zoom/reset.
*   **Proposal**: Listen for touch/pointer events to calculate zoom pinch scales, and map double-clicks to reset the stage's viewport zoom and pan state to 100%.
