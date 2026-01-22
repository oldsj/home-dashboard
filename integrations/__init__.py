"""
Integration auto-discovery module.

Automatically discovers and loads all integrations from subdirectories.
Each integration must have an integration.py file with a class that
inherits from BaseIntegration.
"""

import importlib
import logging
from pathlib import Path
from typing import Any

from .base import BaseIntegration

logger = logging.getLogger(__name__)


def discover_integrations() -> dict[str, type[BaseIntegration]]:
    """
    Discover all integrations in the integrations directory.

    Returns:
        Dict mapping integration name to integration class
    """
    integrations: dict[str, type[BaseIntegration]] = {}
    integrations_dir = Path(__file__).parent

    for item in integrations_dir.iterdir():
        if not item.is_dir():
            continue
        if item.name.startswith("_"):
            continue

        integration_file = item / "integration.py"
        if not integration_file.exists():
            continue

        try:
            module = importlib.import_module(f"integrations.{item.name}.integration")

            # Find the integration class (pragma handles branch where no class found)
            for attr_name in dir(module):  # pragma: no branch
                attr = getattr(module, attr_name)
                if (  # pragma: no branch
                    isinstance(attr, type)
                    and issubclass(attr, BaseIntegration)
                    and attr is not BaseIntegration
                ):
                    integrations[attr.name] = attr
                    break

        except Exception:  # pragma: no cover - defensive error handling
            logger.exception("Failed to load integration '%s'", item.name)

    return integrations


def load_integration(
    name: str,
    config: dict[str, Any],
    integrations: dict[str, type[BaseIntegration]] | None = None,
) -> BaseIntegration:
    """
    Load and instantiate an integration by name.

    Args:
        name: Integration name (e.g., "todoist")
        config: Integration-specific config from credentials.yaml
        integrations: Optional pre-discovered integrations dict

    Returns:
        Instantiated integration object
    """
    if integrations is None:
        integrations = discover_integrations()

    if name not in integrations:
        raise ValueError(f"Unknown integration: {name}")

    return integrations[name](config)
