"""Local Plotly relayout component for dashboard x-axis sync."""

import json
import os

import plotly.utils
import streamlit.components.v1 as components

parent_dir = os.path.dirname(os.path.abspath(__file__))
build_dir = os.path.join(parent_dir, "frontend", "build")
_component_func = components.declare_component(
    "plotly_relayout_chart",
    path=build_dir,
)


def plotly_relayout_chart(
    plot_fig,
    *,
    override_height: int = 450,
    override_width: str = "100%",
    key: str | None = None,
):
    """Render a Plotly chart that reports x-axis relayout events back to Streamlit."""
    spec = json.dumps(plot_fig, cls=plotly.utils.PlotlyJSONEncoder)
    return _component_func(
        spec=spec,
        override_height=override_height,
        override_width=override_width,
        key=key,
    )
