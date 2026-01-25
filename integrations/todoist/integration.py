"""
Todoist integration - Display tasks and projects from Todoist.

Fetches tasks, projects, and productivity stats from Todoist API
and displays them in a dashboard widget.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from dashboard_integration_base import BaseIntegration, IntegrationConfig
from pydantic import Field
from todoist_api_python.api_async import TodoistAPIAsync

logger = logging.getLogger(__name__)


class TodoistConfig(IntegrationConfig):
    """Configuration model for Todoist integration."""

    api_token: str = Field(
        ...,
        description="Todoist API token",
        json_schema_extra={"secret": True},  # nosec
    )
    max_tasks: int = Field(
        default=10,
        description="Maximum number of tasks to display",
    )
    refresh_rate: int = Field(
        default=60,
        description="Refresh rate in seconds",
    )


class TodoistIntegration(BaseIntegration):
    """
    Todoist integration for task management.

    Fetches today's tasks, overdue tasks, and productivity stats from Todoist.
    """

    name = "todoist"
    display_name = "Todoist"
    refresh_interval = 60

    ConfigModel = TodoistConfig

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize Todoist integration."""
        super().__init__(*args, **kwargs)
        self._api: Optional[TodoistAPIAsync] = None

    def _get_api(self) -> TodoistAPIAsync:
        """Get or create Todoist API client."""
        if self._api is None:
            api_token = self.get_config_value("api_token")
            self._api = TodoistAPIAsync(api_token)
        return self._api

    async def fetch_data(self) -> dict[str, Any]:
        """
        Fetch task data from Todoist API.

        Returns:
            Dict with today's tasks, overdue tasks, and stats
        """
        try:
            api = self._get_api()
            max_tasks = self.get_config_value("max_tasks", 10)

            # Fetch all active tasks
            # get_tasks() returns AsyncGenerator[list[Task]] from real API,
            # but may return a list from mocks in tests
            all_tasks = []
            tasks_result = await api.get_tasks()
            if isinstance(tasks_result, list):
                all_tasks = tasks_result
            else:
                async for task_batch in tasks_result:
                    all_tasks.extend(task_batch)

            # Fetch all projects to get project names
            # get_projects() returns AsyncGenerator[list[Project]] from real API,
            # but may return a list from mocks in tests
            projects = []
            projects_result = await api.get_projects()
            if isinstance(projects_result, list):
                projects = projects_result
            else:
                async for project_batch in projects_result:
                    projects.extend(project_batch)
            project_map = {p.id: p.name for p in projects}

            # Categorize tasks
            today = datetime.now().date()
            today_tasks = []
            overdue_tasks = []
            upcoming_tasks = []

            for task in all_tasks:
                task_dict = {
                    "id": task.id,
                    "content": task.content,
                    "description": task.description or "",
                    "priority": task.priority,
                    "labels": task.labels,
                    "project_id": task.project_id,
                    "project_name": project_map.get(task.project_id, ""),
                    "due": None,
                }

                # Parse due date if available
                if task.due:
                    task_dict["due"] = {
                        "date": task.due.date,
                        "string": task.due.string,
                        "is_recurring": task.due.is_recurring,
                        "timezone": task.due.timezone,
                    }

                    # Categorize by due date
                    if task.due.date:
                        # task.due.date is already a parsed date/datetime object
                        if isinstance(task.due.date, datetime):
                            due_date = task.due.date.date()
                        else:
                            due_date = task.due.date

                        if due_date < today:
                            overdue_tasks.append(task_dict)
                        elif due_date == today:
                            today_tasks.append(task_dict)
                        else:
                            upcoming_tasks.append(task_dict)
                    else:
                        # Has due but no specific date - treat as upcoming
                        upcoming_tasks.append(task_dict)
                else:
                    # No due date - consider it an inbox/someday task
                    upcoming_tasks.append(task_dict)

            # Sort by priority (higher priority first)
            today_tasks.sort(key=lambda t: t["priority"], reverse=True)
            overdue_tasks.sort(key=lambda t: t["priority"], reverse=True)

            # Get completed tasks count for today
            # Note: The API doesn't provide easy access to completed tasks count
            # You'd need to use the Sync API or activity log for this
            completed_today = 0

            return {
                "today_tasks": today_tasks,
                "overdue_tasks": overdue_tasks,
                "upcoming_count": len(upcoming_tasks),
                "completed_today": completed_today,
                "total_tasks": len(all_tasks),
                "projects_count": len(projects),
                "timestamp": datetime.now().isoformat(),
                "max_tasks": max_tasks,
            }

        except Exception as e:
            logger.error(f"Error fetching Todoist data: {e}")
            raise
