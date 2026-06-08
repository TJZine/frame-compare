# Windows Portable Install

> [!TIP]
> **The Windows portable bundle is the most complete distribution of Frame Compare.**
> It ships VSPreview + PyQt6 for interactive manual alignment, GPU-accelerated
> tonemapping via the host Vulkan stack, and the native installer/update flow.
> The default Docker path does not include any of these.

---

## Quick Install

### From a GitHub Release Zip (Recommended)

```powershell
# 1) Download frame-compare-portable-win-x64-<tag>.zip from the GitHub Release
# 2) Extract it
# 3) From the extracted folder:
.\install.cmd
```

### From a Cloned Repo

```powershell
# 1) Clone the repo
# 2) From the repo root:
.\install.cmd
```

### Advanced / Legacy (Source Build)

```powershell
.\tools\windows_portable\install-from-source.cmd
```

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

## Optional Dependencies

> [!NOTE]
> The portable **full bundle includes VSPreview + PyQt6** out of the box.
> For source-based installs, install optional dependencies with:
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
