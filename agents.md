# agents.md — Working with Codex (GPT‑5‑Codex)

## Autonomy & Boundaries
- Ask first: external services, public API/CLI changes, network beyond slow.pics.
- Never: commit secrets or run destructive commands.

## Repo Invariants
- No `sys.exit` in libraries; raise exceptions.
- Config lives in TOML → dataclasses.
- No hidden globals; functions pure unless explicitly I/O.
- Type hints + docstrings; `logging` module for library logs.

### Start Session — Auto-Continue (self-executing)

GOAL
Infer the task from my last message in this chat (or from TARGET_TASK below) and complete it end-to-end **without pausing** unless there’s an error or a required tool is missing.

TARGET_TASK
# Optional: override here; otherwise infer from the last user instruction.

RUN MODE
run_mode: auto
pause_on: ["error", "missing_tool", "large_diff"]
large_diff_threshold_lines: 200
max_results_per_table: 100

RULES
- Do **not** ask for approval between steps.
- Never emit the word “STOP” unless a pause_on condition is met.
- If a diff would exceed large_diff_threshold_lines, split it and continue automatically.

STEPS
1) Tool discovery
   - List tools for ripgrep, context7, sequential_thinking, memory with exact names and required params.
   - If names/params differ from assumptions, **use the discovered names** and continue.
   - If a required tool is missing, report `missing_tool` and stop; otherwise proceed automatically.

2) Evidence sweep (ripgrep)
   - Config/CLI: argparse|click|typer; YAML/TOML/JSON loads; env vars → table {Flag/Key/Env, Type?, Default?, File:Line, Context}
   - Outputs: cv2/PIL/imageio/plt saves; csv/json dump; os.makedirs/Path().mkdir → {Artifact, Format, Path pattern, Producer (file:line)}
   - Cap results to max_results_per_table; if larger, summarize by directory and continue.

3)  Docs check (context7)
   - If the task touches OpenCV/NumPy/ffmpeg/VapourSynth  or any other relevant APIs, fetch official snippets (title + link + example). Note doc version/date.
   - Do not paste long excerpts. Continue.

4) Plan (sequential_thinking)
   - Draft a 3–7 step plan tailored to TARGET_TASK: inputs (evidence/docs), exact edits (files/sections), success checks (ripgrep queries or minimal run cmd), rollback notes.
   - **Continue immediately** to execution.

5) Execute
   - Apply small diffs (≤ large_diff_threshold_lines per step). If larger, split into sub-steps.
   - After each step, run the success checks from (4). If failing, rollback that step and try the smallest passing alternative.

6) Persist (memory)
   - Save key decisions/runbook entries (e.g., “README update <YYYY-MM-DD>”, “README Style Policy”, versions used), with tags for retrieval.

7) Verify & summarize
   - Re-run targeted ripgrep checks to confirm doc↔code consistency or task success.
   - Output a concise summary (what changed, files touched, follow-ups).


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

