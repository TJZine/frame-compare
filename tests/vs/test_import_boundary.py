import os
import subprocess
import sys
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_fresh_import_check(source: str) -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONOPTIMIZE", None)
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=_REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"fresh import check failed with exit {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def test_import_vs_does_not_import_submodules() -> None:
    """Importing frame_compare.vs should not eagerly load submodules."""
    _run_fresh_import_check(
        """
        import importlib
        import sys

        importlib.import_module("frame_compare.vs")

        assert "frame_compare.vs" in sys.modules
        assert "frame_compare.vs.tonemap" not in sys.modules
        assert "frame_compare.vs.color" not in sys.modules
        assert "frame_compare.vs.types" not in sys.modules
        """
    )


def test_import_with_blocked_vapoursynth() -> None:
    """Importing frame_compare.vs must succeed even if vapoursynth is not available."""
    _run_fresh_import_check(
        """
        import importlib
        import sys

        sys.modules["vapoursynth"] = None
        vs_mod = importlib.import_module("frame_compare.vs")

        assert vs_mod.is_vapoursynth_available() is False
        settings = vs_mod.TonemapSettings(enabled=False)
        assert settings.enabled is False
        """
    )


def test_lazy_attribute_resolution() -> None:
    """Accessing attributes should trigger submodule loading and resolve correctly."""
    _run_fresh_import_check(
        """
        import importlib
        import sys

        vs_mod = importlib.import_module("frame_compare.vs")

        settings_cls = vs_mod.TonemapSettings
        assert settings_cls is not None
        assert "frame_compare.vs.types" in sys.modules
        """
    )


def test_lazy_decoder_options_resolution() -> None:
    """Decoder options should remain available without eager VS source loading."""
    _run_fresh_import_check(
        """
        import importlib
        import sys

        vs_mod = importlib.import_module("frame_compare.vs")

        assert "frame_compare.vs.source" not in sys.modules
        options = vs_mod.LWLibavSourceOptions(threads=0)

        assert options.threads == 0
        assert "frame_compare.vs.source" in sys.modules
        """
    )
