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
INLINE_CODE = re.compile(r"(?<!`)(?P<ticks>`+)(?!`)[^\n]*?(?<!`)(?P=ticks)(?!`)")
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
