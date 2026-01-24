"""Integration tests for theme system - no mocks, real config loading."""

import tempfile
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from server.config import get_settings, set_config_dir
from server.main import app


@pytest.fixture
def real_config_dir():
    """Create a real temporary config directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)

        # Create config.yaml with matrix theme
        config_data = {
            "dashboard": {
                "title": "Test Dashboard",
                "theme": "matrix",
                "refresh_interval": 30,
                "resolution": "1920x1080",
            },
            "layout": {
                "columns": 3,
                "rows": 2,
                "gap": 16,
                "padding": 16,
                "widgets": [],
            },
        }
        with open(config_dir / "config.yaml", "w") as f:
            yaml.dump(config_data, f)

        # Create empty credentials.yaml
        with open(config_dir / "credentials.yaml", "w") as f:
            yaml.dump({}, f)

        # Set the config directory
        get_settings.cache_info()  # Store original cache state
        set_config_dir(config_dir)

        yield config_dir

        # Restore original
        set_config_dir(None)


def test_matrix_theme_loads_from_real_config(real_config_dir):
    """Test that matrix theme actually loads from config.yaml file."""
    # This is a TRUE integration test - no mocks
    with TestClient(app) as client:
        response = client.get("/")

        assert response.status_code == 200
        # Matrix theme green should be in the rendered HTML
        assert "#00ff41" in response.text, "Matrix green color not found in output"
        # Should NOT have pink theme colors
        assert "#ff1b8d" not in response.text, "Pink theme leaked into matrix theme"


def test_pink_theme_loads_from_real_config():
    """Test that pink theme loads from config.yaml file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)

        # Create config.yaml with pink theme
        config_data = {
            "dashboard": {
                "title": "Pink Dashboard",
                "theme": "pink",
                "refresh_interval": 30,
            },
            "layout": {
                "columns": 3,
                "rows": 2,
                "gap": 16,
                "padding": 16,
                "widgets": [],
            },
        }
        with open(config_dir / "config.yaml", "w") as f:
            yaml.dump(config_data, f)

        with open(config_dir / "credentials.yaml", "w") as f:
            yaml.dump({}, f)

        set_config_dir(config_dir)

        try:
            with TestClient(app) as client:
                response = client.get("/")

                assert response.status_code == 200
                # Pink theme primary should be in output
                assert "#ff1b8d" in response.text, "Pink color not found"
                # Should NOT have matrix green
                assert "#00ff41" not in response.text, "Matrix green leaked in"
        finally:
            set_config_dir(None)


def test_industrial_theme_loads_from_real_config():
    """Test that industrial theme loads from config.yaml file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)

        # Create config.yaml with industrial theme
        config_data = {
            "dashboard": {"title": "Industrial", "theme": "industrial"},
            "layout": {"columns": 3, "rows": 2, "widgets": []},
        }
        with open(config_dir / "config.yaml", "w") as f:
            yaml.dump(config_data, f)

        with open(config_dir / "credentials.yaml", "w") as f:
            yaml.dump({}, f)

        set_config_dir(config_dir)

        try:
            with TestClient(app) as client:
                response = client.get("/")

                assert response.status_code == 200
                # Industrial cyan should be present
                assert "#00d4ff" in response.text, "Industrial cyan not found"
        finally:
            set_config_dir(None)


def test_theme_change_between_requests():
    """Test that changing config and reloading settings picks up new theme."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        config_file = config_dir / "config.yaml"

        # Start with pink
        config_data = {
            "dashboard": {"title": "Test", "theme": "pink"},
            "layout": {"columns": 3, "rows": 2, "widgets": []},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with open(config_dir / "credentials.yaml", "w") as f:
            yaml.dump({}, f)

        set_config_dir(config_dir)

        try:
            # First request - pink
            with TestClient(app) as client:
                response = client.get("/")
                assert "#ff1b8d" in response.text, "Pink not in first request"

            # Change to matrix
            config_data["dashboard"]["theme"] = "matrix"
            with open(config_file, "w") as f:
                yaml.dump(config_data, f)

            # Clear cache to simulate server restart
            from server.config import reload_settings

            reload_settings()

            # Second request - should be matrix
            with TestClient(app) as client:
                response = client.get("/")
                assert "#00ff41" in response.text, "Matrix not in second request"
                assert "#ff1b8d" not in response.text, "Pink still present"

        finally:
            set_config_dir(None)
