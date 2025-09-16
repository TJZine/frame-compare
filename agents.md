# agents.md — Working with Codex (GPT‑5‑Codex) on `comparison_tool/`

## Modes, Models, Reasoning
- **Local** for VS/ffmpeg/media; **Cloud** for long tests & PRs.
- **Model**: default `gpt-5-codex` for coding; base `gpt-5` for explanations.
- **Reasoning**: Medium by default; High for interface design and tests.

## Autonomy & Boundaries
- Allowed: edit under `comparison_tool/`, run tests, open PRs.
- Ask first: external services, public API/CLI changes, network beyond slow.pics.
- Never: commit secrets or run destructive commands.

## Repo Invariants
- No `sys.exit` in libraries; raise exceptions.
- Config lives in TOML → dataclasses.
- No hidden globals; functions pure unless explicitly I/O.
- Type hints + docstrings; `logging` module for library logs.

## Testing Policy
- Unit: `utils`, `analysis`, mocked slow.pics.
- Integration (local): small sample media for `vs_core` + writers.
- Golden/parity: HDR & SDR sample pairs; frame lists + filenames.

