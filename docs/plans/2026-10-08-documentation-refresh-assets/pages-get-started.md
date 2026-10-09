---
search:
  exclude: true
---

# Documentation refresh: Get started pages and README

Part of the [documentation refresh plan](../2026-10-08-documentation-refresh.md).
Owned by unit U3. Apply the [style guide](style-guide.md) to new prose. "Keep" means
byte-identical except for the listed edits and the style guide's
[mechanical corrections](style-guide.md#mechanical-corrections-in-kept-text);
"verbatim" means not one character changes, not even mechanical corrections. Line
numbers refer to the base commit `80beafdcdabc7ac556f78fada5e7593b89e8880c`.

## `README.md` — edit

Outline (H2s unchanged): title and tagline, badges, route links, intro, hero image,
"Why Frame Compare", "Installation", "First comparison", "Documentation map",
"Project status", "License".

1. After the intro paragraph (current lines 15–19), insert the hero image as its own
   paragraph:
   `![Frame Compare report in Slider mode comparing the EBU DVB PQ10 reference with the HLG10 comparison at frame 1000.](docs/images/report-overview.webp)`

   followed by this paragraph, exactly:
   `<sub>Footage: EBU/DVB HEVC test content © EBU, shot by Frans de Jong (EBU), PQ10 conversion by Andrew Cotton (BBC), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).</sub>`
2. "Why Frame Compare" bullets: keep the first, third, and fifth bullets. Replace the
   second bullet (base lines 25–26) with exactly:
   `- **Alignment-aware comparisons** — apply an automatic audio offset only when the video confirms it, reuse accepted offsets, and review the rest in the VSView alignment panel.`
   Replace the fourth bullet (base lines 29–31) with exactly:
   `- **An offline review report** — inspect Slider, Single, Diff, Blink, and Grid views; navigate by frame or category; zoom, pan, use the lens and Inspector, and keep browser-local review notes.`
   (Wrap both at 88 columns with two-space continuation indents, as in the base.)
3. "Installation": keep the table. Replace the sentence after it with: "Not sure
   which route fits? See `[Choose an installation](docs/getting-started/index.md)`."
4. "First comparison": keep.
5. "Documentation map": replace the list with, in order:
   `[How Frame Compare works](docs/guides/how-it-works.md)`,
   `[Sources, references, and labels](docs/guides/sources-and-labels.md)`,
   `[Frame selection and analysis](docs/guides/analysis-modes.md)`,
   `[Audio alignment](docs/guides/audio-alignment.md)`,
   `[VSView alignment review](docs/guides/vsview-review.md)`,
   `[HDR and tonemapping](docs/guides/hdr-tonemapping.md)`,
   `[Reports and overlays](docs/guides/reports-and-overlays.md)`,
   `[Troubleshooting](docs/guides/troubleshooting.md)`,
   `[Commands](docs/reference/commands.md)`,
   `[Configuration](docs/reference/configuration.md)`.
6. Keep "Project status" (mechanical corrections apply to its link text) and keep
   "License" verbatim.

Must not appear: `overlay` as a viewer mode name, `route-comparison`,
`configuration-recipes`, "serious".

## `INSTALL-WINDOWS.md` — keep

No change. It already points to the Windows guide and states the PowerShell and
fresh-folder rules.

## `docs/getting-started/index.md` — rewrite (absorbs `route-comparison.md`)

```text
# Choose an installation
## Which route fits
## What each route includes
## Who owns the runtime
## After installation
```

Sources: current `docs/getting-started/index.md`, current
`docs/getting-started/route-comparison.md`, `docs/docker-environments.md:47-53`.

- **Intro (before the first H2):** two sentences: Frame Compare has one CLI and three
  ways to supply its Python and media runtime; choose by operating system and by how
  much of the media runtime you want to manage. Then the route-card block from the
  [visual specification](visual-spec.md#route-cards), verbatim.
- **Which route fits:** the "Situation | Recommended route" table from current lines
  54–62, unchanged except the Linux NVIDIA/X11 row, which becomes
  "Linux user who needs NVIDIA acceleration or an X11 desktop | Docker, then the
  matching `[Docker profile](docker-profiles.md)`", and the contributor row, whose
  route cell becomes the link
  `[Contributor environment](https://github.com/TJZine/frame-compare/blob/main/CONTRIBUTING.md)`
  (the GitHub URL, as in the site navigation; allowed by the style guide's link rules).
- **What each route includes:** this table, exactly:

  | Capability | Windows portable | Docker | Native source |
  | --- | --- | --- | --- |
  | Discovery, probing, frame selection, and alignment | Yes | Yes | Yes, with the required runtime |
  | SDR screenshots and offline reports | Yes | Yes | Yes, with the required runtime |
  | HDR tonemapping | Host Vulkan driver | Software Vulkan | Host Vulkan driver |
  | VSView alignment panel | Included | Not included | Optional `vsview` extra |
  | Opening the report and slow.pics URL automatically | Interactive desktop session | No; use the host helper | Interactive desktop session |
  | Signed code-only updates and rollback | Yes | No | No |
  | History and caches that persist | Yes | Yes, through the host `generated/` mount | Yes |

  Follow it with one sentence: browser and clipboard actions need an interactive
  desktop session; headless, SSH, service, and non-TTY sessions should not rely on
  them (current route-comparison lines 34–35).
- **Who owns the runtime:** this table, exactly:

  | Route | Runtime owner | Setup effort | Support |
  | --- | --- | --- | --- |
  | Windows portable release | The bundle | Lowest | Recommended on Windows |
  | Windows portable source build | Build scripts that assemble pinned inputs | Medium to high | Packaging fallback |
  | Docker | The image | Low to medium | Recommended headless route on macOS and Linux |
  | Native source with `uv` | Locked Python environment plus your media stack | High | Advanced |
  | Native source with pip | Your Python and media stack | Highest | Advanced integration |

  Then one paragraph from route-comparison lines 19–20 ("Reproducible" does not mean
  identical pixels across operating systems or GPU drivers; use the same route and
  runtime when bit-for-bit output matters), and one sentence linking
  `[Supported media runtime](../supported-media-runtime.md)` as the home of component
  versions.
- **After installation:** keep current lines 69–79 and the "Publishing remains off by
  default" note (retitle it "Publishing stays off").

Delete: every `fc-card*` class, the route-comparison link, the Docker NVIDIA and X11
support rows (now in `docker-profiles.md`).

## `docs/getting-started/route-comparison.md` — delete

Every inbound link moves to `getting-started/index.md` (anchor
`#what-each-route-includes` where the link was about capabilities). Known inbound
links: `README.md`, `docs/index.md` (replaced by U2), the current
`getting-started/index.md`. Run `rg -n "route-comparison" README.md docs --glob '!docs/plans/**' --glob '!docs/reviews/**' --glob '!docs/prompts/**'`;
it must return nothing.

## `docs/windows-portable.md` — edit

```text
# Windows portable
## Install from a published release
## Build the portable bundle from a clone
## Workspace and generated data
## First comparison
## VSView alignment review
## Inspect previous runs
## Update behavior
## Backup and rollback
## Uninstall
## Bundle provenance and licenses
## Troubleshooting
```

1. **Intro (lines 3–12):** keep, but write "VSView with its PySide6 backend" instead of
   "VSView 0.12.0 with its PySide6 backend", and in lines 8–12 write "the base `vsview`
   package" instead of "the base `vsview==0.12.0` package".
2. **Install from a published release:** keep lines 16–65 verbatim (guard test).
   Delete lines 67–70 ("The first native-panel bundle transition…"). Keep lines 72–78.
   Replace the figure (lines 80–83) with the `fc-figure` markup for
   `windows-portable-install.png` using the alt text and caption from the
   [capture specification](capture-spec.md#asset-table), `src="images/windows-portable-install.png"`,
   and `width`/`height` equal to the current file's 1200 × 165 (U10 updates them if the
   recapture differs).
3. **Build the portable bundle from a clone:** verbatim (guard test).
4. **Workspace and generated data:** rename from "Workspace and persistent generated
   data"; keep lines 117–139.
5. **First comparison:** keep lines 143–159.
6. **VSView alignment review:** replaces "Native VSView alignment review" (lines
   161–205). Content, in order:
   - The bundle includes VSView, PySide6, and the packaged
     `frame-compare-alignment-review` panel entry point in one self-contained Python
     environment; Frame Compare launches VSView from that same environment.
   - A PATH-only VSView executable or a separate Python installation is not supported.
   - Turn review on with `audio_alignment.use_vsview = true`, or require it for one run
     with `--force-interactive-alignment`.
   - One sentence linking `[VSView alignment review](guides/vsview-review.md)` for the
     workflow, the saved result, and troubleshooting.
   Required literal strings (guard test): `frame-compare-alignment-review`,
   `self-contained Python`, `PATH-only VSView executable`, `](guides/vsview-review.md)`.
7. **Inspect previous runs:** keep.
8. **Update behavior:** keep lines 219–243 and 251–261. Delete lines 244–249 (the
   "Maintainer update builds…" paragraph moves to the runbook, unit U8). Keep these
   strings verbatim: ``bundle_info.schema_version` 3``, `pre-native-panel schema-2
   bundles`, `fresh, empty folder`, `Overlaying a full ZIP onto an existing bundle
   root is unsupported`, `AppData fallback configuration and external user data are
   preserved`.
9. **Backup and rollback, Uninstall, Bundle provenance and licenses:** keep (guard:
   `Identity-less legacy backups cannot be restored or migrated`).
10. **Troubleshooting:** keep the table, but replace rows at lines 310–313 (panel
    missing, inactive, closes before saving, result rejected) with one row:
    "The alignment panel is missing, stays inactive, or rejects a result | See
    `[VSView alignment review](guides/vsview-review.md#troubleshooting)`".
11. **Delete** the "Physical Windows handoff" section (lines 318–351); U8 moves it.

Must not appear: `Physical Windows handoff`, `0.12.0`, `screenshots_dir`,
`use_run_folders`, `output_dir`, `--source-ref`, `Keep current offset`,
`fc-doc-figure`.

## `docs/getting-started/docker.md` — edit

```text
# Docker
## Run your first comparison
## Where results go
## The index warning
## Next steps
```

- **Intro:** exactly this paragraph: "Docker is the recommended reproducible,
  headless route for macOS and Linux. On macOS Docker Desktop, HDR tonemapping uses
  the CPU-backed software-Vulkan path and needs no GPU passthrough. Supported
  extensions are `.mkv`, `.mp4`, `.avi`, `.m2ts`, and `.ts` (case-insensitive)."
- **Run your first comparison:** first, exactly: "Run the following commands from a
  cloned repository. Copy at least two supported video files into
  `comparison_videos/` before the wizard." Then the UID/GID paragraph (lines 10–11),
  and the command block (lines 13–23) verbatim. Then lines 25–30 (wizard writes only
  after confirmation; mounts; first-use upload off).
- **Where results go:** lines 32–43 (run folders under `generated/`, host helper
  command block verbatim, manual path translation, custom paths need a mount). Add one
  sentence: output and wizard suggestions show container paths such as `/workspace`;
  run the commands above from the host instead.
- **The index warning:** new. Content points:
  1. Every comparison run (not a dry run) prints, once per source each time sources
     load:
     `Loading /workspace/comparison_videos/<file> without an L-SMASH index cache after index construction failed`
     (source: `src/frame_compare/vs/source.py:210`, observed in the 2026-10-08 Docker
     run).
  2. Cause: the run service mounts media read-only, and Frame Compare keeps its
     L-SMASH-Works index beside the media
     (`[Output layout](../reference/output-layout.md)`).
  3. Effect: each run rebuilds the index in memory, which costs indexing time on
     every run. Frame selection, alignment, and rendering are unaffected.
  4. The message is expected on this route and needs no action.
- **Next steps:** links to `[Docker profiles](docker-profiles.md)` for NVIDIA and X11
  and the full service list, and to
  `[Your first comparison](../guides/first-comparison.md)`.

Must not appear: `Advanced Docker Environments`.

## `docs/getting-started/docker-profiles.md` — new (moves `docs/docker-environments.md`)

Move the file with a plain `mv docs/docker-environments.md docs/getting-started/docker-profiles.md` (no Git command; the orchestrator stages the rename), then
edit.

```text
# Docker profiles
## Compose services
## Capability by host
## NVIDIA GPU profile
## Linux X11 GUI profile
## Host open helper
```

1. Replace the H1 and the quote block (lines 1–9) with `# Docker profiles` and one
   sentence: the default Docker route is headless and uses software Vulkan; this page
   covers the Compose services, the optional NVIDIA and X11 profiles, and the host
   helper; basic use is on `[Docker](docker.md)`.
2. Delete "Docker Path Overview" (lines 11–27).
3. **Compose services:** table from lines 31–36 with a new first column "Audience":
   `frame-compare-wizard` and `frame-compare-run` are "User"; `frame-compare` and
   `frame-compare-test` are "Contributor". Replace lines 38–41 with: "Use the wizard and
   run services together so configuration and output paths match. Both run as
   `FRAME_COMPARE_HOST_UID` and `FRAME_COMPARE_HOST_GID` so files they create belong to
   you; the wizard is the only user service that can write configuration."
4. **Capability by host:** the table from lines 47–53 with its columns renamed
   "Environment | Supported | Not supported by default | Notes". In the X11 row's notes,
   delete the sentence "The R81 dependency refresh has Linux-container offscreen proof
   on macOS Docker Desktop." and write "VSView" for "VSView 0.12.0". In the Windows
   portable row, change the link target `windows-portable.md` to `../windows-portable.md`
   (the page now lives in `getting-started/`). Keep lines 55–58. Directly after them,
   add one new paragraph carrying the two support rows from the current
   route-comparison lines 14–15: the NVIDIA profile is experimental until proved on the
   host; the X11 wrapper and a visible desktop are unverified.
5. **NVIDIA GPU profile:** keep lines 64–88.
6. **Linux X11 GUI profile:** keep lines 94–151, but replace lines 118–125 with: "The
   verifier covers the `frame-compare-alignment-review` entry point, offscreen panel
   construction, generated output metadata, the atomic sidecar round trip, and
   malformed-result rejection. An offscreen pass does not prove visible desktop
   behavior; the X11 host wrapper and a visible launch remain unverified until a
   compatible Linux/X11 host runs them. The host wrapper needs Linux with X11 and does
   not run on macOS Docker Desktop."
   Rename its H3s: "X11 Contract" → "X11 contract", "Proof Command" → "Proof command",
   "Manual GUI Launch" → "Manual GUI launch".
7. **Host open helper:** keep lines 157–188.
8. Remove every `---` horizontal rule.
9. Any other relative link in the moved text gains a `../` prefix when its target is
   outside `docs/getting-started/`; links to `docker.md` stay as they are.

Inbound links to update (any page that links `docker-environments.md`): run
`rg -n "docker-environments" README.md docs --glob '!docs/plans/**' --glob '!docs/reviews/**' --glob '!docs/prompts/**'`
after all units; it must return nothing. Known: `docs/getting-started/docker.md`,
`docs/guides/troubleshooting.md`, `docs/getting-started/route-comparison.md`
(deleted).

Must not appear: `plans/`, `Windows 10 handoff`, `README route`.

## `docs/getting-started/native.md` — edit

Outline unchanged (`# Native source`, `## Install with uv`, `## Install with pip`)
plus a new `## Check the runtime` after "Install with pip".

1. The H1 stays exactly `# Native source`: product code links to the
   `#native-source` anchor (`src/frame_compare/orchestration/doctor_checks.py:58`) and
   to the page itself (`src/frame_compare/vsview/adapter.py:120,145`).
2. Keep the prerequisite list with its versions (the one guide exempt from the
   no-versions rule) and lines 14–16.
3. Move lines 18–25 (reference stack, `doctor --json` and a fixture smoke test after
   runtime changes, clear caches after replacing native binaries) into the new
   "Check the runtime" section, verbatim.
4. Delete lines 50–53 (upgrading from the R79 stack).
5. Keep "Install with uv" and "Install with pip" otherwise.

## `docs/guides/first-comparison.md` — edit

Outline unchanged.

1. **Before you begin:** replace the example tree with
   ```text
   comparison_videos/
   ├── pq10-reference.ts
   └── hlg10-comparison.ts
   ```
   and the lead-in with "For a publication-safe example matching the figures below,
   use two sources such as:". Keep the extensions sentence.
2. **Run the four stages:** keep verbatim.
3. **2. Doctor:** delete the duplicated paragraph at lines 84–85.
4. **3. Dry run:** replace the figure with `terminal-dry-run.svg` in `fc-figure`
   markup, using the capture specification's alt text and caption, with no `width` or
   `height` attribute.
5. **4. Run:** replace the figure with `terminal-run-complete.svg` likewise.
6. **Repeat comparisons:** keep; reflow only the paragraph at base lines 151–159 to 88
   columns without changing a word.
7. **Find the result:** replace the tree with:
   ```text
   generated/
   ├── cache/
   ├── clip_probe.toml
   └── <run-name>/
       ├── report.html
       ├── screenshots/
       ├── alignment_diagnostics/
       ├── generated/
       ├── run_info.toml
       └── run_result.toml
   ```
   and add one sentence linking `[Output layout](../reference/output-layout.md)` for
   what each item holds. `alignment_diagnostics/` exists only when audio alignment
   ran.
8. **Confirm the comparison is trustworthy:** keep. In "Continue with", add
   `[VSView alignment review](vsview-review.md)` after the audio alignment link.

Must not appear: `first-run-dry-run.png`, `first-run-complete.png`, `fc-doc-figure`,
`hlg10-encode`, `pq10-encode`.
