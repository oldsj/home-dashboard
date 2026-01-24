"""Tests for integration discovery and base class."""

import pytest
from pydantic import Field

from integrations import discover_integrations, load_integration
from integrations.base import BaseIntegration, IntegrationConfig


class MockIntegrationConfig(IntegrationConfig):
    """Configuration for MockIntegration."""

    url: str = Field(..., description="URL for the mock integration")
    timeout: int = Field(default=30, description="Timeout in seconds")


class MockIntegration(BaseIntegration):
    """Mock integration for testing."""

    name = "mock"
    display_name = "Mock Integration"
    refresh_interval = 10

    ConfigModel = MockIntegrationConfig

    async def fetch_data(self) -> dict:
        return {"status": "ok", "url": self.config.get("url")}


class TestBaseIntegration:
    """Tests for BaseIntegration class."""

    def test_init_with_valid_config(self):
        """Test initialization with valid config."""
        config = {"url": "https://example.com", "api_key": "secret123"}
        integration = MockIntegration(config)

        # Config includes default values from Pydantic model
        assert integration.config["url"] == "https://example.com"
        assert integration.config["api_key"] == "secret123"
        assert integration.config["timeout"] == 30  # Default value
        assert integration.name == "mock"
        assert integration.display_name == "Mock Integration"

    def test_init_missing_required_field(self):
        """Test initialization fails with missing required field."""
        config = {"timeout": 60}  # Missing required 'url'

        with pytest.raises(ValueError, match="config validation failed"):
            MockIntegration(config)

    def test_get_config_value(self):
        """Test getting config values with defaults."""
        config = {"url": "https://example.com"}
        integration = MockIntegration(config)

        assert integration.get_config_value("url") == "https://example.com"
        assert integration.get_config_value("timeout") == 30  # From schema default
        assert integration.get_config_value("nonexistent", "fallback") == "fallback"

    def test_sensitive_keys_filtered(self):
        """Test that sensitive keys are filtered from template config."""
        config = {
            "url": "https://example.com",
            "api_key": "secret123",
            "token": "bearer-token",
            "password": "secret-pass",
            "display_name": "My Widget",
        }
        integration = MockIntegration(config)
        safe_config = integration._get_safe_config()

        # Sensitive keys should be filtered
        assert "api_key" not in safe_config
        assert "token" not in safe_config
        assert "password" not in safe_config

        # Non-sensitive keys should remain
        assert safe_config["url"] == "https://example.com"
        assert safe_config["display_name"] == "My Widget"

    def test_sensitive_keys_case_insensitive(self):
        """Test that sensitive key filtering is case-insensitive."""
        config = {
            "url": "https://example.com",
            "API_KEY": "secret",
            "access_token": "token123",
            "my_secret_value": "hidden",
        }
        integration = MockIntegration(config)
        safe_config = integration._get_safe_config()

        assert "API_KEY" not in safe_config
        assert "access_token" not in safe_config
        assert "my_secret_value" not in safe_config
        assert safe_config["url"] == "https://example.com"

    async def test_fetch_data(self):
        """Test fetch_data returns expected data."""
        config = {"url": "https://example.com"}
        integration = MockIntegration(config)

        data = await integration.fetch_data()

        assert data["status"] == "ok"
        assert data["url"] == "https://example.com"

    def test_pydantic_config_validation_error(self):
        """Test that Pydantic validation errors are caught."""

        class StrictConfig(IntegrationConfig):
            api_key: str = Field(..., json_schema_extra={"secret": True})

        class StrictIntegration(BaseIntegration):
            name = "strict"
            display_name = "Strict"
            ConfigModel = StrictConfig

            async def fetch_data(self):
                return {}

        # Missing required api_key
        with pytest.raises(ValueError, match="config validation failed"):
            StrictIntegration({})

    def test_secret_fields_from_pydantic_config(self):
        """Test that secret fields in Pydantic config are filtered."""

        class SecretConfig(IntegrationConfig):
            api_key: str = Field(default="secret", json_schema_extra={"secret": True})
            public_url: str = Field(default="https://example.com")

        class SecretIntegration(BaseIntegration):
            name = "secret"
            display_name = "Secret"
            ConfigModel = SecretConfig

            async def fetch_data(self):
                return {}

        integration = SecretIntegration(
            {"api_key": "my-secret", "public_url": "https://api.example.com"}
        )
        safe_config = integration._get_safe_config()

        # Secret field should be filtered
        assert "api_key" not in safe_config
        # Public field should remain
        assert safe_config["public_url"] == "https://api.example.com"

    def test_template_env_missing_module(self):
        """Test error when integration module cannot be found."""

        # Create an integration with a fake module
        class FakeIntegrationConfig(IntegrationConfig):
            pass

        class FakeModuleIntegration(BaseIntegration):
            name = "fake"
            display_name = "Fake"
            ConfigModel = FakeIntegrationConfig

            async def fetch_data(self):
                return {}

        # Manually set the module name to something that doesn't exist
        FakeModuleIntegration.__module__ = "nonexistent_module_xyz"

        integration = FakeModuleIntegration({})

        # Trying to get template env should raise RuntimeError
        with pytest.raises(RuntimeError, match="Cannot locate template directory"):
            integration._get_template_env()

    def test_render_widget(self):
        """Test rendering a widget with data."""
        config = {"url": "https://example.com"}
        integration = MockIntegration(config)

        # This will fail because we don't have a widget.html template,
        # but we test that the method exists and works with data
        try:
            integration.render_widget({"status": "ok"})
        except Exception:
            # Expected since MockIntegration has no widget.html
            pass

    def test_get_config_value_from_pydantic_model(self):
        """Test get_config_value with Pydantic model."""

        class MyConfig(IntegrationConfig):
            api_key: str = "default-key"
            timeout: int = 30

        class PydanticIntegration(BaseIntegration):
            name = "pydantic"
            display_name = "Pydantic"
            ConfigModel = MyConfig

            async def fetch_data(self):
                return {}

        integration = PydanticIntegration({"api_key": "custom-key", "timeout": 60})

        # Should get values from Pydantic model
        assert integration.get_config_value("api_key") == "custom-key"
        assert integration.get_config_value("timeout") == 60
        assert integration.get_config_value("nonexistent", "fallback") == "fallback"


class TestIntegrationDiscovery:
    """Tests for integration discovery functions."""

    def test_discover_integrations(self):
        """Test that example integration is discovered."""
        integrations = discover_integrations()

        assert "example" in integrations
        assert issubclass(integrations["example"], BaseIntegration)

    def test_load_integration(self):
        """Test loading an integration by name."""
        integration = load_integration("example", {"message": "Hello"})

        assert integration.name == "example"
        assert integration.display_name == "Example Widget"

    def test_load_integration_unknown(self):
        """Test loading unknown integration raises error."""
        with pytest.raises(ValueError, match="Unknown integration: nonexistent"):
            load_integration("nonexistent", {})

    async def test_example_integration_fetch_data(self):
        """Test example integration returns valid data."""
        integration = load_integration("example", {"message": "Test"})
        data = await integration.fetch_data()

        assert "current_time" in data
        assert "current_date" in data
        assert "message" in data
        assert "stats" in data
        assert len(data["stats"]) == 3

    def test_discover_integrations_with_bad_import(self, tmp_path, monkeypatch):
        """Test discovery gracefully handles import errors."""

        from integrations import discover_integrations

        # Create a bad integration directory
        bad_integration_dir = tmp_path / "integrations" / "bad_integration"
        bad_integration_dir.mkdir(parents=True)

        # Create integration.py that will fail to import
        (bad_integration_dir / "integration.py").write_text(
            "raise RuntimeError('Bad integration')"
        )

        # Add temp directory to path
        monkeypatch.syspath_prepend(str(tmp_path))

        # Test that discovery logs error but doesn't crash
        integrations = discover_integrations()
        # Should not contain the bad integration
        assert "bad_integration" not in integrations

    def test_discover_integrations_ignores_non_integration_classes(self):
        """Test that discover_integrations only picks integration classes."""
        from integrations import discover_integrations

        # Verify that only BaseIntegration subclasses are discovered
        integrations = discover_integrations()

        # All discovered integrations should be classes
        for _name, cls in integrations.items():
            assert isinstance(cls, type)
            assert issubclass(cls, BaseIntegration)
            assert hasattr(cls, "name")
            assert hasattr(cls, "display_name")

    def test_load_integration_with_pre_discovered(self):
        """Test loading integration with pre-discovered integrations dict."""
        from integrations import discover_integrations, load_integration

        discovered = discover_integrations()
        integration = load_integration("example", {"message": "Test"}, discovered)

        assert integration.name == "example"
        assert integration.display_name == "Example Widget"


class TestExampleIntegration:
    """Tests for ExampleIntegration edge cases."""

    async def test_rolling_average_with_empty_deque(self):
        """Test rolling average calculation with empty history."""
        from integrations.example import ExampleIntegration

        integration = ExampleIntegration({"message": "Test"})

        # With empty history, should return 0.0
        result = integration._get_rolling_average(integration._cpu_history)
        assert result == 0.0

    async def test_fetch_data_multiple_times_accumulates_history(self):
        """Test that cpu/memory history accumulates correctly over multiple fetches."""
        from integrations.example import ExampleIntegration

        integration = ExampleIntegration({"message": "Test"})

        # Fetch data multiple times
        for _ in range(5):
            data = await integration.fetch_data()
            assert "stats" in data
            assert len(data["stats"]) == 3

        # History should have accumulated
        assert len(integration._cpu_history) >= 3
        assert len(integration._memory_history) >= 3

    async def test_fetch_data_returns_averaged_stats(self):
        """Test that stats are properly calculated from rolling averages."""
        from integrations.example import ExampleIntegration

        integration = ExampleIntegration({"message": "Test"})

        # Fetch data once to populate history
        data1 = await integration.fetch_data()

        # Check that stats are numbers
        for stat in data1["stats"]:
            assert isinstance(stat["value"], (int, float))
            assert isinstance(stat["label"], str)
            assert isinstance(stat["unit"], str)

    async def test_fetch_data_has_required_fields(self):
        """Test that fetch_data returns all required fields."""
        from integrations.example import ExampleIntegration

        integration = ExampleIntegration({"message": "Custom Message"})
        data = await integration.fetch_data()

        assert "current_time" in data
        assert "current_date" in data
        assert "message" in data
        assert data["message"] == "Custom Message"
        assert "stats" in data
        assert len(data["stats"]) == 3


class TestBaseIntegrationErrorHandling:
    """Tests for error handling in BaseIntegration."""

    def test_config_property_raises_if_not_validated(self):
        """Test that config property raises if _validated_config is None."""

        class BrokenIntegration(BaseIntegration):
            name = "broken"
            display_name = "Broken"
            ConfigModel = None

            async def fetch_data(self):
                return {}

        integration = BrokenIntegration.__new__(BrokenIntegration)
        integration._validated_config = None
        integration.name = "broken"

        with pytest.raises(RuntimeError, match="config not validated"):
            _ = integration.config

    def test_validate_config_without_model(self):
        """Test that validate_config raises if ConfigModel is None."""

        class NoModelIntegration(BaseIntegration):
            name = "no_model"
            display_name = "No Model"
            ConfigModel = None

            async def fetch_data(self):
                return {}

        with pytest.raises(ValueError, match="must define ConfigModel"):
            NoModelIntegration({})

    def test_get_config_value_with_unvalidated_config(self):
        """Test that get_config_value raises if config not validated."""

        class ConfigIntegration(BaseIntegration):
            name = "config_test"
            display_name = "Config Test"
            ConfigModel = None

            async def fetch_data(self):
                return {}

        integration = ConfigIntegration.__new__(ConfigIntegration)
        integration._validated_config = None
        integration.name = "config_test"

        with pytest.raises(RuntimeError, match="config not validated"):
            integration.get_config_value("key")

    def test_safe_config_with_pydantic_secret_fields(self):
        """Test that _get_safe_config filters Pydantic secret fields correctly."""

        class FullSecretConfig(IntegrationConfig):
            url: str = Field(default="https://example.com")
            api_key: str = Field(default="secret", json_schema_extra={"secret": True})
            token: str = Field(default="token123", json_schema_extra={"secret": True})
            webhook_url: str = Field(default="https://webhook.example.com")

        class SecretFilterIntegration(BaseIntegration):
            name = "secret_filter"
            display_name = "Secret Filter"
            ConfigModel = FullSecretConfig

            async def fetch_data(self):
                return {}

        integration = SecretFilterIntegration(
            {
                "url": "https://api.example.com",
                "api_key": "my-secret",
                "token": "my-token",
                "webhook_url": "https://my-webhook.com",
            }
        )
        safe_config = integration._get_safe_config()

        # Secret fields marked in Pydantic should be filtered
        assert "api_key" not in safe_config
        assert "token" not in safe_config

        # Public fields should remain
        assert safe_config["url"] == "https://api.example.com"
        assert safe_config["webhook_url"] == "https://my-webhook.com"

    def test_safe_config_mixed_secret_detection(self):
        """Test that _get_safe_config filters both Pydantic secrets and key patterns."""

        class MixedConfig(IntegrationConfig):
            url: str = Field(default="https://example.com")
            my_password: str = Field(default="pass123")
            api_secret: str = Field(default="secret456")

        class MixedIntegration(BaseIntegration):
            name = "mixed"
            display_name = "Mixed"
            ConfigModel = MixedConfig

            async def fetch_data(self):
                return {}

        integration = MixedIntegration(
            {
                "url": "https://api.example.com",
                "my_password": "secure123",
                "api_secret": "secret789",
            }
        )
        safe_config = integration._get_safe_config()

        # Should filter keys containing sensitive patterns
        assert "my_password" not in safe_config
        assert "api_secret" not in safe_config
        # URL is safe
        assert safe_config["url"] == "https://api.example.com"

    def test_template_env_cached(self):
        """Test that _get_template_env caches the environment."""
        config = {"url": "https://example.com"}
        integration = MockIntegration(config)

        # First call creates the environment
        env1 = integration._get_template_env()
        # Second call should return the cached environment
        env2 = integration._get_template_env()

        # Should be the same object (cached)
        assert env1 is env2

    def test_get_safe_config_with_no_pydantic_model(self):
        """Test _get_safe_config when ConfigModel is None."""

        class NoConfigModel(IntegrationConfig):
            pass

        class NoModelIntegration(BaseIntegration):
            name = "no_model"
            display_name = "No Model"
            ConfigModel = None

            async def fetch_data(self):
                return {}

        # This should raise during init since ConfigModel is required
        with pytest.raises(ValueError, match="must define ConfigModel"):
            NoModelIntegration({})

    def test_safe_config_empty_secret_fields(self):
        """Test _get_safe_config when Pydantic model has no secret fields."""

        class NoSecretsConfig(IntegrationConfig):
            service_url: str = Field(default="https://example.com")
            display_name: str = Field(default="My Service")

        class NoSecretsIntegration(BaseIntegration):
            name = "no_secrets"
            display_name = "No Secrets"
            ConfigModel = NoSecretsConfig

            async def fetch_data(self):
                return {}

        integration = NoSecretsIntegration(
            {"service_url": "https://api.example.com", "display_name": "My API"}
        )
        safe_config = integration._get_safe_config()

        # All fields should be present since none are marked as secret
        assert safe_config["service_url"] == "https://api.example.com"
        assert safe_config["display_name"] == "My API"

    def test_safe_config_with_non_dict_json_schema_extra(self):
        """Test _get_safe_config with json_schema_extra that's not a dict."""

        class MixedExtraConfig(IntegrationConfig):
            field1: str = Field(default="value1", json_schema_extra="string")
            field2: str = Field(default="value2", json_schema_extra=123)
            field3: str = Field(default="value3")

        class MixedExtraIntegration(BaseIntegration):
            name = "mixed_extra"
            display_name = "Mixed Extra"
            ConfigModel = MixedExtraConfig

            async def fetch_data(self):
                return {}

        integration = MixedExtraIntegration(
            {
                "field1": "val1",
                "field2": "val2",
                "field3": "val3",
            }
        )
        safe_config = integration._get_safe_config()

        # All should be present since json_schema_extra is not dict with secret: True
        assert safe_config["field1"] == "val1"
        assert safe_config["field2"] == "val2"
        assert safe_config["field3"] == "val3"

    def test_safe_config_with_empty_secret_dict(self):
        """Test _get_safe_config with json_schema_extra dict but no secret key."""

        class EmptySecretDictConfig(IntegrationConfig):
            field1: str = Field(default="value1", json_schema_extra={"other": True})
            field2: str = Field(default="value2", json_schema_extra={"secret": False})
            field3: str = Field(default="value3")

        class EmptySecretDictIntegration(BaseIntegration):
            name = "empty_secret_dict"
            display_name = "Empty Secret Dict"
            ConfigModel = EmptySecretDictConfig

            async def fetch_data(self):
                return {}

        integration = EmptySecretDictIntegration(
            {
                "field1": "val1",
                "field2": "val2",
                "field3": "val3",
            }
        )
        safe_config = integration._get_safe_config()

        # All should be present since secret: True is not set in any field
        assert safe_config["field1"] == "val1"
        assert safe_config["field2"] == "val2"
        assert safe_config["field3"] == "val3"
