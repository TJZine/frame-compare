# Security Invariants

> **Module:** Reference  
> **Purpose:** Define security constraints for AI agent implementation

---

## 1. Path Containment Rules

### 1.1 Workspace Root Boundary

All file operations MUST be contained within the workspace root:

```python
def validate_path_containment(candidate: Path, root: Path) -> Path:
    """
    Ensure path does not escape workspace root.
    
    Raises:
        PathEscapesRootError(FC-3009): If path escapes root
    """
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise PathEscapesRootError(root=root, candidate=candidate)
    return resolved
```

### 1.2 Blocked Patterns

Reject paths containing:

- `..` sequences that escape root
- Absolute paths outside workspace
- Symlinks pointing outside workspace
- Null bytes (`\x00`)
- Device files (`/dev/*`, `CON`, `NUL`)

### 1.3 Path Validation Points

| Operation | Validate At |
|:----------|:------------|
| Config loading | `load_config()` |
| Input directory | `preflight()` |
| Output directory | `preflight()` |
| Screenshot writes | `render_frames()` |
| Cache reads/writes | `cache_get/put()` |

---

## 2. Subprocess Argument Sanitization

### 2.1 Shell Injection Prevention

**NEVER** use `shell=True`:

```python
# ❌ FORBIDDEN
subprocess.run(f"ffmpeg -i {path}", shell=True)

# ✅ REQUIRED
subprocess.run(["ffmpeg", "-i", str(path)], shell=False)
```

### 2.2 Argument Validation

Before passing to subprocess:

```python
def sanitize_subprocess_arg(arg: str | Path) -> str:
    """Validate argument is safe for subprocess."""
    from frame_compare.errors import InputError, ErrorContext
    
    s = str(arg)
    
    # Reject shell metacharacters
    if any(c in s for c in [';', '|', '&', '$', '`', '\n', '\r']):
        raise InputError(ErrorContext(
            code="FC-3010",
            name="INVALID_SUBPROCESS_ARG",
            message=f"Invalid character in argument: {s!r}",
            hint="Remove shell metacharacters from the argument",
        ))
    
    # Reject control characters
    if any(ord(c) < 32 for c in s):
        raise InputError(ErrorContext(
            code="FC-3011",
            name="CONTROL_CHAR_IN_ARG",
            message=f"Control character in argument: {s!r}",
            hint="Remove control characters from the argument",
        ))
    
    return s
```

### 2.3 External Commands

| Command | Allowed Arguments |
|:--------|:------------------|
| ffmpeg | File paths, numeric options only |
| dovi_tool | RPU extraction with validated paths |
| VapourSynth | Plugin calls via vs.core only |

---

## 3. External URL Policy (SSRF Prevention)

### 3.1 Allowed Domains

Only these external URLs are permitted:

| Domain | Purpose | Protocol |
|:-------|:--------|:---------|
| `slow.pics` | Screenshot upload | HTTPS only |
| `api.themoviedb.org` | Metadata lookup | HTTPS only |

### 3.2 URL Validation

```python
from frame_compare.errors import HttpsRequiredError, HostNotAllowedError

ALLOWED_HOSTS = frozenset({"slow.pics", "api.themoviedb.org"})

def validate_external_url(url: str) -> None:
    """Ensure URL is to an allowed host.
    
    Raises:
        HttpsRequiredError (FC-5010): If URL is not HTTPS
        HostNotAllowedError (FC-5011): If host not in allowlist
    """
    parsed = urlparse(url)
    
    if parsed.scheme != "https":
        raise HttpsRequiredError(url)  # FC-5010
    
    if parsed.hostname not in ALLOWED_HOSTS:
        raise HostNotAllowedError(parsed.hostname or "unknown")  # FC-5011
```

### 3.3 User-Provided URLs

**NEVER** fetch arbitrary URLs. All external requests go only to:

- slow.pics publish endpoint
- TMDB API endpoint (with API key)

### 3.4 Response Handling

- Validate Content-Type before parsing
- Limit response body size (10MB max)
- Timeout all requests (30s default)

---

## 4. Input Validation

### 4.1 File Size Limits

| Operation | Max Size | Error |
|:----------|:---------|:------|
| Config file | 1MB | `FileTooLargeError(FC-3008)` |
| Video file | 100GB | Warning only |
| Cache file | 100MB | Regenerate |

### 4.2 Config Value Constraints

Validated by Pydantic, but additional runtime checks:

```python
# Frame count bounds (match config-reference.md)
assert 1 <= frame_count <= 100

# Nits range (match config-reference.md)
assert 100 <= target_nits <= 1000

# Seed range (match config-reference.md)
assert 0 <= seed <= 2**32 - 1
```

---

## 5. Secrets Handling

### 5.1 API Keys

| Secret | Storage | Access |
|:-------|:--------|:-------|
| TMDB API Key | Environment variable | `os.environ.get()` |

**NEVER**:

- Log API keys
- Include in error messages
- Store in config files
- Pass as command-line arguments (visible in `ps`)

### 5.2 Credential Redaction

```python
def redact_secrets(text: str) -> str:
    """Redact known secret patterns from logs."""
    # TMDB keys are 32 hex chars
    return re.sub(r'[a-f0-9]{32}', '[REDACTED]', text, flags=re.I)
```

---

## 6. Dependency Security

### 6.1 Subprocess Environment

Clear sensitive environment variables before spawning:

```python
safe_env = {k: v for k, v in os.environ.items() 
            if not k.startswith(("FRAME_COMPARE_", "TMDB_"))}
subprocess.run(cmd, env=safe_env)
```

### 6.2 VapourSynth Plugin Loading

Only load plugins from:

- System plugin directory
- Docker container paths
- Explicit `VS_PLUGINS_PATH`

---

## 7. Error Message Security

**Don't leak**:

- Full file paths (show relative from workspace)
- Stack traces to users (log internally)
- System information beyond necessary

```python
# ❌ Too much info
raise Error(f"Failed at {full_path}: {traceback}")

# ✅ Safe
raise Error(f"Failed to load video: {path.name}")
```
