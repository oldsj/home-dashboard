# Home Dashboard

A lightweight dashboard for Raspberry Pi. Built to be managed by Claude Code.

## Setup

**Prerequisites:**

- [Claude Code](https://claude.ai/code) installed
- Raspberry Pi accessible via SSH with pubkey auth

**Deploy:**

```
> "Set up the dashboard on my Pi at office-dashboard"
```

Claude will install Docker, clone the repo, configure systemd services, and set up auto-updates.

## How It Works

Push to `main` → Pi pulls within 60s → Dashboard restarts → Browsers refresh automatically.

If a deploy fails health checks, it rolls back to the last working commit.

## Development

```bash
./run                    # Start locally at http://localhost:9753
pytest tests/            # Run tests
```

## Adding Integrations

Ask Claude to add integrations:

```
> "Add a weather integration for San Francisco"
> "Add a Todoist widget showing today's tasks"
```

Or see `integrations/` for examples.

## Configuration

- `config/config.yaml` - Layout and widget positions
- `config/credentials.yaml` - API keys (gitignored)
