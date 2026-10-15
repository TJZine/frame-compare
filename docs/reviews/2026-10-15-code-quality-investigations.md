---
search:
  exclude: true
---

# Frame Compare Follow-up Investigations

- Date: 2026-10-15
- Repository: `/Users/tristan/Software/frame-compare`
- Reviewed source: `e036bc348431c948314019318d40f642c0923784`
- Status: Investigation handoff; neither candidate is a recommended refactor yet
- Related supported scope: [Code quality planning handoff](/Users/tristan/Software/frame-compare/docs/reviews/2026-10-15-code-quality-planning-handoff.md)

The repository-wide assessment found twenty supported correction/improvement groups and two candidates that need distinguishing evidence. The maintainer asked to keep the latter separate:

> i think we should keep those findings to a second investigatory report then since we need to do some additional work to verify them

This document owns those two candidates. IDs CQ7/CQ14 are retained to avoid breaking references from the main report. Do not schedule a shared image loader or unified resampling pipeline as accepted implementation work. Investigate first, then record a supported local correction, consolidation, explicit disclosure/retention decision, or no change. The main report contains the original request, full source identity, repository obligations, review coverage, and accepted planning scope.

In a cloud checkout, resolve links beginning `/Users/tristan/Software/frame-compare/` relative to that checkout's root. This report is `docs/reviews/2026-10-15-code-quality-investigations.md`; host-specific executable paths and runtime observations below describe the review environment, not capabilities guaranteed in the cloud task.

Neither investigation inherently requires Windows. CQ7 can use the existing Node fixtures for state/lifetime observations and a real browser for scheduling/user-visible claims. CQ14 needs a supported native media runtime with the actual relevant plugins; Linux Docker, native macOS, or Windows may suffice if capable. Any eventual Windows behavior change still needs its own appropriate platform acceptance.

These are bounded follow-up decisions, not evidence that a broad second refactor campaign is necessary. Inspect current source and refresh observations if the implementation advances. Do not modify product code, install dependencies, or change runtime configuration merely to satisfy this handoff without an authorized implementation/investigation task.

## Investigation overview

| ID | Established evidence | Missing distinguishing evidence | Possible justified outcomes |
| --- | --- | --- | --- |
| CQ7 | Repeated request/source/attempt mechanics with legitimately different owners; Grid retry depends on RAF delivery | Complete stale-callback/navigation observations; actual browser/background scheduling if claiming user-visible failure; common policy beyond incidental duplication | Local retry correction, a small shared request-slot owner, or retain separate owners |
| CQ14 | Pillow, fpng, and FFmpeg choose different resampling policies; applied resampler is not described in geometry facts | Actual representative output comparison through both eligible production paths, plus the intended identity/equality contract | Centralized geometry transform, explicit backend transform disclosure/identity, or retain current behavior |

## CQ7 Investigate image request lifetime policy before consolidating it

**Classification:** insufficient data, S4 Informational, Medium confidence in potential consolidation benefit. Scheduling dependence is established; a production browser failure or useful shared policy owner is not.

The [main viewer loader](/Users/tristan/Software/frame-compare/src/frame_compare/services/report/assets/viewer.js:2207), [Grid loader](/Users/tristan/Software/frame-compare/src/frame_compare/services/report/assets/grid_view.js:216), and [Lens loader](/Users/tristan/Software/frame-compare/src/frame_compare/services/report/assets/lens.js:422) independently handle source identity, attempts/generations, stale callbacks, availability, retry, and cleanup.

There is evidence of repeated lifetime mechanics, but also legitimate differences: Diff commits paired images atomically, Grid owns separately mounted cells and generations, and Lens owns cloned images and sampling context. Main-stage retry moved from animation-frame scheduling to a timer in historical commit `bdc2dafe`, while Grid retry still schedules through `requestAnimationFrame`. That difference alone proves neither a defect nor the need for one loader.

Plan this bounded investigation:

1. Use the existing Grid harness around its retry lifecycle. Trigger failure and Retry while withholding animation-frame delivery.
2. Deliver ordinary timers and observe whether a new image request is admitted.
3. Navigate or rebuild cells before delivering delayed retry callbacks; verify old callbacks cannot affect current cells.
4. Compare only the source/attempt identity and cleanup obligations actually shared with main-stage and Lens loading.
5. If claiming a user-visible browser/background-tab failure, obtain a bounded actual-browser observation. A simulated withheld animation frame establishes scheduling dependence only.

Use the result to choose one of three outcomes:

- If only Grid's scheduling needs correction, recommend a local fix and stop expanding the design.
- If multiple owners demonstrably need the same source/attempt/cleanup policy, consider a small request-slot owner exposing load/retry/clear/status. Migrate a complete seam and delete the superseded implementation.
- If differences follow their presentation and lifetime obligations, retain separate owners and record the reason.

Do not make this speculative consolidation a prerequisite for CQ1. Avoid a generic image cache/loader framework, a global store, or speculative plugin interfaces. Completion for the planning task is a bounded decision and its distinguishing evidence; implementation scope depends on that decision.

## CQ14 Decide resampling ownership before changing writer behavior

**Classification:** inferred output-identity/consistency risk, S2 Medium potential impact, Medium confidence; bounded investigation, not a confirmed equality-contract failure.

The [Pillow encoder path](/Users/tristan/Software/frame-compare/src/frame_compare/render/encoders.py:584) uses Lanczos for geometry, the [fpng path](/Users/tristan/Software/frame-compare/src/frame_compare/render/encoders.py:615) uses VS Spline36, and [FFmpeg geometry](/Users/tristan/Software/frame-compare/src/frame_compare/render/backend/_ffmpeg_frame.py:41) leaves scale flags at the backend default. AUTO writer selection depends on plugin availability and overlay eligibility. Geometry facts describe dimensions but omit the effective resampler; report identity deliberately excludes image bytes.

Source therefore establishes differing transform policies, but no native pixel divergence was measured and no universal cross-backend pixel-equality contract was established. Determine the intended contract before prescribing one kernel.

Use a nonconstant existing media fixture through eligible Pillow and fpng geometry paths. Compare unobscured image content, geometry facts, and report identity; inspect the FFmpeg path where applicable. Decide whether geometry should be prepared once independently of PNG encoding, or backend-specific transforms should remain explicit and be disclosed/identified. In either design, preserve supported source formats, integer/mod-safe dimensions, overlays, exact-frame association, and encoder fallback restrictions.

Coordinate any applied resampler facts with CQ11's actual-transform identity and CQ3's render records. Stop if the proposed consolidation adds conversions or changes supported outputs without a demonstrated benefit. A universal renderer/provider framework is not justified.

## Additional bounded observations obtained before separation

Work stopped after the maintainer requested this separate report. These observations refine the next investigation; they do not complete it.

### CQ7 Partial Node observations

A memory-only probe using the existing Grid harness withheld animation-frame delivery after a failed cell's Retry. An ordinary timer ran, but Grid remained loading with an empty image source and one queued animation-frame callback. Delivering that callback assigned `clip-1.png`. This establishes scheduling dependence in the fixture, not a real-browser background-tab defect.

Observed snapshots were:

```json
{"case":"timers_only","timerRan":true,"status":"loading","src":"","failed":[],"generation":1,"pendingRaf":1}
{"case":"raf_delivered","status":"loading","src":"clip-1.png","failed":[],"generation":1,"pendingRaf":0}
```

Rebuilding cells before delivering the late callback preserved the replacement cell's error state and failed set; the old image source remained empty, including after the old image's load event. That is evidence that the rebuild path's generation guard works in the observed case.

The exploratory command subsequently attempted a nonexistent `owner.move` method and exited with `TypeError`. The navigation branch is therefore **unverified**, and the whole exploratory command is not a passing regression. Resume through the exposed next-button click or actual public navigation interface, rather than inventing a helper. No real-browser scheduling observation was obtained. The source trace still supports distinct main-stage, cell-generation, and Lens lifetimes; a shared owner has not earned its cost.

Resume from [the Grid harness](/Users/tristan/Software/frame-compare/tests/services/grid_view_harness.js), its [pytest bridge](/Users/tristan/Software/frame-compare/tests/services/test_report_grid_view_state.py), and [existing real-browser support](/Users/tristan/Software/frame-compare/tests/browser/test_report_browser_smoke.py). In the current Grid fixture, `next.dispatch('click')` invokes the exposed navigation. For background behavior, a monkeypatched RAF in Chrome still proves only scheduling dependence; observe browser-managed suspension if that is the claimed failure mechanism.

### CQ14 Available runtime capabilities

A bounded `.venv` native child imported real VapourSynth R81/API R4.3, created a core, and evaluated an RGB24 `BlankClip` frame. Auto-loaded plugins included Best Source 2, resize, std, and text. **`core.fpng.Write` was absent**, so this host environment could not exercise both requested production writer paths. This is a capability observation, not native acceptance of the application or a representative image comparison.

The separately installed Homebrew `/opt/homebrew/bin/vspipe` reported R80/API R4.3. Do not assume this executable and `.venv` import use the same native runtime. Docker was available (server 29.8.2) and a preexisting `frame-compare:test` image existed; its plugin capability and production geometry behavior were not accepted. A network-disabled, read-only ephemeral container check established Python/uv availability only. No packages were installed or bootstrapped, and no rendering comparison ran.

The next CQ14 task should first select an already supported fpng-capable runtime and record its exact native/plugin identity. Then compare a nonconstant source frame and the same geometry plan through actual Pillow/fpng paths, keeping overlay pixels outside the comparison. Compare output pixels, geometry facts, and report identity. A measured difference alone does not create a universal equality obligation; decide whether the intended product contract calls for consolidation, disclosure, or retention.

## Scope and completion requirements

1. Assign one explicitly scoped investigation per candidate. Reuse relevant fixtures and source owners; avoid a general framework audit.
2. State the hypothesis, distinguishing observation, actual runtime/plugin/browser versions, exact command, and assertions before drawing a conclusion.
3. Preserve temporary-resource cleanup and avoid repository output/cache pollution. Any approved implementation belongs in a separate change with its own migration and verification scope.
4. Report failed probes and unavailable capabilities directly. Simulated scheduling is not browser acceptance; successful blank-frame evaluation is not production geometry proof.
5. End each investigation with a decision and rationale, including the credible smaller alternative. “Retain current owners/behavior” is a valid outcome if evidence does not justify change.
6. If a code change is supported, identify affected callers, deletions, payload/identity compatibility, and meaningful regression/native/browser/platform proof before adding it to an implementation plan.

CQ7 must preserve atomic paired-image commitment, independently mounted Grid generations, Lens sampling context, stale-event rejection, source/attempt identity, and owned cleanup. CQ14 must preserve exact source/frame association, format support, crop/mod-safe dimensions, overlays, encoder fallback restrictions, deterministic artifact identity, and truthful applied-transform facts. Coordinate any eventual facts with main-report CQ11/CQ3; do not delay their supported improvements for speculative resampling work.
