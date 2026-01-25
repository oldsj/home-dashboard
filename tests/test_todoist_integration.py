"""Tests for Todoist integration."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from integrations import load_integration
from integrations.todoist.integration import TodoistConfig, TodoistIntegration


class TestTodoistConfig:
    """Tests for TodoistConfig model."""

    def test_todoist_config_with_required_fields(self):
        """Test TodoistConfig with all required fields."""
        config = TodoistConfig(api_token="test-token-123")

        assert config.api_token == "test-token-123"
        assert config.max_tasks == 10  # Default value
        assert config.refresh_rate == 60  # Default value

    def test_todoist_config_with_custom_values(self):
        """Test TodoistConfig with custom values."""
        config = TodoistConfig(
            api_token="custom-token",
            max_tasks=20,
            refresh_rate=120,
        )

        assert config.api_token == "custom-token"
        assert config.max_tasks == 20
        assert config.refresh_rate == 120

    def test_todoist_config_api_token_marked_as_secret(self):
        """Test that api_token is marked as secret in json_schema_extra."""
        # Get field info from Pydantic model
        field_info = TodoistConfig.model_fields["api_token"]
        json_schema_extra = field_info.json_schema_extra or {}

        assert json_schema_extra.get("secret") is True


def create_mock_task(
    task_id: str,
    content: str,
    due_date: str | None = None,
    priority: int = 1,
    project_id: str = "project1",
):
    """Helper to create a mock Todoist task."""
    task = MagicMock()
    task.id = task_id
    task.content = content
    task.description = ""
    task.priority = priority
    task.labels = []
    task.project_id = project_id

    if due_date:
        from datetime import datetime

        task.due = MagicMock()
        # Parse the string to a date object to match real API behavior
        task.due.date = datetime.fromisoformat(due_date).date()
        task.due.datetime = None
        task.due.string = due_date
        task.due.is_recurring = False
        task.due.timezone = None
    else:
        task.due = None

    return task


def create_mock_project(project_id: str, name: str):
    """Helper to create a mock Todoist project."""
    project = MagicMock()
    project.id = project_id
    project.name = name
    return project


class TestTodoistIntegration:
    """Tests for TodoistIntegration class."""

    def test_init_with_valid_config(self):
        """Test initialization with valid configuration."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        assert integration.name == "todoist"
        assert integration.display_name == "Todoist"
        assert integration.refresh_interval == 60
        assert integration.get_config_value("api_token") == "test-token-123"
        assert integration.get_config_value("max_tasks") == 10
        assert integration._api is None

    def test_init_with_custom_max_tasks(self):
        """Test initialization with custom max_tasks."""
        config = {"api_token": "test-token-123", "max_tasks": 25}
        integration = TodoistIntegration(config)

        assert integration.get_config_value("max_tasks") == 25

    def test_init_missing_required_api_token(self):
        """Test initialization fails without api_token."""
        config = {"max_tasks": 10}

        with pytest.raises(ValueError, match="config validation failed"):
            TodoistIntegration(config)

    async def test_fetch_data_returns_valid_structure(self, monkeypatch):
        """Test fetch_data returns expected data structure."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        # Mock the API client
        mock_api = AsyncMock()
        today_str = datetime.now().date().isoformat()
        mock_api.get_tasks.return_value = [
            create_mock_task("1", "Task 1", today_str),
            create_mock_task("2", "Task 2", "2025-01-01"),  # Overdue
        ]
        mock_api.get_projects.return_value = [
            create_mock_project("project1", "Project 1")
        ]

        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        # Verify all expected fields are present
        assert "today_tasks" in data
        assert "overdue_tasks" in data
        assert "upcoming_count" in data
        assert "completed_today" in data
        assert "total_tasks" in data
        assert "projects_count" in data
        assert "timestamp" in data
        assert "max_tasks" in data

        # Verify data types
        assert isinstance(data["today_tasks"], list)
        assert isinstance(data["overdue_tasks"], list)
        assert isinstance(data["upcoming_count"], int)
        assert isinstance(data["completed_today"], int)
        assert isinstance(data["total_tasks"], int)
        assert isinstance(data["projects_count"], int)
        assert isinstance(data["max_tasks"], int)
        assert isinstance(data["timestamp"], str)

    async def test_fetch_data_respects_max_tasks_config(self, monkeypatch):
        """Test that fetch_data respects max_tasks configuration."""
        config = {"api_token": "test-token-123", "max_tasks": 5}
        integration = TodoistIntegration(config)

        # Mock the API client
        mock_api = AsyncMock()
        mock_api.get_tasks.return_value = []
        mock_api.get_projects.return_value = []
        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        assert data["max_tasks"] == 5

    async def test_fetch_data_with_default_max_tasks(self, monkeypatch):
        """Test fetch_data with default max_tasks value."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        # Mock the API client
        mock_api = AsyncMock()
        mock_api.get_tasks.return_value = []
        mock_api.get_projects.return_value = []
        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        assert data["max_tasks"] == 10  # Default value

    def test_api_token_filtered_from_safe_config(self):
        """Test that api_token is filtered from safe config."""
        config = {"api_token": "secret-token-123", "max_tasks": 15}
        integration = TodoistIntegration(config)

        safe_config = integration._get_safe_config()

        # api_token should be filtered (marked as secret in Pydantic model)
        assert "api_token" not in safe_config
        # max_tasks should be present
        assert safe_config["max_tasks"] == 15

    def test_load_integration_by_name(self):
        """Test loading Todoist integration by name."""
        integration = load_integration("todoist", {"api_token": "test-token"})

        assert isinstance(integration, TodoistIntegration)
        assert integration.name == "todoist"
        assert integration.display_name == "Todoist"

    async def test_fetch_data_error_handling(self, monkeypatch):
        """Test fetch_data handles errors gracefully."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        # Mock the API client to raise an error
        mock_api = AsyncMock()
        mock_api.get_tasks.side_effect = Exception("API error")
        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        # Should re-raise the exception
        with pytest.raises(Exception, match="API error"):
            await integration.fetch_data()

    def test_integration_class_attributes(self):
        """Test TodoistIntegration class has correct attributes."""
        assert TodoistIntegration.name == "todoist"
        assert TodoistIntegration.display_name == "Todoist"
        assert TodoistIntegration.refresh_interval == 60
        assert TodoistIntegration.ConfigModel == TodoistConfig

    def test_config_validation_with_extra_fields(self):
        """Test config validation ignores extra fields."""
        config = {
            "api_token": "test-token-123",
            "max_tasks": 15,
            "extra_field": "ignored",
        }
        integration = TodoistIntegration(config)

        # Should initialize successfully
        assert integration.get_config_value("api_token") == "test-token-123"
        assert integration.get_config_value("max_tasks") == 15

    async def test_multiple_fetch_calls(self, monkeypatch):
        """Test that fetch_data can be called multiple times."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        # Mock the API client
        mock_api = AsyncMock()
        mock_api.get_tasks.return_value = []
        mock_api.get_projects.return_value = []
        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data1 = await integration.fetch_data()
        data2 = await integration.fetch_data()

        # Both calls should succeed and return valid data
        assert data1 is not None
        assert data2 is not None
        assert "today_tasks" in data1
        assert "today_tasks" in data2
        # API should have been called twice
        assert mock_api.get_tasks.call_count == 2

    async def test_fetch_data_exception_logging(self, monkeypatch):
        """Test that fetch_data logs and re-raises exceptions."""
        from integrations.todoist.integration import TodoistIntegration

        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        # Capture log messages
        log_messages = []

        def mock_error(msg):
            log_messages.append(msg)

        # Patch logger.error to capture messages
        monkeypatch.setattr("integrations.todoist.integration.logger.error", mock_error)

        # Mock API to raise an error
        mock_api = AsyncMock()
        mock_api.get_tasks.side_effect = RuntimeError("Simulated error")
        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        # fetch_data should log the error and re-raise
        with pytest.raises(RuntimeError, match="Simulated error"):
            await integration.fetch_data()

        # Verify error was logged
        assert len(log_messages) == 1
        assert "Error fetching Todoist data" in log_messages[0]
        assert "Simulated error" in log_messages[0]

    def test_get_api_creates_client(self):
        """Test that _get_api creates a Todoist API client."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        assert integration._api is None
        api = integration._get_api()
        assert api is not None
        assert integration._api is api

        # Subsequent calls return the same instance
        api2 = integration._get_api()
        assert api2 is api

    async def test_fetch_data_categorizes_tasks_correctly(self, monkeypatch):
        """Test that tasks are categorized into today, overdue, and upcoming."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        today = datetime.now().date()
        yesterday = (today - timedelta(days=1)).isoformat()
        today_str = today.isoformat()
        tomorrow = (today + timedelta(days=1)).isoformat()

        # Mock the API client
        mock_api = AsyncMock()
        mock_api.get_tasks.return_value = [
            create_mock_task("1", "Overdue task", yesterday, priority=4),
            create_mock_task("2", "Today task", today_str, priority=3),
            create_mock_task("3", "Upcoming task", tomorrow, priority=1),
            create_mock_task("4", "No due date", None),
        ]
        mock_api.get_projects.return_value = [
            create_mock_project("project1", "Project 1")
        ]

        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        # Verify categorization
        assert len(data["overdue_tasks"]) == 1
        assert data["overdue_tasks"][0]["content"] == "Overdue task"

        assert len(data["today_tasks"]) == 1
        assert data["today_tasks"][0]["content"] == "Today task"

        assert data["upcoming_count"] == 2  # Tomorrow task + no due date task
        assert data["total_tasks"] == 4
        assert data["projects_count"] == 1

    async def test_fetch_data_sorts_by_priority(self, monkeypatch):
        """Test that tasks are sorted by priority (highest first)."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        today_str = datetime.now().date().isoformat()

        # Mock the API client with multiple today tasks
        mock_api = AsyncMock()
        mock_api.get_tasks.return_value = [
            create_mock_task("1", "Low priority", today_str, priority=1),
            create_mock_task("2", "High priority", today_str, priority=4),
            create_mock_task("3", "Medium priority", today_str, priority=2),
        ]
        mock_api.get_projects.return_value = []

        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        # Verify tasks are sorted by priority (highest first)
        assert len(data["today_tasks"]) == 3
        assert data["today_tasks"][0]["priority"] == 4
        assert data["today_tasks"][1]["priority"] == 2
        assert data["today_tasks"][2]["priority"] == 1

    async def test_fetch_data_includes_project_names(self, monkeypatch):
        """Test that tasks include project names from project map."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        today_str = datetime.now().date().isoformat()

        # Mock the API client
        mock_api = AsyncMock()
        mock_api.get_tasks.return_value = [
            create_mock_task("1", "Task 1", today_str, project_id="proj1"),
            create_mock_task("2", "Task 2", today_str, project_id="proj2"),
        ]
        mock_api.get_projects.return_value = [
            create_mock_project("proj1", "Work"),
            create_mock_project("proj2", "Personal"),
        ]

        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        # Verify project names are included
        assert data["today_tasks"][0]["project_name"] == "Work"
        assert data["today_tasks"][1]["project_name"] == "Personal"

    async def test_fetch_data_with_due_but_no_date(self, monkeypatch):
        """Test task with due object but no date (edge case)."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        # Create a task with due but no date
        task = MagicMock()
        task.id = "1"
        task.content = "Task with due but no date"
        task.description = ""
        task.priority = 1
        task.labels = []
        task.project_id = "proj1"
        task.due = MagicMock()
        task.due.date = None  # Has due object but no date
        task.due.datetime = None
        task.due.string = "someday"

        # Mock the API client
        mock_api = AsyncMock()
        mock_api.get_tasks.return_value = [task]
        mock_api.get_projects.return_value = [create_mock_project("proj1", "Inbox")]

        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        # Task should be categorized as upcoming (no specific date)
        assert len(data["today_tasks"]) == 0
        assert len(data["overdue_tasks"]) == 0
        assert data["upcoming_count"] == 1

    async def test_fetch_data_with_datetime_due_date(self, monkeypatch):
        """Test task with datetime object as due date (instead of date object)."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        today_str = datetime.now().date().isoformat()

        # Create a task with datetime as due date
        task = MagicMock()
        task.id = "1"
        task.content = "Task with datetime due"
        task.description = ""
        task.priority = 1
        task.labels = []
        task.project_id = "proj1"
        task.due = MagicMock()
        # Use datetime object instead of date object
        task.due.date = datetime.now()  # datetime, not date
        task.due.datetime = datetime.now()
        task.due.string = today_str
        task.due.is_recurring = False
        task.due.timezone = None

        # Mock the API client
        mock_api = AsyncMock()
        mock_api.get_tasks.return_value = [task]
        mock_api.get_projects.return_value = [create_mock_project("proj1", "Inbox")]

        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        # Task should be categorized as today
        assert len(data["today_tasks"]) == 1
        assert data["today_tasks"][0]["content"] == "Task with datetime due"

    async def test_fetch_data_with_async_generators(self, monkeypatch):
        """Test fetch_data handles async generators from real API."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        today_str = datetime.now().date().isoformat()

        # Create async generator functions to simulate real API behavior
        async def tasks_async_gen():
            yield [create_mock_task("1", "Task 1", today_str)]

        async def projects_async_gen():
            yield [create_mock_project("proj1", "Project 1")]

        # Mock the API client with async generators
        mock_api = AsyncMock()
        mock_api.get_tasks = AsyncMock(return_value=tasks_async_gen())
        mock_api.get_projects = AsyncMock(return_value=projects_async_gen())

        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        # Verify async generator path works correctly
        assert len(data["today_tasks"]) == 1
        assert data["today_tasks"][0]["content"] == "Task 1"
        assert data["projects_count"] == 1
