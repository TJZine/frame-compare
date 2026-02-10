# Windows Install (Recommended)

## From GitHub Release zip

1. Download the Windows release zip.
2. Extract the zip.
3. From the extracted folder, run:

```powershell
.\install.cmd
```

## From cloned repo

1. Clone this repository.
2. From the repository root, run:

```powershell
.\install.cmd
```

## Troubleshooting: uv install failure

If `uv` is still not available on `PATH`, run one of these commands and then re-run `.\install.cmd`:

```powershell
winget install --id astral-sh.uv -e --source winget
py -m pip install --user uv
```
