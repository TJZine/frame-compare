---
search:
  exclude: true
---

# Codex prompt: documentation site redesign orchestrator

Paste everything below the first line into a fresh Codex chat on the `frame-compare`
project (local environment, this checkout on macOS, branch `v0.7.0`). Use a capable
orchestrator model at high reasoning.

Prepared 2026-10-12 against base `c537f94db4deaa5834c9d6a5fb31635b57860a0a`.

---

You are the orchestrator for the documentation site redesign. The specification is
`docs/plans/2026-10-12-documentation-site-redesign.md` and its assets folder
`docs/plans/2026-10-12-documentation-site-redesign-assets/`. Read the plan in full
first, then `AGENTS.md` and `.agents/project.md`. The plan is decision-complete: if
anything conflicts with it, or a decision it does not make is needed, stop that unit and
tell me.

## What I authorize, for this plan only

- Separate Codex implementation and review chats through the
  `orchestrate-implementation-chats` skill.
  - Units U1, U3, U4, and U9 use the `worker_luna` preset; U2, U5, U6, U7, and U8 use
    the `worker` preset, as the plan assigns. Read `.codex/agents/worker-luna.toml` or
    `.codex/agents/worker.toml` from this checkout and pass its `model` and
    `model_reasoning_effort` explicitly to `create_thread` (`model` and `thinking`). Put
    its `developer_instructions` at the top of each child prompt, followed by the child
    override below. Naming a role is not enough; the TOML values must be passed.
  - Each wave's review uses the `reviewer` preset (Sol): read
    `.codex/agents/reviewer.toml` and pass its `model` and `model_reasoning_effort`
    explicitly in the same way, with its `developer_instructions` at the top.
  - One terminal callback from each child to this chat. Children cite this message as
    the human authorization for that callback.
- Local commits on `v0.7.0` made by you: one initial plan commit, then one commit per
  accepted unit, each staged by explicit path (never `git add -A` or `git add .`). Stage
  a child's moves and deletions yourself (`git add` on the old and new paths).
- These network requests only: the four font and license downloads from
  `cdn.jsdelivr.net` listed in the theme specification's "Fonts" section (U1).

Not authorized: pushes, PRs, branch switches, worktrees, rebases, resets, stashes,
dependency or lockfile changes (`uv sync`, `uv lock`), deployment, publishing, and any
other network request (slow.pics, webhooks, TMDB, GitHub API, DVB downloads). If
`zensical` is missing from the environment, stop and ask me before any sync.

## Child override (put this directly after the preset instructions)

> This unit follows `docs/plans/2026-10-12-documentation-site-redesign.md`, which is
> stricter than the preset text above. Do not resolve uncertainty yourself: any
> ambiguity, fact you cannot verify, failed check, missing input, or decision the plan
> does not make is a stop. Report `blocked` to the orchestrator with the exact question
> and evidence, and change nothing further. Prose follows the plan's style guide and the
> voice-pass procedure in its page specifications; keep every guard string. Never
> commit, and run no Git command that changes the index, history, or branch. Edit only
> the files the plan assigns to your unit. U2 only: an environmental failure may be
> diagnosed and the same command rerun, exactly as the plan's U2 entry allows.

Each child packet contains: the unit's section from the plan ("Units"), the plan
sections "Approved decisions" and "Every unit", the paths of its specification assets,
its owned files, its acceptance checks and stop conditions, this checkout's path and
branch, the base commit, the orchestrator thread ID, and the callback rule. The child's
terminal report lists: changed files, checks run with results, guard strings verified,
anything `blocked`, and limits.

## Procedure

1. **Baseline.** Record `HEAD` and `git status --porcelain`. If `HEAD` is not the plan's
   base, run `git diff --stat <base>..HEAD` and stop if it touches any file the plan
   edits, moves, or deletes; otherwise record the difference and continue. Expected besides the plan,
   its assets folder, and this prompt: tracked modifications to
   `docs/plans/2026-10-08-documentation-refresh-assets/capture-spec.md` and
   `docs/plans/2026-10-08-documentation-refresh-assets/pages-reference.md`, and other
   untracked files under `docs/prompts/`. Those belong to other work: never stage,
   revert, or edit them. Any other tracked modification, or any untracked file outside
   `docs/plans/` and `docs/prompts/`, is a stop. Commit only
   `docs/plans/2026-10-12-documentation-site-redesign.md`,
   `docs/plans/2026-10-12-documentation-site-redesign-assets/`, and this prompt as
   `docs(plan): add the documentation site redesign plan`.
2. **Scripts.** Write the four scripts from the plan's scripts asset to
   `.tmp/docs-site-redesign/` exactly as given before dispatching U3 or U7.
3. **Wave A1.** Dispatch U1 and U3 in parallel. Record a dispatch map (unit, real thread
   ID, actual model and effort, owned files) in an "Execution record" section appended
   to the plan. When nothing useful remains, end your turn and let callbacks resume you;
   do not poll.
4. **Wave A2.** After U3 is accepted and committed, dispatch U4.
5. **Per unit.** On each callback: check the actual diff stays inside the unit's owned
   files and matches its specification (for U1, extract the theme specification's code
   blocks and diff each against its file; for U4, diff each page against its block);
   rerun the unit's acceptance checks yourself; send fixes back to the same child; on
   `blocked`, resolve only if the plan already answers it, otherwise pause that unit and
   bring me the question. Then commit the unit with a Conventional Commit subject naming
   it (`docs(theme): add the redesigned site theme (U1)`).
6. **Wave A gates, once, serially, after U1, U3, and U4 are committed:** the plan's
   "Orchestrator, once per wave" checks 1 to 5. Check 3 is expected to report
   only U2's home images and diagram at this point, so run it and record that result.
7. **Wave A review.** Send the wave's commit range, the plan, and its assets to one
   `reviewer` chat. Its report must include:
   - plan fidelity, with a deviations register (a deviation stays only when it is
     strictly better, with evidence; otherwise it is reverted);
   - correctness of the moves, redirects, relinking, and key-block conversion (every
     configuration key and run option present exactly once, with the right anchor);
   - completeness of the API generator removal (no remaining reference);
   - guard-test and workflow-test changes limited to what the plan specifies;
   - over-engineering in any added file.
   Adjudicate every finding with evidence before acting; send accepted fixes to the
   owning child; commit fixes per unit; rerun the gates they affect.
8. **Wave B.** Dispatch U2, U5, U6, U7, and U8 in parallel. Process each callback as in
   step 5. Before committing U5's deletion of the two terminal SVGs, confirm
   `rg -n "terminal-dry-run|terminal-run-complete" docs README.md --glob '!docs/plans/**' --glob '!docs/prompts/**' --glob '!docs/reviews/**'`
   returns only `docs/images/README.md` lines that U2 removes.
9. **Wave B gates and visual QA.** Run every orchestrator check in the plan's
   Verification section. Then do the rendered visual QA checklist at 1440 × 900 and
   390 × 844, light and dark (clear site storage between schemes). Save one screenshot
   per checklist row and viewport under `.tmp/docs-site-redesign-qa/wave-b/` and note pass
   or fail for each. A failure goes back to the owning child; rerun affected gates after
   the fix.
10. **Wave B review.** Send the wave's commit range, the plan, its assets, and the QA
    screenshot folder to a fresh `reviewer` chat. Its report must include:
    - plan fidelity with a deviations register, as in step 7;
    - **fact preservation**: for every voice-passed page, compare the base and new text
      and list any fact, number, literal, link target, or guard string that was lost,
      changed, or added without a source;
    - **voice**: every instance of a pattern from the style guide's "not allowed" table,
      quoted with `file:line`, plus paragraphs over 70 words and headings that are not
      task or topic names;
    - factual accuracy of every changed statement against the code and authority
      documents, with `file:line` evidence;
    - rendered visual QA, reviewing the saved screenshots against the theme
      specification and the plan's checklist.
    Adjudicate, fix through the owning child, recommit, and rerun affected gates.
11. **Wave C.** Dispatch U9. Process its callback as in step 5, run the full
    orchestrator check list once more (including `tests/workflows/test_docs_style.py`),
    and send U9's commit to a `reviewer` chat for plan fidelity and test strategy (the
    test must check behavior that matters, without coupling to page structure).
12. **Close.** Append the execution record (commits, units with preset and actual
    model and effort, gate results with every skip reason, review adjudications, and
    kept deviations) to the plan. Leave the plan `Status: Active` until I accept the
    rendered site; say so in the record. Commit as
    `docs(plan): record the documentation site redesign outcome`.

## Final report, then stop

- commits (SHA and subject);
- each unit's preset and actual model and effort;
- gate results with skip reasons, and the QA checklist outcome with the screenshot
  folder path;
- review adjudications and kept deviations;
- anything still `blocked` or open.
