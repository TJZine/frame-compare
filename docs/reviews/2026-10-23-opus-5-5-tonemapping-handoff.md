> **Portable handoff correction:** The implementation, report, handoff and review
> evidence are committed together. Start with
> [the evidence bundle](../../review-evidence/2026-10-23-tonemapping/README.md).
> Compare the base commit with HEAD; do not rely on `git diff` without revisions.

# Independent second opinion: Frame Compare highlight preservation

This is a handoff for Opus 5.5, not a review already performed by that model.
Please review read-only first and challenge the conclusions rather than assuming
the measurements imply acceptance. Do not publish, change defaults, or implement
further color changes without a separate request.

## Request to the reviewer

Assess whether the new opt-in `highlight_preserve` preset is correctly wired and
appropriately scoped; whether the evidence supports its claims; and whether
softclip deserves a public opt-in, more investigation, or rejection. Give findings
in severity order with exact file/line or raw evidence pointers. Separate confirmed
bugs, likely image-quality tradeoffs, unsupported claims, and taste. State what you
actually inspected or ran. End with your recommendation and the smallest additional
experiment that could change it. A clean review is acceptable; do not invent issues.

## Checkout and instructions

Repository: `C:/Software/video/frame-compare`.
Base HEAD: `f1d3b9bf4c3406e3d0cddbfbbc536e0ac8a9279e`.
Implementation is now committed with this handoff. Compare base HEAD above with
current HEAD using `git diff f1d3b9bf4c3406e3d0cddbfbbc536e0ac8a9279e..HEAD`.
The exact scoped implementation patch is also committed in
`review-evidence/2026-10-23-tonemapping/highlight-implementation/implementation.diff`.
An empty working-tree diff no longer means the implementation is absent. Read `AGENTS.md` and
`.agents/project.md`. Preserve the five unrelated 2026-10-18 VSView plan files.
A portable evidence bundle is committed at
`review-evidence/2026-10-23-tonemapping/`. Read its README, manifest, and index.html.
Use its mirrored paths wherever the generated paths below do not exist. The
bundle explicitly identifies omitted source-sized real-media arrays/images;
request those only if needed for full-resolution remeasurement.

## Read these in order

1. `docs/reviews/2026-10-23-tonemapping-highlight-research.md`: updated research,
   current/historical provenance, experiments, source citations, recommendations.
2. `git diff f1d3b9bf..HEAD -- src/frame_compare/config/schema_enums.py
   src/frame_compare/vs/tonemap_presets.py src/frame_compare/render/prepare.py`,
   or the saved implementation.diff in the portable bundle.
3. `tests/config/test_color_roundtrip.py`, `tests/vs/test_tonemap.py`, plus the
   applicable docs diff in the HDR guide, configuration/commands references and
   current CLI/architecture contracts.
4. `generated/verification/2026-10-23/highlight-study/real-media/REPORT.md`,
   `comparison.html`, actual images, per-case results and same-evaluation arrays.
5. `generated/verification/2026-10-23/highlight-study/controller/`:
   independent repeatability/negative-control receipt and synthetic summary.
6. `generated/verification/2026-10-23/highlight-softclip-expanded/`: new difficult
   scene study, its selection decisions, visuals and raw outputs.
7. `generated/verification/2026-10-23/highlight-implementation/`: implementation
   tests, installed-console receipt and final evidence index.

## Implementation intent

`--tm-preset highlight_preserve` / `[color] preset = "highlight_preserve"` selects
reference settings with knee 1.0 instead of .5. Reference stays default;
`highlight_guard` remains spline/180. Softclip is not bundled. Explicit color
fields retain existing precedence. A curve override to another algorithm resets
the generic native parameter to .5 instead of reinterpreting the tuned BT.2390
knee as spline/Reinhard contrast. Applied settings/report identity retain preset
and knee. No new public arbitrary gamut or peak controls are added.

## Questions to resolve independently

- Is the preset contract truthful under local explicit overrides, environment
  settings, persistence, fast mode, alignment preview and final still rendering?
- Is resetting the generic parameter on an algorithm switch the right boundary?
  Could it change an existing supported preset combination or hide a supplied value?
- Does the new preset actually differ from reference only in knee and identity?
- Are apparent highlight improvements meaningful separation, or merely darker/
  flatter output? Examine native16, float and RGB8 distinctions and local ROIs.
- Are single-channel saturation, out-of-gamut behavior and neutral white being
  incorrectly combined? Does softclip introduce hue/saturation/texture penalties?
- Are peak-source assumptions warranted? Supplied source_max is not the observed
  effective peak. Fresh runs did not expose numeric effective peak traces.
- Do synthetic inputs and metadata isolate the claimed cause? Spatial recovery
  and dithering can affect ramp monotonicity; invalid extended RGB is not proof
  of ordinary decoder loss. HLG remains separately untested.
- Are sample selection, metric thresholds and inactive controls reported honestly?
  The sampled real-media metric is every fourth pixel, starting at row 250.
- Are fallback, source clipping and final quantization being correctly distinguished?
- Which conclusions generalize beyond the exact Windows/NVIDIA/libplacebo runtime?

## Evidence cautions

Initial study: 28 delegate real-media processes, three controller repeats and 17
controller synthetic processes succeeded. These are diagnostic cases, not 48
independent perceptual approvals. Reference porch white area was 7.3305%, knee1
0.8216%; the synthetic ramp still had 31.4529% white with knee1. Softclip greatly
reduced Spider-Verse single-channel endpoints but left neutral white unchanged.
Disabling contrast recovery could reduce native endpoints while worsening final8
whites or smoothing detail. The full report retains earlier fixes already tried:
range/primaries, double expansion, sRGB conversion, independent still state, curves,
peak/metadata experiments and removal of the old postprocessing contrast clamp.

Do not treat PNG endpoint percentages as physical nits, mean gamma RGB as luminance,
zero white pixels as fidelity, or historical pre-correction figures as fresh results.
No calibrated display ground truth is available. Sources are existing movie excerpts;
reference SDR releases can differ creatively and are not a universal oracle.

## Completion evidence

The final status and expanded-study findings are recorded in the implementation
addendum at the start of the research report and in the implementation evidence
index. Follow those exact receipts rather than assuming all platform gates passed.
If testing locally, serialize native GPU work, use bounded fresh subprocesses,
copy indexes into owned external scratch, preserve originals and record cleanup.

## Final observed gate status

Focused checks: 101 passed. Full suite: 4,197 passed, 78 skipped, 4 failed.
Two failures are portable installer user-PATH helper calls; one is a synthetic
portable launcher child exit; the fourth is a collection-warning test reproduced
on isolated base source with all three changed production files restored from
HEAD. No unrelated fixes were made. See `highlight-implementation/verification.json`,
`full-suite.log`, `full-suite.xml`, and `baseline-lifecycle.json`. Docker/bash and
Zensical were unavailable, so their gates are not passes.

Expanded softclip: 12 successful child cases, one bounded timeout, two successful
controller repeats. Controller verified exact image parity, positive/negative
assertions and all 137 manifest entries. Four active mappings across two titles
include only two clear colored-endpoint stress successes; the live-action pairs
show color changes without full-picture endpoint recovery. Softclip remains
experimental. There is no Opus result yet: this document is the review request.
