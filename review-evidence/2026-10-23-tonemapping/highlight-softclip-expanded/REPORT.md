# Expanded softclip evidence

Executor chat `01a16827-6663-7cb1-911f-a4a3e2d9fc86`, 23 October 2026.
Controller `01a16815-04a8-7d02-96f6-456f0dfcb02f` owns acceptance and production work.

## Scope and outcome

Compared knee1/perceptual1 against knee1/softclip2 on five additional retained
scenes across three titles. Four scenes across two titles show active gamut changes:
two animation endpoint stress scenes, and two live-action saturated-background,
skin, fabric and jewelry scenes. These are **not four demonstrated highlight-fidelity
improvements**: the live-action scenes have no full-picture sampled endpoints in
either result. Immaculate candlelight is an inactive control and is not counted.

Twelve native case processes completed with exit0, including uninstrumented parity
and the actual new public-config resolver. A thirteenth optional case timed out;
its paired case was not attempted. Doctor exit0; pure image positive assertion exit0;
the deliberate baseline-as-softclip negative control exits1 for the intended reason.
No product files, user config, prior evidence, or controller report were edited here.

**All owned native children are reaped; owned scratch is removed.
NATIVE RESOURCE LEASE RELEASED. No further native work was started after release.**

## Source and runtime

HEAD remains `f1d3b9bf4c3406e3d0cddbfbbc536e0ac8a9279e`. The controller added
`highlight_preserve` while this task ran. Source start/end hashes and dirty status
are recorded per native case; `controller-source.diff` preserves the relevant
controller changes. The direct variants use immutable settings and did not depend
on preset resolution. Mapping/conversion/types/encoder hashes are stable within
every pair; decoded RGB16 input hashes match within every pair; resolved settings
differ only in gamut_mapping1 versus2. The preset/configured case is separate proof.

Current doctor succeeds on unmanaged Windows, R81/API4.3, vs-placebo2.0.4,
RTX5080/NVIDIA621.01. Plugin DLL SHA256s and native signatures are in every receipt.
The diagnostic log_level6 changes logging only. A fresh uninstrumented magenta
perceptual render has the same RGB8 hash as its tapped counterpart:
`6ea807c438d2bbafc022b3161d41272f25789d9b4c3264f42c83f86aa30a3e9a`.
Native16, sRGB float and final8 observations use the same evaluated frame as in A.

Selected scenes are exact retained excerpt frame72; these are excerpt-local IDs,
not claimed original-film frame numbers. Each receipt contains source/excerpt path,
absolute excerpt timestamp, source first-packet timestamp, container/DV profile,
source props/RPU hash and input array hash. Excerpt SHA256 is freshly checked
against the historical copy receipt; historical packet-identity work is not rerun.
Spider-Verse uses the strict MP4 copies retaining DV configuration.

## Results

`comparison.html` links full PNGs and labeled regional crops. `summary.json` has
full settings/provenance links and paired metrics. The table uses full-picture
stride4 samples, **different from the older y250-onward picture metric** retained
inside each original probe receipt. All means, gradients and endpoints are code
values, not calibrated luminance or fidelity scores.

| Scene / difficult content | Any RGB8=255 perceptual → softclip | Mean code8 perceptual → softclip | Components changing ≥2 codes |
|---|---:|---:|---:|
| Spider-Verse excerpt2 frame72; magenta lights, bright neutral character | 9.2760% →1.6003% | 76.14 →77.97 | 35.88% |
| Spider-Verse excerpt3 frame72; blue light, faces/skin | 0.5997% →0.00625% | 58.61 →59.01 | 23.12% |
| Substance excerpt2 frame72; orange/red background, hand, white robe | 0% →0% | 90.76 →90.54 | 18.49% |
| Substance excerpt3 frame72; red background, face, reflective jewelry | 0% →0% | 63.49 →63.46 | 4.06% |
| Immaculate excerpt2 frame72; candlelight and dark subject | 0% →0% | 9.00 →9.00 | 0.00043% — inactive |

All-channel white is0 in all five full-picture sampled pairs. Thus this expansion
chiefly tests colored channel endpoints and collateral appearance changes.
Activity is explicitly defined as at least0.1% sampled components changing by2+
codes, with maximum4+codes. It identifies a real mapping effect, not quality.

Visual inspection covered the complete animation comparisons and labeled crops
for all four active scenes, including skin, fabric, colored lights and jewelry.
Softclip preserves more separation in the magenta light pattern and suppresses
hard blue endpoints. It also changes brightness/chroma: the magenta-region code
luma rises2.517 on average and channel spread falls2.240; its horizontal gradient
rises3.803 →4.382. The bright neutral-character crop's gradient rises6.682 →7.522.
These are consistent with local separation, but do not prove fidelity to intent.

In the blue-light patch, mean code luma rises2.688, channel spread falls2.531,
and gradient3.371 →3.443. The animated faces' mean code luma changes only+0.159,
with modest color changes visible under the colored lighting.

The Substance has a different tradeoff: the orange background gets slightly darker
(mean code luma−1.239) and more saturated by the channel-spread proxy(+4.598).
The red background in scene3 changes−0.547/+1.632 respectively. This is an active
color rendering change, not a removed endpoint failure. Skin and neutral fabric
are comparatively stable: hand mean code-luma−0.035, robe−0.131, face−0.020.
Hand/robe/face texture gradients are essentially unchanged. The corrected jewelry
crop contains one sampled perceptual channel endpoint (0.002249%) and none with
softclip; that tiny count is not used as a broad improvement claim. Jewelry mean
code luma−0.007 and gradient2.97944 →2.97903 are effectively stable.

This supports softclip as a promising candidate for very saturated scenes, with
visible color-volume tradeoffs. It does not establish a universal preferred gamut
policy. In particular, do not describe the Substance results as newly recovered
highlight detail, or count the inactive candlelight scene as success.

## Public config-to-native wiring

`stage2/spiderverse-2-72-configured/result.json` uses exactly:

```python
resolve_tonemap_settings(
    ConfigSchema(color=ColorConfig(preset=TonemapPreset.HIGHLIGHT_PRESERVE))
)
```

It produces BT2390,100 nits,knee1,perceptual1,recovery0.3 and exactly matches direct
knee1 RGB8. `summary.json` records both hashes and plain/tapped equality. This is
public-config resolution through actual native mapping, **not installed CLI E2E**.

## Failed optional case and remaining limits

Immaculate excerpt3 frame72 knee1 exceeded the150-second child timeout. The child
was killed/reaped by `subprocess.run`; owned scratch was verified by marker and
removed. Its stderr reaches index100%, while stdout includes native shader output
and ends mid-output. No completed image/result exists. The exact failure boundary
is unresolved; it must not be labeled an indexing-only failure or a quality result.
The corresponding softclip case was not attempted. `stage2/invocations.json` and
the failed case's raw stdout/stderr/scratch/cleanup receipts preserve the evidence.
No retry or further native render occurred after the resource lease release.

Numeric effective peaks remain unavailable on these fresh-still graphs. Auto
metadata and original RPU were retained; no alternate peak authority is inferred.
There is no calibrated display, full DV reconstruction, separately graded SDR
golden, Docker/package acceptance, or performance result. Controller owns final
adjudication and any default/public softclip decision.

## Independent repeat

From `C:/Software/video/frame-compare`, use a fresh output directory:

```powershell
$root = 'generated/verification/2026-10-23/highlight-softclip-expanded'
$repeat = 'generated/verification/2026-10-23/highlight-study/controller/softclip-magenta-repeat'
.venv/Scripts/python.exe "$root/probe.py" run spiderverse-2-72:knee1 spiderverse-2-72:knee1-gamut2 --out $repeat
.venv/Scripts/python.exe "$root/verify_pair.py" $repeat
.venv/Scripts/python.exe "$root/verify_pair.py" $repeat --negative-control
```

Expected exits0,0,1. The final check deliberately substitutes perceptual as softclip
and must fail the endpoint-reduction assertion. Run `analyze.py` only on this owned
evidence root; it summarizes retained case receipts and does not initialize native
media. `artifact-manifest.json` hashes scripts, images, arrays, logs and reports.
