from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, cast

import pytest


@pytest.fixture(scope="module")
def vt_module() -> Any:
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "validate_traceability.py"
    spec = importlib.util.spec_from_file_location("validate_traceability", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_refs_planned_detection_is_per_span(vt_module: Any) -> None:
    vt = cast(Any, vt_module)
    lines = [
        "`tests/a.py` PLANNED: `tests/b.py`",
        "PLANNED: `tests/c.py` `tests/d.py`",
        "`frame-plan-module.md`",
    ]

    refs = vt.dedupe_refs(vt.extract_refs(lines))
    tests = sorted([r for r in refs if r.kind == "test"], key=lambda r: r.ref)
    modules = [r for r in refs if r.kind == "module_spec"]

    assert [r.ref for r in tests] == ["tests/a.py", "tests/b.py", "tests/c.py", "tests/d.py"]
    assert [r.planned for r in tests] == [False, True, True, True]
    assert len(modules) == 1
    assert modules[0].ref == "frame-plan-module.md"


def test_extract_refs_normalizes_windows_separators_for_tests(vt_module: Any) -> None:
    vt = cast(Any, vt_module)
    refs = vt.extract_refs(["PLANNED: `tests\\\\vs\\\\test_loader.py`"])
    assert len(refs) == 1
    assert refs[0].kind == "test"
    assert refs[0].ref == "tests/vs/test_loader.py"
    assert refs[0].planned is True


def test_extract_refs_ignores_non_artifact_code_spans(vt_module: Any) -> None:
    vt = cast(Any, vt_module)
    refs = vt.extract_refs(
        [
            "`--check`",
            "`tests/a.py, tests/b.py`",
            "`docs/somewhere.md`",
            "`tests/a.py`",
        ]
    )
    assert [r.ref for r in refs] == ["tests/a.py"]


def test_dedupe_refs_keeps_lowest_line_no_and_planned_distinct(vt_module: Any) -> None:
    vt = cast(Any, vt_module)
    refs = vt.extract_refs(
        [
            "`tests/a.py`",
            "PLANNED: `tests/a.py`",
            "`tests/a.py`",
        ]
    )
    deduped = vt.dedupe_refs(refs)
    by_key = {(r.kind, r.ref, r.planned): r.line_no for r in deduped}
    assert by_key[("test", "tests/a.py", False)] == 1
    assert by_key[("test", "tests/a.py", True)] == 2


def test_validate_test_function_requires_exact_def(
    vt_module: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vt = cast(Any, vt_module)

    repo_tests = tmp_path / "tests"
    scaffold_tests = tmp_path / "scaffold"
    repo_tests.mkdir()
    scaffold_tests.mkdir()

    test_file = repo_tests / "render" / "test_report.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        "\n".join(
            [
                "def test_report_html() -> None:",
                "    pass",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(vt, "REPO_TESTS_DIR", repo_tests)
    monkeypatch.setattr(vt, "SCAFFOLD_TESTS_DIR", scaffold_tests)

    ref = vt.TraceRef(
        kind="test", ref="tests/render/test_report.py::test_report", planned=False, line_no=7
    )
    ok, msg = vt.validate_test(ref)
    assert ok is False
    assert msg.startswith(
        "✗ tests/render/test_report.py::test_report NOT FOUND (line 7): function test_report missing in "
    )
