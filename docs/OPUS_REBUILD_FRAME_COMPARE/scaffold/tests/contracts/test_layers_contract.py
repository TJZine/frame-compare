"""Contract tests for import layers.

Verifies that pyproject.toml layers are valid and match dependency-graph.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Path to scaffold pyproject.toml
# tests/contracts/test_layers_contract.py -> tests/contracts -> tests -> scaffold
SCAFFOLD_DIR = Path(__file__).parent.parent.parent
PYPROJECT_TOML = SCAFFOLD_DIR / "pyproject.toml"

# Path to dependency-graph.md
OPUS_DIR = SCAFFOLD_DIR.parent
DEP_GRAPH_MD = OPUS_DIR / "03-architecture" / "dependency-graph.md"


def extract_layers_from_pyproject(path: Path) -> list[str]:
    """Extract import-linter layers from pyproject.toml using tomllib."""
    import tomllib

    with open(path, "rb") as f:
        data = tomllib.load(f)

    # Navigate to [tool.importlinter.contracts] -> first contract with layers
    contracts = data.get("tool", {}).get("importlinter", {}).get("contracts", [])
    for contract in contracts:
        if "layers" in contract:
            return contract["layers"]
    return []


def extract_layers_from_dep_graph(path: Path) -> list[str]:
    """Extract layers from dependency-graph.md sentinel block."""
    content = path.read_text(encoding="utf-8")

    # Find the sentinel block
    pattern = r"<!-- BEGIN GENERATED:importlinter -->.*?layers = \[(.*?)\]"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        return []

    layers_block = match.group(1)
    layers: list[str] = []

    for line in layers_block.splitlines():
        stripped = line.strip().strip(",").strip('"').strip("'")
        if stripped:
            layers.append(stripped)

    return layers


@pytest.mark.tier_a
class TestLayersContract:
    """Tests that import-linter layers are valid and consistent."""

    def test_layers_defined(self) -> None:
        """pyproject.toml has layers defined."""
        layers = extract_layers_from_pyproject(PYPROJECT_TOML)
        assert len(layers) > 0, "No layers found in pyproject.toml"

    def test_errors_is_leaf_module(self) -> None:
        """errors is at the bottom of the layer stack."""
        layers = extract_layers_from_pyproject(PYPROJECT_TOML)

        # errors should be last (lowest layer)
        assert any(
            "errors" in layer for layer in layers[-2:]
        ), "frame_compare.errors should be at or near bottom of layers"

    def test_cli_entry_is_top_module(self) -> None:
        """cli_entry is at the top of the layer stack."""
        layers = extract_layers_from_pyproject(PYPROJECT_TOML)

        # cli_entry should be first (highest layer)
        assert any(
            "cli_entry" in layer for layer in layers[:2]
        ), "frame_compare.cli_entry should be at or near top of layers"

    def test_vs_below_domain_modules(self) -> None:
        """vs module is below analysis/render/services."""
        layers = extract_layers_from_pyproject(PYPROJECT_TOML)

        vs_index = None
        domain_index = None

        for i, layer in enumerate(layers):
            if "vs" in layer and "vspreview" not in layer.lower():
                vs_index = i
            if "analysis" in layer or "render" in layer or "services" in layer:
                domain_index = i

        if vs_index is not None and domain_index is not None:
            assert (
                vs_index > domain_index
            ), "vs should be below domain modules (analysis, render, services)"

    def test_dependency_graph_matches_pyproject(self) -> None:
        """dependency-graph.md layers block matches pyproject.toml."""
        assert DEP_GRAPH_MD.exists(), (
            f"dependency-graph.md not found at {DEP_GRAPH_MD}. "
            "This is a contract failure, not a skip."
        )

        pyproject_layers = extract_layers_from_pyproject(PYPROJECT_TOML)
        dep_graph_layers = extract_layers_from_dep_graph(DEP_GRAPH_MD)

        assert dep_graph_layers, (
            "No sentinel block found in dependency-graph.md. "
            "Expected <!-- BEGIN GENERATED:importlinter --> marker. "
            "This is a contract failure, not a skip."
        )

        assert pyproject_layers == dep_graph_layers, (
            "Layers mismatch! Regenerate derived views (from repo root): "
            "`UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py` "
            "(or `python scripts/generate_contract_views.py`).\n"
            f"pyproject.toml: {pyproject_layers}\n"
            f"dependency-graph.md: {dep_graph_layers}"
        )
