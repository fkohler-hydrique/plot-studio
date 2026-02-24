import os
import json
import uuid
import datetime
import difflib
from typing import List, Optional, Dict, Any, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pandas.api.types import is_object_dtype
import streamlit as st

# -------------------- App config -------------------- #
st.set_page_config(
    page_title="CSV Plot Studio",
    page_icon="📈",
    layout="wide",
)

# -------------------- Constants -------------------- #
CANDIDATE_SEPARATORS = [",", ";", "\t", "|"]
DATE_KEYWORDS = ("date", "time", "datum", "zeit", "datetime")
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


# -------------------- Utilities -------------------- #
def detect_separator_from_sample(sample: str, decimal: str = ".") -> Optional[str]:
    """Heuristically detect the field separator from a text sample."""
    lines = [line for line in sample.splitlines() if line.strip()]
    if not lines:
        return None

    best_sep: Optional[str] = None
    best_score: float = 0.0

    for sep in CANDIDATE_SEPARATORS:
        if sep == decimal:
            continue
        counts = [line.count(sep) for line in lines[:25]]
        if not counts or max(counts) == 0:
            continue

        mean_count = sum(counts) / len(counts)
        variance = sum((c - mean_count) ** 2 for c in counts) / len(counts)
        score = mean_count - variance  # prefer consistent delimiter frequency
        if score > best_score:
            best_score = score
            best_sep = sep

    return best_sep


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns if present."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [
            " | ".join([str(x) for x in tup if str(x) != "nan"]).strip()
            for tup in df.columns
        ]
    return df


def _normalize_colname(name: str) -> str:
    if name is None:
        return ""
    s = str(name).strip().lower()
    s = s.replace("-", " ").replace("_", " ")
    s = " ".join(s.split())
    return s


def resolve_column(requested: str, available_cols: List[str]) -> Optional[str]:
    """Resolve requested column to an existing column name."""
    if not requested:
        return None
    if requested in available_cols:
        return requested

    norm_to_actual = {_normalize_colname(c): c for c in available_cols}
    req_norm = _normalize_colname(requested)

    if req_norm in norm_to_actual:
        return norm_to_actual[req_norm]

    candidates = difflib.get_close_matches(
        req_norm, list(norm_to_actual.keys()), n=1, cutoff=0.80
    )
    if candidates:
        return norm_to_actual[candidates[0]]
    return None


def guess_date_column(columns: List[str]) -> Optional[str]:
    """Guess a date/time column based on name keywords."""
    for c in columns:
        cn = _normalize_colname(c)
        if any(k in cn for k in DATE_KEYWORDS):
            return c
    return None


def parse_dates_flexible(
    df: pd.DataFrame,
    date_col: Optional[str],
    dayfirst: bool = False,
    date_format: Optional[str] = None,
) -> pd.DataFrame:
    """Parse dates with optional manual overrides."""
    if date_col is None or date_col not in df.columns:
        return df

    df = df.copy()
    try:
        if date_format:
            df[date_col] = pd.to_datetime(
                df[date_col], format=date_format, errors="coerce"
            )
        else:
            df[date_col] = pd.to_datetime(
                df[date_col], dayfirst=dayfirst, errors="coerce"
            )
    except Exception:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    return df


def load_saved_configs_from_disk() -> List[dict]:
    if not os.path.exists(SAVED_CONFIGS_FILE):
        return []
    try:
        with open(SAVED_CONFIGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [c for c in data if isinstance(c, dict)]
    except Exception:
        pass
    return []


def persist_saved_configs_to_disk(saved_configs: List[dict]) -> None:
    try:
        with open(SAVED_CONFIGS_FILE, "w", encoding="utf-8") as f:
            json.dump(saved_configs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def build_plot_spec_from_builder(
    *,
    title: Optional[str],
    x_col: str,
    y_cols: List[str],
    plot_type: str,
    template: str,
    enable_secondary_axis: bool,
    y2_cols: List[str],
    yaxis_title_1: Optional[str],
    yaxis_title_2: Optional[str],
    color_col: Optional[str],
    agg: Optional[str],
    series_style: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "title": title or None,
        "x_col": x_col,
        "y_cols": y_cols,
        "y2_cols": y2_cols if enable_secondary_axis else [],
        "plot_type": plot_type,
        "template": template,
        "yaxis_title_1": yaxis_title_1 or None,
        "yaxis_title_2": yaxis_title_2 or None,
        "color_col": color_col or None,
        "agg": agg or None,
        "series_style": series_style or {},
    }


def _to_numeric_safe(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c in df.columns and is_object_dtype(df[c]):
            df[c] = pd.to_numeric(df[c], errors="ignore")
    return df


def apply_axis_titles(
    fig, title_y1: Optional[str] = None, title_y2: Optional[str] = None
):
    updates = {}
    if title_y1:
        updates["yaxis"] = dict(title=title_y1)
    if title_y2:
        updates["yaxis2"] = dict(title=title_y2)
    if updates:
        fig.update_layout(**updates)


def apply_series_styles(
    fig: go.Figure, series_style: Dict[str, Dict[str, Any]]
) -> None:
    """Apply per-trace styling (color/width/dash) to a Plotly figure.

    `series_style` maps trace name (typically the column name) to style dict.
    """
    if not series_style:
        return

    for tr in fig.data:
        name = getattr(tr, "name", None)
        if not name:
            continue
        # For Y2 we sometimes suffix in the trace name; try exact then strip common suffix.
        style = series_style.get(name)
        if style is None and name.endswith(" (Y2)"):
            style = series_style.get(name[:-5])  # strip " (Y2)"
        if not style:
            continue

        color = style.get("color")
        width = style.get("width")
        dash = style.get("dash")

        # Lines
        if hasattr(tr, "line"):
            line_updates: Dict[str, Any] = {}
            if color:
                line_updates["color"] = color
            if isinstance(width, (int, float)):
                line_updates["width"] = float(width)
            if dash:
                line_updates["dash"] = dash
            if line_updates:
                tr.update(line=line_updates)

        # Markers (for scatter)
        if hasattr(tr, "marker") and color:
            try:
                tr.update(marker=dict(color=color))
            except Exception:
                pass

        # Bars
        if tr.type == "bar" and color:
            try:
                tr.update(marker=dict(color=color))
            except Exception:
                pass


def make_figure(
    df: pd.DataFrame,
    spec: Dict[str, Any],
) -> go.Figure:
    """Create a plotly figure based on a plot spec."""
    x = spec.get("x_col")
    y_cols = spec.get("y_cols") or []
    y2_cols = spec.get("y2_cols") or []
    plot_type = spec.get("plot_type", "Line")
    template = spec.get("template", "plotly")
    title = spec.get("title") or None
    color_col = spec.get("color_col") or None
    agg = spec.get("agg") or None
    series_style = spec.get("series_style") or {}

    # optional aggregation (simple, for x categories)
    plot_df = df
    if agg and x and (y_cols or y2_cols):
        agg_cols = list(dict.fromkeys(y_cols + y2_cols))
        # Only attempt groupby if x is not datetime-like continuous, or user explicitly wants it.
        try:
            grouped = plot_df.groupby(x, dropna=False)[agg_cols]
            if agg == "mean":
                plot_df = grouped.mean(numeric_only=True).reset_index()
            elif agg == "sum":
                plot_df = grouped.sum(numeric_only=True).reset_index()
            elif agg == "min":
                plot_df = grouped.min(numeric_only=True).reset_index()
            elif agg == "max":
                plot_df = grouped.max(numeric_only=True).reset_index()
            elif agg == "median":
                plot_df = grouped.median(numeric_only=True).reset_index()
        except Exception:
            # If aggregation fails, fall back to raw df
            plot_df = df

    plot_df = _to_numeric_safe(plot_df, list(dict.fromkeys(y_cols + y2_cols)))

    # Single axis via plotly express
    if not y2_cols:
        if plot_type == "Line":
            fig = px.line(
                plot_df,
                x=x,
                y=y_cols,
                color=color_col,
                template=template if template != "none" else None,
                title=title,
            )
        elif plot_type == "Scatter":
            fig = px.scatter(
                plot_df,
                x=x,
                y=y_cols,
                color=color_col,
                template=template if template != "none" else None,
                title=title,
            )
        elif plot_type == "Bar":
            fig = px.bar(
                plot_df,
                x=x,
                y=y_cols,
                color=color_col,
                template=template if template != "none" else None,
                title=title,
            )
        elif plot_type == "Area":
            fig = px.area(
                plot_df,
                x=x,
                y=y_cols,
                color=color_col,
                template=template if template != "none" else None,
                title=title,
            )
        else:
            fig = px.line(
                plot_df,
                x=x,
                y=y_cols,
                color=color_col,
                template=template if template != "none" else None,
                title=title,
            )
        apply_axis_titles(fig, spec.get("yaxis_title_1"), None)
        apply_series_styles(fig, series_style)
        fig.update_layout(margin=dict(l=10, r=10, t=50 if title else 20, b=10))
        return fig

    # Secondary axis: build manually with graph_objects
    fig = go.Figure()
    if template != "none":
        fig.update_layout(template=template)
    if title:
        fig.update_layout(title=title)

    # primary series
    for col in y_cols:
        style = series_style.get(col, {})
        if plot_type in ("Line", "Area"):
            fig.add_trace(
                go.Scatter(
                    x=plot_df[x],
                    y=plot_df[col],
                    mode="lines",
                    name=col,
                    yaxis="y1",
                    line=dict(
                        color=style.get("color") or None,
                        width=float(style.get("width"))
                        if isinstance(style.get("width"), (int, float))
                        else None,
                        dash=style.get("dash") or None,
                    ),
                )
            )
        elif plot_type == "Scatter":
            fig.add_trace(
                go.Scatter(
                    x=plot_df[x],
                    y=plot_df[col],
                    mode="markers",
                    name=col,
                    yaxis="y1",
                    marker=dict(color=style.get("color") or None),
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    x=plot_df[x],
                    y=plot_df[col],
                    name=col,
                    yaxis="y1",
                    marker=dict(color=style.get("color") or None),
                )
            )

    # secondary series
    for col in y2_cols:
        style = series_style.get(col, {})
        trace_name = f"{col} (Y2)"
        if plot_type in ("Line", "Area"):
            fig.add_trace(
                go.Scatter(
                    x=plot_df[x],
                    y=plot_df[col],
                    mode="lines",
                    name=trace_name,
                    yaxis="y2",
                    line=dict(
                        color=style.get("color") or None,
                        width=float(style.get("width"))
                        if isinstance(style.get("width"), (int, float))
                        else None,
                        dash=style.get("dash") or None,
                    ),
                )
            )
        elif plot_type == "Scatter":
            fig.add_trace(
                go.Scatter(
                    x=plot_df[x],
                    y=plot_df[col],
                    mode="markers",
                    name=trace_name,
                    yaxis="y2",
                    marker=dict(color=style.get("color") or None),
                )
            )
        else:
            fig.add_trace(
                go.Bar(
                    x=plot_df[x],
                    y=plot_df[col],
                    name=trace_name,
                    yaxis="y2",
                    marker=dict(color=style.get("color") or None),
                )
            )

    fig.update_layout(
        yaxis=dict(title=spec.get("yaxis_title_1") or None),
        yaxis2=dict(
            title=spec.get("yaxis_title_2") or None,
            overlaying="y",
            side="right",
        ),
        margin=dict(l=10, r=10, t=50 if title else 20, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def render_plot_from_spec(
    df: pd.DataFrame, spec: Dict[str, Any], available_cols: List[str]
) -> Tuple[Optional[go.Figure], List[str]]:
    """Resolve columns, render figure; return (fig, warnings)."""
    warnings: List[str] = []

    # Resolve columns against current df
    x_req = spec.get("x_col")
    x = resolve_column(x_req, available_cols) if x_req else None
    if not x:
        warnings.append(f"Missing X column: '{x_req}'")
        return None, warnings

    y_req = spec.get("y_cols") or []
    y = []
    for c in y_req:
        resolved = resolve_column(c, available_cols)
        if resolved:
            y.append(resolved)
        else:
            warnings.append(f"Missing Y column: '{c}'")

    y2_req = spec.get("y2_cols") or []
    y2 = []
    for c in y2_req:
        resolved = resolve_column(c, available_cols)
        if resolved:
            y2.append(resolved)
        else:
            warnings.append(f"Missing Y2 column: '{c}'")

    if not y and not y2:
        warnings.append("No Y columns could be resolved.")
        return None, warnings

    # Create a copy spec with resolved columns
    resolved_spec = dict(spec)
    resolved_spec["x_col"] = x
    resolved_spec["y_cols"] = y
    resolved_spec["y2_cols"] = y2
    fig = make_figure(df, resolved_spec)
    return fig, warnings


def make_column_preview_figure(
    series: pd.Series,
    x_series: Optional[pd.Series] = None,
    x_label: Optional[str] = None,
) -> Optional[go.Figure]:
    """Create a compact preview chart for one column."""
    try:
        sample = series

        if pd.api.types.is_numeric_dtype(sample):
            values = pd.to_numeric(sample, errors="coerce")

            if x_series is not None:
                x_name = x_label or "x"
                x_values = pd.to_datetime(x_series, errors="coerce")
                plot_df = pd.DataFrame({x_name: x_values, "value": values}).dropna()
                if not plot_df.empty:
                    plot_df = plot_df.sort_values(by=x_name)
                    fig = px.line(plot_df, x=x_name, y="value", template="plotly_white")
                else:
                    plot_df = pd.DataFrame(
                        {"idx": range(len(values)), "value": values}
                    ).dropna()
                    if plot_df.empty:
                        return None
                    fig = px.line(plot_df, x="idx", y="value", template="plotly_white")
            else:
                plot_df = pd.DataFrame(
                    {"idx": range(len(values)), "value": values}
                ).dropna()
                if plot_df.empty:
                    return None
                fig = px.line(plot_df, x="idx", y="value", template="plotly_white")
        elif pd.api.types.is_datetime64_any_dtype(sample):
            dt = pd.to_datetime(sample, errors="coerce").dropna()
            if dt.empty:
                return None
            counts = dt.dt.date.value_counts().sort_index()
            plot_df = counts.rename_axis("date").reset_index(name="count")
            fig = px.line(plot_df, x="date", y="count", template="plotly_white")
        else:
            text = sample.astype("string").fillna("<NA>")
            counts = text.value_counts(dropna=False).head(15)
            if counts.empty:
                return None
            plot_df = counts.rename_axis("value").reset_index(name="count")
            fig = px.bar(plot_df, x="value", y="count", template="plotly_white")

        fig.update_layout(height=185, margin=dict(l=8, r=8, t=8, b=8), showlegend=False)
        fig.update_xaxes(title=None)
        fig.update_yaxes(title=None)
        return fig
    except Exception:
        return None


# -------------------- Session state -------------------- #
if "saved_configs" not in st.session_state:
    st.session_state["saved_configs"] = load_saved_configs_from_disk()

if "df" not in st.session_state:
    st.session_state["df"] = None

if "file_label" not in st.session_state:
    st.session_state["file_label"] = ""

if "active_dashboard_id" not in st.session_state:
    st.session_state["active_dashboard_id"] = None

if "read_date_col" not in st.session_state:
    st.session_state["read_date_col"] = None

if "read_dayfirst" not in st.session_state:
    st.session_state["read_dayfirst"] = False

if "read_date_format" not in st.session_state:
    st.session_state["read_date_format"] = ""

# -------------------- UI: Header -------------------- #
st.markdown(
    """
    <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:12px; margin-bottom: 6px;">
      <div>
        <div style="font-size: 28px; font-weight: 800; line-height: 1.0;">📈 CSV Plot Studio</div>
        <div style="font-size: 14px; opacity: 0.85; margin-top: 6px;">
          Build reusable dashboard templates for any CSV — no plot snapshot saving.
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -------------------- Sidebar: Data + Templates -------------------- #
with st.sidebar:
    with st.expander("Data", expanded=True):
        up = st.file_uploader(
            "Upload CSV", type=["csv"], help="Upload a CSV file from your computer."
        )
        path = st.text_input(
            "…or path on server",
            value="",
            help="If Streamlit runs where the file exists, you can provide a filesystem path.",
        )

        st.markdown("##### Dashboard template")
        configs = st.session_state["saved_configs"]
        if configs:
            name_by_id = {c.get("id"): c.get("name", "Unnamed") for c in configs}
            ordered = sorted(configs, key=lambda c: (c.get("name") or "").lower())
            options = [None] + [c.get("id") for c in ordered]
            idx = 0
            if st.session_state["active_dashboard_id"] in options:
                idx = options.index(st.session_state["active_dashboard_id"])
            active_id = st.selectbox(
                "Active template",
                options=options,
                format_func=lambda v: (
                    "(none)" if v is None else name_by_id.get(v, "Unnamed")
                ),
                index=idx,
            )
            st.session_state["active_dashboard_id"] = active_id
        else:
            st.info("No templates yet. Build one in **Plot Builder** and save it.")
            st.session_state["active_dashboard_id"] = None

        st.caption(
            "Templates are saved to `saved_configs.json` (re-rendered on the current CSV)."
        )

    st.divider()

    with st.expander("Reading options", expanded=False):
        sep_label = st.selectbox(
            "Separator",
            ["Auto-detect", "Comma (,)", "Semicolon (;)", "Tab (\\t)", "Pipe (|)"],
            index=0,
        )
        sep_map = {
            "Auto-detect": None,
            "Comma (,)": ",",
            "Semicolon (;)": ";",
            "Tab (\\t)": "\t",
            "Pipe (|)": "|",
        }
        sep = sep_map[sep_label]

        decimal_label = st.selectbox("Decimal", ["Dot (.)", "Comma (,)"], index=0)
        decimal = "." if decimal_label == "Dot (.)" else ","

        header_label = st.selectbox(
            "Header",
            [
                "First row",
                "Second row (skip first)",
                "Two rows (multi header)",
                "No header",
            ],
            index=0,
        )
        header = 0
        skiprows = None
        if header_label == "First row":
            header, skiprows = 0, None
        elif header_label == "Second row (skip first)":
            header, skiprows = 0, [0]
        elif header_label == "Two rows (multi header)":
            header, skiprows = [0, 1], None
        elif header_label == "No header":
            header, skiprows = None, None

        st.markdown("##### Date parsing")
        sidebar_df = st.session_state.get("df")
        sidebar_cols = (
            list(sidebar_df.columns) if isinstance(sidebar_df, pd.DataFrame) else []
        )
        sidebar_date_guess = guess_date_column(sidebar_cols) if sidebar_cols else None
        date_options = [None] + sidebar_cols if sidebar_cols else [None]

        current_sidebar_date_col = st.session_state.get("read_date_col")
        if current_sidebar_date_col not in date_options:
            current_sidebar_date_col = (
                sidebar_date_guess if sidebar_date_guess in date_options else None
            )
            st.session_state["read_date_col"] = current_sidebar_date_col

        st.selectbox(
            "Date/time column (optional)",
            options=date_options,
            index=date_options.index(current_sidebar_date_col)
            if current_sidebar_date_col in date_options
            else 0,
            key="read_date_col",
            format_func=lambda v: "(none)" if v is None else str(v),
            disabled=(len(sidebar_cols) == 0),
            help="Used for date parsing, mini-plots x-axis, and Plot Builder date filtering.",
        )
        st.toggle(
            "Day-first dates (e.g. 31/01/2024)",
            key="read_dayfirst",
            help="Helps parsing for some European date formats.",
        )
        st.text_input(
            "Optional date format (advanced)",
            key="read_date_format",
            help="Example: %d/%m/%Y. Leave blank for auto parsing.",
        )

# -------------------- Data loading -------------------- #
def read_csv_input(
    uploaded_file, csv_path: str
) -> Tuple[Optional[pd.DataFrame], str, Optional[str]]:
    """Read CSV from upload or path. Returns (df, label, error)."""
    if uploaded_file is None and not (csv_path or "").strip():
        return None, "", None

    try:
        if uploaded_file is not None:
            raw_bytes = uploaded_file.getvalue()
            label = uploaded_file.name
            sample = raw_bytes[:30_000].decode("utf-8", errors="ignore")
            inferred_sep = detect_separator_from_sample(sample, decimal=decimal)
            effective_sep = inferred_sep if sep is None else sep
            df = pd.read_csv(
                uploaded_file,
                sep=effective_sep,
                decimal=decimal,
                header=header,
                skiprows=skiprows,
                engine="python",
            )
        else:
            label = os.path.basename(csv_path.strip())
            with open(csv_path.strip(), "rb") as f:
                raw_bytes = f.read()
            sample = raw_bytes[:30_000].decode("utf-8", errors="ignore")
            inferred_sep = detect_separator_from_sample(sample, decimal=decimal)
            effective_sep = inferred_sep if sep is None else sep
            df = pd.read_csv(
                csv_path.strip(),
                sep=effective_sep,
                decimal=decimal,
                header=header,
                skiprows=skiprows,
                engine="python",
            )

        df = _flatten_columns(df)

        # attempt stripping whitespace in string columns
        for col in df.columns:
            if col in df and is_object_dtype(df[col]):
                df[col] = df[col].astype(str).str.strip()

        return df, label, None
    except Exception as e:
        return None, "", str(e)


df, label, err = read_csv_input(up, path)
if err:
    st.error(f"Could not read CSV: {err}")
elif df is not None:
    st.session_state["df"] = df
    st.session_state["file_label"] = label

df = st.session_state["df"]

# -------------------- Main content -------------------- #
if df is None:
    st.info("Upload a CSV (or provide a server path) to start.")
    st.stop()

cols = list(df.columns)
date_guess = guess_date_column(cols)

date_col_state = st.session_state.get("read_date_col")
date_col = (
    date_col_state
    if date_col_state in cols
    else (date_guess if date_guess in cols else None)
)

dayfirst = bool(st.session_state.get("read_dayfirst", False))
date_format_input = (st.session_state.get("read_date_format", "") or "").strip()
date_format = date_format_input or None
df_parsed = parse_dates_flexible(
    df, date_col, dayfirst=dayfirst, date_format=date_format
)

# Top summary row
left, right = st.columns([2, 1], vertical_alignment="top")
with left:
    st.markdown(f"#### Data: `{st.session_state['file_label'] or 'CSV'}`")
with right:
    st.markdown("")
    st.caption("Tip: Use **Dashboard** for consistent plots across different CSVs.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Rows", f"{len(df):,}")
m2.metric("Columns", f"{len(cols):,}")
m3.metric("Missing cells", f"{int(df.isna().sum().sum()):,}")
m4.metric("Memory (approx.)", f"{df.memory_usage(deep=True).sum() / (1024**2):.1f} MB")

st.divider()

tabs = st.tabs(["🔎 Preview", "🛠️ Plot Builder", "🧩 Dashboard", "⚙️ Templates"])

# -------------------- Preview tab -------------------- #
with tabs[0]:
    c1, c2 = st.columns([1.1, 1], vertical_alignment="top")
    with c1:
        st.markdown("##### Quick preview")
        st.dataframe(df.head(200), width="stretch", height=420)
    with c2:
        st.markdown("##### Columns & types")
        info_df = pd.DataFrame(
            {"column": cols, "dtype": [str(df[c].dtype) for c in cols]}
        )
        st.dataframe(info_df, width="stretch", height=420)
    with st.expander("Show summary statistics", expanded=False):
        st.dataframe(df.describe(include="all").transpose(), width="stretch")

    with st.expander("Column mini plots (all columns)", expanded=False):
        preview_x_col = date_col if date_col in cols else None
        preview_x_series = None
        if preview_x_col:
            parsed_x = df_parsed[preview_x_col]
            if (
                pd.api.types.is_datetime64_any_dtype(parsed_x)
                and parsed_x.notna().sum() > 0
            ):
                preview_x_series = parsed_x
            else:
                preview_x_col = None

        mini_plot_cols = [c for c in cols if c != preview_x_col]
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
                        df[col],
                        x_series=preview_x_series,
                        x_label=preview_x_col,
                    )
                    if mini_fig is not None:
                        idx = start + offset
                        st.plotly_chart(
                            mini_fig,
                            width="stretch",
                            key=f"preview_mini_{idx}_{_normalize_colname(col)}",
                        )
                    else:
                        st.caption("No preview available.")

# -------------------- Plot Builder tab -------------------- #
with tabs[1]:
    st.markdown("#### Plot Builder")
    st.caption(
        "Build a plot and save it as a reusable template (templates re-render on any CSV you load)."
    )

    with st.expander("1) Data & axes", expanded=True):
        # Date filtering UI (date options are centralized in sidebar Reading options)
        filtered_df = df_parsed
        if date_col and date_col in df_parsed.columns:
            dt = df_parsed[date_col]
            if pd.api.types.is_datetime64_any_dtype(dt):
                valid_dt = dt.dropna()
                if not valid_dt.empty:
                    min_d, max_d = valid_dt.min(), valid_dt.max()
                    r = st.slider(
                        "Filter date range",
                        min_value=min_d.to_pydatetime(),
                        max_value=max_d.to_pydatetime(),
                        value=(min_d.to_pydatetime(), max_d.to_pydatetime()),
                    )
                    filtered_df = df_parsed[
                        (df_parsed[date_col] >= r[0]) & (df_parsed[date_col] <= r[1])
                    ]

        x_default = date_col if (date_col in cols) else cols[0]
        x_col = st.selectbox(
            "X axis",
            options=cols,
            index=cols.index(x_default) if x_default in cols else 0,
        )

        numeric_candidates = [
            c for c in cols if pd.api.types.is_numeric_dtype(df_parsed[c])
        ]
        y_candidates = numeric_candidates if numeric_candidates else cols
        y_cols = st.multiselect(
            "Y axis (primary)",
            options=cols,
            default=[c for c in y_candidates[:1] if c in cols],
        )

        st.markdown("##### Plot options")
        plot_type = st.radio("Type", options=PLOT_TYPES, horizontal=True, index=0)

        enable_y2 = st.toggle("Enable secondary Y axis", value=False)
        y2_cols = []
        if enable_y2:
            y2_cols = st.multiselect(
                "Y axis (secondary)",
                options=[c for c in cols if c not in y_cols],
                default=[],
            )

        color_col = st.selectbox(
            "Color/group by (optional)", options=[None] + cols, index=0
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

    # Per-series styling in the left taskbar (sidebar)
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
            style_map: Dict[str, Dict[str, Any]] = {}
            series_list = list(dict.fromkeys((y_cols or []) + (y2_cols or [])))
            if not series_list:
                st.info("Select Y columns to customize them.")
            for idx, s in enumerate(series_list):
                safe = _normalize_colname(s).replace(" ", "_") or "series"
                default_color = DEFAULT_SERIES_COLORS[idx % len(DEFAULT_SERIES_COLORS)]
                color_key = f"sty_{safe}_color"
                if color_key not in st.session_state:
                    st.session_state[color_key] = default_color
                st.markdown(f"**{s}**")
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
                style_map[s] = {"color": color, "width": width, "dash": dash}
                st.markdown("")

    with st.expander("2) Styling", expanded=False):
        template = st.selectbox(
            "Theme", options=TEMPLATES, index=TEMPLATES.index("plotly_white")
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
    warnings = []
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
                filtered_df, spec, list(filtered_df.columns)
            )
            if warnings:
                with st.expander("Warnings", expanded=False):
                    for w in warnings:
                        st.warning(w)

            if fig is not None:
                # Full-width plot (stable unique key to avoid StreamlitDuplicateElementId)
                st.plotly_chart(fig, width="stretch", key="plot_builder_preview")
        except Exception as e:
            st.error(f"Error generating plot: {e}")

    st.divider()
    st.markdown("#### Save as dashboard template")
    st.caption("Templates re-render on any CSV you load (with fuzzy column matching).")
    dash_name = st.text_input(
        "Template name", value="", placeholder="e.g. Discharge dashboard"
    )
    plot_label = st.text_input(
        "Plot label (optional)", value="", placeholder="e.g. Q (m³/s) vs time"
    )

    save_disabled = (fig is None) or (not (dash_name or "").strip())
    if st.button(
        "Save template (single plot)", width="stretch", disabled=save_disabled
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

# -------------------- Dashboard tab -------------------- #
with tabs[2]:
    st.markdown("#### Dashboard")
    st.caption(
        "Select an active template in the sidebar. The dashboard re-renders on the current dataset."
    )

    active_id = st.session_state.get("active_dashboard_id")
    configs = st.session_state["saved_configs"]
    cfg = (
        next((c for c in configs if c.get("id") == active_id), None)
        if active_id
        else None
    )

    if not cfg:
        st.info(
            "No active template selected. Choose one in the sidebar, or create one in **Plot Builder**."
        )
    else:
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
            st.warning("This template contains no plots.")
        else:
            # Optional global date parsing + filtering for dashboard
            st.divider()
            with st.expander("Global dashboard options", expanded=False):
                date_col = st.selectbox(
                    "Date/time column for dashboard (optional)",
                    options=[None] + cols,
                    index=0
                    if date_guess is None
                    else ([None] + cols).index(date_guess),
                )
                dayfirst = st.toggle(
                    "Day-first dates", value=False, key="dash_dayfirst"
                )
                date_format = st.text_input(
                    "Optional date format", value="", key="dash_dateformat"
                )
                dash_df = parse_dates_flexible(
                    df, date_col, dayfirst=dayfirst, date_format=(date_format or None)
                )

                dash_filtered = dash_df
                if date_col and date_col in dash_df.columns:
                    dt = dash_df[date_col]
                    if pd.api.types.is_datetime64_any_dtype(dt):
                        valid_dt = dt.dropna()
                        if not valid_dt.empty:
                            min_d, max_d = valid_dt.min(), valid_dt.max()
                            r = st.slider(
                                "Filter date range",
                                min_value=min_d.to_pydatetime(),
                                max_value=max_d.to_pydatetime(),
                                value=(min_d.to_pydatetime(), max_d.to_pydatetime()),
                                key="dash_dateslider",
                            )
                            dash_filtered = dash_df[
                                (dash_df[date_col] >= r[0])
                                & (dash_df[date_col] <= r[1])
                            ]
                # store
                st.session_state["dash_df_filtered"] = dash_filtered

            dash_filtered = st.session_state.get("dash_df_filtered", df)
            available_cols = list(dash_filtered.columns)

            # Render plots in a modern card-like layout
            for i, spec in enumerate(plots, start=1):
                with st.container(border=True):
                    title = spec.get("title") or f"Plot {i}"
                    st.markdown(f"**{title}**")
                    fig, warns = render_plot_from_spec(
                        dash_filtered, spec, available_cols
                    )
                    if warns:
                        with st.expander("Column resolution warnings", expanded=False):
                            for w in warns:
                                st.warning(w)
                            st.caption(
                                "Tip: You can fix this by editing the template JSON in the Templates tab."
                            )
                    if fig is not None:
                        # Unique per rendered dashboard plot
                        cfg_id = (cfg or {}).get("id", "cfg")
                        st.plotly_chart(
                            fig, width="stretch", key=f"dash_plot_{cfg_id}_{i}"
                        )
                    else:
                        st.error("Could not render this plot on the current dataset.")

# -------------------- Templates tab -------------------- #
with tabs[3]:
    st.markdown("#### Templates")
    st.caption("Manage templates (rename, delete, export/import, edit JSON).")

    configs = st.session_state["saved_configs"]
    if not configs:
        st.info("No templates saved yet.")
    else:
        # Select template
        ordered = sorted(configs, key=lambda c: (c.get("name") or "").lower())
        id_to_cfg = {c.get("id"): c for c in ordered}
        sel_id = st.selectbox(
            "Select template",
            options=[c.get("id") for c in ordered],
            format_func=lambda v: id_to_cfg[v].get("name", "Unnamed"),
        )
        sel = id_to_cfg.get(sel_id)

        c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="top")
        with c1:
            new_name = st.text_input("Rename", value=sel.get("name", ""))
            if st.button("Apply rename", width="stretch"):
                sel["name"] = new_name.strip() or sel.get("name", "")
                persist_saved_configs_to_disk(configs)
                st.success("Renamed.")
        with c2:
            st.download_button(
                "Export selected (JSON)",
                data=json.dumps(sel, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"{_normalize_colname(sel.get('name', 'template')).replace(' ', '_') or 'template'}.json",
                mime="application/json",
                width="stretch",
            )
        with c3:
            if st.button("Delete selected", type="secondary", width="stretch"):
                st.session_state["saved_configs"] = [
                    c for c in configs if c.get("id") != sel_id
                ]
                persist_saved_configs_to_disk(st.session_state["saved_configs"])
                if st.session_state.get("active_dashboard_id") == sel_id:
                    st.session_state["active_dashboard_id"] = None
                st.success("Deleted.")
                st.rerun()

        st.divider()

        with st.expander("Edit template JSON (advanced)", expanded=False):
            edited = st.text_area(
                "Template JSON",
                value=json.dumps(sel, ensure_ascii=False, indent=2),
                height=380,
            )
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Validate JSON", width="stretch"):
                    try:
                        _ = json.loads(edited)
                        st.success("Valid JSON.")
                    except Exception as e:
                        st.error(f"Invalid JSON: {e}")
            with col_b:
                if st.button("Save JSON to template", width="stretch"):
                    try:
                        new_obj = json.loads(edited)
                        if not isinstance(new_obj, dict):
                            st.error("Template JSON must be an object.")
                        else:
                            # preserve ID if missing
                            new_obj.setdefault("id", sel_id)
                            # replace in list
                            new_configs = []
                            for c in configs:
                                if c.get("id") == sel_id:
                                    new_configs.append(new_obj)
                                else:
                                    new_configs.append(c)
                            st.session_state["saved_configs"] = new_configs
                            persist_saved_configs_to_disk(new_configs)
                            st.success("Template updated.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Could not save: {e}")

        st.divider()
        st.markdown("##### Import template JSON")
        upl = st.file_uploader(
            "Import a template (.json)", type=["json"], key="import_json"
        )
        if upl is not None:
            try:
                imported = json.loads(upl.getvalue().decode("utf-8"))
                if not isinstance(imported, dict):
                    st.error("Imported file must be a JSON object.")
                else:
                    imported.setdefault("id", str(uuid.uuid4()))
                    imported.setdefault(
                        "created_at", datetime.datetime.utcnow().isoformat() + "Z"
                    )
                    imported.setdefault("plots", [])
                    st.session_state["saved_configs"].append(imported)
                    persist_saved_configs_to_disk(st.session_state["saved_configs"])
                    st.success("Imported template.")
            except Exception as e:
                st.error(f"Import failed: {e}")
