"""
Base integration class.

All integrations must inherit from BaseIntegration and implement
the required methods. This ensures a consistent pattern that AI
agents can easily follow when creating new integrations.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader


class BaseIntegration(ABC):
    """
    Base class for all dashboard integrations.

    To create a new integration:
    1. Create a new directory in integrations/ (e.g., integrations/todoist/)
    2. Create integration.py with a class inheriting from BaseIntegration
    3. Create widget.html with the Jinja2 template for the widget
    4. Add credentials to config/credentials.yaml
    5. Enable the widget in config/config.yaml

    Required class attributes:
        name: Unique identifier (e.g., "todoist")
        display_name: Human-readable name (e.g., "Todoist")

    Optional class attributes:
        refresh_interval: Seconds between data fetches (default: 30)
        config_schema: Dict describing required/optional config fields
    """

    # Required - must be overridden
    name: str = ""
    display_name: str = ""

    # Optional - can be overridden
    refresh_interval: int = 30
    config_schema: Dict[str, Dict[str, Any]] = {}

    # Keys that should never be exposed to templates
    _sensitive_keys: set = {"api_key", "token", "secret", "password", "credentials", "key"}

    def __init__(self, config: dict):
        """
        Initialize the integration with its configuration.

        Args:
            config: Integration-specific config from credentials.yaml
        """
        self.config = config
        self._validate_config()
        self._template_env = None

    def _validate_config(self) -> None:
        """Validate config against schema."""
        for field, schema in self.config_schema.items():
            if schema.get("required", False) and field not in self.config:
                raise ValueError(
                    f"Integration '{self.name}' requires config field: {field}"
                )

    def _get_template_env(self) -> Environment:
        """Get Jinja2 environment for this integration's templates."""
        if self._template_env is None:
            template_dir = Path(__file__).parent / self.name
            self._template_env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=True
            )
        return self._template_env

    @abstractmethod
    async def fetch_data(self) -> dict:
        """
        Fetch data from the integration's source.

        This method is called periodically (based on refresh_interval)
        to get fresh data for the widget.

        Returns:
            Dict containing data to pass to the widget template
        """
        pass

    def _get_safe_config(self) -> Dict[str, Any]:
        """
        Get config with sensitive keys filtered out.

        Returns:
            Config dict safe for template rendering
        """
        return {
            k: v for k, v in self.config.items()
            if not any(sensitive in k.lower() for sensitive in self._sensitive_keys)
        }

    def render_widget(self, data: dict) -> str:
        """
        Render the widget HTML using the template and data.

        Override this method if you need custom rendering logic.
        By default, it loads widget.html from the integration directory.

        Args:
            data: Data returned from fetch_data()

        Returns:
            Rendered HTML string
        """
        env = self._get_template_env()
        template = env.get_template("widget.html")
        return template.render(data=data, config=self._get_safe_config())

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a config value with optional default.

        Args:
            key: Config key to retrieve
            default: Default value if key not found

        Returns:
            Config value or default
        """
        if key in self.config:
            return self.config[key]

        # Check schema for default
        if key in self.config_schema:
            return self.config_schema[key].get("default", default)

        return default
