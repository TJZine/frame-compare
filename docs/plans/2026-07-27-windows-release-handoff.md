---
search:
  exclude: true
---

Status: Supporting handoff; not a second active plan
Authority: [Initial Release Production Remediation Plan](2026-07-25-initial-release-remediation.md)
Owner: Maintainer and Windows release implementer

# Windows Initial-Release Handoff

## Purpose

Use this handoff on a trusted Windows 10/11 x64 machine to finish the
Windows-specific portions of the initial public-release remediation. The active
remediation plan remains authoritative. This document narrows its P1, P2, P3, P6,
and P7 requirements into a safe execution order with explicit proof and stop
conditions.

This handoff does not authorize publishing `v0.1.0`. It prepares and proves the
Windows release path so the maintainer can later make a separate go/no-go decision.

## Paste-ready Windows Codex prompt

Paste the following into a new Codex task opened from the Windows clone:

```text
Work on Frame Compare's initial Windows release readiness from the checked-out
stage1 branch. Read AGENTS.md, docs/ENGINEERING_RUNBOOK.md,
docs/plans/2026-07-25-initial-release-remediation.md, and
docs/plans/2026-07-27-windows-release-handoff.md completely before changing files.

Execute only the Windows implementation and verification packages authorized by
the handoff. Preserve public CLI/config behavior unless the handoff explicitly
requires a change. Make separate Conventional Commits for key-generation tooling,
the public release key, bundle license/source inventory fixes, and test/documentation
changes when those scopes are present.

Security boundary: you may implement and test signing code with disposable test
keys under pytest temporary directories. You must never generate, read, print,
copy, upload, inspect, or commit the real private release key. Stop and ask me to
perform every step labeled MAINTAINER-ONLY in a separate non-Codex PowerShell
window. The real private key must remain outside the repository, task transcript,
command output, CI logs, caches, and release artifacts.

Begin with the handoff preflight. Report the checked-out commit, worktree status,
available PowerShell executables, and which Windows tests run rather than skip.
Implement and verify one package at a time. Stop on any handoff stop condition.
Do not create or publish the official v0.1.0 tag or merge a release PR.
```

## Baseline and current state

At handoff authoring time on July 27, 2026:

- branch: `stage1`
- commit: `5352c4be`
- remote state: `stage1` matched `origin/stage1`
- worktree: clean
- project license: `GPL-3.0-only`
- `tools/windows_portable/update_public_key.xml`: still a placeholder
- release/manual Windows workflow runs: already fail closed when the public key or
  `WINDOWS_UPDATE_SIGNING_KEY_XML` secret is missing
- pull-request Windows workflow runs: build an unsigned development update without
  requiring signing secrets
- public Windows releases: require the portable ZIP/checksum and signed update
  ZIP/checksum

The branch may advance after this document is committed. A newer clean
`origin/stage1` is acceptable, but the Windows task must reread the active plan and
review intervening commits before continuing. Do not reset or discard newer work to
force the authoring-time commit.

## Scope map

| Work | Windows task responsibility | Exit evidence |
| --- | --- | --- |
| P1 signing trust | Implement safe key-generation tooling; install only the real public key; prove signing, rejection, apply, and rollback | Public-key validation, non-skipped Windows E2E, signed update proof |
| P2 redistribution | Inspect the exact built bundle; close license/notice/source gaps | Versioned inventory, required license texts, immutable source pointers |
| P3 release assets | Prove `workflow_dispatch` signing and later prove the release-event chain without using the official tag | Successful required-secret run and complete artifact set |
| P6 Windows inventory | Produce a repeatable exact bundle inventory | Deterministic machine-readable inventory from the extracted bundle |
| P7 Windows acceptance | Install and use the downloaded release-candidate artifacts | Completed clean-profile acceptance record |

The following are not Windows-only and must not be silently declared complete by
this task:

- P0 Release Please bootstrap configuration and final squash boundary
- remaining P4 CLI help polish
- P6 vulnerability-audit authority, blocking severity, and exception policy
- P6 Docker digest/snapshot decision
- Apple Silicon default-Docker proof
- optional Linux NVIDIA/X11 proof
- official `v0.1.0` publication and post-release observation

## Security boundary

### Agent-allowed work

The Windows Codex task may:

- edit repository scripts, tests, workflows, and documentation;
- generate disposable RSA keys only inside pytest-controlled temporary directories;
- inspect the committed public key;
- build and inspect unsigned or disposable-key test artifacts;
- run release workflows after the maintainer confirms required secrets exist;
- inspect logs and artifacts after confirming they contain no private material.

### MAINTAINER-ONLY work

The maintainer must perform these steps in a separate, ordinary PowerShell or
browser session—not through Codex or a captured task terminal:

- generate the real release keypair;
- choose and access the private-key output location;
- inspect or copy the private XML;
- put the private XML into the GitHub Actions secret;
- store and verify the encrypted offline backup;
- delete any temporary private-key copies;
- rotate or revoke the key after suspected exposure.

### Non-negotiable rules

- Never place the real private key anywhere under the repository, `dist`,
  `.portable_cache`, a task workspace, or an uploaded artifact.
- Never paste private XML into a task, issue, PR, commit, shell argument, log, or
  documentation file.
- Never run a command in a captured task that prints the private file.
- Only the public XML may be committed.
- The public XML must contain only `Modulus` and `Exponent`; private RSA fields such
  as `P`, `Q`, `DP`, `DQ`, `InverseQ`, and `D` must never appear in tracked key
  material.
- If private material appears in task output, repository history, CI logs, or an
  artifact, stop immediately. Treat the key as compromised, remove the GitHub
  secret, generate a new pair, and do not publish with the exposed key.

GitHub recommends limiting credential permissions and using Actions secrets rather
than storing credentials in source. Repository secrets can be added under
**Settings → Secrets and variables → Actions**. See
[Using secrets in GitHub Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
and the [GitHub secrets reference](https://docs.github.com/en/actions/reference/security/secrets).

## Machine and account prerequisites

Prepare:

- Windows 10 or 11, x64
- a trusted local account or disposable Windows VM/user profile for acceptance
- PowerShell 7 available as `pwsh`
- Windows PowerShell 5.1 retained for updater compatibility checks where practical
- Git
- `uv` on `PATH` or permission to install it through the documented source installer
- network access to the pinned Python, FFmpeg, VapourSynth, L-SMASH-Works, and
  vs-placebo artifacts
- several gigabytes of free space for `.portable_cache`, the expanded bundle,
  release ZIPs, and extracted acceptance copies
- write/admin access to the `TJZine/frame-compare` repository settings and Actions
- an encrypted password-manager attachment, encrypted removable drive, or equivalent
  maintainer-controlled store for the private-key backup
- at least two disposable/private SDR clips and two disposable/private HDR clips
  that may be used for local testing
- no live slow.pics, TMDB, or webhook credentials unless a separate disposable test
  is deliberately authorized

The portable installer is user-level and should not require administrator rights.
Use a clean profile or VM for final acceptance so an older shim, configuration, or
runtime cannot mask a packaging defect.

## W0: Preflight and baseline

Run in PowerShell from the intended parent directory:

```powershell
git clone https://github.com/TJZine/frame-compare.git
Set-Location .\frame-compare
git fetch origin
git switch stage1
git pull --ff-only origin stage1
git status --short
git rev-parse HEAD
git log -10 --oneline

pwsh --version
powershell.exe -NoProfile -Command '$PSVersionTable.PSVersion'
uv --version
```

Expected:

- `git status --short` is empty;
- the intended `stage1` head is checked out;
- `pwsh` is PowerShell 7 or newer;
- `uv` works before implementation begins.

Bootstrap and establish the test baseline:

```powershell
uv sync --group dev --group docs --extra vspreview --frozen
uv run --no-sync pytest -q tests/windows_portable tests/workflows/test_github_workflows.py
```

Record every skip. On the Windows host, a skip claiming that `pwsh`, PowerShell, or
Windows process semantics are unavailable is a preflight failure, not an acceptable
expected skip.

Stop if:

- the worktree contains unexplained changes;
- the branch cannot fast-forward cleanly;
- required pinned artifacts are unreachable;
- Windows E2E tests unexpectedly skip or fail;
- the machine cannot keep the private key outside the repository and task boundary.

## W1: Implement safe key-generation tooling

The repository currently documents key generation but has no maintainer key-generation
script. Add a focused PowerShell owner under `tools/windows_portable/` and matching
tests.

Required contract:

- explicit public and private output paths;
- private output is rejected when it resolves inside the repository;
- private output always fails closed when it already exists;
- public output fails closed unless an explicit switch replaces only the known
  repository placeholder; it must never overwrite an already-real public key;
- RSA is at least 2048 bits; default to 3072 bits unless a documented compatibility
  problem requires a different approved size;
- output uses the RSA XML shape already consumed by `sign_update.ps1`;
- public output contains only `Modulus` and `Exponent`;
- private output contains the complete parameters required for signing;
- public file metadata records a non-placeholder key ID and UTC generation date;
- no private parameter, XML, or file content is written to stdout/stderr;
- status output may contain paths, key size, key ID, generation date, and a
  fingerprint derived from the public XML only;
- the private file receives a current-user-only ACL where the output filesystem
  supports Windows ACLs, and ACL failure is reported rather than silently ignored;
- RSA and file handles are disposed deterministically;
- partial failure does not leave half-written key files;
- tests use disposable keys under pytest temporary directories, never the real key.

Recommended files:

- `tools/windows_portable/generate_update_keypair.ps1`
- focused tests under `tests/windows_portable/`
- `tools/windows_portable/README.txt`
- `docs/ENGINEERING_RUNBOOK.md` if the canonical Windows command changes

Required focused proof:

```powershell
uv run --no-sync pytest -q tests/windows_portable/test_windows_portable_update_scripts.py
uv run --no-sync pytest -q tests/windows_portable/test_windows_portable_update_apply_e2e.py
```

Add or extend tests for:

- accepted key size and XML shape;
- overwrite refusal;
- repository-contained private path rejection;
- output redaction;
- matching public/private pair signs and verifies;
- valid signed update apply and rollback;
- modified manifest rejection;
- modified payload rejection;
- installed files remain unchanged after rejected tampered updates.

Suggested commit:

```text
feat(release): add Windows update key generation
```

Do not generate the real key during W1. Stop and hand control to the maintainer when
the tooling commit and disposable-key tests pass.

## W2: Generate and protect the real release key

This entire section is MAINTAINER-ONLY.

1. Open a separate non-Codex PowerShell 7 window.
2. Mount or unlock the encrypted location that will hold the private key.
3. Run the reviewed key-generation script. Use a private path outside the clone and
   a public path at `tools\windows_portable\update_public_key.xml`.
   The reviewed script's expected command shape is:

   ```powershell
   $keyId = "frame-compare-update-2026-01"
   pwsh -NoProfile -ExecutionPolicy Bypass `
     -File .\tools\windows_portable\generate_update_keypair.ps1 `
     -PublicKeyPath .\tools\windows_portable\update_public_key.xml `
     -PrivateKeyPath "<encrypted-location-outside-the-repository>" `
     -KeyId $keyId `
     -KeySize 3072 `
     -ReplacePlaceholderPublicKey
   ```

   Replace the placeholder path in the private PowerShell window. Do not paste the
   real path back into the task.
4. Confirm the command reports only public metadata and a public fingerprint.
5. Validate the public key:

   ```powershell
   pwsh -NoProfile -ExecutionPolicy Bypass `
     -File .\tools\windows_portable\validate_update_public_key.ps1 `
     -PublicKeyPath .\tools\windows_portable\update_public_key.xml
   ```

6. Store a second encrypted backup controlled by the maintainer.
7. In the GitHub repository, create/update the Actions repository secret named
   `WINDOWS_UPDATE_SIGNING_KEY_XML` with the complete private XML as its value.
8. Confirm only the secret name and updated timestamp are visible afterward.
9. Remove any unencrypted temporary copy. Retain only the approved encrypted
   primary and backup copies.

Do not put the private-key contents into a command line. GitHub documents both
browser and interactive `gh secret set` methods; the browser is preferred here so
the private XML does not enter the task terminal.

Return to the Codex task only after stating:

```text
MAINTAINER CHECKPOINT
real key generated: yes
public key written in repository: yes
encrypted primary stored: yes
encrypted backup stored: yes
WINDOWS_UPDATE_SIGNING_KEY_XML configured: yes
private value disclosed to task: no
```

Do not provide the private value, its XML fields, or an unredacted storage path.

## W3: Review and commit only the public key

The agent may resume after the maintainer checkpoint.

Inspect only the public file and repository status:

```powershell
git status --short
pwsh -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\windows_portable\validate_update_public_key.ps1 `
  -PublicKeyPath .\tools\windows_portable\update_public_key.xml
git diff -- .\tools\windows_portable\update_public_key.xml

[xml]$publicKey = Get-Content `
  -LiteralPath .\tools\windows_portable\update_public_key.xml `
  -Raw
$publicFields = @($publicKey.RSAKeyValue.ChildNodes | ForEach-Object { $_.Name })
$privateFields = @("P", "Q", "DP", "DQ", "InverseQ", "D")
if (@($publicFields | Where-Object { $_ -in $privateFields }).Count -ne 0) {
  throw "Committed public key contains private RSA fields."
}
if (@($publicFields | Where-Object { $_ -notin @("Modulus", "Exponent") }).Count -ne 0) {
  throw "Committed public key contains unexpected RSA fields."
}
```

Expected:

- the public key placeholder is gone;
- the modulus meets the validator minimum;
- metadata has a real key ID and UTC date;
- the parsed public XML contains only `Modulus` and `Exponent`;
- no private-key file appears in `git status`;
- no unrelated file changed during key generation.

Suggested separate commit:

```text
chore(release): install Windows update public key
```

Do not rotate this committed public key after shipping clients without a separate
key-migration design.

## W4: Build and inspect the exact Windows bundle

Build from the committed, clean Windows head:

```powershell
$bundleDir = Join-Path $PWD "dist\frame-compare-portable-win-x64"
$cacheDir = Join-Path $PWD ".portable_cache"

pwsh -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\windows_portable\build_portable.ps1 `
  -ManifestPath .\tools\windows_portable\manifest.windows-x64.json `
  -OutDir $bundleDir `
  -CacheDir $cacheDir `
  -RequireReleasePublicKey

& "$bundleDir\frame-compare.ps1" version
& "$bundleDir\frame-compare.ps1" --help
& "$bundleDir\frame-compare.ps1" doctor --json
```

The build itself already proves package imports, VapourSynth layout, L-SMASH frame
loading, tonemap APIs, a real tonemap frame path, and optional VSPreview/PyQt6
imports. Treat any required proof failure as a blocker.

### Exact bundle inventory requirement

Implement or extend a repeatable bundle-audit owner rather than relying on a
one-time manual directory listing. The resulting machine-readable inventory should
be sorted and should contain no absolute local paths or secrets.

The inventory must cover:

- Frame Compare version, commit SHA, and `GPL-3.0-only` license;
- every installed Python distribution name/version and declared license metadata;
- PyQt6, PyQt6-Qt6, PyQt6-sip, VSPreview, and VapourSynth;
- manifest-provided Python, FFmpeg, VapourSynth, L-SMASH-Works, and vs-placebo
  artifacts;
- every copied license/notice relative path and SHA-256;
- the requirements-lock fingerprint;
- immutable or exact-version source locations;
- the corresponding Frame Compare source commit/archive and bundled build/install
  scripts.

At handoff authoring time the lock contains PyQt6 `6.10.2`, PyQt6-Qt6 `6.10.2`,
PyQt6-sip `13.10.3`, VSPreview `0.20.1`, and VapourSynth `R76`. The built artifact,
not this sentence, is authoritative; update the handoff/plan if the lock changes.

Inspect the extracted bundle and fail closed if any required item is missing:

- `licenses\frame-compare-LICENSE.txt` is the complete GPLv3 text;
- Python and PyQt/Qt license directories are present;
- Python, FFmpeg, VapourSynth, L-SMASH-Works, and vs-placebo notices are present;
- `SOURCE_URLS.txt` or its replacement uses exact version/commit source pointers,
  not only generic project homepages;
- the Frame Compare source pointer identifies the exact commit used to build;
- the source tree at that commit contains the Windows build/install scripts;
- no private key, credential, cache, local configuration, input clip, or generated
  report appears in the bundle.

If current `SOURCE_URLS.txt` or copied licenses do not satisfy that inventory, fix
the builder, manifest, tests, and Windows user documentation in one focused package.
Suggested commit:

```text
fix(release): complete Windows bundle license inventory
```

This is an engineering compliance check, not a claim of individualized legal
advice. If the exact PyQt6/Qt source-and-license posture remains uncertain, do not
publish the Windows binary.

## W5: Prove signed update behavior locally

First build an update from the exact bundle and repository source:

```powershell
$appVersion = (
  uv run --no-sync python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"
).Trim()
$updateZip = Join-Path $PWD "dist\frame-compare-update-win-x64-$appVersion.zip"

pwsh -NoProfile -ExecutionPolicy Bypass `
  -File .\tools\windows_portable\build_update.ps1 `
  -BundleDir $bundleDir `
  -OutFile $updateZip
```

Signing the update with the real key is MAINTAINER-ONLY. In the separate private
PowerShell window, set `SIGNING_KEY_XML_PATH` to the protected file path, run
`sign_update.ps1`, and remove the environment variable immediately afterward. The
private XML must not be displayed.

```powershell
$env:SIGNING_KEY_XML_PATH = "<encrypted-private-key-path>"
try {
  pwsh -NoProfile -ExecutionPolicy Bypass `
    -File .\tools\windows_portable\sign_update.ps1 `
    -UpdateZip .\dist\frame-compare-update-win-x64-0.1.0.zip
} finally {
  Remove-Item Env:\SIGNING_KEY_XML_PATH -ErrorAction SilentlyContinue
}
```

Replace both version and protected path with the actual values in the private
window. Only the public fingerprint printed by the signer may be copied into the
evidence record.

Back in the normal task, the agent may inspect the signed ZIP structure and public
signature result. Install the bundle from a clean extracted location:

```powershell
& "$bundleDir\install.cmd"
```

Open a new ordinary terminal and run:

```powershell
frame-compare version
frame-compare --help
frame-compare-update --help
frame-compare-update apply <path-to-signed-update-zip>
frame-compare-update list-backups
frame-compare-update rollback <backup-id>
```

Required proof:

- the signed update applies without an unsigned warning;
- the installed public key verifies the signature created by the protected private
  key;
- a backup is created;
- rollback succeeds;
- version/help/doctor still work after apply and after rollback;
- a manifest-tampered copy is rejected without changing installed files;
- a payload-tampered copy is rejected without changing installed files;
- dependency-fingerprint mismatch remains fail-closed unless the explicitly unsafe
  path is deliberately tested with disposable state;
- the private key is absent from update ZIPs, bundle ZIPs, logs, and temporary
  repository paths.

Prefer automated disposable-key tamper and rollback coverage plus one maintainer-run
real-key valid-signature rehearsal. Do not inject the real private key into pytest.

## W6: Run the full Windows verification gate

Run from a clean committed tree:

```powershell
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
git diff --check
git status --short
```

Also rerun the focused Windows set:

```powershell
uv run --no-sync pytest -q tests/windows_portable tests/workflows/test_github_workflows.py
```

Expected:

- static checks and the full suite pass;
- Windows E2E tests execute rather than skip for missing PowerShell/Windows;
- docs build strictly;
- intended changes are committed in reviewable Conventional Commits;
- the worktree is clean;
- `dist` and `.portable_cache` remain ignored and uncommitted.

## W7: Prove the protected GitHub Actions path

This step requires the public-key commit and the
`WINDOWS_UPDATE_SIGNING_KEY_XML` repository secret to be pushed to a branch.

In GitHub Actions:

1. Open the `windows-portable` workflow.
2. Choose **Run workflow**.
3. Select the branch containing the public key and Windows remediation commits.
4. Start the `workflow_dispatch` run.
5. Confirm the public-key validation step passes.
6. Confirm the signing step completes; absence of the secret must fail the run.
7. Confirm bundle and update ZIP/checksum artifacts are uploaded.
8. Download the artifacts to a clean directory.
9. Verify both SHA-256 files before extraction.
10. Inspect the update ZIP for `update-manifest.json`,
    `update-manifest.sig`, and the code payload.
11. Confirm logs and artifacts contain no private key material.

`workflow_dispatch` proves the protected Windows build/sign path. It does not prove
that a Release Please-created release triggers the separate release event.

`RELEASE_PLEASE_TOKEN` must also be configured as a narrowly scoped fine-grained PAT
or GitHub App token capable of creating/updating the release PR and publishing the
release. For a fine-grained PAT, restrict repository access to
`TJZine/frame-compare`, use a bounded expiration, and grant only the required
repository permissions—currently **Contents: read and write** and
**Pull requests: read and write**. Recheck those permissions against the pinned
Release Please action before creating the credential. GitHub documents fine-grained
token permissions in
[Permissions required for fine-grained personal access tokens](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens).

Prove the actual Release Please → published release → Windows workflow chain with a
disposable repository or explicitly disposable prerelease path. Do not use the
official `v0.1.0` tag as the first experiment. If there is no safe disposable proof
path, return that as an unresolved P3 blocker rather than improvising on `main`.

## W8: Exact downloaded-asset acceptance

Perform this only after a release candidate exists through the approved release
path. Test the downloaded asset, not a workspace bundle.

### Integrity and clean installation

- Download the versioned portable ZIP and its `.sha256` from the same candidate
  release.
- Verify SHA-256 before extraction.
- Extract to a new directory in a clean user profile or VM.
- Run `install.cmd`.
- Open a new terminal.
- Confirm `frame-compare version`, `--help`, and updater help.

### First-run behavior

- Put at least two SDR clips in the documented input directory.
- Run `wizard`, `doctor`, and `run --dry-run`.
- Complete one SDR comparison.
- Repeat with at least two HDR clips and complete one HDR comparison.
- Keep slow.pics and webhooks disabled.

### Feature-complete Windows behavior

- exercise VSPreview/manual alignment;
- inspect screenshot labels;
- open the offline report;
- test slider, overlay, difference, blink, grid, filmstrip, keyboard navigation,
  and zoom;
- confirm run history list/open behavior;
- confirm generated paths remain under the expected bundle/user workspace;
- confirm no unexpected network publication occurs.

### Update lifecycle

- apply the signed candidate update;
- reject manifest and payload tampering;
- list backups;
- roll back;
- verify the app after rollback;
- uninstall the shim;
- confirm user media, reports, and the portable directory are retained.

Any failure returns to its owning package. Do not waive an unexplained warning merely
because the source-tree tests passed.

## Evidence record

Record only non-secret evidence:

```text
WINDOWS_RELEASE_EVIDENCE
date_utc:
tester:
windows_version:
powershell_7_version:
windows_powershell_version:
git_commit:
candidate_tag_or_workflow_run:

focused_windows_tests: PASS | FAIL
full_repository_gate: PASS | FAIL
release_public_key_validation: PASS | FAIL
portable_build_require_release_key: PASS | FAIL
bundle_runtime_proof: PASS | FAIL
bundle_license_inventory: PASS | FAIL
corresponding_source_inventory: PASS | FAIL
real_key_signed_update_apply: PASS | FAIL
tampered_manifest_rejected: PASS | FAIL
tampered_payload_rejected: PASS | FAIL
rollback: PASS | FAIL
workflow_dispatch_signed_artifacts: PASS | FAIL
release_event_chain: PASS | FAIL | NOT YET PROVED
clean_profile_rc_acceptance: PASS | FAIL | NOT YET RUN

portable_zip_sha256:
update_zip_sha256:
public_key_fingerprint:
private_key_present_in_repo_logs_artifacts: NO
unexpected_skips_or_warnings:
remaining_blockers:
commits_created:
```

Do not record the private-key XML, private-key hash, secret value, or unredacted
private storage location.

## Commit boundaries

Use separate commits when each scope is present:

1. `feat(release): add Windows update key generation`
2. `chore(release): install Windows update public key`
3. `fix(release): complete Windows bundle license inventory`
4. `test(release): prove signed Windows update lifecycle`
5. `docs(release): record Windows release evidence`

Do not mix signing-key changes with CLI help, Release Please bootstrap metadata,
Docker hardening, or unrelated cleanup.

Push only after the intended commits pass the full Windows gate and the diff contains
no private material.

## Stop conditions

Stop immediately and report the blocker when:

- real private key material enters the repository, task, logs, or artifacts;
- the public/private pair does not verify end to end;
- the release/manual workflow can succeed without the signing secret;
- a release-like artifact lacks `update-manifest.sig`;
- a tampered update changes installed files;
- rollback cannot restore a working application;
- the exact bundle lacks an applicable license, notice, or source pointer;
- the bundle source pointer does not identify the exact build commit;
- Windows tests skip because the required Windows/PowerShell boundary is unavailable;
- checksum verification fails;
- the downloaded candidate behaves differently from the workspace-built bundle;
- the intended Git history requires destructive rewriting;
- the official tag would be the first proof of release-event chaining.

## Handoff back to the primary release task

Return:

- commit hashes and Conventional Commit titles;
- the completed non-secret evidence record;
- the GitHub Actions run URL;
- artifact names and SHA-256 values;
- public-key ID/fingerprint only;
- exact license/source inventory result;
- every failure, skip, warning, and documented-only proof;
- confirmation that no private key material was exposed;
- whether P1, the Windows portion of P2/P6, P3, and Windows P7 can be marked
  complete.

Do not return “all done” while any stop condition or release blocker remains.
