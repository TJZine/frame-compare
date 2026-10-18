"""Layout contracts shared by run sections and interactive prompts."""

import io

import pytest
from rich.console import Console
from rich.text import Text

from frame_compare.utils.terminal_sections import Section, section_title


@pytest.mark.parametrize("width", [48, 80, 200])
def test_section_wraps_values_at_fixed_column_and_caps_width(width: int) -> None:
    stream = io.StringIO()
    console = Console(file=stream, width=width, no_color=True)
    value = " ".join(f"word{index}" for index in range(45))
    section = Section(section_title("Sources"))
    section.add_row("  path", Text(value))
    section.print(console)
    lines = stream.getvalue().splitlines()
    assert lines[0] == lines[-1] == ""
    assert lines[1] == "╭─ Sources"
    assert lines[-2] == "╰─"
    body = lines[2:-2]
    assert body[0].startswith("│   path")
    assert all(line.startswith("│ " + " " * 16) for line in body[1:])
    assert all(len(line) <= min(width, 120) for line in lines)
    assert " ".join(line[18:].strip() for line in body) == value


def test_list_notes_and_blank_rows_keep_rail_and_literal_values() -> None:
    stream = io.StringIO()
    section = Section(section_title("Audio alignment"))
    section.add_line(Text("[bold]literal[/bold] " + "long " * 12))
    section.add_line()
    section.add_note("attention " * 10)
    section.print(Console(file=stream, width=38))
    output = stream.getvalue()
    assert "│ [bold]literal[/bold]" in output
    assert "\n│\n" in output
    assert "│ ! attention" in output
    assert all(line.startswith(("│", "╭", "╰")) for line in output.splitlines() if line)
    assert all(len(line) <= 38 for line in output.splitlines())


def test_ascii_section_and_prompt_preserve_literal_suffix() -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="ascii")
    console = Console(file=stream, width=80)
    section = Section(section_title("> Publish to slow.pics?"))
    section.add_row("report", Text("[report].html"))
    section.add_line()

    def ask(question: str) -> bool:
        console.print(Text(question + " [y/N]: n"))
        return False

    assert section.prompt(console, "Upload to unlisted slow.pics?", ask) is False
    stream.flush()
    output = raw.getvalue().decode("ascii")
    assert output.startswith("\n+- > Publish to slow.pics?\n")
    assert "| report          [report].html" in output
    assert "| Upload to unlisted slow.pics? [y/N]: n\n+-\n\n" in output
