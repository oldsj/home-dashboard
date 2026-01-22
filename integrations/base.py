"""
Base integration class.

Re-exports from the dashboard-integration-base package for backward compatibility.
All integrations must inherit from BaseIntegration and implement the required methods.
"""

from dashboard_integration_base import BaseIntegration, IntegrationConfig

__all__ = ["BaseIntegration", "IntegrationConfig"]
