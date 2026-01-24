"""Tests for configuration loading."""

import os
from pathlib import Path

import yaml

from server.config import (
    AppSettings,
    get_credentials,
    get_settings,
    reload_settings,
    set_config_dir,
)


class TestGetSettings:
    """Tests for get_settings function."""

    def test_get_settings_returns_app_settings(self, setup_config: Path):
        """Test that get_settings returns AppSettings instance."""
        settings = get_settings()
        assert isinstance(settings, AppSettings)

    def test_dashboard_config(self, setup_config: Path):
        """Test dashboard configuration is loaded."""
        settings = get_settings()
        assert settings.dashboard.title == "Test Dashboard"
        assert settings.dashboard.refresh_interval == 30

    def test_layout_config(self, setup_config: Path):
        """Test layout configuration is loaded."""
        settings = get_settings()
        assert settings.layout.columns == 4
        assert settings.layout.rows == 3

    def test_widget_configs(self, setup_config: Path):
        """Test widget configurations are loaded."""
        settings = get_settings()
        assert len(settings.layout.widgets) == 1
        assert settings.layout.widgets[0].integration == "example"

    def test_settings_cached(self, setup_config: Path):
        """Test that settings are cached."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reload_clears_cache(self, setup_config: Path):
        """Test that reload_settings clears the cache."""
        settings1 = get_settings()
        reload_settings()
        settings2 = get_settings()
        assert settings1 is not settings2

    def test_default_values(self, temp_config_dir: Path):
        """Test default values when config is minimal."""
        # Create minimal config
        with open(temp_config_dir / "config.yaml", "w") as f:
            yaml.dump({}, f)

        set_config_dir(temp_config_dir)
        try:
            settings = get_settings()
            assert settings.dashboard.title == "Home Dashboard"
            assert settings.dashboard.theme == "dark"
            assert settings.layout.columns == 3
        finally:
            set_config_dir(None)


class TestGetCredentials:
    """Tests for get_credentials function."""

    def test_get_credentials(self, setup_config: Path):
        """Test getting credentials for an integration."""
        creds = get_credentials("example")
        assert creds["api_key"] == "test-secret-key"
        assert creds["url"] == "https://example.com"

    def test_get_credentials_missing(self, setup_config: Path):
        """Test getting credentials for non-existent integration."""
        creds = get_credentials("nonexistent")
        assert creds == {}

    def test_credentials_file_missing_returns_empty(self, temp_config_dir: Path):
        """Test that missing credentials file returns empty dict."""
        # Remove credentials file
        creds_file = temp_config_dir / "credentials.yaml"
        if creds_file.exists():
            creds_file.unlink()

        set_config_dir(temp_config_dir)
        try:
            creds = get_credentials("example")
            assert creds == {}
        finally:
            set_config_dir(None)


class TestEnvVarOverrides:
    """Tests for environment variable overrides."""

    def test_dashboard_title_override(self, setup_config: Path):
        """Test overriding dashboard title via env var."""
        os.environ["DASHBOARD_DASHBOARD__TITLE"] = "Env Title"
        try:
            reload_settings()
            settings = get_settings()
            assert settings.dashboard.title == "Env Title"
        finally:
            del os.environ["DASHBOARD_DASHBOARD__TITLE"]
            reload_settings()

    def test_credentials_env_override(self, setup_config: Path):
        """Test overriding credentials via env var."""
        os.environ["DASHBOARD_CREDS_EXAMPLE_API_KEY"] = "env-secret-key"
        try:
            creds = get_credentials("example")
            assert creds["api_key"] == "env-secret-key"
        finally:
            del os.environ["DASHBOARD_CREDS_EXAMPLE_API_KEY"]

    def test_credentials_env_adds_new_key(self, setup_config: Path):
        """Test adding new credential key via env var."""
        os.environ["DASHBOARD_CREDS_EXAMPLE_NEW_KEY"] = "new-value"
        try:
            creds = get_credentials("example")
            assert creds["new_key"] == "new-value"
            assert creds["api_key"] == "test-secret-key"  # Original still there
        finally:
            del os.environ["DASHBOARD_CREDS_EXAMPLE_NEW_KEY"]


class TestConfigModels:
    """Tests for Pydantic config models."""

    def test_widget_config_defaults(self):
        """Test WidgetConfig default values."""
        from server.config import WidgetConfig

        widget = WidgetConfig(integration="test")
        assert widget.integration == "test"
        assert widget.enabled is True
        assert widget.position == {}

    def test_layout_config_defaults(self):
        """Test LayoutConfig default values."""
        from server.config import LayoutConfig

        layout = LayoutConfig()
        assert layout.columns == 3
        assert layout.rows == 2
        assert layout.widgets == []

    def test_dashboard_config_defaults(self):
        """Test DashboardConfig default values."""
        from server.config import DashboardConfig

        dashboard = DashboardConfig()
        assert dashboard.title == "Home Dashboard"
        assert dashboard.theme == "dark"
        assert dashboard.refresh_interval == 30

    def test_widget_config_with_position(self):
        """Test WidgetConfig with position settings."""
        from server.config import WidgetConfig

        widget = WidgetConfig(
            integration="test",
            position={"column": 1, "row": 2, "width": 3, "height": 1},
        )
        assert widget.position == {"column": 1, "row": 2, "width": 3, "height": 1}
        assert widget.enabled is True

    def test_widget_config_with_enabled_false(self):
        """Test WidgetConfig with enabled=False."""
        from server.config import WidgetConfig

        widget = WidgetConfig(integration="test", enabled=False)
        assert widget.enabled is False
