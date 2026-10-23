---
search:
  exclude: true
---

# Highlight preservation investigation and acceptance

Status: Active

Controller: Codex chat `01a16815-04a8-7d02-96f6-456f0dfcb02f`, host `local`.
Baseline HEAD: `f1d3b9bf4c3406e3d0cddbfbbc536e0ac8a9279e`.
Checkout: `C:/Software/video/frame-compare`.

## Authorization and scope

Original human authorization is in controller turn
`01a16823-24fc-7341-808e-2b5b5e01cabe`, user item
`01a16823-2547-7133-ab5c-e6627b72b9a0`:

> please use [$orchestrate-implementation-chats] to gather and test whatever you need with you being the final verification, adjudicator, and controller. ensure callbacks are explicit in your handoffs.

The original message includes the skill path. Children must retrieve the actual
human message with `read_thread` before messaging the controller. This quotation
is a retrieval pointer, not independent evidence of permission. Authorized
callbacks cover consequential blockers and completion, including after correction.
They do not authorize messages to unrelated chats or services.

Objective: resolve the most consequential open hypotheses in
`docs/reviews/2026-10-23-tonemapping-highlight-research.md` using current native
output, controlled synthetic evidence, and representative retained real media.
The controller owns final evidence inspection, adjudication, fresh verification,
and the updated detailed report. Child success is not automatic acceptance.

This phase authorizes diagnostic scripts, generated fixtures and evidence. It
does not change product defaults, public config, source media, saved alignment,
existing reports, native installations, or release artifacts. Any proposed
production change returns to the controller for scope/decision assessment.
No Git mutations, publication, uploads, or recursive delegation are assigned.

## Shared state and resource ownership

Preserve the five pre-existing untracked VSView plans dated October 18, and the
untracked research report. The controller alone edits this plan and that report.
Product source is unchanged at dispatch. Record HEAD and relevant source hashes
at execution; report drift rather than silently changing baseline.

Only unit A may run native media/Vulkan/decoder workloads during wave 1. Unit B
may inspect sources, build isolated diagnostic scripts, and run pure Python
numeric tests without native imports. No full Docker verifier or shared pytest
media-cache run is assigned. The controller will grant the next native resource
lease explicitly after A relinquishes it.

Children have disjoint evidence roots:

- A: `generated/verification/2026-10-23/highlight-study/real-media/`.
- B: `generated/verification/2026-10-23/highlight-study/synthetic/`.
- Controller: `generated/verification/2026-10-23/highlight-study/controller/`.

Use an owned temporary scratch directory outside the checkout for native indexes
and replaceable runtime scratch. Retain scripts, invocation receipts, environment,
errors and results in the assigned evidence root. Do not overwrite October 18–22
evidence. Never remove media or existing indexes. Use bounded child processes,
one native graph/process at a time, and cleanup only positively owned resources.

## Unit A: current real-media curve, peak and gamut comparison

This unit requires diagnosis across native boundaries. Use verify-code and the
repository runtime/verification guidance. Reuse existing scripts as evidence and
adapt copies under the unit root; do not edit historical scripts in place.

Sources: the current product tonemap/conversion/encoder owners, retained
`generated/verification/2026-10-20/hdr-color-study/srgb-implementation/real_media_probe.py`,
`hdr-pro-handoff/diagnostic-summary.json`, `hdr-experiment-a/experiment-a-summary.json`,
and cross-title `hdr-color-study/cross-title/samples.json` under that date root.

First establish doctor, actual plugin identity/signature, current source hashes,
and read-only access to retained media. Reuse existing local excerpts preferentially.
Do not silently drop DV container metadata or use separately graded SDR as a golden.

Initial fixed-frame cases: Kill Bill HDR 12382 porch, 14943 close-up, 110257 dark/control.
Baseline: current reference at100 nits, gamma off, quality independent stills,
BT.709 primaries, corrected sRGB output, contrast recovery0.3. Hold all other
controls fixed unless the case explicitly changes them.

1. Baseline versus BT.2390 knee1.0; include spline100/parameter0.5 as an existing
   alternative. Capture resolved settings explicitly; bypass preset override
   ambiguity with immutable diagnostic settings, not config edits.
2. Porch metadata auto versus metadata2 with identical RPU/detection settings,
   retaining native trace. A supplied source peak is not an effective-peak receipt.
3. A controlled no-RPU/no-PLScene branch: measured99.995 versus measured100, then
   controlled static448 with float props, detector off, metadata2, use_dovi false.
   Strip props for the negative branch rather than assuming a flag suppresses them.
4. On the useful curve candidate, perceptual1 versus softclip2 versus darken7
   for porch and a saturated retained animation example. Also isolate contrast
   recovery0 versus0.3 where useful.
5. Confirm the shortlisted curve on one retained Substance and one Immaculate
   frame; choose the existing sample frame from historical receipts, not arbitrary
   output that changes source identity. Include source packet/profile provenance.

Keep the first wave bounded around30 native case/frame evaluations. Reduce
redundancy if identical or inactive branches explain it; return evidence for
expansion rather than running a full Cartesian sweep. These are not timing benchmarks.

Capture native16 and corrected sRGB/final8 from the same evaluation when possible.
An isolated wrapper/tap is allowed in the harness, not product edits; prove its
baseline final8 equals the uninstrumented product path for one case. Preserve
full images/arrays where manageable, hashes, exact source frame, metadata and kwargs,
native logs, and numeric stats (any/all endpoint, near-white, fixed-region texture).
Use clearly defined fixed regions excluding overlays. A whole-frame average or
white count cannot alone establish fidelity. Supply an HTML comparison with exact
case labels and local relative image references, plus compact JSON results.

Stop a failing runtime route with the error preserved; distinguish absent plugin,
permission error, failed native execution and skipped case. Repair owned harness
issues, not product or runtime installations. Callback if a consequential choice
or unavailable input prevents meaningful progress. Completion must explicitly
release the native resource lease.

## Unit B: independent boundary audit and synthetic diagnostic preparation

Read current source and pinned upstream references in the report, then prepare
an independent synthetic harness and numerical checks. No native imports or
renders until the controller grants the resource lease in a later message.

Questions: percentile authority versus dynamic metadata; BT.2390-only knee
semantics; gamut/channel endpoints; pre-RGB48 loss; final8 quantization; fallback
saturation; and why fewer white pixels is not sufficient proof.

Create compact deterministic PQ/BT.2020 fixture definitions: neutral steps/ramp,
small extreme impulses versus broad patches, saturated colors, missing/understated
metadata, already-clipped source. Define HLG separately or return the exact
additional assumptions needed. Use independently written transfer arithmetic and
known mathematical endpoints, not imported product code as its own oracle.

Prepare executable diagnostic cases for actual current product/native mapping
and same-evaluation checkpoints, with a machine-readable case plan. Numeric
checks can verify PQ encode/decode, dimensions, endpoints, expected distinctions,
metric sensitivity and the algebraic fallback threshold without native execution.
Include deliberate flattened-ramp/one-channel saturation negative controls for
metrics. Distinguish arithmetic predictions from observed renderer results.

Keep fixture data small and final native matrix bounded (roughly12–20 cases,
adaptive). Prefer reusing `tools/hdr_still_probe.py` conventions over a new generic
framework. Supply exact commands, expected observations, dependencies, and output
schema so the controller can run and inspect it. Identify gaps in A's proposed
metrics/case plan in the callback, but do not write A's files or message A.

## Controller acceptance and next waves

On callbacks, inspect evidence, source identity and changed files. Resolve
contradictions against raw receipts. Independently rerun a small positive case
and a discriminating negative/control on stable inputs; inspect candidate images,
not only summary tables. Grant B the native lease or run its harness directly
after A releases it. Request focused corrections in the same child where useful.

Run a current installed-CLI baseline/candidate comparison where existing public
controls express it, or state clearly when internal diagnostic settings are not
yet a supported CLI recipe. Separate native Windows proof from Docker/packaged
and physical display acceptance. Do not claim calibrated display truth.

Then update the research report with current measurements, retained historical
distinctions, accepted/rejected hypotheses, recommended product changes and
remaining evidence limits. Do not adopt a global default based on one film.

## Dispatch and callback ledger

Host tool policy permits an explicit model override only when the human names
that model. No model was named, so child chats use the configured host default;
reasoning is explicit (high for A, medium for B). No cost-saving claim is made.
Repository worker and worker_luna role instructions were inspected; their model
overrides are not silently applied contrary to the tool policy.

- A: `01a16827-6663-7cb1-911f-a4a3e2d9fc86`, host `local`, configured model default / high reasoning; native resource lease assigned for wave1.
- B: `01a16827-719d-72e3-9498-b00fee3ca22a`, host `local`, configured model default / medium reasoning; pure numeric/source preparation only during wave1.
- Both must callback to controller `01a16815-04a8-7d02-96f6-456f0dfcb02f`, host `local`.
- Report unit/child ID, completion or blocker, exact source, files, commands/exits,
  evidence paths, failed/skipped observations, proposed decisions and limits.
- Before callback verify the original human authorization through read_thread.
  If unavailable, leave a final report in the child and state callbacks could not
  be authorized; the controller will retrieve on its next activation.
- Send a completion callback after any earlier blocker/correction; avoid routine
  progress callbacks and acknowledgment loops. End the child after reporting.
- The controller ends its turn when useful independent work is exhausted rather
  than keeping an idle wait loop. Callbacks resume its work.

## Controller observations at dispatch

Both child chats were observed active through one nonblocking wait snapshot.
Saved retrieval cursors: A `e41ee676-7259-4ab0-8f53-b1b3208d658f:1`,
B `54f1a1ff-f732-47e1-a3e9-30b1d42397c3:1`.

Controller executed the actual local ColorConfig -> apply_cli_overrides ->
resolve_tonemap_settings path with the contributor Python. Exit0. Preset-only
highlight_guard resolved to BT.2390/100 due to explicit local overrides;
explicit curve/target resolved to spline/180. VapourSynth was not imported.
Receipt and current source hashes:
`generated/verification/2026-10-23/highlight-study/controller/config-resolution.json`.
This proves configuration behavior, not image appearance. Final native and
image-quality adjudication remain pending the child evidence and controller runs.

## Completed controller adjudication

A completed 28 real-media processes and released its native lease. B completed
pure numeric preparation; its callback was rejected by automatic review, so the
controller retrieved its report directly and instructed it to stop retries and
hold native execution. The controller then ran three fresh porch processes and
17 synthetic native cases serially. All 20 controller native processes exited 0.
The positive endpoint assertion passed and unchanged-baseline negative control
failed as intended, exit 1. Original versus controller baseline/candidate pixels
matched; tapped versus plain baseline matched. No tracked source/config drift.

Final findings, limits and recommendations are in the report's current native
investigation section. Knee 1.0 and softclip are accepted as candidates, not new
defaults. No code or public configuration was changed. Numeric effective peaks
remain unobserved; HLG, packaged/Docker, installed-CLI image journeys and physical
display acceptance remain outside the demonstrated scope. Internal candidates
are not public CLI recipes. Native lease is released; no further child work is
required for this report. Controller receipts are in controller/ under the
study root.

## Authorized implementation follow-up

The human requested an opt-in knee 1.0 option, more difficult softclip scenes,
an updated report, and an Opus 5.5 second-opinion handoff. Controller owns source,
docs, tests and final adjudication. Existing real-media chat A owns new evidence
only in highlight-softclip-expanded and the exclusive native lease until release.
Existing synthetic chat B independently reviews the implementation read-only,
without native execution. Both handoffs explicitly require completion/blocker
callbacks to the parent; a denied callback is retrieved directly without retries.

Implementation: new highlight_preserve preset, reference plus knee 1.0. Existing
reference/highlight_guard and gamut defaults stay unchanged. Explicit switches
to another curve reset the generic native parameter to .5 to avoid cross-curve
parameter reinterpretation. Public docs explain precedence and limitations.

Verification so far: 101 focused tests passed after correcting test scratch/cache
setup; installed contributor CLI help and write-config succeeded, persisted config
resolved knee 1.0. Pyright, Ruff lint/format, Bandit medium/high gate and import
contracts passed. Native follow-up, independent review and full suite pending.
Docker/bash and Zensical were not discoverable on this host; their gates remain
unverified, not replaced by Windows component evidence.

Follow-up closed: A delivered expanded study and released native lease; controller
verified 137 manifest hashes and reran the magenta pair with exact pixel equality,
positive assertion exit0 and negative control exit1. B review found no actionable
issues; blocked callback retrieved directly. Full suite 4197 passed/78 skipped/4
failed; orchestration failure reproduced on isolated base source; three Windows
portable failures outside changed product path remain. Static/focused checks pass.
Report and Opus handoff updated; no commits, release, or softclip-default adoption.
See highlight-implementation/verification.json for exact acceptance limitations.

## Portable handoff correction

The human reported that Claude could not see the uncommitted implementation or
ignored evidence. The controller corrected this delivery failure by committing
the implementation, tests, public docs, research report, handoff and a portable
evidence bundle under review-evidence/2026-10-23-tonemapping. The bundle contains
516 hash-verified copied artifacts (about 39 MB), including raw text receipts,
test logs, numeric summaries, comparison sheets/crops and synthetic arrays.
Large real-media arrays/source-sized PNGs remain local and are explicitly listed
in omitted-local-artifacts.json; source movies are not distributed. Archived
Python probes use .py.txt to avoid normal lint/test discovery. The handoff now
uses base-to-HEAD comparison and links an exact saved implementation diff.
Unrelated October 18 VSView plans remain excluded.
