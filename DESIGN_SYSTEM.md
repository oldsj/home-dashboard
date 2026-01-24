# Dashboard Design System - Industrial Command Center

## Design Concept

This dashboard uses an **Industrial Command Center** aesthetic inspired by aerospace control rooms, NASA mission control, and brutalist cyberpunk interfaces. The design prioritizes readability, data density, and a distinctive terminal-like feel.

## Typography

- **Primary Font**: IBM Plex Mono (monospace)
- **Why**: Evokes data terminals and telemetry systems; ensures perfect tabular alignment
- **Character Spacing**: Slightly tightened (-0.02em) for density
- **Case**: UPPERCASE for labels and headers (command center style)
- **Tracking**: Widened for headers (0.1-0.15em) to enhance readability

## Color Palette

### Core Colors

- **Black Tones**:
  - `command-black` (#000000) - Pure black background
  - `command-darker` (#0a0a0a) - Slightly lifted panels
  - `command-dark` (#111111) - Widget backgrounds
  - `command-panel` (#1a1a1a) - Interactive surfaces
  - `command-border` (#2a2a2a) - Structural lines

### Accent Colors

- **Cyan** (#00d4ff) - Primary accent, data labels, active states
- **Amber** (#ffb000) - Warnings, alerts, highlights
- **Red** (#ff3355) - Critical alerts, errors, overdue
- **Green** (#00ff88) - Success states, online status, completions

### Usage Principles

- High contrast (white text on black backgrounds)
- Colored accents used sparingly for maximum impact
- Status indicators use semantic colors with glows
- Hover states brighten borders with cyan/amber gradients

## Visual Effects

### CRT Aesthetic

1. **Scan Line**: Animated horizontal line (2px cyan) moving down the screen
2. **Grid Texture**: Subtle repeating 4px grid overlay (cyan at 1.5% opacity)
3. **Text Glow**: Drop shadows on important values and status indicators

### Interactive Elements

- **Widget Borders**:
  - Base: 1px solid dark gray
  - Hover: Gradient border (cyan → amber) fades in
  - Corner brackets on all widgets for framing
- **Status Indicators**:
  - Circular dots with color-matched box shadows
  - Pulsing animation for active alerts
- **Buttons/Selects**:
  - Dark backgrounds with cyan text
  - Border changes to amber on focus
  - Monospace font for consistency

## Layout Principles

### Grid Structure

- No rounded corners (brutalist aesthetic)
- Sharp, precise alignments
- Visible structural lines (borders) everywhere
- Fixed-width layouts with defined boundaries

### Spacing

- Compact but not cramped
- 2-3px gaps between small elements
- 8-16px padding in containers
- Consistent rhythm throughout

### Widget Headers

- Amber vertical bar (1px × 16px) as visual anchor
- UPPERCASE titles with wide tracking
- Telemetry-style metadata (counts, statuses) on right
- Thin border-bottom separator

### Data Display

- **Labels**: 0.65rem, uppercase, wide tracking, cyan, 70% opacity
- **Values**: 1.75rem, bold, tight tracking, colored by type
- **Timestamps**: Monospace, amber tint, ISO-style formatting

## Component Patterns

### System Header Bar

- 32px fixed height at top
- System status (green dot + "SYSTEM_ACTIVE")
- Live timestamp in ISO format
- Grid dimensions display

### Camera Feeds

- Corner brackets appear on hover
- Status dots with semantic colors
- Telemetry footer (model, resolution)
- Loading states use monospace "CONNECTING..." text

### Task Lists

- Color-coded left borders (red=overdue, cyan=today)
- Gradient section dividers
- Hover states lighten background
- Empty states use bracket notation: `[ QUEUE_EMPTY ]`

### Motion Logs

- Monospace tabular layout
- Timestamp in HH:MM:SS format
- Subtle dark backgrounds for rows

## Animation Guidelines

- **Subtle by default**: Most transitions are 0.2-0.3s
- **Functional animations**: Scan line (8s), status pulse (1.5-2s)
- **Hover feedback**: Border and background transitions
- **Loading states**: Pulse animation on text

## Accessibility Notes

- High contrast ratios (cyan on black = 14:1)
- Color is supplemented with text labels
- Tabular numbers ensure consistent reading
- Clear focus states for keyboard navigation

## Implementation Notes

### Tailwind Configuration

Custom colors are defined in the `tailwind.config` within `base.html`:

```js
colors: {
  command: {
    black: "#000000",
    darker: "#0a0a0a",
    // ... etc
  }
}
```

### Custom CSS

Global effects (scan line, grid texture, scrollbar) are in `<style>` block in `base.html`.

### Widget Structure

Each widget follows this pattern:

1. Header (title bar with amber accent + metadata)
2. Content area (scrollable, data-dense)
3. Footer (optional, for totals/summaries)

## Design Differentiators

What makes this design memorable:

- ✅ **Monospace everywhere** (most dashboards use sans-serif)
- ✅ **Zero rounded corners** (brutalist precision)
- ✅ **High-contrast cyan/amber** (not generic purple gradients)
- ✅ **CRT effects** (scan line, grid texture, glows)
- ✅ **Telemetry-style data** (ISO timestamps, uppercase labels, wide tracking)
- ✅ **Semantic color coding** with intentional restraint

This design is **intentionally NOT** generic, minimal, or friendly. It's technical, precise, and unapologetically industrial.
