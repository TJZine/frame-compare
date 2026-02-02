from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

from frame_compare.orchestration import RunRequest as PublicRunRequest
from frame_compare.orchestration.coordinator import RunRequest


def test_run_request_defaults() -> None:
    request = RunRequest(root=Path("x"))

    assert request.root == Path("x")

    assert request.config_path is None
    assert request.input_dir is None
    assert request.tm_preset is None
    assert request.tm_target_nits is None
    assert request.tm_curve is None
    assert request.frame_count is None
    assert request.seed is None
    assert request.overlay_mode is None

    assert request.no_cache is False
    assert request.from_cache_only is False
    assert request.skip_analysis is False
    assert request.skip_metadata is False
    assert request.skip_dovi is False
    assert request.no_upload is False
    assert request.no_color is False
    assert request.quiet is False
    assert request.verbose is False
    assert request.json_output is False


def test_run_request_is_frozen() -> None:
    request = RunRequest(root=Path("x"))

    try:
        request.root = Path("y")
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("RunRequest should be frozen.")


def test_run_request_exported_from_orchestration() -> None:
    assert PublicRunRequest is RunRequest
