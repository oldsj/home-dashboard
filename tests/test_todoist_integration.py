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

    def test_todoist_config_with_work_parent_project(self):
        """Test TodoistConfig with work_parent_project configuration."""
        config = TodoistConfig(
            api_token="test-token",
            work_parent_project="Work",
        )

        assert config.work_parent_project == "Work"

    def test_todoist_config_work_parent_project_default(self):
        """Test TodoistConfig work_parent_project defaults to empty string."""
        config = TodoistConfig(api_token="test-token")

        assert config.work_parent_project == ""


def create_mock_task(
    task_id: str,
    content: str,
    due_date: str | None = None,
    priority: int = 1,
    project_id: str = "project1",
    duration: dict | None = None,
):
    """Helper to create a mock Todoist task."""
    task = MagicMock()
    task.id = task_id
    task.content = content
    task.description = ""
    task.priority = priority
    task.labels = []
    task.project_id = project_id
    task.duration = duration

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


def create_mock_project(project_id: str, name: str, parent_id: str | None = None):
    """Helper to create a mock Todoist project."""
    project = MagicMock()
    project.id = project_id
    project.name = name
    project.parent_id = parent_id
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

    def test_poll_interval_config(self):
        """Test poll_interval configuration option."""
        config = {"api_token": "test-token", "poll_interval": 10}
        integration = TodoistIntegration(config)

        assert integration.get_config_value("poll_interval") == 10

    def test_poll_interval_default(self):
        """Test poll_interval defaults to 5 seconds."""
        config = {"api_token": "test-token"}
        integration = TodoistIntegration(config)

        assert integration.get_config_value("poll_interval") == 5


class TestTodoistEventStream:
    """Tests for Todoist event stream (Sync API) functionality."""

    async def test_check_for_changes_full_sync(self, monkeypatch):
        """Test _check_for_changes on initial full sync."""
        import httpx

        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        # Mock httpx response for full sync
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sync_token": "new-token-123",
            "full_sync": True,
            "items": [{"id": "1", "content": "Task 1"}],
            "projects": [],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        has_changes, new_token = await integration._check_for_changes(mock_client)

        assert has_changes is True
        assert new_token == "new-token-123"
        mock_client.post.assert_called_once()

    async def test_check_for_changes_incremental_with_items(self, monkeypatch):
        """Test _check_for_changes detects item changes in incremental sync."""
        import httpx

        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)
        integration._sync_token = "existing-token"

        # Mock httpx response with item changes
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sync_token": "new-token-456",
            "full_sync": False,
            "items": [{"id": "2", "content": "New task"}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        has_changes, new_token = await integration._check_for_changes(mock_client)

        assert has_changes is True
        assert new_token == "new-token-456"

    async def test_check_for_changes_incremental_with_projects(self, monkeypatch):
        """Test _check_for_changes detects project changes."""
        import httpx

        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)
        integration._sync_token = "existing-token"

        # Mock httpx response with project changes
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sync_token": "new-token-789",
            "full_sync": False,
            "projects": [{"id": "p1", "name": "New project"}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        has_changes, new_token = await integration._check_for_changes(mock_client)

        assert has_changes is True
        assert new_token == "new-token-789"

    async def test_check_for_changes_no_changes(self, monkeypatch):
        """Test _check_for_changes when no changes occurred."""
        import httpx

        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)
        integration._sync_token = "existing-token"

        # Mock httpx response with no changes
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sync_token": "existing-token",
            "full_sync": False,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        has_changes, new_token = await integration._check_for_changes(mock_client)

        assert has_changes is False
        assert new_token == "existing-token"

    async def test_start_event_stream_yields_initial_data(self, monkeypatch):
        """Test start_event_stream yields initial data on startup."""
        import asyncio

        import httpx

        config = {"api_token": "test-token-123", "poll_interval": 1}
        integration = TodoistIntegration(config)

        # Mock fetch_data
        mock_data = {"today_tasks": [], "timestamp": "2024-01-01T00:00:00"}
        monkeypatch.setattr(
            integration, "fetch_data", AsyncMock(return_value=mock_data)
        )

        # Mock _check_for_changes to return changes on first call, then cancel
        call_count = 0

        async def mock_check_for_changes(client):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True, "new-token"
            # Cancel after first iteration to prevent infinite loop
            raise asyncio.CancelledError()

        monkeypatch.setattr(integration, "_check_for_changes", mock_check_for_changes)

        # Mock httpx.AsyncClient
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(httpx, "AsyncClient", lambda: mock_client)

        # Collect yielded data
        yielded_data = []
        try:
            async for data in integration.start_event_stream():
                yielded_data.append(data)
        except asyncio.CancelledError:
            pass

        # Should have yielded initial data
        assert len(yielded_data) >= 1
        assert yielded_data[0] == mock_data

    async def test_start_event_stream_only_yields_on_changes(self, monkeypatch):
        """Test start_event_stream only yields when changes are detected."""
        import asyncio

        import httpx

        config = {"api_token": "test-token-123", "poll_interval": 1}
        integration = TodoistIntegration(config)

        # Mock asyncio.sleep to avoid actual waiting
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        # Track fetch_data calls
        fetch_call_count = 0
        mock_data = {"today_tasks": [], "timestamp": "2024-01-01"}

        async def mock_fetch_data():
            nonlocal fetch_call_count
            fetch_call_count += 1
            return mock_data

        monkeypatch.setattr(integration, "fetch_data", mock_fetch_data)

        # Mock _check_for_changes: True, False, False, True, then cancel
        check_results = [
            (True, "token1"),  # Initial - has changes
            (False, "token1"),  # No changes
            (False, "token1"),  # No changes
            (True, "token2"),  # Has changes
        ]
        check_index = 0

        async def mock_check_for_changes(client):
            nonlocal check_index
            if check_index >= len(check_results):
                raise asyncio.CancelledError()
            result = check_results[check_index]
            check_index += 1
            return result

        monkeypatch.setattr(integration, "_check_for_changes", mock_check_for_changes)

        # Mock httpx.AsyncClient
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(httpx, "AsyncClient", lambda: mock_client)

        # Collect yielded data
        yielded_data = []
        try:
            async for data in integration.start_event_stream():
                yielded_data.append(data)
        except asyncio.CancelledError:
            pass

        # Should have yielded only twice (on changes)
        assert len(yielded_data) == 2
        # fetch_data should have been called only twice (when changes detected)
        assert fetch_call_count == 2

    async def test_start_event_stream_handles_http_error(self, monkeypatch):
        """Test start_event_stream handles HTTP errors gracefully."""
        import asyncio

        import httpx

        config = {"api_token": "test-token-123", "poll_interval": 1}
        integration = TodoistIntegration(config)

        # Mock asyncio.sleep to avoid actual waiting
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        mock_data = {"today_tasks": [], "timestamp": "2024-01-01"}
        monkeypatch.setattr(
            integration, "fetch_data", AsyncMock(return_value=mock_data)
        )

        # Mock _check_for_changes: success, HTTP error, then cancel
        call_count = 0

        async def mock_check_for_changes(client):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True, "token1"  # Initial success
            if call_count == 2:
                # Simulate HTTP error
                mock_response = MagicMock()
                mock_response.status_code = 500
                raise httpx.HTTPStatusError(
                    "Server error", request=MagicMock(), response=mock_response
                )
            if call_count == 3:
                return True, "token2"  # Recovery
            raise asyncio.CancelledError()

        monkeypatch.setattr(integration, "_check_for_changes", mock_check_for_changes)

        # Mock httpx.AsyncClient
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(httpx, "AsyncClient", lambda: mock_client)

        # Collect yielded data
        yielded_data = []
        try:
            async for data in integration.start_event_stream():
                yielded_data.append(data)
        except asyncio.CancelledError:
            pass

        # Should have recovered and yielded data
        assert len(yielded_data) >= 1

    async def test_start_event_stream_auth_error_backoff(self, monkeypatch):
        """Test start_event_stream backs off on auth errors."""
        import asyncio

        import httpx

        config = {"api_token": "test-token-123", "poll_interval": 1}
        integration = TodoistIntegration(config)

        mock_data = {"today_tasks": [], "timestamp": "2024-01-01"}
        monkeypatch.setattr(
            integration, "fetch_data", AsyncMock(return_value=mock_data)
        )

        # Track sleep calls to verify backoff
        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 2:
                raise asyncio.CancelledError()

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        # Mock _check_for_changes: success, then 401 error
        call_count = 0

        async def mock_check_for_changes(client):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True, "token1"  # Initial success
            # Simulate auth error
            mock_response = MagicMock()
            mock_response.status_code = 401
            raise httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_response
            )

        monkeypatch.setattr(integration, "_check_for_changes", mock_check_for_changes)

        # Mock httpx.AsyncClient
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(httpx, "AsyncClient", lambda: mock_client)

        try:
            async for _ in integration.start_event_stream():
                pass
        except asyncio.CancelledError:
            pass

        # Should have backed off with 60 second sleep on auth error
        assert 60 in sleep_calls

    async def test_start_event_stream_initial_error_raises(self, monkeypatch):
        """Test start_event_stream raises on initial sync failure."""
        import httpx

        config = {"api_token": "test-token-123", "poll_interval": 1}
        integration = TodoistIntegration(config)

        # Mock _check_for_changes to fail on first call
        async def mock_check_for_changes(client):
            raise RuntimeError("Initial sync failed")

        monkeypatch.setattr(integration, "_check_for_changes", mock_check_for_changes)

        # Mock httpx.AsyncClient
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(httpx, "AsyncClient", lambda: mock_client)

        # Should raise on initial failure
        with pytest.raises(RuntimeError, match="Initial sync failed"):
            async for _ in integration.start_event_stream():
                pass

    async def test_start_event_stream_handles_generic_exception(self, monkeypatch):
        """Test start_event_stream handles generic exceptions gracefully."""
        import asyncio

        import httpx

        config = {"api_token": "test-token-123", "poll_interval": 1}
        integration = TodoistIntegration(config)

        # Mock asyncio.sleep to avoid actual waiting
        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 2:
                raise asyncio.CancelledError()

        monkeypatch.setattr(asyncio, "sleep", mock_sleep)

        mock_data = {"today_tasks": [], "timestamp": "2024-01-01"}
        monkeypatch.setattr(
            integration, "fetch_data", AsyncMock(return_value=mock_data)
        )

        # Mock _check_for_changes: success, generic exception, then cancel
        call_count = 0

        async def mock_check_for_changes(client):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True, "token1"  # Initial success
            # Simulate generic exception (not HTTPStatusError)
            raise ValueError("Unexpected error")

        monkeypatch.setattr(integration, "_check_for_changes", mock_check_for_changes)

        # Mock httpx.AsyncClient
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr(httpx, "AsyncClient", lambda: mock_client)

        # Collect yielded data
        yielded_data = []
        try:
            async for data in integration.start_event_stream():
                yielded_data.append(data)
        except asyncio.CancelledError:
            pass

        # Should have yielded initial data and then handled the error
        assert len(yielded_data) >= 1
        # Should have slept with poll_interval after generic error
        assert 1 in sleep_calls


class TestTodoistCompletedTasks:
    """Tests for completed tasks functionality."""

    async def test_fetch_completed_with_billing_successful(self, monkeypatch):
        """Test _fetch_completed_with_billing successfully fetches and processes tasks."""
        import httpx

        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        # Mock projects for project name mapping
        mock_api = AsyncMock()
        mock_api.get_projects.return_value = [
            create_mock_project("proj1", "Work"),
            create_mock_project("proj2", "Personal"),
        ]
        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        # Build project map
        projects = await mock_api.get_projects()
        project_map = {p.id: p.name for p in projects}

        # Mock httpx response with completed tasks (API v1 format)
        today = datetime.now().date()
        yesterday = (today - timedelta(days=1)).isoformat()
        today_str = today.isoformat()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "task1",
                    "content": "Completed today 1",
                    "project_id": "proj1",
                    "completed_at": f"{today_str}T10:00:00Z",
                    "duration": {"amount": 30, "unit": "minute"},
                },
                {
                    "id": "task2",
                    "content": "Completed today 2",
                    "project_id": "proj2",
                    "completed_at": f"{today_str}T14:30:00Z",
                    "duration": {"amount": 60, "unit": "minute"},
                },
                {
                    "id": "task3",
                    "content": "Completed yesterday",
                    "project_id": "proj1",
                    "completed_at": f"{yesterday}T12:00:00Z",
                    "duration": None,
                },
            ],
            "next_cursor": None,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        def mock_async_client_factory(*args, **kwargs):
            return mock_client

        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_factory)

        today_tasks, weekly_tasks, sparkline = (
            await integration._fetch_completed_with_billing(project_map)
        )

        # Verify today's tasks
        assert len(today_tasks) == 2
        # Should be sorted by completion time (most recent first)
        assert today_tasks[0]["content"] == "Completed today 2"
        assert today_tasks[0]["project_name"] == "Personal"
        assert today_tasks[1]["content"] == "Completed today 1"
        assert today_tasks[1]["project_name"] == "Work"

        # Verify sparkline
        assert sparkline["total"] == 3  # Total across all days
        assert sparkline["max"] >= 1
        assert len(sparkline["counts"]) == 7  # 7 days
        assert len(sparkline["bars"]) == 7

    async def test_fetch_completed_with_billing_with_missing_project(self, monkeypatch):
        """Test _fetch_completed_with_billing handles tasks with unknown project_id."""
        import httpx

        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        project_map = {"proj1": "Work"}  # Only one project

        today_str = datetime.now().date().isoformat()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "1",
                    "content": "Task with unknown project",
                    "project_id": "unknown_proj",
                    "completed_at": f"{today_str}T10:00:00Z",
                    "duration": None,
                }
            ],
            "next_cursor": None,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        def mock_async_client_factory(*args, **kwargs):
            return mock_client

        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_factory)

        today_tasks, weekly_tasks, sparkline = (
            await integration._fetch_completed_with_billing(project_map)
        )

        # Should handle unknown project gracefully
        assert len(today_tasks) == 1
        assert today_tasks[0]["project_name"] == ""  # Empty string for unknown project

    async def test_fetch_completed_with_billing_api_error(self, monkeypatch):
        """Test _fetch_completed_with_billing handles API errors gracefully."""
        import httpx

        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        project_map = {}

        # Mock httpx to raise an error
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=Exception("API error"))

        def mock_async_client_factory(*args, **kwargs):
            return mock_client

        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_factory)

        today_tasks, weekly_tasks, sparkline = (
            await integration._fetch_completed_with_billing(project_map)
        )

        # Should return empty data on error
        assert today_tasks == []
        assert sparkline["counts"] == [0] * 7
        assert sparkline["max"] == 0
        assert sparkline["total"] == 0
        assert sparkline["bars"] == "▁▁▁▁▁▁▁"

    async def test_fetch_completed_with_billing_empty_response(self, monkeypatch):
        """Test _fetch_completed_with_billing handles empty items list."""
        import httpx

        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        project_map = {}

        mock_response = MagicMock()
        mock_response.json.return_value = {"items": [], "next_cursor": None}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        def mock_async_client_factory(*args, **kwargs):
            return mock_client

        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_factory)

        today_tasks, weekly_tasks, sparkline = (
            await integration._fetch_completed_with_billing(project_map)
        )

        # Should return empty sparkline
        assert today_tasks == []
        assert sparkline["counts"] == [0] * 7
        assert sparkline["max"] == 0
        assert sparkline["total"] == 0

    def test_counts_to_sparkline_empty_list(self):
        """Test _counts_to_sparkline with empty list."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        result = integration._counts_to_sparkline([])

        assert result == ""

    def test_counts_to_sparkline_all_zeros(self):
        """Test _counts_to_sparkline with all zero counts."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        result = integration._counts_to_sparkline([0, 0, 0, 0, 0])

        assert result == "▁▁▁▁▁"

    def test_counts_to_sparkline_various_counts(self):
        """Test _counts_to_sparkline with various count values."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        # Test with a range of values
        counts = [0, 1, 2, 4, 8]
        result = integration._counts_to_sparkline(counts)

        # Should return 5 characters (one per count)
        assert len(result) == 5
        # All should be valid sparkline characters
        valid_chars = "▁▂▃▄▅▆▇█"
        assert all(c in valid_chars for c in result)
        # First should be lowest (0 maps to ▁)
        assert result[0] == "▁"
        # Last should be highest (8 maps to █)
        assert result[4] == "█"

    def test_counts_to_sparkline_single_value(self):
        """Test _counts_to_sparkline with single non-zero value."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        result = integration._counts_to_sparkline([5])

        # Single max value should map to highest bar
        assert result == "█"

    def test_counts_to_sparkline_equal_values(self):
        """Test _counts_to_sparkline with all equal non-zero values."""
        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        result = integration._counts_to_sparkline([3, 3, 3, 3])

        # All equal values should map to highest bar
        assert result == "████"

    async def test_fetch_completed_with_billing_empty_completed_at(self, monkeypatch):
        """Test _fetch_completed_with_billing skips items with empty completed_at."""
        import httpx

        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        project_map = {}

        today_str = datetime.now().date().isoformat()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "1",
                    "content": "Task without completed_at",
                    "project_id": "proj1",
                    "duration": None,
                    # No completed_at field
                },
                {
                    "id": "2",
                    "content": "Task with empty completed_at",
                    "project_id": "proj1",
                    "completed_at": "",  # Empty string
                    "duration": None,
                },
                {
                    "id": "3",
                    "content": "Valid task",
                    "project_id": "proj1",
                    "completed_at": f"{today_str}T10:00:00Z",
                    "duration": {"amount": 30, "unit": "minute"},
                },
            ],
            "next_cursor": None,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        def mock_async_client_factory(*args, **kwargs):
            return mock_client

        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_factory)

        today_tasks, weekly_tasks, sparkline = (
            await integration._fetch_completed_with_billing(project_map)
        )

        # Should only include the valid task
        assert len(today_tasks) == 1
        assert today_tasks[0]["content"] == "Valid task"
        assert sparkline["total"] == 1

    async def test_fetch_completed_with_billing_old_tasks_outside_window(
        self, monkeypatch
    ):
        """Test _fetch_completed_with_billing ignores tasks outside 7-day window."""
        import httpx

        config = {"api_token": "test-token-123"}
        integration = TodoistIntegration(config)

        project_map = {}

        today = datetime.now().date()
        today_str = today.isoformat()
        # Task from 10 days ago (outside the 7-day window)
        old_date = (today - timedelta(days=10)).isoformat()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "1",
                    "content": "Old task",
                    "project_id": "proj1",
                    "completed_at": f"{old_date}T10:00:00Z",
                    "duration": None,
                },
                {
                    "id": "2",
                    "content": "Recent task",
                    "project_id": "proj1",
                    "completed_at": f"{today_str}T14:00:00Z",
                    "duration": None,
                },
            ],
            "next_cursor": None,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        def mock_async_client_factory(*args, **kwargs):
            return mock_client

        monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_factory)

        today_tasks, weekly_tasks, sparkline = (
            await integration._fetch_completed_with_billing(project_map)
        )

        # Old task should be ignored in counts (not in 7-day window)
        assert sparkline["total"] == 1  # Only the recent task
        assert len(today_tasks) == 1
        assert today_tasks[0]["content"] == "Recent task"


class TestTodoistWorkProjects:
    """Tests for work projects functionality."""

    def test_parse_duration_to_minutes_with_minutes(self):
        """Test parsing duration in minutes."""
        config = {"api_token": "test-token"}
        integration = TodoistIntegration(config)

        duration = {"amount": 30, "unit": "minute"}
        result = integration._parse_duration_to_minutes(duration)

        assert result == 30

    def test_parse_duration_to_minutes_with_hours(self):
        """Test parsing duration in hours."""
        config = {"api_token": "test-token"}
        integration = TodoistIntegration(config)

        duration = {"amount": 2, "unit": "hour"}
        result = integration._parse_duration_to_minutes(duration)

        assert result == 120

    def test_parse_duration_to_minutes_with_days(self):
        """Test parsing duration in days (8-hour workday)."""
        config = {"api_token": "test-token"}
        integration = TodoistIntegration(config)

        duration = {"amount": 1, "unit": "day"}
        result = integration._parse_duration_to_minutes(duration)

        assert result == 480  # 1 day * 8 hours * 60 minutes

    def test_parse_duration_to_minutes_with_none(self):
        """Test parsing None duration."""
        config = {"api_token": "test-token"}
        integration = TodoistIntegration(config)

        result = integration._parse_duration_to_minutes(None)

        assert result == 0

    def test_parse_duration_to_minutes_with_unknown_unit(self):
        """Test parsing duration with unknown unit."""
        config = {"api_token": "test-token"}
        integration = TodoistIntegration(config)

        duration = {"amount": 5, "unit": "unknown"}
        result = integration._parse_duration_to_minutes(duration)

        assert result == 0

    def test_process_work_projects_empty_config(self):
        """Test _process_work_projects with no work parent project configured."""
        config = {"api_token": "test-token"}
        integration = TodoistIntegration(config)

        result, project_ids = integration._process_work_projects([], [], {}, {})

        assert result == []
        assert project_ids == set()

    def test_process_work_projects_discovers_sub_projects(self):
        """Test _process_work_projects discovers sub-projects dynamically."""
        config = {
            "api_token": "test-token",
            "work_parent_project": "Work",
            "work_project_targets": {"Foodtrails": 20},
        }
        integration = TodoistIntegration(config)

        completed_tasks = [
            {
                "id": "1",
                "content": "Completed task 1",
                "project_id": "sub1",
                "duration": {"amount": 2, "unit": "hour"},
            },
            {
                "id": "2",
                "content": "Completed task 2",
                "project_id": "sub1",
                "duration": {"amount": 30, "unit": "minute"},
            },
            {
                "id": "3",
                "content": "Other project task",
                "project_id": "other",
                "duration": {"amount": 1, "unit": "hour"},
            },
        ]
        today_tasks = []
        # Work is parent, Foodtrails is sub-project
        project_map = {"work": "Work", "sub1": "Foodtrails", "other": "Personal"}
        project_parent_map = {"work": None, "sub1": "work", "other": None}

        result, project_ids = integration._process_work_projects(
            completed_tasks, today_tasks, project_map, project_parent_map
        )

        assert len(result) == 1
        assert result[0]["name"] == "Foodtrails"
        assert result[0]["completed_count"] == 2
        assert result[0]["total_hours"] == 2.5  # 2h + 30m
        assert len(result[0]["completed_tasks"]) == 2
        assert project_ids == {"sub1"}

    def test_process_work_projects_with_active_tasks(self):
        """Test _process_work_projects with active tasks in sub-projects."""
        config = {
            "api_token": "test-token",
            "work_parent_project": "Work",
            "work_project_targets": {"Foodtrails": 20},
        }
        integration = TodoistIntegration(config)

        completed_tasks = []
        today_tasks = [
            {"id": "1", "content": "Active task 1", "project_id": "sub1"},
            {"id": "2", "content": "Active task 2", "project_id": "sub1"},
        ]
        project_map = {"work": "Work", "sub1": "Foodtrails"}
        project_parent_map = {"work": None, "sub1": "work"}

        result, project_ids = integration._process_work_projects(
            completed_tasks, today_tasks, project_map, project_parent_map
        )

        assert len(result) == 1
        assert result[0]["name"] == "Foodtrails"
        assert result[0]["active_count"] == 2
        assert result[0]["completed_count"] == 0
        assert result[0]["total_hours"] == 0
        assert project_ids == {"sub1"}

    def test_process_work_projects_limits_tasks(self):
        """Test _process_work_projects limits tasks to 5 completed and 3 active."""
        config = {
            "api_token": "test-token",
            "work_parent_project": "Work",
            "work_project_targets": {"Foodtrails": 20},
        }
        integration = TodoistIntegration(config)

        # Create more tasks than the limit
        completed_tasks = [
            {"id": str(i), "content": f"Task {i}", "project_id": "sub1"}
            for i in range(10)
        ]
        today_tasks = [
            {"id": str(i), "content": f"Active {i}", "project_id": "sub1"}
            for i in range(10)
        ]
        project_map = {"work": "Work", "sub1": "Foodtrails"}
        project_parent_map = {"work": None, "sub1": "work"}

        result, project_ids = integration._process_work_projects(
            completed_tasks, today_tasks, project_map, project_parent_map
        )

        assert len(result) == 1
        assert len(result[0]["completed_tasks"]) == 5  # Limited to 5
        assert len(result[0]["active_tasks"]) == 3  # Limited to 3
        assert result[0]["completed_count"] == 10  # Full count
        assert result[0]["active_count"] == 10  # Full count
        assert project_ids == {"sub1"}

    def test_process_work_projects_discovers_multiple_sub_projects(self):
        """Test _process_work_projects only includes sub-projects with configured targets."""
        config = {
            "api_token": "test-token",
            "work_parent_project": "Work",
            "work_project_targets": {"Foodtrails": 20, "KellyMitchell Costco": 10},
        }
        integration = TodoistIntegration(config)

        completed_tasks = [
            {
                "id": "1",
                "content": "Foodtrails task",
                "project_id": "sub1",
                "duration": {"amount": 2, "unit": "hour"},
            },
            {
                "id": "2",
                "content": "Costco task",
                "project_id": "sub2",
                "duration": {"amount": 1, "unit": "hour"},
            },
        ]
        today_tasks = []
        project_map = {
            "work": "Work",
            "sub1": "Foodtrails",
            "sub2": "KellyMitchell Costco",
        }
        project_parent_map = {"work": None, "sub1": "work", "sub2": "work"}

        result, project_ids = integration._process_work_projects(
            completed_tasks, today_tasks, project_map, project_parent_map
        )

        assert len(result) == 2
        # Results can be in any order since they're discovered from dict
        names = {r["name"] for r in result}
        assert names == {"Foodtrails", "KellyMitchell Costco"}
        assert project_ids == {"sub1", "sub2"}

    def test_process_work_projects_parent_not_found(self):
        """Test _process_work_projects returns empty when parent not found."""
        config = {"api_token": "test-token", "work_parent_project": "Unknown Parent"}
        integration = TodoistIntegration(config)

        completed_tasks = []
        today_tasks = []
        project_map = {"proj1": "Work"}
        project_parent_map = {"proj1": None}

        result, project_ids = integration._process_work_projects(
            completed_tasks, today_tasks, project_map, project_parent_map
        )

        assert result == []
        assert project_ids == set()

    async def test_fetch_data_includes_work_projects(self, monkeypatch):
        """Test fetch_data includes work_projects in response."""
        config = {
            "api_token": "test-token",
            "work_parent_project": "Work",
            "work_project_targets": {"Foodtrails": 20},
        }
        integration = TodoistIntegration(config)

        today_str = datetime.now().date().isoformat()

        # Mock the API client with parent/child projects
        mock_api = AsyncMock()
        mock_api.get_tasks.return_value = [
            create_mock_task("1", "Task 1", today_str, project_id="sub1"),
        ]
        mock_api.get_projects.return_value = [
            create_mock_project("work", "Work"),
            create_mock_project("sub1", "Foodtrails", parent_id="work"),
        ]

        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        # Verify work_projects is in response
        assert "work_projects" in data
        assert isinstance(data["work_projects"], list)
        assert len(data["work_projects"]) == 1
        assert data["work_projects"][0]["name"] == "Foodtrails"

    async def test_fetch_data_work_projects_empty_when_not_configured(
        self, monkeypatch
    ):
        """Test fetch_data returns empty work_projects when not configured."""
        config = {"api_token": "test-token"}
        integration = TodoistIntegration(config)

        # Mock the API client
        mock_api = AsyncMock()
        mock_api.get_tasks.return_value = []
        mock_api.get_projects.return_value = []

        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        assert data["work_projects"] == []

    async def test_fetch_data_filters_work_tasks_from_general_queue(self, monkeypatch):
        """Test that work sub-project tasks are filtered from general today/overdue queues."""
        config = {
            "api_token": "test-token",
            "work_parent_project": "Work",
            "work_project_targets": {"Foodtrails": 20},
        }
        integration = TodoistIntegration(config)

        today_str = datetime.now().date().isoformat()

        # Mock the API client with tasks in both work and personal projects
        mock_api = AsyncMock()
        mock_api.get_tasks.return_value = [
            create_mock_task("1", "Work task", today_str, project_id="sub1"),
            create_mock_task("2", "Personal task", today_str, project_id="personal"),
        ]
        mock_api.get_projects.return_value = [
            create_mock_project("work", "Work"),
            create_mock_project("sub1", "Foodtrails", parent_id="work"),
            create_mock_project("personal", "Personal"),
        ]

        monkeypatch.setattr(integration, "_get_api", lambda: mock_api)

        data = await integration.fetch_data()

        # Work task should NOT appear in general today queue
        assert len(data["today_tasks"]) == 1
        assert data["today_tasks"][0]["content"] == "Personal task"

        # Work task should appear in work_projects section
        assert len(data["work_projects"]) == 1
        assert data["work_projects"][0]["name"] == "Foodtrails"
        assert len(data["work_projects"][0]["active_tasks"]) == 1
        assert data["work_projects"][0]["active_tasks"][0]["content"] == "Work task"
