Frame Compare - Portable Edition
================================

INSTALL (enables `frame-compare` globally for current user):
  1. Extract the complete ZIP into a fresh, empty folder, then run `install.cmd`
     from the portable bundle root. Windows PowerShell 5.1 and PowerShell 7 are supported.
  2. Open a new terminal.
  3. Run: frame-compare --help

UNINSTALL:
  Run `uninstall.cmd` from the portable bundle root.

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
    installed updater, rollback, reinstall, and uninstall never manage that
    external data. A moved bundle can change cache identity for source clips moved
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
    After building, the installer re-reads one active-pointer byte snapshot under
    an exclusive activation lock, so another completed installation is respected.
    Current bundle installers use the same lock; overlapping activation refuses
    with the lock path and retry instructions. A leftover lock file is harmless
    once its process handle closes. The build itself does not hold this lock.
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
  - A complete runtime reinstall requires a fresh, empty folder. Overlaying a full
    ZIP onto an existing bundle root is unsupported. Preserve user configuration,
    input clips, and generated data; copy only those user files to the new bundle
    if they were bundle-local. AppData fallback configuration and external data
    remain preserved. Do not copy application/runtime files or old update backups.
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

UPDATING (Code-Only Update Package):
  Apply an update zip:
    frame-compare-update apply .\frame-compare-update-win-x64-0.7.0.zip

  List and restore backups:
    frame-compare-update list-backups
    frame-compare-update rollback <backup-id>
    frame-compare-update purge-backups --keep 5

  Safety behavior:
    - Each backup has compatibility.json (media-runtime and requirements-lock identity)
      and backup.json (schema, app version, exact source-file paths/sizes/SHA-256).
      backup.json is written last beside frame_compare\ as the completeness marker.
      list-backups marks missing/invalid/mismatched identity or incomplete inventories
      unavailable; rollback refuses them before creating its update lock. Legacy
      backups missing either record cannot be restored or migrated. Backup IDs must
      be fresh. Failed backup copies are removed; purge retains five complete,
      compatible backups, so incomplete backups cannot displace usable ones.
    - Stable/RC grammar is MAJOR.MINOR.PATCH or MAJOR.MINOR.PATCHrcN (ASCII digits,
      no leading zeroes, N >= 1, components at most nine digits). RCs precede their
      final release. Updates stay in the signed minimum's major.minor line. A stable
      minimum admits its base's RCs; an RC minimum uses strict ordering; max is
      inclusive. Same-line stable-to-RC updates and downgrades remain allowed when
      the signed installed-version range admits them. The target smoke check must
      report exactly the target version, with a successful launcher.
    - Both apply and rollback use one stage/verify/rename/smoke/commit transaction.
      app\.frame_compare_replacement.json records staging/promoting/committed with
      atomic replacement. The next apply or rollback repairs interrupted work under
      the update lock before reading the installed version. The lock file stays
      in place; only its exclusive process handle owns the lock, so retry works
      immediately after a terminated updater releases that handle. Unjournaled .old/.new
      trees are refused with paths. Recovery failures retain trees and the journal
      with manual-repair guidance. Failed promoted trees remain as
      app\src\frame_compare.failed-*; a successful commit keeps only the newest.
    - The updater/helper in the AppData bin folder is replaced only by a full bundle
      installation, never by a code-only ZIP. Existing RC installs with the old
      updater need one full bundle reinstall to obtain RC support and safe rollback.
      Install into a fresh folder and preserve user data; never overlay a runtime.
    - Signature verification is mandatory. Missing or invalid signatures are always
      refused; the updater has no interactive unsigned bypass.
    - Archive processing is bounded before extraction by compressed size, entry count,
      per-entry and total uncompressed size, and compression-ratio limits.
    - If the installed app version cannot be established, the updater fails closed and
      requires a complete portable reinstall rather than skipping the signed range.
    - Pre-native-panel bundles with bundle_info schema_version 2 are refused and
      require a complete portable reinstall; there is no bypass.
    - Dependency fingerprint mismatch always refuses a code-only update and requires
      a complete portable reinstall; there is no bypass.

RELEASE SIGNING (Maintainers):
  One-time key generation is MAINTAINER-ONLY. Run it in a separate, ordinary
  PowerShell 7.3+ window. The private path must be an encrypted location outside the
  repository, task terminals, caches, and release artifacts:
    $keyId = "frame-compare-update-2026-01"
    pwsh -NoProfile -ExecutionPolicy Bypass `
      -File .\tools\windows_portable\generate_update_keypair.ps1 `
      -PublicKeyPath .\tools\windows_portable\update_public_key.xml `
      -PrivateKeyPath "<encrypted-location-outside-the-repository>" `
      -KeyId $keyId `
      -KeySize 3072 `
      -ReplacePlaceholderPublicKey

    The generator refuses repository-contained or existing private outputs, replaces
    only the known public-key placeholder, applies a current-user-only private-file
    ACL on Windows or owner-read/write-only permissions on POSIX, and reports only
    public metadata and a public-key fingerprint.
    Commit only tools\windows_portable\update_public_key.xml. Never paste private
    XML into a command line, task, log, issue, PR, commit, or release artifact.

  Build + sign update zip:
    Run with pwsh (PowerShell 7+) on CI / modern Windows. Signing and verification use
    PKCS#1/SHA256 with RSA XML keys; the scripts import XML keys through cross-platform
    RSA parameters and keep a Windows PowerShell 5.1-compatible legacy fallback.
    pwsh -File .\tools\windows_portable\build_update.ps1 -BundleDir .\dist\frame-compare-portable-win-x64 -OutFile .\dist\frame-compare-update-win-x64-0.7.0.zip
    $env:SIGNING_KEY_XML_PATH = "<secure-private-key.xml>"
    pwsh -File .\tools\windows_portable\sign_update.ps1 -UpdateZip .\dist\frame-compare-update-win-x64-0.7.0.zip -ExpectedPublicKeyPath .\tools\windows_portable\update_public_key.xml

    CI guidance:
      - Prefer injecting the signing key path via a masked secret into SIGNING_KEY_XML_PATH.
      - Avoid passing the key path on the command line to reduce exposure in shell history / process listings.
      - GitHub release/manual bundle workflow signs the code-only update zip when the
        WINDOWS_UPDATE_SIGNING_KEY_XML secret exists only in the approved
        release-candidate and production environments.

  The updater does not apply unsigned zips, including local/development packages.
  Build-update refuses dirty application/version sources and packages committed HEAD,
  matching the source-selection rule used by the complete portable bundle builder. It
  also refuses a supplied full bundle whose app version or packaged application source
  differs from that commit before borrowing the bundle's compatibility fingerprints.

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
  - PySide6/Qt LGPL-3.0 and Qt-bundled FFmpeg LGPL notices are copied from
    manifest-declared, SHA256-verified repository files. Wheel-specific notices
    under *.dist-info\licenses are copied as well.
  - VSView requires Qt Multimedia from PySide6 Addons. The portable deployment
    excludes unused Qt WebEngine/Chromium files and verifies their absence; it does
    not claim to distribute those excluded components.
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
