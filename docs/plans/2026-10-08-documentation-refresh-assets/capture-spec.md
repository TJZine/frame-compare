---
search:
  exclude: true
---

Status: Historical
Scope: Subordinate specification for the completed
[documentation refresh](../2026-10-08-documentation-refresh.md).

The instructions below record that workstream's authoring requirements.
Current behavior is documented in the maintained guides and references.

# Documentation refresh: capture specification

Part of the [documentation refresh plan](../2026-10-08-documentation-refresh.md).
Unit U1 executes the macOS section; unit U10 executes the physical-Windows section.
Every value here is a decision: change nothing. Any failed check, missing input, or
step that does not behave as written is a stop (`blocked`).

## Decisions and reasons

- **Media.** Only the two official EBU/DVB transport streams, used byte-for-byte. No
  remux, re-encode, derivative, synthetic, or private media. The files are licensed
  CC BY 4.0 and carry generic official names.
- **Sources.** Two: the PQ10 stream is the reference and the HLG10 stream is the
  comparison. Both are tonemapped to SDR, so every view shows real HDR handling.
- **No Diff figure.** A natural PQ10/HLG10 difference fills the frame with
  presentation-transform colour change and misleads at documentation width (recorded
  during the 2026-08-17 capture). The Diff mode is described in text only.
- **Report generation in Docker on macOS.** The report is static HTML, so a Mac
  browser renders the same viewer the Windows bundle produces. Docker gives generic
  `/workspace` paths, so no host path or username can reach a capture.
- **Viewer captures by script.** Five viewer states need the same viewport, scale,
  frame, pair, and clean browser state. The tested script below drives headless
  Chrome through the DevTools protocol with Node's built-in WebSocket; it adds no
  dependency and is not committed as a file. Manual browser capture produced
  inconsistent surfaces in the 2026-08-17 pass.
- **Terminal captures as SVG.** Frame Compare's terminal output is Rich text. The
  converter below renders the captured ANSI output with Rich's own SVG exporter, so
  text stays sharp and searchable at any width and the file stays small. The remote
  `@font-face` rules that Rich emits are removed so the docs load no external font.
- **Windows-only captures.** The installer output and the visible VSView panel exist
  only on the physical Windows host (unit U10).

Both scripts below were run on 2026-10-08 against a Docker-generated two-source HDR
report (PQ- and HLG-tagged test streams with the exact labels and config above):
all five viewer states, the clipped dialog, the `Comparison complete` panel
extraction, and the dry-run SVG rendered as specified.

## Prerequisites (maintainer, before U1 starts)

1. Obtain the two files from the Windows capture host's earlier download, or download
   them from the DVB HEVC test-content page
   (`https://dvb.org/specifications/verification-validation/hevc-test-content/`),
   which asks for a name and email address:
   `DVB_7680x4320_HEVC_50fps_PQ10.ts` and `DVB_7680x4320_HEVC_50fps_HLG10.ts`.
2. Place them in `$HOME/FrameCompareCapture/source/` on the Mac.
3. Tell the orchestrator they are in place. U1 does not download anything.

## Host and tools (U1)

| Item | Requirement |
| --- | --- |
| Host | The maintainer's Mac with Docker Desktop running |
| Repository state | `HEAD` when U1 is dispatched (this plan changes no product code); record the SHA |
| Docker image | `frame-compare:dev`, rebuilt from that checkout with `docker compose build frame-compare-run` |
| Browser | Google Chrome at `/Applications/Google Chrome.app` (record `--version`) |
| Node | Node 22 or newer on `PATH` (record `node --version`) |
| WebP encoder | `cwebp` on `PATH` (record `cwebp -version`) |
| Python | The repository environment, through `uv run --no-sync python` |
| Scratch | `.tmp/docs-refresh-2026-10-08/capture/` inside the repository (ignored by Git) |

## Workspace (U1)

Create this layout. The `.ts` names change; the bytes do not.

```text
$HOME/FrameCompareCapture/
├── source/
│   ├── DVB_7680x4320_HEVC_50fps_PQ10.ts
│   └── DVB_7680x4320_HEVC_50fps_HLG10.ts
├── comparison_videos/
│   ├── pq10-reference.ts      (copy of DVB_7680x4320_HEVC_50fps_PQ10.ts)
│   └── hlg10-comparison.ts    (copy of DVB_7680x4320_HEVC_50fps_HLG10.ts)
├── config/
│   └── config.toml
└── generated/
```

```bash
CAP="$HOME/FrameCompareCapture"
mkdir -p "$CAP/comparison_videos" "$CAP/config" "$CAP/generated"
cp "$CAP/source/DVB_7680x4320_HEVC_50fps_PQ10.ts" "$CAP/comparison_videos/pq10-reference.ts"
cp "$CAP/source/DVB_7680x4320_HEVC_50fps_HLG10.ts" "$CAP/comparison_videos/hlg10-comparison.ts"
shasum -a 256 "$CAP/comparison_videos/pq10-reference.ts" "$CAP/comparison_videos/hlg10-comparison.ts"
```

The hashes must equal, case-insensitively:

| File | SHA-256 |
| --- | --- |
| `pq10-reference.ts` | `33773E7275B83976B0D9A19D3AED47AA0FEDB1280BA2019FE3DD344A05DA8D83` |
| `hlg10-comparison.ts` | `B9EA646565751BB41CFC1F954172FDF5162C890D35AAC22238F536F6CF425300` |

A mismatch is a stop.

`$CAP/config/config.toml`, exactly:

```toml
[sources]
reference = "pq10-reference.ts"
analysis_source = "reference"
label_mode = "stem"

[sources.overrides."pq10-reference.ts"]
label = "EBU DVB PQ10 — Reference"

[sources.overrides."hlg10-comparison.ts"]
label = "EBU DVB HLG10 — Comparison"

[analysis]
user_frames = [1000]
random_frame_count = 3
dark_frame_count = 1
bright_frame_count = 1
motion_frame_count = 0
random_seed = 42

[audio_alignment]
enable = false

[screenshots]
overlay_mode = "standard"
geometry_mode = "aligned"
aligned_scale_policy = "explicit_size"
aligned_target_width = 3840
aligned_target_height = 2160

[color]
preset = "reference"

[report]
auto_open = false
default_mode = "slider"

[slowpics]
auto_upload = false

[tmdb]
enabled = false
```

Audio alignment is disabled because the captures are about the report and HDR
handling; the DVB streams are not an alignment example. Screenshots are scaled to
3840 × 2160 so rendering stays fast and the report loads quickly.

## Runs (U1)

Define the Docker command once, from the repository root:

```bash
CAP="$HOME/FrameCompareCapture"
fc() {
  docker run --rm \
    -e FORCE_COLOR=1 -e TTY_INTERACTIVE=0 -e COLUMNS=100 \
    -u "$(id -u):$(id -g)" \
    -e HOME=/tmp/framecompare-home \
    -e PYTHONUSERBASE=/home/framecompare/.local \
    -e VAPOURSYNTH_EXTRA_PLUGIN_PATH=/opt/vapoursynth-extra-plugins \
    -v "$CAP/comparison_videos:/workspace/comparison_videos:ro" \
    -v "$CAP/config:/workspace/config:ro" \
    -v "$CAP/generated:/workspace/generated" \
    -w /workspace frame-compare:dev "$@"
}
OUT=.tmp/docs-refresh-2026-10-08/capture
mkdir -p "$OUT"
```

1. `fc run --root /workspace --dry-run > "$OUT/dry-run.ansi" 2>&1` — exit 0.
2. `fc run --root /workspace --skip-metadata > "$OUT/run.ansi" 2>&1` — exit 0. The
   run folder is `$CAP/generated/pq10-reference + hlg10-comparison/`. Confirm
   `screenshots/1000 - pq10-reference.png` and `screenshots/1000 - hlg10-comparison.png`
   exist; if frame 1000 is absent, stop.
3. `fc run --root /workspace --skip-metadata --overlay diagnostic --quiet > "$OUT/diagnostic.log" 2>&1`
   — exit 0. Its run folder is `$CAP/generated/pq10-reference + hlg10-comparison_2/`.

Steps 2 and 3 must run in this order on an empty `generated/` so the folder names
match. If `generated/` is not empty before step 2, empty it first.

## Terminal SVGs (U1)

Write this converter to `$OUT/ansi_to_svg.py`, exactly:

```python
"""Convert captured Frame Compare ANSI output into a documentation SVG.

Usage: python ansi_to_svg.py INPUT OUTPUT --title TITLE [--panel PANEL_TITLE] [--width 100]
"""
import argparse, io, re, sys
from rich.console import Console
from rich.terminal_theme import TerminalTheme
from rich.text import Text

OSC8 = re.compile(r"\x1b\]8;[^\x1b\x07]*(?:\x1b\\|\x07)")
SGR = re.compile(r"\x1b\[[0-9;]*m")
THEME = TerminalTheme(
    (20, 20, 20), (236, 236, 234),
    [(20, 20, 20), (224, 108, 96), (138, 196, 120), (233, 162, 76), (120, 160, 220),
     (190, 140, 210), (110, 190, 190), (200, 200, 196)],
    [(111, 111, 107), (240, 130, 118), (160, 214, 142), (255, 192, 120), (150, 185, 235),
     (210, 165, 225), (140, 210, 210), (236, 236, 234)],
)

def select_panel(text: str, title: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        plain = SGR.sub("", line)
        if plain.lstrip().startswith("╭") and title in plain:
            for j in range(i, len(lines)):
                if SGR.sub("", lines[j]).lstrip().startswith("╰"):
                    return "\n".join(lines[i : j + 1])
    sys.exit(f"panel not found: {title}")

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("input"); p.add_argument("output")
    p.add_argument("--title", required=True); p.add_argument("--panel")
    p.add_argument("--width", type=int, default=100)
    a = p.parse_args()
    raw = OSC8.sub("", open(a.input, encoding="utf-8").read())
    if a.panel:
        raw = select_panel(raw, a.panel)
    console = Console(record=True, width=a.width, file=io.StringIO(), force_terminal=True, color_system="truecolor")
    console.print(Text.from_ansi(raw.rstrip("\n")), soft_wrap=True)
    svg = console.export_svg(title=a.title, theme=THEME, font_aspect_ratio=0.61)
    svg = re.sub(r"@font-face\s*\{.*?\}\s*", "", svg, flags=re.S)
    open(a.output, "w", encoding="utf-8").write(svg)

main()
```

```bash
uv run --no-sync python "$OUT/ansi_to_svg.py" "$OUT/dry-run.ansi" docs/images/terminal-dry-run.svg --title "frame-compare run --dry-run"
uv run --no-sync python "$OUT/ansi_to_svg.py" "$OUT/run.ansi" docs/images/terminal-run-complete.svg --title "frame-compare run" --panel "Comparison complete"
```

Then confirm both files contain no `@font-face`, `cdnjs`, `/Users/`, or the
maintainer's username (`grep -c`). Any hit is a stop.

## Viewer captures (U1)

Write this script to `$OUT/capture_viewer.mjs`, exactly:

```javascript
// Capture Frame Compare report-viewer states with headless Chrome over CDP.
// Usage: node capture_viewer.mjs <report.html> <out-dir>
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const CHROME = process.env.REPORT_BROWSER ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const [reportArg, outArg] = process.argv.slice(2);
if (!reportArg || !outArg) throw new Error("usage: node capture_viewer.mjs <report.html> <out-dir>");
const reportUrl = pathToFileURL(resolve(reportArg)).href;
const outDir = resolve(outArg);
mkdirSync(outDir, { recursive: true });
const VIEWPORT = { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false };
const PORT = 9333;

const FRAME = process.env.CAPTURE_FRAME ?? "1000";
const RIGHT = process.env.CAPTURE_RIGHT ?? "EBU DVB HLG10 — Comparison";

// Each shot starts from a fresh load with cleared storage, then runs its steps in order.
// Steps: ["frame", n] selects "Frame n ..."; ["right", label] selects the right clip;
// ["click", selector]; ["move", x, y] moves the pointer; ["wait", ms].
// A shot with `clip` captures only that element's bounding box.
const BASE = [["frame", FRAME], ["right", RIGHT], ["wait", 600]];
const SHOTS = [
  { name: "report-overview", steps: [...BASE, ["click", '[aria-label="Slider mode"]'], ["wait", 800]] },
  { name: "report-grid", steps: [...BASE, ["click", '[aria-label="Grid mode"]'], ["wait", 1200]] },
  { name: "report-inspector", steps: [...BASE, ["click", '[aria-label="Open Inspector"]'], ["wait", 600], ["click", "#inspector-tab-clips"], ["wait", 600]] },
  { name: "report-lens", steps: [...BASE, ["click", '[aria-label="Turn lens on"]'], ["wait", 400], ["move", 640, 470], ["wait", 800]] },
  { name: "report-information", steps: [...BASE, ["click", '[aria-label="Report information"]'], ["wait", 800]], clip: "#info-modal .rv-modal-content" },
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const profile = mkdtempSync(join(tmpdir(), "fc-capture-"));
const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--no-default-browser-check", "--allow-file-access-from-files",
  "--hide-scrollbars", "--force-color-profile=srgb", "--lang=en-US", "about:blank",
], { stdio: "ignore", env: { ...process.env, TZ: "UTC" } });

try {
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(200);
    try { target = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find((t) => t.type === "page"); } catch {}
  }
  if (!target) throw new Error("Chrome DevTools endpoint did not start");
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let id = 0; const pending = new Map();
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const send = (method, params = {}) => new Promise((r, j) => {
    const n = ++id; pending.set(n, (m) => (m.error ? j(new Error(`${method}: ${m.error.message}`)) : r(m.result)));
    ws.send(JSON.stringify({ id: n, method, params }));
  });
  const evaluate = async (expression) => {
    const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text);
    return r.result.value;
  };
  await send("Page.enable"); await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", VIEWPORT);
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });

  for (const shot of SHOTS) {
    await send("Page.navigate", { url: reportUrl }); await sleep(800);
    await evaluate("localStorage.clear(); sessionStorage.clear(); true");
    await send("Page.reload", { ignoreCache: true }); await sleep(1500);
    await evaluate("document.fonts.ready.then(() => true)");
    for (const [kind, arg, ...rest] of shot.steps) {
      if (kind === "wait") { await sleep(arg); continue; }
      if (kind === "move") {
        await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: arg, y: rest[0] });
        continue;
      }
      if (kind === "frame" || kind === "right") {
        const select = kind === "frame" ? "#frame-select" : "#right-select";
        const prefix = kind === "frame" ? `Frame ${arg} ` : arg;
        const ok = await evaluate(`(() => { const s = document.querySelector(${JSON.stringify(select)}); const o = s && [...s.options].find((x) => x.text.startsWith(${JSON.stringify(prefix)})); if (!o) return false; s.value = o.value; s.dispatchEvent(new Event("change", { bubbles: true })); return true; })()`);
        if (!ok) throw new Error(`${shot.name}: no ${kind} option starting with ${prefix}`);
        await sleep(600);
        continue;
      }
      const ok = await evaluate(`(() => { const el = document.querySelector(${JSON.stringify(arg)}); if (!el) return false; el.scrollIntoView({block: "center"}); el.click(); return true; })()`);
      if (!ok) throw new Error(`${shot.name}: selector not found: ${arg}`);
    }
    await evaluate("Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; }))).then(() => true)");
    await sleep(400);
    let clip;
    if (shot.clip) {
      clip = await evaluate(`(() => { const r = document.querySelector(${JSON.stringify(shot.clip)}).getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height), scale: 1 }; })()`);
    }
    const { data } = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false, ...(clip ? { clip } : {}) });
    writeFileSync(join(outDir, `${shot.name}.png`), Buffer.from(data, "base64"));
    console.log(`captured ${shot.name}.png`);
  }
  ws.close();
} finally {
  chrome.kill("SIGTERM"); await sleep(500); rmSync(profile, { recursive: true, force: true });
}
```

```bash
node "$OUT/capture_viewer.mjs" "$CAP/generated/pq10-reference + hlg10-comparison/report.html" "$OUT/viewer"
for name in report-overview report-grid report-inspector report-lens report-information; do
  cwebp -quiet -q 90 -metadata none "$OUT/viewer/$name.png" -o "docs/images/$name.webp"
done
```

Open each PNG and confirm it matches its row in the asset table below. A capture
showing a loading message, an error, a different frame, or a different pair is a stop.

## HDR diagnostic crop (U1)

```bash
uv run --no-sync python -c "
from PIL import Image
src = '$CAP/generated/pq10-reference + hlg10-comparison_2/screenshots/1000 - hlg10-comparison.png'
Image.open(src).crop((0, 0, 1920, 1080)).save('$OUT/hdr-crop.png')
"
cwebp -quiet -q 90 -metadata none "$OUT/hdr-crop.png" -o docs/images/hdr-diagnostic-overlay.webp
```

The crop must show the complete baked diagnostic block, including the `Signal:` and
`Tonemap:` lines. If any line is cut off, stop.

## Asset table

Dimensions are exact where given. Assets marked "as generated" or "as captured" have
no fixed size: their figures omit the `width` and `height` attributes (visual
specification, Figures). "Pages" lists every page that embeds the asset. Every
caption of an EBU-footage asset ends with "Footage © EBU, CC BY 4.0."; the home page
and README carry the full credit line instead (visual specification and
`pages-get-started.md`).

| File | Host and unit | Content | Size | Pages | Alt text | Caption |
| --- | --- | --- | --- | --- | --- | --- |
| `report-overview.webp` | Mac, U1 | Slider mode, frame 1000, left `EBU DVB PQ10 — Reference`, right `EBU DVB HLG10 — Comparison`, default zoom, source labels on | 1600 × 1000 | `docs/index.md` (hero and strip), `README.md`, `docs/guides/reports-and-overlays.md` | Frame Compare report in Slider mode comparing the EBU DVB PQ10 reference with the HLG10 comparison at frame 1000. | Home: set in `docs/index.md`. Reports guide: "Slider mode reveals one source against another across the divider; source labels name each side. Footage © EBU, CC BY 4.0." README: none (Markdown image). |
| `report-grid.webp` | Mac, U1 | Grid mode, frame 1000 | 1600 × 1000 | `docs/index.md` (strip), `docs/guides/reports-and-overlays.md` | Report in Grid view showing the PQ10 reference and HLG10 comparison side by side at frame 1000. | "Grid view keeps every source on screen; pick the outlier, then switch to Slider. Footage © EBU, CC BY 4.0." |
| `report-inspector.webp` | Mac, U1 | Slider mode with the Inspector open on the **Clips** tab | 1600 × 1000 | `docs/index.md` (strip), `docs/guides/reports-and-overlays.md` | Report with the Inspector open on the Clips tab, listing each source's picture size, length, file size, presentation, and signal. | "The Clips tab shows each source's identity, HDR signal, and how it was presented for review. Footage © EBU, CC BY 4.0." |
| `report-lens.webp` | Mac, U1 | Slider mode with the lens on, pointer at viewport (640, 470) | 1600 × 1000 | `docs/index.md` (strip), `docs/guides/reports-and-overlays.md` | Report in Slider mode with the lens magnifying the area under the pointer. | "The lens magnifies the area under the pointer; drag its grip to move the window. Footage © EBU, CC BY 4.0." |
| `report-information.webp` | Mac, U1 | **Report Information** dialog, clipped to the dialog | as captured; record it in `docs/images/README.md` | `docs/guides/reports-and-overlays.md` (`fc-figure--narrow`) | Report Information dialog listing the title, report ID, generated time, content, the Opens in view, the default pair, and the sources. | "Report Information holds the report's metadata and rendering settings in one place. Footage © EBU, CC BY 4.0." |
| `hdr-diagnostic-overlay.webp` | Mac, U1 | Top-left 1920 × 1080 crop of the frame-1000 HLG10 screenshot with the `diagnostic` overlay | 1920 × 1080 | `docs/guides/hdr-tonemapping.md` | Diagnostic overlay on the EBU DVB HLG10 comparison at frame 1000, listing the source, geometry, HLG BT.2020 signal, and BT.2390 tonemap at 100 nits. | "A diagnostic overlay bakes the observed signal and the applied tonemap into the screenshot. The target nits describe the output transform, not measured luminance. Footage © EBU, CC BY 4.0." |
| `terminal-dry-run.svg` | Mac, U1 | Complete human dry-run output | as generated | `docs/guides/first-comparison.md` | Dry-run output listing the workspace, two sources, the reference, frame counts, outputs, and disabled publishing. | "A dry run shows what a real run would use and create, without touching media or the network." |
| `terminal-run-complete.svg` | Mac, U1 | The `Comparison complete` panel from the run | as generated | `docs/guides/first-comparison.md` | Completed run summary with the report and screenshot paths, frame and source counts, and timings. | "The summary links the report and screenshots of the run folder you created." |
| `windows-portable-install.png` | Windows, U10 | Checksum verification line through the install script's final "open a new terminal" line | 1200 px wide maximum, height as cropped | `docs/windows-portable.md` | Windows PowerShell showing a verified SHA-256 checksum followed by a successful shim installation. | "Verify the ZIP first, then install the shim and open a new terminal so the updated PATH applies." |
| `vsview-alignment-panel.webp` | Windows, U10 | The **Frame Compare Alignment Review** panel with both sources visited at frame 1000 and the ready state shown | panel bounds as captured, 900 px wide maximum | `docs/guides/vsview-review.md` (`fc-figure--narrow`) | VSView alignment panel listing the Reference and Comparison 1 positions as captured and ready to confirm. | "When every source shows a captured position, the panel is ready to confirm the whole lineup." |

Files deleted from `docs/images/` by U1: `report-viewer-overview.webp`,
`report-slider.webp`, `report-diff.webp`, `first-run-dry-run.png`,
`first-run-complete.png`. Files replaced in place by U1: `report-grid.webp`,
`report-inspector.webp`, `hdr-diagnostic-overlay.webp`. Replaced by U10:
`windows-portable-install.png`. New: the remaining rows.

## Physical Windows captures (U10)

Run on the physical Windows 10/11 x64 capture host at display scaling 100%, in a
workspace at `C:\FrameCompareDemo\` (never under the user profile).

### Installer output

1. Build the portable bundle from the integrated commit with the runbook's
   "Windows portable local packaging path" commands.
2. In PowerShell 7 at the repository root, create the ZIP and its checksum file:

   ```powershell
   Compress-Archive -Path "dist\frame-compare-portable-win-x64\*" -DestinationPath "C:\FrameCompareDemo\frame-compare-portable-win-x64-capture.zip"
   $hash = (Get-FileHash -LiteralPath "C:\FrameCompareDemo\frame-compare-portable-win-x64-capture.zip" -Algorithm SHA256).Hash.ToLowerInvariant()
   Set-Content -LiteralPath "C:\FrameCompareDemo\frame-compare-portable-win-x64-capture.zip.sha256" -Value "$hash  frame-compare-portable-win-x64-capture.zip" -NoNewline
   Expand-Archive -LiteralPath "C:\FrameCompareDemo\frame-compare-portable-win-x64-capture.zip" -DestinationPath "C:\FrameCompareDemo\bundle"
   ```

   `C:\FrameCompareDemo\bundle` must not exist beforehand; `install.cmd` must then be
   at `C:\FrameCompareDemo\bundle\install.cmd`.
3. Open a new Windows Terminal window, 120 columns by 30 rows, running PowerShell 7
   without your profile (so the prompt shows only the path), from Run (Win+R):

   ```text
   wt --size 120,30 pwsh -NoProfile -NoLogo -WorkingDirectory C:\FrameCompareDemo
   ```

   Use the default colour scheme and font size 12. In that window run, in this order:

   ```powershell
   Set-Location C:\FrameCompareDemo
   $env:LOCALAPPDATA = "C:\FrameCompareDemo\LocalAppData"
   Clear-Host
   $tag = "capture"
   ```

   Then paste the checksum block from `docs/windows-portable.md` ("Then verify the ZIP
   checksum") exactly, and run `& .\bundle\install.cmd`. Overriding `LOCALAPPDATA` for
   this tab only keeps the printed install path generic and leaves your real Frame
   Compare installation untouched (`tools/windows_portable/install.ps1:39-41`).
4. Capture the terminal with the Snipping Tool as PNG. Crop from the
   `SHA-256 verified:` line through the line `Open a new terminal, then run:
   frame-compare --help`, at full terminal width, without scaling. Every kept path must
   start with `C:\FrameCompareDemo`; any other path or the Windows user name is a stop.
5. Clean up in the same tab: run `& .\bundle\uninstall.cmd`, which removes the
   `C:\FrameCompareDemo\LocalAppData\Programs\FrameCompare\bin` entry it added to your
   user `PATH`. Confirm with
   `[Environment]::GetEnvironmentVariable("Path", "User")` that the entry is gone.
6. Save as `docs/images/windows-portable-install.png` (PNG, 1200 px wide maximum;
   if the crop is wider, stop and report the width). Set the figure's `width` and
   `height` in `docs/windows-portable.md` to the saved file's pixel size.

### VSView panel

1. Use the bundle extracted for the installer capture. Copy the two verified `.ts` files to `C:\FrameCompareDemo\comparison_videos\` with
   the names and hashes from the workspace table above, and write
   `C:\FrameCompareDemo\config\config.toml` as the macOS config with
   `[audio_alignment] enable = true` and `use_vsview = true` replacing
   `enable = false`.
2. Run the capture bundle's own launcher with the explicit config, so the installed
   shim cannot inject another config (`tools/windows_portable/shim/frame-compare.ps1:170-187`):

   ```powershell
   pwsh -NoProfile -File C:\FrameCompareDemo\bundle\frame-compare.ps1 run --root C:\FrameCompareDemo --config C:\FrameCompareDemo\config\config.toml --skip-metadata
   ```
3. In VSView, open **Frame Compare Alignment Review** from the Tool Panel, unlink the
   playheads, move `Reference` and `Comparison 1` to frame 1000, and wait until the
   panel reports the ready state. Do not confirm.
4. Capture the panel's bounds only (no VSView title bar, no other window) as PNG with
   the Snipping Tool. Then close VSView without saving.
5. Convert with `cwebp -q 90 -metadata none` to
   `docs/images/vsview-alignment-panel.webp`. If the PNG is wider than 900 px, stop and
   report the width. In the figure U10 inserts, set `width` and `height` to the saved
   file's pixel size.

## Privacy review (U1 and U10)

Before handing back, open every new or replaced file at full size and confirm it
contains none of: user names, home-directory paths (`/Users/`, `C:\Users\`), private
release names or groups, server or share names, API keys, webhook URLs, tokens, or
environment values. Confirm alt text and captions match what the image shows. Record
the check in the unit report.
