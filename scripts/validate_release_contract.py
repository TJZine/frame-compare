from __future__ import annotations

import ast
import json
import re
import tomllib
from collections.abc import Mapping

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LEGACY_RELEASE_NOTES_RE = re.compile(
    r"^Frame Compare v\S+\. See CHANGELOG\.md at the tagged commit\.$"
)
STABLE_VERSION_RE = re.compile(r"^(?P<base>0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$", re.ASCII)
RC_VERSION_RE = re.compile(
    r"^(?P<base>(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))rc"
    r"(?P<number>[1-9]\d*)$",
    re.ASCII,
)


class ReleaseContractError(RuntimeError):
    """Raised when a requested release is not authorized by repository state."""


VERSION_FILES = (
    ".release-please-manifest.json",
    "pyproject.toml",
    "src/frame_compare/__init__.py",
    "uv.lock",
    "CHANGELOG.md",
)


def _read_package_version(source: str) -> str:
    module = ast.parse(source, filename="src/frame_compare/__init__.py")
    for statement in module.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            if isinstance(value, str):
                return value
    raise ReleaseContractError("Missing string __version__ in src/frame_compare/__init__.py.")


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


def manifest_version(manifest: str) -> str:
    version = json.loads(manifest).get(".")
    if not isinstance(version, str) or STABLE_VERSION_RE.fullmatch(version) is None:
        raise ReleaseContractError("Release Please manifest must name a stable MAJOR.MINOR.PATCH.")
    return version


def contract(files: Mapping[str, str]) -> tuple[str, str]:
    manifest, project_file, module, lock, changelog = (files[name] for name in VERSION_FILES)
    version = manifest_version(manifest)
    project = tomllib.loads(project_file)["project"]
    if project["name"] != "frame-compare":
        raise ReleaseContractError("pyproject.toml must name the frame-compare project.")
    editable_packages = [
        package
        for package in tomllib.loads(lock)["package"]
        if package["name"] == project["name"] and package.get("source") == {"editable": "."}
    ]
    if len(editable_packages) != 1:
        raise ReleaseContractError(
            "uv.lock must contain exactly one editable frame-compare package."
        )
    versions = {
        "Release Please manifest": version,
        "pyproject.toml": project["version"],
        "package __version__": _read_package_version(module),
        "uv.lock root editable package": editable_packages[0]["version"],
    }
    if any(value != version for value in versions.values()):
        details = ", ".join(f"{owner}={value!r}" for owner, value in versions.items())
        raise ReleaseContractError(f"Release version sources disagree: {details}.")
    return version, _extract_release_notes(changelog, version)
