# Windows installation

See the canonical [Windows portable guide](docs/getting-started/windows-portable.md) for release
and source installation, portable directory layout, optional dependencies,
first-run commands, ZIP reinstall, uninstalling, and troubleshooting.

Source builds require PowerShell 7 or newer. Published bundles support Windows
PowerShell 5.1 and PowerShell 7 for installation and launch.

To update, close running comparisons and extract the complete ZIP into a fresh,
empty folder. Run the new bundle's `install.cmd` while the old bundle is still
active. It moves your bundle-local config, sources, and generated data by default.
See the [same-volume and empty-folder requirements](docs/getting-started/windows-portable.md#update-behavior).
Use `install.cmd -UserData Leave` to keep those folders in the old bundle.
