"""Pytest fixtures for dashboard tests."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest
import yaml
from fastapi.testclient import TestClient


@pytest.fixture
def temp_config_dir() -> Generator[Path, None, None]:
    """Create a temporary config directory with test config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)

        # Create config.yaml
        config = {
            "dashboard": {
                "title": "Test Dashboard",
                "refresh_interval": 30,
            },
            "layout": {
                "columns": 4,
                "rows": 3,
                "widgets": [
                    {
                        "integration": "example",
                        "position": {"column": 1, "row": 1, "width": 2, "height": 1},
                    }
                ],
            },
        }
        with open(config_dir / "config.yaml", "w") as f:
            yaml.dump(config, f)

        # Create credentials.yaml
        credentials = {
            "example": {
                "api_key": "test-secret-key",
                "url": "https://example.com",
            }
        }
        with open(config_dir / "credentials.yaml", "w") as f:
            yaml.dump(credentials, f)

        yield config_dir


@pytest.fixture
def setup_config(temp_config_dir: Path) -> Generator[Path, None, None]:
    """Set up config directory for testing and clean up after."""
    from server.config import set_config_dir

    set_config_dir(temp_config_dir)
    yield temp_config_dir
    set_config_dir(None)


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    from server.main import app

    with TestClient(app) as client:
        yield client
