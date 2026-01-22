# Home Dashboard

A lightweight, AI-agent-friendly dashboard designed for Raspberry Pi. Makes it trivially easy for Claude/Codex/Gemini to add new integrations.

## Quick Start

```bash
./run
```

Opens at http://localhost:9753. Edit any code and it auto-reloads.

## Project Structure

```
dashboard/
├── config/
│   ├── config.yaml           # Dashboard layout, enabled integrations
│   └── credentials.yaml      # API keys, tokens (gitignored)
├── integrations/
│   ├── __init__.py           # Auto-discovers integrations
│   ├── base.py               # BaseIntegration class
│   └── example/              # Reference integration
├── server/
│   ├── main.py               # FastAPI app + WebSocket
│   └── config.py             # Config loader
├── templates/
│   ├── base.html             # HTMX + Tailwind base
│   └── dashboard.html        # Main grid layout
├── requirements.txt
└── run.py                    # Entry point
```

## Adding a New Integration

### Step 1: Create Integration Directory

```bash
mkdir integrations/todoist
touch integrations/todoist/__init__.py
touch integrations/todoist/integration.py
touch integrations/todoist/widget.html
```

### Step 2: Implement Integration Class

```python
# integrations/todoist/integration.py
from integrations.base import BaseIntegration
import httpx


class TodoistIntegration(BaseIntegration):
    """Todoist tasks widget showing today's tasks."""

    name = "todoist"
    display_name = "Todoist"
    refresh_interval = 60  # seconds

    config_schema = {
        "api_token": {"type": "str", "required": True, "secret": True},
        "show_completed": {"type": "bool", "default": False}
    }

    async def fetch_data(self) -> dict:
        """Fetch data from Todoist API."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.todoist.com/rest/v2/tasks",
                headers={"Authorization": f"Bearer {self.config['api_token']}"},
                params={"filter": "today"}
            )
            resp.raise_for_status()
            return {"tasks": resp.json()}
```

### Step 3: Create Widget Template

```html
<!-- integrations/todoist/widget.html -->
<div class="h-full flex flex-col">
  <h2 class="text-lg font-semibold text-white mb-3">Today's Tasks</h2>

  <div class="flex-1 overflow-y-auto space-y-2">
    {% for task in data.tasks %}
    <div class="flex items-center gap-2 py-1">
      <span class="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0"></span>
      <span class="text-gray-200">{{ task.content }}</span>
    </div>
    {% empty %}
    <p class="text-gray-500">No tasks for today</p>
    {% endfor %}
  </div>
</div>
```

### Step 4: Add Credentials

```yaml
# config/credentials.yaml
todoist:
  api_token: "your-todoist-api-token"
```

### Step 5: Enable in Dashboard

```yaml
# config/config.yaml
layout:
  widgets:
    - integration: todoist
      position:
        row: 1
        col: 1
        width: 1
        height: 1
```

### Step 6: Restart Server

The integration will be auto-discovered on startup.

## Integration Pattern Reference

### Required Class Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | str | Unique identifier (lowercase, no spaces) |
| `display_name` | str | Human-readable name |

### Optional Class Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `refresh_interval` | int | 30 | Seconds between data fetches |
| `config_schema` | dict | {} | Schema for required/optional config |

### Required Methods

```python
async def fetch_data(self) -> dict:
    """
    Fetch data from external API or source.
    Called periodically based on refresh_interval.
    Return dict to pass to widget template.
    """
```

### Optional Methods

```python
def render_widget(self, data: dict) -> str:
    """
    Override for custom rendering logic.
    By default, loads widget.html and renders with data.
    """
```

### Config Schema Format

```python
config_schema = {
    "field_name": {
        "type": "str",      # str, int, bool, list, dict
        "required": True,   # Is this field required?
        "default": None,    # Default value if not provided
        "secret": True      # Mark as sensitive (for docs)
    }
}
```

## Configuration

### Dashboard Settings (`config/config.yaml`)

```yaml
dashboard:
  title: "Home Dashboard"
  refresh_interval: 30    # Global default (can be overridden per-integration)
  resolution: "1920x1080"

layout:
  columns: 3              # Number of grid columns
  rows: 2                 # Number of grid rows
  gap: 16                 # Pixels between widgets
  padding: 16             # Pixels around edge
  widgets:
    - integration: example
      position:
        row: 1            # Grid row (1-indexed)
        col: 1            # Grid column (1-indexed)
        width: 1          # Number of columns to span
        height: 1         # Number of rows to span
```

### Widget Positioning

Widgets are positioned using CSS Grid. The `position` object controls placement:

- `row`: Starting row (1-indexed)
- `col`: Starting column (1-indexed)
- `width`: Number of columns to span
- `height`: Number of rows to span

Example for a 3x2 grid:
```
┌─────────┬─────────┬─────────┐
│  (1,1)  │  (1,2)  │  (1,3)  │
├─────────┼─────────┼─────────┤
│  (2,1)  │  (2,2)  │  (2,3)  │
└─────────┴─────────┴─────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard HTML |
| `/ws` | WebSocket | Real-time widget updates |
| `/api/widgets/{name}` | GET | Get widget HTML by integration name |
| `/api/integrations` | GET | List all available integrations |

## Running on Raspberry Pi

```bash
# Clone to your Pi
git clone <your-repo> dashboard
cd dashboard

# Run it
./run
```

Code changes auto-reload. Hack away.
