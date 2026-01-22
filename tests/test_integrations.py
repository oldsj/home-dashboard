"""Tests for integration discovery and base class."""

import pytest

from integrations import discover_integrations, load_integration
from integrations.base import BaseIntegration


class MockIntegration(BaseIntegration):
    """Mock integration for testing."""

    name = "mock"
    display_name = "Mock Integration"
    refresh_interval = 10

    config_schema = {
        "url": {"type": "str", "required": True},
        "timeout": {"type": "int", "required": False, "default": 30},
    }

    async def fetch_data(self) -> dict:
        return {"status": "ok", "url": self.config.get("url")}


class TestBaseIntegration:
    """Tests for BaseIntegration class."""

    def test_init_with_valid_config(self):
        """Test initialization with valid config."""
        config = {"url": "https://example.com", "api_key": "secret123"}
        integration = MockIntegration(config)

        assert integration.config == config
        assert integration.name == "mock"
        assert integration.display_name == "Mock Integration"

    def test_init_missing_required_field(self):
        """Test initialization fails with missing required field."""
        config = {"timeout": 60}  # Missing required 'url'

        with pytest.raises(ValueError, match="requires config field: url"):
            MockIntegration(config)

    def test_get_config_value(self):
        """Test getting config values with defaults."""
        config = {"url": "https://example.com"}
        integration = MockIntegration(config)

        assert integration.get_config_value("url") == "https://example.com"
        assert integration.get_config_value("timeout") == 30  # From schema default
        assert integration.get_config_value("nonexistent", "fallback") == "fallback"

    def test_sensitive_keys_filtered(self):
        """Test that sensitive keys are filtered from template config."""
        config = {
            "url": "https://example.com",
            "api_key": "secret123",
            "token": "bearer-token",
            "password": "secret-pass",
            "display_name": "My Widget",
        }
        integration = MockIntegration(config)
        safe_config = integration._get_safe_config()

        # Sensitive keys should be filtered
        assert "api_key" not in safe_config
        assert "token" not in safe_config
        assert "password" not in safe_config

        # Non-sensitive keys should remain
        assert safe_config["url"] == "https://example.com"
        assert safe_config["display_name"] == "My Widget"

    def test_sensitive_keys_case_insensitive(self):
        """Test that sensitive key filtering is case-insensitive."""
        config = {
            "url": "https://example.com",
            "API_KEY": "secret",
            "access_token": "token123",
            "my_secret_value": "hidden",
        }
        integration = MockIntegration(config)
        safe_config = integration._get_safe_config()

        assert "API_KEY" not in safe_config
        assert "access_token" not in safe_config
        assert "my_secret_value" not in safe_config
        assert safe_config["url"] == "https://example.com"

    async def test_fetch_data(self):
        """Test fetch_data returns expected data."""
        config = {"url": "https://example.com"}
        integration = MockIntegration(config)

        data = await integration.fetch_data()

        assert data["status"] == "ok"
        assert data["url"] == "https://example.com"


class TestIntegrationDiscovery:
    """Tests for integration discovery functions."""

    def test_discover_integrations(self):
        """Test that example integration is discovered."""
        integrations = discover_integrations()

        assert "example" in integrations
        assert issubclass(integrations["example"], BaseIntegration)

    def test_load_integration(self):
        """Test loading an integration by name."""
        integration = load_integration("example", {"message": "Hello"})

        assert integration.name == "example"
        assert integration.display_name == "Example Widget"

    def test_load_integration_unknown(self):
        """Test loading unknown integration raises error."""
        with pytest.raises(ValueError, match="Unknown integration: nonexistent"):
            load_integration("nonexistent", {})

    async def test_example_integration_fetch_data(self):
        """Test example integration returns valid data."""
        integration = load_integration("example", {"message": "Test"})
        data = await integration.fetch_data()

        assert "current_time" in data
        assert "current_date" in data
        assert "message" in data
        assert "stats" in data
        assert len(data["stats"]) == 3
