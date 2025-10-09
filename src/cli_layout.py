"""Data-driven CLI layout rendering utilities."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import json
import os
import re
import shutil
from itertools import zip_longest
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from rich.console import Console
from rich.progress import BarColumn, Progress, ProgressColumn, Task, TextColumn


class CliLayoutError(RuntimeError):
    """Raised when the CLI layout specification is invalid."""


# Regular expression used to identify key tokens.
_KEY_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")

_ANSI_RESET = "\x1b[0m"

_SAFE_FUNCTION_TOKENS = {"abs", "min", "max"}

_COLOR_BLIND_OVERRIDES: Dict[str, str] = {
    "bool_true": "cyan",
    "bool_false": "orange",
    "number_ok": "cyan",
    "number_warn": "orange",
    "number_bad": "purple",
    "success": "cyan",
    "warn": "orange",
    "error": "purple",
}

_SECTION_ACCENT_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("PREPARE", "accent_prepare"),
    ("ANALYZE", "accent_analyze"),
    ("RENDER", "accent_render"),
    ("PUBLISH", "accent_publish"),
)


_ALLOWED_BOOL_OPS: Tuple[type[ast.boolop], ...] = (ast.And, ast.Or)
_ALLOWED_BIN_OPS: Tuple[type[ast.operator], ...] = (
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.FloorDiv,
)
_ALLOWED_UNARY_OPS: Tuple[type[ast.unaryop], ...] = (ast.Not, ast.UAdd, ast.USub)
_ALLOWED_COMPARE_OPS: Tuple[type[ast.cmpop], ...] = (
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)


def _validate_safe_expression(node: ast.AST, *, allowed_calls: Mapping[str, Any], allowed_names: Mapping[str, Any]) -> None:
    """
    Validate that an AST only contains a restricted set of safe expression constructs.
    
    This function walks the provided AST and enforces a whitelist of allowed node kinds:
    boolean, binary and unary operations, comparisons, conditional (if-)expressions,
    direct function calls where the callee is a simple name (no attribute or lambda),
    simple name references, numeric/string/bool/None constants, and list/tuple literals.
    Calls with keyword arguments, complex call targets, unsupported constants or any
    other node kinds are rejected.
    
    Parameters:
        node (ast.AST): The root AST node to validate.
        allowed_calls (Mapping[str, Any]): Mapping of allowed function names to their
            permitted meanings; a call is allowed only if the function name appears
            in this mapping.
        allowed_names (Mapping[str, Any]): Mapping of allowed identifier names to
            their permitted meanings; name nodes are allowed only if present here.
    
    Raises:
        ValueError: If the AST contains any disallowed node, operation, name, call,
            or unsupported constant value.
    """

    def _check(inner: ast.AST) -> None:
        """
        Validate an AST node subtree to ensure it contains only permitted expression constructs.
        
        This function recursively inspects the provided AST node and raises a ValueError if it encounters any node type, operator, name, call target, constant, or argument form that is not allowed by the surrounding validation context (e.g., the `allowed_calls` and `allowed_names` sets in the enclosing scope).
        
        Parameters:
            inner (ast.AST): The AST node to validate.
        
        Raises:
            ValueError: If the node contains disallowed operations, names, calls, keywords, constant types, or any unsupported AST elements.
        """
        if isinstance(inner, ast.Expression):
            _check(inner.body)
            return
        if isinstance(inner, ast.BoolOp):
            if not isinstance(inner.op, _ALLOWED_BOOL_OPS):
                raise ValueError("Boolean operation not allowed")
            for value in inner.values:
                _check(value)
            return
        if isinstance(inner, ast.BinOp):
            if not isinstance(inner.op, _ALLOWED_BIN_OPS):
                raise ValueError("Binary operation not allowed")
            _check(inner.left)
            _check(inner.right)
            return
        if isinstance(inner, ast.UnaryOp):
            if not isinstance(inner.op, _ALLOWED_UNARY_OPS):
                raise ValueError("Unary operation not allowed")
            _check(inner.operand)
            return
        if isinstance(inner, ast.Compare):
            for op in inner.ops:
                if not isinstance(op, _ALLOWED_COMPARE_OPS):
                    raise ValueError("Comparison not allowed")
            _check(inner.left)
            for comparator in inner.comparators:
                _check(comparator)
            return
        if isinstance(inner, ast.IfExp):
            _check(inner.test)
            _check(inner.body)
            _check(inner.orelse)
            return
        if isinstance(inner, ast.Call):
            if not isinstance(inner.func, ast.Name):
                raise ValueError("Only direct function calls are allowed")
            if inner.func.id not in allowed_calls:
                raise ValueError(f"Call to '{inner.func.id}' not permitted")
            if inner.keywords:
                raise ValueError("Keyword arguments are not allowed")
            for arg in inner.args:
                _check(arg)
            return
        if isinstance(inner, ast.Name):
            if inner.id not in allowed_names:
                raise ValueError(f"Name '{inner.id}' is not allowed in expressions")
            return
        if isinstance(inner, ast.Constant):
            if isinstance(inner.value, (int, float, str, bool)) or inner.value is None:
                return
            raise ValueError("Unsupported constant value")
        if isinstance(inner, (ast.List, ast.Tuple)):
            for element in inner.elts:
                _check(element)
            return
        raise ValueError(f"Unsupported expression element: {ast.dump(inner, include_attributes=False)}")

    _check(node)


class _AnsiColorMapper:
    """Translate theme color tokens into ANSI escape sequences."""

    _TOKEN_CODES_16 = {
        "cyan": 36,
        "blue": 34,
        "green": 32,
        "yellow": 33,
        "orange": 33,
        "red": 31,
        "grey": 37,
        "gray": 37,
        "white": 37,
        "black": 30,
        "magenta": 35,
        "purple": 35,
    }

    _TOKEN_CODES_256 = {
        "cyan": 51,
        "blue": 75,
        "green": 84,
        "yellow": 184,
        "orange": 214,
        "red": 203,
        "grey": 240,
        "gray": 240,
        "white": 15,
        "black": 0,
        "magenta": 201,
        "purple": 177,
    }

    def __init__(self, *, no_color: bool) -> None:
        env_no_color = bool(os.environ.get("NO_COLOR"))
        self.no_color = no_color or env_no_color
        self._capability = "none"
        if not self.no_color:
            self._enable_windows_vt_mode()
            self._capability = self._detect_capability()

    @staticmethod
    def _enable_windows_vt_mode() -> None:
        if os.name != "nt":
            return
        try:
            import colorama

            colorama.just_fix_windows_console()
            colorama.init(strip=False, convert=True)
            return
        except Exception:  # pragma: no cover - optional dependency
            pass
        try:  # pragma: no cover - platform dependent
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            # If enabling VT mode fails we silently continue; the console will
            # simply ignore the escape codes.
            pass

    @staticmethod
    def _detect_capability() -> str:
        colorterm = os.environ.get("COLORTERM", "").lower()
        if any(token in colorterm for token in ("truecolor", "24bit")):
            return "256"
        term = os.environ.get("TERM", "").lower()
        if "256color" in term or "truecolor" in term:
            return "256"
        return "16"

    def apply(self, token: str, text: str) -> str:
        if not text or self.no_color:
            return text
        sgr = self._lookup(token)
        if not sgr:
            return text
        return f"{sgr}{text}{_ANSI_RESET}"

    def _lookup(self, token: str) -> str:
        token = (token or "").strip()
        if not token:
            return ""
        parts = token.lower().split(".")
        color = parts[0] if parts else ""
        modifiers = {part for part in parts[1:] if part}

        if self._capability == "256":
            code = self._TOKEN_CODES_256.get(color)
            if code is None:
                return ""
            attrs: List[str] = []
            if "bold" in modifiers:
                attrs.append("1")
            if "dim" in modifiers:
                attrs.append("2")
            attrs.append(f"38;5;{code}")
            return f"\x1b[{';'.join(attrs)}m"

        if self._capability == "16":
            base = self._TOKEN_CODES_16.get(color)
            if base is None:
                return ""
            if "bright" in modifiers and 30 <= base <= 37:
                base += 60
            attrs = []
            if "bold" in modifiers:
                attrs.append("1")
            if "dim" in modifiers:
                attrs.append("2")
            attrs.append(str(base))
            return f"\x1b[{';'.join(attrs)}m"

        return ""


@dataclass
class LayoutTheme:
    colors: Dict[str, str]
    symbols: Dict[str, str]
    units: Dict[str, Any]
    options: Dict[str, Any] = field(default_factory=dict)


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
    highlights: List["HighlightRule"]


@dataclass
class HighlightRule:
    when: str
    path: str
    role: Optional[str] = None
    value: Any = None
    true_role: Optional[str] = None
    false_role: Optional[str] = None


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
    theme_options_raw = theme_raw.get("options", {})
    if theme_options_raw and not isinstance(theme_options_raw, dict):
        raise CliLayoutError("theme.options must be an object if provided")

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

    highlights_raw = raw.get("highlights", [])
    if not isinstance(highlights_raw, list):
        raise CliLayoutError("highlights must be a list when provided")
    highlights: List[HighlightRule] = []
    for index, rule_raw in enumerate(highlights_raw):
        if not isinstance(rule_raw, dict):
            raise CliLayoutError(f"highlights[{index}] must be an object")
        when = str(rule_raw.get("when", "")).strip()
        path = str(rule_raw.get("path", "")).strip()
        if not when or not path:
            raise CliLayoutError(f"highlights[{index}] must include 'when' and 'path'")
        role = rule_raw.get("role")
        value = rule_raw.get("value")
        true_role = rule_raw.get("true_role")
        false_role = rule_raw.get("false_role")
        if when.lower() == "isbool":
            if true_role is None or false_role is None:
                raise CliLayoutError(f"highlights[{index}] requires true_role/false_role for 'isbool'")
        elif rule_raw.get("role") is None:
            raise CliLayoutError(f"highlights[{index}] requires 'role'")
        highlights.append(
            HighlightRule(
                when=when,
                path=path,
                role=str(role) if role is not None else None,
                value=value,
                true_role=str(true_role) if true_role is not None else None,
                false_role=str(false_role) if false_role is not None else None,
            )
        )

    layout = CliLayout(
        version=str(raw["version"]),
        theme=LayoutTheme(
            colors=dict(colors),
            symbols=dict(symbols),
            units=dict(units),
            options=dict(theme_options_raw) if isinstance(theme_options_raw, dict) else {},
        ),
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
        highlights=highlights,
    )
    return layout


class LayoutContext:
    """Runtime values exposed to the layout templates."""

    def __init__(self, data: Mapping[str, Any], flags: Mapping[str, Any], *, renderer: "CliLayoutRenderer") -> None:
        self._data = data
        self._flags = flags
        self._renderer = renderer

    def resolve(self, path: str) -> Any:
        """
        Resolve a dot-separated path against the renderer-bound context data or flags.
        
        Looks up the given path in the following order and semantics:
        - If `path` exactly matches a key in the active flags, return that flag value.
        - Otherwise, traverse the renderer's bound data using dot-separated segments.
        - Numeric segments index into list/tuple-like sequences (0-based).
        - The special segment `e` returns the renderer's path-ellipsis representation of the current value.
        - Segments that are empty are ignored.
        - Any segment that starts with `_` or contains `__` (except the literal `e`) halts traversal and returns `None` to prevent access to private/internal attributes.
        - If a lookup fails at any step, `None` is returned.
        
        Parameters:
            path (str): Dot-separated path string to resolve; an empty string returns the root data object.
        
        Returns:
            The resolved value from flags or data, or `None` if the path cannot be resolved or is disallowed.
        """
        if path in self._flags:
            return self._flags[path]
        segments = path.split(".") if path else []
        current: Any = self._data
        for segment in segments:
            if segment == "":
                continue
            if (segment.startswith("_") or "__" in segment) and segment != "e":
                return None
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
        self._color_mapper = _AnsiColorMapper(no_color=no_color)
        self.no_color = self._color_mapper.no_color
        self._unicode_ok = self._supports_unicode()
        self._progress_state: Dict[str, Dict[str, Any]] = {}
        self._cached_width: Optional[int] = None
        self._rendered_section_ids: List[str] = []
        self._active_values: Mapping[str, Any] = {}
        self._active_flags: Mapping[str, Any] = {}
        self._theme_options = dict(layout.theme.options)
        self._symbols = dict(layout.theme.symbols)
        if self.no_color:
            self._symbols = {
                key: layout.theme.symbols.get(f"ascii_{key}", layout.theme.symbols.get(key, ""))
                for key in layout.theme.symbols
                if not key.startswith("ascii_")
            }
        self._role_tokens = dict(layout.theme.colors)
        self._color_blind_safe = bool(self._theme_options.get("color_blind_safe"))
        if self._color_blind_safe:
            for role, token in _COLOR_BLIND_OVERRIDES.items():
                self._role_tokens.setdefault(role, token)
                self._role_tokens[role] = token
        # Ensure new accent roles fall back gracefully if theme omits them.
        if "accent_subhead" not in self._role_tokens:
            fallback = self._role_tokens.get("accent_render") or self._role_tokens.get("accent") or ""
            self._role_tokens["accent_subhead"] = fallback
        if "rule_dim" not in self._role_tokens:
            self._role_tokens["rule_dim"] = self._role_tokens.get("dim", "grey.dim")

        self._highlight_rules: Dict[str, List[HighlightRule]] = {}
        for rule in layout.highlights:
            self._highlight_rules.setdefault(rule.path, []).append(rule)

        self._progress_blocks: Dict[str, Dict[str, Any]] = {}
        for section in layout.sections:
            if section.get("type") != "group":
                continue
            accent_role = self._resolve_section_accent(section)
            for block in section.get("blocks", []):
                if isinstance(block, Mapping) and block.get("type") == "progress" and block.get("progress_id"):
                    self._progress_blocks[str(block["progress_id"])] = {"block": block, "accent": accent_role}

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

    def _console_width(self) -> int:
        if self._cached_width is not None:
            return self._cached_width
        width = getattr(self.console, "width", None)
        if isinstance(width, int) and width > 0:
            self._cached_width = width
            return self._cached_width
        size = getattr(self.console, "size", None)
        if size is not None:
            width = getattr(size, "width", None)
            if isinstance(width, int) and width > 0:
                self._cached_width = width
                return self._cached_width
        terminal = shutil.get_terminal_size(fallback=(80, 24))
        self._cached_width = max(terminal.columns, 40)
        return self._cached_width

    def _visible_length(self, text: str) -> int:
        return len(_ANSI_ESCAPE_RE.sub("", text))

    def _pad_to_width(self, text: str, width: int) -> str:
        visible = self._visible_length(text)
        if visible >= width:
            return text
        return text + " " * (width - visible)

    def _truncate_visible(self, text: str, width: int) -> str:
        if self._visible_length(text) <= width:
            return text
        plain = _ANSI_ESCAPE_RE.sub("", text)
        if len(plain) <= width:
            return text
        truncated = plain[: max(1, width - 1)] + "…"
        return truncated

    def _colorize(self, role: str, text: str) -> str:
        token = self._role_tokens.get(role, "")
        return self._color_mapper.apply(token, text)

    def _role_style(self, role: Optional[str]) -> Optional[str]:
        if self.no_color or not role:
            return None
        return self._role_tokens.get(role)

    def _rich_style_from_token(self, token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        parts = token.split(".")
        if not parts:
            return None
        color = parts[0]
        modifiers = parts[1:]
        rich_modifiers: List[str] = []
        bright = False
        for modifier in modifiers:
            if modifier == "bright":
                bright = True
            elif modifier == "dim":
                rich_modifiers.append("dim")
            elif modifier == "bold":
                rich_modifiers.append("bold")
            else:
                rich_modifiers.append(modifier.replace(".", " "))
        base_color = color
        if bright:
            if color in {"black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"}:
                base_color = f"bright_{color}"
            elif color in {"grey", "gray"}:
                base_color = "bright_black"
            elif color == "purple":
                base_color = "purple"
                if "bold" not in rich_modifiers:
                    rich_modifiers.append("bold")
            else:
                base_color = color
        rich_modifiers.append(base_color)
        return " ".join(rich_modifiers).strip()

    def _resolve_section_accent(self, section: Mapping[str, Any], badge: Optional[str] = None) -> Optional[str]:
        explicit = section.get("accent_role")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        badge_text = badge or section.get("title_badge") or ""
        if isinstance(badge_text, str):
            for pattern, role in _SECTION_ACCENT_PATTERNS:
                if pattern in badge_text:
                    return role
        if section.get("id") == "banner":
            return "header"
        return None

    def _apply_role_to_chunk(self, role: Optional[str], chunk: str) -> str:
        if not chunk:
            return ""
        if role and not self.no_color:
            return self._colorize(role, chunk)
        return chunk

    def _render_title_badge(self, section: Mapping[str, Any]) -> None:
        badge = section.get("title_badge")
        if not badge:
            return
        role = self._resolve_section_accent(section, badge) or "header"
        self._write(self._colorize(role, badge))

    def _apply_style_spans(self, text: str) -> str:
        if "[[" not in text:
            return text
        result: List[str] = []
        stack: List[str] = []
        index = 0
        length = len(text)
        while index < length:
            next_marker = text.find("[[", index)
            if next_marker == -1:
                result.append(self._apply_role_to_chunk(stack[-1] if stack else None, text[index:]))
                break
            if next_marker > index:
                result.append(self._apply_role_to_chunk(stack[-1] if stack else None, text[index:next_marker]))
            close = text.find("]]", next_marker + 2)
            if close == -1:
                # unmatched marker, treat rest as plain text
                result.append(self._apply_role_to_chunk(stack[-1] if stack else None, text[next_marker:]))
                break
            token = text[next_marker + 2 : close].strip()
            if token == "/":
                if stack:
                    stack.pop()
            elif token:
                stack.append(token)
            index = close + 2
        return "".join(result)

    def _coerce_bool(self, value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "yes", "1", "enabled", "on"}:
                return True
            if lowered in {"false", "no", "0", "disabled", "off"}:
                return False
        return None

    def _to_number(self, value: Any) -> Optional[float]:
        """
        Convert a value to a float when it represents a number.
        
        Accepts booleans (True -> 1.0, False -> 0.0), int/float values, and numeric strings (commas are allowed as thousand separators). Non-convertible values return None.
        
        Parameters:
            value: The input to convert; may be bool, int, float, or str containing a numeric value.
        
        Returns:
            A float parsed from the input, or `None` if the value cannot be converted to a number.
        """
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace(",", ""))
            except ValueError:
                return None
        return None

    def _safe_eval(
        self,
        expression: str,
        namespace: Mapping[str, Any],
        *,
        allowed_call_names: Sequence[str],
    ) -> Any:
        """
        Evaluate a Python expression string after validating it only uses a restricted, whitelisted subset of operations and names.
        
        Parameters:
            expression (str): The expression to validate and evaluate.
            namespace (Mapping[str, Any]): Mapping of names available to the expression during evaluation.
            allowed_call_names (Sequence[str]): Names from `namespace` that are permitted to be called as functions.
        
        Returns:
            Any: The result of evaluating the validated expression.
        
        Raises:
            ValueError: If the expression has invalid syntax or uses disallowed AST constructs or names.
        """
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError("Invalid expression syntax") from exc
        allowed_calls = {name: namespace[name] for name in allowed_call_names if name in namespace}
        _validate_safe_expression(tree, allowed_calls=allowed_calls, allowed_names=namespace)
        compiled = compile(tree, "<cli-layout-expression>", "eval")
        return eval(compiled, {"__builtins__": {}}, namespace)

    def _evaluate_expression(self, expression: str, context: LayoutContext) -> Any:
        """
        Evaluate a template expression in the given layout context and return its computed value.
        
        Parameters:
        	expression (str): An expression string that may reference data via the context (e.g., names resolved by LayoutContext.resolve).
        	context (LayoutContext): Context used to resolve names and provide runtime values for the expression.
        
        Returns:
        	The evaluated result of the expression, or `None` if evaluation fails or the expression is invalid.
        """
        prepared = self._prepare_condition(expression)
        namespace: Dict[str, Any] = {
            "resolve": context.resolve,
            "abs": abs,
            "min": min,
            "max": max,
        }
        try:
            return self._safe_eval(
                prepared,
                namespace,
                allowed_call_names=("resolve", "abs", "min", "max"),
            )
        except Exception:
            return None

    def _resolve_highlight_operand(self, operand: Any, context: LayoutContext) -> Any:
        if isinstance(operand, str):
            text = operand.strip()
            if text.startswith("{") and text.endswith("}"):
                inner = text[1:-1].strip()
                if inner:
                    return self._evaluate_expression(inner, context)
        return operand

    def _evaluate_highlight_rule(
        self, rule: HighlightRule, value: Any, context: LayoutContext
    ) -> Optional[str]:
        when = rule.when.lower()
        if when == "isbool":
            coerced = self._coerce_bool(value)
            if coerced is None:
                return None
            return rule.true_role if coerced else rule.false_role

        comparator_raw = self._resolve_highlight_operand(rule.value, context)
        value_num = self._to_number(value)
        comparator_num = self._to_number(comparator_raw)
        if value_num is None or comparator_num is None:
            return None

        if when == "gt" and value_num > comparator_num:
            return rule.role or None
        if when == "lt" and value_num < comparator_num:
            return rule.role or None
        if when == "abs_gt" and abs(value_num) > comparator_num:
            return rule.role or None
        if when == "abs_gte" and abs(value_num) >= comparator_num:
            return rule.role or None
        if when == "abs_lt" and abs(value_num) < comparator_num:
            return rule.role or None
        return None

    def _pick_highlight(self, path: str, value: Any, context: LayoutContext) -> Optional[str]:
        if not path:
            return None
        rules = self._highlight_rules.get(path)
        if not rules:
            return None
        for rule in rules:
            role = self._evaluate_highlight_rule(rule, value, context)
            if role:
                return role
        return None

    def _style_key_tokens(self, text: str) -> str:
        if not text or self.no_color:
            return text

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            return f"{self._colorize('accent', key)}="

        def colon_repl(match: re.Match[str]) -> str:
            key = match.group(1)
            suffix = match.group(2)
            return f"{self._colorize('accent', key)}{suffix}"

        text = re.sub(r"(?<!\S)([A-Za-z0-9_.-]+)=", repl, text)
        text = re.sub(r"(?<!\S)([A-Za-z0-9_.-]+)(:)(?!//)", colon_repl, text)

        def bool_repl(match: re.Match[str]) -> str:
            value = match.group(0)
            lowered = value.lower()
            if lowered in {"yes", "true", "enabled", "ok"}:
                return self._colorize("success", value)
            if lowered in {"no", "false", "disabled"}:
                return self._colorize("warn", value)
            return value

        text = re.sub(r"(?<![A-Za-z0-9_])(yes|no|true|false|enabled|disabled|ok)(?![A-Za-z0-9_])", bool_repl, text, flags=re.IGNORECASE)
        return text

    def _prepare_output(self, text: str, *, highlight: bool = True) -> str:
        if not text:
            return ""
        stripped = text.rstrip()
        if "[[" in stripped:
            stripped = self._apply_style_spans(stripped)
        if highlight:
            stripped = self._style_key_tokens(stripped)
        return stripped

    def _write(self, text: str = "") -> None:
        if text:
            self.console.print(text)
        else:
            self.console.print()

    def apply_path_ellipsis(self, value: str, *, width: Optional[int] = None) -> str:
        if value is None:
            return ""
        text = str(value)
        limit = width or self._console_width()
        limit = max(10, limit - 4)
        if len(text) <= limit:
            return text
        if self.layout.options.path_ellipsis == "middle":
            last_sep = max(text.rfind("/"), text.rfind("\\"))
            if last_sep == -1:
                return f"{text[: max(1, limit - 1)]}…"
            prefix = text[: last_sep]
            suffix = text[last_sep + 1 :]
            available = limit - len(suffix) - 1
            if available <= 0:
                visible_tail = suffix[-(limit - 1) :]
                return f"…{visible_tail}"
            truncated_prefix = prefix[:available]
            return f"{truncated_prefix}…{suffix}"
        return f"{text[: max(1, limit - 1)]}…"

    def _format_value(self, value: Any, fmt: Optional[str]) -> str:
        if value is None:
            return ""
        if fmt:
            try:
                return format(value, fmt)
            except (TypeError, ValueError):
                pass
        if isinstance(value, int) and not isinstance(value, bool):
            separator = self.layout.theme.units.get("thousands_sep")
            if separator:
                formatted = f"{value:,}"
                if isinstance(separator, str):
                    formatted = formatted.replace(",", separator)
                return formatted
            return str(value)
        if isinstance(value, float):
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
        raw_path = path_part
        if "|" in path_part:
            raw_path, *filters = path_part.split("|")
        value = context.resolve(raw_path)

        for filter_name in filters:
            value = self._apply_filter(value, filter_name)

        if optional_value and value in (None, ""):
            return ""
        formatted = self._format_value(value, fmt_spec)
        highlight_role = self._pick_highlight(raw_path.strip(), value, context)
        if highlight_role and formatted:
            leading_match = re.match(r"\s*", formatted)
            trailing_match = re.search(r"\s*$", formatted)
            lead = leading_match.group(0) if leading_match else ""
            trail = trailing_match.group(0) if trailing_match else ""
            core_start = len(lead)
            core_end = len(formatted) - len(trail)
            core = formatted[core_start:core_end] if core_end > core_start else ""
            if not core:
                return formatted
            return f"{lead}[[{highlight_role}]]{core}[[/]]{trail}"
        return formatted

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
        """
        Evaluate a boolean-like conditional expression within the given layout context.
        
        Parameters:
            expr (str): The conditional expression text to evaluate.
            context (LayoutContext): Context used to resolve path lookups referenced by the expression.
        
        Returns:
            bool: `True` if the expression evaluates to a truthy value in the provided context, `False` if it evaluates to a falsy value, is empty, or if evaluation fails.
        """
        expression = expr.strip()
        if not expression:
            return False

        prepared = self._prepare_condition(expression)
        namespace: Dict[str, Any] = {
            "resolve": context.resolve,
            "True": True,
            "False": False,
            "None": None,
        }
        try:
            result = self._safe_eval(prepared, namespace, allowed_call_names=("resolve",))
        except Exception:
            return False
        return bool(result)

    def _prepare_condition(self, expr: str) -> str:
        """
        Prepare a conditional template expression for safe evaluation by normalizing operators, boolean/null literals, and variable references.
        
        Parameters:
            expr (str): A conditional expression using JavaScript-style operators and identifiers (e.g. "a && b != true", "flag || other.value", "!exists").
        
        Returns:
            str: An equivalent Python expression where `&&`/`||`/`!` are converted to `and`/`or`/`not`, `true`/`false`/`none` are normalized to `True`/`False`/`None`, recognized safe function names are preserved, and bare identifiers are wrapped as `resolve('identifier')` for runtime resolution.
        """
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
                lowered = token.lower()
                if token in {"and", "or", "not", "True", "False", "None"}:
                    tokens.append(token)
                elif lowered == "true":
                    tokens.append("True")
                elif lowered == "false":
                    tokens.append("False")
                elif lowered == "none":
                    tokens.append("None")
                elif lowered in _SAFE_FUNCTION_TOKENS:
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
        text = self._prepare_output(self.render_template(template, values, flags))
        if text:
            self._write(text)

    def _render_box_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        title = section.get("title", "")
        lines = section.get("lines", [])
        if not isinstance(lines, list):
            raise CliLayoutError("box.lines must be a list")
        rendered_lines = [self._prepare_output(self.render_template(line, values, flags)) for line in lines]

        title_plain = f" {title} " if title else ""
        title_visible = len(title_plain)
        styled_title = self._colorize("header", title_plain) if title_plain else ""

        max_line = max((self._visible_length(line) for line in rendered_lines), default=0)
        width = min(self._console_width(), max(20, max_line + 4, title_visible + 2))
        inner_width = max(0, width - 4)

        top_fill = max(0, width - 2 - title_visible)
        if styled_title:
            top_border = f"┌{styled_title}{'─' * top_fill}┐"
        else:
            top_border = f"┌{'─' * (width - 2)}┐"

        bottom_border = f"└{'─' * (width - 2)}┘"

        self._write(top_border)
        for line in rendered_lines:
            truncated = self._truncate_visible(line, inner_width)
            padded = self._pad_to_width(truncated, inner_width)
            self._write(f"│ {padded} │")
        self._write(bottom_border)

    def _render_list_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        self._render_title_badge(section)
        items = section.get("items", [])
        if not isinstance(items, list):
            raise CliLayoutError("list.items must be a list")
        rendered_items = [self._prepare_output(self.render_template(item, values, flags)) for item in items if item]
        width = self._console_width()
        two_column = len(rendered_items) > 3 and width >= self.layout.options.two_column_min_cols
        if two_column and rendered_items:
            midpoint = (len(rendered_items) + 1) // 2
            left_items = rendered_items[:midpoint]
            right_items = rendered_items[midpoint:]
            col_width = max(10, (width - 4) // 2)
            for left, right in zip_longest(left_items, right_items, fillvalue=""):
                left_text = self._truncate_visible(left or "", col_width)
                left_text = self._pad_to_width(left_text, col_width)
                right_text = self._truncate_visible(right or "", col_width)
                if right_text.strip():
                    self._write(f"{left_text}    {right_text}")
                else:
                    self._write(left_text.rstrip())
        else:
            for rendered in rendered_items:
                if rendered:
                    self._write(rendered)

    def _render_group_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        self._render_title_badge(section)
        blocks = section.get("blocks", [])
        if not isinstance(blocks, list):
            raise CliLayoutError("group.blocks must be a list")
        rendered_blocks: List[Tuple[Optional[str], List[str]]] = []
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
            lines: List[str] = []
            for line in block.get("lines", []):
                rendered = self._prepare_output(self.render_template(line, values, flags))
                if rendered:
                    lines.append(rendered)
            if not subtitle and not lines:
                continue
            formatted_lines = self._format_block_lines(lines)
            rendered_blocks.append((subtitle, formatted_lines))
        show_rule = self._console_width() >= 80
        for index, (subtitle, lines) in enumerate(rendered_blocks):
            if subtitle:
                self._write(self._format_subtitle(subtitle))
                if show_rule:
                    rule_line = self._build_rule_line(lines)
                    if rule_line:
                        self._write(rule_line)
            for line in lines:
                self._write(line)
            if index < len(rendered_blocks) - 1 and (lines or subtitle):
                self._write()

    def _supports_unicode(self) -> bool:
        encoding = getattr(self.console, "encoding", None)
        if not encoding:
            return True
        try:
            return "utf" in encoding.lower()
        except AttributeError:
            return False

    def _using_ascii_symbols(self) -> bool:
        return self.no_color or not self._unicode_ok

    def _format_subtitle(self, subtitle: str) -> str:
        prefix = ">" if self._using_ascii_symbols() else "›"
        text = f"{prefix} {subtitle.strip()}"
        if self.no_color:
            return text
        return self._colorize("accent_subhead", text)

    def _build_rule_line(self, lines: Sequence[str]) -> str:
        if not lines:
            return ""
        indent: Optional[int] = None
        max_content_width = 0
        for line in lines:
            stripped = line.lstrip()
            if not stripped:
                continue
            current_indent = len(line) - len(stripped)
            indent = current_indent if indent is None else min(indent, current_indent)
            max_content_width = max(max_content_width, self._visible_length(stripped))
        if max_content_width == 0:
            return ""
        indent = indent or 0
        width_limit = max(1, self._console_width() - indent)
        rule_width = min(max_content_width, width_limit)
        char = "-" if self._using_ascii_symbols() else "─"
        rule_body = char * rule_width
        if not self._using_ascii_symbols():
            rule_body = self._colorize("rule_dim", rule_body)
        return (" " * indent) + rule_body

    def _format_block_lines(self, lines: Sequence[str]) -> List[str]:
        if not lines:
            return []
        structured: List[Tuple[int, Optional[List[str]], str]] = []
        max_cols = 0
        for line in lines:
            if not line:
                structured.append((0, None, line))
                continue
            stripped_line = line.strip()
            if not stripped_line:
                structured.append((len(line) - len(stripped_line), None, line))
                continue
            indent = len(line) - len(line.lstrip(" "))
            segments = re.split(r"\s{2,}", stripped_line)
            max_cols = max(max_cols, len(segments))
            structured.append((indent, segments, line))
        if max_cols <= 1:
            return list(lines)
        col_widths = [0] * max_cols
        for indent, segments, _ in structured:
            if not segments:
                continue
            for idx, segment in enumerate(segments):
                col_widths[idx] = max(col_widths[idx], self._visible_length(segment))
        formatted: List[str] = []
        for indent, segments, original in structured:
            if not segments or len(segments) <= 1:
                formatted.append(original)
                continue
            padded_segments: List[str] = []
            for idx, segment in enumerate(segments):
                if idx == 0:
                    padded_segments.append(segment)
                    continue
                vis = self._visible_length(segment)
                pad = max(0, col_widths[idx] - vis)
                padded_segments.append(" " * pad + segment)
            body = "  ".join(padded_segments)
            formatted.append(" " * indent + body)
        return formatted

    def _render_passthrough_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        self._render_title_badge(section)

    def _render_table_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        self._render_title_badge(section)
        row_template = section.get("row_template", "")
        rows = values.get(section.get("id"), []) if isinstance(values, Mapping) else []
        for row in rows:
            context_values = dict(values)
            context_values.update(row)
            rendered = self._prepare_output(self.render_template(row_template, context_values, flags))
            if rendered:
                self._write(rendered)

    # ------------------------------------------------------------------
    # Progress helpers --------------------------------------------------
    # ------------------------------------------------------------------

    def get_progress_block(self, progress_id: str) -> Optional[Mapping[str, Any]]:
        info = self._progress_blocks.get(progress_id)
        if info is None:
            return None
        return info.get("block")

    def bind_context(self, values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        """Record the active context for later progress template evaluation."""

        self._active_values = values
        self._active_flags = flags

    def create_progress(self, progress_id: str, *, transient: bool = False) -> Progress:
        info = self._progress_blocks.get(progress_id)
        if info is None:
            raise CliLayoutError(f"Unknown progress block: {progress_id}")
        block = info["block"]
        accent_role = info.get("accent")

        bar_style_token = self._role_style(accent_role or "accent")
        rich_bar_style = self._rich_style_from_token(bar_style_token)
        if rich_bar_style:
            bar_column = BarColumn(
                style=rich_bar_style,
                complete_style=rich_bar_style,
                finished_style=rich_bar_style,
                pulse_style=rich_bar_style,
            )
        else:
            bar_column = BarColumn()

        columns: List[ProgressColumn] = [
            TextColumn("{task.description}", justify="left"),
            bar_column,
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

    def render(self, task: Task) -> Any:
        state = dict(self.renderer._progress_state.get(self.progress_id, {}))
        state.setdefault("current", task.completed)
        state.setdefault("total", task.total)
        state.setdefault("percentage", task.percentage)
        context_values = dict(self.renderer._active_values)
        context_values.setdefault("progress", state)
        rendered = self.renderer.render_template(self.template, context_values, self.renderer._active_flags)
        prepared = self.renderer._prepare_output(rendered)
        width = self.renderer._console_width()
        min_cols = self.renderer.layout.options.truncate_right_label_min_cols
        if width < min_cols:
            parts = prepared.split(" | ")
            prepared = parts[0]
        return prepared


__all__ = [
    "CliLayout",
    "CliLayoutError",
    "CliLayoutRenderer",
    "HighlightRule",
    "JsonTailConfig",
    "LayoutOptions",
    "LayoutTheme",
    "load_cli_layout",
]