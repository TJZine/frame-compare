---
name: verify-frame-compare
description: Drive Frame Compare's installed CLI, offline report viewer, and alignment-review journeys using existing harnesses and runtime runbooks. Use for application verification or maintaining its feature coverage; distinguish component checks from native and Windows acceptance.
---

# Verify Frame Compare

Use this application guide alongside the shared `verify-code` skill when choosing
proof for a change. Read [features/README.md](features/README.md), then only the
feature files needed for the task. A targeted verification request does not require
the entire map; a maintenance pass must account for every mapped feature and its
unreached paths. This is a seed map, not an exhaustive product or release gate.

The [repository profile](../../project.md) owns setup and contract routes. The
[engineering runbook](../../../docs/ENGINEERING_RUNBOOK.md#verification-policy)
owns specialist runtime, distribution and release procedures; follow its applicable
gates rather than substituting this map. Product expectations come from the
[CLI contract](../../../docs/current-cli-contract.md) and
[architecture](../../../docs/current-architecture.md), not old test results.

## Launch

Run from the repository root. Use its existing locked contributor environment;
bootstrap only if necessary with the profile's `uv sync --group dev --extra vsview
--frozen`. Do not replace an environment or install native plugins merely to make
an unrelated feature reachable.

There is no shared application server. The CLI harness starts a fresh installed
console for each scenario; the browser harness generates a report and owns isolated
headless Chrome sessions; Qt component tests own offscreen widgets. A genuine
native review is a separate media run and VSView child, described in its feature
file. Never attach these tests to the user's browser profile or existing review.

Create one unique run directory outside the checkout. Keep `evidence/` separate
from `scratch/`, which pytest may replace. For POSIX shells:

```sh
verifyRun=$(uv run --no-sync python -c 'import tempfile; print(tempfile.mkdtemp(prefix="frame-compare-verify-"))')
export FC_VERIFY_RUN="$verifyRun"
export FRAME_COMPARE_E2E_ARTIFACTS="$verifyRun/evidence/cli"
mkdir -p "$verifyRun/evidence" "$verifyRun/scratch"
```

For PowerShell:

```powershell
$verifyRun = uv run --no-sync python -c "import tempfile; print(tempfile.mkdtemp(prefix='frame-compare-verify-'))"
$env:FC_VERIFY_RUN = $verifyRun
$env:FRAME_COMPARE_E2E_ARTIFACTS = "$verifyRun/evidence/cli"
New-Item -ItemType Directory -Force "$verifyRun/evidence", "$verifyRun/scratch" | Out-Null
```

Both shells can run these source receipts from the repository root:

```sh
git rev-parse HEAD > "$verifyRun/evidence/source.txt"
git status --short > "$verifyRun/evidence/worktree-status.txt"
git diff HEAD --binary > "$verifyRun/evidence/worktree.diff"
uv run --no-sync python -c "import platform,sys; print(platform.platform()); print(sys.version)" > "$verifyRun/evidence/environment.txt"
```

Preserve relevant untracked inputs separately after checking for sensitive data;
status records their names, not bytes. Record the exact drive commands and relevant
package/browser versions. An initial ready state means the selected feature's
doctor succeeds, not that every optional native capability is installed.

## Doctor

Run the selected feature's read-only check before its first drive, on each fresh
runtime session, and after a surprising failure. The test harnesses create fresh
owned sessions; inspect their startup failures and skips. Do not keep driving a
wedged UI merely because its process exists: inspect, reset or relaunch the owned
session. Keep doctor output with the evidence. Stop that route if its required
doctor fails; record the gap instead of continuing with a different proof level.

| Feature | Required capability | Not required for that route |
| --- | --- | --- |
| [CLI plan and errors](features/cli-planning.md) | pytest and the intended installed console | media plugins, browser, credentials |
| [Offline report](features/offline-report.md) | discoverable Chrome/Chromium; locked Node wheel for trusted input | media decoding, publishing |
| [Alignment review](features/alignment-review.md) | PySide6/VSView for component tests; native decoder and desktop for real review | component success does not supply native capability |

The full `frame-compare doctor --json` belongs to the native/runtime route; a
missing optional decoder must not block runtime-free CLI planning. A skip is a
capability gap, never a pass. Recheck source if a doctor command itself has drifted.

## Drive

Follow the chosen feature file: it gives the actual user entrypoint, existing
driver, observable result and claim boundary. Run these recipes against disposable
inputs. Existing tests are drivers where they actually reach the public surface:
installed subprocess CLI and generated report in real Chrome qualify for their
stated journeys; synthetic viewer metadata and mocked native launch qualify only
as component/workflow evidence.

Keep one runtime owner. Source investigation can run independently, but do not
drive one browser/native session concurrently. Never overlap full Docker verifier
runs in one checkout: their generated-media cache and pruning are shared.

## Evidence

Each command uses the named `evidence/` directory for JUnit and console logs.
Record its exit code immediately: POSIX `$?`, PowerShell `$LASTEXITCODE`. Inspect
the log and JUnit failures, errors and skips; do not equate test totals with user
journey counts. Save an invocation record alongside them, including any overrides.

For CLI drives, inspect the harness's retained scenario commands, stdout, stderr
and summaries. For browser/native work, retain useful generated HTML/images,
sidecars or screenshots from `scratch/` before cleanup. The tests do not
automatically archive screenshots, DOM dumps or a full native session. Evidence
must show the action and resulting state, including relevant file/authority side
effects. A final screen alone cannot establish the preceding path.

Report separately: observed behavior, component/static evidence, unmet
prerequisites, and unexecuted paths. If the installed behavior contradicts the
product contract, investigate a possible product gap; do not weaken expectations
or edit the product under a verification-only request. Missing driving capability
is a harness gap; an inaccurate command or map is documentation drift.

## Cleanup

Let the existing harnesses reap their children and release their owned temporary
profiles. After a failed drive, inspect its bounded-process cleanup before retrying;
terminate only a child whose identity and ownership this run established. Never
kill by application name or remove shared caches/user profiles.

Copy evidence out of `scratch/`, then remove only this run's scratch tree. This
command works in either shell and refuses a missing run marker:

```sh
uv run --no-sync python -c "import os,shutil; from pathlib import Path; p=Path(os.environ['FC_VERIFY_RUN']); assert p.name.startswith('frame-compare-verify-') and (p/'evidence'/'source.txt').is_file(); shutil.rmtree(p/'scratch') if (p/'scratch').exists() else None; print('Evidence retained at', p/'evidence'); print(*sorted(str(f.relative_to(p)) for f in (p/'evidence').rglob('*') if f.is_file()), sep='\n')"
```

Confirm the selected feature's JUnit/log and useful artifacts still exist and are
readable after cleanup. Archive the evidence to a durable task location before
discarding the temporary run directory. Restore any environment overrides changed
for this run, especially `QT_QPA_PLATFORM`, `FRAME_COMPARE_E2E_ARTIFACTS` and
`REPORT_BROWSER`. Native indexes and persisted overrides can exist outside a run's
generated folder; keep them inside the disposable media root from the outset.

Use the shared `maintain-verification-skill` when explicitly asked to refresh this
map. Preserve the native, transfer and Windows gaps until the corresponding real
route has been observed. No automatic maintenance cadence is implied.

Structure and upkeep adapted from Lauren Tan / poteto's MIT-licensed pstack
verification skills at `99743e9c151c8537cbbf1f98bb38f34ef3368453`;
see [LICENSE](LICENSE). Application procedures reuse this repository's existing
runbooks and test harnesses.
