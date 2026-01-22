"""Tests for configuration loading."""

import tempfile
from pathlib import Path

import pytest
import yaml

from server.config import ConfigLoader


class TestConfigLoader:
    """Tests for ConfigLoader class."""

    def test_load_config(self, config_loader: ConfigLoader):
        """Test loading main config file."""
        config = config_loader.load_config()

        assert "dashboard" in config
        assert config["dashboard"]["title"] == "Test Dashboard"

    def test_load_credentials(self, config_loader: ConfigLoader):
        """Test loading credentials file."""
        creds = config_loader.load_credentials()

        assert "example" in creds
        assert creds["example"]["api_key"] == "test-secret-key"

    def test_get_dashboard_config(self, config_loader: ConfigLoader):
        """Test getting dashboard-specific config."""
        dashboard = config_loader.get_dashboard_config()

        assert dashboard["title"] == "Test Dashboard"
        assert dashboard["refresh_interval"] == 30

    def test_get_layout_config(self, config_loader: ConfigLoader):
        """Test getting layout config."""
        layout = config_loader.get_layout_config()

        assert layout["columns"] == 4
        assert layout["rows"] == 3
        assert "widgets" in layout

    def test_get_widget_configs(self, config_loader: ConfigLoader):
        """Test getting widget configurations."""
        widgets = config_loader.get_widget_configs()

        assert len(widgets) == 1
        assert widgets[0]["integration"] == "example"

    def test_get_integration_credentials(self, config_loader: ConfigLoader):
        """Test getting credentials for a specific integration."""
        creds = config_loader.get_integration_credentials("example")

        assert creds["api_key"] == "test-secret-key"
        assert creds["url"] == "https://example.com"

    def test_get_integration_credentials_missing(self, config_loader: ConfigLoader):
        """Test getting credentials for non-existent integration."""
        creds = config_loader.get_integration_credentials("nonexistent")

        assert creds == {}

    def test_reload(self, config_loader: ConfigLoader):
        """Test reloading configuration."""
        # Load config first
        config_loader.load_config()
        config_loader.load_credentials()

        # Reload
        config_loader.reload()

        # Internal cache should be cleared
        assert config_loader._config is None
        assert config_loader._credentials is None

    def test_config_file_not_found(self):
        """Test error when config file doesn't exist."""
        loader = ConfigLoader(config_dir=Path("/nonexistent/path"))

        with pytest.raises(FileNotFoundError):
            loader.load_config()

    def test_credentials_file_missing_returns_empty(self):
        """Test that missing credentials file returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            # Create only config.yaml, not credentials.yaml
            with open(config_dir / "config.yaml", "w") as f:
                yaml.dump({"dashboard": {}}, f)

            loader = ConfigLoader(config_dir=config_dir)
            creds = loader.load_credentials()

            assert creds == {}

    def test_config_caching(self, config_loader: ConfigLoader):
        """Test that config is cached after first load."""
        config1 = config_loader.load_config()
        config2 = config_loader.load_config()

        # Should be the same object (cached)
        assert config1 is config2
