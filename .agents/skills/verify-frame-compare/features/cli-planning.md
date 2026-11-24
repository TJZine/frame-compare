# Plan a comparison and consume JSON failures

## Sub-features

- Produce a dry-run plan without starting native execution, metadata lookup,
  publishing or browser launch.
- Return typed, machine-readable errors for invalid input/configuration.
- Keep successful planning deterministic for the selected config/source fields.

Authority: [dry-run planning](../../../../docs/current-cli-contract.md#dry-run-planning)
and [JSON/quiet compatibility](../../../../docs/current-cli-contract.md#json-and-quiet-mode-compatibility).
Owners: `src/frame_compare/cli/run_command.py`, `cli/dry_run.py`.

## How to get to it (user POV)

The installed command is `frame-compare`. For a root containing `config/config.toml`
and `comparison_videos/`, run:

```sh
frame-compare run --root <owned-root> --json --dry-run --skip-metadata --no-upload
```

The placeholder denotes a disposable root. The driver below creates it and its
configuration automatically, with metadata lookup, publishing and report auto-open
disabled. No login, real media or native plugins are needed.

## Driving it with the installed-console harness

After the parent skill's Launch, use this read-only doctor and inspect the chosen
console path. It must belong to the intended contributor environment; the resolver
can otherwise fall back to PATH:

```sh
uv run --no-sync python -c "import pytest,sys; from tests.e2e.harness import resolve_entry_point; print(sys.executable); print(resolve_entry_point())" > "$verifyRun/evidence/cli-doctor.log" 2>&1
```

Then run the existing selection (one command, valid in POSIX shells/PowerShell):

```sh
uv run --no-sync pytest -q tests/e2e/test_cli_dry_run.py tests/e2e/test_cli_errors.py::test_cli_errors_are_typed_and_json_only tests/cli/test_run_dry_run.py::test_run_dry_run_does_not_import_or_call_runtime_side_effect_owners --basetemp "$verifyRun/scratch/cli" --junitxml "$verifyRun/evidence/cli-results.xml" > "$verifyRun/evidence/cli-run.log" 2>&1
```

Record its exit status before another command. Inspect the retained scenario
artifacts under `evidence/cli`, `cli-run.log` and JUnit. The success scenario must
exit zero, expose exactly the eight allowlisted top-level plan keys, resolve the
two source names in deterministic order, and leave its workspace path listing
unchanged. The typed failures require their documented exit/error codes, parseable
JSON stdout and empty stderr. Read `tests/e2e/test_cli_errors.py` for each selected
case rather than inferring all failure behavior from one example.

The fresh-process focused test separately blocks runtime imports and side-effect
owners, including network/browser/subprocess owners, and compares file contents
as well as paths. That supporting contract check supplies stronger side-effect
evidence than the installed-console scenario alone. Keep the claims separate.

## Gotchas

- The harness intentionally creates empty `.mkv` files. Passing proves planning,
  not decoding, audio alignment, a fresh wheel install or Windows portable launch.
- `FRAME_COMPARE_E2E_ARTIFACTS` must point outside pytest basetemp. Each scenario
  replaces its matching artifact directory; use a new run directory, preserve
  failure output and inspect the evidence again after cleanup.
- The deterministic assertion covers selected fields, not full stdout byte
  equality over repeated runs. The selection is not every CLI edge case or a
  substitute for the runbook's applicable
  [full verification](../../../../docs/ENGINEERING_RUNBOOK.md#full-verification).
- A missing console or dependency blocks this route. Do not replace it with a
  direct internal function call and claim installed-CLI acceptance.
- These instructions include PowerShell syntax compatibility, but no execution
  on Windows is claimed. Record the actual OS and console tested.
