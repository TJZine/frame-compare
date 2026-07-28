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

OPTIONAL (Interactive Audio Alignment / VSPreview):
  The full portable bundle includes VSPreview + PyQt6. If you set:
    [audio_alignment]
    use_vspreview = true
  interactive alignment can run out of the box.
  If you run the repository's Python environment directly instead of using the
  built portable bundle, install optional deps with:
    uv sync --group dev --extra vspreview --frozen
  or:
    pip install -e ".[vspreview]"

UPDATING (Code-Only Update Package):
  Apply an update zip:
    frame-compare-update apply .\frame-compare-update-win-x64-0.1.1.zip

  List and restore backups:
    frame-compare-update list-backups
    frame-compare-update rollback <backup-id>
    frame-compare-update purge-backups --keep 5

  Safety behavior:
    - Signature verification defaults to Cancel when missing/invalid.
    - Dependency fingerprint mismatch defaults to Cancel.
    - Unsafe apply paths require explicit typed confirmation.
    - Non-interactive sessions fail safely instead of prompting.

RELEASE SIGNING (Maintainers):
  One-time key generation is MAINTAINER-ONLY. Run it in a separate, ordinary
  PowerShell 7 window. The private path must be an encrypted location outside the
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
    ACL on Windows, and reports only public metadata and a public-key fingerprint.
    Commit only tools\windows_portable\update_public_key.xml. Never paste private
    XML into a command line, task, log, issue, PR, commit, or release artifact.

  Build + sign update zip:
    Run with pwsh (PowerShell 7+) on CI / modern Windows. Signing and verification use
    PKCS#1/SHA256 with RSA XML keys; the scripts import XML keys through cross-platform
    RSA parameters and keep a Windows PowerShell 5.1-compatible legacy fallback.
    pwsh -File .\tools\windows_portable\build_update.ps1 -BundleDir .\dist\frame-compare-portable-win-x64 -OutFile .\dist\frame-compare-update-win-x64-0.1.1.zip
    $env:SIGNING_KEY_XML_PATH = "<secure-private-key.xml>"
    pwsh -File .\tools\windows_portable\sign_update.ps1 -UpdateZip .\dist\frame-compare-update-win-x64-0.1.1.zip

    CI guidance:
      - Prefer injecting the signing key path via a masked secret into SIGNING_KEY_XML_PATH.
      - Avoid passing the key path on the command line to reduce exposure in shell history / process listings.
      - GitHub release/manual bundle workflow signs the code-only update zip when the
        WINDOWS_UPDATE_SIGNING_KEY_XML repository secret contains the private key XML.

  Unsigned zips are for local/dev only and require unsafe confirmation in the updater.

THIRD-PARTY LICENSES / SOURCE AVAILABILITY:
  - The build outputs:
      .\licenses\
      .\licenses\python\
  - Python wheel license files are copied from installed *.dist-info metadata.
  - Third-party runtime licenses that do not reliably ship in extracted bundle
    paths are copied from manifest-declared, repo-tracked files under:
      tools\windows_portable\licenses\
    The build SHA256-verifies those vendored license texts before copying them
    into the bundle.
  - Qt license/notice files (when present) are copied from:
      app\site-packages\PyQt6\Qt6\licenses
    Note: newer PyQt6 wheels may ship additional license texts under individual
    wheel *.dist-info\licenses directories;
    the build script copies dist-info license directories when present.
  - Source pointers are shipped in:
      .\licenses\SOURCE_URLS.txt
    (Qt, FFmpeg, VapourSynth upstream source locations)

DOCUMENTATION:
  https://github.com/TJZine/frame-compare
