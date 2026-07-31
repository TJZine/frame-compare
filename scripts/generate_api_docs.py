"""Generate deterministic API documentation for Frame Compare.

This script generates `docs/api.md` by parsing a locked set of modules using the Python AST.
It intentionally avoids importing project code (so optional dependencies do not affect generation).
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

API_DOCS_PACKAGE = "api_docs"
API_DOCS_DIR = Path(__file__).resolve().parent / API_DOCS_PACKAGE


def _module_is_from_local_api_docs(module_name: str) -> bool:
    module = sys.modules.get(module_name)
    if module is None:
        return False
    module_file = getattr(module, "__file__", None)
    if not module_file:
        return False
    try:
        return Path(str(module_file)).resolve().is_relative_to(API_DOCS_DIR.resolve())
    except OSError:
        return False


def _ensure_api_docs_package() -> None:
    # Tests import this wrapper by file path, where Python does not add scripts/ to sys.path.
    if _module_is_from_local_api_docs(API_DOCS_PACKAGE):
        return

    for module_name in list(sys.modules):
        if (
            module_name == API_DOCS_PACKAGE or module_name.startswith(f"{API_DOCS_PACKAGE}.")
        ) and not _module_is_from_local_api_docs(module_name):
            sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(
        API_DOCS_PACKAGE,
        API_DOCS_DIR / "__init__.py",
        submodule_search_locations=[str(API_DOCS_DIR)],
    )
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(API_DOCS_PACKAGE)

    module = importlib.util.module_from_spec(spec)
    sys.modules[API_DOCS_PACKAGE] = module
    spec.loader.exec_module(module)


_ensure_api_docs_package()
run_api_docs_cli = cast(
    Callable[[Sequence[str] | None], int],
    importlib.import_module(f"{API_DOCS_PACKAGE}.cli").main,
)


def main(argv: Sequence[str] | None = None) -> int:
    return run_api_docs_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
