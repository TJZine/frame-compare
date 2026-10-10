# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.6.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in Frame Compare, please report it responsibly.

### How to Report

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Email security concerns to: **<zine96@proton.me>**
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: Within 48 hours of your report
- **Initial Assessment**: Within 1 week
- **Resolution Timeline**: Depends on severity, typically 30-90 days

### Security Considerations

Frame Compare handles local video files and optional network operations. Key security areas include:

- **Path Boundaries**: Media inputs may be read from outside the workspace. The selected config file and `paths.config_dir` must resolve inside the workspace root after symlink resolution. `paths.generated_dir` may name an external directory, and every run folder, cache, and report Frame Compare writes stays inside that resolved generated-data root. Outside it, Frame Compare writes only the selected config file (inside the workspace root), preset files under `<root>/config/presets` (`preset save` follows a user-authored symlink there), and its own L-SMASH-Works `.lwi` index beside each media file. The only selected-config exception is the
  installed Windows portable shim's exact
  `%LOCALAPPDATA%/Programs/FrameCompare/state/config.toml` fallback; a symlinked
  fallback that resolves elsewhere is rejected.
- **Subprocess Hardening**: External tool invocations (FFmpeg, VapourSynth) use validated arguments
- **Network Operations**: slow.pics upload and webhook delivery are opt-in, and TMDB lookups run only when an API key is configured. Webhook delivery requires an external HTTPS endpoint, follows no redirects, and keeps the URL out of diagnostics.

For implementation details, see [Current architecture](docs/current-architecture.md).

## Security-Related Error Codes

| Code    | Description                                          |
| ------- | ---------------------------------------------------- |
| FC-3009 | Path escapes its permitted root (blocked) |

All error families and exit codes are listed in the [CLI contract](docs/current-cli-contract.md#exit-codes-and-error-families).
