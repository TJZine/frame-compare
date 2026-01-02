---
name: fc2-security
description: Use when implementing or reviewing security-sensitive code in Frame Compare (path containment, subprocess args, SSRF policy, secret handling, and error-code invariants).
---

# FC-2.0 Security Skill

## Canonical references

- Error codes registry (SSOT): `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml`
- Workflow STOP rules (read first): `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md`
- Full workflow SSOT: `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`

## Security invariants checklist

- Path traversal containment: all filesystem writes/deletes under an explicit root; reject `..`, absolute escapes, and symlink escapes.
- Subprocess hardening: no `shell=True`; validate/normalize args; reject control chars.
- SSRF: explicit allowlist for outbound requests; prohibit localhost/private IP ranges unless explicitly required.
- Secrets: never log tokens; redact in errors; ensure tests cover redaction.
- Error taxonomy: use existing FC codes; don’t invent new ones.

## Deliverables for a security change

- Targeted tests (negative cases included)
- Verification commands + outputs (per run artifacts)
