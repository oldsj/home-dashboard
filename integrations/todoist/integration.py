"""
Todoist integration - Display tasks and projects from Todoist.

Fetches tasks, projects, and productivity stats from Todoist API
and displays them in a dashboard widget. Uses Sync API for efficient
near real-time updates.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncIterator, Optional

import httpx
from dashboard_integration_base import BaseIntegration, IntegrationConfig
from pydantic import Field
from todoist_api_python.api_async import TodoistAPIAsync

logger = logging.getLogger(__name__)

SYNC_API_URL = "https://api.todoist.com/api/v1/sync"


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
        description="Refresh rate in seconds (fallback polling)",
    )
    poll_interval: int = Field(
        default=5,
        description="Sync API poll interval in seconds for real-time updates",
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
        self._sync_token: str = "*"  # Start with full sync  # nosec B105

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

    async def _check_for_changes(self, client: httpx.AsyncClient) -> tuple[bool, str]:
        """
        Check Todoist Sync API for changes since last sync.

        Returns:
            Tuple of (has_changes, new_sync_token)
        """
        api_token = self.get_config_value("api_token")

        response = await client.post(
            SYNC_API_URL,
            headers={"Authorization": f"Bearer {api_token}"},
            data={
                "sync_token": self._sync_token,
                "resource_types": json.dumps(["items", "projects"]),
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        new_token = data.get("sync_token", self._sync_token)
        is_full_sync = data.get("full_sync", False)

        # Check if there are any task or project changes
        has_items = bool(data.get("items"))
        has_projects = bool(data.get("projects"))
        has_changes = is_full_sync or has_items or has_projects

        if has_changes:
            logger.debug(
                f"Todoist changes detected: full_sync={is_full_sync}, "
                f"items={has_items}, projects={has_projects}"
            )

        return has_changes, new_token

    async def start_event_stream(self) -> AsyncIterator[dict[str, Any]]:
        """
        Stream Todoist updates using efficient Sync API polling.

        Uses incremental sync tokens to detect changes quickly without
        fetching all data on every poll. Only yields updates when
        tasks or projects have actually changed.
        """
        poll_interval = self.get_config_value("poll_interval", 5)
        logger.info(
            f"Todoist starting event stream with {poll_interval}s poll interval"
        )

        # Reset sync token for fresh start ("*" is Todoist's documented initial sync token)
        self._sync_token = "*"  # nosec B105

        async with httpx.AsyncClient() as client:
            # Initial sync - always yield first data
            try:
                has_changes, new_token = await self._check_for_changes(client)
                self._sync_token = new_token
                yield await self.fetch_data()
            except Exception as e:
                logger.error(f"Todoist initial sync failed: {e}")
                raise

            # Continuous polling for changes
            while True:
                await asyncio.sleep(poll_interval)

                try:
                    has_changes, new_token = await self._check_for_changes(client)
                    self._sync_token = new_token

                    if has_changes:
                        logger.debug("Todoist pushing update due to changes")
                        yield await self.fetch_data()

                except httpx.HTTPStatusError as e:
                    logger.error(f"Todoist sync API error: {e.response.status_code}")
                    # On auth errors, don't keep retrying rapidly
                    if e.response.status_code in (401, 403):
                        await asyncio.sleep(60)
                except Exception as e:
                    logger.error(f"Todoist sync error: {e}")
                    await asyncio.sleep(poll_interval)
