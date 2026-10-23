# Unit B: boundary audit and synthetic preparation

Prepared 2026-10-23. Child chat `01a16827-719d-72e3-9498-b00fee3ca22a`.
Parent `01a16815-04a8-7d02-96f6-456f0dfcb02f`, local host.
Completion scope: source audit, runnable diagnostic preparation, pure numeric validation.
**No VapourSynth import, Vulkan initialization, media decode, or native test/render was executed.**
The parent retains acceptance and renderer-lease decisions.

## Source and receipts

HEAD remained `f1d3b9bf4c3406e3d0cddbfbbc536e0ac8a9279e`; no source/config drift.
`numeric-verified/numeric-results.json` records SHA256 of seven relevant product
owners and this harness, Windows `10.0.19045`, Python `3.13.7`, and the exact
`.venv/Scripts/python.exe` executable. This is the Python runtime observed;
native plugin identity/signature is deliberately unobserved until execution.

`command-receipt.json` records the exact numeric command (exit 0, all 19 checks
passed), and a deliberate native invocation without a lease (exit 2, no output
directory created). The latter fails before native imports. Earlier `numeric-01`
and `numeric-final` receipts are retained intermediate runs; use `numeric-verified`
for the final harness identity. `status-before.txt` and `status-after.txt` preserve
working state. All Unit B writes are inside this synthetic root. Existing plans,
research, historical evidence, product code, and config were untouched.

## Boundary findings

1. **Peak hint is not effective peak.** Product `resolve_source_peak` uses internal
   source_peak, then MaxCLL, then 1000; its report records that choice. Float/string
   MaxCLL can be converted to integer by `props.get_optional_int_prop`. The native
   wrapper separately reads float props. Positive supplied src_max suppresses its
   mastering-maximum lookup. PLSceneMax with one component represents CIE Y;
   three components represent MaxRGB. Missing mastering-primary arrays trigger
   a P3 fallback. Fixtures therefore supply explicit BT.2020 mastering primaries
   even in the "missing" luminance-metadata branch. See pinned
   [wrapper lines 218–283](https://raw.githubusercontent.com/Lypheo/vs-placebo/3cfd23f257ecb62b0cbd81eaaca092e18ae8e579/src/tonemap.c).
   This is a source finding, not a claim that real-media primaries were missing.

2. **Metadata preference matters.** The pinned nominal-luminance resolver starts
   with static information, then compatible MaxRGB or CIE-Y metadata can replace
   it. Automatic selection accepts either; CIE-Y comes after MaxRGB in this
   resolver. Missing values have transfer-dependent defaults. Thus percentile
   output equivalence does not prove that the histogram is ineffective: the
   selected metadata could dominate. The harness intentionally calls the
   no-PLScene/no-RPU branch a *measured candidate*, pending native trace.
   [Pinned resolver, lines 737–804](https://raw.githubusercontent.com/haasn/libplacebo/a7a18af88ff0a17c04840dcb3246047bb6b46df3/src/colorspace.c).

3. **The parameter is not universally a knee.** Product
   `build_libplacebo_tonemap_kwargs` passes settings.knee_offset as
   tone_mapping_param for all three supported curves. The pinned implementation
   maps it to BT.2390 knee_offset, spline_contrast, or reinhard_contrast. The
   spline case is therefore named `spline-contrast05`, not "spline knee .5".
   [Pinned parameter mapping, lines 71–90](https://raw.githubusercontent.com/haasn/libplacebo/a7a18af88ff0a17c04840dcb3246047bb6b46df3/src/tone_mapping.c).

4. **Stage separation is necessary.** Product RGB48 conversion precedes native
   mapping. Its integer bounds can erase distinct extended RGB codes. Case 17
   measures that with an explicitly invalid/extended encoded-PQ stress input;
   it is not proof of decoder/YUV clipping on real media. The valid fixtures
   remain inside PQ's 0–10000-nit domain. A real-media YUV-to-RGB48 loss claim
   still needs original decoder-plane samples and corresponding float conversion.
   Product owners: `vs/tonemap_libplacebo.py:46`,
   `vs/tonemap_conversion.py:133`, `render/encoders.py:343`.

5. **Native16, sRGB float, and final8 answer different questions.** The source
   converts bounded native16 through endpoint-relative BT.1886-to-sRGB, then
   Point to RGB24. Six distinct native codes 65530–65535 produce six distinct
   calculated sRGB values but one rounded RGB8 code (255). This is arithmetic
   proof of possible merging, not an observation of zimg's current dithering.
   Do not remove endpoint clamps to claim recovery. The native harness compares
   its float checkpoint against independently expressed absolute BT.1886 and
   sRGB arithmetic with tolerance 2e-5.

6. **Colored endpoints and detail restoration need separate scrutiny.** Any-channel
   saturation can be 100% while all-channel white is 0%. Gamut changes require
   channel/hue/brightness inspection, not just white occupancy. Pinned contrast
   recovery mixes mapped low-frequency and high-frequency values and clamps to
   destination bounds; it cannot restore distinctions already lost in input.
   [Pinned shader, lines 1829–1869](https://raw.githubusercontent.com/haasn/libplacebo/a7a18af88ff0a17c04840dcb3246047bb6b46df3/src/shaders/colorspace.c).

7. **Fallback cutoff is in encoded component space on RGB PQ input.** Source
   `vs/tonemap_fallback.py:51` evaluates clamp(2rx/(1+rx),0,1) without explicit
   PQ linearization. For positive r, saturation starts at x=1/r. At target100,
   peaks448/1000/4000 give thresholds .2232142857/.1/.025. Independently decoding
   those PQ codes gives approximately 3.48981/.324566/.0135721 nits. This makes
   the encoding-domain limitation more concrete than saying "10% saturates".
   These are arithmetic predictions for RGB PQ, not measured fallback frames
   or an explanation of the confirmed libplacebo problem scene. HLG differs.

## Fixtures and metric sensitivity

Fixtures are deterministic 256×256, one frame, full-range PQ/BT.2020 RGB except
the explicitly labeled extended-code stress input. `numeric-verified/fixtures.json`
contains dimensions, float32 RGB hashes and summaries; `highlight_probe.py`
contains the complete compact definitions. Numeric generation imports no product
functions. ST2084 coefficients are expressed independently and checked against
100-nit (.5080784215) and 1000-nit (.7518270962) reference codes, endpoints,
monotonicity and round trips.

- Neutral steps cover black through 10000 nits; neutral ramp covers100–4000.
- One 10000-nit pixel occupies .00152587890625%; the broad64×64 patch occupies
  6.25%, both on100-nit backgrounds. These straddle the .005% tail, but histogram
  binning/downsampling still determines actual native behavior.
- Saturated primary/secondary patches and orange span100/400/1000/4000 nits.
- The clipped ramp is flat above1000; no mapper can recover its original ramp.
- Missing luminance metadata, understated400-nit static metadata, and explicit
  scalar PLScene400 controls share corresponding pixel recipes.
- A flattened .9 ramp has zero white pixels but zero retained rises/span. The
  normal ramp has255 rises; restoring it restores the metric. A one-channel
  saturation control detects8/8 any-channel endpoints and0/8 all-channel whites.

HLG is intentionally deferred: choose scene-linear normalization, reference
white, nominal display peak/black, system gamma and surround/OOTF assumptions
before assigning absolute-luminance expectations. PQ predictions do not carry over.

## Native execution handoff — not run

The machine-readable 18-case plan is `numeric-verified/case-plan.json`.
Start with01/02 (reference/knee1), then choose relevant branches. Cases05–10
separate impulse/broad and scene metadata;11/12 test understated/controlled
static;13–15 compare gamut;16 checks source clipping;17 checks pre16 loss;
18 isolates recovery against02. Each case uses a fresh process and source frame.

After an explicit native lease, from the repo root:

```powershell
.venv/Scripts/python.exe -B generated/verification/2026-10-23/highlight-study/synthetic/highlight_probe.py native --case 01-reference --renderer-lease --output generated/verification/2026-10-23/highlight-study/synthetic/native-01
```

Select another exact case ID and fresh directory for another case. The driver
enforces a180-second child timeout, captures stdout/stderr and invocation exit,
and refuses overwrites. No installs or media files are required. Native mode
requires the existing environment's VapourSynth, placebo, NumPy, Pillow and
product imports. A native import failure is an error in stderr, never a skip/pass.

The harness calls current product apply_libplacebo with an isolated core proxy
and a restored context-manager patch around pre-conversion. Pre16/native16/
sRGB-float tokens propagate into the final8 frame; selected arrays all belong
to that dependency evaluation. Extra helper evaluations may occur; counters
are diagnostic, not proof of native draw-call count. Native trace is enabled
at log_level6 in the proxy. Case01 additionally compares final8 against a fresh
uninstrumented product apply call; failure stops acceptance. This extra evaluation
is solely an equivalence check, not the source of checkpoint arrays.

Outputs: `capture/checkpoints.npz` holds input_float/pre16/native16/srgb_float/
final8 CHW arrays; `final.png` is final8; `result.json` holds plugin identity,
kwargs, settings, tokens, hashes, endpoints, center-row monotonicity/uniqueness,
and fixed interior patch means. `native-log.json` and stderr preserve trace.
`status=captured` means acquisition, **not visual-quality acceptance**. Inspect
effective peak in trace; if absent report unavailable and do not substitute src_max.
Native API compatibility, token propagation, equivalence, and image outcomes remain
unverified until the first leased run.

## Decisions for controller / critique of A

The A matrix is appropriately bounded, but should not rank candidates only by
whole-frame white counts. Fix regions and inspect retained highlight separations,
midtone changes and colored patch behavior. Integer-native noise/dither can
increase unique-code count without restoring source detail; use spatial structure
and patch/row summaries too. A synthetic lower white count is not artistic fidelity.

Do not assume no-RPU/no-PLScene makes percentile authoritative without a trace.
Keep actual float metadata types and mastering primaries visible. Do not confuse
the generic parameter's spline meaning with BT.2390 knee tuning. A pre16 boundary
observation cannot by itself establish decoder loss. No global-default or fallback
replacement recommendation is accepted here; these diagnostics prepare that decision.

The original human callback authorization was retrieved from the parent's actual
userMessage `01a16823-2547-7133-ab5c-e6627b72b9a0` in turn
`01a16823-24fc-7341-808e-2b5b5e01cabe`, before the completion callback.

Callback delivery was BLOCKED by automatic approval review twice, including
after retrieving and displaying the actual human userMessage again. The reviewer
classified read_thread evidence as untrusted and required explicit trusted
authorization for the exact user-visible cross-thread send. No callback was
delivered; no workaround was attempted. The parent can retrieve this report.
An ancillary attempt to read the global orchestration skill returned filesystem
access denied (exit1); it did not affect the locally completed diagnostic scope.
