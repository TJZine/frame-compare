from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any


def _load_devcontainer(repo_root: Path) -> dict[str, Any]:
    path = repo_root / ".devcontainer" / "devcontainer.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_mount(mount: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in mount.split(","):
        key, separator, value = part.partition("=")
        parsed[key] = value if separator else ""
    return parsed


def _dockerfile_stages(dockerfile: str) -> list[tuple[str, str, str]]:
    matches = list(
        re.finditer(
            r"^FROM\s+(?P<base>\S+)\s+AS\s+(?P<name>\S+)\s*$",
            dockerfile,
            re.MULTILINE,
        )
    )
    return [
        (
            match.group("base"),
            match.group("name"),
            dockerfile[
                match.end() : matches[index + 1].start() if index + 1 < len(matches) else None
            ],
        )
        for index, match in enumerate(matches)
    ]


def test_devcontainer_uses_isolated_locked_backend_environment(repo_root: Path) -> None:
    config = _load_devcontainer(repo_root)

    assert config["build"] == {
        "dockerfile": "../Dockerfile",
        "context": "..",
        "target": "devcontainer",
    }
    assert (
        config["customizations"]["vscode"]["settings"]["python.defaultInterpreterPath"]
        == "/workspace/frame-compare/.venv/bin/python"
    )

    mounts = [_parse_mount(mount) for mount in config["mounts"]]
    venv_mounts = [
        mount for mount in mounts if mount.get("target") == "${containerWorkspaceFolder}/.venv"
    ]
    assert venv_mounts == [
        {
            "source": "${localWorkspaceFolderBasename}-${devcontainerId}-venv",
            "target": "${containerWorkspaceFolder}/.venv",
            "type": "volume",
        }
    ]

    assert shlex.split(config["postCreateCommand"]) == [
        "uv",
        "venv",
        "--clear",
        "--system-site-packages",
        ".venv",
        "&&",
        "uv",
        "sync",
        "--group",
        "dev",
        "--frozen",
    ]
    assert config["containerEnv"] == {
        "VAPOURSYNTH_EXTRA_PLUGIN_PATH": "/opt/vapoursynth-extra-plugins"
    }


def test_devcontainer_docker_stage_only_owns_the_venv_mount_target(repo_root: Path) -> None:
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    stages = _dockerfile_stages(dockerfile)
    stage_names = [name for _, name, _ in stages]
    stage_by_name = {name: (base, body) for base, name, body in stages}

    assert stage_names[-1] == "default-runtime"
    assert stage_by_name["devcontainer"][0] == "runtime"
    assert stage_by_name["gui-linux"][0] == "runtime"
    assert stage_by_name["default-runtime"][0] == "runtime"

    instructions = [
        line.strip()
        for line in stage_by_name["devcontainer"][1].splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert instructions == [
        "USER root",
        "RUN install -d -m 0777 -o framecompare -g framecompare /workspace/frame-compare/.venv",
        "USER framecompare",
        "WORKDIR /workspace/frame-compare",
    ]
