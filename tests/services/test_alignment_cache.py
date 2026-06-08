"""Retirement guard for the removed legacy audio_offsets cache owner."""

from __future__ import annotations

import importlib.util


def test_legacy_alignment_cache_module_is_removed() -> None:
    assert importlib.util.find_spec("frame_compare.services.alignment_cache") is None
