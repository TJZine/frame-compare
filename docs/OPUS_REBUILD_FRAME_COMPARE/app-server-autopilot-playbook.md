# FC2 Codex App-Server Autopilot Playbook

This document is a **0-decision-point** implementation plan and reusable playbook for migrating an existing
\"multi-role automation controller\" (Planning -> Plan Review -> Coding -> Verification/Review) from `codex exec`
(fresh processes, no persistent role context) to **`codex app-server`** (persistent threads per role, streamed events).

Primary objectives:
1. Preserve FC2 STOP rules and artifact contracts.
2. Keep **role context persistent** across iterations (Planning <-> Plan Review loops).
3. Make automation status observable via streamed app-server events.
4. Keep rollback easy: the existing `codex exec` automation remains available until app-server is proven stable.

---

## Hard Requirements (No Decisions During Implementation)

1. Artifact SSOT remains unchanged:
`plan-vN.md`, `plan-review-vN.md`, `impl-vN.md`, `verify-vN.md`, `review-vN.md` under `.agent-workflow/runs/<RUN_ID>/`.
2. STOP gates remain controller-owned:
the controller runs validators and quality gates and routes back to the correct role on failure.
3. Verification/Review never edits code:
if any gate fails after coding, the controller routes back to Coding.
4. Role model policy is enforced **per turn** (no reliance on ambient defaults).
5. Thread persistence is deterministic:
each RUN_ID has a stable `threadId` per role stored under that RUN_ID directory.
6. Rollback is always available:
the existing `codex exec` path stays intact.

---

## Role Model Policy (Pinned)

The controller MUST set these values explicitly in every `turn/start` request.

1. Planning: `model="gpt-5.2"`, `effort="high"`
2. Plan Review: `model="gpt-5.2"`, `effort="high"`
3. Coding: `model="gpt-5.2-codex"`, `effort="medium"`
4. Verify+Review: `model="gpt-5.2-codex"`, `effort="high"`

Rationale:
`codex app-server` threads carry defaults forward across turns, so per-turn overrides prevent drift.

---

## App-Server Protocol Constraints (Implementation Rules)

1. The server rejects any request before initialization:
send `initialize`, then send the `initialized` notification, then proceed.
Repeated `initialize` calls return an error (the controller must treat that as a bug and STOP).
2. All communication is JSONL over stdio using JSON-RPC 2.0 semantics, but without the `"jsonrpc":"2.0"` field.
3. The controller MUST read stdout continuously to avoid deadlocks and to surface streamed progress.
4. The controller MUST treat `turn/completed` as the only authoritative end-of-turn signal.
5. The controller MUST handle:
`thread/started`, `turn/started`, `item/*`, `turn/diff/updated`, `turn/completed`.
6. The controller MUST handle server-initiated approval flow:
when the server requests approval for a command or file change, the client must respond (accept/decline) or the run will stall.
The safest initial implementation is interactive prompting (print the requested action + ask for Y/N) and a default of decline on EOF/timeout.
7. The controller MUST restate hard constraints on every turn:
do not rely on thread memory to preserve allowed/disallowed writes. Every `turn/start` input must include the same "Allowed Writes" and "Disallowed Writes" lists the FC2 role prompt would include in `codex exec`.
8. The controller MUST include prior failure context when looping:
when routing back to Planning/Coding due to a validator/gate failure, append a section to the next role prompt:
`## Previous Gate Failure (Autopilot)` followed by the exact stdout/stderr captured by the controller.

### Minimal JSONL Examples (Copy/Paste Shapes)

Initialization handshake:

```json
{ "method": "initialize", "id": 0, "params": { "clientInfo": { "name": "fc2_autopilot", "title": "FC2 Autopilot", "version": "1.0.0" } } }
{ "method": "initialized", "params": {} }
```

Start a role thread:

```json
{ "method": "thread/start", "id": 10, "params": { "cwd": "/path/to/repo", "model": "gpt-5.2-codex" } }
```

Resume a role thread:

```json
{ "method": "thread/resume", "id": 11, "params": { "threadId": "thr_123" } }
```

Start a turn with explicit per-turn model policy:

```json
{ "method": "turn/start", "id": 30, "params": {
  "threadId": "thr_123",
  "input": [ { "type": "text", "text": "Write plan-v1.md at ... (strict allowed writes...)" } ],
  "cwd": "/path/to/repo",
  "model": "gpt-5.2",
  "effort": "high",
  "summary": "concise"
} }
```

Fetch effective config (for asserting sandbox/approvals without guessing):

```json
{ "method": "config/read", "id": 90 }
```

List available models and effort options (for preflight validation):

```json
{ "method": "model/list", "id": 91 }
```

### Required State File Shapes

Thread mapping file (`.agent-workflow/runs/<RUN_ID>/appserver_threads.json`):

```json
{
  "planning": "thr_planning_123",
  "plan_review": "thr_plan_review_456",
  "coding": "thr_coding_789",
  "verify_review": "thr_verify_review_012"
}
```

Resolved app-server config (`.agent-workflow/runs/<RUN_ID>/appserver-config.json`):

```json
{
  "approval_policy": "on-request",
  "sandbox_mode": "workspace-write",
  "model": "gpt-5.2-codex",
  "model_reasoning_effort": "medium"
}
```

Event log (`.agent-workflow/runs/<RUN_ID>/appserver-events.jsonl`):

```jsonl
{"ts":"2026-02-02T12:00:00Z","direction":"in","payload":{"method":"turn/started","params":{"turn":{"id":"turn_123","status":"inProgress"}}}}
{"ts":"2026-02-02T12:00:01Z","direction":"in","payload":{"method":"turn/diff/updated","params":{"threadId":"thr_123","turnId":"turn_123","diff":"..."}}}
{"ts":"2026-02-02T12:00:10Z","direction":"in","payload":{"method":"turn/completed","params":{"turn":{"id":"turn_123","status":"completed"}}}}
```

---

## Controller Flow (Deterministic)

The app-server engine MUST follow this flow for every role turn.

1. Ensure app-server process is started.
2. If not initialized:
send `initialize`, wait for the response, then send the `initialized` notification.
3. Ensure role thread exists:
load `.agent-workflow/runs/<RUN_ID>/appserver_threads.json`.
If missing, create all role threads with `thread/start` and write the mapping.
If present, resume the role thread with `thread/resume`.
4. Start the turn:
send `turn/start` with:
`threadId`, `cwd`, pinned `{model, effort}` for that role, and a role prompt that includes:
the exact RUN_ID, the exact artifact version (`plan-vN`, `plan-review-vN`, etc.), and absolute output paths.
The controller computes `vN` deterministically and the agent must never guess "latest".
Every role turn prompt MUST start with:
`Treat this prompt as complete and authoritative. Do not rely on any prior thread/session context.`
5. Stream and log:
append all inbound events to `appserver-events.jsonl`.
6. Wait for completion:
return only after receiving `turn/completed` for the active turn id.
7. Enforce hard STOPs:
if `turn.status` from `turn/completed` is not `completed`, STOP immediately with the server error payload.

The controller MUST NOT attempt to infer completion from partial `turn/diff/updated` output.

### Approval Handling (Deterministic)

If the app-server asks for approval, the controller MUST:
1. Print a single-line banner indicating an approval is required (include role + RUN_ID).
2. Print the command/file-change summary provided by the server.
3. Prompt the operator with a strict input:
`APPROVE (y/N):`
4. If the operator types `y`, respond with approval.
5. Any other input, EOF, or timeout is treated as decline.
6. After decline, STOP and exit non-zero (so the operator can rerun with different config/policies if desired).

Implementation note:
approval requests may arrive as:
1. Notifications in the `item/*` stream describing what needs approval (for display).
2. Server-initiated JSON-RPC requests (messages with `id` + `method`) that require a response (for unblocking the run).
The client must handle both.

When responding to a server-initiated approval request, the controller MUST send a JSON-RPC response:
`{ "id": <same id>, "result": { "decision": "accept" } }` or `{ "id": <same id>, "result": { "decision": "decline" } }`.

## Implementation Plan (0 Decision Points)

### Step 0: Pre-Flight (Repo Setup)

1. Confirm Codex is installed and usable from the repo:
run `codex --version`.
2. Generate a schema bundle pinned to the local Codex version (local-only; do not commit):
run `codex app-server generate-json-schema --out .codex/schemas/app-server/<CODEX_VERSION>/`.
Ensure `.gitignore` contains `.codex/schemas/`.
3. (Optional but recommended) Add a short README note locally in the schema directory:
the schema must be regenerated whenever Codex is upgraded.
4. Add an app-server preflight check to the controller:
call `model/list` and assert the required models exist.
Call `config/read` and STOP if the resolved config does not match the expected baseline:
`sandbox_mode="workspace-write"` and `approval_policy="on-request"`.
Record the full resolved config to `.agent-workflow/runs/<RUN_ID>/appserver-config.json`.
If the resolved config does not reflect the repo's `.codex/` settings, STOP and fix project trust/config layering before continuing.

Acceptance criteria:
the schema directory exists locally, is ignored by git, and the recorded Codex version matches the schema folder name.

### Step 1: Add an App-Server Client Library (Python, stdio JSONL)

Create a small, testable client under `scripts/` (not `src/`) so this stays automation-only:

1. Add file: `scripts/fc2_codex_appserver_client.py`
2. Implement class: `CodexAppServerProcess`
3. Implement methods:
`start()`, `stop()`, `initialize()`, `request(method, params)`, `notify(method, params)`.
4. Implement a background reader thread:
it parses JSON lines from stdout and routes them to:
`responses_by_id` for request/response pairs, and `notifications` queue for server-initiated events.
5. Implement helper: `wait_for_turn_completed(thread_id, turn_id, timeout_s)`
6. Implement helper: `collect_turn_transcript(thread_id, turn_id)`
this produces a minimal structured record:
turn id, final status, error payload (if any), and selected item outputs (agent text deltas optional).
7. Implement deterministic capture for debugging:
write every JSON line read from server stdout to `.agent-workflow/runs/<RUN_ID>/appserver-events.jsonl`
when a RUN_ID is active.
8. Implement request-id generation:
use a single monotonically increasing integer counter for JSON-RPC request `id` values, and never reuse an id within a process.
9. Implement server-initiated request handling:
if a message arrives with both `id` and `method` (and no `result`/`error`), treat it as a server request and respond.

Acceptance criteria:
the client can:
initialize, start a thread, start a turn, stream events, and return on `turn/completed`.

### Step 2: Persist Thread IDs Per RUN_ID

Add deterministic state file per run:

1. New file per RUN_ID:
`.agent-workflow/runs/<RUN_ID>/appserver_threads.json`
2. Required keys:
`planning`, `plan_review`, `coding`, `verify_review`.
3. Storage rules:
if the file exists, resume each thread with `thread/resume`.
if missing, create each with `thread/start` and write the mapping immediately.
4. Never share threads across different RUN_IDs.
5. Add a controller lock:
create `.agent-workflow/.autopilot.lock` and hold it for the duration of the process.
If the lock cannot be acquired, STOP immediately (prevents two controllers from racing the same worktree).

Acceptance criteria:
after one successful start, rerunning the controller resumes threads and maintains role context.

### Step 3: Introduce an Engine Abstraction (Keep Exec Rollback)

Refactor (or wrap) the controller to support both engines without duplicating workflow logic.

1. Add file: `scripts/fc2_autopilot_engine.py`
2. Define protocol:
`run_turn(role, message, model, effort) -> TurnResult`
`close()`
3. Add engine implementation A:
`ExecEngine` calling `codex exec --profile ...` (existing behavior).
4. Add engine implementation B:
`AppServerEngine` using `CodexAppServerProcess` plus per-role threads.

Acceptance criteria:
`scripts/fc2_autopilot.py` can run with `--engine exec` and remains behavior-identical to current automation.

### Step 4: Implement `--engine app-server` in the FC2 Autopilot

Update `scripts/fc2_autopilot.py`:

1. Add flag: `--engine` with allowed values `exec` and `app-server`.
2. Default remains `exec` until app-server passes an end-to-end run.
3. When `--engine app-server`:
start one `codex app-server` subprocess at process start.
4. Implement phase banners driven by streamed events:
print the active role, RUN_ID, turn id, and final status from `turn/completed`.
5. Preserve existing STOP behavior:
if a plan validator fails, the controller routes back to Planning with the gate failure text included.
6. Preserve existing "confirm run id" behavior:
before any non-dry-run work starts, the operator must type `CONFIRM RUN_ID: <RUN_ID>` exactly unless `--yes`.
7. Avoid ambiguous policy mapping:
do not attempt to translate `.codex/config.toml` approval/sandbox values into app-server `approvalPolicy` or `sandboxPolicy` values.
Instead, rely on `config/read` for visibility and only override `model`, `effort`, `cwd`, and `summary` per turn.
8. Do not run gates inside Codex:
continue to run validators and quality gates as local subprocess calls from the controller, and pass failures back into the next Coding/Planning turn as text.

Acceptance criteria:
`python3 scripts/fc2_autopilot.py --engine app-server --dry-run` prints the same run selection and steps as today.

### Step 5: Deterministic Failure Handling

Implement the following STOP and routing policy with no exceptions:

1. If `initialize` fails: STOP with a single error line and exit non-zero.
2. If any `thread/resume` fails: STOP and print the missing thread id + RUN_ID.
3. If `turn.status` from `turn/completed` is `failed`: STOP and print the server error payload.
4. If run-artifact validation fails: route back to the role that wrote the artifact.
5. If spec-anchor validation fails: route back to Planning (plan must be fixed).
6. If quality gates fail after coding: route back to Coding and include the formatted gate failure.
7. If quality gates fail after verification/review: STOP and route back to Coding in the NEXT prompt.

Acceptance criteria:
all STOPs are deterministic, and there is no Python traceback for expected gate failures.

## Known Risks and Mitigations (No Decisions)

1. Risk: thread resumption fails after a Codex upgrade or state reset.
Mitigation: STOP with a clear message, then rerun using `--engine exec` for that RUN_ID.
2. Risk: the controller deadlocks by not draining server stdout.
Mitigation: always run a dedicated reader thread and enforce timeouts on `wait_for_turn_completed`.
3. Risk: model/effort drift across turns because turn overrides become thread defaults.
Mitigation: set `model` and `effort` on every `turn/start` unconditionally.
4. Risk: the server emits large diffs causing slow rendering or memory growth.
Mitigation: store raw events to `appserver-events.jsonl`, and print only summarized progress to console.
5. Risk: the controller misses a server `error` notification and waits forever.
Mitigation: treat any `error` notification as a STOP and unblock any waiting turn (fail fast).
6. Risk: two controller processes race and corrupt the worktree or artifacts.
Mitigation: enforce `.agent-workflow/.autopilot.lock`.

### Step 6: Verification Checklist (Must Pass Before Default Flip)

Run all commands (from repo root):

1. Style and type checks for new scripts:
`.venv/bin/ruff check scripts/fc2_codex_appserver_client.py scripts/fc2_autopilot_engine.py`
`.venv/bin/pyright --warnings scripts/fc2_codex_appserver_client.py scripts/fc2_autopilot_engine.py`
2. Existing repo gates:
`.venv/bin/pyright --warnings`
`.venv/bin/ruff check .`
`.venv/bin/pytest -q`
`UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini`
`UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check`
`UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check`
3. App-server smoke test (new):
run the controller on a trivial "documentation-only" RUN_ID and confirm:
threads are created, a turn completes, and the process shuts down cleanly.
4. FC2 end-to-end (new):
run one real checklist slice through APPROVED using `--engine app-server`.

Acceptance criteria:
all commands pass and at least one real run completes with APPROVED using app-server.

### Step 7: Flip Default (Only After Proven Stable)

After app-server completes at least one full run:

1. Change default engine in `scripts/fc2_autopilot.py` to `app-server`.
2. Keep `--engine exec` available indefinitely as a recovery mode.

Acceptance criteria:
default execution uses app-server and exec fallback remains functional.

---

## New Repo Setup Template (Reusable)

Use this template when adding a similar automation system to a new repository.

### A. Add Team Config

1. Create `.codex/config.toml`:
set baseline `model`, `model_reasoning_effort`, `approval_policy`, `sandbox_mode`.
2. Add `.codex/skills/`:
either symlink shared skills or copy a repo-specific set.
3. Optional: add `.codex/requirements.toml`:
use this to enforce allowed sandbox and approval policies.

### B. Add Workflow Artifact Rules

1. Decide the artifact directory and naming convention.
2. Add validators that enforce:
file presence, allowed writes per role, and any SSOT anchor policy.
3. Make the controller run validators between roles, not the agent.

### C. Add App-Server Automation

1. Implement a small stdio JSONL client.
2. Persist one thread id per role per RUN_ID.
3. Enforce per-turn `model` and `effort` explicitly.
4. Stream server events to display active role/turn and progress.
5. Keep a rollback engine that does not require app-server.

### D. Acceptance Criteria (Minimal)

1. Smoke test: initialize -> thread/start -> turn/start -> turn/completed.
2. Real run: one full workflow completes with artifacts and gates passing.
3. Resume test: rerun controller and confirm role context is preserved.

---

## Implementation Session Prompt Template (Copy/Paste)

Use this when starting a fresh session to implement the migration in this repo.

```text
You are the Coding Agent. Your task is to migrate FC2 automation from `codex exec` to `codex app-server`
while preserving all FC2 STOP rules and artifact contracts.

Read: docs/OPUS_REBUILD_FRAME_COMPARE/app-server-autopilot-playbook.md

Hard requirements:
1. Implement `--engine app-server` without breaking `--engine exec` rollback.
2. Persist one app-server thread per role per RUN_ID at `.agent-workflow/runs/<RUN_ID>/appserver_threads.json`.
3. Enforce per-turn model policy exactly as specified in the playbook.
4. Stream and label role progress using app-server event notifications.
5. Stop deterministically on failures; no tracebacks for expected STOP gates.

Do not change the FC2 artifact formats. Run all repo gates before finishing.
```
