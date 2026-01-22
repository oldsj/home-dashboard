"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from server.main import app


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
        with client.websocket_connect("/ws") as websocket:
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

            monkeypatch.setattr(loaded_integrations["example"], "fetch_data", broken_fetch)

            try:
                response = client.get("/api/widgets/example")
                # Should return 500 with error message
                assert response.status_code == 500
                assert "Error loading widget" in response.text
            finally:
                # Restore
                monkeypatch.setattr(loaded_integrations["example"], "fetch_data", original_fetch)

    def test_error_handling_in_dashboard_widget(self, client: TestClient, monkeypatch):
        """Test error handling when dashboard widget fails."""
        from server.main import loaded_integrations

        # Temporarily break the example integration
        if "example" in loaded_integrations:
            original_fetch = loaded_integrations["example"].fetch_data

            async def broken_fetch():
                raise RuntimeError("Simulated fetch error")

            monkeypatch.setattr(loaded_integrations["example"], "fetch_data", broken_fetch)

            try:
                response = client.get("/")
                # Dashboard should still load with error message for the widget
                assert response.status_code == 200
                assert "Error loading" in response.text
            finally:
                # Restore
                monkeypatch.setattr(loaded_integrations["example"], "fetch_data", original_fetch)

    def test_dashboard_with_unloaded_widget(self, client: TestClient, monkeypatch):
        """Test dashboard when widget is configured but not loaded."""
        from server.config import get_settings, WidgetConfig

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
        for integration_name, info in data.items():
            assert "loaded" in info
            assert isinstance(info["loaded"], bool)


class TestLoadAllIntegrations:
    """Tests for load_all_integrations function."""

    def test_load_all_integrations_with_empty_layout(self, monkeypatch):
        """Test load_all_integrations with no widgets configured."""
        from server.main import load_all_integrations
        from server.config import get_settings

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
        from server.main import load_all_integrations
        from server.config import get_settings, WidgetConfig

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
        from server.main import load_all_integrations
        from server.config import get_settings, WidgetConfig

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
        from server.main import load_all_integrations
        from server.config import get_settings, WidgetConfig

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
        from server.main import load_all_integrations
        from server.config import get_settings, WidgetConfig
        from integrations import load_integration

        original_get_settings = get_settings
        original_load_integration = load_integration

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
        fake_static_dir = tmp_path / "nonexistent_static"

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
