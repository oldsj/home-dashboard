"""
Example integration - demonstrates the integration pattern.

This is a reference implementation that AI agents can copy when
creating new integrations. It shows all required methods and
common patterns.
"""

from collections import deque
from datetime import datetime
from typing import Any

import psutil
from dashboard_integration_base import BaseIntegration, IntegrationConfig


class ExampleConfig(IntegrationConfig):
    """
    Configuration model for the Example integration.

    This demonstrates how to define typed configuration using Pydantic.
    """

    message: str = "Welcome to Dashboard"


class ExampleIntegration(BaseIntegration):
    """
    Example integration that displays current time and system stats.

    Provides real CPU, memory, and temperature metrics with 3-minute
    rolling averages to reduce jitter.
    """

    name = "example"
    display_name = "Example Widget"
    refresh_interval = 1  # Update every 1 second for smooth clock

    # Pydantic config model for typed validation
    ConfigModel = ExampleConfig

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize with rolling average buffers (180 samples = 3 minutes)."""
        super().__init__(*args, **kwargs)
        self._cpu_history: deque[float] = deque(maxlen=180)
        self._memory_history: deque[float] = deque(maxlen=180)
        self._temp_history: deque[float] = deque(maxlen=180)

    def _get_rolling_average(self, history: deque[float]) -> float:
        """Calculate rolling average from history."""
        if not history:
            return 0.0
        return sum(history) / len(history)

    async def fetch_data(self) -> dict[str, Any]:
        """
        Fetch real system metrics with rolling averages.

        Returns:
            Dict with current time, date, and 3-minute averaged system stats
        """
        # Get current system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent

        # Try to get temperature (may not be available on all systems)
        temp = 0.0
        try:
            temps = psutil.sensors_temperatures()
            if temps:  # pragma: no cover - requires hardware temp sensors
                # Get first available temperature sensor
                first_sensor = next(iter(temps.values()))
                temp = first_sensor[0].current if first_sensor else 0.0
        except (AttributeError, OSError):
            # Temperature not available on this system
            pass

        # Add to rolling history
        self._cpu_history.append(cpu_percent)
        self._memory_history.append(memory_percent)
        if temp > 0:  # pragma: no cover - requires hardware temp sensors
            self._temp_history.append(temp)

        # Calculate rolling averages
        cpu_avg = round(self._get_rolling_average(self._cpu_history), 1)
        memory_avg = round(self._get_rolling_average(self._memory_history), 1)
        temp_avg = (
            round(self._get_rolling_average(self._temp_history), 1)
            if self._temp_history
            else temp
        )

        return {
            "current_time": datetime.now().strftime("%H:%M:%S"),
            "current_date": datetime.now().strftime("%A, %B %d, %Y"),
            "message": self.get_config_value("message"),
            "stats": [
                {"label": "CPU", "value": cpu_avg, "unit": "%"},
                {"label": "Memory", "value": memory_avg, "unit": "%"},
                {"label": "Temp", "value": temp_avg, "unit": "°C"},
            ],
        }
