"""
Example integration shim - re-exports from installed package.

This file provides backward compatibility with the discovery mechanism.
The actual implementation is in the example_integration package.
"""

from example_integration.integration import ExampleIntegration

__all__ = ["ExampleIntegration"]
