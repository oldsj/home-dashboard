"""
Configuration loader for the dashboard.

Handles loading and validating YAML configuration files.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigLoader:
    """Loads and manages dashboard configuration."""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the config loader.

        Args:
            config_dir: Path to config directory. Defaults to project config/
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "config"
        self.config_dir = config_dir
        self._config: Optional[Dict] = None
        self._credentials: Optional[Dict] = None

    def load_config(self) -> Dict[str, Any]:
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

    def load_credentials(self) -> Dict[str, Any]:
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

    def get_dashboard_config(self) -> Dict[str, Any]:
        """Get dashboard-specific configuration."""
        config = self.load_config()
        return config.get("dashboard", {})

    def get_layout_config(self) -> Dict[str, Any]:
        """Get layout configuration."""
        config = self.load_config()
        return config.get("layout", {})

    def get_widget_configs(self) -> list:
        """Get list of widget configurations."""
        layout = self.get_layout_config()
        return layout.get("widgets", [])

    def get_integration_credentials(self, integration_name: str) -> Dict[str, Any]:
        """
        Get credentials for a specific integration.

        Args:
            integration_name: Name of the integration

        Returns:
            Integration credentials dict (empty if not configured)
        """
        credentials = self.load_credentials()
        return credentials.get(integration_name, {})

    def reload(self) -> None:
        """Force reload of all configuration files."""
        self._config = None
        self._credentials = None


# Global config loader instance
config_loader = ConfigLoader()
