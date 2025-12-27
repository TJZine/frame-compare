"""Contract tests for derived view freshness.

Verifies that generated files are up-to-date with canonical contracts.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Path to generator script (relative to project root)
# tests/contracts/ -> tests -> scaffold -> OPUS_REBUILD_FRAME_COMPARE -> docs -> frame-compare
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
GENERATOR_SCRIPT = PROJECT_ROOT / "scripts" / "generate_contract_views.py"


@pytest.mark.tier_a
class TestDerivedViewsFresh:
    """Tests that generated files are not stale."""

    def test_generator_script_exists(self) -> None:
        """Generator script exists at expected location."""
        assert GENERATOR_SCRIPT.exists(), (
            f"Generator script not found: {GENERATOR_SCRIPT}"
        )

    def test_generated_files_fresh(self) -> None:
        """All generated files match current generation (--check passes)."""
        result = subprocess.run(
            [sys.executable, str(GENERATOR_SCRIPT), "--check"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        if result.returncode != 0:
            pytest.fail(
                f"Generated files are stale. Run:\n"
                f"  python scripts/generate_contract_views.py\n\n"
                f"Output:\n{result.stdout}\n{result.stderr}"
            )
