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

When using `.\tools\windows_portable\install-from-source.cmd`, the bundle root is
`dist/frame-compare-portable-win-x64` (not the repository root). Put your config
at `dist/frame-compare-portable-win-x64/config/config.toml` and videos under
`dist/frame-compare-portable-win-x64/comparison_videos/`.

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
frame-compare-update apply .\frame-compare-update-win-x64-0.1.1.zip
```

The updater is offline-first and verifies signature + file hashes before applying
changes. If dependency fingerprints do not match, the default action is cancel;
unsafe apply requires explicit confirmation.

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
user shim; it does not silently delete the portable bundle or your comparison files.

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
