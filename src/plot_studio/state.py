"""Session state helpers for the Streamlit app."""

from collections.abc import MutableMapping
from typing import Any

from plot_studio.services.templates import load_saved_configs_from_disk


def initialize_session_state(session_state: MutableMapping[str, Any]) -> None:
    """Ensure all required Streamlit session state keys exist."""
    if "saved_configs" not in session_state:
        session_state["saved_configs"] = load_saved_configs_from_disk()

    if "df" not in session_state:
        session_state["df"] = None

    if "file_label" not in session_state:
        session_state["file_label"] = ""

    if "active_dashboard_id" not in session_state:
        session_state["active_dashboard_id"] = None

    if "read_date_col" not in session_state:
        session_state["read_date_col"] = None

    if "read_date_mode" not in session_state:
        session_state["read_date_mode"] = (
            "Day-first" if session_state.get("read_dayfirst") else "Auto-detect"
        )

    if "read_date_format" not in session_state:
        session_state["read_date_format"] = ""
