"""Tests for API endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.main import app, hex_to_rgb


@pytest.fixture
def client():
    """Create a test client."""
    with TestClient(app) as client:
        yield client


class TestDashboardEndpoint:
    """Tests for the main dashboard endpoint."""

    def test_dashboard_returns_html(self, client: TestClient):
        """Test that dashboard returns HTML response."""
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_dashboard_contains_title(self, client: TestClient):
        """Test that dashboard contains expected title."""
        response = client.get("/")

        assert response.status_code == 200
        # Should contain some HTML structure
        assert "<html" in response.text or "<!DOCTYPE" in response.text


class TestIntegrationsEndpoint:
    """Tests for the integrations API endpoint."""

    def test_list_integrations(self, client: TestClient):
        """Test listing available integrations."""
        response = client.get("/api/integrations")

        assert response.status_code == 200
        data = response.json()

        # Example integration should be discovered
        assert "example" in data
        assert data["example"]["display_name"] == "Example Widget"
        assert "refresh_interval" in data["example"]
        assert "loaded" in data["example"]


class TestWidgetEndpoint:
    """Tests for the widget API endpoint."""

    def test_get_widget_unknown_integration(self, client: TestClient):
        """Test getting widget for unknown integration returns 404."""
        response = client.get("/api/widgets/nonexistent")

        assert response.status_code == 404
        assert "text/html" in response.headers["content-type"]

    def test_error_messages_sanitized(self, client: TestClient):
        """Test that error messages don't leak sensitive information."""
        response = client.get("/api/widgets/nonexistent")

        # Should not contain stack traces or internal paths
        assert "Traceback" not in response.text
        assert "/Users/" not in response.text
        assert "Exception" not in response.text


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_status(self, client: TestClient):
        """Test health endpoint returns status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_health_response_structure(self, client: TestClient):
        """Test health endpoint has expected response structure."""
        response = client.get("/health")

        data = response.json()
        assert data["status"] in ("healthy", "unhealthy")
        # Healthy responses include integration count
        if data["status"] == "healthy":
            assert "integrations" in data
        # Unhealthy responses include errors
        else:
            assert "errors" in data


class TestWebSocket:
    """Tests for WebSocket endpoint."""

    def test_websocket_connect(self, client: TestClient):
        """Test WebSocket connection."""
        with client.websocket_connect("/ws") as websocket:
            # Send ping
            websocket.send_text("ping")
            data = websocket.receive_text()

            assert data == "pong"

    def test_websocket_multiple_pings(self, client: TestClient):
        """Test multiple WebSocket ping/pong."""
        with client.websocket_connect("/ws") as websocket:
            for _ in range(3):
                websocket.send_text("ping")
                data = websocket.receive_text()
                assert data == "pong"

    def test_websocket_disconnect(self, client: TestClient):
        """Test WebSocket disconnect is handled gracefully."""
        with client.websocket_connect("/ws"):
            pass
        # Connection should be cleanly closed without errors


class TestDashboardEdgeCases:
    """Tests for edge cases in dashboard endpoints."""

    def test_get_widget_existing_integration(self, client: TestClient):
        """Test getting widget for existing integration."""
        response = client.get("/api/widgets/example")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_error_handling_in_widget_rendering(self, client: TestClient, monkeypatch):
        """Test error handling when widget rendering fails."""
        from server.main import loaded_integrations

        # Temporarily break the example integration
        if "example" in loaded_integrations:
            original_fetch = loaded_integrations["example"].fetch_data

            async def broken_fetch():
                raise RuntimeError("Simulated fetch error")

            monkeypatch.setattr(
                loaded_integrations["example"], "fetch_data", broken_fetch
            )

            try:
                response = client.get("/api/widgets/example")
                # Should return 500 with error message
                assert response.status_code == 500
                assert "Error loading widget" in response.text
            finally:
                # Restore
                monkeypatch.setattr(
                    loaded_integrations["example"], "fetch_data", original_fetch
                )

    def test_error_handling_in_dashboard_widget(self, client: TestClient, monkeypatch):
        """Test error handling when dashboard widget fails."""
        from server.main import loaded_integrations

        # Temporarily break the example integration
        if "example" in loaded_integrations:
            original_fetch = loaded_integrations["example"].fetch_data

            async def broken_fetch():
                raise RuntimeError("Simulated fetch error")

            monkeypatch.setattr(
                loaded_integrations["example"], "fetch_data", broken_fetch
            )

            try:
                response = client.get("/")
                # Dashboard should still load with error message for the widget
                assert response.status_code == 200
                assert "Error loading" in response.text
            finally:
                # Restore
                monkeypatch.setattr(
                    loaded_integrations["example"], "fetch_data", original_fetch
                )

    def test_dashboard_with_unloaded_widget(self, client: TestClient, monkeypatch):
        """Test dashboard when widget is configured but not loaded."""
        from server.config import WidgetConfig, get_settings

        original_get_settings = get_settings

        def mock_get_settings():
            settings = original_get_settings()
            # Configure widget that isn't loaded
            settings.layout.widgets = [
                WidgetConfig(integration="nonexistent_widget"),
            ]
            return settings

        # Patch where the function is used, not where it's defined
        monkeypatch.setattr("server.main.get_settings", mock_get_settings)

        response = client.get("/")
        # Dashboard should still load successfully even with unloaded widgets
        assert response.status_code == 200

    def test_list_integrations_shows_loaded_status(self, client: TestClient):
        """Test that list_integrations endpoint shows which integrations are loaded."""
        response = client.get("/api/integrations")
        assert response.status_code == 200

        data = response.json()
        # Each integration should have loaded status
        for _integration_name, info in data.items():
            assert "loaded" in info
            assert isinstance(info["loaded"], bool)


class TestLoadAllIntegrations:
    """Tests for load_all_integrations function."""

    def test_load_all_integrations_with_empty_layout(self, monkeypatch):
        """Test load_all_integrations with no widgets configured."""
        from server.config import get_settings
        from server.main import load_all_integrations

        # Mock settings to have empty widgets list
        original_get_settings = get_settings

        def mock_get_settings():
            settings = original_get_settings()
            settings.layout.widgets = []
            return settings

        monkeypatch.setattr("server.main.get_settings", mock_get_settings)

        integrations = load_all_integrations()
        assert integrations == {}

    def test_load_all_integrations_skips_duplicate(self, monkeypatch):
        """Test that load_all_integrations doesn't load same integration twice."""
        from server.config import WidgetConfig, get_settings
        from server.main import load_all_integrations

        # Mock settings to have same integration twice
        original_get_settings = get_settings

        def mock_get_settings():
            settings = original_get_settings()
            # Create two widgets using same integration
            settings.layout.widgets = [
                WidgetConfig(integration="example"),
                WidgetConfig(integration="example"),
            ]
            return settings

        monkeypatch.setattr("server.main.get_settings", mock_get_settings)

        integrations = load_all_integrations()
        # Should only have one instance of example
        assert "example" in integrations

    def test_load_all_integrations_with_empty_integration_name(self, monkeypatch):
        """Test load_all_integrations skips widgets with empty integration name."""
        from server.config import WidgetConfig, get_settings
        from server.main import load_all_integrations

        original_get_settings = get_settings

        def mock_get_settings():
            settings = original_get_settings()
            # Create widget with empty integration name
            settings.layout.widgets = [
                WidgetConfig(integration=""),
                WidgetConfig(integration="example"),
            ]
            return settings

        monkeypatch.setattr("server.main.get_settings", mock_get_settings)

        integrations = load_all_integrations()
        # Should skip empty integration name
        assert "" not in integrations
        assert "example" in integrations

    def test_load_all_integrations_with_unknown_integration(self, monkeypatch):
        """Test load_all_integrations skips unknown integrations."""
        from server.config import WidgetConfig, get_settings
        from server.main import load_all_integrations

        original_get_settings = get_settings

        def mock_get_settings():
            settings = original_get_settings()
            # Create widget with unknown integration
            settings.layout.widgets = [
                WidgetConfig(integration="nonexistent_integration"),
            ]
            return settings

        monkeypatch.setattr("server.main.get_settings", mock_get_settings)

        integrations = load_all_integrations()
        # Should skip unknown integration
        assert "nonexistent_integration" not in integrations

    def test_load_all_integrations_handles_load_error(self, monkeypatch):
        """Test load_all_integrations handles errors when loading integrations."""
        from server.config import WidgetConfig, get_settings
        from server.main import load_all_integrations

        original_get_settings = get_settings

        def mock_get_settings():
            settings = original_get_settings()
            settings.layout.widgets = [
                WidgetConfig(integration="example"),
            ]
            return settings

        def mock_load_integration(name, config, integrations=None):
            # Simulate error loading integration
            raise RuntimeError("Failed to load integration")

        monkeypatch.setattr("server.main.get_settings", mock_get_settings)
        monkeypatch.setattr("server.main.load_integration", mock_load_integration)

        integrations = load_all_integrations()
        # Should skip integration that failed to load
        assert "example" not in integrations


class TestDashboardWithoutStaticFiles:
    """Tests for create_app when static directory doesn't exist."""

    def test_create_app_without_static_dir(self, monkeypatch, tmp_path):
        """Test create_app when static directory doesn't exist."""
        from server.main import create_app

        # Mock the static directory path to a non-existent location
        tmp_path / "nonexistent_static"

        def mock_path_exists(self):
            return False

        monkeypatch.setattr(Path, "exists", mock_path_exists)

        # Should create app successfully even without static dir
        app = create_app()
        assert app is not None


class TestWebSocketHandling:
    """Tests for WebSocket edge cases."""

    def test_websocket_non_ping_message(self, client: TestClient):
        """Test WebSocket with non-ping message."""
        with client.websocket_connect("/ws") as websocket:
            # Send non-ping message
            websocket.send_text("hello")
            # Should not respond (no automatic response for non-ping)
            # Connection should still be open
            websocket.send_text("ping")
            response = websocket.receive_text()
            assert response == "pong"


class TestRefreshWidgetPollingMode:
    """Tests for polling mode in refresh_widget."""

    @pytest.mark.asyncio
    async def test_broadcast_widget_update(self, monkeypatch):
        """Test that broadcast_widget_update handles WebSocket clients."""
        import json
        from unittest.mock import AsyncMock

        from server.main import active_connections, broadcast_widget_update

        # Create mock WebSocket connections
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        # Clear and add mocks
        active_connections.clear()
        active_connections.add(mock_ws1)
        active_connections.add(mock_ws2)

        # Broadcast a message
        await broadcast_widget_update("test_widget", "<div>test</div>")

        # Both should receive the message
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_called_once()

        # Verify message format
        call_args = mock_ws1.send_text.call_args
        message = json.loads(call_args[0][0])
        assert message["type"] == "widget_update"
        assert message["integration"] == "test_widget"
        assert message["html"] == "<div>test</div>"

        # Clean up
        active_connections.clear()

    @pytest.mark.asyncio
    async def test_broadcast_widget_update_removes_disconnected(self, monkeypatch):
        """Test that broadcast removes disconnected WebSocket clients."""
        from unittest.mock import AsyncMock

        from server.main import active_connections, broadcast_widget_update

        # Create mock WebSocket - one will fail
        mock_ws_good = AsyncMock()
        mock_ws_bad = AsyncMock()
        mock_ws_bad.send_text.side_effect = Exception("Connection closed")

        # Add to active connections
        active_connections.clear()
        active_connections.add(mock_ws_good)
        active_connections.add(mock_ws_bad)

        # Broadcast a message
        await broadcast_widget_update("test_widget", "<div>test</div>")

        # Good connection should still be there
        assert mock_ws_good in active_connections
        # Bad connection should be removed
        assert mock_ws_bad not in active_connections

        # Clean up
        active_connections.clear()

    @pytest.mark.asyncio
    async def test_refresh_widget_with_event_stream(self, monkeypatch):
        """Test refresh_widget processes event stream successfully."""
        import asyncio
        from typing import Any, AsyncIterator

        from integrations.base import BaseIntegration, IntegrationConfig
        from server.main import refresh_widget

        class TestConfig(IntegrationConfig):
            pass

        class TestIntegration(BaseIntegration):
            name = "event_test"
            display_name = "Event Test"
            ConfigModel = TestConfig

            async def fetch_data(self) -> dict[str, Any]:
                return {"test": "data"}

            async def start_event_stream(self) -> AsyncIterator[dict[str, Any]]:
                yield {"data": 1}
                yield {"data": 2}
                # End stream after 2 yields
                return

        integration = TestIntegration({})

        # Mock render_widget to avoid template loading
        monkeypatch.setattr(
            integration, "render_widget", lambda data: "<div>rendered</div>"
        )

        broadcast_calls = []

        async def mock_broadcast(name, html):
            broadcast_calls.append(name)

        monkeypatch.setattr("server.main.broadcast_widget_update", mock_broadcast)

        # Run refresh_widget - should process the event stream
        try:
            await asyncio.wait_for(refresh_widget(integration), timeout=1)
        except asyncio.TimeoutError:
            pass

        # Should have broadcast the initial data and 2 events
        assert len(broadcast_calls) >= 2

    @pytest.mark.asyncio
    async def test_refresh_widget_polling_mode(self, monkeypatch):
        """Test refresh_widget falls back to polling mode when event stream raises TypeError."""
        import asyncio
        from typing import Any

        from integrations.base import BaseIntegration, IntegrationConfig
        from server.main import refresh_widget

        class TestConfig(IntegrationConfig):
            pass

        class PollingIntegration(BaseIntegration):
            name = "polling_test"
            display_name = "Polling Test"
            refresh_interval = 0.01  # Very short interval for testing
            ConfigModel = TestConfig

            async def fetch_data(self) -> dict[str, Any]:
                return {"data": "test"}

            def start_event_stream(self):
                # Not an async generator - will raise TypeError when used
                return {"not": "async"}

        integration = PollingIntegration({})

        # Mock render_widget to avoid template loading
        monkeypatch.setattr(
            integration, "render_widget", lambda data: "<div>rendered</div>"
        )

        broadcast_calls = []
        call_count = 0

        async def mock_broadcast(name, html):
            nonlocal call_count
            call_count += 1
            broadcast_calls.append(name)
            # Stop after 2 calls to avoid infinite loop
            if call_count >= 2:
                raise asyncio.CancelledError()

        monkeypatch.setattr("server.main.broadcast_widget_update", mock_broadcast)

        # Run refresh_widget - should use polling mode
        try:
            await asyncio.wait_for(refresh_widget(integration), timeout=2)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

        # Should have broadcast at least twice (in polling mode)
        assert len(broadcast_calls) >= 2


class TestHexToRgbFunction:
    """Tests for hex_to_rgb color conversion function."""

    def test_hex_to_rgb_basic(self):
        """Test basic hex to RGB conversion."""
        assert hex_to_rgb("#ffffff") == "255, 255, 255"
        assert hex_to_rgb("#000000") == "0, 0, 0"

    def test_hex_to_rgb_pink(self):
        """Test hex to RGB conversion with pink color."""
        assert hex_to_rgb("#ff1b8d") == "255, 27, 141"

    def test_hex_to_rgb_cyan(self):
        """Test hex to RGB conversion with cyan color."""
        assert hex_to_rgb("#00d4ff") == "0, 212, 255"

    def test_hex_to_rgb_without_hash(self):
        """Test hex to RGB conversion without leading hash."""
        # Function uses lstrip('#') so it should work with or without
        result = hex_to_rgb("ff1b8d")
        assert result == "255, 27, 141"

    def test_hex_to_rgb_various_colors(self):
        """Test hex to RGB with various colors."""
        assert hex_to_rgb("#ffb000") == "255, 176, 0"  # Amber
        assert hex_to_rgb("#00ff88") == "0, 255, 136"  # Green
        assert hex_to_rgb("#ff3355") == "255, 51, 85"  # Red


class TestThemeRendering:
    """Tests for theme rendering in dashboard."""

    def test_dashboard_with_pink_theme(self, client: TestClient, monkeypatch):
        """Test dashboard renders with pink theme."""
        from server.config import get_settings

        original_get_settings = get_settings

        def mock_get_settings():
            settings = original_get_settings()
            settings.dashboard.theme = "pink"
            return settings

        monkeypatch.setattr("server.main.get_settings", mock_get_settings)

        response = client.get("/")
        assert response.status_code == 200
        # Should contain pink theme color
        assert "#ff1b8d" in response.text  # Pink primary color

    def test_dashboard_with_industrial_theme(self, client: TestClient, monkeypatch):
        """Test dashboard renders with industrial theme."""
        from server.config import get_settings

        original_get_settings = get_settings

        def mock_get_settings():
            settings = original_get_settings()
            settings.dashboard.theme = "industrial"
            return settings

        monkeypatch.setattr("server.main.get_settings", mock_get_settings)

        response = client.get("/")
        assert response.status_code == 200
        # Should contain industrial theme cyan color
        assert "#00d4ff" in response.text

    def test_dashboard_with_unknown_theme_fallback(
        self, client: TestClient, monkeypatch
    ):
        """Test dashboard falls back to industrial when theme is unknown."""
        from server.config import get_settings

        original_get_settings = get_settings

        def mock_get_settings():
            settings = original_get_settings()
            settings.dashboard.theme = "nonexistent_theme"
            return settings

        monkeypatch.setattr("server.main.get_settings", mock_get_settings)

        response = client.get("/")
        assert response.status_code == 200
        # Should fall back to industrial theme
        assert "#00d4ff" in response.text  # Industrial cyan

    def test_dashboard_contains_theme_css_variables(self, client: TestClient):
        """Test dashboard contains CSS variables for theme colors."""
        response = client.get("/")
        assert response.status_code == 200
        # Should have CSS variables defined
        assert "--theme-primary-rgb" in response.text
        assert "--theme-secondary-rgb" in response.text

    def test_dashboard_with_neon_theme(self, client: TestClient, monkeypatch):
        """Test dashboard renders with neon theme."""
        from server.config import get_settings

        original_get_settings = get_settings

        def mock_get_settings():
            settings = original_get_settings()
            settings.dashboard.theme = "neon"
            return settings

        monkeypatch.setattr("server.main.get_settings", mock_get_settings)

        response = client.get("/")
        assert response.status_code == 200
        # Should contain neon theme purple color
        assert "#b833ff" in response.text

    def test_dashboard_with_matrix_theme(self, client: TestClient, monkeypatch):
        """Test dashboard renders with matrix theme."""
        from server.config import get_settings

        original_get_settings = get_settings

        def mock_get_settings():
            settings = original_get_settings()
            settings.dashboard.theme = "matrix"
            return settings

        monkeypatch.setattr("server.main.get_settings", mock_get_settings)

        response = client.get("/")
        assert response.status_code == 200
        # Should contain matrix theme green color
        assert "#00ff41" in response.text
