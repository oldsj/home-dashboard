"""Tests for the fitness integration."""

from datetime import datetime
from unittest.mock import patch

from integrations.fitness.integration import (
    FitnessConfig,
    FitnessGoal,
    FitnessIntegration,
    TrainingPhase,
    WorkoutDay,
    WorkoutItem,
    WorkoutSection,
)


def _make_config(**overrides):
    """Build a minimal fitness config dict with optional overrides."""
    base = {
        "program_name": "Test Program",
        "program_subtitle": "Test subtitle",
        "weekly_mileage_target": "20 mi/wk",
        "goals": [
            {
                "label": "5K",
                "current": "25:00",
                "target": "22:00",
                "category": "running",
            },
            {
                "label": "Squat",
                "current": "200 lb",
                "target": "315 lb",
                "category": "strength",
            },
        ],
        "schedule": [
            {
                "day": "MON",
                "label": "Workout A",
                "workout_type": "lift",
                "icon": "🏋️",
                "sections": [
                    {
                        "title": "Squat Focus",
                        "duration": "60 min",
                        "items": [
                            {
                                "exercise": "Squat",
                                "detail": "3x5",
                                "note": "+5 lb/wk",
                            }
                        ],
                        "note": "Focus on form",
                    }
                ],
            },
            {
                "day": "SAT",
                "label": "Rest",
                "workout_type": "rest",
                "icon": "😴",
                "sections": [
                    {
                        "title": "Full Rest",
                        "items": [{"exercise": "Recovery", "detail": "No training."}],
                    }
                ],
            },
        ],
        "phases": [
            {
                "name": "Base",
                "period": "Now → April",
                "focus": "Build base",
                "active": True,
            },
            {
                "name": "Peak",
                "period": "May → June",
                "focus": "Peak phase",
                "active": False,
            },
        ],
        "rules": ["Rule 1", "Rule 2"],
    }
    base.update(overrides)
    return base


class TestFitnessConfig:
    """Tests for fitness config models."""

    def test_fitness_goal_model(self):
        """Test FitnessGoal Pydantic model."""
        goal = FitnessGoal(
            label="5K", current="25:00", target="22:00", category="running"
        )
        assert goal.label == "5K"
        assert goal.current == "25:00"
        assert goal.target == "22:00"
        assert goal.category == "running"

    def test_fitness_goal_default_category(self):
        """Test FitnessGoal defaults to strength category."""
        goal = FitnessGoal(label="Squat", current="200", target="315")
        assert goal.category == "strength"

    def test_workout_item_model(self):
        """Test WorkoutItem Pydantic model."""
        item = WorkoutItem(exercise="Squat", detail="3x5", note="+5 lb")
        assert item.exercise == "Squat"
        assert item.detail == "3x5"
        assert item.note == "+5 lb"

    def test_workout_item_default_note(self):
        """Test WorkoutItem defaults to empty note."""
        item = WorkoutItem(exercise="Squat", detail="3x5")
        assert item.note == ""

    def test_workout_section_model(self):
        """Test WorkoutSection Pydantic model."""
        section = WorkoutSection(
            title="Lifting",
            duration="60 min",
            items=[WorkoutItem(exercise="Squat", detail="3x5")],
            note="Focus on form",
        )
        assert section.title == "Lifting"
        assert section.duration == "60 min"
        assert len(section.items) == 1
        assert section.note == "Focus on form"

    def test_workout_section_defaults(self):
        """Test WorkoutSection default values."""
        section = WorkoutSection(title="Test")
        assert section.duration == ""
        assert section.items == []
        assert section.note == ""

    def test_workout_day_model(self):
        """Test WorkoutDay Pydantic model."""
        day = WorkoutDay(day="MON", label="Workout A", workout_type="lift", icon="🏋️")
        assert day.day == "MON"
        assert day.label == "Workout A"
        assert day.workout_type == "lift"
        assert day.icon == "🏋️"

    def test_workout_day_default_icon(self):
        """Test WorkoutDay defaults to empty icon."""
        day = WorkoutDay(day="MON", label="Test", workout_type="lift")
        assert day.icon == ""

    def test_training_phase_model(self):
        """Test TrainingPhase Pydantic model."""
        phase = TrainingPhase(
            name="Base", period="Now → April", focus="Build base", active=True
        )
        assert phase.name == "Base"
        assert phase.active is True

    def test_training_phase_default_inactive(self):
        """Test TrainingPhase defaults to inactive."""
        phase = TrainingPhase(name="Peak", period="May", focus="Peak")
        assert phase.active is False

    def test_fitness_config_model(self):
        """Test FitnessConfig Pydantic model."""
        config = FitnessConfig(program_name="Test", program_subtitle="Sub")
        assert config.program_name == "Test"
        assert config.goals == []
        assert config.schedule == []
        assert config.phases == []
        assert config.rules == []
        assert config.weekly_mileage_target == ""

    def test_fitness_config_defaults(self):
        """Test FitnessConfig default values."""
        config = FitnessConfig()
        assert config.program_name == "Fitness"
        assert config.program_subtitle == ""


class TestFitnessIntegration:
    """Tests for FitnessIntegration class."""

    def test_init(self):
        """Test integration initializes with config."""
        config = _make_config()
        integration = FitnessIntegration(config)
        assert integration.name == "fitness"
        assert integration.display_name == "Fitness Tracker"
        assert integration.refresh_interval == 300

    def test_init_minimal_config(self):
        """Test integration initializes with empty config."""
        integration = FitnessIntegration({})
        assert integration.name == "fitness"

    @patch("integrations.fitness.integration.datetime")
    async def test_fetch_data_monday(self, mock_datetime):
        """Test fetch_data returns correct data for Monday."""
        mock_datetime.now.return_value = datetime(2026, 3, 2)  # Monday
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

        config = _make_config()
        integration = FitnessIntegration(config)
        data = await integration.fetch_data()

        assert data["today_abbr"] == "MON"
        assert data["today_workout"] is not None
        assert data["today_workout"]["label"] == "Workout A"
        assert data["today_workout"]["workout_type"] == "lift"
        assert len(data["today_workout"]["sections"]) == 1
        assert data["today_workout"]["sections"][0]["title"] == "Squat Focus"

    @patch("integrations.fitness.integration.datetime")
    async def test_fetch_data_saturday_rest(self, mock_datetime):
        """Test fetch_data returns rest day for Saturday."""
        mock_datetime.now.return_value = datetime(2026, 3, 7)  # Saturday
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

        config = _make_config()
        integration = FitnessIntegration(config)
        data = await integration.fetch_data()

        assert data["today_abbr"] == "SAT"
        assert data["today_workout"] is not None
        assert data["today_workout"]["workout_type"] == "rest"

    @patch("integrations.fitness.integration.datetime")
    async def test_fetch_data_no_workout_for_day(self, mock_datetime):
        """Test fetch_data when no workout is configured for today."""
        mock_datetime.now.return_value = datetime(2026, 3, 3)  # Tuesday
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # Only MON and SAT in schedule
        config = _make_config()
        integration = FitnessIntegration(config)
        data = await integration.fetch_data()

        assert data["today_abbr"] == "TUE"
        assert data["today_workout"] is None

    async def test_fetch_data_goals_split(self):
        """Test that goals are split by category."""
        config = _make_config()
        integration = FitnessIntegration(config)
        data = await integration.fetch_data()

        assert len(data["running_goals"]) == 1
        assert data["running_goals"][0]["label"] == "5K"
        assert len(data["strength_goals"]) == 1
        assert data["strength_goals"][0]["label"] == "Squat"

    async def test_fetch_data_active_phase(self):
        """Test that active phase is identified."""
        config = _make_config()
        integration = FitnessIntegration(config)
        data = await integration.fetch_data()

        assert data["active_phase"] is not None
        assert data["active_phase"]["name"] == "Base"
        assert data["active_phase"]["active"] is True

    async def test_fetch_data_no_active_phase(self):
        """Test fetch_data when no phase is active."""
        config = _make_config(
            phases=[
                {
                    "name": "Future",
                    "period": "Later",
                    "focus": "TBD",
                    "active": False,
                }
            ]
        )
        integration = FitnessIntegration(config)
        data = await integration.fetch_data()

        assert data["active_phase"] is None

    async def test_fetch_data_schedule_summary(self):
        """Test schedule summary includes all days."""
        config = _make_config()
        integration = FitnessIntegration(config)
        data = await integration.fetch_data()

        assert len(data["schedule_summary"]) == 2  # MON and SAT
        mon = data["schedule_summary"][0]
        assert mon["day"] == "MON"
        assert mon["label"] == "Workout A"
        assert mon["type"] == "lift"
        assert mon["icon"] == "🏋️"

    async def test_fetch_data_metadata(self):
        """Test metadata fields in fetch_data."""
        config = _make_config()
        integration = FitnessIntegration(config)
        data = await integration.fetch_data()

        assert data["program_name"] == "Test Program"
        assert data["program_subtitle"] == "Test subtitle"
        assert data["weekly_mileage_target"] == "20 mi/wk"
        assert data["total_goals"] == 2
        assert data["rules"] == ["Rule 1", "Rule 2"]
        assert len(data["phases"]) == 2

    async def test_fetch_data_empty_config(self):
        """Test fetch_data with empty config."""
        integration = FitnessIntegration({})
        data = await integration.fetch_data()

        assert data["today_workout"] is None
        assert data["active_phase"] is None
        assert data["running_goals"] == []
        assert data["strength_goals"] == []
        assert data["schedule_summary"] == []
        assert data["rules"] == []
        assert data["phases"] == []
        assert data["total_goals"] == 0

    def test_render_widget(self):
        """Test that widget renders without errors."""
        config = _make_config()
        integration = FitnessIntegration(config)

        data = {
            "today_abbr": "MON",
            "today_workout": {
                "day": "MON",
                "label": "Workout A",
                "workout_type": "lift",
                "icon": "🏋️",
                "sections": [
                    {
                        "title": "Squat Focus",
                        "duration": "60 min",
                        "items": [
                            {"exercise": "Squat", "detail": "3x5", "note": "+5 lb"}
                        ],
                        "note": "Focus on form",
                    }
                ],
            },
            "active_phase": {"name": "Base", "period": "Now", "focus": "Build"},
            "running_goals": [{"label": "5K", "current": "25:00", "target": "22:00"}],
            "strength_goals": [{"label": "Squat", "current": "200", "target": "315"}],
            "phases": [
                {
                    "name": "Base",
                    "period": "Now",
                    "focus": "Build",
                    "active": True,
                },
                {
                    "name": "Peak",
                    "period": "May",
                    "focus": "Peak",
                    "active": False,
                },
            ],
            "rules": ["Rule 1"],
            "schedule_summary": [
                {
                    "day": "MON",
                    "label": "Workout A",
                    "type": "lift",
                    "icon": "🏋️",
                    "is_today": True,
                },
                {
                    "day": "SAT",
                    "label": "Rest",
                    "type": "rest",
                    "icon": "😴",
                    "is_today": False,
                },
            ],
            "weekly_mileage_target": "20 mi/wk",
            "program_name": "Test",
            "program_subtitle": "Sub",
            "total_goals": 2,
        }

        html = integration.render_widget(data)
        assert "Test" in html
        assert "Squat Focus" in html
        assert "5K" in html
        assert "Base" in html

    def test_render_widget_rest_day(self):
        """Test widget renders rest day correctly."""
        config = _make_config()
        integration = FitnessIntegration(config)

        data = {
            "today_abbr": "SAT",
            "today_workout": {
                "day": "SAT",
                "label": "Rest",
                "workout_type": "rest",
                "icon": "😴",
                "sections": [],
            },
            "active_phase": None,
            "running_goals": [],
            "strength_goals": [],
            "phases": [],
            "rules": [],
            "schedule_summary": [],
            "weekly_mileage_target": "",
            "program_name": "Test",
            "program_subtitle": "",
            "total_goals": 0,
        }

        html = integration.render_widget(data)
        assert "REST_DAY" in html

    def test_render_widget_no_workout(self):
        """Test widget renders when no workout for today."""
        config = _make_config()
        integration = FitnessIntegration(config)

        data = {
            "today_abbr": "TUE",
            "today_workout": None,
            "active_phase": None,
            "running_goals": [],
            "strength_goals": [],
            "phases": [],
            "rules": [],
            "schedule_summary": [],
            "weekly_mileage_target": "",
            "program_name": "Test",
            "program_subtitle": "",
            "total_goals": 0,
        }

        html = integration.render_widget(data)
        assert "Test" in html

    @patch("integrations.fitness.integration.datetime")
    async def test_all_weekdays(self, mock_datetime):
        """Test that all days of the week map correctly."""
        mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)

        # March 2026: Mon=2, Tue=3, Wed=4, Thu=5, Fri=6, Sat=7, Sun=8
        expected = {
            2: "MON",
            3: "TUE",
            4: "WED",
            5: "THU",
            6: "FRI",
            7: "SAT",
            8: "SUN",
        }

        for day_num, expected_abbr in expected.items():
            mock_datetime.now.return_value = datetime(2026, 3, day_num)
            integration = FitnessIntegration({})
            data = await integration.fetch_data()
            assert data["today_abbr"] == expected_abbr


class TestFitnessIntegrationDiscovery:
    """Test that fitness integration is properly discovered."""

    def test_discover_fitness(self):
        """Test that fitness integration is discovered."""
        from integrations import discover_integrations

        discovered = discover_integrations()
        assert "fitness" in discovered

    def test_load_fitness(self):
        """Test loading fitness integration."""
        from integrations import load_integration

        integration = load_integration("fitness", {})
        assert integration.name == "fitness"
        assert integration.display_name == "Fitness Tracker"
