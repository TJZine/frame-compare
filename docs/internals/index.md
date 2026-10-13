---
title: Internals
description: Contracts, architecture, runbooks, and validation records for people who maintain Frame Compare.
---

# Overview

These pages are for people who change Frame Compare. They state the exact behavior the
code must keep, how the project is built and released, and the evidence behind past
decisions. To use Frame Compare, start with
[Choose an installation](../getting-started/index.md).

<div class="fc-cards" markdown>

- [CLI behavioral contract](../current-cli-contract.md)

    Streams, JSON documents, persistence, and exit codes, stated exactly.

- [Current architecture](../current-architecture.md)

    Modules, ownership, and data flow.

- [Supported media runtime](../supported-media-runtime.md)

    Every component version and the reason it was selected.

- [Engineering runbook](../ENGINEERING_RUNBOOK.md)

    Commands, checks, and procedures for development and release.

- [Physical Windows runtime validation](../media-runtime-windows-validation.md)

    The acceptance checklist for the Windows bundle on real hardware.

- [Analysis performance validation](../analysis-performance-validation.md)

    How analysis performance is measured.

- [Analysis benchmark history](../analysis-benchmark-history.md)

    Recorded benchmark results.

- [Historical decisions](../DECISIONS.md)

    Why past design choices were made.

</div>

Contributing guidelines are in
[`CONTRIBUTING.md`](https://github.com/TJZine/frame-compare/blob/main/CONTRIBUTING.md).
