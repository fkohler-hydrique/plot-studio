import pandas as pd

from plot_studio.plotting.figures import (
    make_column_preview_figure,
    render_plot_from_spec,
)


def test_render_plot_from_spec_returns_warning_for_missing_columns():
    df = pd.DataFrame({"time": [1, 2], "value": [10, 20]})
    spec = {"x_col": "time", "y_cols": ["missing"], "y2_cols": []}

    fig, warnings = render_plot_from_spec(df, spec, list(df.columns))

    assert fig is None
    assert warnings == [
        "Missing Y column: 'missing'",
        "No Y columns could be resolved.",
    ]


def test_make_column_preview_figure_for_numeric_series_returns_figure():
    series = pd.Series([1, 2, 3, 4])
    fig = make_column_preview_figure(series)

    assert fig is not None
    assert len(fig.data) == 1
