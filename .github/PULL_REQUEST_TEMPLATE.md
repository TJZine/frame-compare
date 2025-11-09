## Decision Minute (required)
**Summary (1–3 lines):**  
**Why now / context:**  
**Alternatives considered (brief):**  
**Risks & rollback:**  
**Verification (commands + exit codes):**
- `uv run pyright --warnings` → `0`
- `uv run ruff check` → `0`
- `uv run pytest -q -m "not (network or e2e or slow)"` → `0`

**Files of interest (ripgrep patterns):** `tone_curve|_ColorRange|Mobius|Hable`

<details><summary>Agent notes (auto-filled)</summary>

**Planning:** use sequential thinking.  
**Docs:** include context7 snippets (title + link + date) for any best-practice.  
**Search:** use ripgrep first; list globs excluded by ignore files.

</details>

