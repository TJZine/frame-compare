#!/usr/bin/env python3
"""Generate derived views from canonical contract files.

Usage (recommended / repo standard):
    UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py
    UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check

Usage (fallback):
    python scripts/generate_contract_views.py          # Regenerate all
    python scripts/generate_contract_views.py --check  # Exit 1 if stale

Canonical sources (docs/OPUS_REBUILD_FRAME_COMPARE/contracts/):
    - cli_flags.yaml       -> cli-flags-canonical.md, cli/_generated.py
    - error_codes.yaml     -> error-codes.md
    - config_schema.json   -> config-reference.md (Field Inventory block)
    - pyproject.toml       -> dependency-graph.md (import-linter block)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install with: uv pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# Paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = PROJECT_ROOT / "docs" / "OPUS_REBUILD_FRAME_COMPARE" / "contracts"
IMPL_DIR = PROJECT_ROOT / "docs" / "OPUS_REBUILD_FRAME_COMPARE" / "05-implementation"
ARCH_DIR = PROJECT_ROOT / "docs" / "OPUS_REBUILD_FRAME_COMPARE" / "03-architecture"
SCAFFOLD_DIR = PROJECT_ROOT / "docs" / "OPUS_REBUILD_FRAME_COMPARE" / "scaffold"
CLI_GEN = SCAFFOLD_DIR / "src" / "frame_compare" / "cli" / "_generated.py"
PYPROJECT_TOML = SCAFFOLD_DIR / "pyproject.toml"


def load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_pyproject_layers() -> list[str]:
    """Extract import-linter layers from pyproject.toml using tomllib."""
    import tomllib

    with open(PYPROJECT_TOML, "rb") as f:
        data = tomllib.load(f)

    # Navigate to [tool.importlinter.contracts] -> first contract with layers
    contracts = data.get("tool", {}).get("importlinter", {}).get("contracts", [])
    for contract in contracts:
        if "layers" in contract:
            return contract["layers"]
    return []


def replace_sentinel_block(content: str, marker: str, new_block: str) -> str:
    """Replace content between sentinel markers.

    Markers: <!-- BEGIN GENERATED:marker --> and <!-- END GENERATED:marker -->

    Raises:
        ValueError: If markers are missing or duplicated (count != 1).
    """
    pattern = re.compile(
        rf"(<!-- BEGIN GENERATED:{re.escape(marker)} -->).*?(<!-- END GENERATED:{re.escape(marker)} -->)",
        flags=re.DOTALL,
    )
    replacement = rf"\1\n{new_block}\n\2"
    result, count = pattern.subn(replacement, content)
    if count != 1:
        raise ValueError(f"Missing or duplicate sentinel block: {marker} (replacements={count})")
    return result


# =============================================================================
# GENERATORS
# =============================================================================


def generate_cli_flags_md() -> str:
    """Generate cli-flags-canonical.md from cli_flags.yaml."""
    data = load_yaml(CONTRACTS_DIR / "cli_flags.yaml")

    lines = [
        "# CLI Flags — Single Source of Truth",
        "",
        "> **Module:** Reference  ",
        "> **Purpose:** Canonical CLI flag definitions to sync docs/specs/tests",
        "",
        "> [!NOTE]",
        "> This file is AUTO-GENERATED from `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/cli_flags.yaml`.",
        "> Do not edit manually. Regenerate with: `python scripts/generate_contract_views.py`",
        "",
        "---",
        "",
        "## Canonical Flag Table",
        "",
        "| ID | Long | Short | Type | Default | Config Key | Help |",
        "|:---|:-----|:------|:-----|:--------|:-----------|:-----|",
    ]

    for flag in data["flags"]:
        short = flag.get("short") or "-"
        default = flag.get("default")
        if default is None:
            default_str = "None"
        elif isinstance(default, bool):
            default_str = str(default)
        else:
            default_str = str(default)
        config_key = flag.get("config_key") or "-"

        lines.append(
            f"| {flag['id']} | {flag['long']} | {short} | {flag['type']} | "
            f"{default_str} | {config_key} | {flag['help']} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            f"*Generated from version {data['version']}*",
            "",
        ]
    )

    return "\n".join(lines)


def generate_cli_flags_py() -> str:
    """Generate _generated.py from cli_flags.yaml."""
    data = load_yaml(CONTRACTS_DIR / "cli_flags.yaml")

    lines = [
        '"""Auto-generated from contracts/cli_flags.yaml — DO NOT EDIT MANUALLY.',
        "",
        "Regenerate with: python scripts/generate_contract_views.py",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import TypedDict",
        "",
        "",
        "class CLIFlagInfo(TypedDict):",
        '    """Type-safe CLI flag metadata."""',
        "    long: str",
        "    short: str | None",
        "    type: str",
        "    default: bool | str | int | None",
        "    config_key: str | None",
        "    help: str",
        "    choices: list[str] | None",
        "    envvar: str | None",
        "",
        "",
        "CLI_FLAGS: dict[str, CLIFlagInfo] = {",
    ]

    for flag in data["flags"]:
        lines.append(f'    "{flag["id"]}": {{')
        lines.append(f'        "long": "{flag["long"]}",')

        if flag.get("short"):
            lines.append(f'        "short": "{flag["short"]}",')
        else:
            lines.append('        "short": None,')

        lines.append(f'        "type": "{flag["type"]}",')

        # Handle default value
        default = flag.get("default")
        if default is None:
            lines.append('        "default": None,')
        elif isinstance(default, bool):
            lines.append(f'        "default": {default},')
        elif isinstance(default, str):
            lines.append(f'        "default": "{default}",')
        else:
            lines.append(f'        "default": {default},')

        if flag.get("config_key"):
            lines.append(f'        "config_key": "{flag["config_key"]}",')
        else:
            lines.append('        "config_key": None,')

        lines.append(f'        "help": "{flag["help"]}",')

        if flag.get("choices"):
            choices_str = ", ".join(f'"{c}"' for c in flag["choices"])
            lines.append(f'        "choices": [{choices_str}],')
        else:
            lines.append('        "choices": None,')

        if flag.get("envvar"):
            lines.append(f'        "envvar": "{flag["envvar"]}",')
        else:
            lines.append('        "envvar": None,')

        lines.append("    },")

    lines.extend(
        [
            "}",
            "",
        ]
    )

    return "\n".join(lines)


def generate_error_codes_md() -> str:
    """Generate error-codes.md from error_codes.yaml."""
    data = load_yaml(CONTRACTS_DIR / "error_codes.yaml")

    lines = [
        "# Error Code Reference",
        "",
        "> **Module:** Reference  ",
        "> **Version:** 1.0",
        "",
        "> [!NOTE]",
        "> This file is AUTO-GENERATED from `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml`.",
        "> Do not edit manually. Regenerate with: `python scripts/generate_contract_views.py`",
        "",
        "---",
        "",
        "## 1. Error Code Hierarchy",
        "",
        "```text",
        "FC-xxxx",
        "│",
        "├── FC-1xxx: Configuration Errors (Exit Code 2)",
        "├── FC-2xxx: Dependency Errors (Exit Code 3)",
        "├── FC-3xxx: Input Errors (Exit Code 4)",
        "├── FC-4xxx: Processing Errors (Exit Code 5)",
        "├── FC-5xxx: Network Errors (Exit Code 6)",
        "└── FC-9xxx: Internal Errors (Exit Code 1)",
        "```",
        "",
        "---",
        "",
    ]

    # Group errors by category
    categories = {
        "1": ("Configuration Errors (FC-1xxx)", 2),
        "2": ("Dependency Errors (FC-2xxx)", 3),
        "3": ("Input Errors (FC-3xxx)", 4),
        "4": ("Processing Errors (FC-4xxx)", 5),
        "5": ("Network Errors (FC-5xxx)", 6),
        "9": ("Internal Errors (FC-9xxx)", 1),
    }

    section_num = 2
    for cat_id, (cat_name, _) in categories.items():
        cat_errors = {
            code: err for code, err in data["errors"].items() if code.startswith(f"FC-{cat_id}")
        }

        if not cat_errors:
            continue

        lines.extend(
            [
                f"## {section_num}. {cat_name}",
                "",
                "| Code | Name | Message | Hint |",
                "|------|------|---------|------|",
            ]
        )

        for code in sorted(cat_errors.keys()):
            err = cat_errors[code]
            lines.append(f"| {code} | {err['name']} | {err['message_template']} | {err['hint']} |")

        lines.extend(["", "---", ""])
        section_num += 1

    # Exit codes table
    lines.extend(
        [
            f"## {section_num}. Exit Codes",
            "",
            "| Exit Code | Meaning | Error Categories |",
            "|-----------|---------|------------------|",
            "| 0 | Success | - |",
            "| 1 | General/Internal Error | FC-9xxx |",
            "| 2 | Configuration Error | FC-1xxx |",
            "| 3 | Dependency Error | FC-2xxx |",
            "| 4 | Input Error | FC-3xxx |",
            "| 5 | Processing Error | FC-4xxx |",
            "| 6 | Network Error | FC-5xxx |",
            "| 130 | Interrupted (Ctrl+C) | - |",
            "",
        ]
    )

    return "\n".join(lines)


def generate_config_inventory_block() -> str:
    """Generate the Field Inventory table from config_schema.json."""
    schema = load_json(CONTRACTS_DIR / "config_schema.json")

    lines = [
        "| Section | Field | Type | Default |",
        "|:--------|:------|:-----|:--------|",
    ]

    for section_name, section in schema.get("properties", {}).items():
        if section.get("type") != "object":
            continue

        for field_name, field in section.get("properties", {}).items():
            field_type = field.get("type", "any")
            # Handle nullable types
            if isinstance(field_type, list):
                field_type = "/".join(field_type)

            default = field.get("default")
            if default is None:
                default_str = "null"
            elif isinstance(default, bool):
                default_str = str(default).lower()
            elif isinstance(default, str):
                default_str = f'"{default}"'
            else:
                default_str = str(default)

            lines.append(f"| {section_name} | {field_name} | {field_type} | {default_str} |")

    return "\n".join(lines)


def sync_config_reference() -> str:
    """Update Field Inventory block in config-reference.md using sentinel markers."""
    config_ref_path = IMPL_DIR / "config-reference.md"
    content = config_ref_path.read_text(encoding="utf-8")

    new_block = generate_config_inventory_block()

    return replace_sentinel_block(content, "config_inventory", new_block)


def generate_importlinter_block() -> str:
    """Generate the import-linter TOML block."""
    layers = load_pyproject_layers()

    lines = [
        "```toml",
        "# pyproject.toml",
        "",
        "[tool.importlinter]",
        'root_package = "frame_compare"',
        "",
        "[[tool.importlinter.contracts]]",
        'name = "Layered Architecture"',
        'type = "layers"',
        "layers = [",
    ]

    for layer in layers:
        lines.append(f'    "{layer}",')

    lines.extend(
        [
            "]",
            "",
            "[[tool.importlinter.contracts]]",
            'name = "No circular dependencies"',
            'type = "independence"',
            "modules = [",
            '    "frame_compare.analysis",',
            '    "frame_compare.render",',
            '    "frame_compare.services",',
            "]",
            "```",
        ]
    )

    return "\n".join(lines)


def sync_layers_block() -> str:
    """Update layers block in dependency-graph.md using sentinel markers."""
    dep_graph_path = ARCH_DIR / "dependency-graph.md"
    content = dep_graph_path.read_text(encoding="utf-8")

    new_block = generate_importlinter_block()

    return replace_sentinel_block(content, "importlinter", new_block)


# =============================================================================
# MAIN
# =============================================================================


def generate_all() -> dict[Path, str]:
    """Generate all derived files from canonical sources."""
    # Ensure CLI directory exists
    CLI_GEN.parent.mkdir(parents=True, exist_ok=True)

    return {
        IMPL_DIR / "cli-flags-canonical.md": generate_cli_flags_md(),
        IMPL_DIR / "error-codes.md": generate_error_codes_md(),
        IMPL_DIR / "config-reference.md": sync_config_reference(),
        ARCH_DIR / "dependency-graph.md": sync_layers_block(),
        CLI_GEN: generate_cli_flags_py(),
    }


def check_freshness() -> bool:
    """Check if all derived files are up-to-date. Returns True if fresh."""
    generated = generate_all()
    all_fresh = True

    for path, content in generated.items():
        if not path.exists():
            print(f"STALE: {path.relative_to(PROJECT_ROOT)} does not exist")
            all_fresh = False
            continue

        existing = path.read_text(encoding="utf-8")
        if existing != content:
            print(f"STALE: {path.relative_to(PROJECT_ROOT)} differs from generated")
            all_fresh = False

    return all_fresh


def write_all() -> None:
    """Write all generated files."""
    generated = generate_all()

    for path, content in generated.items():
        # Use LF line endings for cross-platform consistency
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"WROTE: {path.relative_to(PROJECT_ROOT)}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate derived views from canonical contract files."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if files are up-to-date (exit 1 if stale)",
    )

    args = parser.parse_args()

    # Guard against dual authority: fail if root-level contracts/ exists
    root_contracts = PROJECT_ROOT / "contracts"
    if root_contracts.exists():
        print(
            f"ERROR: Root-level contracts/ directory exists at {root_contracts}\n"
            f"Canonical contracts are in docs/OPUS_REBUILD_FRAME_COMPARE/contracts/\n"
            f"Delete {root_contracts} to prevent dual authority.",
            file=sys.stderr,
        )
        return 1

    if args.check:
        if check_freshness():
            print("OK: All derived files are up-to-date")
            return 0
        else:
            print(
                "\nRun 'UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py' to regenerate"
            )
            return 1
    else:
        write_all()
        return 0


if __name__ == "__main__":
    sys.exit(main())
