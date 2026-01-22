"""
Example integration - demonstrates the integration pattern.

This is a reference implementation that AI agents can copy when
creating new integrations. It shows all required methods and
common patterns.
"""

import random
from datetime import datetime

from integrations.base import BaseIntegration


class ExampleIntegration(BaseIntegration):
    """
    Example integration that displays current time and random data.

    This integration requires no external API and serves as a template
    for creating new integrations.
    """

    name = "example"
    display_name = "Example Widget"
    refresh_interval = 5  # Update every 5 seconds

    # No credentials required for this example
    config_schema = {
        "message": {
            "type": "str",
            "required": False,
            "default": "Welcome to Dashboard"
        }
    }

    async def fetch_data(self) -> dict:
        """
        Fetch data for the widget.

        In a real integration, this would call an external API.
        Here we just return current time and some random data.

        Returns:
            Dict with data for the widget template
        """
        return {
            "current_time": datetime.now().strftime("%H:%M:%S"),
            "current_date": datetime.now().strftime("%A, %B %d, %Y"),
            "message": self.get_config_value("message"),
            "stats": [
                {"label": "CPU", "value": random.randint(10, 90), "unit": "%"},
                {"label": "Memory", "value": random.randint(30, 80), "unit": "%"},
                {"label": "Temp", "value": random.randint(40, 70), "unit": "°C"},
            ]
        }
