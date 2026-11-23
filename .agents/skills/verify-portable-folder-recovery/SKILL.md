---
name: verify-portable-folder-recovery
description: Check Windows portable migration rollback and retry guidance when activation, folder moves, or pending marker handling changes.
---

# Verify portable folder recovery

A failed install can clear its migration marker only when each planned source
folder is populated and its candidate folder is absent or empty. Clearing it too
early lets the next install proceed while user data still needs recovery.

From the repo root on Windows with PowerShell 7 and the locked dev environment, run

```powershell
uv run --no-sync pytest -q -rs tests/windows_portable/test_windows_source_preservation.py -k "rollback_folder_model or pipeline_stop_after_first_rename or refusal_reports_interrupted_migration_state"
```

The Windows portable CI job runs these cases in its serial pytest step. Check for
an executed pass for each case. The Windows fixture skips on other platforms.

## Read a failure

The [folder model](../../../tests/windows_portable/test_windows_source_preservation.py)
enumerates all nine pairs of absent, empty and populated directories for one
planned folder at rollback. Starting with a populated source and empty target,
the installer removes the placeholder and atomically renames the source. Those
three layouts permit automatic reconciliation. For every other pair the model
requires retaining the marker and both observed payloads. Two sibling folders
exercise reversal and placeholder restoration in the same install. The checks
read real files and the pointer after a failure at the registration boundary.

The first-rename case interrupts immediately after a real rename. The retry cases
terminate the installer process at selected points, rerun installation, and check
which manual actions it recommends. The model assumes stable observations during
rollback and successful same-volume renames. Folder occupancy establishes location
under that assumption. A concurrent writer can replace a populated folder's contents
without changing its occupancy. File locks, reparse points, sharing
violations, and external changes between an observation and a rename use the
separate platform tests in the same module.

## Confirm correspondence

Last checked against `cb473653601bc7a1c0ce1aec105e6eb150ee0134`.
Inspect `Get-PortableUserFolderState`, `Get-PortableMigrationLocation`,
`Invoke-PortableActivation` and `Write-PendingMigrationRefusal` in the
[activation script](../../../tools/windows_portable/portable_activation.ps1)
when the folder domain, rename sequence or marker lifetime changes. Establish
whether a new counterexample violates the recovery contract or exposes a new
legitimate transition. Update the model and sync commit after reconciling the
implementation with that contract.

To replay the historical failure, in a disposable worktree of this revision use
`git restore --source=7d39e5fb -- tools/windows_portable/portable_activation.ps1`
and run the folder model. In the absent-source, empty-target case the old
transaction moved an empty directory back and discarded the marker. Restore the
worktree's activation script from its HEAD and rerun the same command.
