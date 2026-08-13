# Windows Portable Install

> [!TIP]
> **The Windows portable bundle is the most complete distribution of Frame Compare.**
> It ships VSPreview + PyQt6 for interactive manual alignment, GPU-accelerated
> tonemapping via the host Vulkan stack, and the native installer/update flow.
> The default Docker path does not include any of these.

---

## Quick Install

### From a Published GitHub Release Zip

Release bundles are the intended recommended route. If the
[GitHub Releases page](https://github.com/TJZine/frame-compare/releases) has no
`frame-compare-portable-win-x64-<tag>.zip`, use the source-build route below.

```powershell
# 1) Download both files from the same GitHub Release:
#    frame-compare-portable-win-x64-<tag>.zip
#    frame-compare-portable-win-x64-<tag>.zip.sha256
# 2) Verify the ZIP as shown below, then extract it.
# 3) From the extracted folder:
.\install.cmd
```

Verify the ZIP before extracting or running it. Replace `<tag>` in both filenames
with the release tag shown on GitHub:

```powershell
$zip = ".\frame-compare-portable-win-x64-<tag>.zip"
$checksumFile = "$zip.sha256"
$expected = ((Get-Content -LiteralPath $checksumFile -Raw).Trim() -split "\s+")[0].ToLowerInvariant()
$actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) {
    throw "SHA-256 mismatch. Do not install this download."
}
"SHA-256 verified: $actual"
```

The expected and actual hashes must match exactly. Delete and download both files
again if verification fails; do not bypass a mismatch.

### From a Cloned Repo

Source builds require Windows 10/11 x64, Git, PowerShell, network access for pinned
runtime artifacts, and enough free disk space for the download cache and bundle.
The installer attempts to install `uv` with `winget` or user-level pip when needed.
Building is substantially slower than installing a published bundle.

```powershell
# 1) Clone the repo and enter its root.
# 2) Build the portable bundle and install its user shim:
.\install.cmd
```

The root command delegates to
`tools\windows_portable\install-from-source.cmd`, builds
`dist\frame-compare-portable-win-x64`, and installs the same user-level shim as a
release bundle. After either route, open a new terminal so the updated user `PATH`
is loaded.

---

## Directory Layout

Source installs and portable bundle builds create empty `config/` and
`comparison_videos/` directories in the bundle root.

- Put an existing `config.toml` at `config/config.toml`.
- Drop input clips under `comparison_videos/` if you want to use defaults without
  passing explicit `--config` or `--input` paths.

For the installed `frame-compare` command, a bundle-local `config/config.toml`
takes precedence over the AppData fallback config.

The default generated-data location is the bundle's `generated/` directory. In the
wizard, set **Generated data location** to a normal folder outside the bundle when
you want reports, screenshots, run state, and reusable caches to survive bundle
replacement. The selected authored value is retained in the installed fallback
`%LOCALAPPDATA%\Programs\FrameCompare\state\config.toml`; the shim injects that
same file for `wizard`, `run`, `preset`, and `history` commands whenever the
fallback is selected. A top-level bundle `screenshots/` directory is not a runtime
output root.

The same selected configuration drives `run --diagnose-paths`, run execution, and
both history commands, so they agree on the external generated-data root.

When using `.\tools\windows_portable\install-from-source.cmd`, the bundle root is
`dist/frame-compare-portable-win-x64` (not the repository root). Put your config
at `dist/frame-compare-portable-win-x64/config/config.toml` and videos under
`dist/frame-compare-portable-win-x64/comparison_videos/`.

### Release Inventory and Corresponding Source

Every built bundle contains `bundle_inventory.json`, a deterministic
machine-readable record of:

- the Frame Compare version, exact source commit, `GPL-3.0-only` license, and
  corresponding source archive;
- every installed Python distribution with its exact version and declared
  license metadata;
- each manifest-provided runtime artifact with its binary hash, license, and
  exact source location;
- every copied license or notice path and SHA-256;
- the requirements-lock fingerprint and the build/install scripts available at
  the recorded source commit.

Human-readable exact source pointers are also included at
`licenses/SOURCE_URLS.txt`, and the component summary is at
`licenses/THIRD_PARTY_NOTICES.txt`. PyQt6 and Qt license copies are retained in
dedicated `licenses/PyQt6/`, `licenses/PyQt6-sip/`, and `licenses/Qt/`
directories in addition to the complete Python distribution license inventory.

The selected component profile and compatibility policy are maintained in
[Supported Media Runtime](supported-media-runtime.md) and calculated by
`frame_compare.vs.runtime_contract`. Immutable artifact bytes, SHA-256 values,
source revisions, source-tree digests, and license evidence remain authoritative in
the build manifest, `Dockerfile`, and generated bundle inventory; the selected
profile does not substitute for that artifact-level evidence.
`bundle_info.json` and `bundle_inventory.json` also record the full coordinated
media-runtime fingerprint used by diagnostics and code-only update compatibility
checks.

---

## First Comparison

1. Put at least two supported video files in the bundle's `comparison_videos/`
   directory. Supported extensions are `.mkv`, `.mp4`, `.avi`, `.m2ts`, and `.ts`
   (case-insensitive).
2. Open a new PowerShell terminal.
3. Create or review configuration interactively:

   ```powershell
   frame-compare wizard
   ```

4. Check the runtime. Optional or network warnings do not make doctor exit with a
   dependency error, but review them against the workflow you intend to use:

   ```powershell
   frame-compare doctor
   ```

5. Validate paths, discovered filenames, selection intent, and output intent without
   side effects:

   ```powershell
   frame-compare run --dry-run
   ```

6. Run the comparison:

   ```powershell
   frame-compare run
   ```

Generated run folders and reports are written beneath the bundle's `generated/`
directory by default. Inspect recorded runs with:

```powershell
frame-compare history list
frame-compare history open <run-name>
```

When the generated-data location is external, the same canonical run-folder layout
is written there and the installed updater, rollback backups, reinstall flow, and
uninstaller leave it untouched. A bundle move can change cache identity for source
clips that moved with the bundle because their source paths changed; cache
validation remains authoritative and no cache-hit guarantee is made.

---

## Optional Dependencies

> [!NOTE]
> The portable **full bundle includes VSPreview + PyQt6** out of the box whether
> it came from a release or the source-build route. If you run the repository's
> Python environment directly instead of using the built portable bundle, install
> optional dependencies with:
> - `uv sync --group dev --extra vspreview --frozen`
> - or `pip install -e ".[vspreview]"`
>
> Then run `frame-compare doctor` to confirm interactive alignment dependencies
> are available.

---

## Updating a Portable Install

Apply a code-only update zip:

```powershell
frame-compare-update apply .\frame-compare-update-win-x64-<tag>.zip
```

The updater is offline-first and verifies the signature and every payload hash
before applying changes. A code-only ZIP replaces application files only; it does
**not** replace VapourSynth, L-SMASH-Works, vs-placebo, FFmpeg, runtime manifests,
or native license payloads.

The signed update manifest uses schema version 2 and requires the lowercase
64-character SHA-256 `expected_media_runtime_fingerprint` for the full runtime
scope. The installed full bundle must expose the same valid fingerprint in
`bundle_info.json`. A legacy schema-version-1 manifest, missing or malformed
fingerprint, or different runtime identity fails closed before any
dependency-compatibility override path. Install the complete portable ZIP for that
release when the fingerprint differs.

The R78-to-R79 / L-SMASH-Works 1296 / vs-placebo 2.0.4 refresh is a native-runtime
boundary. Existing R78 bundles require a full portable reinstall because the runtime
fingerprints change; applying only the code-only ZIP is deliberately refused. Keep
`paths.generated_dir` outside the bundle when reports, screenshots, history, and
reusable data must survive bundle
replacement.

Every published Windows release must contain exactly these mandatory assets, using
the release tag verbatim (for example `v0.1.0` or `v0.1.0-rc.1`):

- `frame-compare-portable-win-x64-<tag>.zip`
- `frame-compare-portable-win-x64-<tag>.zip.sha256`
- `frame-compare-update-win-x64-<tag>.zip`
- `frame-compare-update-win-x64-<tag>.zip.sha256`

RCs are always GitHub prereleases. Stable publication rejects RC versions/tags and
is protected by the repository's `production` environment. Dispatch the existing
**Windows portable** workflow with operation `release`; it calls the exact-commit
build and release boundaries. The release path builds, signs, verifies the
signature against the committed public key, and verifies these files before
creating a new draft. The draft is made public only after every remote SHA-256
digest matches the locally verified asset.

### Backup Management

```powershell
# List existing backups
frame-compare-update list-backups

# Roll back to a previous state
frame-compare-update rollback <backup-id>

# Clean old backups
frame-compare-update purge-backups --keep 5
```

---

## Uninstalling

Run `uninstall.cmd` from the current portable bundle root. This removes the installed
user shim and its managed PATH entry. It preserves the installed
`state/config.toml` byte-for-byte and leaves unknown files under the installed
`state`, `bin`, or root directories in place, so reinstalling reuses the existing
configuration. The uninstall does not silently delete the portable bundle or your
comparison files.

---

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `frame-compare` is not found after installation | Open a new terminal. If it remains unavailable, rerun `install.cmd` from the bundle's current location. |
| The shim says the bundle directory is missing | The portable folder moved after installation; rerun `install.cmd` from its new location. |
| `uv` installation fails during a source build | Install it with `winget install --id astral-sh.uv -e --source winget` or `py -m pip install --user uv`, then rerun `install.cmd`. |
| No videos are discovered | Put at least two supported clips in the bundle's `comparison_videos/` directory, or select another contained input directory in the wizard. |
| Doctor reports an optional/network warning | Review it against the intended workflow. Disabled integrations need no setup; FFmpeg-dependent workflows still require FFmpeg. |
| Configuration needs to be rebuilt | Run `frame-compare wizard`; confirmed writes use the installed fallback config unless a bundle-local config takes precedence. |
