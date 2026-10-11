from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import tomllib
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LEGACY_RELEASE_NOTES_RE = re.compile(
    r"^Frame Compare v\S+\. See CHANGELOG\.md at the tagged commit\.$"
)
STABLE_VERSION_RE = re.compile(r"^(?P<base>0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
RC_VERSION_RE = re.compile(
    r"^(?P<base>(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))rc"
    r"(?P<number>[1-9]\d*)$"
)


class ReleaseContractError(RuntimeError):
    """Raised when a requested release is not authorized by repository state."""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate an exact Frame Compare release request.")
    parser.add_argument("--channel", choices=("rc", "stable"), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--main-sha")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--release-notes-output",
        type=Path,
        help="Write the validated version section from CHANGELOG.md to this path.",
    )
    return parser.parse_args()


def _read_package_version(package_init: Path) -> str:
    module = ast.parse(package_init.read_text(encoding="utf-8"), filename=str(package_init))
    for statement in module.body:
        if not isinstance(statement, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            if isinstance(value, str):
                return value
    raise ReleaseContractError(f"Missing string __version__ in {package_init}.")


def _git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def _expected_tag(channel: str, version: str) -> str:
    if channel == "stable":
        if STABLE_VERSION_RE.fullmatch(version) is None:
            raise ReleaseContractError(
                "Stable version must be a final MAJOR.MINOR.PATCH value without RC syntax."
            )
        return f"v{version}"

    match = RC_VERSION_RE.fullmatch(version)
    if match is None:
        raise ReleaseContractError(
            "RC version must use PEP 440 MAJOR.MINOR.PATCHrcN syntax with N >= 1."
        )
    return f"v{match.group('base')}-rc.{match.group('number')}"


def _extract_release_notes(changelog: str, version: str) -> str:
    heading = re.compile(rf"^## \[{re.escape(version)}\][^\r\n]*$", re.MULTILINE)
    matches = list(heading.finditer(changelog))
    if not matches:
        raise ReleaseContractError(
            f"CHANGELOG.md must contain a level-two [{version}] release heading."
        )
    if len(matches) != 1:
        raise ReleaseContractError(
            f"CHANGELOG.md must contain exactly one level-two [{version}] release heading."
        )

    start = matches[0].end()
    next_heading = re.search(r"^## [^\r\n]+$", changelog[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading is not None else len(changelog)
    release_notes = changelog[start:end].strip()
    if not release_notes:
        raise ReleaseContractError(f"CHANGELOG.md [{version}] section must contain release notes.")
    if LEGACY_RELEASE_NOTES_RE.fullmatch(release_notes) is not None:
        raise ReleaseContractError(
            f"CHANGELOG.md [{version}] section must not use the legacy release placeholder."
        )
    return f"{release_notes}\n"


def validate_release_contract(
    *,
    repo_root: Path,
    channel: str,
    version: str,
    tag: str,
    expected_sha: str,
    main_sha: str | None,
) -> str:
    repo_root = repo_root.resolve()
    if SHA_RE.fullmatch(expected_sha) is None:
        raise ReleaseContractError(
            "Expected SHA must be exactly 40 lowercase hexadecimal characters."
        )

    head = _git_head(repo_root)
    if head != expected_sha:
        raise ReleaseContractError(
            f"Checked-out HEAD {head} does not equal expected SHA {expected_sha}."
        )

    expected_tag = _expected_tag(channel, version)
    if tag != expected_tag:
        raise ReleaseContractError(f"{channel} tag must be exactly {expected_tag}; received {tag}.")

    if channel == "stable":
        if main_sha is None or SHA_RE.fullmatch(main_sha) is None:
            raise ReleaseContractError(
                "Stable publication requires an exact 40-character main SHA."
            )
        if main_sha != expected_sha:
            raise ReleaseContractError(
                f"Stable expected SHA {expected_sha} is not current main head {main_sha}."
            )

    with (repo_root / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]
    project_version = project["version"]

    package_name = str(project["name"]).replace("-", "_")
    package_version = _read_package_version(repo_root / "src" / package_name / "__init__.py")
    manifest = json.loads((repo_root / ".release-please-manifest.json").read_text(encoding="utf-8"))
    release_config = json.loads(
        (repo_root / "release-please-config.json").read_text(encoding="utf-8")
    )
    with (repo_root / "uv.lock").open("rb") as lock_file:
        locked_project = next(
            package
            for package in tomllib.load(lock_file)["package"]
            if package["name"] == project["name"] and package.get("source") == {"editable": "."}
        )

    versions = {
        "requested version": version,
        "pyproject.toml": project_version,
        "package __version__": package_version,
        "Release Please manifest": manifest.get("."),
        "uv.lock root editable package": locked_project["version"],
    }
    if len(set(versions.values())) != 1:
        details = ", ".join(f"{owner}={value!r}" for owner, value in versions.items())
        raise ReleaseContractError(f"Release version sources disagree: {details}.")

    release_notes = _extract_release_notes(
        (repo_root / "CHANGELOG.md").read_text(encoding="utf-8"), version
    )

    if channel == "stable":
        forbidden = sorted({"bootstrap-sha", "release-as"} & release_config.keys())
        if forbidden:
            raise ReleaseContractError(
                "Stable publication requires removal of temporary Release Please fields: "
                + ", ".join(forbidden)
                + "."
            )

    return release_notes


def main() -> int:
    args = _parse_args()
    try:
        release_notes = validate_release_contract(
            repo_root=args.repo_root,
            channel=args.channel,
            version=args.version,
            tag=args.tag,
            expected_sha=args.expected_sha,
            main_sha=args.main_sha,
        )
        if args.release_notes_output is not None:
            args.release_notes_output.write_text(release_notes, encoding="utf-8")
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError) as exc:
        raise SystemExit(f"Release contract validation failed: {exc}") from exc
    except ReleaseContractError as exc:
        raise SystemExit(f"Release contract validation failed: {exc}") from exc

    print(
        f"Release contract valid: channel={args.channel} version={args.version} "
        f"tag={args.tag} sha={args.expected_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
