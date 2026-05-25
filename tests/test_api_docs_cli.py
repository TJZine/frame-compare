"""Behavior tests for ``scripts.api_docs.cli``."""
# pyright: reportMissingImports=false

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_cli_check_reports_success_and_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    api_docs_cli = importlib.import_module("api_docs.cli")

    generated = "# API Reference\n\nstable\n"
    output = tmp_path / "api.md"
    output.write_text(generated, encoding="utf-8")

    def _generate_markdown(
        *, project_root: Path, module_cache: dict[Path, object]
    ) -> tuple[str, list[str]]:
        assert project_root == tmp_path.resolve()
        assert module_cache == {}
        return generated, []

    monkeypatch.setattr(api_docs_cli, "generate_markdown", _generate_markdown)

    success_code = api_docs_cli.main(
        ["--project-root", str(tmp_path), "--output", str(output), "--check"]
    )
    success_streams = capsys.readouterr()

    output.write_text("# stale\n", encoding="utf-8")
    mismatch_code = api_docs_cli.main(
        ["--project-root", str(tmp_path), "--output", str(output), "--check"]
    )
    mismatch_streams = capsys.readouterr()

    assert success_code == 0
    assert success_streams.err == ""
    assert mismatch_code == 2
    assert f"STALE: {output.resolve()} differs from generated\n" == mismatch_streams.err
