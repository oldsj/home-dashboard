"""
Configuration management using pydantic-settings.

Provides type-safe configuration with YAML file support and
environment variable overrides for 12-factor app compliance.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class WidgetConfig(BaseModel):
    """Configuration for a single widget in the layout."""

    model_config = ConfigDict(extra="allow")

    integration: str
    enabled: bool = True
    position: dict[str, Any] = {}


class LayoutConfig(BaseModel):
    """Layout configuration for the dashboard."""

    model_config = ConfigDict(extra="allow")

    columns: int = 3
    rows: int = 2
    gap: int = 16
    padding: int = 16
    widgets: list[WidgetConfig] = []


class DashboardConfig(BaseModel):
    """Dashboard-specific configuration."""

    model_config = ConfigDict(extra="allow")

    title: str = "Home Dashboard"
    theme: str = "dark"
    refresh_interval: int = 30
    resolution: str = "1920x1080"


# Config directory (can be overridden for testing)
_config_dir: Path | None = None


def set_config_dir(path: Path | None) -> None:
    """Set the config directory (for testing)."""
    global _config_dir
    _config_dir = path
    # Clear cached settings when directory changes
    get_settings.cache_clear()
    _get_credentials_data.cache_clear()


def get_config_dir() -> Path:
    """Get the config directory path."""
    if _config_dir is not None:
        return _config_dir
    return Path(__file__).parent.parent / "config"


class AppSettings(BaseSettings):
    """Application settings loaded from YAML with env var support."""

    model_config = SettingsConfigDict(
        env_prefix="DASHBOARD_",
        env_nested_delimiter="__",
        extra="allow",
    )

    dashboard: DashboardConfig = DashboardConfig()
    layout: LayoutConfig = LayoutConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources: env vars > YAML > defaults."""
        yaml_file = get_config_dir() / "config.yaml"
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file),
        )


@lru_cache
def get_settings() -> AppSettings:
    """
    Get application settings (cached).

    Returns:
        AppSettings instance with config from YAML and env vars
    """
    return AppSettings()


@lru_cache
def _get_credentials_data() -> dict[str, Any]:
    """Load raw credentials from YAML file (cached)."""
    creds_file = get_config_dir() / "credentials.yaml"
    if creds_file.exists():
        with open(creds_file) as f:
            return yaml.safe_load(f) or {}
    return {}


def get_credentials(integration_name: str) -> dict[str, Any]:
    """
    Get credentials for an integration.

    Supports environment variable overrides with DASHBOARD_CREDS_{INTEGRATION}_{KEY} format.
    For example: DASHBOARD_CREDS_EXAMPLE_API_KEY overrides example.api_key

    Args:
        integration_name: Name of the integration

    Returns:
        Credentials dict for the integration
    """
    import os

    # Start with YAML credentials
    creds = dict(_get_credentials_data().get(integration_name, {}))

    # Apply environment variable overrides
    env_prefix = f"DASHBOARD_CREDS_{integration_name.upper()}_"
    for key, value in os.environ.items():
        if key.startswith(env_prefix):
            cred_key = key[len(env_prefix) :].lower()
            creds[cred_key] = value

    return creds


def reload_settings() -> None:
    """Force reload all settings."""
    get_settings.cache_clear()
    _get_credentials_data.cache_clear()
