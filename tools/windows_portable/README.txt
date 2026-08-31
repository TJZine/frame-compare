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
  - For source builds (`tools\windows_portable\install-from-source.cmd`), use:
      .\dist\frame-compare-portable-win-x64\
    as the bundle root (not the repository root).
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
  generated two-output session, require metadata/result round-trip plus
  script/load/frame-0 evidence, and terminate it after the expected steady-state GUI
  timeout. This is a native runtime gate, not a substitute for later visible-UI
  acceptance on Windows; no hosted result is claimed by this local proof.

UPDATING (Code-Only Update Package):
  Apply an update zip:
    frame-compare-update apply .\frame-compare-update-win-x64-0.1.1.zip

  List and restore backups:
    frame-compare-update list-backups
    frame-compare-update rollback <backup-id>
    frame-compare-update purge-backups --keep 5

  Safety behavior:
    - Signature verification defaults to Cancel when missing/invalid.
    - Pre-native-panel bundles with bundle_info schema_version 2 are refused and
      require a complete portable reinstall; there is no bypass.
    - Dependency fingerprint mismatch always refuses a code-only update and requires
      a complete portable reinstall; there is no bypass.
    - Non-interactive sessions fail safely instead of prompting.

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
    pwsh -File .\tools\windows_portable\build_update.ps1 -BundleDir .\dist\frame-compare-portable-win-x64 -OutFile .\dist\frame-compare-update-win-x64-0.1.1.zip
    $env:SIGNING_KEY_XML_PATH = "<secure-private-key.xml>"
    pwsh -File .\tools\windows_portable\sign_update.ps1 -UpdateZip .\dist\frame-compare-update-win-x64-0.1.1.zip -ExpectedPublicKeyPath .\tools\windows_portable\update_public_key.xml

    CI guidance:
      - Prefer injecting the signing key path via a masked secret into SIGNING_KEY_XML_PATH.
      - Avoid passing the key path on the command line to reduce exposure in shell history / process listings.
      - GitHub release/manual bundle workflow signs the code-only update zip when the
        WINDOWS_UPDATE_SIGNING_KEY_XML secret exists only in the approved
        release-candidate and production environments.

  Unsigned zips are for local/dev only and require unsafe confirmation in the updater.
  That confirmation never bypasses the media-runtime fingerprint boundary: a
  code-only update with a missing, legacy, malformed, or different native runtime
  fingerprint is refused and requires a complete portable bundle reinstall.

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
