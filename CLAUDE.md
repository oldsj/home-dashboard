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
```

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
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Render dashboard with pre-rendered widgets |
| `/ws` | WebSocket | Real-time widget updates |
| `/api/widgets/{name}` | GET | Get widget HTML by integration name |
| `/api/integrations` | GET | List available integrations |

## Creating New Integrations

1. Create `integrations/{name}/` directory
2. Add `integration.py`:
```python
from integrations.base import BaseIntegration

class MyIntegration(BaseIntegration):
    name = "my_integration"
    display_name = "My Service"
    refresh_interval = 60

    config_schema = {
        "api_key": {"type": "str", "required": True, "secret": True},
    }

    async def fetch_data(self) -> dict:
        # Use self.config or self.get_config_value()
        return {"data": "..."}
```
3. Add `widget.html` (Jinja2 template)
4. Add credentials to `config/credentials.yaml`
5. Add widget to `config/config.yaml` under `layout.widgets`

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
- **Validate at boundaries** - Config schemas, API inputs
- Future: Add mypy strict mode, consider Pydantic models for config
