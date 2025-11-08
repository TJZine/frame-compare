# Runner Refactor Checklist

- [2025-11-08] Replace the slow.pics uploader with the legacy comp.py single-session routine. The new flow must:
  - Reuse one `requests.Session` for collection creation and per-frame uploads.
  - Log `Uploading screenshot X/Y` messages so long runs remain transparent without Rich progress bars.
  - Drop the threaded worker pool, `_SessionPool`, and `max_workers` plumbing from both the runner and `src/slowpics.py`.
  - Keep shortcut/webhook handling intact so operators don't lose post-upload automation.
