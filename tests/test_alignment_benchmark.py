"""Pure-logic tests for the production alignment benchmark tool."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_script() -> ModuleType:
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "alignment_benchmark.py"
    name = f"alignment_benchmark_test_{id(path)}_{len(sys.modules)}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("expected_frame", "applied", "frame_offset", "state", "outcome"),
    [
        pytest.param(147, True, 147, "trusted_automatic", "correct_applied", id="applied-truth"),
        pytest.param(0, True, 0, "trusted_automatic", "correct_applied", id="applied-zero"),
        pytest.param(147, True, 146, "trusted_automatic", "wrong_applied", id="applied-wrong"),
        pytest.param(147, False, None, "provisional", "provisional", id="provisional"),
        pytest.param(147, False, None, "unavailable", "unavailable", id="unavailable"),
        pytest.param(None, False, None, "provisional", "correctly_withheld", id="withheld"),
        pytest.param(None, False, None, "unavailable", "correctly_withheld", id="withheld-quiet"),
        pytest.param(None, True, 0, "trusted_automatic", "wrong_applied", id="control-applied"),
    ],
)
def test_classify_outcome(
    expected_frame: int | None,
    applied: bool,
    frame_offset: int | None,
    state: str,
    outcome: str,
) -> None:
    script = _load_script()

    assert (
        script.classify_outcome(
            expected_frame=expected_frame,
            applied=applied,
            frame_offset=frame_offset,
            state=state,
        )
        == outcome
    )


def test_refusal_rate_counts_same_content_pairs_only() -> None:
    script = _load_script()
    records: list[dict[str, Any]] = [
        {"outcome": "correct_applied", "expected_frame": 0},
        {"outcome": "correct_applied", "expected_frame": 147},
        {"outcome": "provisional", "expected_frame": -361},
        {"outcome": "unavailable", "expected_frame": 120},
        {"outcome": "correctly_withheld", "expected_frame": None},
    ]

    assert script.refusal_rate(records) == pytest.approx(0.5)


def test_refusal_rate_without_eligible_pairs_is_none() -> None:
    script = _load_script()

    assert script.refusal_rate([{"outcome": "correctly_withheld", "expected_frame": None}]) is None
