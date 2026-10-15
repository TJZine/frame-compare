"""Start a new integration cycle after an approved, published squash release."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast

REPOSITORY = "TJZine/frame-compare"
SHA = re.compile(r"[0-9a-f]{40}")
STABLE_TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


class RecreationError(RuntimeError):
    """Refusal that preserves integration work for manual reconciliation."""


class RepositoryAPI(Protocol):
    def get(self, path: str) -> dict[str, Any]: ...

    def pulls(self, path: str) -> list[dict[str, Any]]: ...


class GitHub:
    def _read(self, path: str, *, paginate: bool = False) -> Any:
        command = ["gh", "api"]
        if paginate:
            command += ["--paginate", "--slurp"]
        command.append(f"repos/{REPOSITORY}/{path}")
        environment = os.environ.copy()
        for name in ("GH_DEBUG", "DEBUG", "GH_HOST", "GH_ENTERPRISE_TOKEN"):
            environment.pop(name, None)
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, env=environment, timeout=60, check=True
            )
            return json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            raise RecreationError(
                "GitHub metadata unavailable; integration branch unchanged."
            ) from None

    def get(self, path: str) -> dict[str, Any]:
        value = self._read(path)
        if not isinstance(value, dict):
            raise RecreationError("GitHub returned invalid object metadata.")
        return cast(dict[str, Any], value)

    def pulls(self, path: str) -> list[dict[str, Any]]:
        pages = self._read(path, paginate=True)
        if not isinstance(pages, list):
            raise RecreationError("GitHub returned invalid pull-request pages.")
        result: list[dict[str, Any]] = []
        for page in cast(list[Any], pages):
            if not isinstance(page, list):
                raise RecreationError("GitHub returned invalid pull-request pages.")
            for item in cast(list[Any], page):
                if not isinstance(item, dict):
                    raise RecreationError("GitHub returned invalid pull-request metadata.")
                result.append(cast(dict[str, Any], item))
        return result


def git(*arguments: str) -> str:
    try:
        return subprocess.run(
            ["git", "-c", "credential.helper=", *arguments],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise RecreationError(
            f"Git {arguments[0]} refused/failed. Inspect remote refs, protection and maintenance "
            "authorization; no automatic retry or protection bypass was attempted."
        ) from None


def ref(git_command: Callable[..., str], name: str) -> str | None:
    lines = git_command("ls-remote", "--refs", "origin", name).splitlines()
    if not lines:
        return None
    if len(lines) != 1 or len(lines[0].split()) != 2:
        raise RecreationError("Git returned ambiguous remote ref metadata.")
    sha, returned_name = lines[0].split()
    if returned_name != name or SHA.fullmatch(sha) is None:
        raise RecreationError("Git returned invalid remote ref metadata.")
    return sha


def branch(pr: dict[str, Any], side: str) -> dict[str, Any]:
    value = pr.get(side)
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def owned_branch(pr: dict[str, Any], side: str, name: str) -> bool:
    value = branch(pr, side)
    repository = value.get("repo")
    return (
        value.get("ref") == name
        and isinstance(repository, dict)
        and cast(dict[str, Any], repository).get("full_name") == REPOSITORY
    )


def recreate(
    api: RepositoryAPI, git_command: Callable[..., str], release_sha: str, release_tag: str
) -> str:
    if SHA.fullmatch(release_sha) is None or STABLE_TAG.fullmatch(release_tag) is None:
        raise RecreationError("An exact commit SHA and stable release tag are required.")
    release = api.get(f"releases/tags/{release_tag}")
    if (
        release.get("draft") is not False
        or release.get("prerelease") is not False
        or release.get("tag_name") != release_tag
        or release.get("target_commitish") != release_sha
        or not release.get("published_at")
    ):
        raise RecreationError("The exact stable release has not been published.")
    version = release_tag[1:]
    titles = {
        f"chore(release): {version}",
        f"chore(release): prepare Frame Compare v{version}",
        f"chore(release)!: prepare Frame Compare v{version}",
    }
    promotions = [
        pr
        for pr in api.pulls(f"commits/{release_sha}/pulls?per_page=100")
        if pr.get("merged_at")
        and pr.get("merge_commit_sha") == release_sha
        and pr.get("title") in titles
        and owned_branch(pr, "base", "main")
        and owned_branch(pr, "head", "pre-release")
    ]
    if len(promotions) != 1:
        raise RecreationError("Require exactly one merged pre-release -> main release PR.")
    accepted_head = promotions[0]["head"].get("sha", "")
    if not isinstance(accepted_head, str) or SHA.fullmatch(accepted_head) is None:
        raise RecreationError("The accepted integration head is invalid.")
    archive = f"refs/tags/pre-release-archive/{release_tag}-{accepted_head}"

    def check_refs() -> tuple[str | None, str | None]:
        if ref(git_command, "refs/heads/main") != release_sha:
            raise RecreationError(
                "main advanced; branch maintenance requires manual reconciliation."
            )
        if ref(git_command, f"refs/tags/{release_tag}") != release_sha:
            raise RecreationError("Stable tag does not point directly to the published commit.")
        return ref(git_command, "refs/heads/pre-release"), ref(git_command, archive)

    def check_open_prs() -> None:
        prs = api.pulls("pulls?state=open&per_page=100")
        if any(
            branch(pr, "base").get("ref") == "pre-release"
            or owned_branch(pr, "head", "pre-release")
            for pr in prs
        ):
            raise RecreationError("Open PRs depend on pre-release; integration branch retained.")

    check_open_prs()
    current, saved = check_refs()
    if current == release_sha and saved == accepted_head:
        return f"Already recreated; accepted history retained at {archive}."
    if current != accepted_head:
        raise RecreationError("pre-release changed since promotion; integration work retained.")
    if saved is not None:
        raise RecreationError("Archive ref already exists; refusing to overwrite or reuse it.")
    git_command("fetch", "--no-tags", "origin", release_sha, accepted_head)
    parents = git_command("rev-list", "--parents", "-n", "1", release_sha).split()
    if len(parents) != 2 or parents[0] != release_sha:
        raise RecreationError("Release promotion must be a single-parent squash commit.")
    if git_command("rev-parse", f"{release_sha}^{{tree}}") != git_command(
        "rev-parse", f"{accepted_head}^{{tree}}"
    ):
        raise RecreationError("Published tree differs from the accepted integration tree.")
    # API queries do not lock GitHub PR creation. Maintenance approval confirms a
    # development freeze, including local/unopened branches; the lease guards commits.
    check_open_prs()
    if check_refs() != (accepted_head, None):
        raise RecreationError("Integration/archive refs changed before recreation.")
    git_command(
        "push",
        "--atomic",
        f"--force-with-lease=refs/heads/pre-release:{accepted_head}",
        f"--force-with-lease={archive}:",
        "origin",
        f"{accepted_head}:{archive}",
        f"{release_sha}:refs/heads/pre-release",
    )
    if check_refs() != (release_sha, accepted_head):
        raise RecreationError(
            f"Recheck recreation state; accepted history is retained at {archive}."
        )
    return f"pre-release starts at {release_sha}; accepted history retained at {archive}."


def main() -> int:
    try:
        if (
            os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
        ):
            raise RecreationError(
                "Branch maintenance is restricted to this repository's main workflow."
            )
        if not os.environ.get("PRE_RELEASE_RESET_TOKEN"):
            raise RecreationError(
                "Configure the dedicated branch-maintenance identity before recreation."
            )
        # Only an HTTPS origin in this repository may receive the maintenance credential.
        if (
            git("remote", "get-url", "origin").removesuffix(".git")
            != f"https://github.com/{REPOSITORY}"
        ):
            raise RecreationError("Unexpected Git origin; maintenance credential was not used.")
        with tempfile.TemporaryDirectory(prefix="frame-compare-maintenance-") as directory:
            askpass = Path(directory) / "askpass.py"
            askpass.write_text(
                "#!/usr/bin/env python3\nimport os, sys\n"
                'print("x-access-token" if "username" in sys.argv[1].lower() '
                'else os.environ["PRE_RELEASE_RESET_TOKEN"])\n',
                encoding="utf-8",
            )
            askpass.chmod(0o700)
            os.environ["GIT_ASKPASS"] = str(askpass)
            os.environ["GIT_TERMINAL_PROMPT"] = "0"
            print(
                recreate(
                    GitHub(),
                    git,
                    os.environ.get("EXPECTED_SHA", ""),
                    os.environ.get("RELEASE_TAG", ""),
                )
            )
    except RecreationError as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
