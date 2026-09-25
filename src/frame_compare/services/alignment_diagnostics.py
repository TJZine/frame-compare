"""Bounded, run-local persistence for diagnostic-only audio evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from frame_compare.errors import PathEscapesRootError
from frame_compare.services.types import AlignmentResult, AudioAlignmentAttempt
from frame_compare.utils.atomic_write import write_text_atomic
from frame_compare.utils.paths import require_managed_immediate_child

_SCHEMA_VERSION = 3
_MAX_ARTIFACT_BYTES = 128 * 1024

type AlignmentReviewOutcome = Literal[
    "pending",
    "not_requested",
    "confirmed",
    "keep_current",
    "no_result",
    "rejected_result",
]


def _bounded_label(value: str) -> str:
    return " ".join(value.split())[:256]


def _attempt_payload(attempt: AudioAlignmentAttempt | None) -> dict[str, object] | None:
    return asdict(attempt) if attempt is not None else None


def canonical_attempt_bytes(attempt: AudioAlignmentAttempt) -> bytes:
    """Return the canonical bytes covered by the diagnostic history digest."""
    return json.dumps(
        _attempt_payload(attempt),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def original_attempt_digest(attempt: AudioAlignmentAttempt | None) -> str | None:
    if attempt is None:
        return None
    return hashlib.sha256(canonical_attempt_bytes(attempt)).hexdigest()


def diagnostic_path(
    generated_root: Path,
    diagnostics_dir: Path,
    comparison_ordinal: int,
) -> Path:
    """Resolve one contained immediate-child artifact path."""
    if isinstance(comparison_ordinal, bool):
        raise ValueError("comparison_ordinal must be an integer")
    if comparison_ordinal < 1:
        raise ValueError("comparison_ordinal must be >= 1")
    run_dir = require_managed_immediate_child(generated_root, diagnostics_dir.parent)
    resolved_dir = require_managed_immediate_child(run_dir, diagnostics_dir)
    path = resolved_dir / f"comparison-{comparison_ordinal}.json"
    if path.exists() and (path.is_symlink() or path.is_junction() or not path.is_file()):
        raise PathEscapesRootError(path.resolve(), resolved_dir)
    return require_managed_immediate_child(resolved_dir, path)


def write_alignment_diagnostic(
    *,
    generated_root: Path,
    diagnostics_dir: Path,
    comparison_ordinal: int,
    reference_label: str,
    comparison_label: str,
    attempt: AudioAlignmentAttempt | None,
    evidence_availability: str,
    review_outcome: AlignmentReviewOutcome,
    final_result: AlignmentResult,
    final_origin: str,
    confirmed_frame_pair: tuple[int, int] | None = None,
) -> tuple[Path, str | None, int]:
    """Atomically write one bounded pathless diagnostic envelope."""
    path = diagnostic_path(generated_root, diagnostics_dir, comparison_ordinal)
    digest = original_attempt_digest(attempt)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "purpose": "diagnostic_only",
        "pair": {
            "reference_identity_digest": (
                attempt.reference_identity_digest if attempt is not None else None
            ),
            "comparison_identity_digest": (
                attempt.comparison_identity_digest if attempt is not None else None
            ),
            "comparison_ordinal": comparison_ordinal,
            "reference_label": _bounded_label(reference_label),
            "comparison_label": _bounded_label(comparison_label),
        },
        "evidence_availability": evidence_availability,
        "original_audio_attempt": _attempt_payload(attempt),
        "original_attempt_digest": digest,
        "review_outcome": review_outcome,
        "final_resolution": {
            "origin": final_origin if final_result.applied else "none",
            "applied": final_result.applied,
            "frame_offset": final_result.frame_offset if final_result.applied else None,
            "reference_source_frame": (
                confirmed_frame_pair[0] if confirmed_frame_pair is not None else None
            ),
            "comparison_source_frame": (
                confirmed_frame_pair[1] if confirmed_frame_pair is not None else None
            ),
        },
    }
    content = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    size = len(content.encode("utf-8"))
    if size > _MAX_ARTIFACT_BYTES:
        raise ValueError(f"audio alignment diagnostic exceeds {_MAX_ARTIFACT_BYTES} bytes: {size}")
    write_text_atomic(path, content, encoding="utf-8")
    return path, digest, size


__all__ = [
    "AlignmentReviewOutcome",
    "canonical_attempt_bytes",
    "diagnostic_path",
    "original_attempt_digest",
    "write_alignment_diagnostic",
]
