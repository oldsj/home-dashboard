"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

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
