"""Unit tests for performance instrumentation."""

from __future__ import annotations

import os
from unittest.mock import patch

from frame_compare.utils.perf import perf_span


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
