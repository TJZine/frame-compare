## 1) Autonomy & Boundaries

- **Ask first** before:
  - Calling *new* external services or changing existing ones’ behavior (beyond the approved set: **slow.pics**, **TMDB**).
  - Making public API/CLI breaking changes.
  - Network operations outside the approved domains or CI egress allowlist.
- **Never**:
  - Commit secrets or tokens; use env vars or secret stores only.
  - Run destructive commands (delete/move large trees, rewrite history) without an approved plan.
  - Auto-upgrade major runtime components (Python, VapourSynth) without an explicit RFC/issue and sign-off.

---

## 2) Repo Invariants

- **Libraries do not exit:** No `sys.exit()` in library code; raise typed exceptions.
- **Configuration:** Lives in **TOML → dataclasses/models**. No hidden globals; functions are pure unless explicitly I/O.
- **Standards:** Type hints and docstrings required. Use `logging` (library-level loggers); no `print` in libraries.
- **Determinism:** Respect seeds and cached metrics for reproducible runs.
- **Platform:** Windows x64 primary; cross-platform changes must keep Windows green.

---

## 3) Dependency & Environment Policy (🔒 baseline: Python **3.11**, VapourSynth **R65**)

> **Goal:** Always ensure **all required dependencies are present and in sync** with the lockfile and runtime **before** running heavy work.

- **Runtime baselines (do not change without approval):**
  - **Python:** 3.11.x (ABI `cp311`)
  - **VapourSynth:** R65 (Windows, 64-bit)
  - **Plugins/Tools:** ffms2, libvs_placebo, etc., matching the above install
- **Install/Sync (required before run):**
  ```bash
  uv sync --frozen
  ```
- **Readiness checks (must pass):**
  ```bash
  uv run python -c "import sys; print(sys.version); print(sys.executable)"
  uv run python - << 'PY'
import importlib.util as u
spec = u.find_spec('vapoursynth')
print('vapoursynth spec:', spec)
try:
    import vapoursynth as vs
    print('vapoursynth OK:', vs.__version__)
except Exception as e:
    print('vapoursynth import error:', e)
PY
  uv run python -m pytest -q
  ```
- **When something is missing/out of sync:**
  - Do **not** hot-patch site-packages from a different interpreter (no cross-ABI paths).
  - Either (A) install the correct wheel for the current Python, or (B) switch the venv to the baseline interpreter.
- **Upgrades policy:**
  - Patch/minor lib bumps are allowed via PR *if* tests are green and the lockfile is updated.
  - **Major runtime changes** (e.g., Python 3.12 + VapourSynth R72) require an RFC/issue describing risks, roll-back plan, and CI matrix updates.

---

## 4) First-Run / Preflight Checklist (agents must run this)

1. `uv sync --frozen`
2. Dependency probe (Python/VapourSynth as above)
3. Load `config.toml`; verify required keys present (fail fast with a clear error)
4. Dry-run: `uv run python -m pytest -q` (should pass; skips native E2E)
5. Network sanity (optional): resolve slow.pics landing page (no upload), TMDB access if configured

---

## 5) Change Management

- **Small changes:** PR with description, unit tests, and updated docs (README/CONFIG/TROUBLESHOOTING if relevant).
- **Feature flags:** Gate risky behavior behind config flags default-off.
- **CI gating:** `uv sync --frozen` + unit tests must pass; native deps mocked in CI.
- **Docs:** Update README and `docs/CONFIG.md` on any new config or CLI option.

---

## 6) Coding Standards

- **Style:** PEP 8 + type hints; mypy-friendly signatures.
- **Errors:** Raise `SlowpicsAPIError`/domain-specific exceptions with concise, user-facing messages.
- **Logging:** Informational on start/finish; warnings for recoverable issues; errors for fatal conditions. No secret values in logs.
- **I/O boundaries:** Keep VapourSynth/FFmpeg interactions isolated to modules designed for it.

---

## 7) Testing & CI

- **Unit tests:** Pure-Python; mock native deps and network. Cover selection heuristics, config parsing, URL construction, and slow.pics field mapping.
- **Determinism tests:** Same inputs + seed → same outputs (except intentional randomness under config).
- **Slow/Native tests:** Optional, opt-in only; never block PRs.
- **CI jobs:** Lint (if present), unit tests, and a quick “repo health” import sweep.

---

## 8) External Services Policy

- **Approved:** slow.pics (legacy endpoints), TMDB (search + metadata), GitHub.
- **Usage constraints:** Respect rate limits; honor `Retry-After`. Include polite backoff and small caches.
- **New service/API:** open an issue; include quota, auth, data retention, and failure plan.

---

## 9) Security & Secrets

- Never commit tokens/keys. Use env vars or CI secret stores.
- Redact URLs/headers in logs if they may contain credentials.
- Review third-party code before adding new deps; pin versions in the lockfile.

---

## 10) Observability & Logging

- Use structured logs for key events (selection window, chosen frames, slow.pics URL).
- On failure, include minimal context (HTTP status, endpoint, attempt count) without secrets.

---

## 11) Agent Checklists

### Pull Request Checklist
- [ ] `uv sync --frozen` and unit tests green
- [ ] Dependency readiness verified (Python 3.11, VapourSynth R65 loaded)
- [ ] New/changed config documented in README/`docs/CONFIG.md`
- [ ] No `sys.exit()` in libraries; exceptions raised instead
- [ ] Logs are informative and secret-free
- [ ] CI passes

### Pre-Run Checklist (local or CI)
- [ ] Config loaded; required keys present
- [ ] Dependency probe OK (Python version, `vapoursynth` import)
- [ ] Native tools/plugins available when needed (ffms2, libvs_placebo)
- [ ] Network calls within approved services/domains only

---

## 12) Compatibility Matrix (for awareness)

| Component     | Baseline | Notes                                   |
|---------------|----------|------------------------------------------|
| Python        | 3.11.x   | Do not switch majors without RFC         |
| VapourSynth   | R65      | Windows x64; matches Python 3.11 (cp311) |
| slow.pics     | Legacy   | Short-link URLs only `/c/{key}`          |
| TMDB          | Enabled  | Requires `tmdb.api_key` in config        |

> If proposing a move to Python 3.12 + VapourSynth R72, open an RFC that updates the matrix, CI images, and dependency checks; include a rollback plan.
