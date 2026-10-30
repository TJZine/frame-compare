---
search:
  exclude: true
---

# Tone mapping and highlight preservation: research report

Prepared 23 October 2026. Source examined: `f1d3b9bf4c3406e3d0cddbfbbc536e0ac8a9279e`.

This report combines source and history research, primary upstream documentation, and a subsequent controlled native Windows investigation on the stated checkout. The current measurements and controller adjudication appear first; the original research and historical measurements follow with their provenance retained. This is not acceptance of a new product default. The initial research changed no product code. The later implementation addendum records the opt-in product change; user configuration and source media remain unchanged.

## Local review evidence

Review artifacts are retained only on the Windows machine under
`generated/verification/2026-10-23/`. They include comparison images, raw summaries,
native receipts and the implementation diff. The committed copies were removed
from the branch tip because they included film frames, local media filenames and
a Windows username. Local artifact paths in this report are recorded as code;
readers need access to that machine to inspect them. Tracked source and document
links are relative to the repository.

## Implementation follow-up: opt-in knee 1.0 and expanded softclip study

24 October 2026 update: `reference` now uses knee 1.0, and `highlight_preserve` was removed.

The subsequent implementation was committed at `6bedfa31`, based on the source
revision stated above. The source diff is available with
`git diff f1d3b9bf..6bedfa31 -- src/`. `highlight_preserve` is the public opt-in
preset. It uses BT.2390 at 100 nits with knee offset 1.0, retaining the other reference settings.
Reference remains the default with knee 0.5; `highlight_guard` remains spline/180.
Softclip was tested further but is not part of the option.

```bash
frame-compare run --tm-preset highlight_preserve
```

For persistent configuration, set `preset = "highlight_preserve"` under `[color]`.
Existing explicit target, curve, gamma and contrast-recovery fields still override
the preset. An explicit switch to another curve resets the generic native curve
parameter to 0.5, preventing the tuned BT.2390 knee from becoming spline/Reinhard
contrast. Explicit BT.2390 keeps knee 1.0. The normal applied-tonemap record retains
the resolved preset and parameter. Fast mode and other overrides can change results; clipping can remain
with this highlight-preservation option.

### Additional difficult scenes

The expanded study evaluated five additional excerpt/frame pairs: magenta lighting
and a blue-lit closeup in Spider-Verse; bright fabric/skin and reflective jewelry/
skin in The Substance; and candlelight in Immaculate. Every pair holds knee 1.0
constant and compares perceptual gamut mapping (1) against softclip (2).
All use excerpt-local frame 72 of the exact retained excerpt identified in the raw
receipts. Source hashes, source times, indexes and native settings are retained. A separate optional third Immaculate excerpt timed
out at 150 seconds; its child was killed/reaped and owned scratch removed, and its
softclip pair was not attempted. It supplies no quality evidence.

The table uses full-picture stride-4 sampling, unlike the first study's row-250
crop. Do not directly compare its percentages with earlier cropped metrics.
“Active” means measurable mapping change. Recovered highlight detail requires
separate evidence.

| Additional scene | Any channel at 255, perceptual → softclip | Mean RGB code, perceptual → softclip | Interpretation |
| --- | ---: | ---: | --- |
| Spider-Verse excerpt 2, magenta room | 9.2760% → 1.6003% | 76.14 → 77.97 | Strong endpoint reduction; changes color and lifts some bright details |
| Spider-Verse excerpt 3, blue closeup | 0.5997% → 0.00625% | 58.61 → 59.01 | Strong reduction in colored highlights with modest overall mean change |
| Substance excerpt 2, fabric/skin | 0% → 0% | 90.76 → 90.54 | Active color change; no endpoint recovery |
| Substance excerpt 3, jewelry/skin | 0% → 0% | 63.49 → 63.46 | Smaller active color change; no clipping benefit established |
| Immaculate excerpt 2, candlelight | 0% → 0% | 8.995 → 9.000 | Inactive control; supplies no quality evidence |

All-white sampled occupancy was zero for every row on both sides. This matrix
therefore tests colored endpoint behavior and other rendition changes. It
provides no evidence of a neutral-white clipping remedy. Four scenes across two
titles were active under
the study's explicit activity criterion: at least 0.1% of sampled components
change by two or more code values, with a maximum change of at least four.
The live-action scenes satisfy that criterion but must not be described as four
successful clipping recoveries.

The controller inspected the magenta and fabric/skin comparison sheets and
independently reran the magenta pair. Both rerendered images matched the delegate's
pixels exactly. The controller also ran the endpoint-reduction assertion (exit 0)
and the unchanged-image negative control (expected exit 1), and verified all 137
hashes in the expanded-study artifact manifest. In the magenta image the
difference affects the colored light field and the nominally neutral character, with regional luma increases.
Mean absolute code change was 2.285 there and 1.197 in the blue closeup, with
localized maximum differences of 89 and 84 code values. Those local changes are
large enough to deserve artistic scrutiny even though whole-image averages are
small. In the Substance fabric/skin scene, mean absolute change was 0.782 codes,
with a maximum of 12; the visible warm-color rendition changes subtly. No
perceptual reference or calibrated color-error metric establishes which is better.

Regional deltas clarify the direction of the softclip change. Values below
are softclip minus perceptual, with knee 1.0 held constant. Chroma is the mean
per-pixel max−min spread of gamma-coded RGB; luma is a code-value proxy. Neither
is calibrated luminance or a perceptual color-error measure. Hue was not measured.

| Region | Mean chroma delta, codes | Mean luma delta, codes |
| --- | ---: | ---: |
| Spider-Verse magenta lights | −2.24 | +2.52 |
| Spider-Verse blue light | −2.53 | +2.69 |
| Spider-Verse bright neutral character | −5.14 | +3.30 |
| Substance orange background | +4.60 | −1.24 |
| Substance red background | +1.63 | −0.55 |

In clipped saturated regions, softclip lowers chroma and raises luma. In the
unclipped warm backgrounds, it raises chroma and darkens slightly. Its endpoint
reduction therefore includes desaturation, while the live-action results show
changes to colors that were already within the output range.

The new scenes support further softclip evaluation for difficult
saturated colors, but do not justify changing the default or bundling it with the
knee preset. Its effects extend beyond clipped pixels. Obtain an independent
color/texture assessment before making it a public policy. Retain the distinction
between fewer channel endpoints and more faithful image detail.

### Implementation evidence and review

The focused set passed all 101 tests, including preset resolution, all-preset
persistence/merge roundtrips, curve overrides, render wiring, runtime-free help and
CLI-contract docs. Installed contributor CLI `run --help` lists the preset;
`run --tm-preset highlight_preserve --write-config` on an isolated workspace
succeeded and its saved config resolved to BT.2390/knee 1.0. Native execution of
the public config resolver's settings matched direct knee1 pixels on the magenta
scene, and the tapped and untapped versions also matched.

The independent source reviewer reported no actionable findings after checking
all 32 preset/curve combinations through in-memory TOML roundtrip, CLI merge and
native-argument construction. This read-only source/component review supplied no
image-quality acceptance. Its callback was rejected by automatic approval review; the controller retrieved the result directly, so the review
was not lost. No callback authorization workaround was used.

Pyright reported zero errors/warnings; Ruff lint, Bandit at the required
medium/high threshold, and both import contracts passed in the implementation
checks. The earlier claim that whole-repository Ruff formatting passed was
incorrect. At `6bedfa31`, PR #138 failed `Lint (Ruff)` because the committed
expanded-study `REPORT.md` contained a code block rejected by
`ruff format --check`. It also failed `Build documentation` because the handoff
and research report contained broken local and artifact links.
Initial focused-test attempts failed on existing cache permissions and then a
missing scratch parent; a fresh isolated scratch run passed. Those setup failures
are not represented as product failures or clean test runs.

The expanded unit completed 12 successful native cases (five pairs plus plain
and configured parity) and one timeout; the controller added two successful
independent repeats. Full-suite outcome is recorded in the historical Windows verification
receipt below. Docker/bash and Zensical were unavailable on the Windows
investigation host, leaving the Docker media gate and strict documentation-site
build unverified in that phase.
No new Windows portable build, installed-CLI full media render, HLG, or calibrated
physical-display acceptance is claimed.

### Independent review

The independent review of `6bedfa31` found six issues: committed film frames and
private local-path evidence (R1), broken documentation links (R2), missing proof
that the knee reaches the native plugin (R3), tests inheriting local configuration
and environment settings (R4), overstated or inaccurate report claims (R5), and
misplaced architecture text and configuration-specific guide instructions (R6).
The preset values and resolver rule were accepted without a product-code change.

The review ran the strict documentation build at base `f1d3b9bf` (pass) and
`6bedfa31` (seven warnings, failure). The full macOS suite at `6bedfa31` exited 0
with 3,746 passed and 336 skipped. A mutation hardcoding the native curve parameter
to 0.5 still passed that suite, demonstrating the missing boundary coverage.
CWD-config and environment reproductions each triggered the collection-warning
test failure. The reviewer also inspected the porch and Spider-Verse comparison
sheets and raw summaries. These are historical review results; they are separate
from checks run while correcting this documentation.

Knee 1.0 is a sound opt-in with modest measured separation: fewer near-white and
endpoint pixels, slightly more distinct values, and a mean reduction of about
3.5 RGB codes on the porch. Much of the bright sky remains near white, and the
visible change is small. Softclip stays experimental. It reduces colored
endpoints partly by desaturating clipped colors and also changes unclipped
saturated colors. Hue was not measured.

The local implementation artifacts are
`generated/verification/2026-10-23/highlight-implementation/`; expanded-study
artifacts are `generated/verification/2026-10-23/highlight-softclip-expanded/`.
The earlier research and initial-study sections below retain their historical
provenance. Statements there about unexposed controls and unchanged code describe
that earlier phase, before the opt-in implementation.

### Historical Windows implementation verification receipt

Full repository pytest completed in 396.7 seconds: **4,197 passed, 78 skipped,
4 failed** (4,279 collected; exit 1). This is not a clean full gate. Failures:

- Both PowerShell variants of the portable install/uninstall lifecycle failed at
  the helper that sets the user PATH. These tests use copied installer scripts
  and a stub launcher. No permission
  escalation or retry of the user-PATH mutation was attempted.
- The generated portable-bundle launcher environment-restoration check observed
  child exit 1 instead of 0. It uses a copied Python executable and synthetic CLI
  entry. Its underlying environment failure was not diagnosed
  or fixed in this scope.
- The collection-warning orchestration test expected a metadata-mismatch warning
  but received “upload skipped because report confirmation was unavailable.”
  The earlier base-source reproduction restored the three changed production
  files but still ran from the checkout and inherited its local configuration.
  Independent review traced the failure to a bare `ConfigSchema()` reading
  `config/config.toml` and `FRAME_COMPARE_*` variables. At base on macOS the test
  passes. It fails from a scratch CWD with
  `[slowpics] confirm_upload_after_report = true`, or with
  `FRAME_COMPARE_SLOWPICS__CONFIRM_UPLOAD_AFTER_REPORT=true`. The evidence
  identifies test isolation as the cause. No upload was performed; the test uses
  a mocked publisher and rejects unexpected HTTP.

No unrelated installer, launcher or publishing behavior was changed to make these
checks pass. The skipped cases and unavailable Docker/site-build gates were
explicit acceptance gaps in that Windows run. The implemented option has focused
public configuration,
installed-console persistence and actual native-render evidence; broader release
acceptance is incomplete. Exact receipts and the reviewable diff are in
verification.json (`generated/verification/2026-10-23/highlight-implementation/verification.json`)
and the adjacent XML/log/manifest files.

## Native investigation and adjudication before implementation

The requested orchestration is complete for this diagnostic scope. Two separate chats gathered real-media evidence and synthetic controls under explicit handoffs and completion-callback instructions. The controller reviewed their evidence, inspected the porch and Spider-Verse comparison images, reran the real-media positive and negative controls, and personally executed the synthetic native matrix. Native GPU execution was serialized. No proposed change was promoted into product defaults.

The native investigation recommended an opt-in BT.2390 knee 1.0 policy, separate
softclip evaluation for colored highlights, and effective-peak observability
before adopting a new automatic peak policy. Spline remains a useful stronger-compression alternative with a visible rendition cost. Neither knee 1.0 nor any other tested option is a general guarantee against blown highlights.

### What actually ran

- Real-media unit: 28 bounded native case subprocesses, all exit 0, on six selected frames across Kill Bill, Spider-Verse, The Substance, and Immaculate. A successful native doctor receipt accompanied the runs.
- Controller: three additional fresh real-media subprocesses (porch baseline, knee 1.0, and uninstrumented baseline), all exit 0. Their decoded PNG pixels exactly matched the corresponding original baseline/candidate evidence; the tapped and untapped baselines also matched.
- Controller: 17 fresh synthetic native case subprocesses, all exit 0 and all acquisition/oracle checks passed. The prepared step-pattern case 04 was not run; it was unnecessary for the bounded decisions here.
- Synthetic preparation: 19 pure numeric checks passed. These are arithmetic/fixture checks, distinct from the native executions above.
- The real-media endpoint-reduction assertion passed. Replacing the candidate with the baseline deliberately failed the required reduction assertion, exit 1. This proves the check discriminates that regression; it is not a comprehensive perceptual-quality oracle.
- Native environment: Windows 10 build 19045, Python 3.13.7, VapourSynth R81/API 4.3, vs-placebo 2.0.4, libplacebo 7.371, RTX 5080, NVIDIA driver 621.01. Source remained at the report's stated HEAD with no tracked source/configuration drift.

These 48 successful diagnostic case processes establish bounded numeric and
repeatability results. Artistic acceptance requires separate assessment. Real-media cases used the current still-image owner and final encoder boundary. Synthetic inputs bypassed the decoder and exercised the current conversion/mapper boundary. The knee, gamut, percentile, and metadata candidates were internal settings at
that stage and unavailable as public CLI recipes. The controller separately exercised actual configuration resolution: preset-only `highlight_guard` stayed BT.2390/100 under this checkout's explicit local overrides; explicit curve/target resolved to spline/180. That runtime-free configuration check did not render through the installed CLI. No packaged/Docker or calibrated physical-display acceptance is claimed.

### Real-media results from the corrected pipeline

Percentages below count sampled final sRGB8 pixels with all channels exactly 255. The real-media sampling uses every fourth pixel in both dimensions, starting at row 250; these figures are not whole-frame luminance measurements. Mean RGB is a gamma-encoded code average, useful only as a coarse guard against broadly darkening the image.

| Scene / intervention | All-white pixels | Mean RGB code | Controller interpretation |
| --- | ---: | ---: | --- |
| Porch, reference | 7.3305% | 139.13 | Current corrected-pipeline baseline |
| Porch, knee 1.0 | 0.8216% | 135.67 | Modest visible separation; much of the sky remains near white |
| Porch, spline / 100 nits | 0.0003% | 121.68 | Strong compression with substantial overall appearance change |
| Porch, metadata policy 2 | 0.0012% | 132.18 | Output improves this endpoint metric, but effective peak was not observed in fresh logs |
| Porch, measured CIE Y / 99.995 | 8.5814% | 139.40 | Does not solve this frame |
| Porch, measured CIE Y / 100 | 7.3286% | 139.13 | Better than 99.995 here, essentially baseline endpoint area |
| Porch, controlled static 448 | 0.1510% | 136.96 | Useful policy experiment; artistic authority remains unproven |
| Closeup, reference → knee 1.0 | 3.8773% → 1.3952% | Unrecorded here | Direction agrees with porch |
| Closeup, spline / 100 nits | 0.0404% | 75.67 versus reference 86.53 | Same retention-versus-rendition tradeoff |

On the same porch picture sample, near-white occupancy (all channels at or
above 250) falls from 20.90% to 11.45%. Distinct sampled RGB triplets increase
from 4,199 to 4,512, and mean RGB code falls from 139.13 to 135.67, about 3.5 codes.
In the upper-center sky region, near-white occupancy remains 76.20%, compared
with 81.88% at reference. The endpoint reduction alone overstates the visible
change; the inspected comparison shows a small improvement in separation.

The porch's metadata-policy-2 experiment retained its original RPU and detection settings; the measured/static experiments deliberately removed RPU and scene properties and disabled Dolby Vision use. Each comparison changes a different policy; attributing the effect to one
metadata field requires a separate control. The historical 285/1001-nit effective peaks discussed later were **not** remeasured in these fresh runs.

For colored highlights, Spider-Verse provides a more discriminating result:

| Spider-Verse intervention | Any channel at 255 | All channels at 255 | Mean RGB code |
| --- | ---: | ---: | ---: |
| Reference | 6.6331% | 0.4124% | 112.53 |
| Knee 1.0 | 3.6893% | 0.2062% | 111.97 |
| Knee 1.0 + softclip | 0.3387% | 0.2062% | 111.63 |
| Knee 1.0 + darken | 0.1889% | 0% | 101.73 |

Softclip reduced single-channel endpoint occupancy substantially with a small mean-code change and a relatively subtle visual difference in this scene. It did not remove neutral white pixels. Darken also reduced endpoints but visibly darkened the rendition; it is not the preferred default candidate. These one-scene color observations lack a perceptual color-error measurement.

The selected Substance and Immaculate baseline/knee images were identical and endpoint-free. They serve as inactive controls and supply no quality evidence for those titles'
difficult highlights. The Kill Bill dark frame had no all-white pixels but did have single-channel saturation: 18.2255% at reference versus 16.4300% with knee 1.0. All-white counts alone would have missed that behavior.

### Why zero clipped pixels is the wrong acceptance target

The contrast-recovery controls provide direct counterexamples. With the original knee, disabling recovery changed native any-channel endpoint occupancy from 5.3982% to 0.0003%, while final sRGB8 all-white occupancy increased from 7.3305% to 7.6532%. An apparent native endpoint victory therefore made this final-output metric worse.

With knee 1.0, disabling recovery almost eliminated porch final endpoints, but the sampled upper-center region's horizontal gradient fell from 1.9068 to 1.1234 and distinct RGB triplets from 728 to 434; near-white occupancy slightly increased, 76.20% to 76.68%. The bright background looked smoother in the inspected sheet. These metrics do not prove which texture is artistically correct, but they reject the claim that fewer exact whites automatically means more preserved detail. Do not turn off recovery globally based on endpoint counts.

### Synthetic controls: useful findings and limits

Fixtures were explicit BT.2020/PQ float RGB with controlled metadata. Same-evaluation taps captured input float, pre-plugin RGB16, native RGB16, sRGB float, and final RGB8. The independent BT.1886-to-sRGB arithmetic oracle matched every native case within 1.46e-7 maximum absolute error, below its 2e-5 threshold. The synthetic reference's tapped and untapped outputs matched. This supports the conversion boundary and instrumentation; it does not certify libplacebo's artistic result.

| Control | Observed native-run result | Decision supported |
| --- | --- | --- |
| 100–4000-nit neutral ramp | Final white occupancy: reference 62.2818%, knee 1.0 31.4529%, spline 1.1719%. Red center-row unique codes: 35, 59, 127 respectively | Knee improves the tested ramp but does not solve its compression; spline retains more distinctions with a different rendition |
| Tiny 10,000-nit impulse on 100-nit background | 99.995 and 100 produced different output; both retained one white impulse pixel. Center-row code span changed 4 → 69 | Absolute-maximum mode can change the surrounding rendition; white-pixel count alone misses it |
| Broad 10,000-nit patch | Both percentiles retained 6.25% white area and matching reported center-row metrics; whole outputs were not byte-identical | No material endpoint benefit demonstrated on this fixture; do not call it exact equivalence |
| Explicit scene metadata with impulse | Both percentile outputs were byte-identical | Percentile is not an unconditional control over output under every metadata situation |
| Understated versus true static ramp metadata | White occupancy 96.0983% versus 62.2665% | Bad peak policy can be harmful; true static metadata alone is not sufficient to eliminate compression |
| Saturated patches with knee 1.0 | Any-channel endpoint area: perceptual 62.5015%, softclip 50.9399%, darken 30.5862% | Gamut policy matters separately; none removes every saturated endpoint |
| Already-clipped source ramp | Flat source region remained unrecoverable | Tone mapping cannot reconstruct absent source detail |
| Extended encoded RGB stress values | Distinct negative values collapsed to zero and values above one collapsed to 65535 before the plugin | Confirms a bounded integer-input loss mechanism for invalid/extended RGB; its relevance to real decoded samples remains unproven |

The ramp's native rows include reversals, and knee 1.0 has three final8 red-channel reversals; disabling recovery removes those final8 reversals in this fixture. These measurements include the renderer's full spatial processing and quantization. They do not establish that the isolated analytic tone curve is nonmonotonic. A spatially uniform patch series and explicit dithering/recovery controls would be needed to assign that cause.

Fresh native logs did not provide numeric effective-peak traces, including in synthetic runs. The impulse results establish output sensitivity. The detector's exact histogram
estimate and numerical precedence remain unobserved. HLG was deliberately deferred until its OOTF/system-gamma and display assumptions are specified. Synthetic PNGs are convenient previews without an explicit sRGB chunk; numerical adjudication used the saved arrays.

### Accepted next work, rejected shortcuts, and evidence access

1. BT.2390 opt-in: expose a curve-specific BT.2390 knee control or documented highlight-preserving policy, then validate a larger set of actively difficult scenes. Keep baseline available. A global default switch requires further evidence.
2. Gamut mapping: evaluate softclip with the chosen shoulder on more saturated real scenes, including hue/saturation and local texture checks. Do not silently bundle gamut changes into the knee conclusion.
3. Peak diagnostics: record supplied metadata, selected authority, detector settings, and the effective peak where the native interface can expose it. Do not label a supplied hint as a measured effective value. Compare static, scene, and measured policies with the same curve.
4. Spline: its highlight compression is stronger, with a real brightness/contrast cost. A parameter comparison is more useful than rebranding it as a guarantee.
5. Output acceptance: use selected ROIs, near-white occupancy, local gradients, distinct output values, and visual comparison alongside both endpoint counts. More export precision cannot recover distinctions already lost in native output.

Rejected as general fixes: changing percentile to 100 alone; disabling contrast recovery alone; picking darken because its endpoint count is smallest; assuming `source_peak` is the effective peak; removing the final sRGB clamp; repeating already-fixed range/primaries/double-expansion changes. The fallback remains a separate hardening opportunity and was not exercised as a native alternative in this matrix.

Evidence is retained locally under the study directory (`generated/verification/2026-10-23/highlight-study`). Start with the real-media report (`generated/verification/2026-10-23/highlight-study/real-media/REPORT.md`), comparison viewer (`generated/verification/2026-10-23/highlight-study/real-media/comparison.html`), synthetic summary (`generated/verification/2026-10-23/highlight-study/controller/synthetic-summary.json`), and controller receipt (`generated/verification/2026-10-23/highlight-study/controller/adjudication-receipt.json`). These generated outputs remain local evidence outside the product fixtures. The [orchestration plan](../plans/2026-10-23-highlight-verification.md) records chat ownership and callback authorization. One child's callback was blocked by automatic approval review; its report was retrieved directly, so that did not prevent controller verification.

## Initial research findings and recommendation

The initial research recommended a controlled comparison on the corrected
pipeline, centered on BT.2390 knee 1.0 and explicit peak-selection policy. Prior
trials showed highlight changes with both. Neither had been adopted as a general
product default. The initial search found no completed representative real-content
study of gamut mapping or true-maximum peak detection.

The investigation covers several mechanisms:

- A shoulder can squeeze distinct highlights into almost identical values; subsequent RGB8 quantization can turn them all white.
- Individual color channels can reach their endpoints even when the complete pixel is not white.
- Metadata or measured scene peaks determine how much compression the curve applies.
- Gamut conversion can lose colored highlight detail independently of the luminance curve.
- The degraded fallback has its own explicit saturation threshold.

The initial priorities were:

| Priority | Action | Why it earns the next investigation |
| --- | --- | --- |
| 1 | Compare current BT.2390 knee 0.5 against 1.0, with everything else identical | Already helped the actual problem scenes; narrower change than replacing the whole transform |
| 1 | Make the effective peak source observable; compare automatic, measured, and explicitly controlled static peak policies | Prior native traces showed that `src_max=448` could produce an effective peak of approximately 285 or 1001 nits, depending on metadata selection |
| 2 | Compare percentile 99.995 against 100 on the measured-peak branch | Directly tests whether tiny bright features are intentionally omitted from the peak estimate |
| 2 | Compare perceptual gamut mapping with softclip and darken, after controlling curve and peak | No retained real-content challenger study found; especially relevant to colored highlights |
| 2 | Evaluate final sRGB8 highlight separation, alongside native16 | Existing evidence shows that counting exact native white alone misses visible flattening |
| 3 | Offer a documented highlight-preserving policy with curve-specific parameters | Most relevant controls exist internally but are not public configuration fields |
| 3 | Replace or make strict-mode refusal possible for the degraded fallback | Its formula can mathematically flatten a large range to white; unrelated to the confirmed libplacebo Kill Bill case |
| Later | Evaluate additional modern curves, richer local mapping, or another rendering backend | Higher cost and larger appearance changes; current evidence does not require replacing libplacebo |

Two practical cautions shape these recommendations. First, the browser sRGB and independent-still corrections are already implemented and should be retained. Second, **`highlight_guard` is spline at 180 nits, with the shared defaults. Its name does not represent a no-clipping guarantee.**

## What the current application actually does

The screenshot path resolves the selected preset and explicit color overrides, checks HDR source evidence, converts to RGB48, calls vs-placebo, converts the known BT.1886 destination into endpoint-relative sRGB, then writes the screenshot. Quality stills use a separate native mapper for each original source frame. Fast stills disable dynamic peak detection and share one node. Alignment previews now use the configured transform too, but quality previews retain sequence state, so they can differ from independently mapped screenshots. See the [settings/caller path][prepare], [native mapper][mapper], [conversion boundary][conversion], and [HDR guide][guide].

Current reference settings are:

| Setting | Value | Consequence for this investigation |
| --- | --- | --- |
| Curve / destination | BT.2390 / 100 nits | Baseline appearance; physical monitor calibration remains separate |
| BT.2390 knee offset | 0.5 | The value whose alternatives helped in prior studies |
| Destination black | 0.18 nits | Part of both native output and subsequent sRGB conversion |
| Dynamic peak detection | On in quality; off in fast | Does not by itself identify the effective peak chosen under automatic metadata |
| Percentile | 99.995 | Below the absolute-maximum setting |
| Gamut mapping | 1, perceptual | Existing gamut mapping policy |
| Metadata policy | 0, automatic | Dynamic metadata can matter even when peak detection is disabled |
| Dolby Vision use | Requested true | Does not establish full Dolby Vision reconstruction/rendering |
| Contrast recovery | 0.3 | An existing additional image transformation |
| Gamma lift | Off | Not responsible for the default-path example |
| Sequence smoothing | 45 frames | Relevant to sequence previews; fresh still nodes prevent cross-frame history |

These application values are defined in [TonemapSettings][types] and [presets][presets]. The application explicitly targets BT.709 primaries using the plugin's `dst_prim=3`.

### The public configuration is narrower than the internal settings

Public `[color]` accepts enable/disable, preset, speed, target, curve, gamma lift, and contrast recovery. It does **not** currently expose knee offset, percentile, gamut policy, metadata policy, source peak, or Dolby Vision policy. Unknown configuration keys are rejected. Internal `TonemapSettings.source_peak` exists, but the ordinary color resolver does not populate it from a public configuration field. See [ColorConfig][schema] and [resolution][prepare].

The local config color section (`config/config.toml:129`) explicitly contains `target_nits=100`, `tone_curve="bt2390"`, `gamma_lift=false`, and `contrast_recovery=0.3`. Explicit fields override preset values. Consequently, **using only `--tm-preset highlight_guard` with that configuration does not switch the actual curve to spline or target to 180.** This is an important confound when interpreting a preset trial. It is established by source/configuration inspection; it is not proof that a particular earlier user run encountered it.

For a reproducible comparison using existing controls, append explicit flags to the existing run command:

```text
--tm-speed quality --tm-curve bt2390 --tm-target 100
--tm-speed quality --tm-curve spline --tm-target 100
```

These are two alternative runs. They isolate the curve at one target, with the
other resolved controls held constant. To evaluate the named 180-nit preset under
this config, supply
`--tm-preset highlight_guard --tm-curve spline --tm-target 180 --tm-speed quality`.
That preset comparison changes both curve and target relative to reference. No
such run was executed in the initial research phase.

## What we have already tried

### Implemented corrections and existing options

| Work | Evidence / status | What it establishes and what it does not |
| --- | --- | --- |
| Initial curve presets, including `highlight_guard` | Present since `c4293723`; current preset remains spline / 180 nits / no gamma lift | Existing option. No retained controlled real-content acceptance specifically for this preset was found |
| Earlier HDR/range export repairs | `3c45a94f`, `7fe23ba0`, `f14118bf` | Historical repairs to HDR/export behavior, including avoiding repeated range expansion; retain the corrected range handling |
| Removed postprocessing contrast multiply/clamp | `7fe23ba0` | Replaced that older operation with native contrast recovery. Removing the old contrast clamp is already completed work; the separate fallback formula below still exists |
| Applied-transform reporting | `bc182b07` | Reports can distinguish requested settings from actual fallback/native transforms |
| Correct destination primaries | `44dc3ba7`; independent native check in `b7856f53` | Fixed erroneous BT.601/SMPTE-C selection to BT.709. Earlier diagnosis found this alone did not solve brightness |
| BT.1886-to-sRGB export and PNG declaration | `5c15cbf4` | Implemented output correctness. The retained porch control got slightly brighter after correct conversion; clipping remained |
| Independent mapper state for quality stills | `5c15cbf4`, retained harness `79c52a6c` | Prevents another requested frame's detector history influencing the still. Does not select a more protective shoulder |
| Experimental native mapper reuse | `e193e955`, default off and capability gated | Determinism/performance investigation; highlight-quality acceptance remains unproven |
| Fast metadata-based stills | `3117e850`, configuration in `7f7ef883`, verification `3be9edc3` | Implemented optional detector-off path. Not equivalent to forced HDR10-only metadata, and not guaranteed to preserve more highlights |
| Configured HDR previews | `1130d64e` | Preview now respects configured transform; quality preview/still temporal policy still differs |

Current code confirms the relevant implemented state. Historical verification scope and remaining platform/display gaps are recorded in the [verification ledger][ledger]; this report does not turn those old results into new passes.

### Actual highlight and color trials

The retained evidence includes the 18 October diagnosis (`generated/verification/2026-10-18/kill-bill-diagnosis/findings.json`), 20 October fixed-frame matrix (`generated/verification/2026-10-20/hdr-pro-handoff/diagnostic-summary.json`), metadata Experiment A (`generated/verification/2026-10-20/hdr-experiment-a/experiment-a-summary.json`), eight-scene color study (`generated/verification/2026-10-20/hdr-color-study/study-summary.json`), cross-title assessment (`generated/verification/2026-10-20/hdr-color-study/mastering-audit/assessment.json`), and output/history controls (`generated/verification/2026-10-20/hdr-color-study/output-history-controls/summary.json`). Much of it lives under ignored `generated/verification`, so those receipts remain local evidence outside the tracked release tests.

| Trial already performed | Recorded result | Interpretation today |
| --- | --- | --- |
| Strip Dolby Vision RPU | Did not resolve the original porch problem; one later automatic/dynamic trial increased white occupancy | Do not assume disabling DV is the solution |
| Set `src_max=1000` alone | Did not resolve tested highlights in the initial diagnosis | A constructor value alone does not prove the native mapper used that peak |
| Disable dynamic detection / use controlled static branches | Later controlled branches reduced white occupancy; several early toggles did not | The exact metadata branch and retained props matter; these are not interchangeable experiments |
| BT.2390 knee 1.0 and 2.0 | Large reductions in porch/close-up white occupancy | Candidate evidence at the time; effects vary by scene |
| Knee 1.5 | Included in the later eight-scene study | Already tried; no need for another unconstrained broad sweep |
| Spline | Strong reductions on problem highlights, with changes elsewhere | Already tried at 100 nits. This does not validate the 180/203-nit presets or prove universal fidelity |
| Reinhard | Included in the initial diagnostic script | Already screened; no broad acceptance evidence found |
| Contrast recovery 0 versus 0.3 | Modest improvement, substantial white areas remained | Secondary control with a smaller effect than knee or metadata changes |
| CLL/FALL integer-to-float conversion only | Native16 and RGB8 outputs byte-identical on the porch automatic/RPU branch | Not the leading cause there; does not validate types on every other metadata path |
| Zero smoothing | Selected real-media histories initially matched; later epsilon investigation found detector-metadata history dependence even where native16/RGB8 pixels matched | Insufficient to guarantee state independence; this is not a claim that those matching images visibly differed. Current fresh-per-frame mapper is the stronger implemented solution |
| Correct output conversion / tags | Numerically validated; tags alone did not change pixel data | Already corrected. Do not merely relabel or double-convert samples |
| Multiple titles / mastering differences | Substance, Spider-Verse, Immaculate plus Kill Bill examined | Some differences predate mapping; an older SDR master is not a ground-truth image |

The October 20 spline study omitted the generic curve parameter; a separate fixed-frame check compared omission with 0.5 and got the same images. Both are materially different from changing a preset and leaving an explicit BT.2390 override in place.

### The historical numbers worth retaining

These historical sampled RGB code statistics precede the final sRGB and
independent-still corrections. They provide no calibrated luminance or fidelity
measurement. The fixed-frame study sampled below the overlay.

| Historical variant at 100-nit target | Porch, HDR frame 12382: all-channel RGB8 white | Close-up, HDR frame 14943: all-channel RGB8 white |
| --- | ---: | ---: |
| Reference BT.2390, knee 0.5 | 7.1934% | 3.8005% |
| BT.2390, knee 1.0 | 0.7942% | 1.3545% |
| BT.2390, knee 2.0 | 0.3288% | 1.0611% |
| Reference, contrast recovery disabled | 6.6864% | 3.2249% |
| Controlled HDR10 static branch | 0.1467% | 0.5877% |

Source: fixed-frame matrix (`generated/verification/2026-10-20/hdr-pro-handoff/diagnostic-summary.json`). The initial spline porch result was approximately 0.000308%, but this reduction accompanied a different rendering of midtones and shadows. Fewer white pixels alone does not establish greater fidelity.

In Experiment A (`generated/verification/2026-10-20/hdr-experiment-a/experiment-a-summary.json`), changing **only `metadata=0` to `metadata=2`**, while retaining the RPU and detector setting, changed the native trace from approximately **285 → 100 nits** to **1001 → 100 nits**. Porch RGB8 white occupancy changed from **7.1934% to 0.001233%**. It also lowered the average code value. This demonstrates a metadata-policy effect; it does not demonstrate that 1001 nits was the correct artistic or physical source peak.

A later provenance assessment found the porch's RPU scene peak around 284.85 nits agreed with a measured PQ-base luminance maximum around 285.04 nits. Thus **a badly understated scene-luminance peak was not demonstrated for that case**. Forcing a larger range can relieve a steep shoulder even when the smaller measured peak is meaningful. These observations support evaluating shoulder shape and color-volume behavior.
They provide no basis for labeling the DV metadata corrupt. Cross-title/provenance assessment (`generated/verification/2026-10-20/hdr-color-study/mastering-audit/assessment.json`)

The output conversion control (`generated/verification/2026-10-20/hdr-color-study/output-history-controls/summary.json`) changed porch white occupancy from 7.1934% to 7.3872%. It establishes why the sRGB correction cannot be advertised as the highlight fix.

There is also an important reconciliation of earlier wording: the porch had **zero all-channel native16 endpoint occupancy**, but **5.4691% any-channel native16 endpoint occupancy** in the later audit. These statements are compatible. Neither permits the blanket conclusion that no native component clipped. Exact endpoint occupancy by itself still does not locate where saturation occurred.

### What has not been established

I found no completed representative real-content acceptance study for percentile 100, perceptual versus softclip/darken gamut mapping, a protective spline-contrast sweep, final RGB8 dithering, BT.2446A/ST2094 alternatives, or a replacement fallback. Synthetic controls using `gamut_mapping=0` exist, but were designed to isolate output conversion; they are not gamut-quality comparisons. Proposed gamut experiments in old handoffs are not completed experiments.

The retained studies also do not establish a generally accepted new default, a calibrated physical display result, or equivalence to an independently graded SDR release.

## Further work proposed by the initial research

### 1. Promote BT.2390 knee 1.0 from historical candidate to a current-pipeline decision

The initial evidence supported a narrow appearance change. Compare 0.5 with 1.0
first and retain 2.0 as a diagnostic bound. Judge each result by its measured
separation and appearance.

The pinned libplacebo implementation gives BT.2390 a parameter default of 1.0 and range 0.5–2.0. Its compatibility parameter means **knee offset for BT.2390, spline contrast for spline, and Reinhard contrast for Reinhard**. The same numerical change therefore has different meanings across curves. [Pinned curve implementation](https://raw.githubusercontent.com/haasn/libplacebo/a7a18af88ff0a17c04840dcb3246047bb6b46df3/src/tone_mapping.c)

The application currently sends `settings.knee_offset` as `tone_mapping_param` for all three curves. Any implementation should make this curve-specific, or omit the generic parameter when the selected curve should use its own default. Blindly changing the shared 0.5 to 1.0 would also change spline and Reinhard behavior. [Native kwargs][mapper]

The label `bt2390_spec` should retain its intentional distinction if a tuned reference policy is added. Upstream documents 0.5 as spec-defined behavior and 1.0 as its own default; neither name alone proves best visual preservation for our screenshots. [libplacebo options](https://libplacebo.org/options/#knee_offset0520)

### 2. Separate peak detection, metadata preference, and actual effective peak

Today the report's resolved source peak is the application's `src_max` selection: configured internal value, otherwise MaxCLL, otherwise 1000. It is not a measured record of the exact per-frame peak actually used inside libplacebo. [Peak resolver][peak] [Applied facts][types]

The pinned plugin reads frame metadata, can populate scene statistics from `PLSceneMax/Avg`, and reads RPU-derived values. A positive explicit `src_max` also prevents its ordinary mastering-display maximum lookup. Its RPU processing and full DV signal mapping are distinct paths; our RGB HDR10 path is not the YUV `src_csp=3` path. [Pinned plugin source](https://raw.githubusercontent.com/Lypheo/vs-placebo/3cfd23f257ecb62b0cbd81eaaca092e18ae8e579/src/tonemap.c)

Libplacebo's nominal-luminance resolver initializes static values and can replace them with compatible dynamic values under automatic selection. Its HDR10 mode and automatic mode therefore need not choose the same maximum. [Pinned metadata selection](https://raw.githubusercontent.com/haasn/libplacebo/a7a18af88ff0a17c04840dcb3246047bb6b46df3/src/colorspace.c)

Recommended work:

1. Disclose the distinction between the supplied source-peak hint and the measured/metadata-derived effective peak. Where a native value cannot be observed reliably, say it is unavailable.
2. In diagnostics, retain input MaxCLL, mastering maximum, exact-frame RPU presence, selected metadata policy, detector state, and native effective-peak trace together.
3. Compare automatic metadata, a branch with verified measured-peak authority, and a controlled static branch at identical curve settings. Confirm which branch actually ran.
4. Only then consider a public peak policy or explicit override. Specify whether an override is a hint, floor, or authoritative replacement.

Do not simply substitute mastering-display maximum for content peak: those describe different quantities. Likewise, stripping RPU and changing metadata policy together cannot identify which change helped. For a true no-RPU control, remove the RPU property in an isolated diagnostic graph and verify the native result; do not trust a flag name alone.

Fast mode is not an answer to this question by itself. It disables detection while retaining automatic metadata. It may still use dynamic scene metadata. The historical 1001-nit Experiment A result is not a prediction of `--tm-speed fast`.

### 3. Try true-maximum measurement, but only where measurement has authority

Compare percentile 100 with the existing 99.995 after confirming that the measured statistics actually drive the mapper. Upstream defines 100 as brightest-pixel measurement; lower values discard the upper histogram tail. This trades protection of tiny highlights against a potentially darker rendering driven by a few extreme pixels. [libplacebo peak options](https://libplacebo.org/options/#peak_percentile001000)

As a scale illustration, 0.005% of a 3840×2160 image is about 415 pixels. That is not a prediction of the number clipped: histogram bins, image content, and metadata authority affect the result. It does explain why a numerically small percentile adjustment can matter to sparks, stars, reflections, and tiny lamps.

This is a good new experiment for bright HDR10-only sources. It may have little or no effect on an RPU-driven frame. It also cannot repair a shoulder that compresses a large bright region into a few output codes despite a correct peak.

A 2026 upstream investigation of overblown highlights likewise identified interacting metadata, detector-history, percentile, and gamut factors. That incident concerned FFmpeg's integration, so its fix is not automatically a Frame Compare fix. [Upstream issue 358](https://github.com/haasn/libplacebo/issues/358)

### 4. Evaluate gamut mapping separately from luminance mapping

Use perceptual as the baseline, softclip as the first challenger, and darken as a second targeted challenger. Include neutral highlights and saturated reds, blues, greens, fire, neon, and stage lights. Track hue/saturation as well as brightness and texture. A gray ramp alone cannot validate this decision.

The pinned plugin exposes these gamut modes, as well as `show_clipping` and `visualize_lut` diagnostics. Those diagnostics are useful but cannot detect every loss caused by subsequent RGB8 quantization. [Pinned vs-placebo API](https://raw.githubusercontent.com/Lypheo/vs-placebo/3cfd23f257ecb62b0cbd81eaaca092e18ae8e579/README.md)

Do not treat gamut `clip` as a preservation strategy. Do not optimize only for zero clipped components: desaturating or darkening everything can improve that count while harming the comparison. Apply the same chosen presentation policy to both sources; per-source beautification would make encode differences harder to interpret.

If the existing modes show a clear tradeoff that cannot be balanced, richer gamut constants are a later integration task. The current wrapper does not expose every modern libplacebo option, so copying an mpv setting into our configuration will not make it work.

### 5. Retain contrast recovery as a secondary, measurable choice

We have already tried zero. The historical improvement was real but much smaller than knee/metadata changes. Re-test it in combination with the shortlisted curve.

In the pinned shader, contrast recovery mixes a base tone map with a detail-restored value and clamps to the destination range. It can therefore affect endpoint behavior; its name does not mean it recovers information already lost earlier. [Pinned color-mapping shader](https://raw.githubusercontent.com/haasn/libplacebo/a7a18af88ff0a17c04840dcb3246047bb6b46df3/src/shaders/colorspace.c)

Use 0 and 0.3 first, then an intermediate value only if useful. Inspect halos, fine texture, bright edges, and grain. Avoid adding sharpening or gamma adjustment as a proxy for highlight restoration.

### 6. Preserve distinctions through the final 8-bit export

The native mapper returns 16-bit integer samples, followed by float sRGB conversion and RGB8 output. The Pillow preparation route uses `resize.Point(format=RGB24)` without an explicit dithering choice. [Encoder boundary][encoder]

Investigate deterministic spatial dithering at this final quantization boundary and retain 16-bit diagnostic images or arrays alongside ordinary PNGs. These are separate goals:

- Dithering can represent small differences statistically and reduce banding.
- A higher-precision diagnostic identifies whether detail existed before RGB8.
- Neither can restore detail already flattened by the source, tone curve, gamut mapping, or native integer output.

Do not use animated/randomized dithering for independent comparison screenshots. A stable pattern and documented policy are necessary to avoid artificial differences. A 16-bit PNG option might be useful for inspection/export, but its actual browser/display path would need verification; extra storage precision is not proof of extra visible precision.

The sRGB function's endpoint clamps should not simply be removed. It receives the plugin's already-bounded integer SDR output. Moving or removing that clamp cannot recover detail lost upstream.

### 7. Address the degraded fallback as a separate correctness problem

The fallback computes, per component, approximately:

```text
y = clamp(2*r*x / (1 + r*x), 0, 1)
r = source_peak / target_nits
```

For nonnegative input, `y` reaches 1 when `x >= 1/r`, or `x >= target_nits/source_peak`. At 1000/100, every component at or above 0.1 saturates; at 448/100, the threshold is about 0.2232. These thresholds follow directly from the expression and were calculated
without a new runtime measurement. [Fallback implementation][fallback]

Its conversion helper does not explicitly linearize PQ/HLG and perform the complete HDR-to-BT.709 rendering operation before this expression. It is a deliberately degraded path and should not be represented as equivalent to the requested curve. Current reporting already distinguishes it.

Recommended product choices are either a validated HDR-aware fallback, or an explicit strict rendering option that refuses degraded output. Replacing only the formula with another rational curve would leave transfer, primaries, and color handling unresolved. This is worthwhile independently, but the retained Kill Bill problem was confirmed on libplacebo, so it does not explain that incident.

### 8. Consider more curves only after the narrower controls

Spline is already available and already studied. A bounded spline-contrast comparison is more targeted than adding many names. Upstream describes lower spline contrast as favoring highlight retention at the expense of midtone contrast. [Spline controls](https://libplacebo.org/options/#spline_contrast0015)

BT.2446A and ST2094-10/40 are reasonable later challengers supported by the underlying plugin, but not by the application's current three-value curve selection. They need configuration, reporting, validation, and native-path work. BT.2446 is specifically a report about HDR/SDR conversion methods and their evaluation; being standards-based does not make a particular output an artistic ground truth. [ITU-R BT.2446-1](https://www.itu.int/dms_pub/itu-r/opb/rep/R-REP-BT.2446-1-2021-PDF-E.pdf)

A new local tone mapper or custom shader could preserve spatial contrast differently, but introduces risks such as halos, altered grain, and content-dependent appearance. It should be considered only if current curves, peak policy, and gamut handling cannot meet a defined acceptance target. There is no evidence here that a wholesale backend replacement is necessary.

### 9. Check pre-mapping loss and display behavior when symptoms point there

Our RGB48 input conversion is compatible with the plugin and avoids early RGB8 reduction. However, integer RGB can bound values before tone mapping. For extreme/saturated samples, compare decoder output with the actual pre-plugin RGB48 input to determine whether distinctions are already gone. A YUV16 plugin-input experiment would change conversion/chroma/DV assumptions and requires separate proof; it should not be adopted solely to avoid one intermediate format.

For HLG, use a separate fixture with explicitly defined viewing/peak assumptions. For DV, distinguish an HDR-compatible base plus metadata from full reconstruction, especially enhancement-layer and non-HDR10-compatible cases.

For browser-only discrepancies, record browser, monitor profile, Windows HDR state, and SDR brightness setting. Compare decoded image values with actual display observations. Our target nits describes a transform. The browser's physical brightness depends
on its display environment. Existing SDR inputs also retain their current interpretation, so a separately mastered SDR comparison should not silently be treated as an output-transfer oracle.

## Experiment proposed by the initial research

The goal is to decide a protective default or opt-in policy without repeating every earlier study.

### Freeze the current baseline

Use this checkout's corrected sRGB boundary, explicit BT.709 destination, quality independent-still policy, gamma off, and one target. Record the actual source, frame, runtime/plugin identity, applied kwargs, and input metadata. Check for explicit config overrides. Use fresh output locations and preserve historical artifacts.

Start with the retained porch 12382 and close-up 14943, plus a dark control. Then reuse the earlier animation/dark-title samples and add the previously missing bright HDR10-only specular sample and an HLG control. Do not present re-rendered old frames as a completely new content-validation corpus.

### Separate the variables

| Stage | Comparison | Decision supported |
| --- | --- | --- |
| A | BT.2390 knee 0.5 vs 1.0, same automatic metadata | Effect of knee 1.0 after the pipeline corrections |
| B | Automatic vs measured vs controlled static peaks, same curve | Contribution of peak authority and curve compression |
| C | Percentile 99.995 vs 100 on a confirmed measured branch | Effect of the estimator on isolated highlights |
| D | Perceptual vs softclip vs darken on shortlisted settings | Contribution of gamut mapping to colored highlight loss |
| E | Contrast recovery 0 vs 0.3; then final-quantization controls if needed | Remaining detail, noise and endpoint tradeoffs |
| F | Current reference vs selected candidate vs spline at the same target | Generalization and appearance changes outside the highlights |

Avoid a full Cartesian sweep. Stop pursuing a control when it is proven inactive on the tested branch. Treat a deliberately larger static peak as a rendering choice. A more accurate
source measurement requires independent evidence.

### Capture useful measurements

Capture the same evaluation at pre-plugin input, native RGB16, corrected float sRGB, and final PNG. Where feasible, add a native effective-peak/LUT diagnostic. Avoid independent re-evaluations with different temporal histories masquerading as stage captures.

Measure separately:

- Any-channel and all-channel endpoint occupancy.
- Near-white occupancy and the number/separation of output codes within fixed highlight regions.
- Monotonicity and retained steps on known ramps.
- Local texture/contrast in bright cloth, clouds, skin shine, reflections, and colored lights.
- Midtone/shadow changes, hue changes, halos, and banding.
- Order independence for the selected still policy.

Include synthetic PQ ramps with peaks below and above metadata, tiny bright impulses, broad bright patches, saturated colors, and a source that is already clipped. Add missing, inaccurate, and type-varied metadata controls. Define HLG separately.

Acceptance requires meaningful highlight distinctions with acceptable midtone and
color changes. Zero white pixels is not a valid standalone target: legitimate white and already-clipped source regions can remain white. Matching the older SDR release is also not a valid standalone target.

Reuse the existing [native integration tests][integration], [media tests][media-tests], and [same-evaluation checkpoint harness][probe] where appropriate. They already establish important conversion and request-history contracts; they do not currently constitute broad highlight-quality acceptance. A production change would also need the affected runtime/platform verification from the repository runbook. That was the scope of the initial research pass. The subsequent native investigation is documented at the start of this report; its limited diagnostic acceptance does not establish a production or packaged-platform pass.

## Product direction proposed by the initial research

The initial research proposed this sequence:

1. Make peak-source reporting unambiguous and add a diagnostic path for the active curve/peak.
2. Evaluate a tuned BT.2390 knee-1 policy against the corrected reference pipeline.
3. If it passes, expose curve-specific controls and preserve an explicitly named spec-oriented option.
4. Add a tested highlight-preserving preset only after its peak, gamut, and export behavior are defined. Avoid promising that every source will be unclipped.
5. Address fallback behavior separately, and add higher-precision/dither options only where the staged evidence shows a benefit.

This preserves the substantial fixes already made while tackling the still-open artistic and numeric behavior. The largest historical improvements came from the shoulder and peak-selection policy. The remaining areas for investigation are gamut handling, true-maximum measured peaks, and final-output detail retention.

## Evidence boundaries and source index

The initial research phase used read-only code/history inspection, local JSON/text evidence, and primary-source web research. That phase decoded no source media, rendered no candidate, performed no browser/display acceptance, and changed no configuration or default. The later native investigation and opt-in implementation are recorded above. Missing or inaccessible historical evidence cannot prove an experiment never happened; “not found” above means no completed result was found in the inspected repository and retained targeted evidence.

The packaged runtime pins examined are vs-placebo `3cfd23f257ecb62b0cbd81eaaca092e18ae8e579` and libplacebo `a7a18af88ff0a17c04840dcb3246047bb6b46df3`, corroborated by Docker and Windows manifest declarations. Current online options may exceed the pinned wrapper's API; recommendations distinguish existing application controls, wrapper controls, and future integration work.

Local primary evidence:

- [Current settings and screenshot caller][prepare], [native mapper][mapper], [presets][presets], [types][types], [public configuration][schema].
- [Output conversion][conversion], [source-peak resolver][peak], [fallback][fallback], [encoder][encoder].
- Original Kill Bill diagnosis (`generated/verification/2026-10-18/kill-bill-diagnosis/findings.json`), fixed-frame matrix (`generated/verification/2026-10-20/hdr-pro-handoff/diagnostic-summary.json`), metadata Experiment A (`generated/verification/2026-10-20/hdr-experiment-a/experiment-a-summary.json`).
- Color study (`generated/verification/2026-10-20/hdr-color-study/study-summary.json`), cross-title/mastering assessment (`generated/verification/2026-10-20/hdr-color-study/mastering-audit/assessment.json`), output/history controls (`generated/verification/2026-10-20/hdr-color-study/output-history-controls/summary.json`), sRGB implementation results (`generated/verification/2026-10-20/hdr-color-study/srgb-implementation/summary.json`).
- [Verification ledger][ledger], [HDR guide][guide].

[prepare]: ../../src/frame_compare/render/prepare.py
[mapper]: ../../src/frame_compare/vs/tonemap_libplacebo.py
[presets]: ../../src/frame_compare/vs/tonemap_presets.py
[types]: ../../src/frame_compare/vs/types.py
[schema]: ../../src/frame_compare/config/schema_models.py
[conversion]: ../../src/frame_compare/vs/tonemap_conversion.py
[peak]: ../../src/frame_compare/vs/tonemap_conversion.py
[fallback]: ../../src/frame_compare/vs/tonemap_fallback.py
[encoder]: ../../src/frame_compare/render/encoders.py
[ledger]: 2026-10-17-outstanding-verification.md
[guide]: ../guides/hdr-tonemapping.md
[integration]: ../../tests/vs/test_integration.py
[media-tests]: ../../tests/e2e/test_media_tonemap.py
[probe]: ../../tools/hdr_still_probe.py
