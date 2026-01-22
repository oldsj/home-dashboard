"""
Configuration loader for the dashboard.

Handles loading and validating YAML configuration files.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict


class WidgetConfig(BaseModel):
    """Configuration for a single widget in the layout."""

    model_config = ConfigDict(extra="allow")

    name: str
    enabled: bool = True
    position: int = 0


class LayoutConfig(BaseModel):
    """Layout configuration for the dashboard."""

    model_config = ConfigDict(extra="allow")

    columns: int = 3
    widgets: list[WidgetConfig] = []


class DashboardConfig(BaseModel):
    """Dashboard-specific configuration."""

    model_config = ConfigDict(extra="allow")

    title: str = "Home Dashboard"
    theme: str = "dark"
    refresh_interval: int = 30


class AppConfig(BaseModel):
    """Root configuration model."""

    model_config = ConfigDict(extra="allow")

    dashboard: DashboardConfig = DashboardConfig()
    layout: LayoutConfig = LayoutConfig()


class ConfigLoader:
    """Loads and manages dashboard configuration."""

    def __init__(self, config_dir: Path | None = None) -> None:
        """
        Initialize the config loader.

        Args:
            config_dir: Path to config directory. Defaults to project config/
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "config"
        self.config_dir = config_dir
        self._config: dict[str, Any] | None = None
        self._credentials: dict[str, Any] | None = None
        self._app_config: AppConfig | None = None

    def load_config(self) -> dict[str, Any]:
        """
        Load the main configuration file.

        Returns:
            Parsed config dict
        """
        if self._config is None:
            config_file = self.config_dir / "config.yaml"
            if not config_file.exists():
                raise FileNotFoundError(f"Config file not found: {config_file}")

            with open(config_file) as f:
                self._config = yaml.safe_load(f) or {}

        return self._config

    def get_app_config(self) -> AppConfig:
        """
        Load and validate configuration using Pydantic models.

        Returns:
            Validated AppConfig instance
        """
        if self._app_config is None:
            raw_config = self.load_config()
            self._app_config = AppConfig(**raw_config)
        return self._app_config

    def load_credentials(self) -> dict[str, Any]:
        """
        Load the credentials file.

        Returns:
            Parsed credentials dict (empty dict if file doesn't exist)
        """
        if self._credentials is None:
            creds_file = self.config_dir / "credentials.yaml"
            if creds_file.exists():
                with open(creds_file) as f:
                    self._credentials = yaml.safe_load(f) or {}
            else:
                self._credentials = {}

        return self._credentials

    def get_dashboard_config(self) -> dict[str, Any]:
        """Get dashboard-specific configuration."""
        config = self.load_config()
        return dict(config.get("dashboard", {}))

    def get_layout_config(self) -> dict[str, Any]:
        """Get layout configuration."""
        config = self.load_config()
        return dict(config.get("layout", {}))

    def get_widget_configs(self) -> list[dict[str, Any]]:
        """Get list of widget configurations."""
        layout = self.get_layout_config()
        widgets = layout.get("widgets", [])
        return list(widgets) if widgets else []

    def get_integration_credentials(self, integration_name: str) -> dict[str, Any]:
        """
        Get credentials for a specific integration.

        Args:
            integration_name: Name of the integration

        Returns:
            Integration credentials dict (empty if not configured)
        """
        credentials = self.load_credentials()
        return dict(credentials.get(integration_name, {}))

    def reload(self) -> None:
        """Force reload of all configuration files."""
        self._config = None
        self._credentials = None
        self._app_config = None


# Global config loader instance
config_loader = ConfigLoader()
