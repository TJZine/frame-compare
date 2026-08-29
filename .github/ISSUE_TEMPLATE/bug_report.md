---
name: Bug report
about: Report reproducible incorrect or unexpected behavior
title: "[Bug]: "
labels: ["bug", "triage"]
assignees: ''
---

## Summary

Describe the observed problem and its impact.

## Environment

- **Operating system and version**:
- **Frame Compare version**:
- **Installation route**: Windows portable / Docker / native uv / native pip
- **Python version** (native routes):
- **Relevant media runtime** (native routes):
- **Command and exit code**:

## Steps to reproduce

1.
2.
3.

Include the smallest publication-safe fixture or source properties that reproduce the
problem when possible.

## Expected behavior

Describe the result you expected.

## Actual behavior

Describe what happened instead.

## Diagnostics

Paste sanitized output from the same route used to run the comparison:

```text
frame-compare doctor
frame-compare run --dry-run
```

Use `doctor --json` when structured runtime identity is useful. Redact usernames,
private paths, source names, webhook URLs, API keys, tokens, cookies, and unrelated
environment values.

## Logs or error output

```text
Paste the complete relevant error and warning context here.
```

## Screenshots or report evidence

Attach publication-safe screenshots only when they materially clarify the problem. Do
not upload private media frames without permission.

## Additional context

Include configuration fields relevant to the issue, whether caches were reused, and
whether the problem reproduces after a dry run or clean generated fixture.

## Checklist

- [ ] I searched existing issues for the same problem.
- [ ] I used a supported installation route or identified the unmanaged native setup.
- [ ] I included the exact Frame Compare version, command, and exit code.
- [ ] I included sanitized doctor output and the full relevant error.
- [ ] I removed secrets and unnecessary private data.
