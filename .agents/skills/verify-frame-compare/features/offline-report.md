# Open an offline report and review frames

## Sub-features

- Load screenshot paths containing spaces, punctuation and Unicode from a local
  report, and initialize its selected mode and accessible control state.
- Operate selected view/fit/focus/label/offset controls and enter Unicode notes.
- Export review data, move the report and its assets, import into fresh browser
  storage and reload: a mapped user route with incomplete browser acceptance.

Authority: [reports and overlays](../../../../docs/guides/reports-and-overlays.md),
[report architecture](../../../../docs/current-architecture.md#report-viewer), and
[browser verification](../../../../docs/ENGINEERING_RUNBOOK.md#report-viewer-verification).
Owner: `src/frame_compare/services/report/`.

## How to get to it (user POV)

Open `report.html` from a completed run folder in a browser. Keep its sibling
`screenshots/` folder when moving it, unless images are embedded. No web server or
authentication is needed. Select a view, use the source/fit controls, and open
**Inspector → Review** for review data. **Image offset** is spatial; it does not
change timing alignment.

The harness generates its own production report and images, then opens its
`file:` URL in isolated Chrome. It avoids needing a native media comparison merely
to reach the report controls.

## Driving it with the existing Chrome harness

After Launch, run a read-only discovery/version check using the same selector as
the harness. It reports absence as failure rather than silently accepting a skip:

```sh
uv run --no-sync python -c "import subprocess; from tests.browser.test_report_browser_smoke import _browser_executable; from nodejs_wheel import node; browser=_browser_executable(); assert browser, 'Chrome/Chromium missing; configure REPORT_BROWSER'; print(browser, flush=True); subprocess.run([browser,'--version'], check=True, timeout=15)" > "$verifyRun/evidence/browser-doctor.log" 2>&1
```

If needed, set `REPORT_BROWSER` to the actual Chrome/Chromium executable before
doctor. The trusted-input helper uses the locked `nodejs-wheel-binaries` package,
not whatever Node is on PATH. Record its package version with the environment.
Then use the runbook's existing browser entrypoint with evidence options:

```sh
uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py --basetemp "$verifyRun/scratch/browser" --junitxml "$verifyRun/evidence/browser-results.xml" > "$verifyRun/evidence/browser-run.log" 2>&1
```

Record the exit status immediately. Inspect skips, failures and actual assertions.
The module loads percent-encoded image paths, checks mode/ARIA state over viewport
and scale cases, and exercises selected fit/focus/offset/label behavior. Most
probes inject DOM instrumentation into the real generated page; note insertion
also uses Chrome trusted input events and checks its Unicode scalar limit and
exported text. It also contains mocked subprocess retry/cleanup tests, so its total
case count is not a count of browser-driven journeys.

Before cleanup, retain a useful generated HTML report and its associated synthetic
images from the browser basetemp if the assertions need a reproducible artifact.
The log/JUnit are retained assertions; a screenshot/DOM dump is not automatically
archived. Temporary Chrome profiles for DOM dumps are removed by their helper;
trusted-input profiles remain under basetemp, while the helper terminates/reaps
its Chrome child.

For the transfer route, use these manual steps, consistent with the runbook's
browser/manual evidence guidance: edit a
note/bookmark, use **Export review JSON** and observe the downloaded file, copy the
report, assets and review file to the destination, open with fresh storage, select
**Import review JSON**, choose merge/replace and reload. Capture the action, file,
resulting state and matching report ID/payload version. Record both environments. If a second
machine or observable download/import control is unavailable, report that route
unverified; the smoke module does not stand in for it.

## Gotchas

- The generated images are synthetic one-pixel PNGs. Browser success does not
  establish real-media rendering, subjective visual quality or another browser.
- Node-based `tests/services/test_report_viewer_state.py` and
  `test_report_review_state.py` cover additional state/merge contracts, not the
  download and transfer journey in a browser.
- A matching report ID and payload version are required for review imports.
  Browser storage availability matters; carrying the HTML/assets alone does not
  carry browser-local review state.
- Keep regular browser profiles and user reports untouched. Use a fresh test run
  directory, and inspect the helper's ownership/cleanup after a timeout.
- Cross-machine transfer and Windows browser execution remain explicit gaps until
  directly observed. A prior macOS Chrome result supplies neither claim.
