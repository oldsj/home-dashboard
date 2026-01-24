"""Tests for the theming system."""

import pytest

from server.themes import (
    INDUSTRIAL_THEME,
    MATRIX_THEME,
    NEON_THEME,
    PINK_THEME,
    THEMES,
    get_theme,
    list_themes,
)


def test_industrial_theme_structure():
    """Test industrial theme has required structure."""
    assert INDUSTRIAL_THEME["name"] == "industrial"
    assert INDUSTRIAL_THEME["display_name"] == "Industrial Command Center"
    assert "colors" in INDUSTRIAL_THEME

    colors = INDUSTRIAL_THEME["colors"]
    # Check all required color keys exist
    required_keys = [
        "bg_black",
        "bg_darker",
        "bg_dark",
        "bg_panel",
        "bg_border",
        "primary",
        "primary_glow",
        "primary_dark",
        "secondary",
        "secondary_glow",
        "success",
        "warning",
        "error",
        "status_online",
        "status_offline",
        "text_primary",
        "text_secondary",
        "text_muted",
    ]
    for key in required_keys:
        assert key in colors, f"Missing color key: {key}"
        assert colors[key].startswith("#"), f"Color {key} should be hex"


def test_pink_theme_structure():
    """Test pink theme has required structure."""
    assert PINK_THEME["name"] == "pink"
    assert PINK_THEME["display_name"] == "Pink Dream"
    assert "colors" in PINK_THEME

    colors = PINK_THEME["colors"]
    # Spot check some pink-specific colors
    assert colors["primary"] == "#ff1b8d"
    assert colors["bg_black"] == "#0a0014"
    assert colors["text_primary"] == "#ff1b8d"


def test_neon_theme_structure():
    """Test neon theme has required structure."""
    assert NEON_THEME["name"] == "neon"
    assert NEON_THEME["display_name"] == "Cyberpunk Neon"
    assert "colors" in NEON_THEME

    colors = NEON_THEME["colors"]
    assert colors["primary"] == "#b833ff"  # Electric purple
    assert colors["secondary"] == "#00d9ff"  # Electric blue


def test_matrix_theme_structure():
    """Test matrix theme has required structure."""
    assert MATRIX_THEME["name"] == "matrix"
    assert MATRIX_THEME["display_name"] == "Matrix Green"
    assert "colors" in MATRIX_THEME

    colors = MATRIX_THEME["colors"]
    assert colors["primary"] == "#00ff41"  # Matrix green
    assert colors["secondary"] == "#ccff00"  # Bright lime


def test_themes_dict():
    """Test THEMES dict contains all themes."""
    assert "industrial" in THEMES
    assert "pink" in THEMES
    assert "neon" in THEMES
    assert "matrix" in THEMES
    assert "dark" in THEMES  # Legacy alias


def test_get_theme_industrial():
    """Test getting industrial theme."""
    theme = get_theme("industrial")
    assert theme == INDUSTRIAL_THEME


def test_get_theme_pink():
    """Test getting pink theme."""
    theme = get_theme("pink")
    assert theme == PINK_THEME


def test_get_theme_neon():
    """Test getting neon theme."""
    theme = get_theme("neon")
    assert theme == NEON_THEME


def test_get_theme_matrix():
    """Test getting matrix theme."""
    theme = get_theme("matrix")
    assert theme == MATRIX_THEME


def test_get_theme_dark_alias():
    """Test that 'dark' is an alias for 'industrial'."""
    theme = get_theme("dark")
    assert theme == INDUSTRIAL_THEME


def test_get_theme_unknown():
    """Test getting unknown theme raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        get_theme("nonexistent")

    assert "Unknown theme 'nonexistent'" in str(exc_info.value)
    assert "industrial, pink, neon, matrix, dark" in str(exc_info.value)


def test_list_themes():
    """Test listing available themes."""
    themes = list_themes()
    assert "industrial" in themes
    assert "pink" in themes
    assert "neon" in themes
    assert "matrix" in themes
    assert "dark" not in themes  # Legacy alias should be excluded


def test_all_themes_have_same_color_keys():
    """Test all themes define the same color keys."""
    industrial_keys = set(INDUSTRIAL_THEME["colors"].keys())

    for theme_name, theme in THEMES.items():
        if theme_name == "dark":
            continue  # Skip alias
        theme_keys = set(theme["colors"].keys())
        assert theme_keys == industrial_keys, (
            f"Theme {theme_name} has different keys: "
            f"missing={industrial_keys - theme_keys}, "
            f"extra={theme_keys - industrial_keys}"
        )


def test_all_colors_are_hex():
    """Test all color values are valid hex colors."""
    for theme_name, theme in THEMES.items():
        if theme_name == "dark":
            continue  # Skip alias
        for color_key, color_value in theme["colors"].items():
            assert color_value.startswith(
                "#"
            ), f"Theme {theme_name}, color {color_key} is not hex: {color_value}"
            assert (
                len(color_value) == 7
            ), f"Theme {theme_name}, color {color_key} has invalid length: {color_value}"
            # Check it's valid hex
            int(color_value[1:], 16)  # Will raise ValueError if invalid
