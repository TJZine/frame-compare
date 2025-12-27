# ADR-005: Modernized CLI & Configuration Stack

## Status

Accepted

## Date

2025-12-16

## Context

For a ground-up rebuild with no version constraints, we should select the best modern tooling for CLI interface and configuration management. The original v0.0.14 used Click and basic TOML loading.

## Decision

### CLI Framework: Typer (instead of Click)

**Use Typer** as the CLI framework.

**Rationale:**

- Built on Click, so same reliability and ecosystem
- Native type hints for arguments and options
- Automatic generation of beautiful help text
- Shell completion out of the box
- Cleaner, more Pythonic syntax
- Better IDE support

**Example:**

```python
import typer
from pathlib import Path

app = typer.Typer(help="Frame Compare - Video comparison tool")

@app.command()
def run(
    root: Path | None = typer.Option(None, help="Workspace root directory"),
    config: Path | None = typer.Option(None, help="Path to config file"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Force recomputation"),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Minimal output"),
):
    """Execute the full comparison pipeline."""
    ...
```

### Configuration: Pydantic v2 Settings

**Use Pydantic v2** for configuration management.

**Rationale:**

- Type-validated configuration with zero boilerplate
- Automatic environment variable support
- Nested model support for complex config
- Schema generation for documentation
- Excellent IDE completion
- Fast (Rust-based validation in v2)

**Example:**

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class AnalysisConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FRAME_COMPARE_ANALYSIS_",
        toml_file="config.toml",
    )
    
    frame_count: int = Field(default=10, ge=3, le=100)
    random_seed: int = Field(default=42)
    mode: SelectionMode = Field(default=SelectionMode.MIXED)
```

### Serialization: msgspec or Pydantic

**Use msgspec** for performance-critical JSON/cache serialization, **Pydantic models** for validated data.

**Rationale:**

- msgspec is 10-50x faster than json stdlib
- Pydantic provides validation + serialization
- Both support type hints natively

### Error Handling: Result Types

**Use explicit Result types** for operations that can fail.

**Rationale:**

- Makes error paths explicit in type signatures
- No hidden exceptions to catch
- Easier to test error paths
- Common pattern in Rust, gaining Python adoption

**Implementation:**

```python
from dataclasses import dataclass
from typing import TypeVar, Generic

T = TypeVar("T")
E = TypeVar("E")

@dataclass
class Ok(Generic[T]):
    value: T

@dataclass  
class Err(Generic[E]):
    error: E

Result = Ok[T] | Err[E]

# Usage
def load_cache(path: Path) -> Result[FrameMetrics, CacheError]:
    if not path.exists():
        return Err(CacheError.NOT_FOUND)
    try:
        data = msgspec.json.decode(path.read_bytes(), type=FrameMetrics)
        return Ok(data)
    except msgspec.DecodeError as e:
        return Err(CacheError.CORRUPT)
```

## Consequences

### Positive

- Cleaner CLI code with better UX
- Type-safe configuration with validation
- Faster serialization
- Explicit error handling
- Better IDE experience throughout

### Negative

- Typer adds dependency (small, based on Click)
- Pydantic v2 is a heavier dependency
- Result types require pattern matching discipline
- Team needs to learn new patterns

### Migration Notes

- Click commands port directly to Typer with minimal changes
- Existing dataclasses can inherit from Pydantic BaseModel
- Gradual adoption of Result types possible

## References

- Typer documentation: <https://typer.tiangolo.com/>
- Pydantic v2: <https://docs.pydantic.dev/>
- msgspec: <https://jcristharif.com/msgspec/>
