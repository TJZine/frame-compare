"""Unit tests for performance instrumentation."""

from __future__ import annotations

import os
from unittest.mock import patch

from frame_compare.utils.perf import is_perf_enabled, perf_span


def test_is_perf_enabled_default_false():
    """Verify returns False when env var unset."""
    with patch.dict(os.environ, {}, clear=True):
        assert is_perf_enabled() is False


def test_is_perf_enabled_true_values():
    """Verify returns True for various enabled values."""
    for val in ("1", "true", "yes", "on", "TRUE", "Yes"):
        with patch.dict(os.environ, {"FRAME_COMPARE_PERF": val}):
            assert is_perf_enabled() is True


def test_perf_span_disabled_no_log():
    """Verify does not log when disabled."""
    with (
        patch.dict(os.environ, {"FRAME_COMPARE_PERF": "0"}),
        patch("frame_compare.utils.perf.log") as mock_log,
    ):
        with perf_span("test"):
            pass
        mock_log.info.assert_not_called()


def test_perf_span_enabled_logs():
    """Verify logs perf event when enabled."""
    with (
        patch.dict(os.environ, {"FRAME_COMPARE_PERF": "1"}),
        patch("frame_compare.utils.perf.log") as mock_log,
    ):
        with perf_span("test_span", extra="field"):
            pass
        # Should call log.info("perf", span="test_span", elapsed_ms=..., extra="field")
        mock_log.info.assert_called_once()
        args, kwargs = mock_log.info.call_args
        assert args[0] == "perf"
        assert kwargs["span"] == "test_span"
        assert "elapsed_ms" in kwargs
        assert kwargs["extra"] == "field"
