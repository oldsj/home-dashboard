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
from server.config import get_credentials, get_settings
from server.themes import get_theme

logger = logging.getLogger(__name__)


# Store active WebSocket connections
active_connections: set[WebSocket] = set()

# Store loaded integration instances
loaded_integrations: dict[str, BaseIntegration] = {}

# Background tasks
background_tasks: set[asyncio.Task[None]] = set()


def hex_to_rgb(hex_color: str) -> str:
    """
    Convert hex color to RGB values for CSS variables.

    Args:
        hex_color: Hex color string (e.g., "#ff1b8d")

    Returns:
        RGB values as comma-separated string (e.g., "255, 27, 141")
    """
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"{r}, {g}, {b}"


def setup_templates() -> Environment:
    """Set up Jinja2 template environment."""
    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)

    # Add custom filters
    env.filters["rgb_values"] = hex_to_rgb

    return env


template_env = setup_templates()


async def broadcast_widget_update(integration_name: str, html: str) -> None:
    """
    Broadcast a widget update to all connected WebSocket clients.

    Args:
        integration_name: Name of the integration
        html: Rendered HTML to broadcast
    """
    message = json.dumps(
        {"type": "widget_update", "integration": integration_name, "html": html}
    )

    disconnected = set()
    for (
        ws
    ) in active_connections:  # pragma: no cover - background task with live connections
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)

    # Clean up disconnected clients
    active_connections.difference_update(disconnected)


async def refresh_widget(integration: BaseIntegration) -> None:
    """
    Handle widget updates via event stream OR polling.

    Tries event stream first (start_event_stream). If not implemented,
    falls back to polling mode (fetch_data + refresh_interval).

    Args:
        integration: The integration to refresh
    """
    # Try event stream first
    try:
        event_stream = integration.start_event_stream()

        # Check if it's actually implemented (yields at least once)
        try:
            data = await anext(event_stream)
            logger.info(f"{integration.name} using event stream mode")

            # Process initial data
            html = integration.render_widget(data)
            await broadcast_widget_update(integration.name, html)

            # Continue streaming events
            async for data in event_stream:
                html = integration.render_widget(data)
                await broadcast_widget_update(integration.name, html)

        except StopAsyncIteration:
            # Event stream ended, shouldn't happen for infinite streams
            logger.warning(f"{integration.name} event stream ended unexpectedly")

    except (TypeError, StopAsyncIteration):
        # No event stream - fall back to polling
        logger.info(
            f"{integration.name} using polling mode ({integration.refresh_interval}s)"
        )

        while True:
            try:
                # Fetch fresh data
                data = await integration.fetch_data()
                html = integration.render_widget(data)
                await broadcast_widget_update(integration.name, html)

            except Exception:  # pragma: no cover - defensive error handling
                logger.exception("Error refreshing %s", integration.name)

            # Wait for next refresh
            await asyncio.sleep(integration.refresh_interval)


def load_all_integrations() -> dict[str, BaseIntegration]:
    """Load all configured integrations."""
    integrations = {}
    discovered = discover_integrations()
    settings = get_settings()

    for widget_config in settings.layout.widgets:
        integration_name = widget_config.integration
        if not integration_name:
            continue

        if integration_name not in discovered:
            logger.warning("Unknown integration '%s'", integration_name)
            continue

        if integration_name in integrations:
            continue  # Already loaded

        try:
            credentials = get_credentials(integration_name)
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
    settings = get_settings()

    # Get theme
    try:
        theme = get_theme(settings.dashboard.theme)
    except ValueError:
        logger.warning(
            "Unknown theme '%s', using 'industrial'", settings.dashboard.theme
        )
        theme = get_theme("industrial")

    # Pre-render all widgets with initial data
    widgets = []
    for widget_config in settings.layout.widgets:
        integration_name = widget_config.integration

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
                "position": widget_config.position,
                "refresh_interval": integration.refresh_interval,
            }
        )

    template = template_env.get_template("dashboard.html")
    return template.render(
        title=settings.dashboard.title,
        theme=theme,
        layout=settings.layout.model_dump(),
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


@app.post("/api/trigger-refresh")
async def trigger_refresh() -> dict[str, str]:
    """Trigger all connected browsers to refresh."""
    message = json.dumps({"type": "refresh"})
    disconnected = set()
    count = 0

    for ws in active_connections:
        try:
            await ws.send_text(message)
            count += 1
        except Exception:
            disconnected.add(ws)

    active_connections.difference_update(disconnected)
    return {"status": "ok", "clients_notified": str(count)}


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint for deploy validation."""
    errors = []

    # Check background tasks are running
    dead_tasks = [t for t in background_tasks if t.done()]
    if dead_tasks:
        for task in dead_tasks:
            if task.exception():
                errors.append(f"Background task crashed: {task.exception()}")

    # Check template renders
    try:
        template_env.get_template("dashboard.html")
    except Exception as e:
        errors.append(f"Template error: {e}")

    # Check each integration can fetch data
    for name, integration in loaded_integrations.items():
        try:
            await asyncio.wait_for(integration.fetch_data(), timeout=5.0)
        except asyncio.TimeoutError:
            errors.append(f"Integration '{name}' timed out")
        except Exception as e:
            errors.append(f"Integration '{name}' failed: {e}")

    if errors:
        return {"status": "unhealthy", "errors": errors}

    return {
        "status": "healthy",
        "integrations": len(loaded_integrations),
        "websocket_clients": len(active_connections),
    }


@app.get("/api/debug/config")
async def debug_config() -> dict[str, Any]:
    """Debug endpoint to view current configuration and theme."""
    settings = get_settings()
    try:
        theme = get_theme(settings.dashboard.theme)
        theme_status = {
            "name": theme["name"],
            "display_name": theme["display_name"],
            "loaded_successfully": True,
        }
    except ValueError as e:
        theme_status = {"error": str(e), "loaded_successfully": False}

    return {
        "dashboard": {
            "title": settings.dashboard.title,
            "theme": settings.dashboard.theme,
            "theme_status": theme_status,
            "refresh_interval": settings.dashboard.refresh_interval,
            "resolution": settings.dashboard.resolution,
        },
        "layout": settings.layout.model_dump(),
    }
