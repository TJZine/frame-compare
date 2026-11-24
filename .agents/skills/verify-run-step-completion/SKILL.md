---
name: verify-run-step-completion
description: Check exception precedence and terminal progress status when changing RunSteps.run or StepCompletion.write in Frame Compare.
---

# Verify run-step completion

From the checkout root, run the bounded model against the real step runner. The
regular CI pytest job collects this file on every PR.

```sh
uv run --no-sync pytest -q tests/orchestration/test_run_step_completion_model.py
```

A failed step must keep its exception and terminal status when writing its last
progress line also fails. Otherwise a closed stderr can change the CLI exit code
for an alignment cleanup failure. A completion write that fails after success
or a handled warning must itself surface, even inside a caller's exception handler.

The executable transition table in
`tests/orchestration/test_run_step_completion_model.py` models one admitted,
warn-only alignment step. Its paths start at the body, pass through the success
description and progress advance when reachable, and end with one completion
write. Pytest replays all six terminal paths with both write outcomes and both
caller contexts on production code. The fixture controls the callbacks and
compares the exception object, progress events, and return value. The scope
includes a body raising cancellation. Timing of incoming task cancellation,
native cleanup, persisted run records and terminal rendering have separate
integration coverage.

On the base branch, find the last verification update with
`git log -1 --format=%H -- .agents/skills/verify-run-step-completion/SKILL.md`.
Review `RunSteps.run`, `RunSteps._raised_status` and `StepCompletion.write` in
`src/frame_compare/orchestration/execution.py` when those paths change.
The module-level `run_selection_steps` supplies the production fatal-error policy
for alignment.

A failing case name gives the caller context, completion write result and
ordered callback outcomes. For example, on the parent of the fix in PR #187,
`a9b82f13`, `normal-caller-write-failed-body.cleanup-error` observed an
`OSError` in place of `AudioAlignmentCleanupError`. The later `e692e4ae`
implementation still lost errors from the description and progress advance.
Fetch the historical controls with
`git fetch origin refs/pull/187/head refs/pull/188/head`.
To replay either version, create a disposable worktree at that commit, copy the
current model file into its corresponding tests directory, and run the command
there.

For a changed contract, compare the shortest failing trace with the production
callback order and the outcome the caller should receive. Update the transition
relation and adapter together when that contract changes. Recheck the source mapping and replay a historical failure before recording
any change to the model’s coverage here.
