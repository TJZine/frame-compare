---
search:
  exclude: true
---

# Documentation site redesign: repository changes

Part of the [documentation site redesign plan](../2026-10-12-documentation-site-redesign.md).
These are the changes outside the documentation pages: the API generator removal, guard
tests, the docs workflow, contributor and maintainer instructions, and the new style
test.

## Page moves and deletions (unit U3)

Use plain `mv` and `rm`; the orchestrator stages moves and deletions.

```bash
mv docs/windows-portable.md docs/getting-started/windows-portable.md
mv docs/guides/first-comparison.md docs/getting-started/first-comparison.md
rm docs/api.md
mkdir -p docs/internals
python3 -I .tmp/docs-site-redesign/relink.py docs \
  windows-portable.md=getting-started/windows-portable.md \
  guides/first-comparison.md=getting-started/first-comparison.md \
  api.md=-
python3 -I .tmp/docs-site-redesign/convert_reference.py docs
```

`relink.py` must exit 0. On the 2026-10-12 base it updated `getting-started/docker-profiles.md`,
`getting-started/docker.md`, `getting-started/first-comparison.md`, `getting-started/index.md`,
`getting-started/native.md`, `getting-started/windows-portable.md`,
`guides/troubleshooting.md`, `index.md`, and `reference/commands.md`, plus any plan that
linked a moved page. A different list is not a stop; a non-zero exit is.

## API reference removal (unit U3)

Delete the generator, its package, and its tests (`docs/api.md` is deleted above):

```bash
rm scripts/generate_api_docs.py
rm -r scripts/api_docs
rm tests/test_generate_api_docs.py tests/test_api_docs_cli.py tests/test_api_docs_model.py tests/test_api_docs_render.py
```

No other code imports these modules. Two documents still refer to the generator:

- `docs/current-architecture.md`: delete the paragraph beginning "`docs/api.md` is
  generated reference material" (three lines, at line 242 on the base).
- `docs/media-runtime-windows-validation.md`: in the command block that runs the Python
  gates, delete the line `uv run --no-sync python scripts/generate_api_docs.py --check`
  (line 99 on the base).

`tests/fixtures/alignment_oracle/streaming-production-results.json` contains the string
`api_docs` inside recorded data; it is unrelated and stays unchanged.

## `.github/workflows/docs.yml` (unit U3)

- In the shared `paths` list, delete `scripts/generate_api_docs.py` and
  `scripts/api_docs/**`, and add `overrides/**` directly after `zensical.toml`.
- Delete the step named `Check generated API documentation`.

Nothing else in the workflow changes.

## `tests/workflows/test_docs_workflow.py` (unit U3)

- In `EXPECTED_PATHS`, delete `"scripts/generate_api_docs.py"` and
  `"scripts/api_docs/**"`, and add `"overrides/**"`.
- In `test_docs_workflow_builds_strictly_from_locked_docs_group`, delete the assertion on
  the `Check generated API documentation` step (the three lines beginning
  `assert _step_by_name(build, "Check generated API documentation")`).

## `tests/test_cli_contract_docs.py` (unit U3)

In `test_configuration_reference_lists_every_config_key`, replace the `documented =`
statement with:

```python
    documented = set(
        re.findall(
            r"^#### `([a-z_]+(?:\.[a-z_<>]+)+)` \{ #[a-z_.]+ \.fc-key \}$",
            reference,
            flags=re.MULTILINE,
        )
    )
```

The rest of the test is unchanged. It still requires one key block per schema field.

## `tests/windows_portable/test_windows_portable_docs.py` (unit U3)

- Replace every `repo_root / "docs" / "windows-portable.md"` and
  `repo_root / "docs/windows-portable.md"` with
  `repo_root / "docs" / "getting-started" / "windows-portable.md"`.
- Replace `assert "](guides/vsview-review.md)" in portable` with
  `assert "](../guides/vsview-review.md)" in portable`.

## `.agents/project.md` (unit U3)

Delete the table row `| API-reference drift | `uv run --no-sync python scripts/generate_api_docs.py --check` |`.
This is the only agent-file change; it removes a command that no longer exists.

## `docs/ENGINEERING_RUNBOOK.md` (unit U3)

1. In the authority list, change
   "`docs/DECISIONS.md`: historical rationale; `docs/api.md`: generated reference, not a
   compatibility promise by itself." to "`docs/DECISIONS.md`: historical rationale."
2. In "Command Canon", delete the paragraph "API documentation regeneration and drift
   check:" and the code block after it.
3. In the documentation code block, delete the comment line
   `# Check generated API documentation before building the site`, the command line
   after it, and the blank line that follows.
4. Replace the two sentences "`docs/**` owns authored site content, while root
   `zensical.toml` owns site structure, navigation, and built-in presentation features.
   Generated output belongs in the ignored `site/` directory." with: "`docs/**` owns
   authored site content and its assets. Root `zensical.toml` owns site structure,
   navigation, and theme features, and `overrides/` owns the theme templates. Generated
   output belongs in the ignored `site/` directory." Keep the next sentence, which
   begins "Restore the contributor environment".

## `CONTRIBUTING.md`

### Unit U3

In "Documentation development":

- Delete the line `uv run --no-sync python scripts/generate_api_docs.py --check` from the
  first code block.
- Delete the paragraph beginning "`docs/api.md` is generated by".
- Change the first paragraph to: "Authored documentation lives under `docs/`.
  `zensical.toml` owns site navigation and theme features, and `overrides/` owns the
  theme templates. Generated site output belongs in the ignored `site/` directory."

### Unit U9 {#contributing-md}

Replace everything from the heading `### Documentation style` up to, but not including,
`## Architecture and public contracts` with a new `### Documentation style` section
built from the [style guide](style-guide.md), with these adaptations:

1. Heading levels: the style guide's H2 sections become H4 (`####`), its H3 sections
   become bold lead-in paragraphs.
2. Include these style guide sections, in this order: Scope, Voice (with its rules, the
   "not allowed" table, and the three examples), Headings, Page structure, Terminology,
   Command blocks, Terminal output, Configuration snippets, Callouts, Steps, Key blocks,
   Cards, Tables, Links, UI text, keys, and literals, Figures.
3. Replace every reference to units, the plan, or the plan's assets exactly as this
   table says. These are all of them.

    | Style guide text | `CONTRIBUTING.md` text |
    | --- | --- |
    | Scope, Authority pages: "… apply to text a unit adds." | "… apply to text you add." |
    | Voice rule 12: "… or a guard string requires the literal (see [page specifications](pages.md#guard-strings))." | "… or a test requires the literal." |
    | Page structure, item 5: "… when the page specification lists one." | "… when the page has natural follow-on pages." |
    | Page structure, item 1: "The [page specifications](pages.md) give the exact text." | "Keep it to one sentence of 160 characters or fewer." |
    | Configuration snippets: "Every snippet must load with the configuration schema (the TOML check in the plan's [verification section](…))." | "Every snippet must load with the configuration schema: `ConfigSchema(**tomllib.loads(snippet))` must succeed." |
    | Key blocks: "Unit U3 creates them with `convert_reference.py`; later edits follow the same shape." | "Use this shape for every key and option." |

4. In Voice, rule 11, keep the link target as a code span
   (`docs/reference/requirements.md`).
5. After the "not allowed" table, keep the sentence that names
   `tests/workflows/test_docs_style.py`.
6. Keep the three bullets above the old "Audience and voice" heading that are not in the
   style guide ("Keep task guides separate from maintainer contracts.", "Update the
   authoritative contract in the same change when public behavior changes.", "Redact
   private paths, source names, and secrets; prefer generic filenames and a clean
   capture workspace over redaction.") as a short list directly after Scope.

## `tests/workflows/test_docs_style.py` (unit U9, new)

The voice rules that a machine can check reliably are the banned words. This test keeps
them out of user pages, including text written later by people or agents.

```python
"""Keep promotional and filler wording out of the user documentation."""

from __future__ import annotations

import re
from pathlib import Path

USER_FILES = ("README.md", "INSTALL-WINDOWS.md", "docs/index.md")
USER_DIRS = ("docs/getting-started", "docs/guides", "docs/reference", "docs/internals")
BANNED = (
    "simply",
    "just",
    "easy",
    "easily",
    "powerful",
    "seamless",
    "seamlessly",
    "robust",
    "blazing",
    "serious",
    "effortless",
    "effortlessly",
    "intuitive",
    "comprehensive",
    "cutting-edge",
    "state-of-the-art",
    "best-in-class",
    "world-class",
    "game-changer",
    "revolutionize",
    "unlock",
    "unleash",
    "elevate",
    "empower",
    "supercharge",
    "streamline",
    "leverage",
    "delve",
    "harness",
    "journey",
    "landscape",
    "realm",
    "crucial",
    "vital",
    "trustworthy",
    "in summary",
    "ultimately",
    "that's it",
    "it's worth noting",
    "in order to",
    "note that",
    "please",
    "not just",
    "more than just",
)
FENCED = re.compile(
    r"^[ \t]*(?P<fence>`{3,}|~{3,}).*?^[ \t]*(?P=fence)[ \t]*$", re.MULTILINE | re.DOTALL
)
INLINE_CODE = re.compile(r"`[^`\n]*`")
WORDS = re.compile(r"\b(" + "|".join(re.escape(term) for term in BANNED) + r")\b", re.IGNORECASE)


def _user_pages(repo_root: Path) -> list[Path]:
    pages = [repo_root / name for name in USER_FILES]
    for directory in USER_DIRS:
        pages.extend(sorted((repo_root / directory).rglob("*.md")))
    return pages


def test_user_pages_avoid_promotional_and_filler_words(repo_root: Path) -> None:
    findings: list[str] = []
    for page in _user_pages(repo_root):
        prose = INLINE_CODE.sub("", FENCED.sub("", page.read_text(encoding="utf-8")))
        for line in prose.splitlines():
            for match in WORDS.finditer(line):
                relative = page.relative_to(repo_root).as_posix()
                findings.append(f"{relative}: {match.group(0)!r} in {line.strip()[:80]!r}")
    assert not findings, "\n".join(findings)
```

Line numbers are not reported because code-fence removal shifts them; the excerpt
identifies the line. The test uses the `repo_root` fixture that the other
`tests/workflows` modules use.

Before committing, run it against the integrated pages. Any finding is fixed in the page,
not by editing `BANNED`. If a finding is a legitimate technical use that cannot be
reworded, report `blocked` with the line.

## Exit-code sync test (unit U8)

The Commands page copies the contract's exit-code table so readers find it in Reference.
This test keeps the copy identical. Add it to `tests/test_cli_contract_docs.py`:

```python
def test_commands_reference_exit_codes_match_contract() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    commands = (repo_root / "docs" / "reference" / "commands.md").read_text(encoding="utf-8")
    row = re.compile(r"^\| `(\d+)` \| (.+?) \|$", re.MULTILINE)

    contract_rows = row.findall(
        contract.split("## Exit Codes And Error Families", 1)[1].split("\n## ", 1)[0]
    )
    commands_rows = row.findall(commands.split("## Exit codes", 1)[1].split("\n## ", 1)[0])

    assert len(contract_rows) == 8
    assert commands_rows == contract_rows
```
