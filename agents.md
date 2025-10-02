# agents.md — Working with Codex (GPT‑5‑Codex)

## Autonomy & Boundaries
- Ask first: external services, public API/CLI changes, network beyond slow.pics.
- Never: commit secrets or run destructive commands.

## Repo Invariants
- No `sys.exit` in libraries; raise exceptions.
- Config lives in TOML → dataclasses.
- No hidden globals; functions pure unless explicitly I/O.
- Type hints + docstrings; `logging` module for library logs.

# Tools (MCP) — What to use and how

> Use MCP tools in this order for most tasks: **ripgrep → context7 → sequential_thinking → memory **. Start every session with the **Tool Discovery** macro below so Codex knows exact method names/params for your installed servers.

### ripgrep (code evidence)
**Purpose.** Find flags, examples, outputs, and metric implementations in the repo quickly.

### sequential_thinking (gated plans)
**Purpose.** Create stepwise plans with checkpoints.

**Tips.** Keep steps small; require a DIFF preview before applying file edits; abort if a step exceeds ~200 changed lines.

### memory (reference)
**Purpose.** Persist decisions, version facts, and runbooks for future sessions.

**What to store.**
- “README Style Policy”; “README update <date>” notes.
- Runtime/library versions used in examples (Python, OpenCV, NumPy, ffmpeg/VapourSynth).
- Policies: frame-selection defaults, output structure.

**Macros.**

- **Search entries**
  ```
  memory.search tags: ["policy","frames"] query: "seed|random_frames|user_frames"
  ```

**Guardrails.** Never store secrets or user data; include dates and tags for retrieval.

---

### context7 (docs on tap)
**Purpose.** Pull *official docs* snippets into context so edits match real APIs (e.g., OpenCV color conversion, NumPy image ops, ffmpeg/VapourSynth usage).

**Use when.**
- whenever relevant libraries from context 7 are referenced
- Unsure about library calls or parameters (OpenCV cvtColor codes, optical-flow APIs).
- Need canonical examples straight from docs.
- Want the latest guidance without hard-coding long quotes into README.

**Macros.**

- **Cross-check code vs docs**
  ```
  Compare our use of <function> (file:line) with the official context7 snippet. List mismatches and propose minimal fixes.
  ```

**Guardrails.** Prefer official domains; avoid user blogs. Summarize—don’t dump full pages. Note doc versions; if versionless, say “as of <today>”.

### Recipes (tool interplay)

- **Doc‑verified change**
  1) ripgrep: find the call site and current flags.
  2) context7: pull the official function docs.
  3) sequential_thinking: propose a 3‑step edit with a DIFF preview.
  4) memory: record “API rationale” with doc link & date.

- **README update loop**
  1) ripgrep: extract flags/examples/outputs.
  2) context7: confirm definitions (e.g., luma/motion) from official docs.
  3) sequential_thinking: apply humanized edits section‑by‑section.
  4) memory: persist style policy and changelog note.

