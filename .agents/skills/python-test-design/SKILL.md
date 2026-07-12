---
name: python-test-design
description: Use when changing Frame Compare pytest coverage, fixtures, CLI tests, mocks, property tests, subprocess tests, or runtime-boundary verification.
---

# Python Test Design

Test stable behavior and public seams. Add a regression/contract test when a real
failure or public contract needs protection; otherwise prefer existing coverage plus
focused proof. Keep fixtures local and explicit, use `tmp_path` for filesystem state,
and mock external boundaries rather than owned internals.

For CLI contracts assert exit code and separate stdout/stderr; parse JSON output.
Bound subprocess and network behavior with realistic timeouts. Use property tests only
for genuine input domains. Avoid giant snapshots, private probes, implementation-
restating tests, and concurrent `CliRunner` calls.
