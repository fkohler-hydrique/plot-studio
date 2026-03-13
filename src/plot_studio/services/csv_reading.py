"""CSV parsing and loading helpers."""

import os
from collections.abc import Sequence
from typing import Any

import pandas as pd
from pandas.api.types import is_object_dtype

from plot_studio.config import CANDIDATE_SEPARATORS


def detect_separator_from_sample(sample: str, decimal: str = ".") -> str | None:
    """Heuristically detect the field separator from a text sample."""
    lines = [line for line in sample.splitlines() if line.strip()]
    if not lines:
        return None

    best_sep: str | None = None
    best_score = 0.0

    for sep in CANDIDATE_SEPARATORS:
        if sep == decimal:
            continue
        counts = [line.count(sep) for line in lines[:25]]
        if not counts or max(counts) == 0:
            continue

        mean_count = sum(counts) / len(counts)
        variance = sum((count - mean_count) ** 2 for count in counts) / len(counts)
        score = mean_count - variance
        if score > best_score:
            best_score = score
            best_sep = sep

    return best_sep


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns if present."""
    if isinstance(df.columns, pd.MultiIndex):
        flattened = df.copy()
        flattened.columns = [
            " | ".join(str(value) for value in column if str(value) != "nan").strip()
            for column in df.columns
        ]
        return flattened
    return df


def strip_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace from string-like dataframe columns."""
    stripped = df.copy()
    for col in stripped.columns:
        if col in stripped and is_object_dtype(stripped[col]):
            stripped[col] = stripped[col].astype(str).str.strip()
    return stripped


def read_csv_input(
    uploaded_file: Any,
    csv_path: str,
    *,
    decimal: str,
    sep: str | None,
    header: int | Sequence[int] | None,
    skiprows: Sequence[int] | None,
) -> tuple[pd.DataFrame | None, str, str | None]:
    """Read CSV content from an uploaded file or a filesystem path."""
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
            trimmed_path = csv_path.strip()
            label = os.path.basename(trimmed_path)
            with open(trimmed_path, "rb") as file_obj:
                raw_bytes = file_obj.read()
            sample = raw_bytes[:30_000].decode("utf-8", errors="ignore")
            inferred_sep = detect_separator_from_sample(sample, decimal=decimal)
            effective_sep = inferred_sep if sep is None else sep
            df = pd.read_csv(
                trimmed_path,
                sep=effective_sep,
                decimal=decimal,
                header=header,
                skiprows=skiprows,
                engine="python",
            )

        cleaned = flatten_columns(df)
        cleaned = strip_object_columns(cleaned)
        return cleaned, label, None
    except Exception as exc:
        return None, "", str(exc)
