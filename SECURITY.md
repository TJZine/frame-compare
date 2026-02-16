# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

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

- **Path Traversal**: All file operations are contained within the workspace root
- **Subprocess Hardening**: External tool invocations (FFmpeg, VapourSynth) use validated arguments
- **Network Operations**: Optional slow.pics/TMDB integrations follow SSRF prevention policies

For implementation details, see:

- [Decisions](docs/DECISIONS.md)

## Security-Related Error Codes

| Code    | Description                                          |
| ------- | ---------------------------------------------------- |
| FC-3009 | Path escapes workspace root (path traversal blocked) |
| FC-3012 | Invalid path format                                  |
| FC-3xxx | Security-related errors                              |
