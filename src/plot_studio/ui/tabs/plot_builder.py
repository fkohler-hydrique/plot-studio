"""Plot Builder tab renderer."""

import datetime
import uuid
from typing import Any

import pandas as pd
import streamlit as st

from plot_studio.config import DEFAULT_SERIES_COLORS, PLOT_TYPES, TEMPLATES
from plot_studio.plotting.figures import render_plot_from_spec
from plot_studio.plotting.specs import build_plot_spec_from_builder
from plot_studio.services.columns import normalize_colname
from plot_studio.services.templates import persist_saved_configs_to_disk
from plot_studio.ui.context import MainDatasetContext


def render_plot_builder_tab(dataset: MainDatasetContext) -> None:
    """Render the Plot Builder tab."""
    st.markdown("#### Plot Builder")
    st.caption(
        "Build a plot and save it as a reusable template (templates re-render on any CSV you load)."
    )

    with st.expander("1) Data & axes", expanded=True):
        filtered_df = dataset.df_parsed
        if dataset.date_col and dataset.date_col in dataset.df_parsed.columns:
            dt = dataset.df_parsed[dataset.date_col]
            if pd.api.types.is_datetime64_any_dtype(dt):
                valid_dt = dt.dropna()
                if not valid_dt.empty:
                    min_d, max_d = valid_dt.min(), valid_dt.max()
                    date_range = st.slider(
                        "Filter date range",
                        min_value=min_d.to_pydatetime(),
                        max_value=max_d.to_pydatetime(),
                        value=(min_d.to_pydatetime(), max_d.to_pydatetime()),
                    )
                    filtered_df = dataset.df_parsed[
                        (dataset.df_parsed[dataset.date_col] >= date_range[0])
                        & (dataset.df_parsed[dataset.date_col] <= date_range[1])
                    ]

        x_default = (
            dataset.date_col if dataset.date_col in dataset.cols else dataset.cols[0]
        )
        x_col = st.selectbox(
            "X axis",
            options=dataset.cols,
            index=dataset.cols.index(x_default) if x_default in dataset.cols else 0,
        )

        numeric_candidates = [
            col
            for col in dataset.cols
            if pd.api.types.is_numeric_dtype(dataset.df_parsed[col])
        ]
        y_candidates = numeric_candidates if numeric_candidates else dataset.cols
        y_cols = st.multiselect(
            "Y axis (primary)",
            options=dataset.cols,
            default=[col for col in y_candidates[:1] if col in dataset.cols],
        )

        st.markdown("##### Plot options")
        plot_type = st.radio("Type", options=PLOT_TYPES, horizontal=True, index=0)

        enable_y2 = st.toggle("Enable secondary Y axis", value=False)
        y2_cols: list[str] = []
        if enable_y2:
            y2_cols = st.multiselect(
                "Y axis (secondary)",
                options=[col for col in dataset.cols if col not in y_cols],
                default=[],
            )

        color_col = st.selectbox(
            "Color/group by (optional)",
            options=[None] + dataset.cols,
            index=0,
        )

        with st.expander("Advanced: aggregation (for categorical X)", expanded=False):
            agg = st.selectbox(
                "Aggregate Y by X",
                options=[None, "mean", "sum", "min", "max", "median"],
                index=0,
            )
            st.caption(
                "Useful when X is categorical and you have many rows per category."
            )

    style_map = render_series_styling(y_cols, y2_cols)

    with st.expander("2) Styling", expanded=False):
        template = st.selectbox(
            "Theme",
            options=TEMPLATES,
            index=TEMPLATES.index("plotly_white"),
        )
        title = st.text_input("Plot title (optional)", value="")
        yaxis_title_1 = st.text_input("Y1 axis title (optional)", value="")
        yaxis_title_2 = (
            st.text_input("Y2 axis title (optional)", value="") if enable_y2 else ""
        )

    st.divider()
    st.markdown("#### Preview")
    st.caption(
        "The figure updates based on your settings. If parsing/filters change, plots update too."
    )

    fig = None
    warnings: list[str] = []
    if not x_col or (not y_cols and not y2_cols):
        st.info("Pick an X column and at least one Y column.")
    else:
        try:
            spec = build_plot_spec_from_builder(
                title=title.strip() or None,
                x_col=x_col,
                y_cols=y_cols,
                plot_type=plot_type,
                template=template,
                enable_secondary_axis=enable_y2,
                y2_cols=y2_cols,
                yaxis_title_1=yaxis_title_1.strip() or None,
                yaxis_title_2=yaxis_title_2.strip() or None,
                color_col=color_col,
                agg=agg,
                series_style=style_map,
            )
            fig, warnings = render_plot_from_spec(
                filtered_df,
                spec,
                list(filtered_df.columns),
            )
            if warnings:
                with st.expander("Warnings", expanded=False):
                    for warning in warnings:
                        st.warning(warning)

            if fig is not None:
                st.plotly_chart(fig, width="stretch", key="plot_builder_preview")
        except Exception as exc:
            st.error(f"Error generating plot: {exc}")

    st.divider()
    st.markdown("#### Save as dashboard template")
    st.caption("Templates re-render on any CSV you load (with fuzzy column matching).")
    dash_name = st.text_input(
        "Template name",
        value="",
        placeholder="e.g. Discharge dashboard",
    )
    plot_label = st.text_input(
        "Plot label (optional)",
        value="",
        placeholder="e.g. Q (m³/s) vs time",
    )

    save_disabled = (fig is None) or (not (dash_name or "").strip())
    if st.button(
        "Save template (single plot)",
        width="stretch",
        disabled=save_disabled,
    ):
        new_cfg = {
            "id": str(uuid.uuid4()),
            "name": dash_name.strip(),
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "plots": [
                build_plot_spec_from_builder(
                    title=plot_label.strip() or (title.strip() or None),
                    x_col=x_col,
                    y_cols=y_cols,
                    plot_type=plot_type,
                    template=template,
                    enable_secondary_axis=enable_y2,
                    y2_cols=y2_cols,
                    yaxis_title_1=yaxis_title_1.strip() or None,
                    yaxis_title_2=yaxis_title_2.strip() or None,
                    color_col=color_col,
                    agg=agg,
                    series_style=style_map,
                )
            ],
        }
        st.session_state["saved_configs"].append(new_cfg)
        persist_saved_configs_to_disk(st.session_state["saved_configs"])
        st.session_state["active_dashboard_id"] = new_cfg["id"]
        st.success("Template saved and selected in the sidebar.")

    st.caption(
        "Multi-plot dashboards can be added next (UI for adding plots to an existing template)."
    )


def render_series_styling(
    y_cols: list[str],
    y2_cols: list[str],
) -> dict[str, dict[str, Any]]:
    """Render the Plot Builder sidebar style controls."""
    with st.sidebar:
        st.markdown("### Plot Builder")
        with st.expander("Series styling (per Y)", expanded=False):
            st.caption("Optional: override each series' line color, width, and style.")
            dash_options = [
                "solid",
                "dash",
                "dot",
                "dashdot",
                "longdash",
                "longdashdot",
            ]
            style_map: dict[str, dict[str, Any]] = {}
            series_list = list(dict.fromkeys((y_cols or []) + (y2_cols or [])))
            if not series_list:
                st.info("Select Y columns to customize them.")
            for idx, series_name in enumerate(series_list):
                safe = normalize_colname(series_name).replace(" ", "_") or "series"
                default_color = DEFAULT_SERIES_COLORS[idx % len(DEFAULT_SERIES_COLORS)]
                color_key = f"sty_{safe}_color"
                if color_key not in st.session_state:
                    st.session_state[color_key] = default_color
                st.markdown(f"**{series_name}**")
                c1, c2, c3 = st.columns([1.2, 1, 1])
                with c1:
                    color = st.color_picker(
                        "Color",
                        key=color_key,
                        label_visibility="collapsed",
                    )
                with c2:
                    width = st.slider(
                        "Width",
                        min_value=1,
                        max_value=8,
                        value=2,
                        key=f"sty_{safe}_width",
                        label_visibility="collapsed",
                    )
                with c3:
                    dash = st.selectbox(
                        "Style",
                        options=dash_options,
                        index=0,
                        key=f"sty_{safe}_dash",
                        label_visibility="collapsed",
                    )
                style_map[series_name] = {
                    "color": color,
                    "width": width,
                    "dash": dash,
                }
                st.markdown("")

    return style_map
