"""
Main FastAPI application for the dashboard.

Provides HTTP routes for the dashboard UI and WebSocket endpoint
for real-time widget updates.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from integrations import discover_integrations, load_integration
from integrations.base import BaseIntegration
from server.config import config_loader

logger = logging.getLogger(__name__)


# Store active WebSocket connections
active_connections: set[WebSocket] = set()

# Store loaded integration instances
loaded_integrations: dict[str, BaseIntegration] = {}

# Background tasks
background_tasks: set[asyncio.Task[None]] = set()


def setup_templates() -> Environment:
    """Set up Jinja2 template environment."""
    templates_dir = Path(__file__).parent.parent / "templates"
    return Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)


template_env = setup_templates()


async def refresh_widget(integration: BaseIntegration) -> None:
    """
    Periodically refresh a widget and broadcast updates.

    Args:
        integration: The integration to refresh
    """
    while True:
        try:
            # Fetch fresh data
            data = await integration.fetch_data()
            html = integration.render_widget(data)

            # Broadcast to all connected clients
            message = json.dumps(
                {"type": "widget_update", "integration": integration.name, "html": html}
            )

            disconnected = set()
            for ws in active_connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.add(ws)

            # Clean up disconnected clients
            active_connections.difference_update(disconnected)

        except Exception:
            logger.exception("Error refreshing %s", integration.name)

        # Wait for next refresh
        await asyncio.sleep(integration.refresh_interval)


def load_all_integrations() -> dict[str, BaseIntegration]:
    """Load all configured integrations."""
    integrations = {}
    discovered = discover_integrations()
    widget_configs = config_loader.get_widget_configs()

    for widget_config in widget_configs:
        integration_name = widget_config.get("integration")
        if not integration_name:
            continue

        if integration_name not in discovered:
            logger.warning("Unknown integration '%s'", integration_name)
            continue

        if integration_name in integrations:
            continue  # Already loaded

        try:
            credentials = config_loader.get_integration_credentials(integration_name)
            integration = load_integration(integration_name, credentials, discovered)
            integrations[integration_name] = integration
        except Exception:
            logger.exception("Failed to load integration '%s'", integration_name)

    return integrations


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler - start/stop background tasks."""
    global loaded_integrations

    # Load integrations on startup
    loaded_integrations = load_all_integrations()
    logger.info("Loaded %d integration(s)", len(loaded_integrations))

    # Start background refresh tasks
    for integration in loaded_integrations.values():
        task = asyncio.create_task(refresh_widget(integration))
        background_tasks.add(task)

    yield

    # Cancel all background tasks on shutdown
    for task in background_tasks:
        task.cancel()
    background_tasks.clear()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Home Dashboard",
        description="Lightweight, AI-agent-friendly dashboard",
        lifespan=lifespan,
    )

    # Mount static files
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


app = create_app()


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Render the main dashboard page."""
    dashboard_config = config_loader.get_dashboard_config()
    layout_config = config_loader.get_layout_config()
    widget_configs = config_loader.get_widget_configs()

    # Pre-render all widgets with initial data
    widgets = []
    for widget_config in widget_configs:
        integration_name = widget_config.get("integration")
        if integration_name not in loaded_integrations:
            continue

        integration = loaded_integrations[integration_name]
        try:
            data = await integration.fetch_data()
            html = integration.render_widget(data)
        except Exception:
            logger.exception("Error loading widget %s", integration_name)
            html = f'<div class="text-red-500">Error loading {integration_name}</div>'

        widgets.append(
            {
                "name": integration_name,
                "display_name": integration.display_name,
                "html": html,
                "position": widget_config.get("position", {}),
                "refresh_interval": integration.refresh_interval,
            }
        )

    template = template_env.get_template("dashboard.html")
    return template.render(
        title=dashboard_config.get("title", "Dashboard"),
        layout=layout_config,
        widgets=widgets,
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time widget updates."""
    await websocket.accept()
    active_connections.add(websocket)

    try:
        while True:
            # Keep connection alive, handle any client messages
            data = await websocket.receive_text()
            # Could handle client requests here (e.g., force refresh)
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        active_connections.discard(websocket)


@app.get("/api/widgets/{integration_name}", response_class=HTMLResponse)
async def get_widget(integration_name: str) -> HTMLResponse:
    """Get the current HTML for a specific widget."""
    if integration_name not in loaded_integrations:
        return HTMLResponse(
            content=f'<div class="text-red-500">Unknown integration: {integration_name}</div>',
            status_code=404,
        )

    integration = loaded_integrations[integration_name]
    try:
        data = await integration.fetch_data()
        html = integration.render_widget(data)
        return HTMLResponse(content=html)
    except Exception:
        logger.exception("Error fetching widget %s", integration_name)
        return HTMLResponse(
            content='<div class="text-red-500">Error loading widget</div>',
            status_code=500,
        )


@app.get("/api/integrations")
async def list_integrations() -> dict[str, dict[str, Any]]:
    """List all available integrations."""
    discovered = discover_integrations()
    return {
        name: {
            "display_name": cls.display_name,
            "refresh_interval": cls.refresh_interval,
            "loaded": name in loaded_integrations,
        }
        for name, cls in discovered.items()
    }
