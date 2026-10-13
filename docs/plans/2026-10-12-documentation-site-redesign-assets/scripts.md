---
search:
  exclude: true
---

# Documentation site redesign: scripts

Part of the [documentation site redesign plan](../2026-10-12-documentation-site-redesign.md).
These scripts are one-time tools for the units that call them. They are not added to the
repository. Write each one exactly as given to `.tmp/docs-site-redesign/` and run it from
the repository root with `python3 -I`. Each script was run against a scratch copy of the
documentation on 2026-10-12 and produced the result its unit expects.

## `relink.py`

Unit U3 runs it once, after moving the pages:

```bash
python3 -I .tmp/docs-site-redesign/relink.py docs \
  windows-portable.md=getting-started/windows-portable.md \
  guides/first-comparison.md=getting-started/first-comparison.md \
  api.md=-
```

It rewrites every relative Markdown link and raw-HTML `src`/`href` in `docs/**/*.md` so
it points at the moved files, resolves links inside a moved page against its old
location, prints each file it changed, and exits 1 if any link still targets the deleted
`api.md`. It rewrites links in plans and reviews as well; that is intended, because the
strict build checks every page under `docs/`.

```python
"""Rewrite relative links and image paths in docs/ after page moves.

Usage: python relink.py DOCS_DIR OLD=NEW [OLD=NEW ...]
Paths are relative to DOCS_DIR. Pages must already be moved. Links inside a moved
page are resolved against its old location. A NEW of "-" marks a deleted page and
reports every link that still points at it.
"""
import posixpath, re, sys
from pathlib import Path

docs = Path(sys.argv[1])
moves = dict(arg.split("=", 1) for arg in sys.argv[2:])
reverse = {new: old for old, new in moves.items() if new != "-"}
LINK = re.compile(r'(\]\(|(?:href|src)=")([^)"\s#]+)(#[^)"\s]*)?')
problems = 0
for path in sorted(docs.rglob("*.md")):
    rel_new = path.relative_to(docs).as_posix()
    rel_old = reverse.get(rel_new, rel_new)
    text = path.read_text(encoding="utf-8")

    def fix(m):
        global problems
        prefix, target, anchor = m.group(1), m.group(2), m.group(3) or ""
        if ":" in target or target.startswith("/"):
            return m.group(0)
        old_target = posixpath.normpath(posixpath.join(posixpath.dirname(rel_old), target))
        new_target = moves.get(old_target, old_target)
        if new_target == "-":
            print(f"DELETED TARGET {rel_new}: {target}")
            problems += 1
            return m.group(0)
        rewritten = posixpath.relpath(new_target, posixpath.dirname(rel_new) or ".")
        return f"{prefix}{rewritten}{anchor}"

    updated = LINK.sub(fix, text)
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        print(f"updated {rel_new}")
sys.exit(1 if problems else 0)
```

## `convert_reference.py`

Unit U3 runs it once: `python3 -I .tmp/docs-site-redesign/convert_reference.py docs`.
It converts every `| Key | Values | Default | Effect |` table in
`docs/reference/configuration.md` and the Run options table in
`docs/reference/commands.md` into key blocks, grouped under the six `run --help`
headings. On the 2026-10-12 base it produces 84 configuration key blocks and 26 run
option blocks.

```python
"""Convert reference tables in configuration.md and commands.md to key blocks.

Usage: python convert_reference.py DOCS_DIR
Only these tables are converted:
- configuration.md: every table whose header is | Key | Values | Default | Effect |
- commands.md: the Run table whose header is
  | Option | Value | Effect | Saved by `--write-config` |
Cell text is copied unchanged. The script stops if a table has an unexpected shape.
"""
import re, sys
from pathlib import Path

docs = Path(sys.argv[1])
RUN_GROUPS = [
    ("Workspace and configuration", ["--root", "--config"]),
    ("Sources and frame selection", ["--input", "--frames", "--random-frame-count", "--dark-frame-count", "--bright-frame-count", "--motion-frame-count", "--seed"]),
    ("Rendering and alignment", ["--tm-preset", "--tm-target", "--tm-curve", "--overlay", "--force-interactive-alignment"]),
    ("Reports and publishing", ["--no-upload"]),
    ("Planning and diagnostics", ["--skip-analysis", "--skip-metadata", "--no-cache", "--from-cache-only", "--dry-run", "--write-config", "--diagnose-paths"]),
    ("Output modes", ["--json", "--no-color", "--quiet", "--verbose"]),
]


def cells(line):
    parts = [c.strip() for c in line.strip().strip("|").split("|")]
    return parts


def sentence(text):
    text = text.strip()
    if not text:
        sys.exit("empty effect cell")
    text = text[0].upper() + text[1:]
    return text if text.endswith((".", ")")) else text + "."


def tables(lines, header):
    i = 0
    while i < len(lines):
        if lines[i].strip() == header:
            if not re.fullmatch(r"\|( --- \|)+", lines[i + 1].strip()):
                sys.exit(f"bad separator after {header!r}")
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            yield i, j
            i = j
        else:
            i += 1


def config_block(row):
    key, values, default, effect = row
    m = re.fullmatch(r"`([a-z_]+(?:\.[a-z_<>]+)+)`", key)
    if not m:
        sys.exit(f"unexpected key cell {key!r}")
    name = m.group(1)
    anchor = name.replace("<selector>", "selector")
    return [
        f"#### `{name}` {{ #{anchor} .fc-key }}",
        "",
        "Values",
        f":   {values}",
        "",
        "Default",
        f":   {default}",
        "",
        sentence(effect),
        "",
    ]


def convert_configuration(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    out, last = [], 0
    for start, end in tables(lines, "| Key | Values | Default | Effect |"):
        out += lines[last:start]
        for line in lines[start + 2:end]:
            row = cells(line)
            if len(row) != 4:
                sys.exit(f"configuration row has {len(row)} cells: {line}")
            out += config_block(row)
        if out[-1] == "":
            out.pop()
        last = end
    out += lines[last:]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def option_block(row):
    option, value, effect, saved = row
    names = re.findall(r"`(-[^`]+)`", option)
    if not names:
        sys.exit(f"unexpected option cell {option!r}")
    anchor = "run-" + names[0].lstrip("-")
    heading = ", ".join(f"`{n}`" for n in names)
    block = [f"#### {heading} {{ #{anchor} .fc-key }}", ""]
    if value != "—":
        block += ["Value", f":   {value}", ""]
    block += ["Saved by `--write-config`", f":   {saved}", "", sentence(effect), ""]
    return names[0], block


def convert_commands(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    header = "| Option | Value | Effect | Saved by `--write-config` |"
    found = list(tables(lines, header))
    if len(found) != 1:
        sys.exit(f"expected one Run table, found {len(found)}")
    start, end = found[0]
    blocks = {}
    for line in lines[start + 2:end]:
        row = cells(line)
        if len(row) != 4:
            sys.exit(f"run row has {len(row)} cells: {line}")
        name, block = option_block(row)
        blocks[name] = block
    grouped = [n for _, names in RUN_GROUPS for n in names]
    if sorted(grouped) != sorted(blocks):
        sys.exit(f"group map mismatch: {sorted(set(grouped) ^ set(blocks))}")
    out = lines[:start]
    for title, names in RUN_GROUPS:
        out += [f"### {title}", ""]
        for n in names:
            out += blocks[n]
    if out[-1] == "":
        out.pop()
    out += lines[end:]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


convert_configuration(docs / "reference" / "configuration.md")
convert_commands(docs / "reference" / "commands.md")
print("converted")
```

## `convert_troubleshooting.py`

Unit U7 runs it once, before editing the page:
`python3 -I .tmp/docs-site-redesign/convert_troubleshooting.py docs`. It turns the 20
rows of the Common problems table into H3 entries.

```python
"""Convert the Troubleshooting "Common problems" table into one H3 entry per row.

Usage: python convert_troubleshooting.py DOCS_DIR
The symptom cell becomes the H3 text unchanged. The "What to do" cell becomes the
paragraph below it, with its first letter upper-cased and a final period added.
The script stops if the table is missing or a row has an unexpected shape.
"""
import sys
from pathlib import Path

path = Path(sys.argv[1]) / "guides" / "troubleshooting.md"
lines = path.read_text(encoding="utf-8").splitlines()
header = "| Symptom | What to do |"
try:
    start = lines.index(header)
except ValueError:
    sys.exit("Common problems table not found")
if lines[start + 1].strip() != "| --- | --- |":
    sys.exit("unexpected separator")
end = start + 2
while end < len(lines) and lines[end].startswith("|"):
    end += 1
entries = []
for line in lines[start + 2:end]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) != 2:
        sys.exit(f"row has {len(cells)} cells: {line}")
    symptom, action = cells
    action = action[0].upper() + action[1:]
    if not action.endswith((".", ")")):
        action += "."
    entries += [f"### {symptom}", "", action, ""]
if entries[-1] == "":
    entries.pop()
path.write_text("\n".join(lines[:start] + entries + lines[end:]) + "\n", encoding="utf-8")
print(f"converted {len(entries) // 4 + 1} entries")
```

## `check_assets.py`

The orchestrator runs it at each wave's integration: `python3 -I
.tmp/docs-site-redesign/check_assets.py docs`. The strict build does not check image
paths written as raw HTML; this script does. It exits 1 and lists every missing file.

```python
"""Report raw-HTML and Markdown references to files that do not exist under docs/."""
import posixpath, re, sys
from pathlib import Path
docs = Path(sys.argv[1])
REF = re.compile(r'(?:\]\(|(?:href|src)=")([^)"\s#?]+)')
missing = 0
for page in sorted(docs.rglob("*.md")):
    rel = page.relative_to(docs).as_posix()
    if rel.startswith(("plans/", "prompts/", "reviews/", "archive/")):
        continue
    for target in REF.findall(page.read_text(encoding="utf-8")):
        if ":" in target or target.startswith("/") or target.endswith(".md"):
            continue
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(rel), target))
        if not (docs / resolved).exists():
            print(f"{rel}: {target}")
            missing += 1
sys.exit(1 if missing else 0)
```
