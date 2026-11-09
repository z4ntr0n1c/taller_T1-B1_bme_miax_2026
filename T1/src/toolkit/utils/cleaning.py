"""Data cleaning, missing value management, and multi-exchange calendar alignment routines."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd


def clean_missing_values(
    df: pd.DataFrame,
    method: str = "ffill",
    columns: Sequence[str] | None = None,
    max_consecutive_nans: int | None = 5,
) -> pd.DataFrame:
    """Clean missing values (NaNs) in financial time series according to the selected strategy.

    Strategies:
      - 'ffill': Forward-fills missing quotes (appropriate for financial time series where
                 exchange holidays imply no price change). Leading NaNs and remaining gaps
                 beyond the limit are dropped to avoid filling from future observations.
      - 'drop': Removes rows containing any NaN.
      - 'interpolate': Linearly interpolates between valid observations. Leading NaNs are dropped.

    Args:
        df: Input DataFrame with DatetimeIndex.
        method: Cleaning strategy ('ffill', 'drop', 'interpolate').
        columns: Specific columns to clean (defaults to all columns).
        max_consecutive_nans: Maximum tolerable consecutive missing days before dropping.

    Returns:
        Cleaned pd.DataFrame.

    Raises:
        ValueError: If an unsupported cleaning method is provided.
    """
    df_clean = df.copy()
    target_cols = list(columns) if columns is not None else list(df.columns)

    if method == "drop":
        return df_clean.dropna(subset=target_cols)

    if method == "ffill":
        if max_consecutive_nans is not None and (
            isinstance(max_consecutive_nans, bool)
            or not isinstance(max_consecutive_nans, int)
            or max_consecutive_nans < 1
        ):
            raise ValueError("max_consecutive_nans must be a positive integer or None.")

        df_clean[target_cols] = df_clean[target_cols].ffill(limit=max_consecutive_nans)
        return df_clean.dropna(subset=target_cols)

    if method == "interpolate":
        df_clean[target_cols] = df_clean[target_cols].interpolate(method="time")
        return df_clean.dropna(subset=target_cols)

    raise ValueError(
        f"Unsupported cleaning method '{method}'. Choose from 'ffill', 'drop', 'interpolate'."
    )


def align_calendar_series(
    series_map: Mapping[str, pd.Series],
    join_method: str = "inner",
) -> pd.DataFrame:
    """Synchronize and align multiple asset time series originating from different exchange calendars.

    For example, US markets (NYSE/NASDAQ) and European markets (BME) observe different
    bank holidays (e.g. Thanksgiving in US, Epiphany in Spain).

    Alignment Modes:
      - 'inner': Strict intersection of trading days (only days when all markets were open).
                 Preferred for econometric regressions and clean covariance estimation.
      - 'outer_ffill': Union of trading days. If an asset's exchange is closed on day t,
                       its price is carried forward from day t-1. Appropriate for continuous
                       portfolio net asset value tracking.

    Args:
        series_map: Mapping of {ticker: pd.Series} with DatetimeIndex.
        join_method: 'inner' or 'outer_ffill'.

    Returns:
        Aligned pd.DataFrame where each column corresponds to an asset ticker.

    Raises:
        ValueError: If an unknown join_method is provided.
    """
    if not series_map:
        return pd.DataFrame()

    combined = pd.DataFrame(series_map)

    if join_method == "inner":
        aligned = combined.dropna()
    elif join_method == "outer_ffill":
        aligned = combined.ffill().dropna()
    else:
        raise ValueError(f"Unknown join method '{join_method}'. Use 'inner' or 'outer_ffill'.")

    aligned.index.name = "date"
    return aligned


def filter_anomalous_returns(
    returns_series: pd.Series,
    max_abs_return: float = 1.0,
) -> tuple[pd.Series, pd.Series]:
    """Detect and isolate potential data anomalies or unadjusted split spikes.

    Args:
        returns_series: Daily percentage returns.
        max_abs_return: Maximum realistic absolute daily return (default: 1.0 = 100% intraday swing).

    Returns:
        Tuple of (clean_series, anomalies_detected).
    """
    mask = returns_series.abs() > max_abs_return
    return returns_series[~mask], returns_series[mask]
