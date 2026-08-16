# HDR and tonemapping

Frame Compare can normalize HDR sources into SDR screenshots so sources with different
HDR metadata or delivery formats can be reviewed in the same browser report. The
selected VapourSynth and vs-placebo path performs tonemapping when the effective source
properties indicate it is required.

## What the pipeline does

1. Probe container metadata and source-frame properties.
2. Preserve explicit frame evidence and fill only missing or unspecified color facts.
3. Decide whether the frame requires HDR-to-SDR conversion.
4. Convert to the working color representation without unnecessary 8-bit reduction.
5. Apply the configured vs-placebo tonemapping preset and target luminance.
6. Render the screenshot and selected overlay.

Ambiguous transfer or primaries metadata remains unknown at the conservative FFmpeg
fallback boundary rather than being treated as ordinary SDR.

## Runtime requirements

HDR tonemapping requires:

- VapourSynth;
- the supported vs-placebo plugin;
- a compatible Vulkan implementation and driver;
- source loading through the selected supported runtime.

The Windows portable bundle includes the selected application and plugin stack but still
uses the host Vulkan-capable graphics environment. The default Docker route uses the
canonical software-Vulkan path. Native installations own their host setup.

Run `frame-compare doctor` after installation and after any graphics-driver, Vulkan,
VapourSynth, source-plugin, or vs-placebo change.

## Configure the result

The wizard is the safest way to select a tonemapping preset and target luminance. For a
manual configuration, use the fields documented in the
[color and tonemapping contract](../current-cli-contract.md#config-only-color-surface).

A representative shape is:

```toml
[color]
enable_tonemap = true
target_nits = 203
```

Use one consistent target and preset for every source in a comparison unless the goal is
specifically to study different conversions.

## HDR versus SDR sources

Comparing an HDR source with an SDR source is valid only after deciding what question the
comparison should answer:

- **Encode fidelity after a common SDR presentation transform** — tonemap the HDR source
  and review both as SDR screenshots.
- **Native HDR mastering differences** — static SDR screenshots are insufficient; use
  HDR-aware playback and measurement outside this report workflow.
- **Metadata correctness** — use diagnostic overlays and recorded properties, but do not
  infer perceptual equivalence from metadata alone.

Frame Compare’s report is an SDR browser review artifact unless a future documented
output contract says otherwise.

## Dolby Vision considerations

Dolby Vision sources can expose useful RPU-derived properties through the selected media
runtime, but profile, fallback-layer, decoder, and metadata availability vary. Treat
missing or partial dynamic metadata as insufficient evidence rather than silently
inventing values.

For publication-bound comparisons:

- record whether a compatible HDR10/base layer was used;
- inspect several dark and bright scenes;
- check for raised blacks, clipped highlights, hue shifts, and range mistakes;
- validate the result on the physical Windows/GPU environment intended for release.

## Overlays and measurements

`diagnostic` overlays can include available mastering metadata, MaxCLL/MaxFALL, color
range, Dolby Vision facts, and selection context. The values depend on what the source
and selected runtime can prove.

Selection scores are useful for explaining why a frame was chosen. They are not a
replacement for calibrated luminance measurement, VMAF, or a perceptual review.

## Common problems

| Symptom | What to check |
| --- | --- |
| Tonemapping plugin unavailable | Run `doctor`; verify the selected vs-placebo plugin and runtime profile |
| Vulkan initialization fails | Update or repair the host Vulkan driver/runtime; use the supported software-Vulkan Docker path where appropriate |
| HDR frame is rendered as SDR without conversion | Inspect transfer, primaries, matrix, and range evidence; do not force a conclusion from partial metadata |
| Output looks washed out or crushed | Check full/limited range interpretation, source metadata, and target/preset choices |
| Different sources show inconsistent hue or brightness | Confirm both pass through the intended common transform and that one source is not being double-tonemapped |
| Docker output differs from Windows | Remember that the routes use different Vulkan implementations and may not be pixel-identical |

The authoritative component matrix and profile policy are in
[Supported Media Runtime](../supported-media-runtime.md).
