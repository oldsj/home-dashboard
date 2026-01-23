# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Dashboard - A lightweight dashboard for Raspberry Pi with a plugin architecture for integrations. Built with FastAPI + Jinja2 (server-side rendering), HTMX for dynamic updates, and Tailwind CSS.

## Development

**Server**: Run `./run` in a separate terminal. Expect the user to already have it running. Do not attempt to start the server manually—if it's not running, notify the user to start it with `./run`.

```bash
# Testing
pytest tests/                       # All tests
pytest tests/test_api.py            # Single test file
pytest tests/test_api.py -v         # Verbose

# Dependency management (always use uv, never edit pyproject.toml directly)
uv add <package>                    # Add a dependency
uv add --dev <package>              # Add a dev dependency
uv remove <package>                 # Remove a dependency
uv sync                             # Sync dependencies from lockfile

# Linting (ALWAYS run before committing)
trunk check                         # Check all files for issues
trunk check --fix                   # Auto-fix issues where possible
trunk fmt                           # Format all files
```

**Pre-commit requirement**: Always run `trunk check` before committing. Fix any errors before proceeding with the commit.

## Architecture

### Tech Stack

- **Backend**: FastAPI, Jinja2 templates, WebSockets
- **Frontend**: HTMX + Tailwind CSS (CDN)
- **Package Manager**: uv (pyproject.toml + uv.lock)
- **Runtime**: Python 3.13+

### Key Patterns

**Plugin-based integrations**: Each integration lives in `integrations/{name}/` with:

- `integration.py` - Class inheriting from `BaseIntegration`, implements `async fetch_data() -> dict`
- `widget.html` - Jinja2 template receiving data from `fetch_data()`

Integrations are auto-discovered on startup from subdirectories.

**Server-side rendering**: All HTML rendered on server. WebSocket broadcasts updates; HTMX polling as fallback.

**Configuration**: YAML files in `config/`:

- `config.yaml` - Dashboard layout, widget positioning
- `credentials.yaml` - API keys/tokens (gitignored)

### Core Files

- `server/main.py` - FastAPI app, routes, WebSocket handling, background refresh tasks
- `server/config.py` - ConfigLoader for YAML files with caching
- `integrations/base.py` - BaseIntegration abstract class
- `integrations/__init__.py` - `discover_integrations()`, `load_integration()`
- `run.py` - CLI entry point (argparse -> uvicorn)

### API Endpoints

| Endpoint              | Method    | Purpose                                    |
| --------------------- | --------- | ------------------------------------------ |
| `/`                   | GET       | Render dashboard with pre-rendered widgets |
| `/ws`                 | WebSocket | Real-time widget updates                   |
| `/api/widgets/{name}` | GET       | Get widget HTML by integration name        |
| `/api/integrations`   | GET       | List available integrations                |

## Creating New Integrations

1. Create `integrations/{name}/` directory
2. Add `integration.py`:

```python
from pydantic import Field
from dashboard_integration_base import BaseIntegration, IntegrationConfig

class MyIntegrationConfig(IntegrationConfig):
    """Configuration model for MyIntegration."""

    api_key: str = Field(..., description="API key", json_schema_extra={"secret": True})
    refresh_rate: int = Field(default=60, description="Refresh rate in seconds")

class MyIntegration(BaseIntegration):
    name = "my_integration"
    display_name = "My Service"
    refresh_interval = 60

    ConfigModel = MyIntegrationConfig

    async def fetch_data(self) -> dict:
        # Use self.config or self.get_config_value()
        api_key = self.get_config_value("api_key")
        return {"data": "..."}
```

3. Add `widget.html` (Jinja2 template)
4. Add credentials to `config/credentials.yaml`
5. Add widget to `config/config.yaml` under `layout.widgets`

### Optional: Event-Driven Updates

To support real-time updates instead of polling, override `start_event_stream()`:

```python
async def start_event_stream(self) -> AsyncIterator[dict[str, Any]]:
    """Stream events as they happen."""
    # Yield initial state
    yield await self.fetch_data()

    # Subscribe to event source
    async for event in self._client.subscribe_events():
        if event.type in ['motion', 'alert']:
            yield await self.fetch_data()
```

If not implemented, the integration will use polling mode (fetch_data + refresh_interval).

## Security Notes

- Sensitive config keys (containing api_key, token, secret, password, credentials, key) are filtered by `BaseIntegration._get_safe_config()`
- Jinja2 autoescape is enabled
- Credentials stored in gitignored YAML, never in code

## AI-Friendly Code Guidelines

This project follows practices that make the codebase AI-agent friendly. Maintain these standards:

### 1. Test Coverage

- **Target 100% coverage** - Every line should have executable examples
- Run with coverage: `pytest --cov=server --cov=integrations --cov-report=term-missing`
- Write tests for all new code before or alongside implementation
- Use `tests/conftest.py` fixtures for isolation

### 2. Intentional File Organization

- **Small, focused files** - Keep files under 200 lines when possible
- **Semantic paths** - File location should indicate purpose
- **One concern per file** - Don't mix unrelated functionality
- Current structure: `server/` (backend), `integrations/` (plugins), `templates/` (views), `config/` (settings)

### 3. Fast, Ephemeral, Concurrent Environments

- **Docker + uv** for reproducible builds
- **Isolated test fixtures** - Use `TemporaryDirectory` and pytest fixtures
- **No shared state** between tests
- Tests must run independently and in any order

### 4. End-to-End Type Systems

- **Type all function signatures** - Parameters and return types
- **Use type hints consistently** - `Dict`, `List`, `Optional`, `Type`, etc.
- **Validate at boundaries** - Use Pydantic models for config validation
- **All integrations must use ConfigModel** - No dict-based config schemas
- Future: Add mypy strict mode

### 5. No Backward Compatibility Code

**IMPORTANT**: This codebase does not maintain backward compatibility for deprecated patterns. When we adopt a better approach, we fully migrate and remove the old code.

- ✅ **Correct**: Use Pydantic `ConfigModel` for all integrations
- ❌ **Incorrect**: Dict-based `config_schema` (removed)
- ✅ **Correct**: Event-driven updates via `start_event_stream()`
- ❌ **Incorrect**: Polling-only implementations when events are available

**Why**: Backward compatibility adds complexity that makes the codebase harder for AI agents to understand and modify. Clean, single-path implementations are easier to reason about and maintain.
