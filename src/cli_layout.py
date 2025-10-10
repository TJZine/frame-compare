"""Data-driven CLI layout rendering utilities."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import json
import os
import re
import shutil
import textwrap
from itertools import zip_longest
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from rich.console import Console
from rich.progress import BarColumn, Progress, ProgressColumn, Task, TextColumn
from rich.text import Text


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
    """Ensure the parsed AST only contains whitelisted operations."""

    def _check(inner: ast.AST) -> None:
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
        """
        Initialize the color mapper and determine the terminal color capability.
        
        Determines whether color output is disabled by combining the explicit `no_color` flag with the `NO_COLOR` environment variable, records that state on `self.no_color`, and sets `self._capability` to `"none"` when color is disabled. When color is enabled, attempts to enable Windows VT processing and detects the terminal's color capability, storing the result on `self._capability`. This may modify console state when enabling VT mode on Windows.
        
        Parameters:
            no_color (bool): If True, force-disable all ANSI color output regardless of environment.
        """
        env_no_color = bool(os.environ.get("NO_COLOR"))
        self.no_color = no_color or env_no_color
        self._capability = "none"
        if not self.no_color:
            self._enable_windows_vt_mode()
            self._capability = self._detect_capability()

    @staticmethod
    def _enable_windows_vt_mode() -> None:
        """
        Enable ANSI VT (virtual terminal) processing on Windows consoles so ANSI escape sequences are interpreted.
        
        This function is a no-op on non-Windows platforms. On Windows it first attempts to initialize color support via the optional `colorama` package; if `colorama` is unavailable it falls back to enabling VT processing through the Windows console API. Failures are handled silently — if VT mode cannot be enabled the function returns without raising.
        """
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
        """
        Determine the terminal color capability based on environment variables.
        
        Checks COLORTERM and TERM for indications of truecolor or 256-color support and returns "256" when detected, otherwise returns "16".
        
        Returns:
            capability (str): "256" if truecolor/256-color support is likely, "16" otherwise.
        """
        colorterm = os.environ.get("COLORTERM", "").lower()
        if any(token in colorterm for token in ("truecolor", "24bit")):
            return "256"
        term = os.environ.get("TERM", "").lower()
        if "256color" in term or "truecolor" in term:
            return "256"
        return "16"

    def apply(self, token: str, text: str) -> str:
        """
        Apply the color/style represented by `token` to `text` using ANSI SGR sequences.
        
        Parameters:
            token (str): Color or style token name understood by the mapper.
            text (str): The text to wrap with the style; returned unchanged if empty or styling is disabled.
        
        Returns:
            str: `text` wrapped with the ANSI SGR sequence for `token` and an ANSI reset, or the original `text` if no style is applied.
        """
        if not text or self.no_color:
            return text
        sgr = self._lookup(token)
        if not sgr:
            return text
        return f"{sgr}{text}{_ANSI_RESET}"

    def _lookup(self, token: str) -> str:
        """
        Convert a color token into the corresponding ANSI SGR escape sequence for the renderer's detected terminal capability.
        
        Parameters:
            token (str): Color token string (e.g. "accent.bold" or "green.bright") where the first segment names a color role and subsequent dot-separated segments are modifiers such as "bright", "bold", or "dim".
        
        Returns:
            str: The ANSI escape sequence that applies the token's color and modifiers, or an empty string if the token is empty or not supported for the current terminal capability.
        """
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
    """Theme definition providing colors, symbols, and formatting options."""
    colors: Dict[str, str]
    symbols: Dict[str, str]
    units: Dict[str, Any]
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LayoutOptions:
    """Global CLI layout behaviour toggles and dimension thresholds."""
    two_column_min_cols: int
    blank_line_between_sections: bool
    path_ellipsis: str
    truncate_right_label_min_cols: int


@dataclass
class JsonTailConfig:
    """Configuration describing optional JSON output appended to the CLI run."""
    pretty_on_flag: str
    must_be_last: bool = True


@dataclass
class CliLayout:
    """Validated CLI layout specification loaded from disk."""
    version: str
    theme: LayoutTheme
    options: LayoutOptions
    sections: List[Dict[str, Any]]
    folding: Dict[str, Any]
    json_tail: JsonTailConfig
    highlights: List["HighlightRule"]


@dataclass
class HighlightRule:
    """Conditional highlighting rule applied to rendered layout values."""
    when: str
    path: str
    role: Optional[str] = None
    value: Any = None
    true_role: Optional[str] = None
    false_role: Optional[str] = None


def _require_keys(mapping: Mapping[str, Any], keys: Iterable[str], *, context: str) -> None:
    """
    Validate that all specified keys are present in a mapping.
    
    Parameters:
        mapping: Mapping to validate for presence of keys.
        keys: Iterable of keys required to exist in `mapping`.
        context: Short description of the mapping used in the error message when keys are missing.
    
    Raises:
        CliLayoutError: If one or more keys from `keys` are not present in `mapping`. The exception message lists the missing keys and includes `context`.
    """
    missing = [key for key in keys if key not in mapping]
    if missing:
        joined = ", ".join(missing)
        raise CliLayoutError(f"Missing keys for {context}: {joined}")


def load_cli_layout(path: Path) -> CliLayout:
    """
    Load and validate a CLI layout from a JSON file.
    
    Parses the JSON document at the given path, validates required top-level sections and theme/layout schema, and returns a populated CliLayout instance.
    
    Parameters:
        path (Path): Filesystem path to the layout JSON file.
    
    Returns:
        CliLayout: The parsed and validated layout configuration.
    
    Raises:
        CliLayoutError: If the file cannot be read, the JSON is malformed, or the layout fails schema validation.
    """

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
        """
        Create a runtime context used to resolve template paths and flags during rendering.
        
        Parameters:
            data: Mapping of the current template data available for path resolution.
            flags: Mapping of runtime flags (e.g., quiet/verbose) accessible during rendering.
            renderer: The CliLayoutRenderer instance that owns this context and provides rendering utilities.
        """
        self._data = data
        self._flags = flags
        self._renderer = renderer

    def resolve(self, path: str) -> Any:
        """
        Resolve a dotted path or flag name against the context's data and flags.
        
        Looks up `path` in flags first; if present, returns the flag value. Otherwise traverses `self._data` following dot-separated segments:
        - Dictionary-like objects: use mapping keys.
        - Sequence-like objects (except str/bytes/bytearray): numeric segments are treated as indices (out-of-range yields `None`).
        - Object attributes: use attribute access when mapping/sequence lookup does not apply.
        - The special segment `e` returns the current value converted to a path with ellipsis via the renderer's `apply_path_ellipsis`.
        
        Parameters:
            path (str): A dotted lookup path (e.g. "a.b.0.c"); an empty or missing path returns the root data.
        
        Returns:
            The resolved value for the path, or `None` if any lookup step fails or the path does not exist.
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
        """
        Initialize a CliLayoutRenderer with layout, console, and runtime flags and prepare internal rendering state.
        
        Sets up color mapping (respecting no_color and color-blind options), symbol and role token maps, unicode support detection, cached width and progress state, grouped highlight rules, and progress block metadata extracted from group sections.
        
        Parameters:
            layout: The parsed CliLayout describing theme, sections, options, folding, json_tail, and highlights.
            console: A Rich Console used for output.
            quiet: When True, suppresses non-banner sections during rendering.
            verbose: When True, enables additional verbose output paths.
            no_color: When True, disables ANSI color output and prefers ASCII symbols where available.
        """
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
        self._unknown_role_warnings: Set[str] = set()
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
        """
        Return a copy of the renderer's symbol map.
        
        Returns:
            Mapping[str, str]: A mapping of symbol token names to their current string values (shallow copy).
        """
        return dict(self._symbols)

    def update_progress_state(self, progress_id: str, *, state: Mapping[str, Any]) -> None:
        """
        Update the stored progress state for the given progress identifier.
        
        Merges the provided mapping into the existing state for `progress_id`, creating a new state mapping if none exists. Existing keys are overwritten by values from `state`.
        
        Parameters:
            progress_id (str): Identifier for the progress block to update.
            state (Mapping[str, Any]): Mapping of state keys and values to merge into the existing progress state.
        """
        self._progress_state.setdefault(progress_id, {}).update(state)

    # ------------------------------------------------------------------
    # Template rendering utilities
    # ------------------------------------------------------------------

    def _console_width(self) -> int:
        """
        Determine the current console width to use for rendering.
        
        Checks cached value, then tries console.width, then console.size.width, and finally falls back to the system terminal size with a minimum of 40 columns. Caches the resolved width for subsequent calls.
        
        Returns:
            int: The number of columns to use for layout rendering (at least 40).
        """
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
        """
        Compute the visible character length of a string excluding ANSI escape sequences.
        
        Returns:
        	The number of printable characters in `text` after removing ANSI escape sequences.
        """
        return len(_ANSI_ESCAPE_RE.sub("", text))

    def _pad_to_width(self, text: str, width: int) -> str:
        """
        Pad `text` with spaces so its visible (ANSI-stripped) length reaches `width`.
        
        Parameters:
            text (str): The input string, may include ANSI escape sequences.
            width (int): Target visible width in characters (excluding ANSI escapes).
        
        Returns:
            str: The original string if its visible length is >= `width`, otherwise the string padded on the right with spaces so its visible length equals `width`.
        """
        visible = self._visible_length(text)
        if visible >= width:
            return text
        return text + " " * (width - visible)

    def _truncate_visible(self, text: str, width: int) -> str:
        """
        Truncates a string so its visible length (excluding ANSI escape sequences) does not exceed the given width, appending an ellipsis when truncated.
        
        If the visible length is already within width the original string is returned unchanged (including any ANSI sequences). If truncation is required, ANSI escape sequences are removed and a plain-text truncation with a trailing "…" is returned; the resulting visible length will be less than or equal to width.
        
        Returns:
            A string whose visible length (counting characters but ignoring ANSI escapes) is <= width.
        """
        if self._visible_length(text) <= width:
            return text
        plain = _ANSI_ESCAPE_RE.sub("", text)
        if len(plain) <= width:
            return text
        truncated = plain[: max(1, width - 1)] + "…"
        return truncated

    def _colorize(self, role: str, text: str) -> str:
        """
        Apply the theme role's color/style to the given text.

        Returns:
                The input text wrapped with ANSI escape sequences for the role, or the original text if no style is configured.
        """
        token = self._lookup_role_token(role)
        return self._color_mapper.apply(token, text)

    def _role_style(self, role: Optional[str]) -> Optional[str]:
        """
        Map a theme role name to its style token used for colorization.
        
        Parameters:
            role (Optional[str]): The role name to look up.
        
        Returns:
            Optional[str]: The style token associated with `role`, or `None` if coloring is disabled or no token is defined for the role.
        """
        if self.no_color or not role:
            return None
        token = self._lookup_role_token(role)
        return token or None

    def _rich_style_from_token(self, token: Optional[str]) -> Optional[str]:
        """
        Convert an internal color token into a Rich-compatible style string.
        
        The token is a dot-separated string where the first segment is a color name and subsequent
        segments are modifiers. Recognized modifiers:
        - `bright`: prefer a bright variant of the base color when available.
        - `dim`: maps to the `dim` Rich modifier.
        - `bold`: maps to the `bold` Rich modifier.
        Any other modifier segments are included as literal words (periods replaced by spaces).
        
        Special handling:
        - `grey` / `gray` with `bright` maps to `bright_black`.
        - `purple` with `bright` ensures the `bold` modifier is included.
        
        Parameters:
            token (Optional[str]): A dot-separated color token or `None`.
        
        Returns:
            Optional[str]: A space-separated Rich style string (modifiers followed by a base color),
            or `None` if `token` is falsy.
        """
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

    def _lookup_role_token(self, role: Optional[str]) -> str:
        """Return the style token for ``role`` and warn once when missing."""

        if not role:
            return ""
        token = self._role_tokens.get(role)
        if token is not None:
            return token
        if role not in self._unknown_role_warnings:
            message = f"Unknown color role '{role}' in layout"
            if self.no_color:
                self.console.print(f"Warning: {message}")
            else:
                self.console.print(f"[yellow]Warning:[/] {message}")
            self._unknown_role_warnings.add(role)
        return ""

    def _log_section_role(self, section_id: Optional[str], role: Optional[str]) -> None:
        """Emit a verbose log line describing the role applied to a section header."""

        if not self.verbose:
            return
        label = section_id or "unknown"
        applied = role or "header"
        message = f"section[{label}] header role → {applied}"
        if self.no_color:
            self.console.log(message, markup=False)
        else:
            escaped = message.replace("[", "[[").replace("]", "]]" )
            self.console.log(f"[dim]{escaped}[/dim]")

    def _resolve_section_accent(self, section: Mapping[str, Any], badge: Optional[str] = None) -> Optional[str]:
        """
        Determine the accent role for a section based on an explicit role, badge content, or the section id.
        
        Parameters:
            section (Mapping[str, Any]): Section metadata; may include the keys "accent_role", "title_badge", and "id".
            badge (Optional[str]): Optional badge text to use instead of the section's "title_badge".
        
        Returns:
            Optional[str]: The resolved accent role name (e.g., "header", "accent") if one is determined, otherwise `None`.
        """
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
        """
        Apply a role-based color/style to a text chunk when coloring is enabled.
        
        Parameters:
        	role (Optional[str]): The style role token to apply (e.g., "accent", "warn"); if None or empty, no styling is applied.
        	chunk (str): The text to style.
        
        Returns:
        	The styled string if a role is provided and coloring is enabled, otherwise the original chunk (or an empty string if `chunk` is empty).
        """
        if not chunk:
            return ""
        if role and not self.no_color:
            return self._colorize(role, chunk)
        return chunk

    def _render_title_badge(self, section: Mapping[str, Any]) -> None:
        """
        Render a section's title badge if present.
        
        If the section mapping contains a 'title_badge', determine an accent role from the section and badge (falling back to "header"), colorize the badge text with that role, and write it to the console.
        
        Parameters:
            section (Mapping[str, Any]): Section specification mapping; may include a 'title_badge' string.
        """
        badge = section.get("title_badge")
        if not badge:
            return
        role = self._resolve_section_accent(section, badge) or "header"
        self._log_section_role(section.get("id"), role)
        self._write(self._colorize(role, badge))

    def _apply_style_spans(self, text: str) -> str:
        """
        Apply inline style spans in the form [[role]]...[[/]] to the input text and return the styled result.
        
        This recognizes role tokens enclosed in double brackets (e.g. [[accent]]) to start a styling span and the token [[/]] to end the most recent span. Spans may be nested; inner spans override outer roles for their contents. Unmatched or unterminated markers are treated as literal text.
        
        Parameters:
            text (str): Input string that may contain style span markers.
        
        Returns:
            str: The input string with style spans applied and replaced by their styled equivalents.
        """
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
        """
        Coerces common truthy and falsy representations into a boolean.
        
        Accepts booleans, numeric types, and strings. Numeric values are treated as truthy when nonzero. String values recognized as truthy: "true", "yes", "1", "enabled", "on"; falsy: "false", "no", "0", "disabled", "off". Whitespace and case are ignored.
        
        Returns:
            `True` if the value maps to a truthy representation, `False` if it maps to a falsy representation, `None` if the value cannot be determined as boolean.
        """
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
        Convert a value to a numeric float when possible.
        
        Accepts ints and floats (returned as float), booleans (returned as 1.0 or 0.0), and numeric strings (commas allowed) and returns their float representation; returns None if conversion is not possible.
        
        Returns:
            A float representation of the input value, or `None` if the value cannot be converted to a number.
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
        Evaluate a layout expression using a restricted namespace that can resolve template paths.
        
        Parameters:
            expression (str): The expression to evaluate.
            context (LayoutContext): Context used for resolving path tokens via `resolve`.
        
        Returns:
            The result of the evaluated expression, or `None` if evaluation fails.
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
        """
        Resolve an operand that may be an expression enclosed in braces.
        
        If `operand` is a string of the form "{...}" with a non-empty inner expression, evaluates that expression in `context` and returns the result; otherwise returns `operand` unchanged.
        
        Parameters:
            operand: The value or expression to resolve; may be any type.
            context (LayoutContext): Context used to evaluate expressions.
        
        Returns:
            The evaluated result when `operand` is a non-empty brace-enclosed expression, or the original `operand` otherwise.
        """
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
        """
        Evaluate a HighlightRule against a value in the given LayoutContext and return the highlight role when the rule matches.
        
        Parameters:
            rule (HighlightRule): The highlight rule to evaluate; its `when` field controls the comparison type.
            value (Any): The value to test against the rule.
            context (LayoutContext): Context used to resolve operands or expressions referenced by the rule.
        
        Notes:
            Supported `when` types:
              - "isbool": coerces the value to boolean and returns `true_role` or `false_role`.
              - "gt", "lt": numeric greater-than / less-than comparisons.
              - "abs_gt", "abs_gte", "abs_lt": comparisons against the absolute value.
            If operand resolution or numeric coercion fails, the rule does not match.
        
        Returns:
            Optional[str]: The role name to apply when the rule matches, or `None` if it does not match or cannot be evaluated.
        """
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
        """
        Selects the first highlight role that applies to a given path and value.
        
        Checks registered highlight rules for the exact `path` and evaluates them in order using `context`. Returns the role from the first rule whose condition matches the supplied `value`.
        
        Parameters:
            path (str): Dotted path used to look up highlight rules.
            value (Any): The value to evaluate against highlight rules.
            context (LayoutContext): Runtime context used when evaluating rule expressions.
        
        Returns:
            Optional[str]: The highlight role from the first matching rule, or `None` if no rule applies.
        """
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
        """
        Apply color styling to key-like tokens and boolean words in a text string.
        
        This method highlights tokens that look like keys (words immediately followed by "=" or ":" not part of a URL) using the renderer's "accent" role, and maps boolean-like words ("yes", "no", "true", "false", "enabled", "disabled", "ok") to "success" or "warn" roles. If `text` is empty or color output is disabled, the original string is returned unchanged.
        
        Parameters:
            text (str): The input text to style.
        
        Returns:
            str: The input string with key tokens and boolean words wrapped with the renderer's color roles.
        """
        if not text or self.no_color:
            return text

        def repl(match: re.Match[str]) -> str:
            """
            Render a regex match for a key token as a colored key followed by an equals sign.
            
            Parameters:
                match (re.Match[str]): Regex match whose first capture group is the key token.
            
            Returns:
                str: The key wrapped with the renderer's 'accent' color token followed by '='.
            """
            key = match.group(1)
            return f"{self._colorize('accent', key)}="

        def colon_repl(match: re.Match[str]) -> str:
            """
            Replace a regex match representing a key:suffix pair with a colorized key and the original suffix.
            
            Parameters:
                match (re.Match[str]): A regex match where group 1 is the key token and group 2 is the following suffix (e.g., delimiter and value).
            
            Returns:
                str: The input reconstructed as "<accent-colored key><suffix>".
            """
            key = match.group(1)
            suffix = match.group(2)
            return f"{self._colorize('accent', key)}{suffix}"

        text = re.sub(r"(?<!\S)([A-Za-z0-9_.-]+)=", repl, text)
        text = re.sub(r"(?<!\S)([A-Za-z0-9_.-]+)(:)(?!//)", colon_repl, text)

        def bool_repl(match: re.Match[str]) -> str:
            """
            Map a regex match of boolean-like words to a role-colored string or return the original text.
            
            Parameters:
                match (re.Match[str]): A regex match whose matched text will be inspected.
            
            Returns:
                str: The matched text colorized with the "success" role if it is one of "yes", "true", "enabled", or "ok"; colorized with the "warn" role if it is one of "no", "false", or "disabled"; otherwise the original matched text.
            """
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
        """
        Prepare rendered output by applying inline style spans and optional key-token highlighting.
        
        The function trims trailing whitespace from the input, applies inline style spans of the form `[[role]]...[[/]]` when present, and optionally transforms key-like tokens and boolean words into styled tokens.
        
        Parameters:
            text (str): The rendered text to prepare.
            highlight (bool): If True, apply key-token and boolean-word styling; if False, skip that step.
        
        Returns:
            str: The processed string with trailing right-side whitespace removed, style spans applied, and key-token highlighting applied when enabled. An empty string is returned for falsy input.
        """
        if not text:
            return ""
        stripped = text.rstrip()
        if "[[" in stripped:
            stripped = self._apply_style_spans(stripped)
        if highlight:
            stripped = self._style_key_tokens(stripped)
        return stripped

    def _write(self, text: str = "") -> None:
        """
        Write a line to the renderer's console.
        
        If `text` is non-empty it is printed as a single line; if `text` is empty a blank line is emitted.
        """
        if text:
            self.console.print(text)
        else:
            self.console.print()

    def apply_path_ellipsis(self, value: str, *, width: Optional[int] = None) -> str:
        """
        Shorten a path-like string with an ellipsis so it fits within the console width.
        
        If `value` is None an empty string is returned. The effective width is `width` if provided or the current console width minus padding; a minimum usable width is enforced. When the layout option `path_ellipsis` is "middle", the function preserves the final path segment (after the last '/' or '\') and inserts an ellipsis in the middle; otherwise it truncates the end and appends an ellipsis. The result always contains at least one visible character plus the ellipsis when truncation is required.
        
        Parameters:
            value (str | None): The path or text to shorten. `None` yields an empty string.
            width (int, optional): Override for the maximum width to fit; if omitted the console width is used.
        
        Returns:
            str: The possibly truncated string, using "…" (ellipsis) to indicate removed content.
        """
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
        """
        Format a value for display according to the layout theme and an optional format specifier.
        
        When `value` is None returns an empty string. If `fmt` is provided, attempts to format using Python's `format(value, fmt)` and falls back to subsequent rules on error. Integers (excluding booleans) use the theme's `units.thousands_sep` to insert a thousands separator when present; otherwise they are converted with `str()`. Floats are formatted with a number of decimal places taken from `theme.units.seconds_decimals` (default 2). All other values are converted with `str()`.
        
        Parameters:
            value (Any): The value to format.
            fmt (Optional[str]): Optional Python format specification to apply.
        
        Returns:
            str: The formatted string representation suitable for CLI output.
        """
        if value is None:
            return ""
        if fmt:
            try:
                return format(value, fmt)
            except (TypeError, ValueError):
                pass
        if isinstance(value, bool):
            return "true" if value else "false"
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
        """
        Apply a named simple display filter to a value.
        
        Parameters:
            value (Any): The input value to transform.
            filter_name (str): One of the supported filters:
                - "none": returns the original value unless it is None or empty string, in which case returns "none".
                - "unchanged": returns "unchanged" when the value is None or empty string, otherwise returns the value.
                - "tallest": returns "tallest" when the value is falsy, otherwise returns the value.
                - "ellipsis": returns a path-truncated string produced by apply_path_ellipsis(str(value)).
                Any other filter_name returns the value unchanged.
        
        Returns:
            Any: The transformed value according to the selected filter.
        """
        if filter_name == "bool":
            return "true" if bool(value) else "false"
        if filter_name == "wrap_indent2":
            text = "" if value is None else str(value)
            if not text:
                return ""
            width = max(10, self._console_width() - 2)
            return textwrap.fill(
                text,
                width=width,
                subsequent_indent="  ",
                break_long_words=False,
                break_on_hyphens=False,
            )
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
        """
        Render a single template token into its string representation using the provided context.
        
        Supports:
        - Conditional tokens in the form `cond?true:else`; the chosen branch is rendered (backticked branches are treated as dollar-templates).
        - Optional tokens with a trailing `?` which yield an empty string when the resolved value is `None` or an empty string.
        - Path resolution with optional format specifier using `path:fmt`.
        - Value filters appended with `|`, e.g. `path|filter1|filter2`.
        - Highlighting: when a highlight rule matches the resolved path and value, the non-whitespace core of the formatted result is wrapped with a role span `[[role]]...[[/]]`.
        
        Parameters:
            token (str): The token text to render (typically the contents between `{}` in a template).
            context (LayoutContext): Context used to resolve paths and evaluate conditions.
        
        Returns:
            str: The rendered string for the token (possibly empty), with formatting, filters, conditional evaluation, and optional highlight span applied.
        """
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
        """
        Render a template string by replacing {tokens} with their rendered values using the provided context.
        
        Parameters:
            template (str): Template text containing zero or more brace-enclosed tokens (e.g., "{path}") to be rendered.
            context (LayoutContext): Context used to resolve and render tokens.
        
        Returns:
            str: The fully rendered string. Malformed or unmatched opening braces are preserved as literal characters; each well-formed `{...}` token is replaced by its rendered value.
        """
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
        """
        Extract the token substring delimited by a matching `}` starting from a given index, supporting nested `{}` pairs.
        
        Parameters:
            text (str): The full template string to scan.
            start (int): The index to begin scanning from (expected to be just after an opening `{`).
        
        Returns:
            tuple[Optional[str], int]: A pair where the first element is the extracted token (the substring between `start` and the matching `}`) or `None` if no matching closing brace was found; the second element is the index immediately after the closing `}` or `len(text)` if unmatched.
        """
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
        """
        Replace `${path}`-style placeholders in a template with resolved values from a LayoutContext.
        
        Parameters:
        	template (str): Template text containing `${...}` placeholders where `...` is a dotted path.
        	context (LayoutContext): Context used to resolve each placeholder path; if resolution returns `None` the placeholder is replaced with an empty string.
        
        Returns:
        	str: The template with all `${...}` placeholders substituted by their resolved string values.
        """
        def replace(match: re.Match[str]) -> str:
            path = match.group(1)
            value = context.resolve(path)
            if value is None:
                return ""
            return str(value)

        dollar_re = re.compile(r"\$\{([^{}]+)\}")
        return dollar_re.sub(replace, template)

    def _find_conditional_split(self, token: str) -> Optional[Tuple[str, str, str]]:
        """
        Locate a ternary-style conditional in a template token and split it into condition, true branch, and false branch.
        
        Parameters:
            token (str): A template token that may contain a conditional expression of the form `condition?true_expr:false_expr`.
        
        Returns:
            tuple[str, str, str] | None: A 3-tuple (condition, true_expr, false_expr) with surrounding whitespace removed if a matching `?` and its corresponding `:` are found; otherwise `None`.
        """
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
        return left.strip(), true_expr, false_expr

    def _find_unescaped_question(self, text: str) -> Optional[int]:
        """
        Locate the first top-level, unescaped question mark in a template string.
        
        The search ignores question marks that occur inside backtick-delimited spans, inside balanced `{}` brace groups, or when nested within any parentheses at depth greater than zero.
        
        Parameters:
            text (str): Template text to scan.
        
        Returns:
            index (int | None): The index of the first unescaped `?` found at top-level, or `None` if none exists.
        """
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
        """
        Find the index of the colon that pairs with the first top-level conditional split in a token.
        
        Scans `text` for a colon ':' that corresponds to the top-level '?' conditional operator, ignoring colons that appear inside balanced '{...}' groups or inside backtick-delimited segments. Nested conditionals are supported: each '?' increments nesting and the matching ':' for the outermost conditional is returned.
        
        Parameters:
            text (str): The token text to search for a matching colon.
        
        Returns:
            Optional[int]: The index of the matching colon in `text`, or `None` if no top-level matching colon is found.
        """
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
        Determine whether a condition expression evaluates to true using the given layout context.
        
        The expression is prepared for evaluation (mapping token names to calls to the context resolver) and executed in a restricted namespace where `resolve` is available along with `True`, `False`, and `None`. Any evaluation error or an empty expression results in `False`.
        
        Parameters:
            expr (str): The condition expression to evaluate.
            context (LayoutContext): Context used to resolve tokens referenced by the expression.
        
        Returns:
            bool: `True` if the prepared expression evaluates truthy, `False` otherwise.
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
        Convert a layout condition expression into a Python-evaluable expression that resolves symbols at runtime.
        
        The input expression may use C-style logical operators and unqualified identifiers; this function:
        - replaces `&&`/`||` with `and`/`or`,
        - normalizes boolean and null-like literals (`true`/`false`/`none`) to `True`/`False`/`None`,
        - replaces identifiers (e.g., `foo.bar`) with calls to `resolve('foo.bar')`,
        - converts unary `!` to Python `not` while preserving `!=`.
        
        Parameters:
            expr (str): A condition expression from the layout template.
        
        Returns:
            str: A Python expression string suitable for evaluation in the renderer's restricted namespace.
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
        """
        Render a layout template string using the provided values and flags.
        
        Parameters:
            template (str): Template text containing layout tokens, conditional expressions, and style spans to be resolved.
            values (Mapping[str, Any]): Mapping of variable names to values used when resolving template tokens.
            flags (Mapping[str, Any]): Runtime flags (for example quiet/verbose/no_color) that influence rendering and conditional evaluation.
        
        Returns:
            str: The rendered string with tokens evaluated, filters and formatting applied, highlights and styles resolved.
        """
        context = LayoutContext(values, flags, renderer=self)
        return self._render_text(template, context)

    # ------------------------------------------------------------------
    # Section rendering -------------------------------------------------
    # ------------------------------------------------------------------

    def render_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        """
        Render a single layout section according to the renderer's configuration and the provided data.
        
        Evaluates the section's optional "when" condition and skips rendering when it is false; honors the renderer's quiet mode and the layout option to insert a blank line between sections; dispatches to the appropriate section-specific render method and records the section as rendered. Raises CliLayoutError if the section's type is not supported.
        
        Parameters:
            section (Mapping[str, Any]): Section specification from the layout (must include "type" and may include "id" and "when").
            values (Mapping[str, Any]): Runtime values used for template rendering and condition evaluation.
            flags (Mapping[str, Any]): Runtime flags (e.g., quiet/verbose) used during rendering.
        """
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
        """
        Render a single-line section by evaluating its template and writing the resulting text if non-empty.
        
        Parameters:
        	section (Mapping[str, Any]): Section definition; may contain a "template" string to render.
        	values (Mapping[str, Any]): Data values used when rendering the template.
        	flags (Mapping[str, Any]): Flag values used when rendering the template.
        """
        template = section.get("template", "")
        text = self._prepare_output(self.render_template(template, values, flags))
        if text:
            self._write(text)

    def _render_box_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        """
        Render a framed box section with an optional styled title and content lines.
        
        Renders the section described by `section` using `values` and `flags` as the template context. Expects `section["lines"]` to be a list of template strings; each line is rendered, truncated and padded to fit the console width, and placed inside a box drawn with Unicode box-drawing characters. If a `title` is present it is shown in the top border and styled with the theme's header role. Raises CliLayoutError if `section["lines"]` is not a list.
        
        Parameters:
            section (Mapping[str, Any]): Section specification; recognizes the keys:
                - "title" (str, optional): Box title.
                - "lines" (list): List of template strings to render as the box body.
            values (Mapping[str, Any]): Mapping of runtime values used when rendering templates.
            flags (Mapping[str, Any]): Mapping of runtime flags used when rendering templates.
        """
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
        """
        Render a "list" section: print the section badge/title and the section's items either as a single column or two columns depending on available console width.
        
        Each non-empty item is rendered as a template, processed for styling, and printed. When there are more than three items and the console width is at least layout.options.two_column_min_cols, items are split into two columns, truncated and padded to fit; otherwise items are printed one per line.
        
        Raises:
            CliLayoutError: if `section["items"]` exists and is not a list.
        """
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
        """
        Render a "group" section by evaluating and printing its member blocks with optional subtitles and dividing rules.
        
        Each block may include:
        - "when": a conditional expression; the block is skipped if the condition evaluates to false.
        - "type": if "progress", the block is skipped (progress handled separately); otherwise treated as line-based content.
        - "subtitle": an optional subtitle rendered before the block's lines.
        - "lines": a list of templates; each template is rendered, styled, and included if non-empty.
        
        Behavior:
        - Validates that section["blocks"], if present, is a list and raises CliLayoutError if not.
        - Renders each block's lines via render_template, applies styling and alignment, and formats multi-column block lines.
        - Emits a decorative rule between a subtitle and its block lines when the console width is >= 80.
        - Writes a blank line between rendered blocks.
        
        Raises:
            CliLayoutError: if section["blocks"] is present but is not a list.
        """
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
                    rule_line = self._build_rule_line(subtitle, lines)
                    if rule_line:
                        self._write(rule_line)
            for line in lines:
                self._write(line)
            if index < len(rendered_blocks) - 1 and (lines or subtitle):
                self._write()

    def _supports_unicode(self) -> bool:
        """
        Determine whether the associated console is likely to support Unicode.
        
        Checks the console's `encoding` attribute and treats encodings containing "utf" (case-insensitive) as Unicode-capable; if the console has no `encoding` attribute or it's falsy, assumes Unicode support. Returns `False` if the encoding value is present but does not appear UTF-compatible or if its type is not string-like.
        
        Returns:
            `true` if the console is expected to support Unicode, `false` otherwise.
        """
        encoding = getattr(self.console, "encoding", None)
        if not encoding:
            return True
        try:
            return "utf" in encoding.lower()
        except AttributeError:
            return False

    def _using_ascii_symbols(self) -> bool:
        """
        Determine whether rendering should fall back to ASCII-only symbols.
        
        Returns:
            `true` if rendering must use ASCII symbols (color disabled or Unicode unsupported), `false` otherwise.
        """
        return self.no_color or not self._unicode_ok

    def _format_subtitle(self, subtitle: str) -> str:
        """
        Format a section subtitle with a leading symbol and optional accent styling.
        
        Parameters:
        	subtitle (str): Subtitle text; leading/trailing whitespace will be trimmed.
        
        Returns:
        	str: The subtitle prefixed with an ASCII ">" or Unicode "›" (depending on symbol mode). If colors are enabled, the result is colorized using the `accent_subhead` role; otherwise plain text is returned.
        """
        prefix = ">" if self._using_ascii_symbols() else "›"
        text = f"{prefix} {subtitle.strip()}"
        if self.no_color:
            return text
        return self._colorize("accent_subhead", text)

    def _build_rule_line(self, subtitle: str, lines: Sequence[str]) -> str:
        """
        Construct a horizontal rule sized to the subtitle label and block content width.

        Parameters:
            subtitle (str): Subtitle text used to size the decorative rule.
            lines (Sequence[str]): Lines used to determine indentation and available content width.

        Returns:
            str: A single-line string containing a horizontal rule indented to the minimal indentation found and truncated to fit the console width, block content width, and subtitle width. Returns an empty string if there is no visible content. Uses '-' when ASCII symbols are required; otherwise uses '─' and applies the `rule_dim` role color.
        """
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
        subtitle_width = self._visible_length(self._format_subtitle(subtitle))
        max_rule_width = max(1, min(32, subtitle_width + 2))
        rule_width = min(rule_width, max_rule_width)
        if rule_width <= 0:
            return ""
        char = "-" if self._using_ascii_symbols() else "─"
        rule_body = char * rule_width
        if not self._using_ascii_symbols():
            rule_body = self._colorize("rule_dim", rule_body)
        return (" " * indent) + rule_body

    def _format_block_lines(self, lines: Sequence[str]) -> List[str]:
        """
        Aligns multi-column text lines into evenly padded columns.
        
        Takes an input sequence of lines where columns are delimited by two or more spaces, preserves leading indentation and empty lines, and returns a new list of lines with columns padded so each column aligns vertically across all lines. Lines that do not contain multiple columns are returned unchanged.
        
        Parameters:
            lines (Sequence[str]): Input lines to format; columns are detected by runs of two or more spaces.
        
        Returns:
            List[str]: The formatted lines with aligned columns, or the original lines when no multi-column layout is detected.
        """
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
        """
        Render a passthrough section header (title/badge) without additional body content.
        
        This renders only the section's title badge using the current theme and accent rules; passthrough sections do not produce content lines.
        """
        self._render_title_badge(section)

    def _render_table_section(self, section: Mapping[str, Any], values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        """
        Render a table-style section by iterating over rows and rendering a per-row template.
        
        For the section's "row_template", looks up an iterable of rows from the provided values using the section's "id", merges each row into the current values as the rendering context, renders and post-processes the template, and writes each non-empty rendered line to the console. Empty or falsy rendered results are skipped.
        """
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
        """
        Return the progress block configuration for the given progress identifier, or None if not present.
        
        Returns:
            Mapping[str, Any] or None: The progress block mapping for the specified `progress_id`, or `None` if no block exists.
        """
        info = self._progress_blocks.get(progress_id)
        if info is None:
            return None
        return info.get("block")

    def bind_context(self, values: Mapping[str, Any], flags: Mapping[str, Any]) -> None:
        """
        Store the current rendering values and flags for later use by progress-template rendering.
        
        Parameters:
            values (Mapping[str, Any]): Mapping of active data values available to templates.
            flags (Mapping[str, Any]): Mapping of active flags (e.g., quiet, verbose, no_color) available to templates.
        """

        self._active_values = values
        self._active_flags = flags

    def create_progress(self, progress_id: str, *, transient: bool = False) -> Progress:
        """
        Create a Rich Progress instance configured for the specified progress block.
        
        Constructs a Progress configured with columns (description, progress bar, completed/total and an optional right-side template column), styled according to the block's accent role and the layout theme. Raises an error if the progress_id is not known.
        
        Parameters:
            progress_id (str): Identifier of the progress block defined in the layout.
            transient (bool): Fallback transient flag used when the block does not specify its own `transient` setting.
        
        Returns:
            Progress: A configured Rich Progress instance ready to be started.
        
        Raises:
            CliLayoutError: If no progress block is registered for `progress_id`.
        """
        info = self._progress_blocks.get(progress_id)
        if info is None:
            raise CliLayoutError(f"Unknown progress block: {progress_id}")
        block = info["block"]
        accent_role = info.get("accent")

        bar_style_token = self._role_style(accent_role or "accent")
        progress_style = str(self._active_flags.get("progress_style", "fill")).strip().lower()
        if progress_style not in {"fill", "dot"}:
            progress_style = "fill"
        if progress_style == "dot":
            bar_column = _DotProgressColumn(self, bar_style_token)
        else:
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


class _DotProgressColumn(ProgressColumn):
    """Progress column that renders a single moving marker along a track."""

    def __init__(self, renderer: "CliLayoutRenderer", style_token: Optional[str]) -> None:
        super().__init__()
        self.renderer = renderer
        self._style_token = style_token

    def render(self, task: Task) -> Text:
        total = task.total or 0
        completed = task.completed or 0
        ratio = 0.0
        if total:
            try:
                ratio = max(0.0, min(1.0, float(completed) / float(total)))
            except ZeroDivisionError:
                ratio = 0.0
        width = max(10, min(28, self.renderer._console_width() // 3))
        if self.renderer._using_ascii_symbols():
            track_char = "-"
            marker = "*"
        else:
            track_char = "─"
            marker = "●"
        bar_chars = [track_char] * width
        index = 0
        if width > 1:
            index = min(width - 1, round(ratio * (width - 1)))
        bar_chars[index] = marker
        bar_text = "".join(bar_chars)
        rich_style = self.renderer._rich_style_from_token(self._style_token)
        if rich_style:
            return Text(bar_text, style=rich_style)
        return Text(bar_text)


class _TemplateProgressColumn(ProgressColumn):
    """Rich progress column that renders using a layout template."""
    def __init__(self, renderer: CliLayoutRenderer, progress_id: str, template: str) -> None:
        """
        Initialize the progress column with its renderer, the target progress block id, and the template used to render the right-side label.
        
        Parameters:
            renderer (CliLayoutRenderer): Renderer instance used to render templates and access theme/symbols.
            progress_id (str): Identifier of the progress block this column is bound to.
            template (str): Template string used to produce the column's right-side label from the current progress state.
        """
        super().__init__()
        self.renderer = renderer
        self.progress_id = progress_id
        self.template = template

    def render(self, task: Task) -> Any:
        """
        Render the dynamic right-side label for a progress bar using the renderer's active context.
        
        Parameters:
        	task (Task): The progress task object whose completed, total, and percentage values will be exposed as `progress` in the template context.
        
        Returns:
        	str: The rendered and post-processed label string, truncated to a single segment if the console width is below the configured `truncate_right_label_min_cols`.
        """
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