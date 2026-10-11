---
search:
  exclude: true
---

# Decisions needed before dependent work

These are unresolved contract choices, not approval requests made during the read-only review. No option is approved and no fix has begun. Existing clear obligations are corrected in the draft packages without inventing new product decisions.

## D-01 — Interpreter support for source installation

F-011: root install.cmd explicitly falls back to Windows PowerShell5.1, but the builder immediately calls a newer .NET overload. Published bundle launch/install/update are separate and may keep5.1.

Options:

1. **Recommended:** require PowerShell7 for source builds; detect/refuse early with a precise prerequisite before uv/bootstrap/output mutation, and align root CMD/source docs. Keep5.1 published-bundle support and fix its UTF-8 readers independently.
2. Support source installation on5.1: replace unsupported APIs throughout the source route, audit adjacent modern runtime calls, and obtain actual5.1 source-builder acceptance. Fixing only one overload is insufficient.

Why this needs the maintainer: it chooses a supported contributor/user interpreter boundary. The current “PowerShell” wording and fallback do not establish an intentional7-only source contract. P8 depends on this choice. O-02 defines acceptance.

## D-02 — User-authored preset-directory symlinks

The executed V3 scratch probe confirms preset save follows a symlinked `<root>/config/presets` parent and writes its external target. Selected-config containment and atomic replacement do not determine this destination policy. No existing instruction clearly forbids deliberately shared preset directories; therefore no vulnerability is reported.

Options:

1. **Recommended if shared presets are useful/current:** explicitly permit user-authored preset-directory links, document that save targets their resolved destination, retain atomicity/name safety and avoid claiming workspace containment for them.
2. Require real resolved preset destinations beneath the workspace/config owner; reject symlink/junction escape before any write and prove refusal preserves both local/external bytes on POSIX and Windows.

Why this needs the maintainer: tightening containment changes an otherwise plausible shared-preset workflow. Treat it as a supported persistence boundary choice, not a cleanup/security label inferred from symlink existence. No dependent fix is in P3 until chosen.

## D-03 — Full portable reinstall into an existing bundle root

Independent VW3 downgraded W3 to a conditional hypothesis. Rollback backups carry only source bytes; restore has no runtime/requirements check before removing current code. But supported cross-runtime retention is unresolved: source builder clears output, reinstall E2E uses a replacement directory, docs say full ZIP reinstall without explicitly choosing overlay versus fresh root.

Options:

1. **Recommended:** define full runtime replacement as fresh-directory install with preserved user config/data and explicit migration of the installed pointer; document and verify that prior incompatible backups cannot become current listed rollback candidates. Avoid in-place overlay ambiguity.
2. Support complete full-ZIP overlay into the existing root. Then preserve backup compatibility identity and refuse cross-runtime rollback before mutation, or make reinstall reliably invalidate incompatible backups while retaining useful same-runtime backups.

Why this needs the maintainer: a missing guard alone does not prove a reachable supported migration defect. If overlay is supported, the traced missing guard can become LIKELY; O-03 still needs authenticated real A/B artifacts and proof that B is complete/valid before rollback. Do not manufacture reproduction by manually copying backups or testing an already-invalid mixed overlay. Unconditional backup deletion in the installer is not an automatically justified fix.

The current wizard scope, localized timestamp and manual authority semantics have sufficiently clear contracts for the report's recommendations. No extra feature, timezone or manual-flag decision is required just to reconcile those findings.
