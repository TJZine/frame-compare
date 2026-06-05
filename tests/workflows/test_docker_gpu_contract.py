from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from ._helpers import SCRIPT_SUBPROCESS_TIMEOUT_SECONDS
from ._helpers import bash_executable_or_skip as _bash_executable_or_skip
from ._helpers import bash_path_or_skip as _bash_path_or_skip
from ._helpers import read_text_or_fail as _read_text_or_fail
from ._helpers import with_bash_env as _with_bash_env
from ._helpers import write_bash_env as _write_bash_env


def _write_nvidia_icd(path: Path) -> None:
    path.write_text(
        '{"file_format_version":"1.0.0","ICD":{"library_path":"libGLX_nvidia.so.0"}}',
        encoding="utf-8",
    )


def test_gpu_override_keeps_default_services_unchanged(repo_root: Path) -> None:
    base_compose = yaml.safe_load(_read_text_or_fail(repo_root / "docker-compose.yml"))
    gpu_override = yaml.safe_load(_read_text_or_fail(repo_root / "docker-compose.gpu-nvidia.yml"))

    base_services = base_compose["services"]
    override_services = gpu_override["services"]

    assert set(override_services) == {"frame-compare", "frame-compare-test", "frame-compare-run"}

    for service_name in override_services:
        assert "gpus" not in base_services[service_name]
        assert "profiles" not in base_services[service_name]
        base_env = base_services[service_name].get("environment", [])
        assert "LIBGL_ALWAYS_SOFTWARE=0" not in base_env
        assert "NVIDIA_VISIBLE_DEVICES=all" not in base_env
        assert "NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics" not in base_env

        assert override_services[service_name]["profiles"] == ["gpu-nvidia"]
        assert override_services[service_name]["gpus"] == "all"
        assert "LIBGL_ALWAYS_SOFTWARE=0" in override_services[service_name]["environment"]
        assert "NVIDIA_VISIBLE_DEVICES=all" in override_services[service_name]["environment"]
        assert (
            "NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics"
            in override_services[service_name]["environment"]
        )


def test_verify_docker_gpu_script_emits_compose_version_fallback(
    repo_root: Path, tmp_path: Path
) -> None:
    bash = _bash_executable_or_skip()
    bash_env = tmp_path / "docker-fallback.env"
    _write_bash_env(
        bash_env,
        """
docker() {
  if [[ "$1" == "compose" && "$2" == "version" && "${3:-}" == "--short" ]]; then
    printf '2.29.7\\n'
    return 0
  fi
  if [[ "$1" == "compose" && "$2" == "version" ]]; then
    printf 'Docker Compose version v2.29.7\\n'
    return 0
  fi
  if [[ "$1" == "info" ]]; then
    return 0
  fi
  echo "unexpected docker invocation: $*" >&2
  return 99
}
""",
    )

    result = subprocess.run(
        [bash, "tools/verify_docker_gpu.sh", "--no-build"],
        cwd=repo_root,
        env=_with_bash_env({}, bash_env),
        check=False,
        capture_output=True,
        text=True,
        timeout=SCRIPT_SUBPROCESS_TIMEOUT_SECONDS,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 27
    assert "Docker Compose 2.30.0 or later is required" in combined
    assert "DOCKER_GPU_FALLBACK command_begin" in combined
    assert "docker run --rm --gpus all" in combined
    assert "NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics" in combined
    assert "bash tools/verify_docker_gpu.sh --inside-container" in combined


def test_verify_docker_gpu_script_accepts_suffixed_compose_version(
    repo_root: Path, tmp_path: Path
) -> None:
    bash = _bash_executable_or_skip()
    bash_env = tmp_path / "docker-suffixed-version.env"
    _write_bash_env(
        bash_env,
        """
docker() {
  if [[ "$1" == "compose" && "$2" == "version" && "${3:-}" == "--short" ]]; then
    printf '2.30.0-desktop.1\\n'
    return 0
  fi
  if [[ "$1" == "compose" && "$2" == "version" ]]; then
    printf 'Docker Compose version v2.30.0-desktop.1\\n'
    return 0
  fi
  if [[ "$1" == "info" ]]; then
    return 0
  fi
  if [[ "$1" == "compose" && " $* " == *" run "* ]]; then
    printf 'compose run ok\\n'
    return 0
  fi
  echo "unexpected docker invocation: $*" >&2
  return 99
}
""",
    )

    result = subprocess.run(
        [bash, "tools/verify_docker_gpu.sh", "--no-build"],
        cwd=repo_root,
        env=_with_bash_env({}, bash_env),
        check=False,
        capture_output=True,
        text=True,
        timeout=SCRIPT_SUBPROCESS_TIMEOUT_SECONDS,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0
    assert "Docker Compose 2.30.0 or later is required" not in combined
    assert "DOCKER_GPU_FALLBACK command_begin" not in combined
    assert "compose run ok" in combined


def test_verify_docker_gpu_script_rejects_mixed_software_selected_device(
    repo_root: Path, tmp_path: Path
) -> None:
    bash = _bash_executable_or_skip()
    icd_dir = tmp_path / "icd"
    icd_dir.mkdir()
    _write_nvidia_icd(icd_dir / "nvidia_icd.json")
    bash_icd_dir = _bash_path_or_skip(bash, icd_dir)

    bash_env = tmp_path / "docker-mixed-device.env"
    _write_bash_env(
        bash_env,
        """
nvidia-smi() {
  printf 'GPU 0: NVIDIA RTX 6000 Ada Generation (UUID: GPU-1234)\\n'
}

vulkaninfo() {
  printf 'GPU0 : llvmpipe (LLVM 17.0.0, 256 bits)\\n'
  printf 'GPU1 : NVIDIA RTX 6000 Ada Generation\\n'
}
""",
    )

    result = subprocess.run(
        [bash, "tools/verify_docker_gpu.sh", "--inside-container"],
        cwd=repo_root,
        env=_with_bash_env(
            {
                "FRAME_COMPARE_GPU_ICD_SEARCH_DIRS": bash_icd_dir,
                "FRAME_COMPARE_GPU_PLACEBO_PROOF_CMD": "printf 'DOCKER_GPU_PROOF placebo_tonemap=ok\\n'",
            },
            bash_env,
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=SCRIPT_SUBPROCESS_TIMEOUT_SECONDS,
    )

    combined = result.stdout + result.stderr
    assert result.returncode != 0
    assert "DOCKER_GPU_PROOF nvidia_visible=ok" in combined
    assert "DOCKER_GPU_PROOF vulkan_icd=" in combined
    assert "nvidia_icd.json" in combined
    assert "DOCKER_GPU_PROOF vulkan_device=llvmpipe (LLVM 17.0.0, 256 bits)" in combined
    assert "DOCKER_GPU_PROOF vulkan_hardware=ok" not in combined
    assert "DOCKER_GPU_PROOF placebo_tonemap=ok" not in combined
    assert "software-backed" in combined


def test_verify_docker_gpu_script_accepts_selected_nvidia_device(
    repo_root: Path, tmp_path: Path
) -> None:
    bash = _bash_executable_or_skip()
    icd_dir = tmp_path / "icd"
    icd_dir.mkdir()
    nvidia_icd = icd_dir / "nvidia_icd.json"
    _write_nvidia_icd(nvidia_icd)
    bash_icd_dir = _bash_path_or_skip(bash, icd_dir)

    bash_env = tmp_path / "docker-selected-nvidia.env"
    _write_bash_env(
        bash_env,
        """
nvidia-smi() {
  printf 'GPU 0: NVIDIA RTX 6000 Ada Generation (UUID: GPU-1234)\\n'
}

vulkaninfo() {
  printf 'GPU0 : NVIDIA RTX 6000 Ada Generation\\n'
  printf 'GPU1 : lavapipe (LLVM 17.0.0, 256 bits)\\n'
}
""",
    )

    result = subprocess.run(
        [bash, "tools/verify_docker_gpu.sh", "--inside-container"],
        cwd=repo_root,
        env=_with_bash_env(
            {
                "FRAME_COMPARE_GPU_ICD_SEARCH_DIRS": bash_icd_dir,
                "FRAME_COMPARE_GPU_PLACEBO_PROOF_CMD": "printf 'DOCKER_GPU_PROOF placebo_tonemap=ok\\n'",
            },
            bash_env,
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=SCRIPT_SUBPROCESS_TIMEOUT_SECONDS,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0
    assert "DOCKER_GPU_PROOF nvidia_visible=ok" in combined
    assert "DOCKER_GPU_PROOF vulkan_icd=" in combined
    assert "nvidia_icd.json" in combined
    assert "DOCKER_GPU_PROOF vulkan_device=NVIDIA RTX 6000 Ada Generation" in combined
    assert "DOCKER_GPU_PROOF vulkan_hardware=ok" in combined
    assert "DOCKER_GPU_PROOF placebo_tonemap=ok" in combined


def test_verify_docker_gpu_script_fails_closed_without_nvidia_icd(
    repo_root: Path, tmp_path: Path
) -> None:
    bash = _bash_executable_or_skip()
    empty_icd_dir = tmp_path / "empty-icd"
    empty_icd_dir.mkdir()

    bash_env = tmp_path / "docker-missing-icd.env"
    _write_bash_env(
        bash_env,
        """
nvidia-smi() {
  printf 'GPU 0: NVIDIA RTX 6000 Ada Generation (UUID: GPU-1234)\\n'
}
""",
    )

    result = subprocess.run(
        [bash, "tools/verify_docker_gpu.sh", "--inside-container"],
        cwd=repo_root,
        env=_with_bash_env(
            {"FRAME_COMPARE_GPU_ICD_SEARCH_DIRS": str(empty_icd_dir)},
            bash_env,
        ),
        check=False,
        capture_output=True,
        text=True,
        timeout=SCRIPT_SUBPROCESS_TIMEOUT_SECONDS,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 24
    assert "DOCKER_GPU_PROOF nvidia_visible=ok" in combined
    assert "unable to locate an NVIDIA Vulkan ICD" in combined
    assert "DOCKER_GPU_PROOF vulkan_hardware=ok" not in combined
    assert "DOCKER_GPU_PROOF placebo_tonemap=ok" not in combined


def test_verify_docker_gpu_script_unsets_default_software_forcing(repo_root: Path) -> None:
    script = _read_text_or_fail(repo_root / "tools" / "verify_docker_gpu.sh")

    assert "unset LIBGL_ALWAYS_SOFTWARE" in script
    assert "VK_ICD_FILENAMES points at a lavapipe ICD" in script
    assert "DOCKER_GPU_PROOF nvidia_visible=ok" in script
    assert "DOCKER_GPU_PROOF vulkan_icd=" in script
    assert "DOCKER_GPU_PROOF vulkan_device=" in script
    assert "DOCKER_GPU_PROOF vulkan_hardware=ok" in script
    assert "DOCKER_GPU_PROOF placebo_tonemap=ok" in script
