# Publishing and webhooks

Frame Compare is offline-first. slow.pics upload is disabled by default, and a
first-use wizard writes `slowpics.auto_upload = false`. Enable it deliberately only
after a local report looks right:

```toml
[slowpics]
auto_upload = true
visibility = "unlisted"
```

`--no-upload` forces upload off for a run. For an interactive report-first decision,
you can also set `confirm_upload_after_report = true`; this requires an interactive,
report-enabled run and has no dedicated run flag.

Uploads use the explicitly planned screenshots from the current render. At most three
image requests are in flight. Navigation and metadata requests use
`timeout_seconds = 60.0` by default, image uploads use a separate 180-second default,
and `max_retries = 3`. Rate-limited responses honor the service's retry timing within
the configured retry budget. See the
[slow.pics contract](../current-cli-contract.md#slowpics-upload-behavior) before changing
retention, deletion, retry, or post-upload behavior.

## Webhook notification

After a successful upload, Frame Compare can send the resulting URL to a
Discord-compatible incoming webhook. Set the secret outside tracked configuration:

```bash
# For an interactive shell; the value is not echoed or placed in shell history.
read -rsp "Webhook URL: " FRAME_COMPARE_SLOWPICS__WEBHOOK_URL
export FRAME_COMPARE_SLOWPICS__WEBHOOK_URL
printf '\n'
```

For unattended runs, inject the same variable through a secret store or process
manager instead.

Do not commit a live webhook URL. Although manually authored TOML can contain
`webhook_url`, generated configuration and preset files omit it, including wizard
rewrites, `run --write-config`, `preset save`, and `preset apply`.

The webhook payload is the Discord-compatible `content` JSON shape containing the
slow.pics URL. The endpoint must be external HTTPS. Delivery follows no redirects,
uses a 10-second absolute deadline per attempt, and makes at most three attempts.
Pre-send connection failures and server errors use bounded backoff; HTTP 429 is
retried only for a valid `Retry-After` of at most 10 seconds. Once transmission starts,
an uncertain outcome is not retried because a second POST could duplicate the
notification. Delivery failures are warnings and do not fail a completed comparison;
URL details remain redacted from diagnostics.

The [webhook policy](../current-cli-contract.md#slowpics-webhook-policy) is the
authority for validation, retry, redaction, and failure semantics.
