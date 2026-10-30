---
search:
  exclude: true
---

# Highlight detail experiment

Prepared 24 October 2026. Experiment analysis and independent review completed. Branch `feat/hdr-highlight-detail`; source and experiment base `06015be59350c186efcfab2293fdd880adae5f1e`. The reference knee 1.0 default has landed. No product source, configuration or dependencies changed for this experiment.

## Finding and recommendation

Outcome (c): adding a highlight-detail mode remains inconclusive. The source contains measurable variation and some recognizable edges; the six bright frames fail the mostly-source-flat stop condition. V17 is the strongest eligible numerical candidate. Its equal-frame mean flattened fraction is 18.894826%, versus 39.290359% for V01, with mean retention 0.429495 versus 0.289828. Its maximum absolute midtone shift across nine cases is 5.155792 codes, maximum absolute measured shadow shift 0.294846 codes, and maximum edge overshoot 0.000810%.

Native-resolution inspection shows modest preservation of grain, thin wires, ridges and existing blurred edges. The porch sky remains nearly featureless at larger scales. No newly resolved cloud structure was identified in the inspected source or output windows. These observations do not establish a useful perceptual gain large enough to justify a new product mode. A blanket source-limited verdict is also unsupported: source standard deviation includes grain, and recognizable structure exists in some bright regions.

The smallest next experiment is a blinded V01/V17 comparison using the saved 1:1 crops of Kill Bill Vol. 2 frames 12382 and 14943, including the fixed supplementary upper-center porch window and the frozen face windows. Use a controlled sRGB SDR display, fixed brightness/viewing distance, randomized labels and repeated choices. Ask separately about recognizable structure, grain preference, facial rendition and halos. A correctly managed PQ source view can supply the HDR reference; the raw PQ-code diagnostics here cannot. Retain the two saved colored controls for a color-preference check. This next experiment is UNRUN and needs no additional candidate sweep or native rerender.

The exact candidate for that comparison is V17: BT.2390, `tone_mapping_param=2.0`, `contrast_recovery=0.6`, target 100 nits, gamma lift off, `metadata=0`, `use_dovi=True`, gamut mapping 1, quality still path and independent per-frame mapping. All other settings are listed below. No product change is recommended at this stage. If a later perceptual check supports an opt-in, existing BT.2390 and recovery support suffice internally; a public way to select knee 2.0, such as an explicit preset, would be needed because the current public color model does not expose knee offset. No new `ToneCurve` value is needed for V17.

## Provenance and runtime

This extends the investigation recorded in `docs/reviews/2026-10-23-tonemapping-highlight-research.md` without overwriting it. Historical endpoint percentages used different sampling and must not be compared directly with the full-resolution percentages below. The exact historical Kill Bill receipt path was reused; historical receipts contain decoded-input and RGB8 hashes but no whole-file digest. Fresh whole-file hashes are retained locally. Both V00 and V01 porch input/output hashes exactly match the archived receipts, including fresh parity after the approved harness revision. Excerpt control whole-file hashes match their historical receipts.

Windows 10 build 19045; Python 3.13.7, MSC 1944, 64-bit; VapourSynth R81/API R4.3; stock vs-placebo 2.0.4/libplacebo 7.371; NVIDIA GeForce RTX 5080, driver 621.01. Placebo SHA256 `b0a0689946e03f6f7467b798fba4678018bb28ba6b1caecdded8d08945049310`; LSMASHSource SHA256 `98ce1bc67218bd09bf84f45d7fc726bbf0972a90dd4c29d68f0797dd1606e7ea`. Both match the archive. Runtime identity is retained in `generated/verification/2026-10-24/highlight-detail/runtime.json`.

Source manifests, full hashes and local decode identity are retained in `generated/verification/2026-10-24/highlight-detail/sources.json`. Media filenames and paths are intentionally excluded from this document. There is one admitted HDR Kill Bill encode. The additional discovered encode is untagged 8-bit H264, with transfer/primaries/matrix unspecified and product `detect_hdr=False` at the sampled frames. Its intended transfer remains unknown. Its requested V00/V01/final-top-three HDR comparisons are UNRUN/inapplicable; forcing PQ interpretation would invalidate the source metrics and bypass product HDR gating. Evidence is retained in `generated/verification/2026-10-24/highlight-detail/alternate-encode-metadata/`. No HDR10+ evidence was found in sampled frame properties or inspected stream metadata; this is not an exhaustive bitstream claim. The conditional ST2094-40 experiment was not admitted.

The active revision2 probe SHA256 is `6bfe2a90baf4cc33f1c76ce1222e4f859cc2408866831b17cbee7adffd15d9fb`; metrics SHA256 `751791a10e9953dbbb81f4f5a9f478325d1c148588e51ff47915aa926fd4cb27`; variants SHA256 `69000209dd0da641339e3ed4fee8d94db09346f1bfd37d7e9032691e1e7ffd05`. Current authority is `generated/verification/2026-10-24/highlight-detail/harness-manifest.json`, `generated/verification/2026-10-24/highlight-detail/s0-revision-summary.json` and `generated/verification/2026-10-24/highlight-detail/controller-decisions.md`. Earlier blocked V14/V15 wording in S0 history was superseded by explicit human approval for probe-only existing `TonemapSettings(target_nits=203/250,gamma_lift=True)`. The unchanged product path then applies its actual gamma 0.9 postprocessing and matching export white reference. Native overrides remain at the Tonemap wrapper.

## Settings and variants

Common settings: enabled reference preset, quality, target 100 nits, BT.2390 knee 1.0, source peak unset, dynamic peak detection on, destination black 0.18 nits, smoothing period 45, scene thresholds 0.8/2.4, percentile 99.995, gamut mapping 1, metadata 0, Dolby Vision use enabled, contrast recovery 0.3, gamma lift off. Destination is BT.709 (`dst_csp=0`, `dst_prim=3`), exported to sRGB RGB8 through the product still path with independent per-frame native state. Source metadata and the exact kwargs actually passed are retained per case. Probe wrapper settings can differ from the product's requested/applied diagnostic fields; actual call receipts are the mapping authority for this experiment.

| Variant | Explicit change from common settings |
| --- | --- |
| V00 | BT.2390 knee 0.5 (old default) |
| V01 | BT.2390 knee 1.0 (delta baseline) |
| V02 | BT.2390 knee 1.5 |
| V03 | BT.2390 knee 2.0 |
| V04 | Contrast recovery 0.6 |
| V05 | Contrast recovery 1.0 |
| V06 | Contrast recovery 1.5 (probe-only value outside public config limit) |
| V07 | bt2446a; omit tone_mapping_param |
| V08 | st2094-10; omit tone_mapping_param; metadata 0 and use_dovi enabled retained |
| V09 | hable; omit tone_mapping_param |
| V10 | mobius; omit tone_mapping_param |
| V11 | spline at 100 nits, param 0.5 |
| V12 | spline at 100 nits, param 0.3 |
| V13 | spline at 100 nits, param 0.2 |
| V14 | BT.2390 knee 1.0, target 203 nits, gamma lift on; approved probe settings exception |
| V15 | BT.2390 knee 1.0, target 250 nits, gamma lift on; approved probe settings exception |
| V16 | Selected base V04 + recovery 0.6 is already V04; nine duplicate skips |
| V17 | Selected base V03 + recovery 0.6: BT.2390 knee 2.0, target 100 nits, gamma lift off |

## Measurement method and fixed decisions

Pre-plugin RGB48 is normalized by 65535. Apply the ST2084 PQ EOTF to each channel to obtain nits; linear luminance is `Y=0.2627R+0.6780G+0.0593B`. Re-encode Y with inverse PQ and multiply by 1023 for source texture. The bright ROI is `Y >= max(80 nits, 0.5 * percentile99.9(Y))`. Masks depend only on the source.

Use non-overlapping 8×8 blocks from origin (0,0), entirely inside the ROI; incomplete picture-edge blocks are omitted. Source texture is population std of 10-bit PQ luminance codes. Output texture is population std of final RGB8 luma `0.2126R+0.7152G+0.0722B`, evaluated at full resolution. Source-flat percentage counts source std <1. Flattened percentage counts blocks with source std >=2 and output std <1, divided by all entirely-ROI blocks, including source-flat blocks. Retention is the median output-std/source-std ratio; its mixed code units permit cross-variant comparison only.

Midtone and shadow shifts are mean output luma minus V01 on source intervals [5,50] and [0.5,5] nits, endpoints inclusive. Edge overshoot is the percentage in an eight-pixel outside ROI band with luma more than eight codes above V01. The declared band convention is Chebyshev distance (17×17 square dilation), clipped to the picture; it is a crude brightening indicator and cannot by itself diagnose a halo. Secondary metrics count full-picture all-channel 255, any-channel 255 and all-channel >=250 pixels, each as a percentage. These counts do not determine ranking.

Control color is the mean change versus V01 of per-pixel max-minus-min RGB code over the fixed historical saturated regions. Fractional bounds (x0,y0,x1,y1) are (0.05,0.13,0.40,0.70) for Spider-Verse and (0.11,0.04,0.44,0.90) for The Substance, truncated to integer coordinates at each source size. There is no candidate-dependent saturation mask. This code-spread proxy measures neither hue error nor perceptual color fidelity.

Declared undefined-value conventions: exclude 0/0 blocks from retention; preserve positive-output/zero-source ratios as positive infinity. Empty regions or blocks produce null. Frame 118560 has 66 zero-std ROI blocks; its per-variant undefined/infinite counts are reported below. Its [0.5,5]-nit shadow interval is empty for every variant, producing 17 explicit null shifts. Only that unavailable shadow guard is omitted. No null is converted to zero or a numeric pass. All other measured guards remain active.

Ranking was fixed before candidate results: equal-frame arithmetic mean flattened percentage over the six bright Kill Bill frames, ascending; ties use higher equal-frame mean retention, then lower numeric variant ID. Eligibility requires every measured midtone/shadow shift across all nine cases in [-6,+6] inclusive and every edge overshoot strictly below 1%. Raw rank and eligibility are reported separately. Initial eligible bases were V04, V03, V02; V04 supplied best eligible recovery 0.6. V16 duplicates V04, while V17 combines V03 and recovery 0.6. The final rank below independently includes V17; the earlier compact S1 selection/ranking lists retain the pre-combination order.

## Source diagnosis and G0

S0 scanned every 480th frame of the same HDR source at quarter resolution, using product conversion semantics before PQ analysis. All 412 requested frames completed in 35 bounded decode batches, 582.273 seconds total scan wall time, inside the 30-minute budget. Source RGB code resampling preceded EOTF. Rank by share Y>=100 nits, descending, ties by ascending frame; greedily choose four frames at least 2,000 apart and from 12382/14943. The resulting additional frames are 118560, 10080, 82560 and 76800. Full-resolution source arrays supply the statistics below. The scan ranking has no output-candidate input.

G0: CONTINUE. All six bright source-flat fractions are below 70%; the mostly-flat stop condition is false. This establishes numeric variation including grain. The dark control is reported for context and does not enter G0 or bright-frame ranking.

| Kill Bill Vol. 2 frame | ROI % | Threshold nits | ROI blocks | Source-flat % | Source std p10 / p50 / p90 | Zero-std blocks |
| --- | --- | --- | --- | --- | --- | --- |
| 12382 (porch) | 31.551774 | 123.870999 | 26679 | 0.011245 | 1.991471 / 2.923581 / 4.690107 | 0 |
| 14943 (close-up) | 8.671061 | 144.067194 | 7170 | 0.041841 | 2.158013 / 3.487803 / 5.959371 | 0 |
| 118560 | 37.389974 | 202.982814 | 33730 | 28.218203 | 0.481954 / 1.550332 / 3.737278 | 66 |
| 10080 | 46.214404 | 122.533652 | 42320 | 0.000000 | 2.757431 / 3.673786 / 4.996657 | 0 |
| 82560 | 53.840641 | 123.905729 | 50457 | 7.689716 | 1.125229 / 2.216914 / 3.557101 | 0 |
| 76800 | 53.778630 | 100.759037 | 43182 | 0.000000 | 2.373061 / 3.508254 / 7.648868 | 0 |
| 110257 (dark control) | 7.387500 | 92.325842 | 4645 | 0.000000 | 3.227560 / 4.683959 / 7.450805 | 0 |

Source statistics and scan receipts: `generated/verification/2026-10-24/highlight-detail/s0-summary.json`, `generated/verification/2026-10-24/highlight-detail/scan/selection.json`, `generated/verification/2026-10-24/highlight-detail/scan/invocations.json`. The original S0 summary's blocked-status/count history predates the approved revision and S1; use the cumulative ledger below.

## Final numerical ranking

Raw rank covers measured candidate variants V02–V15 and V17. V00/V01 are separate references. Guard maxima span all nine cases, with only frame 118560's absent shadow interval omitted. Full signed per-frame values follow. V16 references V04 and has no independent raw rank or measured values.

| Raw rank | ID | Mean flattened % | Mean retention | Max abs mid | Max abs shadow | Max edge % | Eligible |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | V13 | 0.443733 | 0.685104 | 39.329760 | 7.873332 | 0.002078 | no |
| 2 | V12 | 0.476047 | 0.680553 | 39.826691 | 8.234303 | 0.002078 | no |
| 3 | V11 | 0.540661 | 0.672504 | 40.839899 | 8.961166 | 0.002078 | no |
| 4 | V09 | 0.880587 | 0.649488 | 30.043258 | 12.005793 | 0.002078 | no |
| 5 | V08 | 1.058446 | 0.656686 | 41.719572 | 13.856989 | 0.002078 | no |
| 6 | V07 | 2.744862 | 0.570112 | 32.664022 | 16.444377 | 63.291877 | no |
| 7 | V15 | 3.662501 | 0.893571 | 60.471602 | 26.547581 | 0.000000 | no |
| 8 | V06 | 5.942706 | 0.687330 | 0.194305 | 1.171310 | 5.378770 | no |
| 9 | V14 | 8.755869 | 0.632210 | 50.138600 | 22.988714 | 0.000000 | no |
| 10 | V05 | 11.994346 | 0.530277 | 0.116981 | 0.685676 | 1.920743 | no |
| 11 | V10 | 13.213116 | 0.421023 | 1.950771 | 6.264508 | 0.000000 | no |
| 12 | V17 | 18.894826 | 0.429495 | 5.155792 | 0.294846 | 0.000810 | yes |
| 13 | V04 | 21.675665 | 0.399350 | 0.049673 | 0.294598 | 0.022370 | yes |
| 14 | V03 | 33.438858 | 0.315231 | 5.106380 | 0.000017 | 0.000000 | yes |
| 15 | V02 | 34.335771 | 0.311122 | 3.701853 | 0.000007 | 0.000000 | yes |
| reference | V01 | 39.290359 | 0.289828 | 0.000000 | 0.000000 | 0.000000 | yes |
| reference | V00 | 62.007117 | 0.182790 | 1.592728 | 0.000000 | 95.238635 | no |

V17 ranks first among eligible candidates (raw rank 12), followed by V04 (13), V03 (14), V02 (15). Its mean flattened fraction is 20.395533 percentage points below V01. The porch drops from 21.634994% to 0.449792%, with retention increasing from 0.424465 to 0.646212. This substantial threshold-crossing change exceeds the visible structural change in the crop inspection.

The numerical winners are rejected under the unchanged guards. Spline V11–V13, Hable V09, ST2094-10 V08 and BT2446a V07 incur large midtone changes; several also fail shadow guards, and V07 reaches 63.291877% edge overshoot in The Substance. V14/V15 reach absolute midtone changes of 50.138600/60.471602 codes despite their low white occupancy. Recovery V05/V06 fails the edge guard (maxima 1.920743%/5.378770%). Mobius V10 fails shadow guards (maximum absolute 6.264508 codes). These remain measured candidates with retained numbers; neither low white counts nor low flattened fractions waive a guard. V00's 95.238635% maximum edge value reflects broad brightening versus V01 and cannot be interpreted as 95% visible halos.

Derived final ranking and full failure lists: `generated/verification/2026-10-24/highlight-detail/s2/ranking.json`. Frozen selection input: `generated/verification/2026-10-24/highlight-detail/combinations.json`.

## Native-resolution inspection

Official crop coordinates are frozen in `generated/verification/2026-10-24/highlight-detail/source-crops.json`: two non-overlapping source-texture windows and one source-selected midtone/face window, each exactly 640×360. The selector used an eight-pixel lattice and source ROI std only. Face windows were fixed from source previews before candidate results; frame 82560 retains the automatic window because no face is present. S1 detail records also contain an earlier automatic midtone coordinate; the authorized frozen source-crops file was used for every sheet here. This coordinate difference does not affect numerical masks or results.

For every one of the nine cases, the main six-variant sheet contains V00, V01, V17, V04, V03, V02. A separate six-variant sheet contains V00, V01, V13, V09, V08, V07 to inspect strong ineligible curves. Each six-column sheet was split by pixel copy into two three-column, 1920×1170 sub-sheets, with 30-pixel labels and no spatial scaling. All 36 sub-sheets were inspected with original-resolution image tools; the assembly script verifies every copied crop pixel. No visual judgment relies on a downscaled sheet.

Nine additional source diagnostic sheets show the same frozen windows by converting RGB48 to eight-bit PQ code values with integer right-shift by eight, with no spatial scaling or local stretch. These diagnostics expose spatial structure but do not represent correctly displayed HDR or sRGB color. One supplementary porch window uses the fixed geometric upper-center rectangle (1600,0)–(2240,360), chosen independently of candidate advantage, with source and V00/V01/V17/V04/V13. It does not change official crop coordinates or metrics. Highest-texture windows can favor edges and grain and do not represent the whole porch sky.

Evidence inventory and image-by-image observations: `generated/verification/2026-10-24/highlight-detail/s2/inspection-inventory.json`, `generated/verification/2026-10-24/highlight-detail/s2/source-diagnostics.json`, `generated/verification/2026-10-24/highlight-detail/s2/inspection-log.json`. Crop pixels remain under `generated/verification/2026-10-24/highlight-detail/s2/` and are excluded from Git.

### Kill Bill Vol. 2, frame 12382 (porch)

Inspected leaders: ROI 1 contains soft dark background shapes against a bright field; ROI 2 is mainly a pale field with fine mottling. V00 is smoother and whiter; V01 shows a little more variation. V17 and V04 increase visible grain and separation around the existing blurred shapes. V03 and V02 are closer to V01. No clearly resolved cloud structure appears. The nose, cheek and lip retain similar shape and local contrast in the eligible leaders; V17 is slightly darker. No conspicuous new rim is visible in these leader crops.

Inspected ineligible challengers: V13, V09, V08 and V07 make bright-field mottling stronger. The face becomes visibly darker, especially under V08. Their numerical gains include an overall rendition change.

Source diagnostic: Raw PQ-code diagnostic shows the same blurred shapes and fine mottling. The supplementary upper-center window is nearly uniform apart from fine grain; candidate changes mainly expose that grain.

### Kill Bill Vol. 2, frame 14943 (close-up)

Inspected leaders: ROI 1 contains a bright folded or ridged surface; ROI 2 includes hair against a bright background. V17 and V04 retain more fine variation and slightly clearer existing ridges than V01; V00 washes out more of the broad pale surface. V03 and V02 give smaller changes. The tight face crop is dark in every version and stays similar among the eligible leaders.

Inspected ineligible challengers: V13, V09, V08 and V07 show stronger shading on the bright ridges and more background grain, with visibly darker facial rendition. V08 deepens the face most clearly.

Source diagnostic: The ridges, hair strands and grain are present in the source diagnostic. This establishes existing structure at those positions without a calibrated HDR appearance comparison.

### Kill Bill Vol. 2, frame 118560

Inspected leaders: Both bright windows show broad pale yellow/green shading with very little recognizable fine structure. V17 and V04 add fine variation, while the field remains smooth at larger scales. The face/lips crop remains strongly grainy; V17 and V03 are somewhat darker than V01. V00 and V01 are especially close in the bright field.

Inspected ineligible challengers: The four challengers visibly darken the pale field and face and expose more mottling. This is a large rendition difference rather than evidence of newly resolved object detail.

Source diagnostic: The source diagnostic is also dominated by broad soft shading and grain. Its 28.22% source-flat blocks and 66 zero-std blocks distinguish it from the other bright frames.

### Kill Bill Vol. 2, frame 10080

Inspected leaders: The bright windows include thin wires and utility poles against an almost white sky. V17 and V04 make the thin wire and background grain easier to see than V01 and V00. V03 and V02 make smaller changes. The face stays close to V01 for the eligible leaders. No clear cloud forms or conspicuous new halo are visible in the inspected windows.

Inspected ineligible challengers: V13, V09, V08 and V07 show much more grain and stronger wire contrast, accompanied by a noticeably darker face; V08 gives the deepest shadows.

Source diagnostic: The source diagnostic contains the wires and poles clearly, with fine sky grain. Thus some structural detail exists, even though the sky itself is visually plain.

### Kill Bill Vol. 2, frame 82560

Inspected leaders: The bright windows are soft cyan/green fields with a dark edge in ROI 1; they do not resolve rice-grain shapes. V17 and V04 make fine mottling more apparent than V01; V00 is smoother. V03 and V02 are closer to V01. The lower blue-gray crop stays heavily grainy in all six; this frozen window contains no face.

Inspected ineligible challengers: The four challengers darken the bright fields and emphasize mottling; the lower crop remains visibly noisy. The texture metric does not establish recovery of recognizable objects here.

Source diagnostic: The source diagnostic already has soft boundaries and fine texture, without sharply resolved bright objects in these windows.

### Kill Bill Vol. 2, frame 76800

Inspected leaders: Both bright windows show blurred dark branch/foliage-like shapes against a pale cyan field. V17 and V04 modestly strengthen their existing edges and fine grain relative to V01 and V00. V03 and V02 change less. The moustache, mouth and skin crop stays close in the eligible versions. No distinct cloud texture or conspicuous new leader halo is visible.

Inspected ineligible challengers: The four challengers make the blurred background and grain more prominent while changing facial brightness. V08 makes the face particularly dark.

Source diagnostic: The source diagnostic contains those blurred shapes and fine grain, so stronger output texture has a source counterpart but limited spatial definition.

### Kill Bill Vol. 2, frame 110257 (dark control)

Inspected leaders: The selected windows are brightly lit cloth and faces inside the dark-control frame. V17 and V04 slightly increase cloth and skin variation while keeping the warm rendition close to V01; V00 is slightly more washed out. V03 and V02 are subtle changes. These crops do not establish acceptance of the whole dark background.

Inspected ineligible challengers: V13, V09, V08 and V07 darken skin and cloth and alter their warm rendition. This visible difference accompanies failed numerical guards.

Source diagnostic: The source diagnostic contains cloth folds, skin texture and lip reflections. Its displayed code values have no calibrated brightness authority.

### Spider-Man: Across the Spider-Verse, excerpt 2, frame 72

Inspected leaders: The bright windows show a pale animated figure against magenta lights; linework, spots and the light pattern are already visible in V00 and V01. The four eligible leaders look close, with small pale-figure shading differences. The frozen midtone window shows background, hair-like strokes and a hand rather than a useful facial close-up. No obvious new halo or large magenta shift appears in the leader crops.

Inspected ineligible challengers: V13, V09, V08 and V07 visibly change the pale figure and magenta-light rendition more than the eligible leaders. A chroma mean alone cannot judge hue or artistic fidelity.

Source diagnostic: The source diagnostic contains the figure linework and patterned colored lights.

### The Substance, excerpt 2, frame 72

Inspected leaders: The bright crop contains orange background and a pale fabric edge; the second bright crop and mouth/chin window are soft or motion-blurred. V00, V01 and all four eligible leaders look very close. No recovered fine fabric structure or obvious color penalty is visible.

Inspected ineligible challengers: V13, V09, V08 and V07 lift and change the warm face/background rendition; Hable and BT2446a are especially visibly different. The soft source limits what detail can be judged.

Source diagnostic: The source diagnostic has the same soft boundaries and motion blur. This frame has only 182 entirely-ROI blocks and is a limited highlight-detail control.

Across the four eligible leaders, V17 offers the largest measured retention and the strongest inspected small-scale separation. V04 preserves midtones more closely and gives much of the visible gain. V03 and V02 provide smaller changes without the increased recovery setting. None of these observations establishes calibrated display acceptance, a preferred artistic rendition, temporal stability or a dramatic porch-sky restoration.

## Complete per-frame output results

There are 153 observed rows: 17 variants × nine cases. Each table also accounts for its V16 duplicate skip by reference to V04, yielding 162 planned case slots without fabricated observations. Flat is flattened percentage, Ret is retention, Mid/Shadow are signed luma code deltas versus V01, Edge is overshoot percentage, All255/Any255 are endpoint percentages, Near250 is all-channel >=250 percentage. Values are rounded to six decimals here; decisions used unrounded float64 data. Zero after rounding can represent a small nonzero value. Color control tables include mean_chroma_change in RGB codes. All source statistics and output definitions remain unchanged.

All compact rows and CSV fields were checked against retained per-case detail metrics and receipt input hashes; all 153 output file hashes matched. Seven selected rows were recomputed offline from source RGB48 and final pixels using the unchanged metric implementation: porch V00/V01/V04/V17/V13 and The Substance V04/V17. Every checked metric matched exactly. This is a consistency and selected-recomputation check, not a second independent implementation of every metric. S0 separately retains known numeric fixtures and three scalar source-block checks.

Raw evidence: `generated/verification/2026-10-24/highlight-detail/s1-results.json`, `generated/verification/2026-10-24/highlight-detail/s1-results.csv`, `generated/verification/2026-10-24/highlight-detail/s1-renders/`, `generated/verification/2026-10-24/highlight-detail/s1b-renders/`. Derived recomputation: `generated/verification/2026-10-24/highlight-detail/s2/recomputed.json`.

### Kill Bill Vol. 2, frame 12382 (porch)

| ID | Flat % | Ret | Mid | Shadow | Edge % | All255 % | Any255 % | Near250 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V00 | 50.908955 | 0.260322 | 0.196627 | 0.000000 | 95.238635 | 11.469564 | 12.628125 | 24.983984 |
| V01 | 21.634994 | 0.424465 | 0.000000 | 0.000000 | 0.000000 | 2.188509 | 2.491455 | 16.964551 |
| V02 | 15.015555 | 0.450847 | -0.731218 | 0.000000 | 0.000000 | 1.289274 | 1.481348 | 16.271989 |
| V03 | 13.883579 | 0.455708 | -1.126137 | -0.000002 | 0.000000 | 1.164486 | 1.340592 | 16.141748 |
| V04 | 1.649237 | 0.604303 | 0.039853 | 0.029939 | 0.013767 | 4.532910 | 4.888102 | 17.156836 |
| V05 | 0.206155 | 0.799086 | 0.093738 | 0.070774 | 0.354906 | 6.403776 | 6.855111 | 17.197266 |
| V06 | 0.078714 | 1.019155 | 0.160261 | 0.123023 | 1.018962 | 7.788184 | 8.490853 | 17.209001 |
| V07 | 0.000000 | 0.641018 | -13.197032 | 1.659426 | 0.000000 | 0.000749 | 0.000781 | 0.069824 |
| V08 | 0.000000 | 0.636173 | -14.591115 | -9.024340 | 0.000000 | 0.000716 | 0.000749 | 0.053760 |
| V09 | 0.000000 | 0.681753 | -14.223108 | -0.178902 | 0.000000 | 0.000326 | 0.000326 | 0.010303 |
| V10 | 1.731699 | 0.499278 | -1.947751 | -5.691552 | 0.000000 | 0.009928 | 0.011719 | 3.987288 |
| V11 | 0.000000 | 0.658891 | -11.879422 | -3.540119 | 0.000000 | 0.000293 | 0.000293 | 0.006217 |
| V12 | 0.000000 | 0.671768 | -11.902249 | -2.943592 | 0.000000 | 0.000293 | 0.000293 | 0.005176 |
| V13 | 0.000000 | 0.680896 | -11.912012 | -2.649026 | 0.000000 | 0.000293 | 0.000293 | 0.004850 |
| V14 | 0.041231 | 0.697918 | -41.926405 | -20.075455 | 0.000000 | 0.058333 | 0.070671 | 6.699202 |
| V15 | 0.000000 | 0.994016 | -49.771401 | -23.094028 | 0.000000 | 0.000700 | 0.000814 | 0.222314 |
| V17 | 0.449792 | 0.646212 | -1.073917 | 0.029937 | 0.000810 | 3.084668 | 3.340771 | 15.948340 |
| V16 (skip) | duplicate V04 | — | — | — | — | — | — | — |

### Kill Bill Vol. 2, frame 14943 (close-up)

| ID | Flat % | Ret | Mid | Shadow | Edge % | All255 % | Any255 % | Near250 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V00 | 58.898187 | 0.221862 | 0.364494 | 0.000000 | 87.484036 | 3.707064 | 4.521940 | 8.433757 |
| V01 | 23.068340 | 0.379822 | 0.000000 | 0.000000 | 0.000000 | 1.339193 | 1.539665 | 5.836865 |
| V02 | 18.437936 | 0.411057 | -1.165824 | 0.000000 | 0.000000 | 1.097526 | 1.245605 | 5.184635 |
| V03 | 17.712692 | 0.416901 | -1.722376 | 0.000000 | 0.000000 | 1.061833 | 1.202507 | 5.066748 |
| V04 | 9.539749 | 0.527863 | 0.010374 | 0.012427 | 0.004042 | 1.868132 | 2.161865 | 5.908301 |
| V05 | 3.249651 | 0.689107 | 0.024877 | 0.027780 | 0.553696 | 2.381022 | 2.799593 | 5.947656 |
| V06 | 1.129707 | 0.874533 | 0.042917 | 0.047437 | 2.951970 | 2.814095 | 3.376611 | 5.977930 |
| V07 | 0.292887 | 0.616168 | -16.455724 | 1.674919 | 0.000000 | 0.062174 | 0.066504 | 0.771842 |
| V08 | 0.320781 | 0.590810 | -13.414530 | -8.017977 | 0.000000 | 0.066195 | 0.070996 | 0.856006 |
| V09 | 0.153417 | 0.662471 | -17.204545 | -0.154233 | 0.000000 | 0.051758 | 0.056396 | 0.580745 |
| V10 | 3.598326 | 0.467575 | -1.782316 | -6.067866 | 0.000000 | 0.145752 | 0.163411 | 2.094108 |
| V11 | 0.055788 | 0.666170 | -12.565982 | -3.119108 | 0.000000 | 0.043929 | 0.047738 | 0.468750 |
| V12 | 0.055788 | 0.668836 | -12.962151 | -2.563969 | 0.000000 | 0.042985 | 0.046501 | 0.457568 |
| V13 | 0.055788 | 0.673198 | -13.162826 | -2.293209 | 0.000000 | 0.042513 | 0.045833 | 0.452490 |
| V14 | 5.760112 | 0.646525 | -44.069976 | -18.917476 | 0.000000 | 0.525846 | 0.586963 | 2.600879 |
| V15 | 2.161785 | 0.985760 | -52.505732 | -21.715677 | 0.000000 | 0.279704 | 0.295052 | 1.297900 |
| V17 | 7.489540 | 0.573723 | -1.705788 | 0.012427 | 0.000000 | 1.501725 | 1.710270 | 5.180371 |
| V16 (skip) | duplicate V04 | — | — | — | — | — | — | — |

### Kill Bill Vol. 2, frame 118560

| ID | Flat % | Ret | Mid | Shadow | Edge % | All255 % | Any255 % | Near250 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V00 | 32.988438 | 0.124331 | 1.592728 | N/A (null) | 29.602834 | 0.000553 | 56.473307 | 0.918311 |
| V01 | 31.769938 | 0.184776 | 0.000000 | N/A (null) | 0.000000 | 0.000553 | 31.415332 | 0.917806 |
| V02 | 30.435814 | 0.194558 | -3.701853 | N/A (null) | 0.000000 | 0.000553 | 27.138883 | 0.917497 |
| V03 | 30.059294 | 0.196669 | -5.106380 | N/A (null) | 0.000000 | 0.000553 | 26.502751 | 0.917513 |
| V04 | 30.257931 | 0.232873 | -0.042164 | N/A (null) | 0.000000 | 0.000553 | 32.052425 | 0.915755 |
| V05 | 26.341536 | 0.291051 | -0.098484 | N/A (null) | 0.039972 | 0.000553 | 32.721598 | 0.912516 |
| V06 | 18.597688 | 0.361928 | -0.167627 | N/A (null) | 0.311473 | 0.000553 | 33.553223 | 0.909180 |
| V07 | 4.802846 | 0.479742 | -32.664022 | N/A (null) | 0.000000 | 0.000423 | 0.569320 | 0.107585 |
| V08 | 2.365846 | 0.590049 | -41.719572 | N/A (null) | 0.000000 | 0.000374 | 0.276514 | 0.088981 |
| V09 | 3.691076 | 0.513251 | -30.043258 | N/A (null) | 0.000000 | 0.000391 | 0.460628 | 0.100960 |
| V10 | 27.764601 | 0.253917 | -0.227208 | N/A (null) | 0.000000 | 0.000537 | 15.619531 | 0.772282 |
| V11 | 2.253187 | 0.580548 | -40.839899 | N/A (null) | 0.000000 | 0.000358 | 0.248958 | 0.082503 |
| V12 | 1.974503 | 0.598130 | -39.826691 | N/A (null) | 0.000000 | 0.000309 | 0.222965 | 0.075732 |
| V13 | 1.849985 | 0.604566 | -39.329760 | N/A (null) | 0.000000 | 0.000309 | 0.212712 | 0.072298 |
| V14 | 24.933294 | 0.250623 | -50.138600 | N/A (null) | 0.000000 | 0.000521 | 19.938346 | 0.676644 |
| V15 | 19.813223 | 0.289072 | -60.471602 | N/A (null) | 0.000000 | 0.000456 | 16.807129 | 0.671891 |
| V17 | 28.170768 | 0.248538 | -5.155792 | N/A (null) | 0.000000 | 0.000553 | 27.270329 | 0.914990 |
| V16 (skip) | duplicate V04 | — | — | — | — | — | — | — |

### Kill Bill Vol. 2, frame 10080

| ID | Flat % | Ret | Mid | Shadow | Edge % | All255 % | Any255 % | Near250 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V00 | 93.161626 | 0.177253 | 0.083690 | 0.000000 | 60.660261 | 31.615511 | 32.822282 | 46.473893 |
| V01 | 50.465501 | 0.269029 | 0.000000 | 0.000000 | 0.000000 | 21.752523 | 22.765918 | 44.956299 |
| V02 | 40.328450 | 0.293784 | -0.596458 | -0.000007 | 0.000000 | 19.769482 | 20.705176 | 44.573991 |
| V03 | 38.508979 | 0.298591 | -0.950543 | -0.000017 | 0.000000 | 19.426758 | 20.346810 | 44.481689 |
| V04 | 10.777410 | 0.401384 | -0.049673 | -0.294598 | 0.022370 | 23.727848 | 24.417594 | 44.161572 |
| V05 | 1.672968 | 0.576001 | -0.116981 | -0.685676 | 1.920743 | 24.991390 | 25.542171 | 42.051872 |
| V06 | 0.439509 | 0.792111 | -0.194305 | -1.171310 | 5.378770 | 25.903662 | 26.453857 | 39.760856 |
| V07 | 0.070888 | 0.622134 | -10.582179 | 2.875565 | 0.000000 | 2.827490 | 3.006868 | 18.385124 |
| V08 | 0.009452 | 0.778835 | -26.543638 | -13.856989 | 0.000000 | 1.537093 | 1.611654 | 9.824007 |
| V09 | 0.023629 | 0.710915 | -13.077335 | 0.998741 | 0.000000 | 1.955990 | 2.088428 | 12.928223 |
| V10 | 0.569471 | 0.516585 | -1.662633 | -4.228846 | 0.000000 | 4.571501 | 4.841960 | 28.463525 |
| V11 | 0.009452 | 0.754539 | -28.670559 | -8.961166 | 0.000000 | 1.601367 | 1.685319 | 10.217806 |
| V12 | 0.009452 | 0.759049 | -27.940916 | -8.234303 | 0.000000 | 1.577083 | 1.655192 | 10.049398 |
| V13 | 0.009452 | 0.761051 | -27.576663 | -7.873332 | 0.000000 | 1.565527 | 1.642562 | 9.977913 |
| V14 | 3.083648 | 0.745434 | -46.255610 | -22.988714 | 0.000000 | 7.529785 | 7.959587 | 25.913753 |
| V15 | 0.000000 | 1.060061 | -55.162937 | -26.547581 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| V17 | 8.412098 | 0.428493 | -1.010947 | -0.294846 | 0.000000 | 21.926579 | 22.584082 | 43.398177 |
| V16 (skip) | duplicate V04 | — | — | — | — | — | — | — |

### Kill Bill Vol. 2, frame 82560

| ID | Flat % | Ret | Mid | Shadow | Edge % | All255 % | Any255 % | Near250 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V00 | 60.241394 | 0.121377 | 0.077304 | 0.000000 | 56.069206 | 0.000000 | 49.857438 | 0.000260 |
| V01 | 57.835385 | 0.214351 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 29.599072 | 0.000016 |
| V02 | 56.949482 | 0.227836 | -0.437240 | 0.000000 | 0.000000 | 0.000000 | 24.275439 | 0.000000 |
| V03 | 56.737420 | 0.230530 | -0.718840 | 0.000000 | 0.000000 | 0.000000 | 23.375814 | 0.000000 |
| V04 | 52.599243 | 0.278777 | 0.016399 | -0.001080 | 0.000000 | 0.000000 | 31.305387 | 0.000146 |
| V05 | 34.792001 | 0.355651 | 0.038347 | -0.001531 | 0.158504 | 0.000000 | 32.473340 | 0.000179 |
| V06 | 14.039677 | 0.451908 | 0.066760 | -0.000999 | 2.462397 | 0.000000 | 33.353044 | 0.000277 |
| V07 | 11.179816 | 0.512682 | -9.972963 | 2.995270 | 0.000000 | 0.000000 | 0.058333 | 0.000000 |
| V08 | 3.654597 | 0.612765 | -15.035666 | -9.278062 | 0.000000 | 0.000000 | 0.035775 | 0.000000 |
| V09 | 1.413084 | 0.671609 | -11.696855 | 1.057964 | 0.000000 | 0.000000 | 0.023633 | 0.000000 |
| V10 | 44.641972 | 0.304878 | -1.791233 | -5.414798 | 0.000000 | 0.000000 | 0.530062 | 0.000000 |
| V11 | 0.925541 | 0.673876 | -12.705027 | -3.711794 | 0.000000 | 0.000000 | 0.018766 | 0.000000 |
| V12 | 0.816537 | 0.681069 | -12.558510 | -3.133582 | 0.000000 | 0.000000 | 0.018066 | 0.000000 |
| V13 | 0.747171 | 0.684579 | -12.484831 | -2.846885 | 0.000000 | 0.000000 | 0.017562 | 0.000000 |
| V14 | 18.716927 | 0.427830 | -42.365221 | -20.599289 | 0.000000 | 0.000000 | 6.510059 | 0.000000 |
| V15 | 0.000000 | 1.053121 | -50.290850 | -23.712580 | 0.000000 | 0.000000 | 0.006152 | 0.000000 |
| V17 | 48.750421 | 0.303427 | -0.698911 | -0.001080 | 0.000000 | 0.000000 | 26.503320 | 0.000114 |
| V16 (skip) | duplicate V04 | — | — | — | — | — | — | — |

### Kill Bill Vol. 2, frame 76800

| ID | Flat % | Ret | Mid | Shadow | Edge % | All255 % | Any255 % | Near250 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V00 | 75.844102 | 0.191594 | 0.003125 | 0.000000 | 2.082925 | 0.344743 | 35.772803 | 18.320475 |
| V01 | 50.967996 | 0.266524 | 0.000000 | 0.000000 | 0.000000 | 0.130094 | 23.175667 | 15.996891 |
| V02 | 44.847390 | 0.288652 | -0.137335 | 0.000000 | 0.000000 | 0.103760 | 20.863428 | 15.368929 |
| V03 | 43.731184 | 0.292985 | -0.295478 | 0.000000 | 0.000000 | 0.099919 | 20.463542 | 15.251156 |
| V04 | 25.230420 | 0.350902 | -0.008648 | -0.104279 | 0.000000 | 0.186979 | 25.051790 | 15.714355 |
| V05 | 5.703765 | 0.470765 | -0.019729 | -0.241112 | 0.124025 | 0.231527 | 26.930924 | 15.164665 |
| V06 | 1.370942 | 0.624342 | -0.033659 | -0.412357 | 1.340254 | 0.259782 | 28.607910 | 14.620150 |
| V07 | 0.122736 | 0.548928 | -4.387114 | 5.829918 | 0.000000 | 0.004980 | 2.329736 | 4.042480 |
| V08 | 0.000000 | 0.731483 | -20.133667 | -11.097365 | 0.000000 | 0.001855 | 0.673503 | 1.618962 |
| V09 | 0.002316 | 0.656926 | -7.823631 | 3.847389 | 0.000000 | 0.002458 | 1.222054 | 2.198779 |
| V10 | 0.972627 | 0.483904 | -1.325973 | -4.703383 | 0.000000 | 0.007764 | 3.303092 | 5.605452 |
| V11 | 0.000000 | 0.700997 | -22.077268 | -5.321283 | 0.000000 | 0.002002 | 0.743343 | 1.762760 |
| V12 | 0.000000 | 0.704467 | -21.537352 | -4.778860 | 0.000000 | 0.001969 | 0.727962 | 1.712077 |
| V13 | 0.000000 | 0.706333 | -21.269011 | -4.507072 | 0.000000 | 0.001969 | 0.720361 | 1.686312 |
| V14 | 0.000000 | 1.024930 | -45.520635 | -21.167300 | 0.000000 | 0.000000 | 0.008545 | 0.184554 |
| V15 | 0.000000 | 0.979396 | -54.223972 | -24.386744 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| V17 | 20.096336 | 0.376574 | -0.315442 | -0.104279 | 0.000000 | 0.150553 | 22.603174 | 15.086149 |
| V16 (skip) | duplicate V04 | — | — | — | — | — | — | — |

### Kill Bill Vol. 2, frame 110257 (dark control)

| ID | Flat % | Ret | Mid | Shadow | Edge % | All255 % | Any255 % | Near250 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V00 | 29.300323 | 0.263209 | 0.030300 | 0.000000 | 17.399426 | 0.000000 | 15.625928 | 0.000000 |
| V01 | 7.448870 | 0.385244 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 14.088265 | 0.000000 |
| V02 | 4.757804 | 0.442034 | -0.489173 | 0.000000 | 0.000000 | 0.000000 | 12.495524 | 0.000000 |
| V03 | 4.219591 | 0.453807 | -0.843830 | 0.000000 | 0.000000 | 0.000000 | 11.996110 | 0.000000 |
| V04 | 2.691066 | 0.453268 | 0.006981 | -0.004875 | 0.000000 | 0.000000 | 14.105973 | 0.000000 |
| V05 | 0.753498 | 0.549912 | 0.016372 | -0.012294 | 0.000891 | 0.000000 | 14.127327 | 0.000000 |
| V06 | 0.193757 | 0.672250 | 0.027820 | -0.020305 | 0.183821 | 0.000000 | 14.149919 | 0.000000 |
| V07 | 0.086114 | 0.599673 | -11.816032 | 2.866211 | 0.000000 | 0.000000 | 3.122233 | 0.000000 |
| V08 | 0.129171 | 0.563970 | -10.887479 | -7.771412 | 0.000000 | 0.000000 | 4.369938 | 0.000000 |
| V09 | 0.021529 | 0.632273 | -13.203921 | 0.836490 | 0.000000 | 0.000000 | 1.343880 | 0.000000 |
| V10 | 1.614639 | 0.447090 | -1.950771 | -6.264508 | 0.000000 | 0.000000 | 12.289176 | 0.000000 |
| V11 | 0.021529 | 0.589565 | -10.005486 | -2.895325 | 0.000000 | 0.000000 | 1.737207 | 0.000000 |
| V12 | 0.021529 | 0.596798 | -10.261868 | -2.349642 | 0.000000 | 0.000000 | 1.478532 | 0.000000 |
| V13 | 0.021529 | 0.599810 | -10.387493 | -2.080523 | 0.000000 | 0.000000 | 1.362402 | 0.000000 |
| V14 | 0.000000 | 0.893847 | -42.529125 | -18.534614 | 0.000000 | 0.000000 | 0.704769 | 0.000000 |
| V15 | 0.000000 | 0.858147 | -50.659895 | -21.285137 | 0.000000 | 0.000000 | 0.031217 | 0.000000 |
| V17 | 1.506997 | 0.522186 | -0.836067 | -0.004875 | 0.000000 | 0.000000 | 12.027002 | 0.000000 |
| V16 (skip) | duplicate V04 | — | — | — | — | — | — | — |

### Spider-Man: Across the Spider-Verse, excerpt 2, frame 72

| ID | Flat % | Ret | Mid | Shadow | Edge % | All255 % | Any255 % | Near250 % | mean_chroma_change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V00 | 26.823529 | 0.261933 | 0.001194 | 0.000000 | 0.000000 | 0.000081 | 9.599056 | 0.005371 | -0.031948 |
| V01 | 13.647059 | 0.345736 | 0.000000 | 0.000000 | 0.000000 | 0.000049 | 9.244922 | 0.003597 | 0.000000 |
| V02 | 9.882353 | 0.393674 | -0.024784 | 0.000000 | 0.000000 | 0.000049 | 9.137191 | 0.003288 | 0.044409 |
| V03 | 9.411765 | 0.402044 | -0.056107 | 0.000000 | 0.000000 | 0.000049 | 9.113932 | 0.003190 | 0.075944 |
| V04 | 8.470588 | 0.412743 | 0.028421 | 0.010012 | 0.000000 | 0.000065 | 9.303760 | 0.004557 | -0.033630 |
| V05 | 3.529412 | 0.506317 | 0.068558 | 0.028185 | 0.000000 | 0.000081 | 9.362858 | 0.005127 | -0.081946 |
| V06 | 2.117647 | 0.609827 | 0.122667 | 0.057777 | 0.505502 | 0.000098 | 9.420199 | 0.005501 | -0.147611 |
| V07 | 0.235294 | 0.610075 | 0.258276 | 6.719074 | 0.292495 | 0.000016 | 6.347900 | 0.001676 | 0.264442 |
| V08 | 0.000000 | 0.688147 | -4.592933 | -4.212316 | 0.002078 | 0.000000 | 4.488835 | 0.001025 | -9.358483 |
| V09 | 0.000000 | 0.693513 | -1.782612 | 3.931510 | 0.002078 | 0.000000 | 5.030501 | 0.000993 | -1.254109 |
| V10 | 1.411765 | 0.515952 | -1.118194 | -2.887216 | 0.000000 | 0.000016 | 8.661589 | 0.002181 | -1.153829 |
| V11 | 0.000000 | 0.674511 | -4.112100 | -1.555228 | 0.002078 | 0.000000 | 5.084782 | 0.000977 | -7.732579 |
| V12 | 0.000000 | 0.678168 | -4.008966 | -1.259137 | 0.002078 | 0.000000 | 5.037842 | 0.000977 | -7.286122 |
| V13 | 0.000000 | 0.679611 | -3.958218 | -1.110559 | 0.002078 | 0.000000 | 5.014551 | 0.000944 | -7.069525 |
| V14 | 0.000000 | 0.950074 | -20.009268 | -11.609363 | 0.000000 | 0.000000 | 0.446631 | 0.000000 | -49.350313 |
| V15 | 0.000000 | 0.862054 | -24.049305 | -13.475262 | 0.000000 | 0.000000 | 0.008382 | 0.000000 | -61.690182 |
| V17 | 5.176471 | 0.464951 | -0.025807 | 0.010012 | 0.000000 | 0.000049 | 9.173893 | 0.004020 | 0.039756 |
| V16 (skip) | duplicate V04 | — | — | — | — | — | — | — | — |

### The Substance, excerpt 2, frame 72

| ID | Flat % | Ret | Mid | Shadow | Edge % | All255 % | Any255 % | Near250 % | mean_chroma_change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V00 | 0.000000 | 0.771136 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| V01 | 0.000000 | 0.768593 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| V02 | 0.000000 | 0.761167 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| V03 | 0.000000 | 0.752332 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000038 |
| V04 | 0.000000 | 0.769409 | 0.002830 | 0.004564 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.001513 |
| V05 | 0.000000 | 0.769877 | 0.006519 | 0.010366 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.001874 |
| V06 | 0.000000 | 0.772834 | 0.011226 | 0.017607 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000627 |
| V07 | 1.098901 | 0.505418 | 22.236748 | 16.444377 | 63.291877 | 0.000000 | 0.005620 | 0.000000 | 2.728269 |
| V08 | 0.000000 | 0.744500 | 9.923136 | 3.854081 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1.416922 |
| V09 | 0.000000 | 0.738117 | 13.848937 | 12.005793 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1.730302 |
| V10 | 0.000000 | 0.853478 | -0.282353 | -2.559496 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.169141 |
| V11 | 0.000000 | 0.840027 | 6.515962 | 4.919696 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.794811 |
| V12 | 0.000000 | 0.855878 | 6.400504 | 5.117386 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.790331 |
| V13 | 0.000000 | 0.850248 | 6.334306 | 5.216873 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.787986 |
| V14 | 0.000000 | 0.853972 | -41.849276 | -21.806191 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | -28.893396 |
| V15 | 0.000000 | 0.787889 | -49.757898 | -25.161230 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | -36.060726 |
| V17 | 0.000000 | 0.768610 | 0.002830 | 0.004564 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.001550 |
| V16 (skip) | duplicate V04 | — | — | — | — | — | — | — | — |

### Frame 118560 retention division counts

Only this frame has zero source-std blocks. All other measured frames have zero undefined and zero infinite ratios. Undefined 0/0 blocks are excluded from each median; positive-over-zero blocks remain infinite, and all reported medians are finite. Its 17 shadow shifts above are null because the source interval is empty.

| ID | Undefined 0/0 blocks | Positive/0 infinite blocks |
| --- | --- | --- |
| V00 | 3 | 63 |
| V01 | 3 | 63 |
| V02 | 3 | 63 |
| V03 | 3 | 63 |
| V04 | 3 | 63 |
| V05 | 3 | 63 |
| V06 | 3 | 63 |
| V07 | 1 | 65 |
| V08 | 0 | 66 |
| V09 | 4 | 62 |
| V10 | 62 | 4 |
| V11 | 12 | 54 |
| V12 | 23 | 43 |
| V13 | 58 | 8 |
| V14 | 62 | 4 |
| V15 | 61 | 5 |
| V17 | 3 | 63 |

## Control color interpretation

V17 mean chroma changes are +0.039756 codes in the Spider-Verse magenta region and +0.001550 in The Substance orange region; V04 gives -0.033630 and +0.001513. These small regional means agree with the inspected leaders' similar colored rendition, but can conceal local changes. No hue or calibrated perceptual color-error metric was measured. The animated figure and fabric/face crops do not show an obvious new leader artifact. The Substance's source is soft and has a very small ROI, so unchanged flattened percentage there is weak evidence of highlight-detail quality. The dark-control face/cloth crops and whole-frame interval deltas cover different aspects; whole-scene shadow appearance remains outside the cropped visual proof.

## Execution and verification ledger

Every native case used a fresh bounded subprocess with a 150-second timeout, serialized GPU ownership, exit recording, reaping and owned-scratch cleanup. No native timeout or failure occurred. Native constructor/helper calls can include frame zero; they are distinct from requested target render-case counts. Render walltimes are single-run execution receipts, with no latency, throughput or speedup claim.

| Stage/work | Successful work | Failure / timeout / skip | Evidence |
| --- | --- | --- | --- |
| S0 original | 10 full-resolution native cases | 0 / 0 / 0 | s0-summary.json |
| S0 approved revision | 2 native faithfulness cases | 0 / 0 / 0 | s0-revision-summary.json |
| S0 scan | 35 decode batches, 412 frames; 582.273 s | 0 / 0 / 0 | scan/invocations.json |
| S0 metadata | 4 ffprobe jobs (3 original + 1 revision) | 0 failed jobs | metadata/ and alternate-encode-metadata/ |
| S0 alternate classification | 1 decode-only job, 3 frames | 0 failed jobs | alternate-encode-metadata/ |
| S1a | 144 native cases, V00–V15 × 9 | 0 / 0 / 0 | s1-invocation-inventory.json |
| S1b | 9 native V17 cases | 0 / 0 / 9 V16 duplicate skips | s1b-invocation-inventory.json |
| Cumulative native | 165 successful target cases | 0 failures; 0 timeouts; 9 duplicate skips | S0 12 + S1 153 |
| S2 offline | 153-row consistency/hash audit; 7 row recomputations; 18 six-variant sheets, 36 unscaled sub-sheets, 9 source diagnostics, 1 supplement | No native renders | s2/ranking.json and s2/recomputed.json |

The short evidence names in this ledger resolve under `generated/verification/2026-10-24/highlight-detail/`. Full per-case commands, timestamps, exits, timeout/reaping state, settings, kwargs and cleanup receipts remain local in those inventories and render directories. S1 supervisors/analysis commands `s1_orchestrate.py`, `s1_analyze.py`, `s1b_orchestrate.py`, `s1b_analyze.py` and `s1_finalize.py` each exited 0. Their receipts are experiment evidence and make no product-suite claim.

Nonnative corrections are retained rather than counted as successful product tests. S0's first numeric-fixture run exited 1 on exact floating-point equality for one-third; it corrected assertion tolerance, left metric arithmetic unchanged and reran successfully. The first input-property audit exited 1 after assuming deprecated _ColorRange; the correction checks current _Range through product normalization and passed for all nine captures. The controller's first S1 audit exited 1 because its 153-count assertion searched only the 144-case S1a directory; corrected scope included nine S1b cases, exited 0 and found no mismatches. S2's exploratory receipt-directory listing exited 1 on an incorrect directory assumption; the correct paths came from each compact row. An exploratory source search/read also encountered obsolete profile paths; direct current-owner lookup resolved the public color-model question. S2 document validation had two initial exit-1 attempts because it checked its own pending receipt before writing it; the first repair also compared a relative path with an absolute path. Resolving the path and checking the parent before writing corrected the audit, which then exited 0. These were fixture/audit/navigation errors and caused no native rerender or product modification.

S2 commands from repository root: `.venv/Scripts/python.exe generated/verification/2026-10-24/highlight-detail/s2_analysis.py`, `.venv/Scripts/python.exe generated/verification/2026-10-24/highlight-detail/s2_sources.py` and `.venv/Scripts/python.exe generated/verification/2026-10-24/highlight-detail/s2_report.py` each exited 0. The corrected `.venv/Scripts/python.exe generated/verification/2026-10-24/highlight-detail/s2_validate.py` exited 0: all 153 observed rows, nine V16 references, required columns and rounded values, all CSV columns, 34 control chroma values, 24 relative evidence references, front matter, privacy/content scan and all 33 frozen hashes passed. Direct trailing-whitespace/newline validation passed, and `git diff --check` exited 0. Final S2 outcomes are retained in `generated/verification/2026-10-24/highlight-detail/s2/validation.json`.

Executor settings: S0 and S2 use `gpt-6.1-sol / medium`; S1 uses `gpt-5.6-luna / xhigh`; independent R used `gpt-6.1-sol / high`. The executor preset does not itself apply a model setting; these are the explicitly selected chat settings. No child stages or commits files. The controller owns the pending documentation commit and any later publication approval.

## Independent review

R completed an instruction-enforced read-only review with no material findings, no file writes and no native rerender. Independent Python audits exited 0 without importing the frozen metric implementation. R used the ST2084 rational constants, independent sliding-window extraction sampled every eight pixels, and manually centered population variance. Using the declared matrix-weight arithmetic, R reproduced all nine source statistics and all nine V01/V17 flattened fractions, retention values, midtone/shadow shifts and edge measurements, plus both control chroma means, within an assertion tolerance of 1e-8; the final comparisons had zero delta from the retained unrounded results.

Confirmed porch V01 flattened fraction/retention were 21.634993815360396% / 0.42446477068348043, versus V17 0.4497919712133138% / 0.6462119265555365. The six-bright-frame means were V01 39.290358886229875% / 0.2898277709319976 and V17 18.894825911406993% / 0.42949469350991953. Confirmed V17 control chroma means were +0.03975596543441938 and +0.0015499974033548656 codes. Eligibility and raw ranking were unchanged.

The first independent calculation exited 1 at frame 118560 retention: 0.18477718710002483 versus 0.18477582436896597, a difference of about 1.36e-6. Scalar-channel summation instead of the declared matrix-weight arithmetic changed machine-zero standard-deviation classification in this frame. Repeating the declared arithmetic while retaining independent block extraction and variance calculation reproduced the retained values. This is a numerical-sensitivity caveat and failed exploratory assertion; no native failure, threshold change or conclusion change resulted.

R independently checked all 33 frozen hashes, all 153 compact/detail rows and output file hashes, recorded settings in all 153 receipts and 306 actual native calls, all 153 document rows and nine duplicate references, all 165 successful native receipts, complete scan coverage and greedy frame selection, and 324 pixel-copied tiles across all 36 sub-sheets. Source arrays for V01 in all nine cases were rehashed through independent recomputation; the other receipt input identities were audited without rehashing every retained array. No source/plugin drift or candidate-dependent threshold, mask or crop tuning was found. These checks reuse saved native evidence and make no fresh native-parity claim.

R inspected 26 original-resolution images: both leader sub-sheets, both challenger sub-sheets and the source diagnostic for porch, close-up, dark, Spider-Verse and The Substance, plus the porch supplement. R agreed that V17 modestly strengthens grain and existing edges, with little change in larger-scale sky structure; eligible faces and colored controls remained close within those windows. The controller separately inspected eight original-resolution sheets and agreed with those bounded observations. Source diagnostic quantization and unmanaged PQ-code viewing further limit absence claims. Outcome (c) and the proposed blinded saved-crop comparison remain supported; physical display, color, temporal and broader-master acceptance remain unverified. S2 finalized status and reran document validation without repeating analysis or rendering; its ignored finalization ledger is `generated/verification/2026-10-24/highlight-detail/s2/review-finalization.json`.

## Limits and unrun work

The sample covers one admitted HDR Kill Bill encode, six selected bright frames and three controls. It does not establish multiple-master behavior. Grain, dithering, compression noise and edges contribute to standard deviation. Threshold crossings and mixed-unit retention cannot establish perceptual structure restoration. Source-only highest-texture crop selection can favor edges/grain; the supplementary porch window is only one additional region. Neither the source-code diagnostics nor the image-tool view is calibrated physical HDR/SDR acceptance.

The single-frame independent still path supplies no temporal-stability evidence. Color means have no hue or perceptual-error authority. Edge overshoot detects broad brightening as well as possible halos and misses dark halos. No claim is made that all visual artifacts are absent. Further curve/target tuning, a full Cartesian matrix, alternate-encode HDR comparisons, conditional ST2094-40, calibrated display acceptance and the proposed blinded comparison are UNRUN or not admitted as described above.

Full product/native tests, CLI E2E, Docker, Windows packaged-release acceptance, release/signing and a documentation-site build are UNRUN for this findings-only change. No product/runtime pass is inferred from successful analysis scripts, previous research, a missing CI job or a skip. No product change, staging, commit, branch change or push is performed by S2.
