from pathlib import Path


def _first_significant_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        return stripped
    return ""


def test_install_from_source_param_block_is_first_statement() -> None:
    script_path = Path("tools/windows_portable/install-from-source.ps1")
    script_text = script_path.read_text(encoding="utf-8")
    assert _first_significant_line(script_text).startswith("Param(")


def test_install_from_source_avoids_pscore_only_windows_variable() -> None:
    script_path = Path("tools/windows_portable/install-from-source.ps1")
    script_text = script_path.read_text(encoding="utf-8")
    assert "$IsWindows" not in script_text
