from __future__ import annotations

import json
from dataclasses import asdict, replace

from frame_compare.services.alignment_evidence import audio_attempt_payload
from tests.services.alignment_evidence_test_support import attempt_with_chunks


def test_full_attempt_serializes_with_unbounded_psr() -> None:
    attempt = attempt_with_chunks(2)
    attempt = replace(attempt, chunks=replace(attempt.chunks, psrs=("unbounded", 88.5)))

    payload = json.loads(json.dumps(audio_attempt_payload(attempt), allow_nan=False))

    assert payload["chunks"]["psrs"] == ["unbounded", 88.5]
    assert payload == json.loads(json.dumps(asdict(attempt), allow_nan=False))
