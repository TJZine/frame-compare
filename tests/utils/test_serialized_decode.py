"""Guard the decoder failure taxonomy against interpreter changes."""

import json
import tomllib
from pathlib import Path

import pytest

from frame_compare.utils.serialized_decode import SERIALIZED_DECODE_FAILURES


@pytest.mark.parametrize(
    "kind, content",
    [
        ("json", b"[" * 10000),
        ("json", b"1" * 5000),
        ("toml", b"x = " + b"{x=" * 1500 + b"0" + b"}" * 1500),
        ("toml", b"x = " + b"1" * 5000),
        ("json", b"\xff"),
        ("toml", b"\xff"),
    ],
)
def test_serialized_decoder_failures(tmp_path: Path, kind: str, content: bytes) -> None:
    path = tmp_path / "input"
    path.write_bytes(content)
    with pytest.raises(SERIALIZED_DECODE_FAILURES):
        if kind == "json":
            json.loads(path.read_text(encoding="utf-8"))
        else:
            with path.open("rb") as handle:
                tomllib.load(handle)
