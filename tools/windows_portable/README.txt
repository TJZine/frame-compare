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

OPTIONAL (Interactive Audio Alignment / VSPreview):
  The full portable bundle includes VSPreview + PyQt6. If you set:
    [audio_alignment]
    use_vspreview = true
  interactive alignment can run out of the box.
  For source installs, install optional deps:
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
  One-time key generation (private key must stay out-of-repo):
    - Generate RSA keypair (PKCS#1/SHA256 compatible with PowerShell 5.1).
    - Commit only the public key XML at:
        tools\windows_portable\update_public_key.xml
    - Record key_id and generation date in release notes.

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

  Unsigned zips are for local/dev only and require unsafe confirmation in the updater.

THIRD-PARTY LICENSES / SOURCE AVAILABILITY:
  - The build outputs:
      .\licenses\
      .\licenses\python\
  - Python wheel license files are copied from installed *.dist-info metadata.
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
