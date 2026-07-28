# Windows initial-release evidence — 2026-07-28

This record captures non-secret Windows evidence for commit
`47e207ecfdae72cbcc57fe2dfe99d20907d7fce5`. It does not authorize or record
publication of the official `v0.1.0` tag.

```text
WINDOWS_RELEASE_EVIDENCE
date_utc: 2026-07-28T20:32:02Z
tester: Codex on the maintainer-provided Windows host
windows_version: Microsoft Windows 10 Home 10.0.19045 build 19045
powershell_7_version: 7.6.4
windows_powershell_version: 5.1.19041.7548
git_commit: 47e207ecfdae72cbcc57fe2dfe99d20907d7fce5
candidate_tag_or_workflow_run: workflow_dispatch run 30396146397

focused_windows_tests: PASS
full_repository_gate: PASS
release_public_key_validation: PASS
portable_build_require_release_key: PASS
bundle_runtime_proof: PASS
bundle_license_inventory: PASS
corresponding_source_inventory: PASS
real_key_signed_update_apply: NOT YET RUN FOR AN EXACT DOWNLOADED PRERELEASE
tampered_manifest_rejected: PASS WITH DISPOSABLE TEST KEYS
tampered_payload_rejected: PASS WITH DISPOSABLE TEST KEYS
rollback: PASS WITH DISPOSABLE TEST KEYS
workflow_dispatch_signed_artifacts: PASS
release_event_chain: NOT YET PROVED
clean_profile_rc_acceptance: NOT YET RUN

portable_zip_sha256: 41e4025b650e8afd9b4c71a4a568174df4e4ae136832cbf3e37bb946f75ff538
update_zip_sha256: 395d328f60feb9d29dc0e1db79e53850efa4f0c48fdc5b29f8a87627d3c702a9
public_key_fingerprint: fca110f86c9304cc5394597c6d5d152f79d11e58a6cf59dab32adafbf4e0479a
private_key_present_in_repo_logs_artifacts: NO
unexpected_skips_or_warnings: see Notes
remaining_blockers: release-event chain and exact prerelease acceptance
commits_created: f212c475b584ac97d309736abd268df41c96d876
```

## Protected workflow proof

- Run: <https://github.com/TJZine/frame-compare/actions/runs/30396146397>
- Branch and head: `cleanup` at
  `47e207ecfdae72cbcc57fe2dfe99d20907d7fce5`
- Result: the `build` job and all of its steps passed. The release-only asset job
  was correctly skipped for `workflow_dispatch`.
- The public-key validator, release-mode portable build, extracted install smoke,
  secret-required signing step, signed-update layout verification, and both
  artifact uploads passed.
- `frame-compare-update-win-x64` artifact ID `8702976263`; GitHub artifact
  digest `d46ee8c4d6549ffac6efe690a684611ac69e1a9ed416996af8aed089be40ed07`.
- `frame-compare-portable-win-x64` artifact ID `8702975907`; GitHub artifact
  digest `73d7718a82062732442d3c11dd620fd6f210cf3cab6fc19c4c85c61c83737303`.

The downloaded update contained 173 manifest-listed payload files. Every size and
SHA-256 matched, `update-manifest.sig` was present, and its RSA-SHA256-PKCS1
signature verified against the committed public key. The downloaded portable ZIP
contained 9,325 entries under one root, identified the exact cleanup commit, and
reported 57 Python distributions, five pinned manifest artifacts, and 92
license/source entries. Neither archive contained Python cache, runtime-smoke, or
private-key-like residue.

## Notes and remaining gates

- The CI-equivalent full suite passed from an isolated working directory. Expected
  local skips were one browser-autodetection test, two manual live slow.pics tests,
  and six bash-dependent Docker contract tests. Their applicable GitHub/browser
  and Docker proof remains separate.
- The exact local bundle emitted the known L-SMASH API3 deprecation warning during
  runtime proof; loading and frame access still passed.
- GitHub requires a `workflow_dispatch` workflow to exist on the default branch.
  Commit `f212c475b584ac97d309736abd268df41c96d876`
  (`ci(release): enable Windows workflow dispatch`) adds the exact cleanup workflow
  file to `main`; both branches use the same workflow blob.
- P1 and the Windows inventory portion of P2/P6 have exit evidence. The manual
  protected-signing path of P3 passes.
- P3 is not complete until the Release Please to published-prerelease to Windows
  release-event chain is proved through an explicitly disposable prerelease path.
- Windows P7 is not complete until the exact assets from that approved prerelease
  pass the clean-profile SDR/HDR, report, update, rollback, and uninstall matrix.
- Codex did not access any private key value, private-key hash, private storage
  path, or signing secret. The GitHub workflow consumed the configured secret
  without disclosing or recording it in repository content, task output, logs,
  caches, or artifacts.
