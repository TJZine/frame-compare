---
name: fc2-next-prompt
description: Use when you want to advance the FC-2.0 workflow by extracting the exact '## NEXT AGENT PROMPT (COPY/PASTE)' block from a run artifact so the human can paste it into the next agent.
---

# FC-2.0 NEXT Prompt Extractor Skill

## Goal

Reduce operator work to: provide the artifact path → copy/paste the extracted NEXT block.

## Script

```bash
python3 codex-skills/fc2-next-prompt/scripts/extract_next_prompt.py .agent-workflow/runs/<RUN_ID>/<artifact>-vN.md
```

## Notes

- The authoritative enforcement rules are still `scripts/validate_run_artifacts.py`.
- This tool is for convenience (extracting the block), not validation.
