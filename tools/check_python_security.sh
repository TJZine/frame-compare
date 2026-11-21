#!/usr/bin/env bash
set -euo pipefail

# Maintained application, release, and runtime/diagnostic owners. The top-level
# tools directory also holds local experiments, so select its active files.
targets=(
  src/frame_compare
  scripts
  tools/windows_portable
  tools/alignment_benchmark.py
  tools/benchmark_analysis_tiers.py
  tools/docker_runtime_smoke.py
  tools/hdr_still_probe.py
  tools/open_docker_host_target.py
  tools/validate_pip_audit.py
  tools/verify_hdr_still.py
)
for target in "${targets[@]}"; do
  if [[ ! -e "$target" ]]; then
    echo "ERROR: missing Python security target: $target" >&2
    exit 1
  fi
done

uv run --no-sync ruff check "${targets[@]}"
uv run --no-sync ruff format --check "${targets[@]}"
report="$(mktemp)"
trap 'rm -f -- "$report"' EXIT
status=0
uv run --no-sync bandit -c pyproject.toml -r "${targets[@]}" \
  --severity-level medium --format json --output "$report" || status=$?
# Bandit can exit successfully even when it could not scan a target.
uv run --no-sync python - "$report" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for failure in report["errors"]:
    print(f"Bandit could not scan {failure['filename']}: {failure['reason']}", file=sys.stderr)
for finding in report["results"]:
    print(
        f"{finding['filename']}:{finding['line_number']} "
        f"{finding['test_id']} ({finding['issue_severity']}): {finding['issue_text']}",
        file=sys.stderr,
    )
sys.exit(bool(report["errors"] or report["results"] or not report["metrics"]["_totals"]["loc"]))
PY
exit "$status"
