"""Preview tab renderer."""

import pandas as pd
import streamlit as st

from plot_studio.plotting.figures import make_column_preview_figure
from plot_studio.services.columns import normalize_colname
from plot_studio.ui.context import MainDatasetContext


def render_preview_tab(dataset: MainDatasetContext) -> None:
    """Render the dataset preview tab."""
    c1, c2 = st.columns([1.1, 1], vertical_alignment="top")
    with c1:
        st.markdown("##### Quick preview")
        st.dataframe(dataset.df.head(200), width="stretch", height=420)
    with c2:
        st.markdown("##### Columns & types")
        info_df = pd.DataFrame(
            {
                "column": dataset.cols,
                "dtype": [str(dataset.df[col].dtype) for col in dataset.cols],
            }
        )
        st.dataframe(info_df, width="stretch", height=420)
    with st.expander("Show summary statistics", expanded=False):
        st.dataframe(dataset.df.describe(include="all").transpose(), width="stretch")

    with st.expander("Column mini plots (all columns)", expanded=False):
        preview_x_col = dataset.date_col if dataset.date_col in dataset.cols else None
        preview_x_series = None
        if preview_x_col:
            parsed_x = dataset.df_parsed[preview_x_col]
            if (
                pd.api.types.is_datetime64_any_dtype(parsed_x)
                and parsed_x.notna().sum() > 0
            ):
                preview_x_series = parsed_x
            else:
                preview_x_col = None

        mini_plot_cols = [col for col in dataset.cols if col != preview_x_col]
        if preview_x_col:
            st.caption(
                f"Quick scan of all non-time columns using `{preview_x_col}` as shared x-axis."
            )
        else:
            st.caption("Quick scan of all columns.")

        if not mini_plot_cols:
            st.info("No preview columns available.")

        for start in range(0, len(mini_plot_cols), 3):
            row_cols = st.columns(3)
            for offset, col in enumerate(mini_plot_cols[start : start + 3]):
                with row_cols[offset]:
                    st.markdown(f"**{col}**")
                    mini_fig = make_column_preview_figure(
                        dataset.df[col],
                        x_series=preview_x_series,
                        x_label=preview_x_col,
                    )
                    if mini_fig is not None:
                        idx = start + offset
                        st.plotly_chart(
                            mini_fig,
                            width="stretch",
                            key=f"preview_mini_{idx}_{normalize_colname(col)}",
                        )
                    else:
                        st.caption("No preview available.")
