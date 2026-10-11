---
search:
  exclude: true
---

# Codex prompt: documentation refresh orchestrator

Paste everything below the first line into a fresh Codex chat on the `frame-compare`
project (local environment, this checkout, branch `agent/e2e-test-strategy`). Use a
capable orchestrator model at high reasoning. The section "Physical Windows host"
at the end is a separate prompt for a Codex chat on the Windows capture machine; do
not paste it into the orchestrator.

Prepared 2026-10-09 against base `80beafdcdabc7ac556f78fada5e7593b89e8880c`.

---

You are the orchestrator for the documentation refresh. The specification is
`docs/plans/2026-10-08-documentation-refresh.md` and its assets folder
`docs/plans/2026-10-08-documentation-refresh-assets/`. Read the plan in full first,
then `AGENTS.md` and `.agents/project.md`. The plan is decision-complete: if anything
conflicts with it, or a decision it does not make is needed, stop that unit and tell
me.

## What I authorize, for this plan only

- Separate Codex implementation and review chats through the
  `orchestrate-implementation-chats` skill.
  - Implementation unit U1 uses the `worker` preset; U2–U9 use the `worker_luna`
    preset. Read `.codex/agents/worker.toml` (U1) or `.codex/agents/worker-luna.toml`
    (U2–U9) from this checkout and pass its `model` and `model_reasoning_effort`
    explicitly to `create_thread` (`model` and `thinking`). Put its
    `developer_instructions` at the top of each child prompt, followed by the override
    below.
  - Each wave's review uses the `reviewer` preset (Sol): read
    `.codex/agents/reviewer.toml` and pass its `model` and `model_reasoning_effort`
    explicitly in the same way, with its `developer_instructions` at the top.
  - One terminal callback from each child to this chat. Children cite this message as
    the human authorization for that callback.
- Local commits on `agent/e2e-test-strategy` made by you: one initial plan commit, then
  one commit per accepted unit, each staged by explicit path (never `git add -A` or
  `git add .`). Stage a child's moves and deletions yourself (`git add` on the old and
  new paths).

Not authorized: pushes, PRs, branch switches, worktrees, rebases, resets, stashes,
dependency or lockfile changes (`uv sync`, `uv lock`), deployment, publishing, and
requests to live services (slow.pics, webhooks, TMDB, DVB downloads). If `zensical`
is missing from the environment, stop and ask me before any sync.

## Child override (put this directly after the preset instructions)

> This unit follows `docs/plans/2026-10-08-documentation-refresh.md`, which is
> stricter than the preset text above. Do not resolve uncertainty yourself: any
> ambiguity, fact you cannot verify, failed check, missing input, or decision the plan
> does not make is a stop. Report `blocked` to the orchestrator with the exact
> question and evidence, and change nothing further. Write prose under the plan's
> "points rule". Never commit, and run no Git command that changes the index,
> history, or branch. Edit only the files the plan assigns to your unit. U1 only: an
> environmental failure may be diagnosed and the same command rerun, exactly as the
> plan's U1 "Environment failures" rule allows.

Each child packet contains: the unit's section from the plan ("Units"), the plan
sections "Approved decisions" and "Every unit", the paths of its specification
assets, its owned files, its acceptance checks and stop conditions, this checkout's
path and branch, the base commit, the orchestrator thread ID, and the callback rule.
The child's terminal report lists: changed files, checks run with results, every
"must not appear" check, anything `blocked`, and limits.

## Procedure

1. **Baseline.** Record `HEAD` and `git status --porcelain`. Besides the untracked
   plan, its assets folder, and this prompt, the tree may hold other untracked files
   under `docs/prompts/` that belong to other work; any tracked modification, or any
   untracked file outside `docs/plans/` and `docs/prompts/`, is a stop. Commit only
   `docs/plans/2026-10-08-documentation-refresh.md`,
   `docs/plans/2026-10-08-documentation-refresh-assets/`, and this prompt as
   `docs(plan): add the documentation refresh plan`. Leave every other untracked file
   untouched.
2. **U1 prerequisite.** Ask me to confirm the two DVB files are in
   `$HOME/FrameCompareCapture/source/` (capture specification, Prerequisites). Dispatch
   U1 only after I confirm.
3. **Wave A.** Dispatch U2–U9 in parallel, and U1 once its prerequisite is met. Record
   a dispatch map (unit, real thread ID, model and effort, owned files) in a short
   "Execution record" section appended to the plan. When nothing useful remains, end
   your turn and let callbacks resume you; do not poll.
4. **Per unit.** On each callback: check the actual diff stays inside the unit's owned
   files and matches its specification; rerun the unit's acceptance checks yourself;
   send fixes back to the same child; on `blocked`, resolve only if the plan already
   answers it, otherwise pause that unit and bring me the question. Then commit the
   unit (`docs(<area>): …` Conventional Commit subject naming the unit).
5. **Wave A gates, once, serially, after every wave-A unit is committed:**
   - the orchestrator checks in the plan's "Verification" section, in order:
     API-doc drift, strict build, search-scope check, the full guard-test list, and
     the link-residue `rg`;
   - rendered visual QA against the plan's checklist at 1440 × 900 and 390 × 844,
     light and dark (clear site storage between schemes). Save one screenshot per
     checklist row under `.tmp/docs-refresh-qa/wave-a/` and note pass or fail for each.
   A failure goes back to the owning unit's child; rerun the affected gates after the
   fix.
6. **Wave A review.** Send the wave's commit range, the plan, its assets, and the QA
   screenshot folder to one `reviewer` chat. Its report must include:
   - plan fidelity, with a deviations register (a deviation stays only when it is
     strictly better, with evidence; otherwise it is reverted);
   - style-guide conformance (terminology, headings, link rules, "must not appear");
   - factual accuracy of every changed statement against the code and authority
     documents, with `file:line` evidence;
   - rendered visual QA: review the saved screenshots against the visual
     specification's "Behavior by context" table and the plan's QA checklist.
   Adjudicate every finding with evidence before acting; send accepted fixes to the
   owning child; commit fixes per unit; rerun the gates they affect.
7. **Wave B (U10).** Tell me wave A is complete and give me the commit SHA. I make that
   commit available on the Windows host and run the "Physical Windows host" prompt
   there. When I return its patch (`u10.patch`), apply it with `git apply --check`
   then `git apply`, verify it touches only U10's owned files, rerun the strict build,
   the guard tests, and the QA rows for Windows portable and VSView alignment review,
   then send the U10 commit range to a fresh `reviewer` chat with the same report
   requirements, adjudicate, and commit as `docs(images): add physical Windows
   captures (U10)`.
8. **Close.** Append the execution record (commits, units with preset and actual
   model/effort, gate results with every skip reason, review adjudications and
   deviations) to the plan. If I have accepted the assets, change the plan's status to
   `Status: Historical`; otherwise leave it `Active` and say why. Commit as
   `docs(plan): record the documentation refresh outcome`.

## Final report, then stop

- commits (SHA and subject);
- each unit's preset and actual model and effort;
- gate results with skip reasons, and the QA checklist outcome;
- review adjudications and kept deviations;
- anything still `blocked` or open, including U10 if it has not run.

---

## Physical Windows host (separate prompt for unit U10)

Paste this into a Codex chat on the physical Windows 10/11 x64 capture host, in a
clean clone of `TJZine/frame-compare` checked out at the wave-A commit I give you.
Use the `worker_luna` preset's model and reasoning effort from
`.codex/agents/worker-luna.toml` in that clone, as the plan assigns.

You run unit U10 of `docs/plans/2026-10-08-documentation-refresh.md`. Read that
plan's "U10" section, "Every unit", and the capture specification
`docs/plans/2026-10-08-documentation-refresh-assets/capture-spec.md`, sections
"Physical Windows captures", "Asset table", and "Privacy review". Also read
`AGENTS.md` and `.agents/project.md`.

Authorized: building the portable bundle locally from the checked-out commit with the
runbook's "Windows portable local packaging path" commands; the capture workspace
`C:\FrameCompareDemo\`; the temporary `LOCALAPPDATA` override and cleanup exactly as
specified; editing only `docs/images/windows-portable-install.png`,
`docs/images/vsview-alignment-panel.webp`, set 2 of `docs/images/README.md`, the
VSView figure in `docs/guides/vsview-review.md`, and the install figure's `width` and
`height` in `docs/windows-portable.md`.

Not authorized: commits, pushes, branch changes, dependency or lockfile changes,
changes to your real Frame Compare installation or system settings, production
signing keys, and requests to live services.

Steps that need a visible desktop (the VSView panel, the Snipping Tool) are done by
the maintainer at the keyboard while you give exact instructions, unless this session
has desktop control. Any step that does not behave as written, any private string in a
capture, or any size limit exceeded is a stop: report `blocked` with evidence.

When done, mark the new image for the patch and write it (this disposable clone
is the only place an index change is allowed):

```powershell
git add --intent-to-add docs/images/vsview-alignment-panel.webp
git diff --binary > C:\FrameCompareDemo\u10.patch
```

Then record the commit, Windows build,
display scaling, bundle SHA, and the privacy review in your report, and stop. The
maintainer carries `u10.patch` back to the orchestrator.
