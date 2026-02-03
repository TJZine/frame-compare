from pathlib import Path

import pytest


def test_runner_exports_public_symbols() -> None:
    import frame_compare.runner as runner

    assert hasattr(runner, "RunRequest")
    assert hasattr(runner, "RunResult")
    assert hasattr(runner, "RunDependencies")
    assert hasattr(runner, "run")


def test_runner_run_is_scaffold_raises() -> None:
    import frame_compare.runner as runner

    request = runner.RunRequest(root=Path("."))

    with pytest.raises(
        NotImplementedError,
        match=r"^frame_compare\.runner\.run is not implemented yet \(scaffold\)$",
    ):
        runner.run(request)
