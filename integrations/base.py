"""
Base integration class.

All integrations must inherit from BaseIntegration and implement
the required methods. This ensures a consistent pattern that AI
agents can easily follow when creating new integrations.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Optional, Type

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, ConfigDict, ValidationError


class IntegrationConfig(BaseModel):
    """
    Base Pydantic model for integration configuration.

    Subclass this to define typed configuration for your integration.
    Fields marked with `json_schema_extra={"secret": True}` will be
    filtered from template context.

    Example:
        class MyConfig(IntegrationConfig):
            api_key: str = Field(..., json_schema_extra={"secret": True})
            refresh_rate: int = 60
            message: str = "Hello"
    """

    model_config = ConfigDict(extra="allow")


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
        ConfigModel: Pydantic model class for config validation (recommended)
        config_schema: Dict describing config fields (legacy, deprecated)
    """

    # Required - must be overridden
    name: str = ""
    display_name: str = ""

    # Optional - can be overridden
    refresh_interval: int = 30

    # Pydantic config model (recommended approach)
    ConfigModel: ClassVar[Optional[Type[IntegrationConfig]]] = None

    # Legacy dict-based schema (deprecated, use ConfigModel instead)
    config_schema: ClassVar[dict[str, dict[str, Any]]] = {}

    # Keys that should never be exposed to templates
    _sensitive_keys: ClassVar[set[str]] = {
        "api_key", "token", "secret", "password", "credentials", "key"
    }

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the integration with its configuration.

        Args:
            config: Integration-specific config from credentials.yaml
        """
        self._raw_config = config
        self._validated_config: Optional[IntegrationConfig] = None
        self._validate_config()
        self._template_env: Optional[Environment] = None

    @property
    def config(self) -> dict[str, Any]:
        """Get config as a dict (for backward compatibility)."""
        if self._validated_config is not None:
            return self._validated_config.model_dump()
        return self._raw_config

    def _validate_config(self) -> None:
        """Validate config against schema or Pydantic model."""
        # Prefer Pydantic model if defined
        if self.ConfigModel is not None:
            try:
                self._validated_config = self.ConfigModel(**self._raw_config)
            except ValidationError as e:
                raise ValueError(
                    f"Integration '{self.name}' config validation failed: {e}"
                ) from e
            return

        # Fall back to legacy dict-based validation
        for field, schema in self.config_schema.items():
            if schema.get("required", False) and field not in self._raw_config:
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
    async def fetch_data(self) -> dict[str, Any]:
        """
        Fetch data from the integration's source.

        This method is called periodically (based on refresh_interval)
        to get fresh data for the widget.

        Returns:
            Dict containing data to pass to the widget template
        """
        pass

    def _get_safe_config(self) -> dict[str, Any]:
        """
        Get config with sensitive keys filtered out.

        For Pydantic models, also filters fields marked with secret=True
        in json_schema_extra.

        Returns:
            Config dict safe for template rendering
        """
        safe_config: dict[str, Any] = {}

        # Get secret fields from Pydantic model if available
        secret_fields: set[str] = set()
        if self.ConfigModel is not None:
            for field_name, field_info in self.ConfigModel.model_fields.items():
                extra = field_info.json_schema_extra
                if isinstance(extra, dict) and extra.get("secret"):
                    secret_fields.add(field_name)

        for key, value in self.config.items():
            # Skip if marked as secret in Pydantic model
            if key in secret_fields:
                continue
            # Skip if key contains sensitive patterns
            if any(sensitive in key.lower() for sensitive in self._sensitive_keys):
                continue
            safe_config[key] = value

        return safe_config

    def render_widget(self, data: dict[str, Any]) -> str:
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
        # For Pydantic models, use getattr on validated config
        if self._validated_config is not None:
            return getattr(self._validated_config, key, default)

        # Legacy dict-based config
        if key in self._raw_config:
            return self._raw_config[key]

        # Check schema for default
        if key in self.config_schema:
            schema_default = self.config_schema[key].get("default", default)
            return schema_default

        return default
