"""PriceSeries — Standardized single-asset financial time series dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from ..utils.validation import ValidationError, validate_price_dataframe
from . import metrics

if TYPE_CHECKING:
    from .monte_carlo import MonteCarloResult


@dataclass
class PriceSeries:
    """Standardized time series container for an equity, index, or macroeconomic asset.

    Attributes:
        ticker: Asset symbol (uppercased).
        asset_type: Semantic classification (``'equity'``, ``'index'``, ``'macro'``, etc.).
        data: Date-indexed DataFrame containing ``'close'`` and ``'returns'``.
        mean_return: Arithmetic daily mean return (auto-computed).
        std_return: Sample daily return volatility (auto-computed).
    """

    ticker: str
    asset_type: str
    data: pd.DataFrame
    mean_return: float = field(init=False)
    std_return: float = field(init=False)

    def __post_init__(self) -> None:
        """Validate ``'close'`` column, ensure ``'returns'`` exist, and compute base stats."""
        validate_price_dataframe(self.data, required_columns=("close",))
        self.ticker = self.ticker.strip().upper()
        self.data = self.data.copy()
        calculated_returns = self.data["close"].pct_change(fill_method=None)
        if not np.isfinite(calculated_returns.dropna().to_numpy(dtype=float)).all():
            raise ValidationError(
                "Calculated column 'returns' contains non-finite values."
            )

        if "returns" in self.data.columns:
            if not pd.api.types.is_numeric_dtype(self.data["returns"]):
                raise ValidationError("Column 'returns' must contain numeric data.")

            provided_returns = self.data["returns"].to_numpy(dtype=float, na_value=np.nan)
            if np.isinf(provided_returns).any():
                raise ValidationError("Column 'returns' contains infinite values.")
            if self.data["returns"].dropna().empty:
                raise ValidationError(
                    "Column 'returns' must contain at least one valid observation."
                )
            if not np.allclose(
                provided_returns,
                calculated_returns.to_numpy(dtype=float),
                rtol=1e-5,
                atol=1e-8,
                equal_nan=True,
            ):
                raise ValidationError("Column 'returns' is inconsistent with 'close' prices.")

        self.data["returns"] = calculated_returns

        clean_returns = self.returns
        if clean_returns.empty:
            raise ValidationError("Column 'returns' must contain at least one valid observation.")

        self.mean_return = float(clean_returns.mean())
        self.std_return = float(clean_returns.std())
        if not np.isfinite(self.mean_return) or not np.isfinite(self.std_return):
            raise ValidationError("Calculated return statistics contain non-finite values.")

    def __len__(self) -> int:
        """Return the number of valid return observations in the series."""
        return len(self.returns)

    def __str__(self) -> str:
        return (
            f"PriceSeries({self.ticker}, type='{self.asset_type}', "
            f"obs={len(self)}, mean={self.mean_return:+.4f}, std={self.std_return:.4f})"
        )

    @property
    def returns(self) -> pd.Series:
        """Return the clean daily returns series (without NaNs)."""
        return self.data["returns"].dropna()

    @property
    def close(self) -> pd.Series:
        """Return the clean close price series (without NaNs)."""
        return self.data["close"].dropna()

    def annualized_return(self, trading_days: int = metrics.TRADING_DAYS_PER_YEAR) -> float:
        """Compute the annualized return assuming geometric compounding."""
        return metrics.compute_annualized_return(
            self.mean_return,
            has_observations=not self.returns.empty,
            trading_days=trading_days,
        )

    def annualized_volatility(self, trading_days: int = metrics.TRADING_DAYS_PER_YEAR) -> float:
        """Compute the annualized volatility (standard deviation)."""
        return metrics.compute_annualized_volatility(self.std_return, trading_days=trading_days)

    def sharpe_ratio(
        self,
        risk_free_rate: float = 0.0,
        trading_days: int = metrics.TRADING_DAYS_PER_YEAR,
    ) -> float:
        """Compute the annualized Sharpe ratio."""
        return metrics.compute_sharpe_ratio(
            self.annualized_return(trading_days),
            self.annualized_volatility(trading_days),
            risk_free_rate=risk_free_rate,
        )

    def cumulative_returns(self) -> pd.Series:
        """Compute the cumulative return series starting from 0.0."""
        return metrics.compute_cumulative_returns(self.returns)

    def drawdown_series(self) -> pd.Series:
        """Compute underwater drawdown series relative to running maximum."""
        return metrics.compute_drawdown_series(self.returns)

    def max_drawdown(self) -> float:
        """Compute maximum historical peak-to-trough decline (negative value)."""
        return metrics.compute_max_drawdown(self.returns)

    def value_at_risk(
        self,
        confidence_level: float = 0.95,
        method: str = "historical",
    ) -> float:
        """Compute daily Value at Risk (VaR) at the given confidence level."""
        return metrics.compute_value_at_risk(
            self.returns,
            confidence_level=confidence_level,
            method=method,
            mean_return=self.mean_return,
            std_return=self.std_return,
        )

    def conditional_value_at_risk(self, confidence_level: float = 0.95) -> float:
        """Compute daily Conditional Value at Risk (CVaR / Expected Shortfall)."""
        return metrics.compute_conditional_value_at_risk(
            self.returns, confidence_level=confidence_level
        )

    def simulate_montecarlo(
        self,
        n_simulations: int = 1000,
        horizon: int = metrics.TRADING_DAYS_PER_YEAR,
        mu: float | None = None,
        sigma: float | None = None,
        initial_value: float | None = None,
        seed: int | None = None,
    ) -> MonteCarloResult:
        """Simulate stochastic price trajectories using Geometric Brownian Motion (GBM)."""
        from .monte_carlo import MonteCarloEngine

        init_val = initial_value if initial_value is not None else float(self.close.iloc[-1])
        drift = mu if mu is not None else self.mean_return
        vol = sigma if sigma is not None else self.std_return

        return MonteCarloEngine.simulate_gbm(
            initial_value=init_val,
            mu=drift,
            sigma=vol,
            horizon=horizon,
            n_simulations=n_simulations,
            seed=seed,
            name=self.ticker,
        )

    def plot_montecarlo(
        self,
        n_simulations: int = 1000,
        horizon: int = metrics.TRADING_DAYS_PER_YEAR,
        save_path: str | Path | None = None,
        show: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Execute Monte Carlo simulation and render trajectory and distribution plots."""
        sim = self.simulate_montecarlo(n_simulations=n_simulations, horizon=horizon, **kwargs)
        return sim.plot(save_path=save_path, show=show)
