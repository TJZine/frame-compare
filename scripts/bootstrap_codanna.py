"""Generate checkout-local Codanna settings from the tracked template."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

_WORKSPACE_ROOT_TOKEN = "@WORKSPACE_ROOT@"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    template_path = repo_root / ".codanna" / "settings.toml.in"
    settings_path = repo_root / ".codanna" / "settings.toml"
    template = template_path.read_text(encoding="utf-8")
    if template.count(_WORKSPACE_ROOT_TOKEN) != 2:
        raise SystemExit(f"{template_path} must contain exactly two {_WORKSPACE_ROOT_TOKEN} tokens")

    rendered = template.replace(
        _WORKSPACE_ROOT_TOKEN,
        json.dumps(str(repo_root), ensure_ascii=False),
    )
    tomllib.loads(rendered)
    settings_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {settings_path}")


if __name__ == "__main__":
    main()
