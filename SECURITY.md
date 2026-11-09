# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.7.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in Frame Compare, please report it responsibly.

### How to Report

1. Use [GitHub's private vulnerability report form](https://github.com/TJZine/frame-compare/security/advisories/new)
   if available, or email **<zine96@proton.me>**. Keep the report private.
2. Redact credentials, webhook URLs, private media, and unrelated personal paths.
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

- **Path boundaries.** Media may be read from outside the workspace. The selected
  config file and `paths.config_dir` must resolve inside the workspace after
  symlink resolution. The installed Windows shim may also select its exact
  `%LOCALAPPDATA%/Programs/FrameCompare/state/config.toml` fallback. Redirected
  fallback paths are rejected. Run folders, durable source indexes, other caches
  and reports stay inside the resolved generated-data root. Preset writes have
  their own workspace policy. Frame Compare's managed loader treats all
  media-adjacent L-SMASH-Works indexes as inert. See the
  [source-index boundary](docs/current-architecture.md#shared-caches-and-decoder-indexes).
- **Native media admission.** Cold and cache-free L-SMASH-Works opens validate
  coded and visible frame dimensions with a bounded scan. Warm managed opens
  reuse that proof only when the source, probe, policy, runtime and index still
  match. See the [source admission rules](docs/current-architecture.md#shared-caches-and-decoder-indexes).
- **Subprocess hardening.** External tool invocations use argument vectors,
  independent stdout/stderr limits and bounded timeouts. Application children
  receive only the credentials their specific integration owns. The Windows
  launch and assignment limits are described under
  [external boundaries](docs/current-architecture.md#external-boundaries).
- **Network Operations**: slow.pics upload and webhook delivery are opt-in, and TMDB lookups run only when an API key is configured. Webhook delivery requires an external HTTPS endpoint, follows no redirects, and keeps the URL out of diagnostics.
- **Release integrity.** The Windows release path independently rebuilds and
  compares the portable ZIP, scans the verified artifact before signing the
  canonical update manifest, and separates signing from publication. See the
  [final-artifact gate](docs/ENGINEERING_RUNBOOK.md#final-artifact-security-evidence).

For implementation details, see [Current architecture](docs/current-architecture.md).

For a suspected update-signing key compromise, report it privately and follow the
[signer compromise response](docs/ENGINEERING_RUNBOOK.md#signer-compromise-response).

## Security-Related Error Codes

| Code    | Description                                          |
| ------- | ---------------------------------------------------- |
| FC-3009 | Path escapes its permitted root (blocked) |

All error families and exit codes are listed in the [CLI contract](docs/current-cli-contract.md#exit-codes-and-error-families).
