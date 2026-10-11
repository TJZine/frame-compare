# Windows Installation

See the canonical [Windows Portable Guide](docs/windows-portable.md) for release
and source installation, portable directory layout, optional dependencies,
first-run commands, updates, backups, rollback, uninstalling, and troubleshooting.

Source builds require PowerShell 7 or newer. Published-bundle installation, launch,
and updates support Windows PowerShell 5.1 as well as PowerShell 7.

Install a complete portable ZIP into a fresh, empty folder; overlaying it onto an
existing bundle root is unsupported. Preserve user configuration and data as described
in the guide before pointing the installed shim at the new bundle.
