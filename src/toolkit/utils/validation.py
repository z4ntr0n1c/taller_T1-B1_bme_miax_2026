"""Input validation utilities and policy enforcement for financial time series and portfolios.

Design Rationale and Architectural Justification:
------------------------------------------------
In quantitative finance and portfolio engineering, silent propagation of corrupted,
misaligned, or unconstrained data represents a major operational risk. Allowing arbitrary
inputs without strict structural validation can lead to:
  1. Distorted covariance matrices (singular or non-positive-definite matrices).
  2. Spurious returns or division-by-zero errors resulting from negative or zero prices.
  3. Lookahead bias and miscalculations caused by non-monotonic or duplicated timestamps.
  4. Flawed Sharpe ratios and risk estimates caused by unhandled NaNs or mixed frequencies.

Therefore, the toolkit implements a 'fail-fast with clear diagnostics' policy:
any incoming dataset must strictly adhere to structural and semantic invariants before
being admitted into the analytical layer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


class ValidationError(ValueError):
    """Custom exception raised when financial data fails validation invariants."""


def validate_price_dataframe(
    df: pd.DataFrame,
    required_columns: Sequence[str] = ("close",),
    min_observations: int = 5,
    allow_zero_prices: bool = False,
) -> bool:
    """Validate that a DataFrame satisfies the invariants required for financial time series.

    Checks enforced:
      1. Instance type: Must be a pandas DataFrame.
      2. Non-emptiness and minimum observation count.
      3. Index type: Must have a DatetimeIndex.
      4. Temporal order: Index must be monotonically increasing.
      5. Index uniqueness: No duplicated timestamps allowed.
      6. Required columns: Must contain specified columns (e.g. 'close').
      7. Numeric types: Target columns must be numeric floats/ints.
      8. Semantic sanity: Prices must be strictly positive (> 0) unless explicitly allowed.

    Args:
        df: DataFrame to validate.
        required_columns: Sequence of column names that must be present.
        min_observations: Minimum acceptable number of rows.
        allow_zero_prices: Whether to permit prices <= 0 (default: False).

    Returns:
        True if all invariants pass.

    Raises:
        ValidationError: If any structural or semantic invariant is violated.
    """
    if not isinstance(df, pd.DataFrame):
        raise ValidationError(f"Expected pandas DataFrame, got {type(df).__name__}.")

    if df.empty:
        raise ValidationError("DataFrame is empty; cannot ingest empty time series.")

    if len(df) < min_observations:
        raise ValidationError(
            f"Insufficient observations: got {len(df)}, minimum required is {min_observations}."
        )

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValidationError(
            f"DataFrame index must be a pd.DatetimeIndex, but found {type(df.index).__name__}. "
            "Ensure dates are parsed using pd.to_datetime()."
        )

    if not df.index.is_monotonic_increasing:
        raise ValidationError(
            "Temporal ordering violated: DataFrame index must be monotonically increasing."
        )

    if df.index.has_duplicates:
        duplicated_dates = df.index[df.index.duplicated()].unique().tolist()
        raise ValidationError(
            f"Duplicate timestamps detected in index: {duplicated_dates[:5]}. "
            "Financial time series must have strictly unique observation dates."
        )

    req_index = pd.Index(required_columns)
    missing_cols = req_index[~req_index.isin(df.columns)]
    if not missing_cols.empty:
        raise ValidationError(
            f"Missing required column '{missing_cols[0]}'. Available columns: {list(df.columns)}."
        )

    numeric_mask = df[list(required_columns)].dtypes.map(pd.api.types.is_numeric_dtype)
    if not numeric_mask.all():
        bad_col = str(numeric_mask.index[~numeric_mask][0])
        raise ValidationError(
            f"Column '{bad_col}' must contain numeric data, but has dtype '{df[bad_col].dtype}'."
        )

    req_values = df[list(required_columns)].to_numpy(dtype=float, na_value=np.nan)
    finite_col_mask = np.isfinite(req_values).all(axis=0)
    if not finite_col_mask.all():
        bad_col = str(req_index[~finite_col_mask][0])
        raise ValidationError(f"Column '{bad_col}' contains missing or non-finite values.")

    if "close" in req_index and not allow_zero_prices:
        non_positive = int(np.sum(df["close"].to_numpy(dtype=float) <= 0))
        if non_positive > 0:
            raise ValidationError(
                f"Column 'close' contains {non_positive} non-positive values (<= 0). "
                "Financial asset prices must be strictly positive."
            )

    return True


def validate_portfolio_weights(
    weights: Mapping[str, float] | Sequence[float] | np.ndarray,
    tickers: Sequence[str],
    tolerance: float = 1e-4,
    allow_short: bool = False,
) -> dict[str, float]:
    """Validate and normalize allocation weights for a set of portfolio assets.

    Invariants checked:
      1. Correct dimension matching asset count.
      2. No NaN or infinite values.
      3. Non-negative weights unless short positions are permitted.
      4. Non-zero aggregate sum.

    Args:
        weights: Dictionary of {ticker: weight} or numeric sequence.
        tickers: Sequence of expected ticker symbols.
        tolerance: Numerical tolerance for checking if sum equals 1.0.
        allow_short: Whether to permit negative weights (short positions).

    Returns:
        Normalized dictionary mapping ticker -> weight summing to 1.0.

    Raises:
        ValidationError: If weight specification is invalid.
    """
    n_assets = len(tickers)
    tickers_arr = np.asarray(tickers, dtype=str)

    if isinstance(weights, Mapping):
        missing = set(tickers) - set(weights.keys())
        if missing:
            raise ValidationError(
                f"Weights dictionary is missing tickers: {sorted(missing)}"
            )
        raw_vals = pd.Series(weights).reindex(tickers).to_numpy(dtype=float)
    elif isinstance(weights, (Sequence, np.ndarray)) and not isinstance(weights, (str, bytes)):
        if len(weights) != n_assets:
            raise ValidationError(
                f"Weights length ({len(weights)}) does not match asset count ({n_assets})."
            )
        raw_vals = np.asarray(weights, dtype=float)
    else:
        raise ValidationError(f"Unsupported weights type: {type(weights).__name__}.")

    if not np.all(np.isfinite(raw_vals)):
        raise ValidationError("Portfolio weights contain NaN or infinite values.")

    if not allow_short and np.any(raw_vals < 0):
        neg_mask = raw_vals < 0
        negative_weights = dict(
            zip(tickers_arr[neg_mask].tolist(), raw_vals[neg_mask].tolist(), strict=False)
        )
        raise ValidationError(
            f"Negative weights detected while allow_short=False: {negative_weights}."
        )

    total_w = float(np.sum(raw_vals))
    if abs(total_w) < 1e-9:
        raise ValidationError("Sum of portfolio weights cannot be zero.")

    normalized = np.round(raw_vals / total_w, 8)
    return dict(zip(tickers, normalized.tolist(), strict=False))
