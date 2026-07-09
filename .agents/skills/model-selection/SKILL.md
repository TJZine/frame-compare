---
name: model-selection
description: Use when a user asks which model or reasoning effort to use for a Frame Compare task, or when preparing a high-risk handoff that should include a model suggestion for the next session.
---

# Model Selection

## Overview

Use this skill to recommend the least expensive GPT-5.6 setup that is still reliable for the next Frame Compare session.

Use the tracked `worker` (`gpt-5.6-sol medium`) for normal implementation. Use
`worker_terra` (`gpt-5.6-terra medium`) only for explicitly approved, bounded,
exact, cheap-to-verify units with clear stop conditions.

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

- Score `0-1`: omit `MODEL_SUGGESTION` unless asked; if asked, use the current
  model or `gpt-5.6-sol medium`. `gpt-5.6-terra medium` is appropriate through
  `worker_terra` only when the unit is exact, bounded, cheap to verify, and has
  explicit stop/escalation rules.
- Score `2-3`: include `MODEL_SUGGESTION`; planner `gpt-5.6-sol medium`,
  implementer `gpt-5.6-sol medium`, reviewer `gpt-5.6-sol medium` or `high`
  when hidden architecture risk is present.
- Score `4+`: include `MODEL_SUGGESTION`; planner `gpt-5.6-sol high`,
  implementer `gpt-5.6-sol medium` by default, reviewer `gpt-5.6-sol high`.

## Role Defaults

- `planner`: `gpt-5.6-sol high`
- `reviewer`: `gpt-5.6-sol high`
- `worker`: `gpt-5.6-sol medium`; normal implementation default
- `worker_terra`: `gpt-5.6-terra medium`; explicitly eligible cost-sensitive units only
- `docs_researcher`: `gpt-5.6-terra medium`
- `explorer`: keep `gpt-5.3-codex-spark xhigh` for intentionally latency-sensitive code exploration
- `explorer_fallback`: `gpt-5.6-terra high`
- `monitor`: keep `gpt-5.3-codex-spark low`
- `monitor_fallback`: `gpt-5.6-luna low`

Preserve the current reasoning effort for the first GPT-5.6 run, then compare
the same effort with one level lower on representative tasks. Use `xhigh` only
for unusually difficult quality-first work. Reserve `max` for measured cases
where `xhigh` is insufficient; do not make `max` or host-specific `ultra` a
tracked default.

Use `gpt-5.5` at the same effort as the reliability fallback for Sol/Terra
roles when GPT-5.6 is unavailable. Use `gpt-5.4-mini` only for low-risk,
cost-sensitive work that would otherwise use Luna or a lightweight Terra role.

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
- Routing ordinary or ambiguous implementation through `worker_terra` only to save cost
