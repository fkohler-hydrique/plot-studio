"""Project-wide configuration constants."""

import plotly.express as px

APP_PAGE_TITLE = "Plot Studio"
APP_PAGE_ICON = ":chart_with_upwards_trend:"
APP_LAYOUT = "wide"
APP_HEADER_TITLE = "Plot Studio"
APP_HEADER_SUBTITLE = (
    "Build reusable dashboard templates for CSV data without saving plot snapshots."
)

CANDIDATE_SEPARATORS = [",", ";", "\t", "|"]
DATE_KEYWORDS = ("date", "time", "datum", "zeit", "datetime")
DATE_PARSE_MODES = ["Auto-detect", "Day-first", "Month-first"]
SAVED_CONFIGS_FILE = "saved_configs.json"

PLOT_TYPES = ["Line", "Scatter", "Bar", "Area"]
TEMPLATES = [
    "plotly",
    "plotly_white",
    "plotly_dark",
    "ggplot2",
    "seaborn",
    "simple_white",
    "none",
]
DEFAULT_SERIES_COLORS = px.colors.qualitative.Plotly
