"""Dashboard tab renderer."""

import pandas as pd
import streamlit as st

from plot_studio.config import DATE_PARSE_MODES
from plot_studio.plotting.figures import render_plot_from_spec
from plot_studio.services.date_parsing import parse_dates_flexible
from plot_studio.ui.context import MainDatasetContext


def render_dashboard_tab(dataset: MainDatasetContext) -> None:
    """Render the dashboard tab."""
    st.markdown("#### Dashboard")
    st.caption(
        "Select one or more saved plot configs. Each selected config renders on the current dataset."
    )

    configs = st.session_state["saved_configs"]
    if not configs:
        st.info("No saved plot configs yet. Build one in **Plot Builder** and save it.")
        return

    ordered = sorted(configs, key=lambda cfg: (cfg.get("name") or "").lower())
    id_to_cfg = {cfg.get("id"): cfg for cfg in ordered}
    cfg_options = [cfg.get("id") for cfg in ordered]

    active_id = st.session_state.get("active_dashboard_id")
    default_selected = [active_id] if active_id in cfg_options else cfg_options[:1]
    selected_cfg_ids = st.multiselect(
        "Plot configs to display",
        options=cfg_options,
        default=default_selected,
        format_func=lambda value: id_to_cfg.get(value, {}).get("name", "Unnamed"),
    )

    if selected_cfg_ids:
        st.session_state["active_dashboard_id"] = selected_cfg_ids[0]

    if not selected_cfg_ids:
        st.info("Select at least one plot config.")
        return

    dash_filtered = render_dashboard_global_options(dataset)
    available_cols = list(dash_filtered.columns)

    for cfg_id in selected_cfg_ids:
        cfg = id_to_cfg.get(cfg_id)
        if not cfg:
            continue

        with st.container(border=True):
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
                  <div style="font-size:18px; font-weight:700;">{cfg.get("name", "Unnamed")}</div>
                  <div style="opacity:0.8; font-size:12px;">Created: {cfg.get("created_at", "")}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            plots = cfg.get("plots") or []
            if not plots:
                st.warning("This config contains no plots.")
                continue

            spec = plots[0]
            fig, warnings = render_plot_from_spec(dash_filtered, spec, available_cols)
            if warnings:
                with st.expander(
                    f"Column resolution warnings - {cfg.get('name', 'Unnamed')}",
                    expanded=False,
                ):
                    for warning in warnings:
                        st.warning(warning)
                    st.caption(
                        "Tip: You can fix this by editing the template JSON in the Templates tab."
                    )
            if fig is not None:
                st.plotly_chart(fig, width="stretch", key=f"dash_plot_{cfg_id}")
            else:
                st.error("Could not render this plot on the current dataset.")


def render_dashboard_global_options(dataset: MainDatasetContext) -> pd.DataFrame:
    """Render optional global date parsing and filtering for the dashboard."""
    st.divider()
    with st.expander("Global dashboard options", expanded=False):
        date_col_dash = st.selectbox(
            "Date/time column for dashboard (optional)",
            options=[None] + dataset.cols,
            index=(
                0
                if dataset.date_guess is None
                else ([None] + dataset.cols).index(dataset.date_guess)
            ),
        )
        dash_date_mode_default = st.session_state.get(
            "dash_date_mode",
            st.session_state.get("read_date_mode", "Auto-detect"),
        )
        if dash_date_mode_default not in DATE_PARSE_MODES:
            dash_date_mode_default = "Auto-detect"
        dash_date_mode = st.selectbox(
            "Date order",
            options=DATE_PARSE_MODES,
            index=DATE_PARSE_MODES.index(dash_date_mode_default),
            key="dash_date_mode",
            help="Auto-detect infers day/month order from the selected column when possible.",
        )
        date_format_dash = st.text_input(
            "Date format override (optional)",
            value="",
            key="dash_dateformat",
            help="Example: %d/%m/%Y or %m/%d/%Y. If filled, this overrides auto-detection.",
        )
        dash_df = parse_dates_flexible(
            dataset.df,
            date_col_dash,
            date_mode=dash_date_mode,
            date_format=(date_format_dash or None),
        )

        dash_filtered = dash_df
        if date_col_dash and date_col_dash in dash_df.columns:
            dt = dash_df[date_col_dash]
            if pd.api.types.is_datetime64_any_dtype(dt):
                valid_dt = dt.dropna()
                if not valid_dt.empty:
                    min_d, max_d = valid_dt.min(), valid_dt.max()
                    date_range = st.slider(
                        "Filter date range",
                        min_value=min_d.to_pydatetime(),
                        max_value=max_d.to_pydatetime(),
                        value=(min_d.to_pydatetime(), max_d.to_pydatetime()),
                        key="dash_dateslider",
                    )
                    dash_filtered = dash_df[
                        (dash_df[date_col_dash] >= date_range[0])
                        & (dash_df[date_col_dash] <= date_range[1])
                    ]
        st.session_state["dash_df_filtered"] = dash_filtered

    return st.session_state.get("dash_df_filtered", dataset.df)
