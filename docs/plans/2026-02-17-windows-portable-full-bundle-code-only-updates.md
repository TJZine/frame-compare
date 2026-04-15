# Windows Portable Full Bundle + Code-Only Updates Implementation Plan

Status: Historical
Scope: Historical implementation record for the February 2026 Windows portable/update work
Owner: Historical session archive

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship a Windows portable **full** bundle that includes VSPreview (+ Qt backend) out-of-the-box, and a small, offline, code-only update package + updater command that avoids re-downloading heavy dependencies every release.

**Architecture:** Treat the portable install as two layers: (1) a rarely-changing **base runtime** (embedded Python + site-packages + VS/FFmpeg/Qt), and (2) frequently-changing **app code** (`app/src/frame_compare`). Distribute small “update zips” that replace only the app code after hash verification, with backup + rollback.

**Tech Stack:** PowerShell scripts (updater MUST be compatible with Windows PowerShell 5.1; PowerShell 7 supported), `uv` lock/export/install, JSON manifests, SHA256 verification (`Get-FileHash`), Windows portable layout already used by `build_portable.ps1`.

---

## Release Artifacts (Target)

- **Full bundle zip** (rare): `frame-compare-portable-win-x64-full-<version>.zip`
  - Contains: embedded Python, `app/site-packages` (including `vspreview` + Qt backend), VapourSynth, plugins, FFmpeg, and launchers.
- **Code-only update zip** (often): `frame-compare-update-win-x64-<version>.zip`
  - Contains: `update-manifest.json` + a payload directory with only `app/src/frame_compare/**`.
- **Updater command** (ships in full bundle + installed shim): `frame-compare-update.cmd` / `frame-compare-update.ps1`
  - Applies an update zip to the currently-installed portable bundle.

## Invariants / Best-Practice Guardrails

- Offline-first: update packages apply without network.
- Integrity: update zip must include SHA256 hashes; updater verifies before applying.
- Authenticity: update package must be **cryptographically signed**; updater verifies signature using a committed public key before applying.
- Safety: updater creates a backup and supports rollback; auto-rollback on smoke-check failure.
- Determinism: dependencies are pinned in `uv.lock`, exported to `requirements.lock.txt` inside the bundle.
- Strictness: if dependency fingerprint mismatch is detected, default action is **Cancel**; user can “Apply anyway (Unsafe)” with explicit confirmation and auto-rollback.
- Non-interactive safety: in non-TTY contexts, updater must not prompt; it must fail with a clear message and exit code.
- Concurrency safety: updater uses a lock file to prevent concurrent updates and provides actionable error messages when files are locked (AV / running processes).
- Cleanup: updater must clean temp extraction directories and only retain bounded backups (retention policy).

---

### Task 1: Define a portable “interactive alignment” dependency set (VSPreview + Qt)

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` (regenerated)
- Modify: `README.md`

**Step 1: Add an optional dependency extra**

Edit `pyproject.toml` to add:

```toml
[project.optional-dependencies]
vspreview = [
  "vspreview",
  "PySide6",
]
```

Notes:
- Prefer `PySide6` as the default Qt backend for licensing/distribution simplicity; support `PyQt5` later only if needed.
- Keep constraints permissive in `pyproject.toml`; determinism comes from `uv.lock`.
- Treat GUI stack as a “full bundle only” dependency: `slim` (if ever revived) must NOT include it.

**Step 2: Regenerate lock**

Run:
- `uv lock`

Expected: `uv.lock` updates with new wheels/hashes.

**Step 3: Update docs to explain “full bundle includes VSPreview”**

Update `README.md` “Windows Portable” section to state:
- Full portable includes VSPreview+Qt.
- Source installs may optionally add `.[vspreview]`.

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock README.md
git commit -m "feat(portable): add vspreview extra for full bundle"
```

---

### Task 2: Make the portable build include the VSPreview extra in `app/site-packages`

**Files:**
- Modify: `tools/windows_portable/build_portable.ps1`

**Step 1: Write a failing “bundle runtime validation” check (PowerShell)**

In `Assert-BundleRuntime`, extend the validation command to include VSPreview + Qt:

Expected behavior:
- Before implementation, it should fail in a locally built bundle because VSPreview isn’t installed into `app/site-packages`.

Add a check like:

```powershell
& $python -c "import vspreview; import PySide6; import frame_compare"
```

**Step 2: Run the portable build and confirm it fails**

On Windows (or CI Windows runner):

```powershell
pwsh -File .\tools\windows_portable\build_portable.ps1
```

Expected: FAIL with import error for `vspreview` or `PySide6`.

**Step 3: Install deps with the extra**

Change the export line in `Install-PythonDeps` to include the extra:

```powershell
uv export --frozen --no-dev --no-emit-project --extra vspreview --format requirements.txt --output-file $reqFile | Out-Null
```

**Step 4: Re-run portable build and confirm it passes**

Expected: `Assert-BundleRuntime` passes, portable folder assembled.

**Step 5: Ensure Qt DLL / plugin resolution works in the portable runtime**

Rationale:
- Installing `PySide6` into `app/site-packages` is necessary but may be insufficient: Qt DLLs (e.g. `Qt6Core.dll`)
  live under `PySide6/Qt/bin` and must be discoverable by the Windows loader at runtime.
- VSPreview launch also requires Qt platform plugins (e.g. `qwindows.dll`) under `PySide6/Qt/plugins`.

Implementation requirements (PowerShell):
- In the bundle launcher generated by `Write-LauncherFiles` inside `tools/windows_portable/build_portable.ps1`,
  add `"$bundleRoot\\app\\site-packages\\PySide6\\Qt\\bin"` to the front of `$env:PATH` (best-effort if it exists).
- In `Assert-BundleRuntime`, also add that same path to `$env:PATH` before running the import validation.

Manual validation (Windows):
- After building the bundle, run:

```powershell
.\dist\frame-compare-portable-win-x64\frame-compare.ps1 doctor
```

Expected: doctor reports VSPreview available (not just installed).

**Step 6: Commit**

```bash
git add tools/windows_portable/build_portable.ps1
git commit -m "feat(portable): bundle vspreview + PySide6 in full build"
```

---

### Task 3: Add a stable dependency fingerprint to the full bundle

**Files:**
- Modify: `tools/windows_portable/build_portable.ps1`
- Create: `tools/windows_portable/bundle_info.schema.json` (optional but recommended)

**Step 1: Define `bundle_info.json` shape**

Create a small JSON object written into bundle root (e.g. `<bundle>/bundle_info.json`):

```json
{
  "schema_version": 1,
  "bundle_kind": "full",
  "app_version": "0.1.0",
  "requirements_lock_sha256": "<hex>",
  "manifest_version": 1,
  "platform": "windows-x64"
}
```

**Step 2: Implement writing `bundle_info.json`**

In `build_portable.ps1`, after `Install-PythonDeps` (after `requirements.lock.txt` exists), compute:
- SHA256 of `<bundle>/requirements.lock.txt`
- app version by reading `src/frame_compare/__init__.py` in repo or by invoking embedded python in bundle.

Write JSON with UTF-8 (no BOM).

**Step 3: Manual verification**

Build the bundle; verify:
- `bundle_info.json` exists
- fingerprint matches `Get-FileHash requirements.lock.txt -Algorithm SHA256`

**Step 4: Commit**

```bash
git add tools/windows_portable/build_portable.ps1 tools/windows_portable/bundle_info.schema.json
git commit -m "feat(portable): write bundle_info.json with deps fingerprint"
```

---

### Task 4: Specify the code-only update package format (manifest + signature + payload)

**Files:**
- Create: `tools/windows_portable/update_manifest.schema.json`
- Create: `docs/api.md` (optional doc section) OR update `README.md` update section

**Step 1: Define the schema**

Create `tools/windows_portable/update_manifest.schema.json` for a JSON manifest like:

```json
{
  "schema_version": 1,
  "target_platform": "windows-x64",
  "to_app_version": "0.1.1",
  "from_app_version_min": "0.1.0",
  "from_app_version_max": null,
  "expected_requirements_lock_sha256": "<hex>",
  "signature_algorithm": "rsa-sha256-pkcs1",
  "signature_file": "update-manifest.sig",
  "payload_root": "payload",
  "files": [
    {
      "path": "app/src/frame_compare/__init__.py",
      "sha256": "<hex>",
      "bytes": 1234
    }
  ]
}
```

Constraints:
- `files[].path` MUST be relative and MUST NOT contain `..`, start with `/`, or include drive letters.
- All file paths MUST live under `app/src/frame_compare/`.
- `signature_file` MUST be a relative path under the update zip root and MUST NOT contain traversal.
- `from_app_version_min`/`from_app_version_max` are a safety valve for updater format changes. Default to wide compatibility (min = current major/minor, max = null) unless intentionally breaking.

**Step 2: Commit**

```bash
git add tools/windows_portable/update_manifest.schema.json
git commit -m "feat(portable): add code-only update manifest schema"
```

---

### Task 5: Add an update signing key (public) and signing process (private out-of-repo)

**Files:**
- Create: `tools/windows_portable/update_public_key.xml`
- Create: `tools/windows_portable/sign_update.ps1`
- Modify: `tools/windows_portable/README.txt`

**Step 1: Choose a signature scheme compatible with Windows PowerShell 5.1**

Use RSA SHA-256 PKCS#1 v1.5 for v1, because it is supported by .NET Framework:
- Public key: committed as `.xml` (RSAParameters) for easy import in PS5.1.
- Private key: stored securely by maintainers, never committed.

**Step 2: Create `update_public_key.xml`**

Add a placeholder with clear instructions:
- Real public key value must be generated once and committed.
- Include a `key_id` comment (human-readable) and the generation date in `README.txt`.

**Step 3: Create a signing script `sign_update.ps1`**

Script behavior:
- Inputs: `-UpdateZip <path>` and a private key path provided via `SIGNING_KEY_XML_PATH` (or interactive prompt).
- Extract `update-manifest.json` bytes from the zip
- Compute signature over the exact UTF-8 bytes of `update-manifest.json` as stored in the zip
- Write signature as base64 to `update-manifest.sig` inside the zip (replace if present)
- Print the public key fingerprint and the update version for release logs

**Step 4: Document release signing**

In `tools/windows_portable/README.txt`, document:
- How to generate the RSA keypair (one-time)
- How to sign an update zip for release
- That unsigned updates are for local/dev only and require explicit unsafe flags in the updater

**Step 5: Commit**

```bash
git add tools/windows_portable/update_public_key.xml tools/windows_portable/sign_update.ps1 tools/windows_portable/README.txt
git commit -m "feat(portable): add signed update mechanism (public key + signing script)"
```

---

### Task 6: Build an update zip generator (`build_update.ps1`)

**Files:**
- Create: `tools/windows_portable/build_update.ps1`
- Modify: `tools/windows_portable/README.txt`

**Step 1: Implement staging layout**

`build_update.ps1` inputs:
- `-BundleDir` (path to a built full bundle directory)
- `-RepoRoot` (default: `..\..` like build_portable)
- `-OutFile` (zip path)

Staging directory layout:

```
<staging>/
  update-manifest.json
  update-manifest.sig   (optional; present only when signed)
  payload/
    app/src/frame_compare/**   (copied from repo)
```

**Step 2: Compute hashes**

For each file under `src/frame_compare/**` in repo, map it to payload path `app/src/frame_compare/**` and compute:
- SHA256 (`Get-FileHash`)
- bytes (`(Get-Item).Length`)

Sort file entries by `path` for determinism.

**Step 3: Set expected deps fingerprint**

Read the built bundle’s fingerprint from:
- `<BundleDir>/bundle_info.json` (preferred), else
- compute SHA256 of `<BundleDir>/requirements.lock.txt`

Write it into the manifest as `expected_requirements_lock_sha256`.

**Step 4: Zip**

Create zip at `-OutFile`:
- ensure deterministic-ish ordering by writing files in sorted order (PowerShell zip determinism is imperfect; hash verification is what matters).

**Step 5: Manual test**

On Windows:

```powershell
pwsh -File .\tools\windows_portable\build_update.ps1 -BundleDir .\dist\frame-compare-portable-win-x64 -OutFile .\dist\frame-compare-update.zip
```

Expected: zip created; contains manifest + payload.

**Step 6: Commit**

```bash
git add tools/windows_portable/build_update.ps1 tools/windows_portable/README.txt
git commit -m "feat(portable): add code-only update zip generator"
```

---

### Task 7: Add an updater shim command (`frame-compare-update`)

**Files:**
- Create: `tools/windows_portable/shim/frame-compare-update.ps1`
- Create: `tools/windows_portable/shim/frame-compare-update.cmd`
- Modify: `tools/windows_portable/install.ps1`
- Modify: `tools/windows_portable/uninstall.ps1`

**Step 1: Implement “locate active bundle” logic**

Copy the config discovery logic from `tools/windows_portable/shim/frame-compare.ps1`:
- read `%LOCALAPPDATA%\Programs\FrameCompare\state\config.json`
- validate schema_version/install_type
- get `bundle_path`

**Step 2: Implement `apply` command parsing**

Example UX:

```text
frame-compare-update apply C:\Downloads\frame-compare-update-win-x64-0.1.1.zip
frame-compare-update rollback <backup-id>
frame-compare-update list-backups
frame-compare-update purge-backups --keep 5
frame-compare-update --help
```

**Step 3: Implement secure extraction + manifest validation**

- Do NOT use `Expand-Archive` on an untrusted update zip (zip-slip risk).
- Open the zip via `.NET` (`System.IO.Compression.ZipArchive`) and validate all entry names BEFORE extracting anything:
  - No absolute paths (`/`, `\\`, drive letters like `C:`)
  - No traversal segments (`..`)
  - Normalize separators and re-check
- Extract ONLY the expected entries (`update-manifest.json`, `update-manifest.sig`, and payload files) into a temp dir under
  `%TEMP%\FrameCompareUpdate\<guid>\` using safe join + prefix checks.
- Load `update-manifest.json`
- Validate:
  - `schema_version`
  - `target_platform`
  - installed app version is within `[from_app_version_min, from_app_version_max]` (treat null max as “no upper bound”)
  - `payload_root`
  - file paths are safe (no traversal, only under `app/src/frame_compare/`)
- Verify each file hash matches manifest before applying.
- Verify signature BEFORE hashing/copying payload:
  - Load `tools/windows_portable/update_public_key.xml` (installed with updater)
  - Read `signature_file` from manifest and load it from the extracted temp directory
  - Verify RSA signature over the exact bytes of `update-manifest.json`
  - If signature missing/invalid:
    - If non-interactive: fail
    - If interactive: prompt with default **Cancel** and an **explicit** “Apply unsigned (Unsafe)” path requiring typing `UNSIGNED`

**Step 4: Compare deps fingerprint**

- Compute installed fingerprint from `<bundle>/requirements.lock.txt` SHA256 (or `<bundle>/bundle_info.json`)
- If mismatch:
  - If non-interactive: fail with message + exit code
  - If interactive: prompt with default **Cancel**
    - `C` Cancel (recommended)
    - `O` Open download page (best-effort)
    - `U` Unsafe apply anyway (requires typing `APPLY`)
    - `X` Apply unsigned (Unsafe) (requires typing `UNSIGNED`) (only offered when signature is missing/invalid)

**Step 5: Backup + apply with rollback**

Backup target dir:
- `<bundle>/app/src/frame_compare` → `<bundle>/app/.update_backups/<timestamp>/frame_compare`

Apply strategy (minimize “partial apply”):
- Copy payload `app/src/frame_compare` to `<bundle>/app/src/frame_compare.new`
- Rename existing to `<bundle>/app/src/frame_compare.old`
- Rename `.new` to `frame_compare`
- If any step fails, restore from backup and remove temp dirs.

Robustness requirements:
- Use a lock file: `<bundle>/app/.update_lock` acquired at start, removed at end (in `finally`).
- Implement retry with backoff for rename/delete operations (common AV/file-lock issues):
  - 10 attempts; sleep 200ms → 2s
  - On final failure, print: “Close any running frame-compare terminals, then retry.”

**Step 6: Smoke check**

Run:
- `<bundle>/frame-compare.ps1 version` and ensure it prints the new version.
- Or: `python -c "import frame_compare; print(frame_compare.__version__)"`

On failure: auto-rollback and print a clear explanation.

**Step 6.5: Retention + cleanup**

- After successful apply:
  - delete `<bundle>/app/src/frame_compare.old`
  - delete `<bundle>/app/src/frame_compare.new` if it exists
  - delete the temp extraction directory
- Backup retention:
  - keep newest N backups (default 5)
  - provide `purge-backups --keep N` and call it automatically after a successful update

**Step 7: Wire installer/uninstaller**

Update `install.ps1` to copy the new shim scripts into `%LOCALAPPDATA%\Programs\FrameCompare\bin` like it does for `frame-compare`.
Update `uninstall.ps1` to remove them.

**Step 8: Commit**

```bash
git add tools/windows_portable/shim/frame-compare-update.ps1 tools/windows_portable/shim/frame-compare-update.cmd tools/windows_portable/install.ps1 tools/windows_portable/uninstall.ps1
git commit -m "feat(portable): add frame-compare-update shim for code-only updates"
```

---

### Task 8: Include updater scripts in the built bundle root (optional convenience)

**Files:**
- Modify: `tools/windows_portable/build_portable.ps1`

**Step 1: Copy updater entrypoints into bundle root**

Optionally ship:
- `<bundle>/frame-compare-update.ps1`
- `<bundle>/frame-compare-update.cmd`

These can forward to the shim-installed updater OR run standalone from bundle root.

**Step 2: Commit**

```bash
git add tools/windows_portable/build_portable.ps1
git commit -m "feat(portable): ship updater entrypoints in bundle root"
```

---

### Task 9: Documentation + “happy path” UX copy

**Files:**
- Modify: `README.md`
- Modify: `tools/windows_portable/README.txt`

**Step 1: Add an “Updating” section**

Document:
- Full bundle download/install
- Where updates are published
- How to apply:

```powershell
frame-compare-update apply .\frame-compare-update-win-x64-0.1.1.zip
```

Include:
- What to do on “deps mismatch”
- How to rollback
- How signature verification works (and why unsigned updates are blocked by default)

**Step 2: Commit**

```bash
git add README.md tools/windows_portable/README.txt
git commit -m "docs(portable): document full bundle + code-only updates"
```

---

### Task 10: License/compliance + clean-machine validation (required before release)

**Files:**
- Modify: `tools/windows_portable/build_portable.ps1`
- Modify: `tools/windows_portable/README.txt`

**Step 1: Decide and document the compliance stance for bundled Python wheels**

Bundling `PySide6`/Qt introduces license obligations (e.g., LGPL terms, notice files). Before shipping the “full” bundle:
- Add a “Third-party licenses” note to `tools/windows_portable/README.txt` describing where license texts are located.
- Extend the build to emit a `licenses/python/` directory with license texts for Python-installed wheels included in `app/site-packages`.
  Minimal acceptable v1: copy each dist’s `LICENSE*` and `COPYING*` file from its `*.dist-info/` directory when present,
  plus preserve any Qt license/notice files shipped in `PySide6` (e.g. under `PySide6/Qt/licenses` when present).
- Add a short “Source availability” note for LGPL components (Qt/FFmpeg/VapourSynth) pointing to upstream source URLs
  and/or the exact artifact URLs already pinned in the manifest for reproducibility.

**Step 2: Verify the full bundle on a clean Windows machine**

On a clean Windows VM (no Python/VS/Qt installed; ideally default MSVC runtimes only):
- Extract the full bundle
- Run `.\install.cmd`
- Confirm:

```powershell
frame-compare doctor
frame-compare run --force-interactive-alignment
```

Expected:
- doctor reports VSPreview available
- `--force-interactive-alignment` triggers VSPreview launch when inputs are present, or fails with an actionable message
  (not missing DLL / missing Qt platform plugin errors).

If PySide6 requires additional MSVC runtime DLLs beyond what the embedded Python provides, document the requirement or
bundle the runtime with explicit licensing.

---

### Task 11: End-to-end manual verification on Windows (required before release)

**Files:**
- (no code changes; verification only)

**Step 1: Build the full bundle**

```powershell
pwsh -File .\tools\windows_portable\build_portable.ps1
```

**Step 2: Install shim**

From the built bundle directory:

```powershell
.\install.cmd
```

Open a new terminal and confirm:

```powershell
frame-compare doctor
frame-compare version
```

Expected:
- doctor shows VSPreview available
- version prints expected app version

**Step 3: Build an update zip for a newer code version**

Change code version (`src/frame_compare/__init__.py`) and rebuild update zip:

```powershell
pwsh -File .\tools\windows_portable\build_update.ps1 -BundleDir .\dist\frame-compare-portable-win-x64 -OutFile .\dist\frame-compare-update.zip
```

**Step 4: Apply update**

```powershell
frame-compare-update apply .\dist\frame-compare-update.zip
frame-compare version
```

Expected: version updates; a backup folder is created; update reports success.

**Step 5: Simulate mismatch and confirm UX**

Modify `expected_requirements_lock_sha256` in manifest (or use a bundle from a different deps fingerprint) and ensure:
- updater prompts and defaults to Cancel
- unsafe apply requires explicit `APPLY`
- failed smoke-check rolls back automatically
- signature missing/invalid triggers prompt and defaults to Cancel
- non-interactive mode fails safely with a clear message + exit code

---

## Notes / Future Hardening (Not required for v1)

- Key rotation + multi-key trust store (support overlapping keys during rotation).
- Optional “signed zip” verification (sign the whole update zip in addition to the manifest) for defense-in-depth.
- Delta patches (bsdiff) to reduce update zip size further (complex, optional).
- Add a `frame-compare update` CLI subcommand for parity (still keep shim for best UX).

---

## NEXT AGENT PROMPT (COPY/PASTE)

Implement the plan in `docs/plans/2026-02-17-windows-portable-full-bundle-code-only-updates.md` task-by-task.
Use superpowers:executing-plans. Create small commits per task. Keep the updater offline-first with hash verification,
signature verification (default Cancel on missing/invalid signature; unsafe requires typing UNSIGNED), backup + rollback,
bounded backup retention, and an interactive prompt on deps fingerprint mismatch (default Cancel; unsafe apply requires typing APPLY).
