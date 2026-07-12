---
name: review-adjudication
description: Compatibility entrypoint for adjudicating Frame Compare review feedback; use the review-request review lifecycle.
---

# Review Adjudication

Load `review-request` and follow its finding-adjudication rules. This is a one-way
compatibility entrypoint for older plans; `review-request` is the sole authority and
must not route back here.
