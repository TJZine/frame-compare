Frame Compare - Portable Edition
================================

INSTALL (enables `frame-compare` globally for current user):
  1. Run `install.cmd` from the portable bundle root.
  2. Open a new terminal.
  3. Run: frame-compare --help

UNINSTALL:
  Run `uninstall.cmd` from the portable bundle root.

NOTES:
  - Installation uses a shim under:
      %LOCALAPPDATA%\Programs\FrameCompare\bin
  - Shim state/config is stored under:
      %LOCALAPPDATA%\Programs\FrameCompare\state\config.json
  - Default portable config is stored at:
      %LOCALAPPDATA%\Programs\FrameCompare\state\config.toml
  - To override config for a run, pass:
      frame-compare run --config <path-to-config.toml>
  - Bundle defaults include empty:
      .\config\
      .\comparison_videos\
    Put config at .\config\config.toml and source clips under .\comparison_videos\.
  - For source builds (`tools\windows_portable\install-from-source.cmd`), use:
      .\dist\frame-compare-portable-win-x64\
    as the bundle root (not the repository root).
  - If the bundle is moved, run `install.cmd` again from the new location.

QUICK START:
  frame-compare wizard
  frame-compare doctor
  frame-compare run

DOCUMENTATION:
  https://github.com/TJZine/frame-compare
