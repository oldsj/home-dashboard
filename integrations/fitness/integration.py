"""
Fitness metrics integration.

Displays today's workout plan, training stats vs goals,
current training phase, and weekly schedule overview.
All data is config-driven from credentials.yaml.
"""

from datetime import datetime
from typing import Any

from dashboard_integration_base import BaseIntegration, IntegrationConfig
from pydantic import Field


class FitnessGoal(IntegrationConfig):
    """A single fitness goal with current and target values."""

    label: str = Field(..., description="Goal label (e.g., '5K', 'Squat e1RM')")
    current: str = Field(..., description="Current value (e.g., '25:20', '239 lb')")
    target: str = Field(..., description="Target value (e.g., 'Sub-22:00', '315+ lb')")
    category: str = Field(
        default="strength", description="Category: 'running' or 'strength'"
    )


class WorkoutItem(IntegrationConfig):
    """A single exercise in a workout section."""

    exercise: str = Field(..., description="Exercise name")
    detail: str = Field(..., description="Sets/reps/duration details")
    note: str = Field(default="", description="Optional progression note")


class WorkoutSection(IntegrationConfig):
    """A section within a day's workout (e.g., lifting, running)."""

    title: str = Field(..., description="Section title")
    duration: str = Field(default="", description="Estimated duration")
    items: list[WorkoutItem] = Field(default_factory=list)
    note: str = Field(default="", description="Section-level note")


class WorkoutDay(IntegrationConfig):
    """A single day's workout plan."""

    day: str = Field(..., description="Day abbreviation (MON, TUE, etc.)")
    label: str = Field(..., description="Workout label (e.g., 'Workout A')")
    workout_type: str = Field(
        ..., description="Type: lift, run-hard, run-easy, both, rest"
    )
    icon: str = Field(default="", description="Emoji icon")
    sections: list[WorkoutSection] = Field(default_factory=list)


class TrainingPhase(IntegrationConfig):
    """A training phase/block."""

    name: str = Field(..., description="Phase name")
    period: str = Field(..., description="Time period")
    focus: str = Field(..., description="Phase focus description")
    active: bool = Field(default=False, description="Whether this is the current phase")


class FitnessConfig(IntegrationConfig):
    """Configuration model for the Fitness integration."""

    goals: list[FitnessGoal] = Field(default_factory=list)
    schedule: list[WorkoutDay] = Field(default_factory=list)
    phases: list[TrainingPhase] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    weekly_mileage_target: str = Field(
        default="", description="Weekly running mileage target"
    )
    program_name: str = Field(
        default="Fitness", description="Program name for the header"
    )
    program_subtitle: str = Field(default="", description="Subtitle/tagline")


class FitnessIntegration(BaseIntegration):
    """
    Fitness metrics integration.

    Displays workout schedule, goals, training phases,
    and today's workout. All data comes from config.
    """

    name = "fitness"
    display_name = "Fitness Tracker"
    refresh_interval = 300  # 5 minutes, data is mostly static

    ConfigModel = FitnessConfig

    async def fetch_data(self) -> dict[str, Any]:
        """Build fitness widget data from config."""
        config: FitnessConfig = self._validated_config  # type: ignore[assignment]

        # Determine today's day of week
        day_map = {
            0: "MON",
            1: "TUE",
            2: "WED",
            3: "THU",
            4: "FRI",
            5: "SAT",
            6: "SUN",
        }
        today_abbr = day_map[datetime.now().weekday()]

        # Find today's workout
        today_workout = None
        for day in config.schedule:
            if day.day.upper() == today_abbr:
                today_workout = day
                break

        # Find active phase
        active_phase = None
        for phase in config.phases:
            if phase.active:
                active_phase = phase
                break

        # Split goals by category
        running_goals = [g for g in config.goals if g.category == "running"]
        strength_goals = [g for g in config.goals if g.category == "strength"]

        # Build weekly schedule summary
        schedule_summary = []
        for day in config.schedule:
            schedule_summary.append(
                {
                    "day": day.day,
                    "label": day.label,
                    "type": day.workout_type,
                    "icon": day.icon,
                    "is_today": day.day.upper() == today_abbr,
                }
            )

        return {
            "today_abbr": today_abbr,
            "today_workout": (today_workout.model_dump() if today_workout else None),
            "active_phase": (active_phase.model_dump() if active_phase else None),
            "running_goals": [g.model_dump() for g in running_goals],
            "strength_goals": [g.model_dump() for g in strength_goals],
            "phases": [p.model_dump() for p in config.phases],
            "rules": config.rules,
            "schedule_summary": schedule_summary,
            "weekly_mileage_target": config.weekly_mileage_target,
            "program_name": config.program_name,
            "program_subtitle": config.program_subtitle,
            "total_goals": len(config.goals),
        }
