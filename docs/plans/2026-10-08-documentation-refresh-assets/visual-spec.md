---
search:
  exclude: true
---

# Documentation refresh: visual specification

Part of the [documentation refresh plan](../2026-10-08-documentation-refresh.md).
The maintainer approved direction **B, viewer-matched** on 2026-10-08. This file is
complete: unit U2 copies the blocks below verbatim and makes no other styling,
markup, or wording decision.

## Direction

- **Thesis:** the documentation looks like the product. The report viewer's charcoal
  surfaces and brass selection accent carry into the site, so a reader recognises
  the tool before reading a word.
- **Signature:** a charcoal "stage" hero holding the real report capture, a headline
  split by a brass divider that echoes the viewer's slider handle, and a filmstrip of
  four viewer states beneath it.
- **System:** brass replaces Zensical's default indigo for every link, navigation
  highlight, and primary button, in both schemes. Content figures sit in a charcoal
  frame so screenshots read the same in light and dark mode.
- **Fonts:** system fonts only (`font = false` stays). The kicker, chips, step
  numbers, and route tags use the theme's monospace stack.
- **Theme:** the site follows the operating system's light or dark preference on
  first visit; the existing toggle still switches and remembers the choice.

Measured contrast (WCAG 2.2): brass `#8f4b00` on white 6.6:1; dark-scheme brass
`#e9a24c` on `#141414` 8.5:1; stage muted text `#a3a39e` on `#141414` 7.3:1; button
text `#1a1208` on `#e9a24c` 8.6:1.

## `zensical.toml`

Replace the two existing `[[project.theme.palette]]` tables with this block. Do not
change any other theme key.

```toml
[[project.theme.palette]]
media = "(prefers-color-scheme: light)"
scheme = "default"
primary = "custom"
accent = "custom"
toggle.icon = "lucide/sun"
toggle.name = "Switch to dark mode"

[[project.theme.palette]]
media = "(prefers-color-scheme: dark)"
scheme = "slate"
primary = "custom"
accent = "custom"
toggle.icon = "lucide/moon"
toggle.name = "Switch to light mode"
```

Replace the `nav = [...]` value with the block in the plan's
[navigation section](../2026-10-08-documentation-refresh.md#navigation).

## `docs/stylesheets/extra.css`

Replace the entire file with this content.

```css
/* Frame Compare documentation presentation layer (viewer-matched direction). */

/* ── Tokens ─────────────────────────────────────────────── */
:root,
[data-md-color-scheme="default"] {
  --fc-brass: #8f4b00;
  --fc-brass-strong: #6f3a00;
  --fc-brass-soft: rgb(143 75 0 / 7%);
  --fc-on-brass: #ffffff;
  --fc-stage: #141414;
  --fc-stage-raised: #1d1d1c;
  --fc-stage-line: #2c2c2a;
  --fc-stage-text: #ececea;
  --fc-stage-muted: #a3a39e;
  --fc-stage-accent: #e9a24c;
  --fc-stage-on-accent: #1a1208;
  --fc-line: var(--md-default-fg-color--lightest);
  --fc-muted: var(--md-default-fg-color--light);
  --fc-mono: var(--md-code-font-family, ui-monospace, "SF Mono", Menlo, Consolas, monospace);
  --fc-radius-lg: 0.9rem;
  --fc-radius: 0.6rem;
  --fc-radius-sm: 0.3rem;
  --fc-lift: 0 0 0 0.05rem rgb(0 0 0 / 6%), 0 0.6rem 1.6rem -0.4rem rgb(0 0 0 / 22%);

  --md-primary-fg-color: var(--fc-brass);
  --md-primary-fg-color--light: #b06a1a;
  --md-primary-fg-color--dark: var(--fc-brass-strong);
  --md-primary-bg-color: #ffffff;
  --md-accent-fg-color: var(--fc-brass-strong);
  --md-accent-fg-color--transparent: rgb(143 75 0 / 10%);
  --md-typeset-a-color: var(--fc-brass);
}

[data-md-color-scheme="slate"] {
  --fc-brass: #e9a24c;
  --fc-brass-strong: #ffc078;
  --fc-brass-soft: rgb(233 162 76 / 9%);
  --fc-on-brass: #1a1208;
  --fc-line: var(--md-default-fg-color--lightest);
  --fc-muted: var(--md-default-fg-color--light);
  --fc-lift: 0 0 0 0.05rem rgb(255 255 255 / 8%);

  --md-default-bg-color: #141414;
  --md-default-bg-color--light: #1b1b1a;
  --md-code-bg-color: #1d1d1c;
  --md-footer-bg-color: #101010;
  --md-footer-bg-color--dark: #0c0c0c;
  --md-primary-fg-color: var(--fc-brass);
  --md-primary-fg-color--light: #f2b971;
  --md-primary-fg-color--dark: #c8822f;
  --md-primary-bg-color: #141414;
  --md-accent-fg-color: var(--fc-brass-strong);
  --md-accent-fg-color--transparent: rgb(233 162 76 / 12%);
  --md-typeset-a-color: var(--fc-brass);
}

/* ── Content pages ──────────────────────────────────────── */
.md-typeset {
  font-size: 0.84rem;
  line-height: 1.72;
}

.md-typeset :is(h1, h2, h3) {
  text-wrap: balance;
}

.md-typeset h1,
.md-typeset h2 {
  letter-spacing: -0.02em;
}

.md-typeset :is(p, li, figcaption) {
  text-wrap: pretty;
}

.md-typeset a:not(.md-button) {
  text-decoration: underline;
  text-decoration-color: color-mix(in srgb, currentcolor 35%, transparent);
  text-decoration-thickness: 0.06em;
  text-underline-offset: 0.16em;
}

.md-typeset a:not(.md-button):hover {
  text-decoration-color: currentcolor;
}

.md-typeset kbd {
  white-space: nowrap;
}

.md-typeset figure.fc-figure {
  margin: 1.6rem 0 2rem;
  padding: 0.5rem;
  border-radius: calc(var(--fc-radius-sm) + 0.5rem);
  background: var(--fc-stage);
  box-shadow: var(--fc-lift);
}

.md-typeset figure.fc-figure img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: var(--fc-radius-sm);
  outline: 0.05rem solid rgb(255 255 255 / 6%);
  outline-offset: -0.05rem;
}

.md-typeset figure.fc-figure figcaption {
  max-width: none;
  margin: 0.55rem 0.25rem 0.1rem;
  color: var(--fc-stage-muted);
  font-size: 0.74rem;
  font-style: normal;
  text-align: left;
}

.md-typeset figure.fc-figure--narrow {
  max-width: 30rem;
  margin-inline: auto;
}

/* ── Home ───────────────────────────────────────────────── */
.md-content__inner:has(.fc-home) > .md-content__button {
  display: none;
}

.md-typeset .fc-home > h2 {
  margin-top: 3.2rem;
  font-size: 1.45rem;
}

.md-typeset .fc-stage {
  display: grid;
  grid-template-columns: minmax(16rem, 1fr) minmax(20rem, 1.3fr);
  gap: clamp(1.5rem, 3.5vw, 3rem);
  align-items: center;
  padding: clamp(1.4rem, 3.5vw, 2.6rem);
  border-radius: var(--fc-radius-lg);
  background:
    radial-gradient(120% 90% at 85% 10%, rgb(233 162 76 / 10%), transparent 60%),
    var(--fc-stage);
  color: var(--fc-stage-text);
  box-shadow: var(--fc-lift);
}

.md-typeset .fc-kicker {
  margin: 0;
  color: var(--fc-stage-accent);
  font: 700 0.64rem/1.4 var(--fc-mono);
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.md-typeset .fc-stage h1 {
  margin: 0.4rem 0 0.9rem;
  color: var(--fc-stage-text);
  font-size: clamp(2rem, 3.4vw, 2.75rem);
  font-weight: 750;
  line-height: 1.06;
  letter-spacing: -0.03em;
}

.md-typeset .fc-split {
  position: relative;
  display: inline-block;
  padding-left: 0.42em;
  color: var(--fc-stage-accent);
  white-space: nowrap;
}

.md-typeset .fc-split::before {
  position: absolute;
  top: 0.1em;
  bottom: 0.04em;
  left: 0.12em;
  width: 0.08em;
  border-radius: 1rem;
  background: var(--fc-stage-accent);
  content: "";
}

.md-typeset .fc-stage-copy > p:not(.fc-kicker) {
  max-width: 46ch;
  color: var(--fc-stage-muted);
  font-size: 1rem;
  line-height: 1.65;
}

.md-typeset .fc-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem 1.2rem;
  align-items: center;
  margin-top: 1.5rem;
}

.md-typeset .fc-stage .md-button--primary {
  border-color: var(--fc-stage-accent);
  background: var(--fc-stage-accent);
  color: var(--fc-stage-on-accent);
  transition: filter 120ms ease-out;
}

.md-typeset .fc-stage .md-button--primary:is(:hover, :focus-visible) {
  border-color: var(--fc-stage-accent);
  background: var(--fc-stage-accent);
  color: var(--fc-stage-on-accent);
  filter: brightness(1.08);
}

.md-typeset .fc-stage a:focus-visible {
  outline: 0.1rem solid var(--fc-stage-accent);
  outline-offset: 0.2rem;
}

.md-typeset .fc-stage .fc-text-link {
  color: var(--fc-stage-text);
  font-weight: 650;
  white-space: nowrap;
}

.md-typeset .fc-stage-shot {
  margin: 0;
}

.md-typeset .fc-stage-shot img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: var(--fc-radius);
  outline: 0.05rem solid var(--fc-stage-line);
  outline-offset: -0.05rem;
}

.md-typeset .fc-stage-shot figcaption {
  margin-top: 0.6rem;
  color: var(--fc-stage-muted);
  font-size: 0.7rem;
  font-style: normal;
  text-align: left;
}

.md-typeset .fc-chip {
  display: inline-block;
  margin-right: 0.35rem;
  padding: 0.05rem 0.4rem;
  border-radius: var(--fc-radius-sm);
  background: var(--fc-stage-accent);
  color: var(--fc-stage-on-accent);
  font: 700 0.62rem/1.5 var(--fc-mono);
}

.md-typeset ol.fc-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.6rem;
  margin: 0.8rem 0 0;
  padding: 0.6rem;
  border-radius: var(--fc-radius-lg);
  background: var(--fc-stage-raised);
  list-style: none;
}

.md-typeset .fc-strip li {
  position: relative;
  margin: 0;
  overflow: hidden;
  border-radius: var(--fc-radius-sm);
}

.md-typeset .fc-strip img {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: cover;
  object-position: top left;
}

.md-typeset .fc-strip span {
  position: absolute;
  inset: auto 0 0;
  padding: 1rem 0.5rem 0.35rem;
  background: linear-gradient(transparent, rgb(0 0 0 / 75%));
  color: #ffffff;
  font: 600 0.66rem/1 var(--fc-mono);
  text-align: center;
}

.md-typeset .fc-credit {
  margin: 0.5rem 0 0;
  color: var(--fc-muted);
  font-size: 0.68rem;
}

.md-typeset .fc-routes {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
  margin-top: 1rem;
}

.md-typeset .fc-route {
  position: relative;
  padding: 1rem 1.1rem;
  border: 0.05rem solid var(--fc-line);
  border-radius: var(--fc-radius);
  transition: border-color 120ms ease-out;
}

.md-typeset .fc-route:is(:hover, :focus-within) {
  border-color: var(--fc-brass);
}

.md-typeset .fc-route > * {
  margin: 0;
}

.md-typeset .fc-route-tag {
  color: var(--fc-brass);
  font: 700 0.62rem/1.4 var(--fc-mono);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.md-typeset .fc-route h3 {
  margin: 0.3rem 0;
  font-size: 1.02rem;
}

.md-typeset .fc-route h3 a {
  color: inherit;
  text-decoration: none;
}

.md-typeset .fc-route h3 a::after {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  content: "";
}

.md-typeset .fc-route h3 a:focus-visible {
  outline: none;
}

.md-typeset .fc-route:has(a:focus-visible) {
  outline: 0.1rem solid var(--fc-brass);
  outline-offset: 0.15rem;
}

.md-typeset .fc-route p:last-child {
  color: var(--fc-muted);
}

.md-typeset .fc-flow {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1.4rem;
  margin-top: 1rem;
}

.md-typeset .fc-flow > div {
  padding-top: 0.8rem;
  border-top: 0.12rem solid var(--fc-brass);
}

.md-typeset .fc-step {
  color: var(--fc-brass);
  font: 700 0.7rem/1 var(--fc-mono);
}

.md-typeset .fc-flow h3 {
  margin: 0.4rem 0 0.3rem;
}

.md-typeset .fc-flow p {
  margin: 0;
  color: var(--fc-muted);
}

.md-typeset .fc-answer-links ul {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.4rem 2rem;
}

@media screen and (max-width: 60rem) {
  .md-typeset .fc-stage {
    grid-template-columns: 1fr;
  }

  .md-typeset .fc-flow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media screen and (max-width: 44.984375em) {
  .md-typeset .fc-routes,
  .md-typeset .fc-flow,
  .md-typeset .fc-answer-links ul {
    grid-template-columns: 1fr;
  }

  .md-typeset ol.fc-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .md-typeset .fc-stage .md-button {
    width: 100%;
    text-align: center;
  }
}

@media (prefers-reduced-motion: reduce) {
  .md-typeset .fc-stage .md-button--primary,
  .md-typeset .fc-route {
    transition: none;
  }
}
```

The stylesheet adds `fc-credit` for the home page's media credit line.

Classes deleted by this replacement, which no page may use afterwards:
`fc-hero`, `fc-hero-copy`, `fc-hero-visual`, `fc-section-intro`, `fc-card-grid`,
`fc-route-grid`, `fc-card`, `fc-card-label`, `fc-capability-grid`, `fc-steps`,
`fc-step-number`, `fc-inline-cta`, and `fc-doc-figure`. Every page that used
`fc-doc-figure` switches to `fc-figure` (page units own those edits).

## `docs/index.md`

Replace the entire file with this content. The images are produced by unit U1.

````markdown
---
hide:
  - toc
---

<div class="fc-home" markdown>

<section class="fc-stage" markdown>

<div class="fc-stage-copy" markdown>

<p class="fc-kicker">Deterministic video comparison</p>

<h1 id="compare-sources-not-guesswork">Compare sources,<br><span class="fc-split">not guesswork</span></h1>

Select useful frames, align source timing, render HDR-aware screenshots, and review
every difference in a report that opens without a server.

<div class="fc-actions" markdown>

[Choose an installation](getting-started/index.md){ .md-button .md-button--primary }
[Run your first comparison](guides/first-comparison.md){ .fc-text-link }

</div>

</div>

<figure class="fc-stage-shot">
  <img src="images/report-overview.webp" alt="Frame Compare report in Slider mode comparing the EBU DVB PQ10 reference with the HLG10 comparison at frame 1000." width="1600" height="1000" loading="eager">
  <figcaption><span class="fc-chip">Slider</span> EBU DVB PQ10 reference and HLG10 comparison, frame 1000.</figcaption>
</figure>

</section>

<ol class="fc-strip" aria-label="Report viewer views">
  <li><img src="images/report-overview.webp" alt="" width="1600" height="1000" loading="lazy"><span>Slider</span></li>
  <li><img src="images/report-grid.webp" alt="" width="1600" height="1000" loading="lazy"><span>Grid</span></li>
  <li><img src="images/report-inspector.webp" alt="" width="1600" height="1000" loading="lazy"><span>Inspector</span></li>
  <li><img src="images/report-lens.webp" alt="" width="1600" height="1000" loading="lazy"><span>Lens</span></li>
</ol>

<p class="fc-credit">Footage: EBU/DVB HEVC test content © EBU, shot by Frans de Jong (EBU), PQ10 conversion by Andrew Cotton (BBC), licensed under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Source: <a href="https://dvb.org/specifications/verification-validation/hevc-test-content/">DVB HEVC test content</a>.</p>

## Pick the route that owns your runtime

<div class="fc-routes" markdown>

<div class="fc-route" markdown>

<p class="fc-route-tag">Windows 10/11 x64</p>

### [Windows portable](windows-portable.md)

Complete runtime, VSView alignment panel, installer, and signed code-only updates.

</div>

<div class="fc-route" markdown>

<p class="fc-route-tag">macOS · Linux</p>

### [Docker](getting-started/docker.md)

Headless managed runtime with software-Vulkan HDR. Reports stay on the host.

</div>

<div class="fc-route" markdown>

<p class="fc-route-tag">Advanced</p>

### [Native source](getting-started/native.md)

Bring your own FFmpeg, VapourSynth, L-SMASH-Works, vs-placebo, and Vulkan.

</div>

</div>

## From sources to a report in four commands

<div class="fc-flow" markdown>

<div markdown>

<span class="fc-step">01</span>

### Configure

`frame-compare wizard` sets the input folder, reference, and frame goal.

</div>

<div markdown>

<span class="fc-step">02</span>

### Diagnose

`frame-compare doctor` checks the media runtime you will render with.

</div>

<div markdown>

<span class="fc-step">03</span>

### Preview

`frame-compare run --dry-run` shows sources, frames, and outputs without side effects.

</div>

<div markdown>

<span class="fc-step">04</span>

### Compare

`frame-compare run` aligns, renders, and writes `report.html`.

</div>

</div>

Docker and `uv` add a command prefix; [Your first comparison](guides/first-comparison.md)
shows every route.

## Find an answer

<div class="fc-answer-links" markdown>

- [Configuration](reference/configuration.md) — every key, type, and default.
- [Troubleshooting](guides/troubleshooting.md) — symptoms by pipeline stage.
- [Audio alignment](guides/audio-alignment.md) — what `APPLIED` and `NOT APPLIED` mean.
- [CLI behavioral contract](current-cli-contract.md) — exact streams, JSON, and exit codes.

</div>

</div>
````

## Components

### Figures

Every screenshot or terminal capture in a page uses this markup. `src` is relative to
the page. `width` and `height` are the asset's pixel dimensions from the
[capture specification](capture-spec.md#asset-table); for the three assets whose size
is "as generated" or "as captured" (`terminal-dry-run.svg`,
`terminal-run-complete.svg`, `report-information.webp`) omit both attributes, so no
page unit depends on U1's output. The two Windows assets
(`windows-portable-install.png`, `vsview-alignment-panel.webp`) carry the saved file's
size, which U10 sets. `loading="lazy"` is used everywhere except the home hero.

```html
<figure class="fc-figure">
  <img src="../images/report-grid.webp" alt="ALT TEXT FROM THE CAPTURE SPECIFICATION" width="1600" height="1000" loading="lazy">
  <figcaption>CAPTION FROM THE CAPTURE SPECIFICATION</figcaption>
</figure>
```

Add the modifier class `fc-figure--narrow` (`class="fc-figure fc-figure--narrow"`)
only where a page specification says so; it centres a portrait or small capture at
30 rem wide.

### Route cards

`docs/getting-started/index.md` reuses the home page's route cards. Copy this block
exactly, with links relative to `docs/getting-started/`:

```markdown
<div class="fc-routes" markdown>

<div class="fc-route" markdown>

<p class="fc-route-tag">Windows 10/11 x64</p>

### [Windows portable](../windows-portable.md)

Complete runtime, VSView alignment panel, installer, and signed code-only updates.

</div>

<div class="fc-route" markdown>

<p class="fc-route-tag">macOS · Linux</p>

### [Docker](docker.md)

Headless managed runtime with software-Vulkan HDR. Reports stay on the host.

</div>

<div class="fc-route" markdown>

<p class="fc-route-tag">Advanced</p>

### [Native source](native.md)

Bring your own FFmpeg, VapourSynth, L-SMASH-Works, vs-placebo, and Vulkan.

</div>

</div>
```

The whole card is clickable: the heading link's `::after` covers the card, and the
card shows a brass focus ring when the link has keyboard focus.

## Behavior by context

| Context | Expected result |
| --- | --- |
| Light scheme | White page, brass links and active navigation, charcoal hero stage and figure frames with a soft lift shadow. |
| Dark scheme | `#141414` page, amber links (`#e9a24c`), stage and figures separated by a 1 px light ring instead of a shadow. |
| First visit | Scheme follows the OS preference; the header toggle switches and persists. |
| Width ≤ 60 rem | Hero stacks copy above the image; the four-step flow becomes two columns. |
| Width < 45 em (phones) | Route cards, steps, and answer links become one column; the filmstrip becomes 2 × 2; the primary button spans the width. No horizontal page scroll. |
| Reduced motion | Button brightness and card border transitions are removed. |
| Keyboard | Route cards and hero links show a 0.1 rem brass outline on focus. |

## Evidence

The direction was prototyped as real Zensical builds in scratch
(`.tmp/docs-refresh-2026-10-08/proj-final`) and checked in the built-in browser at
1440 × 900 and 390 × 844 in both schemes, including card click-through and the
absence of horizontal overflow. Scratch screenshots are not committed.
