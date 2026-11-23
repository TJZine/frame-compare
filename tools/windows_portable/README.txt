Frame Compare - Portable Edition
================================

INSTALL (enables `frame-compare` globally for current user):
  1. Extract the complete ZIP into a fresh, empty folder, then run `install.cmd`
     from the portable bundle root. Windows PowerShell 5.1 and PowerShell 7 are supported.
  2. Open a new terminal.
  3. Run: frame-compare --help

UNINSTALL:
  Run `uninstall.cmd` from the portable bundle root.
  If uninstall reports state\source-migration.pending.json, follow the recovery steps:
    https://tjzine.github.io/frame-compare/getting-started/windows-portable/#recover-a-pending-migration

NOTES:
  - Installation uses a shim under:
      %LOCALAPPDATA%\Programs\FrameCompare\bin
  - Shim state/config is stored under:
      %LOCALAPPDATA%\Programs\FrameCompare\state\config.json
  - Installed-shim fallback config is stored at:
      %LOCALAPPDATA%\Programs\FrameCompare\state\config.toml
  - To override config for a run, pass:
      frame-compare run --config <path-to-config.toml>
  - Bundle defaults include empty:
      .\config\
      .\comparison_videos\
    When .\config\config.toml exists in the bundle, the installed `frame-compare`
    command uses it before the AppData fallback config. Source clips can go under
    .\comparison_videos\.
  - The default generated-data location is .\generated\. Use the wizard's
    "Generated data location" prompt to select a normal folder outside the bundle
    when reports, screenshots, run state, and caches must survive bundle replacement.
    Run diagnostics, execution, and history use the same selected location. The
    installer and uninstaller leave that external data in place. A moved bundle can change cache identity for source clips moved
    with it because their source paths changed.
  - Source builds require PowerShell 7 or newer before bootstrap or output changes.
    For source builds (`tools\windows_portable\install-from-source.cmd`), use:
      .\dist\frame-compare-portable-win-x64-<yyyyMMdd-HHmmss>Z\
    as the bundle root (UTC timestamp, not the repository root). Every source
    reinstall builds and verifies a fresh bundle before activating it. The shim
    always uses the active bundle recorded in AppData, regardless of your cwd.
    Non-empty config\, comparison_videos\, and generated\ folders move from the
    previous active bundle by default. Use install.cmd -UserData Leave to opt out;
    the folders then remain in the old bundle, and the shim may select an older
    AppData fallback config if the new bundle has no config\config.toml.
    The source installer holds the exclusive activation lock during the build
    and activation. After building, it re-reads the active-pointer byte snapshot
    under that lock. Current bundle installers use the same lock and report its
    path and retry instructions if the lock is held. A leftover lock file is
    harmless once its process handle closes.
    Builder and source-install paths with junction/symlink/mount-point ancestry
    are refused because lexical containment cannot prove their physical location.
    Use physical paths. Drive-relative and root-relative stored pointers are invalid.
    Move requires same-volume renames. Failed moves or activation reverse the
    moves and restore the previous pointer/shims; a recovery failure reports all
    remaining paths for manual repair without deleting user folders.
    Moving media makes path-keyed caches recompute once; absolute config paths
    are not rewritten. Old bundles are never deleted: remove them manually only
    after accepting the new installation.
    The direct builder refuses occupied or unsafe output folders. Maintainers
    must explicitly remove disposable build output before reusing its path.
  - Extract the complete portable ZIP into a fresh, empty folder and run
    install.cmd. Overlaying a full ZIP onto an existing bundle root is
    unsupported. The installer moves non-empty config\, comparison_videos\,
    and generated\ folders from the previous active bundle. Run
    install.cmd -UserData Leave to keep the folders in the old bundle or to copy
    selected user files yourself. AppData fallback configuration and external
    data stay in place. The previous bundle retains its application and runtime.
  - If the bundle is moved, run `install.cmd` again from the new location.

QUICK START:
  1. Put at least two supported video files under .\comparison_videos\.
     Supported extensions: .mkv, .mp4, .avi, .m2ts, and .ts.
  2. Open a new terminal after installation.
  3. Run these commands in order:
     frame-compare wizard
     frame-compare doctor
     frame-compare run --dry-run
     frame-compare run

  Optional or network doctor warnings do not make doctor exit with a dependency
  error, but review them against the workflow you intend to use.

RUN HISTORY:
  frame-compare history list
  frame-compare history open <run-name>

OPTIONAL (Native VSView Alignment Review):
  The full portable bundle includes VSView + PySide6 + the native Frame Compare
  alignment-review panel. Frame Compare and VSView run from the same bundled Python
  environment; a PATH-only VSView executable is unsupported. If you set:
    [audio_alignment]
    use_vsview = true
  native panel review can run out of the box.
  If you run the repository's Python environment directly instead of using the
  built portable bundle, install optional deps with:
    uv sync --group dev --extra vsview --frozen
  or:
    pip install -e ".[vsview]"
  The hosted Windows release build is required to discover and load the exact panel
  entry point, construct it offscreen, start the managed VSView launcher against a
  generated three-output session (Reference, Comparison 1, and Comparison 2), require metadata/result round-trip plus
  script/load/frame-0 evidence, and terminate it after the expected steady-state GUI
  timeout. This is a native runtime gate, not a substitute for later visible-UI
  acceptance on Windows; no hosted result is claimed by this local proof.

REACTIVATING AN EARLIER BUNDLE:
  Run install.cmd from the bundle you want to use. Installers from version
  0.7.0 onward move the same user folders back by default. An older installer
  restores its own app and legacy update command. The moved folders stay in
  the newer bundle, where you can find them to copy back manually.

THIRD-PARTY LICENSES / SOURCE AVAILABILITY:
  - The build outputs:
      .\licenses\
      .\licenses\python\
      .\bundle_inventory.json
  - Python wheel license files are copied from installed *.dist-info metadata.
  - Third-party runtime licenses that do not reliably ship in extracted bundle
    paths are copied from manifest-declared, repo-tracked files under:
      tools\windows_portable\licenses\
    The build SHA256-verifies those vendored license texts before copying them
    into the bundle.
  - PySide6/Qt LGPL-3.0 notices are copied from manifest-declared, SHA256-verified
    repository files. Wheel-specific notices under *.dist-info\licenses are
    copied as well.
  - VSView plays audio through Qt Multimedia's native Windows backend. The
    portable deployment excludes Qt's FFmpeg plugin and DLLs and the unused Qt
    WebEngine/Chromium runtime files. It includes the standalone BtbN FFmpeg
    executable.
  - Deterministic component versions, declared license metadata, copied
    license/notice hashes, requirements-lock fingerprint, exact Frame Compare
    source commit/archive, and build/install script inventory are shipped in:
      .\bundle_inventory.json
  - Exact-version/commit source pointers are shipped in:
      .\licenses\SOURCE_URLS.txt
  - A human-readable component summary is shipped in:
      .\licenses\THIRD_PARTY_NOTICES.txt

DOCUMENTATION:
  https://github.com/TJZine/frame-compare
