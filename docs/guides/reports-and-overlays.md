# Reports and overlays

Frame Compare generates a static HTML report that works offline and needs no server.
By default, the report references screenshots with relative paths; set
`report.embed_images = true` when you need a single HTML file with the images inlined.
Each report is the canonical `report.html` at the root of its reserved generated-data
run folder, next to `screenshots/`. Keeping that folder together preserves offline
viewing when it is moved or copied to another generated-data root.

The viewer supports Single/overlay, slider, diff, pair blink, and grid views; frame
and category navigation; pan and zoom; fit controls; a filmstrip; an inspector; and
browser-local review notes. Viewer choices such as the current frame, view mode,
clip selection, viewport, reveal, and pair alignment persist locally for that report.
Those preferences do not modify the report or run directory.

`report.auto_open = true` is the default for an interactive local run. Auto-open is
suppressed for JSON, quiet, and non-TTY output, and a Docker container cannot open
the host browser. Use the [Docker host helper](../getting-started/docker.md) there.
For exact opening precedence and edge cases, see the
[report auto-open contract](../current-cli-contract.md#report-auto-open-ownership).

## Screenshot overlays

Choose a baked screenshot overlay with the `--overlay` run option or the
`screenshots.overlay_mode` configuration value:

- `none`
- `minimal`
- `standard` (default)
- `diagnostic`

Overlay text is part of the rendered screenshot, while report viewer controls are
browser presentation. Font rendering uses system/default fonts, so its appearance can
vary by operating system. The ordinary report is not a blind-comparison artifact:
source identity can remain in screenshot overlays, filenames, and report metadata.

The [CLI/configuration contract](../current-cli-contract.md#config-only-screenshot-surface)
is authoritative for screenshot settings, and the
[report architecture](../current-architecture.md#report-viewer) describes the viewer's
current behavior in detail.
