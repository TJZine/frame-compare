---
search:
  exclude: true
---

# TODO

> Non-authoritative backlog. These items are candidates, not approved plans or
> current product contracts. Update or remove an item when its work is completed,
> rejected, or promoted into an active plan.

- Consider adding a dedicated packaging/release workflow skill if Python packaging, Docker, Windows portable, or updater/signing work becomes frequent.

## VSPreview Upstream Compatibility

- Track an upstream VSPreview release that supports VSJetPack 2.x without the
  removed `vs_object`, `set_output`, and `DitherType.is_fmtc` APIs. When one is
  available and the dependency update is approved, remove
  `prepare_vspreview_compatibility()` and its compatibility tests only after the
  frozen deep import, native Windows GUI flow, and extracted Windows portable
  runtime proof all pass without the shim.

## Release Identity Presentation Follow-Ups

- Consider dedicated release-identity display fields for the HTML report/HUD, baked
  screenshot overlays, wizard/dry-run exact-file presentation, and warnings where
  useful. Exclude run-folder/history names, the slow.pics collection title, and all
  internal identities.

---
