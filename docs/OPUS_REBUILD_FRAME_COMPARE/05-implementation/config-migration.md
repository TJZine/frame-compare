# Config Migration (v0.0.14 → v2.0)

> **Module:** Reference  
> **Purpose:** Define migration behavior for configuration files

---

## 1. Migration Strategy

| Behavior | Description |
|:---------|:------------|
| **Auto-migrate** | Valid v1 configs converted silently |
| **Warn** | Deprecated options trigger warning but work |
| **Error** | Invalid combinations fail with FC-1003 |
| **Interactive** | Ambiguous cases prompt user (if TTY) |

---

## 2. Auto-Migrated Settings

These settings map directly with no user action:

| v0.0.14 Key | v2.0 Key | Transformation |
|:------------|:---------|:---------------|
| `input_dir` | `paths.input_dir` | Nest under `[paths]` |
| `screenshots_dir` | `paths.screenshots_dir` | Nest under `[paths]` |
| `frame_count` | `analysis.frame_count` | Nest under `[analysis]` |
| `random_seed` | `analysis.random_seed` | Nest under `[analysis]` |
| `preset` | `color.preset` | Nest under `[color]` |
| `target_nits` | `color.target_nits` | Nest under `[color]` |
| `auto_upload` | `slowpics.auto_upload` | Nest under `[slowpics]` |

---

## 3. Deprecated (Warn)

These work but trigger a warning:

| v0.0.14 | v2.0 Equivalent | Warning Message |
|:--------|:----------------|:----------------|
| `curve` | `color.tone_curve` | "Use 'color.tone_curve' instead" |
| `contrast` | `color.contrast_recovery` | "Use 'color.contrast_recovery' instead" |
| `log_level` (root) | `logging.level` | "Move to '[logging]' section" |

**Warning Format**:

```text
[WARN] Deprecated config key 'curve' at line 5. Use 'color.tone_curve' instead.
```

---

## 4. Error Cases

These combinations fail with `ConfigValidationError(FC-1003)` or `ConfigMigrationError(FC-1006)`:

| Condition | Error Code | Error Message |
|:----------|:-----------|:--------------|
| Both `preset` and `color.preset` | FC-1003 | "Conflicting keys: 'preset' and 'color.preset'" |
| Invalid preset name | FC-1003 | "Unknown preset: '{name}'. Run 'frame-compare preset list'" |
| Incompatible Python version | FC-2010 | "Python {version} not supported. Requires 3.13+" |
| Migration cannot resolve conflicts | FC-1006 | "Config migration failed: {details}" |
| V1 config has invalid values for v2 schema | FC-1006 | "Config migration failed: v1 value '{value}' invalid for v2 field '{field}'" |

> [!NOTE]
> Unknown top-level keys are ignored (logged at WARNING) rather than causing errors,
> per the `extra="ignore"` setting in the Pydantic schema.

---

## 5. Interactive Prompts

When running in a TTY with ambiguous input:

| Condition | Prompt |
|:----------|:-------|
| v1 config detected | "Migrate config to v2 format? [Y/n]" |
| Missing required field | "Enter value for 'paths.input_dir':" |

**Non-interactive mode** (CI/scripts):  
Set `FRAME_COMPARE_NONINTERACTIVE=1` to auto-accept defaults or fail.

> [!NOTE]
> `FRAME_COMPARE_NONINTERACTIVE` is a special environment variable that:
>
> - Disables all interactive prompts
> - Auto-accepts safe defaults where possible
> - Fails with exit code 2 when user input would be required
>
> This is separate from the config env vars documented in config-reference.md.

---

## 6. Migration Implementation

```python
# JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
def migrate_config(raw: dict[str, JSONValue]) -> tuple[dict[str, JSONValue], list[str]]:
    """
    Migrate v1 config to v2 format.
    
    Returns:
        (migrated_config, warnings_list)
        
    Raises:
        ConfigValidationError: On irreconcilable conflicts
    """
    warnings = []
    migrated = {}
    
    # 1. Detect version
    if not any(key in raw for key in ["paths", "analysis", "color"]):
        # Flat v1 format detected
        warnings.append("Auto-migrating v1 config format to v2")
        raw = _nest_v1_keys(raw)
    
    # 2. Apply deprecated key mappings
    # 3. Validate no conflicts
    # 4. Return migrated + warnings
```

---

## 7. Cache Compatibility

| Cache Version | Behavior |
|:--------------|:---------|
| v1.x (msgpack) | Delete, log "Regenerating cache (v1 format obsolete)" |
| v2.0 | Use directly |
| v2.x (future) | Use if minor version, regenerate if major |
