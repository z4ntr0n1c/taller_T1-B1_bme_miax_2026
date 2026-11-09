"""Shared return and risk metric calculations for financial time series and portfolios.

Centralizing these pure functions eliminates duplication between :class:`PriceSeries`
and :class:`Portfolio` while guaranteeing consistent numerical definitions across the toolkit.
"""

from __future__ import annotations

from statistics import NormalDist

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def validate_confidence_level(confidence_level: float) -> None:
    """Validate a probability threshold used by VaR and related risk metrics."""
    if (
        isinstance(confidence_level, (bool, np.bool_))
        or not isinstance(confidence_level, (int, float, np.integer, np.floating))
        or not np.isfinite(confidence_level)
        or not 0.0 < confidence_level < 1.0
    ):
        raise ValueError(
            f"confidence_level must be a finite number strictly between 0 and 1, "
            f"got {confidence_level!r}."
        )


def compute_annualized_return(
    mean_return: float,
    has_observations: bool = True,
    trading_days: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Compute geometric annualized return from daily mean return."""
    if not has_observations:
        return 0.0
    return float(((1.0 + mean_return) ** trading_days) - 1.0)


def compute_annualized_volatility(
    std_return: float,
    trading_days: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Compute annualized volatility from daily return standard deviation."""
    return float(std_return * np.sqrt(trading_days))


def compute_sharpe_ratio(
    annualized_return: float,
    annualized_vol: float,
    risk_free_rate: float = 0.0,
) -> float:
    """Compute annualized Sharpe ratio given annualized return and volatility."""
    if annualized_vol == 0.0:
        return 0.0
    return float((annualized_return - risk_free_rate) / annualized_vol)


def compute_cumulative_returns(returns: pd.Series) -> pd.Series:
    """Compute cumulative return series starting from 0.0."""
    return (1.0 + returns).cumprod() - 1.0


def compute_drawdown_series(returns: pd.Series) -> pd.Series:
    """Compute underwater drawdown series relative to running wealth peak."""
    wealth = (1.0 + returns).cumprod()
    running_max = wealth.cummax().clip(lower=1.0)
    return (wealth - running_max) / running_max


def compute_max_drawdown(returns: pd.Series) -> float:
    """Compute maximum historical peak-to-trough decline (negative float)."""
    dd = compute_drawdown_series(returns)
    return float(dd.min()) if not dd.empty else 0.0


def compute_value_at_risk(
    returns: pd.Series,
    confidence_level: float = 0.95,
    method: str = "historical",
    mean_return: float | None = None,
    std_return: float | None = None,
) -> float:
    """Compute daily Value at Risk (VaR) at the specified confidence level.

    Args:
        returns: Clean daily return series.
        confidence_level: Probability threshold (e.g. ``0.95`` for 95% VaR).
        method: ``"historical"`` (empirical quantile) or ``"parametric"`` (Gaussian).
        mean_return: Optional precomputed mean return for parametric VaR.
        std_return: Optional precomputed std return for parametric VaR.

    Returns:
        Daily VaR expressed as a decimal return (typically negative).

    Raises:
        ValueError: If the confidence level or ``method`` is invalid.
    """
    validate_confidence_level(confidence_level)
    if returns.empty:
        return 0.0

    if method == "historical":
        return float(np.percentile(returns, (1.0 - confidence_level) * 100.0))

    if method == "parametric":
        mu = float(returns.mean()) if mean_return is None else mean_return
        sigma = float(returns.std()) if std_return is None else std_return
        z = NormalDist().inv_cdf(1.0 - confidence_level)
        return float(mu + z * sigma)

    raise ValueError(f"Unknown VaR method '{method}'. Use 'historical' or 'parametric'.")


def compute_conditional_value_at_risk(
    returns: pd.Series,
    confidence_level: float = 0.95,
) -> float:
    """Compute daily Conditional Value at Risk (CVaR / Expected Shortfall)."""
    validate_confidence_level(confidence_level)
    if returns.empty:
        return 0.0
    var = compute_value_at_risk(returns, confidence_level=confidence_level, method="historical")
    tail = returns[returns <= var]
    return float(tail.mean()) if not tail.empty else var
