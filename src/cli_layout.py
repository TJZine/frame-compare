"""Data-driven CLI layout rendering utilities."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from rich.console import Console
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import BarColumn, Progress, ProgressColumn, Task, TextColumn


class CliLayoutError(RuntimeError):
    """Raised when the CLI layout specification is invalid."""


# Regular expression used to identify key tokens.
_KEY_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")


@dataclass
class LayoutTheme:
    colors: Dict[str, str]
    symbols: Dict[str, str]
    units: Dict[str, Any]


@dataclass
class LayoutOptions:
    two_column_min_cols: int
    blank_line_between_sections: bool
    path_ellipsis: str
    truncate_right_label_min_cols: int


@dataclass
class JsonTailConfig:
    pretty_on_flag: str
    must_be_last: bool = True


@dataclass
class CliLayout:
    version: str
    theme: LayoutTheme
    options: LayoutOptions
    sections: List[Dict[str, Any]]
    folding: Dict[str, Any]
    json_tail: JsonTailConfig


def _require_keys(mapping: Mapping[str, Any], keys: Iterable[str], *, context: str) -> None:
    missing = [key for key in keys if key not in mapping]
    if missing:
        joined = ", ".join(missing)
        raise CliLayoutError(f"Missing keys for {context}: {joined}")


def load_cli_layout(path: Path) -> CliLayout:
    """Load and validate the CLI layout JSON document."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - surfaced via tests
        raise CliLayoutError(f"Failed to parse layout JSON: {exc}") from exc
    except OSError as exc:  # pragma: no cover - surfaced via tests
        raise CliLayoutError(f"Unable to read layout JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise CliLayoutError("Layout JSON must be an object")

    _require_keys(raw, ("version", "theme", "layout", "sections", "folding", "json_tail"), context="layout root")

    theme_raw = raw["theme"]
    if not isinstance(theme_raw, dict):
        raise CliLayoutError("theme must be an object")
    _require_keys(theme_raw, ("colors", "symbols", "units"), context="theme")
    colors = theme_raw["colors"]
    symbols = theme_raw["symbols"]
    units = theme_raw["units"]
    if not isinstance(colors, dict) or not isinstance(symbols, dict) or not isinstance(units, dict):
        raise CliLayoutError("theme colors/symbols/units must be objects")

    options_raw = raw["layout"]
    if not isinstance(options_raw, dict):
        raise CliLayoutError("layout options must be an object")
    _require_keys(options_raw, ("two_column_min_cols", "blank_line_between_sections", "path_ellipsis", "truncate_right_label_min_cols"), context="layout options")

    sections_raw = raw["sections"]
    if not isinstance(sections_raw, list):
        raise CliLayoutError("sections must be a list")
    for index, section in enumerate(sections_raw):
        if not isinstance(section, dict):
            raise CliLayoutError(f"section[{index}] must be an object")
        _require_keys(section, ("id", "type"), context=f"section[{index}]")

    folding = raw["folding"]
    if not isinstance(folding, dict):
        raise CliLayoutError("folding must be an object")

    json_tail_raw = raw["json_tail"]
    if not isinstance(json_tail_raw, dict):
        raise CliLayoutError("json_tail must be an object")
    _require_keys(json_tail_raw, ("pretty_on_flag",), context="json_tail")

    layout = CliLayout(
        version=str(raw["version"]),
        theme=LayoutTheme(colors=dict(colors), symbols=dict(symbols), units=dict(units)),
        options=LayoutOptions(
            two_column_min_cols=int(options_raw["two_column_min_cols"]),
            blank_line_between_sections=bool(options_raw["blank_line_between_sections"]),
            path_ellipsis=str(options_raw["path_ellipsis"]),
            truncate_right_label_min_cols=int(options_raw["truncate_right_label_min_cols"]),
        ),
        sections=list(sections_raw),
        folding=dict(folding),
        json_tail=JsonTailConfig(
            pretty_on_flag=str(json_tail_raw["pretty_on_flag"]),
            must_be_last=bool(json_tail_raw.get("must_be_last", True)),
        ),
    )
    return layout


class LayoutContext:
    """Runtime values exposed to the layout templates."""

    def __init__(self, data: Mapping[str, Any], flags: Mapping[str, Any], *, renderer: "CliLayoutRenderer") -> None:
        self._data = data
        self._flags = flags
        self._renderer = renderer

    def resolve(self, path: str) -> Any:
        if path in self._flags:
            return self._flags[path]
        segments = path.split(".") if path else []
        current: Any = self._data
        for segment in segments:
            if segment == "":
                continue
            if isinstance(current, Mapping):
                current = current.get(segment)
                continue
            if isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
                if segment.isdigit():
                    idx = int(segment)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        current = None
                    continue
            if segment == "e":
                return self._renderer.apply_path_ellipsis(str(current))
            current = getattr(current, segment, None)
        return current


class CliLayoutRenderer:
    """Render CLI sections according to a layout specification."""

    def __init__(
        self,
        layout: CliLayout,
        console: Console,
        *,
        quiet: bool = False,
        verbose: bool = False,
        no_color: bool = False,
    ) -> None:
        self.layout = layout
        self.console = console
        self.quiet = quiet
        self.verbose = verbose
        self.no_color = no_color
        self._progress_state: Dict[str, Dict[str, Any]] = {}
        self._cached_width: Optional[int] = None
        self._rendered_section_ids: List[str] = []
        self._active_values: Mapping[str, Any] = {}
        self._active_flags: Mapping[str, Any] = {}
        self._symbols = dict(layout.theme.symbols)
        if no_color:
            self._symbols = {
                key: layout.theme.symbols.get(f"ascii_{key}", layout.theme.symbols.get(key, ""))
                for key in layout.theme.symbols
                if not key.startswith("ascii_")
            }
        self._progress_blocks: Dict[str, Mapping[str, Any]] = {}
        for section in layout.sections:
            if section.get("type") != "group":
                continue
            for block in section.get("blocks", []):
                if isinstance(block, Mapping) and block.get("type") == "progress" and block.get("progress_id"):
                    self._progress_blocks[str(block["progress_id"])] = block

    # ------------------------------------------------------------------
    # High-level public API
    # ------------------------------------------------------------------

    @property
    def symbols(self) -> Mapping[str, str]:
        return dict(self._symbols)

    def update_progress_state(self, progress_id: str, *, state: Mapping[str, Any]) -> None:
        self._progress_state.setdefault(progress_id, {}).update(state)

    # ------------------------------------------------------------------
    # Template rendering utilities
    # ------------------------------------------------------------------

    def apply_path_ellipsis(self, value: str, *, width: Optional[int] = None) -> str:
        if value is None:
            return ""
        text = str(value)
        limit = width or self.console.size.width or 80
        limit = max(10, limit - 4)
        if len(text) <= limit:
            return text
        if self.layout.options.path_ellipsis == "middle":
            head = max(1, limit // 2 - 1)
            tail = max(1, limit - head - 1)
            return f"{text[:head]}…{text[-tail:]}"
        return text[:limit - 1] + "…"

    def _format_value(self, value: Any, fmt: Optional[str]) -> str:
        if value is None:
            return ""
        if isinstance(value, (int, float)) and fmt:
            return format(value, fmt)
        if isinstance(value, int) and not fmt:
            if self.layout.theme.units.get("thousands_sep"):
                return f"{value:,}"
            return str(value)
        if isinstance(value, float) and not fmt:
            decimals = int(self.layout.theme.units.get("seconds_decimals", 2))
            return f"{value:.{decimals}f}"
        return str(value)

    def _apply_filter(self, value: Any, filter_name: str) -> Any:
        if filter_name == "none":
            return value if value not in (None, "") else "none"
        if filter_name == "unchanged":
            if value in (None, ""):
                return "unchanged"
            return value
        if filter_name == "tallest":
            if not value:
                return "tallest"
            return value
        if filter_name == "ellipsis":
            return self.apply_path_ellipsis(str(value))
        return value

    def _render_token(self, token: str, context: LayoutContext) -> str:
        token = token.strip()
        if not token:
            return ""

        # Conditional expression token? support syntax a?b:c
        cond_index = self._find_conditional_split(token)
        if cond_index is not None:
            cond, true_expr, false_expr = cond_index
            condition_result = self._evaluate_condition(cond, context)
            branch = true_expr if condition_result else false_expr
            if branch.startswith("`") and branch.endswith("`"):
                inner = branch[1:-1]
                template = self._translate_dollar_template(inner, context)
                return template
            return self._render_text(branch, context)

        fmt_spec: Optional[str] = None
        optional_value = False
        if token.endswith("?") and ":" not in token:
            token = token[:-1]
            optional_value = True

        if ":" in token:
            path_part, fmt_spec = token.split(":", 1)
        else:
            path_part = token

        filters: List[str] = []
        if "|" in path_part:
            path_part, *filters = path_part.split("|")
        value = context.resolve(path_part)

        for filter_name in filters:
            value = self._apply_filter(value, filter_name)

        if optional_value and value in (None, ""):
            return ""
        return self._format_value(value, fmt_spec)

    def _render_text(self, template: str, context: LayoutContext) -> str:
        result: List[str] = []
        index = 0
        length = len(template)

        while index < length:
            char = template[index]
            if char != "{":
                result.append(char)
                index += 1
                continue

            token, next_index = self._extract_token(template, index + 1)
            if token is None:
                result.append(char)
                index += 1
                continue
            result.append(self._render_token(token, context))
            index = next_index

        return "".join(result)

    def _extract_token(self, text: str, start: int) -> tuple[Optional[str], int]:
        depth = 0
        index = start
        while index < len(text):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                if depth == 0:
                    return text[start:index], index + 1
                depth -= 1
            index += 1
        return None, len(text)

    def _translate_dollar_template(self, template: str, context: LayoutContext) -> str:
        # Replace ${a.b} style placeholders
        def replace(match: re.Match[str]) -> str:
            path = match.group(1)
            value = context.resolve(path)
            if value is None:
                return ""
            return str(value)

        dollar_re = re.compile(r"\$\{([^{}]+)\}")
        return dollar_re.sub(replace, template)

    def _find_conditional_split(self, token: str) -> Optional[Tuple[str, str, str]]:
        question_index = self._find_unescaped_question(token)
        if question_index is None:
            return None
        left = token[:question_index]
        remainder = token[question_index + 1 :]
        colon_index = self._find_matching_colon(remainder)
        if colon_index is None:
            return None
        true_expr = remainder[:colon_index]
        false_expr = remainder[colon_index + 1 :]
        return left.strip(), true_expr.strip(), false_expr.strip()

    def _find_unescaped_question(self, text: str) -> Optional[int]:
        depth = 0
        brace_depth = 0
        in_backtick = False
        for index, char in enumerate(text):
            if char == "`":
                in_backtick = not in_backtick
                continue
            if in_backtick:
                continue
            if char == "{":
                brace_depth += 1
                continue
            if char == "}":
                brace_depth = max(0, brace_depth - 1)
                continue
            if brace_depth > 0:
                continue
            if char == "?" and depth == 0:
                return index
            if char == "(":
                depth += 1
            elif char == ")" and depth > 0:
                depth -= 1
        return None

    def _find_matching_colon(self, text: str) -> Optional[int]:
        depth = 0
        brace_depth = 0
        in_backtick = False
        for index, char in enumerate(text):
            if char == "`":
                in_backtick = not in_backtick
                continue
            if in_backtick:
                continue
            if char == "{":
                brace_depth += 1
                continue
            if char == "}":
                brace_depth = max(0, brace_depth - 1)
                continue
            if brace_depth > 0:
                continue
            if char == "?":
                depth += 1
            elif char == ":":
                if depth == 0:
                    return index
                depth -= 1
        return None

    def _evaluate_condition(self, expr: str, context: LayoutContext) -> bool:
        expression = expr.strip()
        if not expression:
            return False

        prepared = self._prepare_condition(expression)
        namespace = {
            "resolve": context.resolve,
            "True": True,
            "False": False,
            "None": None,
        }
        try:
            result = eval(prepared, {"__builtins__": {}}, namespace)
        except Exception:
            return False
        return bool(result)

    def _prepare_condition(self, expr: str) -> str:
        cleaned = expr.replace("&&", " and ").replace("||", " or ")
        tokens: List[str] = []
        index = 0
        while index < len(cleaned):
            char = cleaned[index]
            if char.isalpha() or char == "_":
                start = index
                while index < len(cleaned) and (cleaned[index].isalnum() or cleaned[index] in {"_", "."}):
                    index += 1
                token = cleaned[start:index]
                if token in {"and", "or", "not", "True", "False", "None"}:
                    tokens.append(token)
                else:
                    tokens.append(f"resolve('{token}')")
                continue
            if char == "!":
                if index + 1 < len(cleaned) and cleaned[index + 1] == "=":
                    tokens.append("!=")
                    index += 2
                    continue
                tokens.append("not ")
                index += 1
                continue
            tokens.append(char)
            index += 1
        return "".join(tokens)

    def render_template(self, template: str, values: Mapping[str, Any], flags: Mapping[str, Any]) -> str:
        context = LayoutContext(values, flags, renderer=self)
        return self._render_text(template, context)

    # ------------------------------------------------------------------
    # Section rendering -------------------------------------------------
    # ------------------------------------------------------------------

    def render_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        if self.quiet and section.get("id") not in {"banner"}:
            return
        condition = section.get("when")
        if condition:
            context = LayoutContext(values, flags, renderer=self)
            if not self._evaluate_condition(condition, context):
                return
        if (
            self.layout.options.blank_line_between_sections
            and self._rendered_section_ids
            and section.get("id") not in {"banner"}
        ):
            self.console.print()
        section_type = section["type"]
        render_method = getattr(self, f"_render_{section_type}_section", None)
        if render_method is None:
            raise CliLayoutError(f"Unsupported section type: {section_type}")
        self._active_values = values
        self._active_flags = flags
        render_method(section, values, flags)
        self._rendered_section_ids.append(str(section.get("id")))

    # Section renderers -------------------------------------------------

    def _render_line_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        template = section.get("template", "")
        text = self.render_template(template, values, flags)
        if text:
            self.console.print(text)

    def _render_box_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        title = section.get("title", "")
        lines = section.get("lines", [])
        if not isinstance(lines, list):
            raise CliLayoutError("box.lines must be a list")
        rendered = [self.render_template(line, values, flags) for line in lines]
        content = "\n".join(rendered)
        panel = Panel(content, title=title, expand=False)
        self.console.print(panel)

    def _render_list_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        title_badge = section.get("title_badge")
        if title_badge:
            self.console.print(title_badge)
        items = section.get("items", [])
        if not isinstance(items, list):
            raise CliLayoutError("list.items must be a list")
        rendered_items = [self.render_template(item, values, flags) for item in items if item]
        two_column = (
            len(rendered_items) > 3
            and (self.console.size.width or 0) >= self.layout.options.two_column_min_cols
        )
        if two_column and rendered_items:
            self.console.print(Columns(rendered_items, equal=True, expand=False))
        else:
            for rendered in rendered_items:
                if rendered:
                    self.console.print(rendered)

    def _render_group_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        title_badge = section.get("title_badge")
        if title_badge:
            self.console.print(title_badge)
        blocks = section.get("blocks", [])
        if not isinstance(blocks, list):
            raise CliLayoutError("group.blocks must be a list")
        for block in blocks:
            when_expr = block.get("when")
            if when_expr:
                context = LayoutContext(values, flags, renderer=self)
                if not self._evaluate_condition(when_expr, context):
                    continue
            block_type = block.get("type") or "lines"
            if block_type == "progress":
                continue
            subtitle = block.get("subtitle")
            if subtitle:
                self.console.print(subtitle)
            for line in block.get("lines", []):
                rendered = self.render_template(line, values, flags)
                if rendered:
                    self.console.print(rendered)

    def _render_passthrough_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        title_badge = section.get("title_badge")
        if title_badge:
            self.console.print(title_badge)

    def _render_table_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        title_badge = section.get("title_badge")
        if title_badge:
            self.console.print(title_badge)
        group_by = section.get("group_by")
        row_template = section.get("row_template", "")
        rows = values.get(section.get("id"), []) if isinstance(values, Mapping) else []
        table = Table(show_header=False, box=None)
        for row in rows:
            context_values = dict(values)
            context_values.update(row)
            rendered = self.render_template(row_template, context_values, flags)
            table.add_row(Text(rendered))
        self.console.print(table)

    # ------------------------------------------------------------------
    # Progress helpers --------------------------------------------------
    # ------------------------------------------------------------------

    def get_progress_block(self, progress_id: str) -> Optional[Mapping[str, Any]]:
        return self._progress_blocks.get(progress_id)

    def bind_context(self, values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        """Record the active context for later progress template evaluation."""

        self._active_values = values
        self._active_flags = flags

    def create_progress(self, progress_id: str, *, transient: bool = False) -> Progress:
        block = self.get_progress_block(progress_id)
        if block is None:
            raise CliLayoutError(f"Unknown progress block: {progress_id}")

        accent_style = self.layout.theme.colors.get("accent", "") if not self.no_color else ""

        columns: List[ProgressColumn] = [
            TextColumn("{task.description}", style=accent_style, justify="left"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}", justify="right"),
        ]

        right_label = str(block.get("right_label", ""))
        if right_label:
            columns.append(_TemplateProgressColumn(self, progress_id, right_label))

        transient_flag = bool(block.get("transient", transient))
        return Progress(*columns, console=self.console, transient=transient_flag)


class _TemplateProgressColumn(ProgressColumn):
    def __init__(self, renderer: CliLayoutRenderer, progress_id: str, template: str) -> None:
        super().__init__()
        self.renderer = renderer
        self.progress_id = progress_id
        self.template = template

    def render(self, task: Task) -> Text:
        state = dict(self.renderer._progress_state.get(self.progress_id, {}))
        state.setdefault("current", task.completed)
        state.setdefault("total", task.total)
        state.setdefault("percentage", task.percentage)
        context_values = dict(self.renderer._active_values)
        context_values.setdefault("progress", state)
        rendered = self.renderer.render_template(self.template, context_values, self.renderer._active_flags)
        return Text(rendered)


__all__ = [
    "CliLayout",
    "CliLayoutError",
    "CliLayoutRenderer",
    "JsonTailConfig",
    "LayoutOptions",
    "LayoutTheme",
    "load_cli_layout",
]
