# Proportional MVP security simplification

Status: Implementation complete. Integrated verification and review remain open.

The [implementation plan](IMPLEMENTATION_PLAN.md) records the current
requirements and verification matrix. This record captures the decisions
that changed the original design and the remaining handoff.

## Source and scope

- Branch `dev/mvp-security-hardening`, based on `origin/v0.7.0` at
  `1ad19886efc1424a9e475a52f156c86f5013782a`.
- Rebased security head before simplification
  `34b7c5da0be04f9424534517b71b1bbd66f52031`.
- PR #173 targets `v0.7.0`. The orchestrator owns integration, the PR update
  and final acceptance. This task ends at PR review.

## S1 — Cache the complete media geometry proof

Implemented in `dca6af39`.

A header-only check was considered for all opens. A real mixed-resolution H.264
transport stream reproduced a native L-SMASH heap abort when admitted without
complete frame validation. Cold and private cache-free opens, including the
VSView fallback, therefore retain a bounded scan of coded and visible geometry.
Each open still begins with a bounded header probe.

Warm managed L-SMASH opens reuse a proof only when the source identity, geometry
policy version, ffprobe identity and runtime facts, native runtime token and
index digest match under the cache lease. The managed index transaction, owned
decoder-side pixel limits and shared canvas policy remain in force. See the
[cache and admission contract](../../current-architecture.md#shared-caches-and-decoder-indexes).

## S2 — Reconstruct and scan the portable artifact

Implemented in `01f4019b`.

The frozen lock and native archive pins define the inputs to the portable
runtime. Pinned uv installs the exact authenticated wheelhouse offline with
build hooks disabled. The source-only `anitopy` 2.1.1 uses a deterministic,
package-specific conversion that reads only approved package and metadata
files. The assembly preserves the Qt subset with WebEngine excluded, native
pins, licenses and project metadata. A fresh verifier reconstructs the tree
and compares the canonical ZIP bytes.

The artifact gate uses checksum-pinned Syft and Grype with scanner identity
checks, nonempty inventories and a fresh, bounded database. It refuses
suppressions, known exploited matches and high, critical or unknown severity.
The receipt binds the exact artifact, source commit, verification result and
scanner evidence. See the [release procedure](../../ENGINEERING_RUNBOOK.md#windows-portable-release-path-verification).

## S3 — Simplify application process ownership

Implemented in `4b7d084f`.

The Windows launcher uses normal `Popen` followed by immediate assignment to
a preconfigured kill-on-close Job Object. Descendants can escape in the brief
pre-assignment interval. An interrupt inside `Popen` can prevent it from
returning a child handle for cleanup. The owner preserves bounded cleanup,
including job-owned descendants after leader exit, as well as separate output
limits and credential filtering. POSIX uses process groups. See
[external boundaries](../../current-architecture.md#external-boundaries).

## S4 — Integration and review

The report, implementation contract, runbook, architecture, security policy
and changelog reflect S1–S3. The orchestrator runs the applicable integrated
checks and reviews the complete diff before updating PR #173. Hosted Windows
reproduction and signing, and physical Windows runtime acceptance, remain
separate release gates. Further active adversarial exercises remain outside
the authorized scope.
