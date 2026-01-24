"""
Theme definitions for the dashboard.

Each theme defines color schemes, effects, and visual styling.
"""

from typing import TypedDict


class ThemeColors(TypedDict):
    """Color definitions for a theme."""

    # Background colors
    bg_black: str
    bg_darker: str
    bg_dark: str
    bg_panel: str
    bg_border: str

    # Accent colors
    primary: str
    primary_glow: str
    primary_dark: str
    secondary: str
    secondary_glow: str

    # Status colors
    success: str
    warning: str
    error: str
    status_online: str
    status_offline: str

    # Text colors
    text_primary: str
    text_secondary: str
    text_muted: str


class Theme(TypedDict):
    """Complete theme definition."""

    name: str
    display_name: str
    colors: ThemeColors


# Industrial Command Center Theme (original)
INDUSTRIAL_THEME: Theme = {
    "name": "industrial",
    "display_name": "Industrial Command Center",
    "colors": {
        # Backgrounds
        "bg_black": "#000000",
        "bg_darker": "#0a0a0a",
        "bg_dark": "#111111",
        "bg_panel": "#1a1a1a",
        "bg_border": "#2a2a2a",
        # Primary accent (cyan)
        "primary": "#00d4ff",
        "primary_glow": "#00ffff",
        "primary_dark": "#0088aa",
        # Secondary accent (amber)
        "secondary": "#ffb000",
        "secondary_glow": "#ff8800",
        # Status
        "success": "#00ff88",
        "warning": "#ffb000",
        "error": "#ff3355",
        "status_online": "#00ff88",
        "status_offline": "#555555",
        # Text
        "text_primary": "#00d4ff",
        "text_secondary": "#ffffff",
        "text_muted": "#666666",
    },
}

# Pink Dream Theme (new)
PINK_THEME: Theme = {
    "name": "pink",
    "display_name": "Pink Dream",
    "colors": {
        # Backgrounds - deep purple/magenta tones
        "bg_black": "#0a0014",
        "bg_darker": "#140a1f",
        "bg_dark": "#1a0f2e",
        "bg_panel": "#2a1a3d",
        "bg_border": "#3d2952",
        # Primary accent (hot pink)
        "primary": "#ff1b8d",
        "primary_glow": "#ff66b3",
        "primary_dark": "#cc0066",
        # Secondary accent (rose gold/peach)
        "secondary": "#ffb3d9",
        "secondary_glow": "#ffd6ec",
        # Status - pink-tinted
        "success": "#ff85c0",
        "warning": "#ffb3d9",
        "error": "#ff0066",
        "status_online": "#ff85c0",
        "status_offline": "#6b5570",
        # Text
        "text_primary": "#ff1b8d",
        "text_secondary": "#ffe6f7",
        "text_muted": "#8b6b91",
    },
}

# Cyberpunk Neon Theme
NEON_THEME: Theme = {
    "name": "neon",
    "display_name": "Cyberpunk Neon",
    "colors": {
        # Backgrounds - deep purple/blue
        "bg_black": "#0a0014",
        "bg_darker": "#0f0a1f",
        "bg_dark": "#14111f",
        "bg_panel": "#1f1a2e",
        "bg_border": "#2e2a3d",
        # Primary accent (electric purple)
        "primary": "#b833ff",
        "primary_glow": "#d966ff",
        "primary_dark": "#8800cc",
        # Secondary accent (electric blue)
        "secondary": "#00d9ff",
        "secondary_glow": "#66e5ff",
        # Status
        "success": "#00ff99",
        "warning": "#ffcc00",
        "error": "#ff0066",
        "status_online": "#00ff99",
        "status_offline": "#555566",
        # Text
        "text_primary": "#b833ff",
        "text_secondary": "#e6e6ff",
        "text_muted": "#6b5580",
    },
}

# Matrix Green Theme
MATRIX_THEME: Theme = {
    "name": "matrix",
    "display_name": "Matrix Green",
    "colors": {
        # Backgrounds - very dark green-tinted
        "bg_black": "#000a00",
        "bg_darker": "#001400",
        "bg_dark": "#001f00",
        "bg_panel": "#002b00",
        "bg_border": "#003d00",
        # Primary accent (matrix green)
        "primary": "#00ff41",
        "primary_glow": "#66ff88",
        "primary_dark": "#00b32e",
        # Secondary accent (bright lime)
        "secondary": "#ccff00",
        "secondary_glow": "#e5ff66",
        # Status
        "success": "#00ff41",
        "warning": "#ccff00",
        "error": "#ff3333",
        "status_online": "#00ff41",
        "status_offline": "#335533",
        # Text
        "text_primary": "#00ff41",
        "text_secondary": "#e6ffe6",
        "text_muted": "#336633",
    },
}

# All available themes
THEMES: dict[str, Theme] = {
    "industrial": INDUSTRIAL_THEME,
    "pink": PINK_THEME,
    "neon": NEON_THEME,
    "matrix": MATRIX_THEME,
}

# Legacy alias
THEMES["dark"] = INDUSTRIAL_THEME


def get_theme(theme_name: str) -> Theme:
    """
    Get theme by name.

    Args:
        theme_name: Name of the theme

    Returns:
        Theme definition

    Raises:
        ValueError: If theme doesn't exist
    """
    if theme_name not in THEMES:
        available = ", ".join(THEMES.keys())
        raise ValueError(f"Unknown theme '{theme_name}'. Available: {available}")
    return THEMES[theme_name]


def list_themes() -> list[str]:
    """Get list of available theme names."""
    # Exclude legacy alias
    return [name for name in THEMES.keys() if name != "dark"]
