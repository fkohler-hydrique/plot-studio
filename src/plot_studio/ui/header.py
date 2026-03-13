"""Header and summary UI components."""

import streamlit as st

from plot_studio.config import APP_HEADER_SUBTITLE, APP_HEADER_TITLE
from plot_studio.ui.context import MainDatasetContext


def render_header() -> None:
    """Render the app header."""
    st.markdown(
        f"""
        <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:12px; margin-bottom: 6px;">
          <div>
            <div style="font-size: 28px; font-weight: 800; line-height: 1.0;">{APP_HEADER_TITLE}</div>
            <div style="font-size: 14px; opacity: 0.85; margin-top: 6px;">
              {APP_HEADER_SUBTITLE}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dataset_summary(dataset: MainDatasetContext) -> None:
    """Render top-of-page dataset summary metrics."""
    left, right = st.columns([2, 1], vertical_alignment="top")
    with left:
        st.markdown(f"#### Data: `{dataset.label or 'CSV'}`")
    with right:
        st.markdown("")
        st.caption("Tip: Use **Dashboard** for consistent plots across different CSVs.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Rows", f"{len(dataset.df):,}")
    m2.metric("Columns", f"{len(dataset.cols):,}")
    m3.metric("Missing cells", f"{int(dataset.df.isna().sum().sum()):,}")
    m4.metric(
        "Memory (approx.)",
        f"{dataset.df.memory_usage(deep=True).sum() / (1024**2):.1f} MB",
    )

    st.divider()
