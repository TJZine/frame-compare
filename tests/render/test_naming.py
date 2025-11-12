from __future__ import annotations

import pytest

from src.frame_compare.render import naming


def test_sanitise_label_replaces_invalid_characters() -> None:
    result = naming.sanitise_label('Comp<>:"/\\|?*')
    disallowed = set('<>:"/\\|?*')
    assert all(ch not in disallowed for ch in result)
    assert result.startswith("Comp")


def test_sanitise_label_strips_windows_trailing_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(naming.os, "name", "nt", raising=False)
    result = naming.sanitise_label(" demo .")
    assert result == "demo"


def test_derive_labels_prefers_metadata_label() -> None:
    metadata = {"label": " Example "}
    raw, safe = naming.derive_labels("unused.mkv", metadata)
    assert raw == "Example"
    assert safe == "Example"


def test_prepare_filename_formats_frame_and_label() -> None:
    assert naming.prepare_filename(42, "Clean") == "42 - Clean.png"
