"""Streamlit application composition for Plot Studio."""

import streamlit as st

from plot_studio.config import APP_LAYOUT, APP_PAGE_ICON, APP_PAGE_TITLE
from plot_studio.services.columns import guess_date_column
from plot_studio.services.csv_reading import read_csv_input
from plot_studio.services.date_parsing import parse_dates_flexible
from plot_studio.state import initialize_session_state
from plot_studio.ui.context import MainDatasetContext
from plot_studio.ui.header import render_dataset_summary, render_header
from plot_studio.ui.sidebar import render_sidebar
from plot_studio.ui.tabs.compare import render_compare_tab
from plot_studio.ui.tabs.dashboard import render_dashboard_tab
from plot_studio.ui.tabs.plot_builder import render_plot_builder_tab
from plot_studio.ui.tabs.preview import render_preview_tab
from plot_studio.ui.tabs.templates import render_templates_tab


def main() -> None:
    """Run the Streamlit app."""
    st.set_page_config(
        page_title=APP_PAGE_TITLE,
        page_icon=APP_PAGE_ICON,
        layout=APP_LAYOUT,
    )

    initialize_session_state(st.session_state)
    render_header()

    sidebar_selection = render_sidebar()
    df, label, err = read_csv_input(
        sidebar_selection.uploaded_file,
        sidebar_selection.csv_path,
        decimal=sidebar_selection.reading_options.decimal,
        sep=sidebar_selection.reading_options.sep,
        header=sidebar_selection.reading_options.header,
        skiprows=sidebar_selection.reading_options.skiprows,
    )

    if err:
        st.error(f"Could not read CSV: {err}")
    elif df is not None:
        st.session_state["df"] = df
        st.session_state["file_label"] = label

    current_df = st.session_state["df"]
    if current_df is None:
        st.info("Upload a CSV (or provide a server path) to start.")
        st.stop()

    dataset = build_main_dataset_context(current_df)
    render_dataset_summary(dataset)

    tabs = st.tabs(
        [
            "🔎 Preview",
            "🛠️ Plot Builder",
            "🧩 Dashboard",
            "⚖️ Compare (2 CSVs)",
            "⚙️ Templates",
        ]
    )

    with tabs[0]:
        render_preview_tab(dataset)
    with tabs[1]:
        render_plot_builder_tab(dataset)
    with tabs[2]:
        render_dashboard_tab(dataset)
    with tabs[3]:
        render_compare_tab(dataset, sidebar_selection.reading_options)
    with tabs[4]:
        render_templates_tab()


def build_main_dataset_context(df) -> MainDatasetContext:
    """Build the derived dataset context shared across tabs."""
    cols = list(df.columns)
    date_guess = guess_date_column(cols)
    date_col_state = st.session_state.get("read_date_col")
    date_col = (
        date_col_state
        if date_col_state in cols
        else (date_guess if date_guess in cols else None)
    )
    df_parsed = parse_dates_flexible(
        df,
        date_col,
        date_mode=st.session_state.get("read_date_mode", "Auto-detect"),
        date_format=(st.session_state.get("read_date_format", "") or "").strip()
        or None,
    )
    return MainDatasetContext(
        df=df,
        df_parsed=df_parsed,
        cols=cols,
        date_col=date_col,
        date_guess=date_guess,
        label=st.session_state["file_label"] or "CSV",
    )
