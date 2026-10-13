---
search:
  exclude: true
---

# Documentation site redesign: theme specification

Part of the [documentation site redesign plan](../2026-10-12-documentation-site-redesign.md).
Unit U1 writes every file in this specification exactly as given. Each block below is
the complete file content. All of it was built and inspected in a scratch prototype on
2026-10-12 with Zensical 0.0.69 (`uv run --no-sync zensical build --clean --strict`
reported no issues).

## Files

| Path | Action |
| --- | --- |
| `zensical.toml` | Replace |
| `overrides/main.html` | New |
| `overrides/home.html` | New |
| `overrides/404.html` | New |
| `overrides/partials/source.html` | New |
| `overrides/partials/copyright.html` | New |
| `docs/stylesheets/extra.css` | Replace |
| `docs/stylesheets/fonts.css` | New |
| `docs/javascripts/compare-slider.js` | New |
| `docs/assets/brand/logo.svg` | New |
| `docs/assets/brand/favicon.svg` | New |
| `docs/assets/fonts/geist-latin-wght-normal.woff2` | New, downloaded (see [Fonts](#fonts)) |
| `docs/assets/fonts/geist-mono-latin-wght-normal.woff2` | New, downloaded |
| `docs/assets/fonts/OFL-Geist.txt` | New, downloaded |
| `docs/assets/fonts/OFL-Geist-Mono.txt` | New, downloaded |

The raster brand files (`social-card.jpg`, `favicon-32.png`, `apple-touch-icon.png`)
and the home images belong to unit U2 and the [asset specification](assets.md).

## Design tokens

The stylesheet defines every color as a custom property. The values and their roles:

| Token | Light | Dark | Role |
| --- | --- | --- | --- |
| `--fc-stage` | `#111110` | `#111110` | Header, tabs, hero, code blocks, figure frames |
| `--fc-stage-text` | `#edece8` | `#edece8` | Text on the stage |
| `--fc-stage-muted` | `#a9a79f` | `#a9a79f` | Secondary text on the stage |
| `--fc-brass-bright` | `#e9a24c` | `#e9a24c` | Accent on the stage |
| `--fc-paper` | `#fafaf7` | `#141413` | Page background |
| `--fc-card` | `#ffffff` | `#1a1a18` | Cards, disclosure blocks |
| `--fc-ink` | `#1b1a17` | `#ecebe7` | Body text and headings |
| `--fc-ink-2` | `#58564f` | `#a9a79f` | Secondary text |
| `--fc-rule` | `#e4e1d9` | `#2b2b28` | Borders and dividers |
| `--fc-brass` | `#8f4b00` | `#e9a24c` | Links, active navigation, accents on paper |
| `--fc-ref` | `#e9a24c` | `#e9a24c` | Reference source label on dark surfaces |
| `--fc-cmp` | `#c6def4` | `#c6def4` | Comparison source label on dark surfaces |

Contrast, computed with the WCAG 2 formula: body text on paper is 16.6:1 (light) and
15.5:1 (dark); `--fc-ink-2` is 7.0:1 and 7.7:1; `--fc-brass` links are 6.3:1 and 8.6:1;
`--fc-stage-muted` on `--fc-stage` is 7.8:1; code comments are 5.3:1. Every current use
of the reference and comparison colors is on a dark surface (the hero labels and the
offset diagram). The pair differs in hue (orange against blue) and in lightness
(relative luminance ratio 1.6), so the two stay distinct without color vision.

Type: Geist for text and headings, Geist Mono for code, both self-hosted. Body text is
`clamp(16px, 0.8rem, 18px)` with line height 1.7. Prose blocks are limited to `42rem`;
code, tables, key blocks, cards, and figures use the full article width. The page grid
is `80rem` wide.

## Components

| Component | Markup | Defined in |
| --- | --- | --- |
| Lead paragraph | First paragraph after the H1; no class | `extra.css` "Base and layout" |
| Callouts | `!!! note`, `tip`, `warning`, `danger`; `??? fc-disclosure` | "Callouts" |
| Steps | `<div class="fc-steps" markdown>` around an ordered list | "Steps" |
| Key blocks | `#### `key` { #anchor .fc-key }` followed by a definition list | "Key reference blocks" |
| Cards | `<div class="fc-cards" markdown>` around a bullet list of links | "Cards" |
| Output blocks | ` ``` { .text .fc-output title="Output · …" } ` | "Inline code, code blocks, output" |
| Code titles | ` ```powershell title="…" ` | "Inline code, code blocks, output" |
| Figures | `<figure class="fc-figure">` | "Figures" |
| Pipeline strip | `<div class="fc-pipeline" markdown>` around an ordered list of links | "Pipeline strip" |
| Home hero and slider | `overrides/home.html` and `compare-slider.js` | "Home" |
| Home features and strip | `.fc-features`, `.fc-feature`, `.fc-feature__visual`, `ol.fc-strip` | "Home" |

The [style guide](style-guide.md) gives the authoring rules for each component.

## `zensical.toml`

```toml
[project]
site_name = "Frame Compare"
site_description = "Frame Compare picks frames from two or more videos, aligns them by audio when needed, renders matching screenshots, and writes an offline report."
site_url = "https://tjzine.github.io/frame-compare/"
site_author = "Tristan Zine"
copyright = "© 2025–2026 Tristan Zine. Released under the GPL-3.0-only license."
repo_url = "https://github.com/TJZine/frame-compare"
repo_name = "GitHub"
edit_uri = "edit/main/docs/"
docs_dir = "docs"
site_dir = "site"
extra_css = ["stylesheets/fonts.css", "stylesheets/extra.css"]
extra_javascript = ["javascripts/compare-slider.js"]
nav = [
  { "Home" = "index.md" },
  { "Get started" = [
    { "Choose an installation" = "getting-started/index.md" },
    { "Windows portable" = "getting-started/windows-portable.md" },
    { "Docker" = "getting-started/docker.md" },
    { "Docker profiles" = "getting-started/docker-profiles.md" },
    { "Native source" = "getting-started/native.md" },
    { "Your first comparison" = "getting-started/first-comparison.md" },
  ] },
  { "Guides" = [
    { "Overview" = "guides/index.md" },
    { "How Frame Compare works" = "guides/how-it-works.md" },
    { "Sources, references, and labels" = "guides/sources-and-labels.md" },
    { "Frame selection and analysis" = "guides/analysis-modes.md" },
    { "Audio alignment" = "guides/audio-alignment.md" },
    { "VSView alignment review" = "guides/vsview-review.md" },
    { "HDR and tonemapping" = "guides/hdr-tonemapping.md" },
    { "Reports and overlays" = "guides/reports-and-overlays.md" },
    { "Presets, history, and generated data" = "guides/presets-history-generated-data.md" },
    { "Publishing and webhooks" = "guides/publishing-and-webhooks.md" },
    { "Troubleshooting" = "guides/troubleshooting.md" },
  ] },
  { "Reference" = [
    { "Overview" = "reference/index.md" },
    { "Commands" = "reference/commands.md" },
    { "Configuration" = "reference/configuration.md" },
    { "Output layout" = "reference/output-layout.md" },
    { "Requirements" = "reference/requirements.md" },
    { "Glossary" = "reference/glossary.md" },
    { "Release notes" = "https://github.com/TJZine/frame-compare/blob/main/CHANGELOG.md" },
  ] },
  { "Internals" = [
    { "Overview" = "internals/index.md" },
    { "CLI behavioral contract" = "current-cli-contract.md" },
    { "Current architecture" = "current-architecture.md" },
    { "Supported media runtime" = "supported-media-runtime.md" },
    { "Engineering runbook" = "ENGINEERING_RUNBOOK.md" },
    { "Physical Windows runtime validation" = "media-runtime-windows-validation.md" },
    { "Analysis performance validation" = "analysis-performance-validation.md" },
    { "Analysis benchmark history" = "analysis-benchmark-history.md" },
    { "Historical decisions" = "DECISIONS.md" },
  ] },
]

[project.theme]
language = "en"
custom_dir = "overrides"
font = false
logo = "assets/brand/logo.svg"
favicon = "assets/brand/favicon.svg"
features = [
  "content.action.edit",
  "content.action.view",
  "content.code.copy",
  "content.tabs.link",
  "navigation.footer",
  "navigation.instant",
  "navigation.path",
  "navigation.sections",
  "navigation.tabs",
  "navigation.tabs.sticky",
  "navigation.top",
  "navigation.tracking",
  "search.highlight",
  "toc.follow",
]

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

[project.extra]
generator = false

[project.plugins.redirects.redirect_maps]
"windows-portable.md" = "getting-started/windows-portable.md"
"guides/first-comparison.md" = "getting-started/first-comparison.md"
"api.md" = "internals/index.md"

[project.markdown_extensions.admonition]
[project.markdown_extensions.attr_list]
[project.markdown_extensions.def_list]
[project.markdown_extensions.md_in_html]
[project.markdown_extensions.pymdownx.details]
[project.markdown_extensions.pymdownx.highlight]
[project.markdown_extensions.pymdownx.superfences]

[project.markdown_extensions.pymdownx.tabbed]
alternate_style = true

[project.markdown_extensions.toc]
permalink = true
toc_depth = 3
```

## `overrides/main.html`

Adds Open Graph and Twitter card tags, PNG icons, and a font preload to every page.

```jinja
{% extends "base.html" %}

{% block extrahead %}
  {% if not page.url %}
    {% set fc_title = config.site_name ~ " documentation" %}
  {% elif page.meta and page.meta.title %}
    {% set fc_title = page.meta.title %}
  {% elif page.title and not page.is_homepage %}
    {% set fc_title = page.title | striptags %}
  {% else %}
    {% set fc_title = config.site_name %}
  {% endif %}
  {% if page.meta and page.meta.description %}
    {% set fc_description = page.meta.description %}
  {% else %}
    {% set fc_description = config.site_description %}
  {% endif %}
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{{ config.site_name }}">
  <meta property="og:title" content="{{ fc_title }}">
  <meta property="og:description" content="{{ fc_description }}">
  {% if page.canonical_url %}
    <meta property="og:url" content="{{ page.canonical_url }}">
  {% endif %}
  <meta property="og:image" content="{{ config.site_url }}assets/brand/social-card.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="Frame Compare logo and title beside a harbour frame split between the PQ10 and HLG10 sources.">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" type="image/png" sizes="32x32" href="{{ 'assets/brand/favicon-32.png' | url }}">
  <link rel="apple-touch-icon" href="{{ 'assets/brand/apple-touch-icon.png' | url }}">
  <link rel="preload" href="{{ 'assets/fonts/geist-latin-wght-normal.woff2' | url }}" as="font" type="font/woff2" crossorigin>
{% endblock %}
```

## `overrides/home.html`

The home page template. It renders the hero above the tabs' content area at full width
and prints the page content without the automatic H1.

```jinja
{% extends "main.html" %}

{% block content %}
  {{ page.content }}
{% endblock %}

{% block hero %}
  <section class="fc-hero" aria-labelledby="fc-hero-title">
    <div class="fc-hero__inner md-grid">
      <div class="fc-hero__copy">
        <p class="fc-hero__kicker">Documentation</p>
        <h1 id="fc-hero-title" class="fc-hero__title">Frame Compare</h1>
        <p class="fc-hero__lead">{{ config.site_description }}</p>
        <div class="fc-hero__actions">
          <a class="fc-button fc-button--primary" href="{{ 'getting-started/' | url }}">Install</a>
          <a class="fc-button fc-button--ghost" href="{{ 'getting-started/first-comparison/' | url }}">Your first comparison</a>
        </div>
      </div>
      <figure class="fc-compare" data-fc-compare>
        <div class="fc-compare__stage">
          <img class="fc-compare__img" src="{{ 'images/home-frame-pq10.webp' | url }}" alt="EBU DVB PQ10 reference at frame 1000: boats in a harbour at sunset." width="1600" height="900">
          <img class="fc-compare__img fc-compare__img--top" src="{{ 'images/home-frame-hlg10.webp' | url }}" alt="EBU DVB HLG10 comparison at frame 1000." width="1600" height="900">
          <div class="fc-compare__rule" aria-hidden="true"><span class="fc-compare__knob"></span></div>
          <span class="fc-compare__label fc-compare__label--ref"><span class="fc-compare__source">EBU DVB </span>PQ10 · Reference</span>
          <span class="fc-compare__label fc-compare__label--cmp"><span class="fc-compare__source">EBU DVB </span>HLG10 · Comparison</span>
          <span class="fc-compare__frame">Frame 1000</span>
          <input class="fc-compare__range" type="range" min="0" max="100" step="1" value="50" aria-label="Divider position. Left of the divider shows the PQ10 reference; right shows the HLG10 comparison.">
        </div>
        <figcaption class="fc-compare__credit">Footage: EBU/DVB HEVC test content © EBU, shot by Frans de Jong (EBU), PQ10 conversion by Andrew Cotton (BBC), <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.</figcaption>
      </figure>
    </div>
  </section>
{% endblock %}
```

## `overrides/404.html`

```jinja
{% extends "main.html" %}

{% block content %}
  <div class="fc-404">
    <p class="fc-404__code">404</p>
    <h1>Page not found</h1>
    <p>This page does not exist. Search with <kbd>/</kbd>, or start from one of these pages.</p>
    <ul class="fc-404__links">
      <li><a href="{{ 'getting-started/' | url }}">Choose an installation</a></li>
      <li><a href="{{ 'getting-started/first-comparison/' | url }}">Your first comparison</a></li>
      <li><a href="{{ 'reference/configuration/' | url }}">Configuration</a></li>
      <li><a href="{{ 'guides/troubleshooting/' | url }}">Troubleshooting</a></li>
    </ul>
  </div>
{% endblock %}
```

## `overrides/partials/source.html`

Replaces the repository widget so the header shows "GitHub" without star and fork counts.

```jinja
<a href="{{ config.repo_url }}" title="Frame Compare on GitHub" class="md-source fc-source">
  <div class="md-source__icon md-icon">
    {% include ".icons/fontawesome/brands/github.svg" %}
  </div>
  <div class="md-source__repository">GitHub</div>
</a>
```

## `overrides/partials/copyright.html`

The footer content: project links, copyright, footage credit, and generator credit.

```jinja
<div class="md-copyright fc-footer">
  <nav class="fc-footer__links" aria-label="Project links">
    <a href="{{ config.repo_url }}">GitHub</a>
    <a href="{{ config.repo_url }}/blob/main/CHANGELOG.md">Release notes</a>
    <a href="{{ config.repo_url }}/releases">Releases</a>
    <a href="{{ config.repo_url }}/blob/main/SECURITY.md">Security</a>
    <a href="{{ config.repo_url }}/blob/main/CONTRIBUTING.md">Contributing</a>
    <a href="{{ 'internals/' | url }}">Internals</a>
  </nav>
  <p class="fc-footer__legal">{{ config.copyright }} Test footage © EBU, <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Built with <a href="https://zensical.org/">Zensical</a>.</p>
</div>
```

## `docs/stylesheets/fonts.css`

```css
/* Geist and Geist Mono, Fontsource 5.3.0, latin subset, SIL Open Font License 1.1. */
@font-face {
  font-family: "Geist";
  font-style: normal;
  font-display: swap;
  font-weight: 100 900;
  src: url("../assets/fonts/geist-latin-wght-normal.woff2") format("woff2-variations");
}

@font-face {
  font-family: "Geist Mono";
  font-style: normal;
  font-display: swap;
  font-weight: 100 900;
  src: url("../assets/fonts/geist-mono-latin-wght-normal.woff2") format("woff2-variations");
}
```

## `docs/stylesheets/extra.css`

```css
/* Frame Compare documentation theme (direction A, "Screening room"). */

/* ── Tokens ─────────────────────────────────────────────── */
:root,
[data-md-color-scheme="default"] {
  --fc-stage: #111110;
  --fc-stage-raised: #1a1a18;
  --fc-stage-line: #2b2b28;
  --fc-stage-text: #edece8;
  --fc-stage-muted: #a9a79f;
  --fc-brass-bright: #e9a24c;
  --fc-on-brass: #1a1208;
  --fc-ref: #e9a24c;
  --fc-cmp: #c6def4;

  --fc-paper: #fafaf7;
  --fc-card: #ffffff;
  --fc-soft: #f3efe7;
  --fc-ink: #1b1a17;
  --fc-ink-2: #58564f;
  --fc-rule: #e4e1d9;
  --fc-code-inline: #efece5;
  --fc-brass: #8f4b00;
  --fc-brass-strong: #6f3a00;

  --fc-note-bg: #eef2f6;
  --fc-note-line: #cfdbe7;
  --fc-note-ink: #1d3247;
  --fc-tip-bg: #eef3ee;
  --fc-tip-line: #cfe0d0;
  --fc-tip-ink: #1f3a24;
  --fc-warn-bg: #fdf1e4;
  --fc-warn-line: #f0d2ad;
  --fc-warn-ink: #4a2a05;
  --fc-danger-bg: #fbeceb;
  --fc-danger-line: #efc9c5;
  --fc-danger-ink: #5a1a14;

  --fc-radius-lg: 0.8rem;
  --fc-radius: 0.6rem;
  --fc-radius-sm: 0.3rem;
  --fc-measure: 42rem;
  --fc-font: "Geist", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --fc-mono: "Geist Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace;

  --md-text-font: "Geist";
  --md-code-font: "Geist Mono";
  --md-default-bg-color: var(--fc-paper);
  --md-default-fg-color: rgb(27 26 23 / 92%);
  --md-default-fg-color--light: var(--fc-ink-2);
  --md-default-fg-color--lighter: rgb(27 26 23 / 32%);
  --md-default-fg-color--lightest: var(--fc-rule);
  --md-primary-fg-color: var(--fc-stage);
  --md-primary-fg-color--light: var(--fc-stage-raised);
  --md-primary-fg-color--dark: #0a0a09;
  --md-primary-bg-color: var(--fc-stage-text);
  --md-primary-bg-color--light: var(--fc-stage-muted);
  --md-accent-fg-color: var(--fc-brass-strong);
  --md-accent-fg-color--transparent: rgb(143 75 0 / 10%);
  --md-typeset-color: var(--fc-ink);
  --md-typeset-a-color: var(--fc-brass);
  --md-code-bg-color: var(--fc-stage);
  --md-code-fg-color: var(--fc-stage-text);
  --md-footer-bg-color: var(--fc-stage);
  --md-footer-bg-color--dark: #0a0a09;
  --md-footer-fg-color: var(--fc-stage-text);
  --md-footer-fg-color--light: var(--fc-stage-muted);
  --md-footer-fg-color--lighter: #77756d;
}

[data-md-color-scheme="slate"] {
  --fc-paper: #141413;
  --fc-card: #1a1a18;
  --fc-soft: #221f1a;
  --fc-ink: #ecebe7;
  --fc-ink-2: #a9a79f;
  --fc-rule: #2b2b28;
  --fc-code-inline: #23221f;
  --fc-brass: #e9a24c;
  --fc-brass-strong: #ffc078;

  --fc-note-bg: #17202a;
  --fc-note-line: #2a3a4b;
  --fc-note-ink: #d4e2ef;
  --fc-tip-bg: #16211a;
  --fc-tip-line: #2a3d2f;
  --fc-tip-ink: #d2e6d5;
  --fc-warn-bg: #241a0e;
  --fc-warn-line: #4d3618;
  --fc-warn-ink: #f3dcbc;
  --fc-danger-bg: #2a1614;
  --fc-danger-line: #523029;
  --fc-danger-ink: #f3d0cb;

  --md-default-bg-color: var(--fc-paper);
  --md-default-bg-color--light: #1b1b1a;
  --md-default-fg-color: rgb(236 235 231 / 92%);
  --md-default-fg-color--light: var(--fc-ink-2);
  --md-default-fg-color--lighter: rgb(236 235 231 / 32%);
  --md-default-fg-color--lightest: var(--fc-rule);
  --md-primary-fg-color: var(--fc-stage);
  --md-primary-bg-color: var(--fc-stage-text);
  --md-accent-fg-color: var(--fc-brass-strong);
  --md-accent-fg-color--transparent: rgb(233 162 76 / 12%);
  --md-typeset-color: var(--fc-ink);
  --md-typeset-a-color: var(--fc-brass);
  --md-code-bg-color: #0d0d0c;
  --md-code-fg-color: var(--fc-stage-text);
  --md-footer-bg-color: #0d0d0c;
  --md-footer-bg-color--dark: #090908;
}

.md-typeset .highlight {
  --md-default-fg-color: var(--fc-stage-text);
  --md-default-fg-color--light: var(--fc-stage-text);
  --md-default-fg-color--lightest: var(--fc-stage-muted);
  --md-accent-fg-color: var(--fc-stage-text);
  --md-code-hl-comment-color: #8a877e;
  --md-code-hl-keyword-color: #e9a24c;
  --md-code-hl-string-color: #a8c99a;
  --md-code-hl-number-color: #8db8e0;
  --md-code-hl-name-color: var(--fc-stage-text);
  --md-code-hl-variable-color: #f0c38e;
  --md-code-hl-function-color: #d8c6f0;
  --md-code-hl-constant-color: #8db8e0;
  --md-code-hl-operator-color: var(--fc-stage-muted);
  --md-code-hl-punctuation-color: var(--fc-stage-muted);
  --md-code-hl-generic-color: var(--fc-stage-muted);
  --md-code-hl-special-color: #e9a24c;
}

/* ── Base and layout ────────────────────────────────────── */
body {
  font-feature-settings: "ss01" off;
  -webkit-font-smoothing: antialiased;
}

.md-grid {
  max-width: 80rem;
}

.md-typeset {
  font-size: clamp(16px, 0.8rem, 18px);
  line-height: 1.7;
}

.md-typeset :is(p, ul, ol, dl, blockquote) {
  max-width: var(--fc-measure);
}

.md-typeset :is(h1, h2, h3, h4) {
  color: var(--fc-ink);
  text-wrap: balance;
}

.md-typeset h1 {
  margin: 0 0 0.8rem;
  font-size: 2.3em;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.03em;
}

.md-typeset h1 + p {
  color: var(--fc-ink-2);
  font-size: 1.16em;
  line-height: 1.6;
}

.md-typeset h2 {
  margin: 2.6em 0 0.7em;
  font-size: 1.55em;
  font-weight: 650;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.md-typeset h3 {
  margin: 2em 0 0.6em;
  font-size: 1.2em;
  font-weight: 620;
  letter-spacing: -0.01em;
}

.md-typeset h4 {
  margin: 1.8em 0 0.5em;
  font-size: 1em;
  font-weight: 620;
}

.md-typeset :is(p, li, figcaption, td) {
  text-wrap: pretty;
}

.md-typeset a:not(.md-button, .fc-button, .headerlink) {
  text-decoration: underline;
  text-decoration-color: color-mix(in srgb, currentcolor 35%, transparent);
  text-decoration-thickness: 0.06em;
  text-underline-offset: 0.18em;
}

.md-typeset a:not(.md-button, .fc-button, .headerlink):hover {
  text-decoration-color: currentcolor;
}

.md-typeset .headerlink {
  color: var(--fc-rule);
}

.md-typeset :focus-visible,
.md-header :focus-visible,
.md-nav :focus-visible {
  outline: 2px solid var(--fc-brass);
  outline-offset: 2px;
  border-radius: 2px;
}

/* ── Header, tabs, sidebars ─────────────────────────────── */
.md-header {
  background-color: var(--fc-stage);
  color: var(--fc-stage-text);
  box-shadow: none;
  border-bottom: 1px solid var(--fc-stage-line);
}

.md-header :is(.md-header__button, .md-header__title, .md-source) {
  color: var(--fc-stage-text);
}

.md-header__title {
  font-weight: 600;
  letter-spacing: -0.01em;
}

.md-header__button.md-logo img {
  width: 1.3rem;
  height: 1.3rem;
}


@media screen and (max-width: 76.234375em) {
  .md-header__button.md-logo {
    display: block;
  }

  .md-sidebar--primary .md-logo {
    background: var(--fc-stage);
    border-radius: var(--fc-radius-sm);
  }
}

.md-tabs {
  background-color: var(--fc-stage);
  border-bottom: 1px solid var(--fc-stage-line);
}

.md-tabs__link {
  color: var(--fc-stage-muted);
  font-size: 0.72rem;
  font-weight: 500;
  opacity: 1;
}

.md-tabs__item--active .md-tabs__link,
.md-tabs__link:is(:hover, :focus) {
  color: var(--fc-stage-text);
}

.md-tabs__item--active {
  box-shadow: inset 0 -2px 0 var(--fc-brass-bright);
}

.md-search__form {
  border-radius: var(--fc-radius-sm);
  background-color: var(--fc-stage-raised);
  box-shadow: inset 0 0 0 1px var(--fc-stage-line);
}

.fc-source .md-source__repository {
  font-weight: 500;
}

.md-nav {
  font-size: 0.72rem;
}

.md-nav__link {
  color: var(--fc-ink-2);
}

.md-nav__link--active,
.md-nav__item .md-nav__link--active {
  color: var(--fc-brass);
  font-weight: 600;
}

.md-nav--primary .md-nav__item--section > .md-nav__link {
  color: var(--fc-ink);
  font-weight: 600;
}

.md-path {
  font-size: 0.68rem;
}

/* ── Buttons in content ─────────────────────────────────── */
.md-typeset .md-button {
  min-height: 44px;
  padding: 0.55em 1.2em;
  border: 1px solid var(--fc-rule);
  border-radius: var(--fc-radius);
  color: var(--fc-ink);
  font-weight: 600;
}

.md-typeset .md-button--primary,
.md-typeset .md-button--primary:is(:hover, :focus) {
  border-color: var(--fc-ink);
  background-color: var(--fc-ink);
  color: var(--fc-paper);
}

.md-typeset .md-button:not(.md-button--primary):is(:hover, :focus) {
  border-color: var(--fc-brass);
  background-color: transparent;
  color: var(--fc-ink);
}

/* ── Inline code, code blocks, output ───────────────────── */
.md-typeset :not(pre) > code {
  padding: 0.1em 0.38em;
  border-radius: var(--fc-radius-sm);
  background-color: var(--fc-code-inline);
  color: var(--fc-ink);
  font-size: 0.86em;
  word-break: normal;
  overflow-wrap: normal;
}

.md-typeset pre > code {
  font-size: 0.82em;
  line-height: 1.75;
}

.md-typeset .highlight,
.md-typeset pre {
  border-radius: var(--fc-radius);
}

.md-typeset .highlight :is(pre, code) {
  border-radius: var(--fc-radius);
}

.md-typeset .highlight span.filename {
  display: flex;
  align-items: center;
  margin: 1em 0 0;
  padding: 0.55em 1em;
  border-radius: var(--fc-radius) var(--fc-radius) 0 0;
  border-bottom: 1px solid var(--fc-stage-line);
  background-color: var(--md-code-bg-color);
  color: var(--fc-stage-muted);
  font-family: var(--fc-font);
  font-size: 0.74em;
  font-weight: 500;
}

.md-typeset .highlight span.filename + pre,
.md-typeset .highlight span.filename + pre > code {
  margin-top: 0;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
}

.md-typeset .fc-output pre > code {
  color: #d9d7d0;
}

.md-typeset .fc-output span.filename::before {
  width: 0.55em;
  height: 0.55em;
  margin-right: 0.6em;
  border-radius: 50%;
  background: var(--fc-brass-bright);
  content: "";
}

.md-typeset .md-clipboard {
  color: var(--fc-stage-muted);
}

/* ── Tables ─────────────────────────────────────────────── */
.md-typeset table:not([class]) {
  border: 1px solid var(--fc-rule);
  border-radius: var(--fc-radius);
  font-size: 0.86em;
  box-shadow: none;
}

.md-typeset table:not([class]) th {
  background: var(--fc-soft);
  color: var(--fc-ink);
  font-weight: 600;
}

.md-typeset table:not([class]) :is(th, td) {
  padding: 0.75em 1em;
  border-top: 1px solid var(--fc-rule);
}

.md-typeset table:not([class]) tr:first-child :is(th, td) {
  border-top: 0;
}

.md-typeset table:not([class]) td code {
  white-space: nowrap;
}

/* ── Callouts (admonitions) ─────────────────────────────── */
.md-typeset :is(.admonition, details)[class] {
  --fc-callout-bg: var(--fc-note-bg);
  --fc-callout-line: var(--fc-note-line);
  --fc-callout-ink: var(--fc-note-ink);
  max-width: var(--fc-measure);
  margin: 1.4em 0;
  padding: 0.85em 1.1em;
  border: 0;
  border-radius: var(--fc-radius);
  background-color: var(--fc-callout-bg);
  box-shadow: inset 0 0 0 1px var(--fc-callout-line);
  color: var(--fc-callout-ink);
  font-size: 0.94em;
}

.md-typeset :is(.admonition, details) :is(p, li, code) {
  color: inherit;
}

.md-typeset :is(.admonition-title, summary) {
  margin: 0 0 0.3em;
  padding: 0 0 0 1.7em;
  border: 0;
  background: transparent;
  color: var(--fc-callout-ink);
  font-weight: 650;
}

.md-typeset [class] > :is(.admonition-title, summary)::before {
  top: 0.2em;
  left: 0;
  width: 1.1em;
  height: 1.1em;
  background-color: currentcolor;
}

.md-typeset :is(.admonition, details) > :last-child {
  margin-bottom: 0;
}

.md-typeset :is(.admonition, details):is(.tip, .success) {
  --fc-callout-bg: var(--fc-tip-bg);
  --fc-callout-line: var(--fc-tip-line);
  --fc-callout-ink: var(--fc-tip-ink);
}

.md-typeset :is(.admonition, details):is(.warning, .caution, .attention) {
  --fc-callout-bg: var(--fc-warn-bg);
  --fc-callout-line: var(--fc-warn-line);
  --fc-callout-ink: var(--fc-warn-ink);
}

.md-typeset :is(.admonition, details):is(.danger, .failure, .bug) {
  --fc-callout-bg: var(--fc-danger-bg);
  --fc-callout-line: var(--fc-danger-line);
  --fc-callout-ink: var(--fc-danger-ink);
}

.md-typeset details.fc-disclosure[class] {
  --fc-callout-bg: var(--fc-card);
  --fc-callout-line: var(--fc-rule);
  --fc-callout-ink: var(--fc-ink);
}

.md-typeset details > summary {
  cursor: pointer;
  min-height: 1.6em;
}

.md-typeset details[class] > summary::after {
  top: 0.2em;
  color: var(--fc-ink-2);
}

/* ── Steps ──────────────────────────────────────────────── */
.md-typeset .fc-steps > ol {
  max-width: var(--fc-measure);
  margin: 1.4em 0;
  padding: 0;
  list-style: none;
  counter-reset: fc-step;
}

.md-typeset .fc-steps > ol > li {
  position: relative;
  margin: 0;
  padding: 0 0 1.5em 2.9em;
  counter-increment: fc-step;
}

.md-typeset .fc-steps > ol > li::before {
  position: absolute;
  top: 0;
  left: 0;
  width: 1.8em;
  height: 1.8em;
  border-radius: 50%;
  background: var(--fc-ink);
  color: var(--fc-paper);
  font: 600 0.86em/1.8em var(--fc-mono);
  text-align: center;
  content: counter(fc-step);
}

.md-typeset .fc-steps > ol > li::after {
  position: absolute;
  top: 2.2em;
  bottom: 0.4em;
  left: 0.85em;
  width: 1px;
  background: var(--fc-rule);
  content: "";
}

.md-typeset .fc-steps > ol > li:last-child::after {
  display: none;
}

.md-typeset .fc-steps > ol > li > p:first-child {
  margin-top: 0.15em;
}

.md-typeset .fc-steps > ol > li > p:first-child > strong:first-child {
  display: block;
  color: var(--fc-ink);
  font-size: 1.06em;
}

/* ── Key reference blocks ───────────────────────────────── */
.md-typeset h4.fc-key {
  margin: 0;
  padding: 1.3em 0 0.4em;
  border-top: 1px solid var(--fc-rule);
  font-family: var(--fc-mono);
  font-size: 0.95em;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.md-typeset h4.fc-key code {
  padding: 0;
  background: none;
  font-size: inherit;
}

.md-typeset h4.fc-key + dl {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  gap: 0.15em 1em;
  max-width: none;
  margin: 0.2em 0 0.7em;
  font-size: 0.9em;
  line-height: 1.55;
}

.md-typeset h4.fc-key + dl :is(dt, dd) {
  margin: 0;
  padding: 0;
}

.md-typeset h4.fc-key + dl dt {
  color: var(--fc-ink-2);
  font-weight: 500;
}

.md-typeset h4.fc-key + dl dd {
  color: var(--fc-ink);
}

/* ── Cards ──────────────────────────────────────────────── */
.md-typeset .fc-cards > ul {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
  gap: 0.8rem;
  max-width: none;
  margin: 1.2em 0;
  padding: 0;
  list-style: none;
}

.md-typeset .fc-cards > ul > li {
  position: relative;
  margin: 0;
  padding: 1em 1.1em;
  border: 1px solid var(--fc-rule);
  border-radius: var(--fc-radius);
  background: var(--fc-card);
  color: var(--fc-ink-2);
  font-size: 0.92em;
  line-height: 1.55;
  transition: border-color 120ms ease-out;
}

.md-typeset .fc-cards > ul > li:is(:hover, :focus-within) {
  border-color: var(--fc-brass);
}

.md-typeset .fc-cards > ul > li > :first-child {
  margin-top: 0;
}

.md-typeset .fc-cards > ul > li > :last-child {
  margin-bottom: 0;
}

.md-typeset .fc-cards > ul > li > p:first-child > a {
  color: var(--fc-ink);
  font-size: 1.06em;
  font-weight: 650;
  text-decoration: none;
}

.md-typeset .fc-cards > ul > li > p:first-child > a::after {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  content: "";
}

.md-typeset .fc-cards > ul > li > p:first-child > a:focus-visible {
  outline: none;
}

.md-typeset .fc-cards > ul > li:has(> p:first-child > a:focus-visible) {
  outline: 2px solid var(--fc-brass);
  outline-offset: 2px;
}

/* ── Figures ────────────────────────────────────────────── */
.md-typeset figure.fc-figure {
  margin: 1.6em 0 2em;
  padding: 0.5rem;
  border-radius: var(--fc-radius-lg);
  background: var(--fc-stage);
}

.md-typeset figure.fc-figure img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: var(--fc-radius-sm);
}

.md-typeset figure.fc-figure figcaption {
  max-width: none;
  margin: 0.6rem 0.3rem 0.15rem;
  color: var(--fc-stage-muted);
  font-size: 0.8em;
  font-style: normal;
  text-align: left;
}

.md-typeset figure.fc-figure--narrow {
  max-width: 30rem;
}

/* ── Pipeline strip (How Frame Compare works) ───────────── */
.md-typeset .fc-pipeline > ol {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0.4rem;
  max-width: none;
  margin: 1.4em 0 2em;
  padding: 0;
  list-style: none;
  counter-reset: fc-stage;
}

.md-typeset .fc-pipeline > ol > li {
  position: relative;
  margin: 0;
  padding: 0.8em 0.9em;
  border: 1px solid var(--fc-rule);
  border-radius: var(--fc-radius);
  background: var(--fc-card);
  font-size: 0.86em;
  line-height: 1.4;
  counter-increment: fc-stage;
}

.md-typeset .fc-pipeline > ol > li::before {
  display: block;
  margin-bottom: 0.35em;
  color: var(--fc-brass);
  font: 600 0.8em/1 var(--fc-mono);
  content: "0" counter(fc-stage);
}

.md-typeset .fc-pipeline a {
  color: var(--fc-ink);
  font-weight: 600;
  text-decoration: none;
}

.md-typeset .fc-pipeline a::after {
  position: absolute;
  inset: 0;
  content: "";
}

/* ── Home ───────────────────────────────────────────────── */
.fc-hero {
  background:
    radial-gradient(90% 70% at 85% 0%, rgb(233 162 76 / 10%), transparent 60%),
    var(--fc-stage);
  color: var(--fc-stage-text);
}

.fc-hero__inner {
  display: grid;
  grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.4fr);
  gap: 2.4rem;
  align-items: center;
  padding: 3.2rem 1.2rem 3.6rem;
}

.fc-hero__kicker {
  margin: 0 0 0.6rem;
  color: var(--fc-brass-bright);
  font: 600 0.6rem/1.4 var(--fc-mono);
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.fc-hero__title {
  margin: 0;
  color: var(--fc-stage-text);
  font-size: clamp(2.2rem, 4vw, 3.2rem);
  font-weight: 700;
  line-height: 1.02;
  letter-spacing: -0.035em;
}

.fc-hero__lead {
  margin: 1rem 0 0;
  color: var(--fc-stage-muted);
  font-size: 0.95rem;
  line-height: 1.6;
}

.fc-hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-top: 1.5rem;
}

.fc-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 0 1.1rem;
  border-radius: var(--fc-radius);
  font-size: 0.76rem;
  font-weight: 600;
  text-decoration: none;
  transition: filter 120ms ease-out, border-color 120ms ease-out;
}

.fc-button--primary {
  background: var(--fc-brass-bright);
  color: var(--fc-on-brass);
}

.fc-button--primary:is(:hover, :focus-visible) {
  color: var(--fc-on-brass);
  filter: brightness(1.07);
}

.fc-button--ghost {
  border: 1px solid var(--fc-stage-line);
  color: var(--fc-stage-text);
}

.fc-button--ghost:is(:hover, :focus-visible) {
  border-color: var(--fc-stage-muted);
  color: var(--fc-stage-text);
}

.fc-hero :focus-visible {
  outline: 2px solid var(--fc-brass-bright);
  outline-offset: 3px;
}

.fc-compare {
  margin: 0;
}

.fc-compare__stage {
  position: relative;
  overflow: hidden;
  aspect-ratio: 16 / 9;
  border-radius: var(--fc-radius-lg);
  background: #000;
  box-shadow: 0 0 0 1px var(--fc-stage-line), 0 1.5rem 4rem -1.5rem rgb(0 0 0 / 80%);
  --fc-pos: 50%;
}

.fc-compare__img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.fc-compare__img--top {
  clip-path: inset(0 0 0 var(--fc-pos));
}

.fc-compare__rule {
  position: absolute;
  top: 0;
  bottom: 0;
  left: var(--fc-pos);
  width: 2px;
  margin-left: -1px;
  background: var(--fc-stage-text);
  pointer-events: none;
}

.fc-compare__knob {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 2.2rem;
  height: 2.2rem;
  margin: -1.1rem 0 0 -1.1rem;
  border-radius: 50%;
  background: var(--fc-stage-text);
  box-shadow: 0 0.2rem 0.9rem rgb(0 0 0 / 45%);
}

.fc-compare__knob::before {
  position: absolute;
  inset: 0;
  color: var(--fc-stage);
  font: 700 0.8rem/2.2rem var(--fc-font);
  text-align: center;
  content: "‹ ›";
}

.fc-compare__range {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  opacity: 0;
  cursor: ew-resize;
}

.fc-compare__stage:has(.fc-compare__range:focus-visible) {
  outline: 2px solid var(--fc-brass-bright);
  outline-offset: 3px;
}

.fc-compare__label,
.fc-compare__frame {
  position: absolute;
  padding: 0.25rem 0.5rem;
  border-radius: var(--fc-radius-sm);
  background: rgb(17 17 16 / 72%);
  font: 600 0.56rem/1.3 var(--fc-mono);
  pointer-events: none;
}

.fc-compare__label {
  top: 0.75rem;
}

.fc-compare__label--ref {
  left: 0.75rem;
  color: var(--fc-ref);
  box-shadow: inset 0 0 0 1px rgb(233 162 76 / 45%);
}

.fc-compare__label--cmp {
  right: 0.75rem;
  color: var(--fc-cmp);
  box-shadow: inset 0 0 0 1px rgb(198 222 244 / 45%);
}

.fc-compare__frame {
  bottom: 0.75rem;
  left: 0.75rem;
  color: var(--fc-stage-text);
}

.fc-compare__credit {
  margin-top: 0.6rem;
  color: var(--fc-stage-muted);
  font-size: 0.56rem;
}

.fc-compare__credit a {
  color: inherit;
}

.md-content__inner:has(.fc-home) {
  padding-top: 0.6rem;
}

.md-typeset .fc-home {
  max-width: 62rem;
  margin: 0 auto;
}

.md-content__inner:has(.fc-home) > .md-content__button {
  display: none;
}

.md-typeset .fc-home > h2 {
  margin-top: 2.4em;
}

.md-typeset .fc-home .tabbed-set {
  max-width: none;
}

.md-typeset .fc-home .tabbed-block > figure {
  margin-top: 0.8rem;
}

.md-typeset .fc-features {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin: 1.2em 0;
}

.md-typeset .fc-feature {
  overflow: hidden;
  border: 1px solid var(--fc-rule);
  border-radius: var(--fc-radius-lg);
  background: var(--fc-card);
}

.md-typeset .fc-feature > :not(.fc-feature__visual) {
  margin-right: 1.2rem;
  margin-left: 1.2rem;
}

.md-typeset .fc-feature h3 {
  margin-top: 1rem;
}

.md-typeset .fc-feature__visual {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 9.5rem;
  margin: 0;
  padding: 1rem;
  background: var(--fc-stage);
  color: var(--fc-stage-text);
}

.md-typeset .fc-feature__visual img {
  display: block;
  width: 100%;
  border-radius: var(--fc-radius-sm);
}

.md-typeset .fc-feature__visual pre {
  margin: 0;
}

.md-typeset .fc-feature__visual pre > code {
  padding: 0;
  background: none;
  font-size: 0.72rem;
}

.md-typeset ol.fc-strip {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0.3rem;
  max-width: none;
  margin: 0;
  padding: 0;
  list-style: none;
}

.md-typeset .fc-strip li {
  margin: 0;
  color: var(--fc-stage-muted);
  font: 500 0.52rem/1.3 var(--fc-mono);
}

.md-typeset .fc-strip img {
  margin-bottom: 0.3rem;
  aspect-ratio: 16 / 9;
  object-fit: cover;
}

.md-typeset .fc-strip .fc-strip__user {
  color: var(--fc-brass-bright);
}

.md-typeset .fc-strip .fc-strip__user img {
  outline: 2px solid var(--fc-brass-bright);
  outline-offset: 1px;
}

/* ── Footer ─────────────────────────────────────────────── */
.md-footer-meta {
  background-color: var(--md-footer-bg-color--dark);
}

.fc-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem 2rem;
  align-items: baseline;
  justify-content: space-between;
  width: 100%;
  margin: 0;
  padding: 1rem 0;
  font-size: 0.64rem;
}

.fc-footer__links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 1.2rem;
}

html .md-footer-meta.md-typeset .fc-footer a:not(:focus, :hover) {
  color: var(--fc-stage-muted);
  text-decoration: none;
}

.md-footer .fc-footer a:is(:hover, :focus) {
  color: var(--fc-stage-text);
}

.fc-footer__legal {
  margin: 0;
  color: #8a877e;
}

/* ── 404 ────────────────────────────────────────────────── */
.md-typeset .fc-404 {
  max-width: 34rem;
  margin: 2rem 0 4rem;
}

.md-typeset .fc-404__code {
  margin: 0;
  color: var(--fc-brass);
  font: 600 0.8rem/1 var(--fc-mono);
  letter-spacing: 0.14em;
}

.md-typeset .fc-404__links {
  margin-top: 1.4em;
}

/* ── Responsive ─────────────────────────────────────────── */
@media screen and (max-width: 76.234375em) {
  .md-typeset .fc-pipeline > ol {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media screen and (max-width: 59.984375em) {
  .fc-hero__inner {
    grid-template-columns: 1fr;
    gap: 1.6rem;
    padding: 2rem 0.8rem 2.4rem;
  }

  .md-typeset .fc-features {
    grid-template-columns: 1fr;
  }
}

@media screen and (max-width: 44.984375em) {
  .fc-hero__actions .fc-button {
    flex: 1 1 100%;
  }

  .fc-compare__label {
    top: 0.5rem;
    font-size: 0.5rem;
  }

  .fc-compare__source {
    display: none;
  }

  .fc-compare__label--ref {
    left: 0.5rem;
  }

  .fc-compare__label--cmp {
    right: 0.5rem;
  }

  .md-typeset .fc-pipeline > ol {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .md-typeset ol.fc-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .md-typeset table:not([class]) td code {
    white-space: normal;
  }
}

@media (prefers-reduced-motion: reduce) {
  .fc-button,
  .md-typeset .fc-cards > ul > li {
    transition: none;
  }
}
```

## `docs/javascripts/compare-slider.js`

The range input carries keyboard and pointer input; arrow keys move the divider. Without
JavaScript the hero shows a fixed 50/50 split.

```js
// Home page before/after comparison. The range input carries keyboard and pointer
// input; this script mirrors its value into the --fc-pos custom property.
function initCompareSliders() {
  for (const figure of document.querySelectorAll("[data-fc-compare]")) {
    const stage = figure.querySelector(".fc-compare__stage");
    const range = figure.querySelector(".fc-compare__range");
    if (!stage || !range || range.dataset.fcBound === "true") {
      continue;
    }
    const update = () => stage.style.setProperty("--fc-pos", `${range.value}%`);
    range.addEventListener("input", update);
    range.dataset.fcBound = "true";
    update();
  }
}

if (window.document$) {
  window.document$.subscribe(initCompareSliders);
} else {
  document.addEventListener("DOMContentLoaded", initCompareSliders);
}
```

## `docs/assets/brand/logo.svg`

The header mark: a frame split by a vertical line, the right half filled with brass.

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 26" width="26" height="26"><rect x="1.5" y="4.5" width="23" height="17" rx="3.5" fill="none" stroke="#edece8" stroke-width="1.6"/><path d="M13 4.5h8a3.5 3.5 0 0 1 3.5 3.5v10a3.5 3.5 0 0 1-3.5 3.5h-8z" fill="#e9a24c"/><path d="M13 1.5v23" stroke="#edece8" stroke-width="1.6" stroke-linecap="round"/></svg>
```

## `docs/assets/brand/favicon.svg`

The same mark with an outline that follows the browser's color scheme.

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 26"><style>.o{stroke:#1b1a17}@media (prefers-color-scheme:dark){.o{stroke:#edece8}}</style><rect class="o" x="1.5" y="4.5" width="23" height="17" rx="3.5" fill="none" stroke-width="2"/><path d="M13 4.5h8a3.5 3.5 0 0 1 3.5 3.5v10a3.5 3.5 0 0 1-3.5 3.5h-8z" fill="#e9a24c"/><path class="o" d="M13 1.5v23" stroke-width="2" stroke-linecap="round"/></svg>
```

## Fonts

Download these four files from the jsDelivr mirror of the Fontsource npm packages,
version `5.3.0` (published 2026-07-19), and verify each SHA-256 before adding it. A hash
mismatch is a stop.

| Saved as | URL | SHA-256 |
| --- | --- | --- |
| `docs/assets/fonts/geist-latin-wght-normal.woff2` | `https://cdn.jsdelivr.net/npm/@fontsource-variable/geist@5.3.0/files/geist-latin-wght-normal.woff2` | `19f9c92546aa300c312235e3125af1b81394d8db9a4bc4a425cd5b641d2d54e1` |
| `docs/assets/fonts/geist-mono-latin-wght-normal.woff2` | `https://cdn.jsdelivr.net/npm/@fontsource-variable/geist-mono@5.3.0/files/geist-mono-latin-wght-normal.woff2` | `684ad5b531f81d43c1e8c7038262d5db7cdc1f68006e04d6c7769efa8d33c8cc` |
| `docs/assets/fonts/OFL-Geist.txt` | `https://cdn.jsdelivr.net/npm/@fontsource-variable/geist@5.3.0/LICENSE` | `71609cbb5c78b5870d712eab73a31d76622635c6ed034ab5cee3b9ecbda8685f` |
| `docs/assets/fonts/OFL-Geist-Mono.txt` | `https://cdn.jsdelivr.net/npm/@fontsource-variable/geist-mono@5.3.0/LICENSE` | `cc815ed4fc045f0e991abb10395b7932bd028c6a067deb13316d6002105074e6` |

```bash
mkdir -p docs/assets/fonts
base=https://cdn.jsdelivr.net/npm/@fontsource-variable
curl -fsSL -o docs/assets/fonts/geist-latin-wght-normal.woff2 "$base/geist@5.3.0/files/geist-latin-wght-normal.woff2"
curl -fsSL -o docs/assets/fonts/geist-mono-latin-wght-normal.woff2 "$base/geist-mono@5.3.0/files/geist-mono-latin-wght-normal.woff2"
curl -fsSL -o docs/assets/fonts/OFL-Geist.txt "$base/geist@5.3.0/LICENSE"
curl -fsSL -o docs/assets/fonts/OFL-Geist-Mono.txt "$base/geist-mono@5.3.0/LICENSE"
shasum -a 256 docs/assets/fonts/*
```

The fonts are licensed under the SIL Open Font License 1.1, which permits embedding and
redistribution with the license text; the two `OFL-*.txt` files are that text.
