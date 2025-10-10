# Deep Code Review Findings

## CRITICAL: CLI layout expression evaluation enables arbitrary code execution
**File:** src/cli_layout.py:323-358, 587-598, 918-969
**Risk Level:** HIGH
**Impact:** Any malicious or simply unvetted layout JSON can execute arbitrary Python in the frame-compare process, giving full code execution (RCE). Attackers only need to control the layout file on disk (e.g., through a compromised distribution or shared workspace) to pivot into command execution under the user's account.
**Evidence:** `CliLayoutRenderer` pipes layout expressions directly into `eval(...)` with a namespace that still exposes the full object graph returned by `LayoutContext.resolve`, including magic attributes like `__class__` and sequence indexing. That allows payloads such as `{resolve('clips.0').__class__.__mro__[1].__subclasses__()[index](...)}` to break out of the intended DSL. 【F:src/cli_layout.py†L323-L358】【F:src/cli_layout.py†L587-L606】【F:src/cli_layout.py†L918-L969】
**Fix Required:** Replace `eval` with a hardened expression interpreter. Parse layout expressions with `ast.parse`, reject any node outside a small whitelist (comparisons, boolean ops, literals, attribute/name access that never traverses `__` attributes), and resolve values without exposing raw objects (e.g., resolve to primitive copies). Alternatively, replace the ad-hoc DSL with a declarative rules engine that never executes user text. Document the security expectations for layout files and add regression tests with malicious payload fixtures.
**Timeline:** Immediate

## PERFORMANCE: TMDB cache is unbounded and leaks memory across runs
**File:** src/tmdb.py:113-131
**Current:** `_TTLCache` keeps every `(path, params)` combination forever until the TTL expires, but there is no eviction or cap, so a CLI that handles many distinct titles will grow without bound, retaining every JSON payload in memory.
**Target:** Ensure the cache stays bounded (e.g., max 128-256 entries) and evicts the oldest or least-recently-used entries automatically.
**Bottleneck:** The cache dictionary never trims entries; unique search terms accumulate indefinitely, especially when `cache_ttl_seconds` is large (default 86,400 seconds).
**Optimization:** Replace `_TTLCache` with `collections.OrderedDict` or `functools.lru_cache`+TTL wrapper so old entries are evicted as new ones arrive; expose configuration knobs for size and TTL. Clear cache entries explicitly when the client is closed.
**Expected Gain:** Prevents multi-megabyte steady memory growth during long comparison sessions and keeps repeated CLI runs from retaining stale process-wide state.

## ARCHITECTURE: Audio alignment silences global NumPy warnings for the entire process
**File:** src/audio_alignment.py:21-27
**Pattern Broken:** Principle of least astonishment / cross-cutting concerns containment.
**Current Implementation:** At import time, `audio_alignment` installs a global `warnings.filterwarnings` that ignores an entire class of NumPy warnings for every module in the interpreter, not just audio alignment. Any consumer that relies on those warnings elsewhere will silently lose diagnostic coverage.
**Correct Pattern:** Scope warning suppression to the specific operations that trigger noisy alerts (e.g., use `warnings.catch_warnings()` around the relevant NumPy calls) instead of globally muting them at import time.
**Refactor Steps:** Remove the module-level `filterwarnings` call, wrap the librosa/Numpy operations inside `_load_optional_modules` or `_onset_envelope` with a local `catch_warnings`, and add regression tests to ensure other parts of the app still receive NumPy warnings.
**Risk of Not Fixing:** Debugging unrelated numerical issues becomes harder, and future contributors may miss real data-quality problems because the global warning channel is muted.

## Additional Observations
- The CLI layout DSL is powerful but currently undocumented about its trust boundaries; once the expression evaluator is hardened, add guidance for users about sourcing layout files securely.
- Consider explicitly closing the `requests.Session` created in `slowpics.upload_comparison` to avoid leaking sockets in long-lived integrations.

## Review 2025-10-10 – CLI progress style validation hardening
- **Scope:** Commit `55e156608b18cf2e1236b29298c0b348eec7e58f` (`frame_compare.py`, `src/config_loader.py`).
- **Summary:** The loader now normalizes and validates `cli.progress.style`, rejecting values outside `{fill, dot}`, and the runtime gracefully degrades invalid styles to `fill` with a warning when operating on pre-loaded configs. 【F:src/config_loader.py†L170-L212】【F:frame_compare.py†L2164-L2177】
- **Security:** No new injection surfaces or privilege boundary regressions detected. Validation occurs before any downstream usage.
- **Performance:** No measurable hot-path impact; the new checks are constant-time string operations executed once per run.
- **Reliability:** Runtime fallback preserves compatibility for tests or integrations that bypass `load_config`.
- **Action:** No changes required; monitor future layout/CLI adjustments against these guarantees.
