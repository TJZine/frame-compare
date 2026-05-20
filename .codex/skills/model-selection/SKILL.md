---
name: model-selection
description: Use when a user asks which model or reasoning effort to use for a Frame Compare task, or when preparing a high-risk handoff that should include a model suggestion for the next session.
---

# Model Selection

## Overview

Use this skill to recommend the cheapest model setup that is still reliable for the next Frame Compare session.

Default low, escalate only when risk is real.

## Use This Skill For

- Explicit asks like "what model should I use for this plan?"
- Preparing a high-risk handoff
- Architecture-heavy planning or review around hotspots, public contracts, or release paths

Do not use this skill for every routine handoff.

## Risk Score

Start at `0` and add `+1` for each:

- hotspot file or composition root involved
- ownership move or import-layer change
- more than one repo-local boundary skill applies
- public CLI/config/JSON/release behavior is involved
- Docker, Windows portable, FFmpeg, VapourSynth, TMDB, slow.pics, or browser-open behavior is involved
- mixed routing ambiguity or likely hidden dependency

## Recommendation Rules

- Score `0-1`: omit `MODEL_SUGGESTION` unless asked; if asked, use current model or `gpt-5.5 medium`.
- Score `2-3`: include `MODEL_SUGGESTION`; planner/implementer `gpt-5.5 medium`, reviewer `gpt-5.5 medium` or `high` for hidden architecture risk.
- Score `4+`: include `MODEL_SUGGESTION`; planner `gpt-5.5 high`, implementer `gpt-5.5 medium` by default, reviewer `gpt-5.5 high`.

Use `gpt-5.4` as fallback when `gpt-5.5` is unavailable. Use smaller models only for low-risk read-only sidecars.

## Handoff Format

```text
MODEL_SUGGESTION
PLANNER: <model or n/a>
IMPLEMENTER: <model or n/a>
REVIEWER: <model or n/a>
WHY: <short reason tied to risk signals>
```

## Common Mistakes

- Emitting model advice for every handoff
- Using high effort just because work is important
- Recommending mini models for ambiguous release, runtime, or public-contract work
