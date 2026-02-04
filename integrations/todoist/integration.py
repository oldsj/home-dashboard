"""
Todoist integration - Display tasks and projects from Todoist.

Fetches tasks, projects, and productivity stats from Todoist API
and displays them in a dashboard widget. Uses Sync API for efficient
near real-time updates.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
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
    work_parent_project: str = Field(
        default="",
        description="Parent project name - all sub-projects will be shown with hours tracking",
    )
    work_project_targets: dict[str, float] = Field(
        default={},
        description="Map of sub-project names to billing target hours (e.g., {'Foodtrails': 20})",
    )
    billing_since: str = Field(
        default="",
        description="ISO date (YYYY-MM-DD) to start counting hours. Update after billing to reset.",
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
            project_parent_map = {p.id: getattr(p, "parent_id", None) for p in projects}

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
                    "duration": getattr(task, "duration", None),
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

            # Fetch completed tasks for today, billing period, and weekly sparkline
            completed_tasks, billing_completed, weekly_sparkline = (
                await self._fetch_completed_with_billing(project_map)
            )

            # Process work sub-projects with hours tracking (uses billing period)
            work_projects, work_project_ids = self._process_work_projects(
                billing_completed, today_tasks, project_map, project_parent_map
            )

            # Filter out work sub-project tasks from general queues
            today_tasks = [
                t for t in today_tasks if t["project_id"] not in work_project_ids
            ]
            overdue_tasks = [
                t for t in overdue_tasks if t["project_id"] not in work_project_ids
            ]

            return {
                "today_tasks": today_tasks,
                "overdue_tasks": overdue_tasks,
                "upcoming_count": len(upcoming_tasks),
                "completed_today": len(completed_tasks),
                "completed_tasks": completed_tasks,
                "weekly_sparkline": weekly_sparkline,
                "total_tasks": len(all_tasks),
                "projects_count": len(projects),
                "work_projects": work_projects,
                "timestamp": datetime.now().isoformat(),
                "max_tasks": max_tasks,
            }

        except Exception as e:
            logger.error(f"Error fetching Todoist data: {e}")
            raise

    async def _fetch_completed_with_billing(
        self, project_map: dict[str, str]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        """
        Fetch completed tasks since billing_since date for hours tracking.

        Returns:
            Tuple of (today's completed tasks, billing period tasks, weekly sparkline data)
        """
        api_token = self.get_config_value("api_token")
        today = datetime.now().date()
        # Calculate Monday of current week for sparkline
        week_start = today - timedelta(days=today.weekday())

        # Get billing period start date
        billing_since_str = self.get_config_value("billing_since", "")
        if billing_since_str:
            billing_start = datetime.fromisoformat(billing_since_str).date()
        else:
            # Default to 30 days ago if not configured
            billing_start = today - timedelta(days=30)

        # Use the earlier of week_start or billing_start for the API call
        fetch_since = min(week_start, billing_start)

        # Initialize daily counts for current week (Mon-Sun)
        daily_counts: dict[str, int] = {}
        for i in range(7):
            day = (week_start + timedelta(days=i)).isoformat()
            daily_counts[day] = 0

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.todoist.com/sync/v9/completed/get_all",
                    headers={"Authorization": f"Bearer {api_token}"},
                    data={
                        "since": f"{fetch_since.isoformat()}T00:00:00",
                        "limit": "200",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                today_tasks = []
                billing_tasks = []
                today_str = today.isoformat()
                billing_start_str = billing_start.isoformat()

                items = data.get("items", [])
                logger.debug(f"Sync API returned {len(items)} completed items")

                # Collect task IDs that need duration lookup
                tasks_needing_duration: list[dict[str, Any]] = []

                for item in items:
                    completed_at = item.get("completed_at", "")
                    if completed_at:
                        # Extract date from ISO timestamp
                        completed_date = completed_at[:10]
                        if completed_date in daily_counts:
                            daily_counts[completed_date] += 1

                        # Build task dict - use v2_project_id for new ID format
                        v2_project_id = item.get("v2_project_id")
                        v2_task_id = item.get("v2_task_id")
                        task_dict = {
                            "id": v2_task_id or item.get("task_id"),
                            "content": item.get("content", ""),
                            "project_id": v2_project_id,
                            "project_name": project_map.get(v2_project_id, ""),
                            "duration": None,  # Will be fetched via REST API
                            "completed_at": completed_at,
                            "completed_date": completed_date,
                        }
                        tasks_needing_duration.append(task_dict)

                # Fetch duration for tasks via REST API (batched)
                await self._fetch_task_durations(
                    client, api_token, tasks_needing_duration
                )

                # Now categorize tasks
                for task_dict in tasks_needing_duration:
                    completed_date = task_dict.pop("completed_date")

                    # Collect today's tasks for the list
                    if completed_date == today_str:
                        today_tasks.append(task_dict)

                    # Collect all billing period tasks for hours tracking
                    if completed_date >= billing_start_str:
                        billing_tasks.append(task_dict)

                # Sort tasks by completion time, most recent first
                today_tasks.sort(
                    key=lambda t: t.get("completed_at") or "", reverse=True
                )
                billing_tasks.sort(
                    key=lambda t: t.get("completed_at") or "", reverse=True
                )

                # Build sparkline data
                counts = [daily_counts[d] for d in sorted(daily_counts.keys())]
                max_count = max(counts) if counts else 0
                sparkline = {
                    "counts": counts,
                    "max": max_count,
                    "total": sum(counts),
                    "bars": self._counts_to_sparkline(counts),
                }

                return today_tasks, billing_tasks, sparkline

        except Exception as e:
            logger.warning(f"Failed to fetch completed tasks: {e}")
            return [], [], {"counts": [0] * 7, "max": 0, "total": 0, "bars": "▁▁▁▁▁▁▁"}

    async def _fetch_task_durations(
        self,
        client: httpx.AsyncClient,
        api_token: str,
        tasks: list[dict[str, Any]],
    ) -> None:
        """
        Fetch duration for completed tasks via REST API.

        The Sync API doesn't include duration for completed tasks,
        so we fetch each task individually via REST API v2.

        Args:
            client: HTTP client to use
            api_token: Todoist API token
            tasks: List of task dicts to update with duration (modified in place)
        """
        for task in tasks:
            task_id = task.get("id")
            if not task_id:
                continue

            try:
                resp = await client.get(
                    f"https://api.todoist.com/rest/v2/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {api_token}"},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    task["duration"] = data.get("duration")
            except Exception as e:
                logger.debug(f"Failed to fetch duration for task {task_id}: {e}")

    def _counts_to_sparkline(self, counts: list[int]) -> str:
        """Convert counts to sparkline characters."""
        if not counts or max(counts) == 0:
            return "▁" * len(counts)

        bars = "▁▂▃▄▅▆▇█"
        max_val = max(counts)
        result = []
        for c in counts:
            idx = int((c / max_val) * (len(bars) - 1)) if max_val > 0 else 0
            result.append(bars[idx])
        return "".join(result)

    def _parse_duration_to_minutes(self, duration: dict | None) -> int:
        """
        Parse Todoist duration object to total minutes.

        Args:
            duration: Dict with 'amount' and 'unit' keys

        Returns:
            Total minutes, or 0 if no duration
        """
        if not duration:
            return 0

        amount = duration.get("amount", 0)
        unit = duration.get("unit", "minute")

        if unit == "minute":
            return amount
        elif unit == "hour":
            return amount * 60
        elif unit == "day":
            return amount * 60 * 8  # 8-hour workday
        return 0

    def _process_work_projects(
        self,
        completed_tasks: list[dict[str, Any]],
        today_tasks: list[dict[str, Any]],
        project_map: dict[str, str],
        project_parent_map: dict[str, str | None],
    ) -> tuple[list[dict[str, Any]], set[str]]:
        """
        Process work sub-projects to calculate hours and group tasks.

        Dynamically discovers all sub-projects under the configured parent project.

        Args:
            completed_tasks: List of completed tasks with project info
            today_tasks: List of today's active tasks
            project_map: Map of project IDs to names
            project_parent_map: Map of project IDs to parent IDs

        Returns:
            Tuple of (work project data dicts, set of work project IDs)
        """
        parent_project_name = self.get_config_value("work_parent_project", "")
        if not parent_project_name:
            return [], set()

        # Find parent project ID by name
        name_to_id = {name: pid for pid, name in project_map.items()}
        parent_id = name_to_id.get(parent_project_name)
        if not parent_id:
            logger.debug(f"Work parent project '{parent_project_name}' not found")
            return [], set()

        # Find all sub-projects under the parent
        sub_project_ids = {
            pid for pid, parent in project_parent_map.items() if parent == parent_id
        }

        # Only include projects with configured targets
        targets = self.get_config_value("work_project_targets", {})

        work_projects = []
        for project_id in sub_project_ids:
            project_name = project_map.get(project_id, "Unknown")

            # Skip projects without configured targets
            if project_name not in targets:
                continue

            # Filter completed tasks for this project
            project_completed = [
                t for t in completed_tasks if t.get("project_id") == project_id
            ]

            # Filter today's active tasks for this project
            project_active = [
                t for t in today_tasks if t.get("project_id") == project_id
            ]

            # Calculate total hours from completed task durations
            total_minutes = sum(
                self._parse_duration_to_minutes(t.get("duration"))
                for t in project_completed
            )
            total_hours = total_minutes / 60.0 if total_minutes > 0 else 0

            # Get target hours for this project
            target_hours = targets.get(project_name, 0)
            progress_percent = (
                (total_hours / target_hours * 100) if target_hours > 0 else 0
            )

            work_projects.append(
                {
                    "id": project_id,
                    "name": project_name,
                    "completed_tasks": project_completed[:5],  # Limit to 5
                    "active_tasks": project_active[:3],  # Limit to 3
                    "total_hours": total_hours,
                    "target_hours": target_hours,
                    "progress_percent": min(progress_percent, 100),  # Cap at 100%
                    "over_target": progress_percent > 100,
                    "completed_count": len(project_completed),
                    "active_count": len(project_active),
                }
            )

        return work_projects, sub_project_ids

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
