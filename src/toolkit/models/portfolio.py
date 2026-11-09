"""Portfolio — DataClass representing an investment portfolio composed of multiple PriceSeries.

Manages asset aggregation, calendar alignment, weight assignment, and auto-computed
statistical and risk metrics upon instantiation. Markdown reporting and Matplotlib
dashboards are delegated to :mod:`toolkit.reports`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from operator import attrgetter, itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from ..utils.cleaning import align_calendar_series
from ..utils.validation import validate_portfolio_weights, validate_price_dataframe
from . import metrics
from .series import PriceSeries

if TYPE_CHECKING:
    from .monte_carlo import MonteCarloResult


@dataclass
class Portfolio:
    """DataClass representing an investment portfolio composed of multiple :class:`PriceSeries` assets.

    Attributes:
        assets: List of :class:`PriceSeries` instances constituting the portfolio.
        weights: Optional asset allocation weights:
                 - ``None``: automatically assigns equal weights (1 / N).
                 - ``Mapping[str, float]``: mapping of ticker symbol -> weight.
                 - ``Sequence[float]`` or ``np.ndarray``: weights ordered as ``assets``.
                 Weights are verified and normalized to sum to 1.0.
        name: Human-readable name or identifier for the portfolio.
        initial_capital: Nominal baseline capital allocated to the portfolio (default: 10,000.0).
    """

    assets: list[PriceSeries]
    weights: Mapping[str, float] | Sequence[float] | np.ndarray | None = None
    name: str = "Portfolio"
    initial_capital: float = 10000.0

    # Auto-computed fields
    weights_dict: dict[str, float] = field(init=False)
    weights_vector: np.ndarray = field(init=False)
    returns_df: pd.DataFrame = field(init=False)
    prices_df: pd.DataFrame = field(init=False)
    portfolio_returns: pd.Series = field(init=False)
    mean_return: float = field(init=False)
    std_return: float = field(init=False)
    covariance_matrix: pd.DataFrame = field(init=False)
    correlation_matrix: pd.DataFrame = field(init=False)
    _asset_map: dict[str, PriceSeries] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate inputs, align asset time series, normalize weights, and compute metrics."""
        if not self.assets:
            raise ValueError("Portfolio must contain at least one PriceSeries asset.")
        if (
            isinstance(self.initial_capital, bool)
            or not np.isfinite(self.initial_capital)
            or self.initial_capital < 0
        ):
            raise ValueError(
                f"initial_capital must be a non-negative finite number, got {self.initial_capital}"
            )

        invalid_asset = next(
            filter(lambda a: not isinstance(a, PriceSeries), self.assets),
            None,
        )
        if invalid_asset is not None:
            raise TypeError(
                f"All items in 'assets' must be instances of PriceSeries, got {type(invalid_asset)}."
            )

        list(
            map(
                lambda asset: validate_price_dataframe(asset.data, required_columns=("close",)),
                self.assets,
            )
        )

        tickers = list(map(attrgetter("ticker"), self.assets))
        if len(tickers) != len(set(tickers)):
            raise ValueError(f"Duplicate tickers detected in portfolio assets: {tickers}")

        self._asset_map = dict(zip(tickers, self.assets, strict=False))

        self._align_data()
        self._process_weights()
        self._compute_metrics()

    def _align_data(self) -> None:
        """Align asset prices first, then calculate returns over identical intervals."""
        tickers = self.tickers
        data_frames = list(map(attrgetter("data"), self.assets))
        prices_dict = dict(zip(tickers, map(itemgetter("close"), data_frames), strict=False))

        aligned_prices = align_calendar_series(prices_dict, join_method="inner")
        self.returns_df = aligned_prices.pct_change(fill_method=None).dropna()
        if self.returns_df.empty:
            raise ValueError(
                "Unable to align asset returns: No overlapping trading dates found across assets."
            )

        self.prices_df = aligned_prices.reindex(self.returns_df.index)

    def _process_weights(self) -> None:
        """Validate and normalize weights using policy validation utilities."""
        tickers = self.tickers
        if self.weights is None:
            equal_w = 1.0 / len(self.assets)
            self.weights_dict = dict.fromkeys(tickers, equal_w)
        else:
            self.weights_dict = validate_portfolio_weights(self.weights, tickers)

        self.weights_vector = pd.Series(self.weights_dict).reindex(tickers).to_numpy(dtype=float)

    def _compute_metrics(self) -> None:
        """Compute daily weighted returns, covariance, correlation, and basic stats."""
        self.portfolio_returns = self.returns_df @ self.weights_vector
        self.portfolio_returns.name = "portfolio_returns"

        self.mean_return = (
            float(self.portfolio_returns.mean()) if not self.portfolio_returns.empty else 0.0
        )
        self.std_return = (
            float(self.portfolio_returns.std()) if not self.portfolio_returns.empty else 0.0
        )

        self.covariance_matrix = self.returns_df.cov()
        self.correlation_matrix = self.returns_df.corr()

    # -------------------------------------------------------------------------
    # Analytical & Risk Methods
    # -------------------------------------------------------------------------

    @property
    def tickers(self) -> list[str]:
        """List of asset tickers in the portfolio."""
        return list(map(attrgetter("ticker"), self.assets))

    @property
    def start_date(self) -> str:
        """First overlapping trading date in portfolio."""
        return str(self.returns_df.index[0].date()) if not self.returns_df.empty else ""

    @property
    def end_date(self) -> str:
        """Last overlapping trading date in portfolio."""
        return str(self.returns_df.index[-1].date()) if not self.returns_df.empty else ""

    def annualized_return(self, trading_days: int = metrics.TRADING_DAYS_PER_YEAR) -> float:
        """Compute annualized geometric return of the portfolio."""
        return metrics.compute_annualized_return(
            self.mean_return,
            has_observations=not self.portfolio_returns.empty,
            trading_days=trading_days,
        )

    def annualized_volatility(self, trading_days: int = metrics.TRADING_DAYS_PER_YEAR) -> float:
        """Compute annualized portfolio volatility based on daily std."""
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
        """Compute cumulative return series starting from 0.0."""
        return metrics.compute_cumulative_returns(self.portfolio_returns)

    def cumulative_wealth(self, capital: float | None = None) -> pd.Series:
        """Compute the monetary value trajectory of the portfolio over time."""
        base_capital = self.initial_capital if capital is None else capital
        return base_capital * (1.0 + self.portfolio_returns).cumprod()

    def drawdown_series(self) -> pd.Series:
        """Compute portfolio underwater drawdown series relative to running high."""
        return metrics.compute_drawdown_series(self.portfolio_returns)

    def max_drawdown(self) -> float:
        """Compute maximum historical peak-to-trough decline (negative float)."""
        return metrics.compute_max_drawdown(self.portfolio_returns)

    def value_at_risk(
        self,
        confidence_level: float = 0.95,
        method: str = "historical",
    ) -> float:
        """Compute daily Value at Risk (VaR) at the specified confidence level."""
        return metrics.compute_value_at_risk(
            self.portfolio_returns,
            confidence_level=confidence_level,
            method=method,
            mean_return=self.mean_return,
            std_return=self.std_return,
        )

    def conditional_value_at_risk(self, confidence_level: float = 0.95) -> float:
        """Compute daily Conditional Value at Risk (CVaR / Expected Shortfall)."""
        return metrics.compute_conditional_value_at_risk(
            self.portfolio_returns, confidence_level=confidence_level
        )

    def summary(self, risk_free_rate: float = 0.0) -> dict[str, Any]:
        """Return a comprehensive summary dictionary of portfolio characteristics."""
        return {
            "name": self.name,
            "assets": self.tickers,
            "weights": self.weights_dict,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "observations": len(self.portfolio_returns),
            "daily_mean_return": self.mean_return,
            "daily_std_return": self.std_return,
            "annualized_return": self.annualized_return(),
            "annualized_volatility": self.annualized_volatility(),
            "sharpe_ratio": self.sharpe_ratio(risk_free_rate=risk_free_rate),
            "max_drawdown": self.max_drawdown(),
            "historical_var_95": self.value_at_risk(0.95),
            "cvar_95": self.conditional_value_at_risk(0.95),
        }

    def __len__(self) -> int:
        """Return the number of assets in the portfolio."""
        return len(self.assets)

    def __getitem__(self, ticker: str) -> PriceSeries:
        """Allow dictionary-style access to constituent :class:`PriceSeries` by ticker."""
        key = ticker.strip().upper()
        if key not in self._asset_map:
            raise KeyError(f"Asset with ticker '{ticker}' not found in portfolio.")
        return self._asset_map[key]

    def __str__(self) -> str:
        weights_str = ", ".join(
            map(lambda item: f"{item[0]}: {item[1]:.1%}", self.weights_dict.items())
        )
        return (
            f"Cartera '{self.name}' con {len(self.assets)} activos ({weights_str}) "
            f"y capital inicial {self.initial_capital:,.2f} EUR"
        )

    def __repr__(self) -> str:
        weights_str = ", ".join(
            map(lambda item: f"{item[0]}: {item[1]:.1%}", self.weights_dict.items())
        )
        return (
            f"Portfolio(name='{self.name}', assets={len(self.assets)}, "
            f"weights={{{weights_str}}}, mean={self.mean_return:.5f}, "
            f"std={self.std_return:.5f}, sharpe={self.sharpe_ratio():.2f})"
        )

    # -------------------------------------------------------------------------
    # Monte Carlo Stochastic Simulation (Requirement 4.4)
    # -------------------------------------------------------------------------

    def simulate_montecarlo(
        self,
        n_simulations: int = 1000,
        horizon: int = metrics.TRADING_DAYS_PER_YEAR,
        mu: float | None = None,
        sigma: float | None = None,
        initial_capital: float | None = None,
        seed: int | None = None,
        multivariate: bool = True,
    ) -> MonteCarloResult:
        """Simulate future portfolio trajectories using Monte Carlo stochastic diffusion."""
        from .monte_carlo import MonteCarloEngine

        cap = initial_capital if initial_capital is not None else self.initial_capital

        if multivariate and len(self.assets) > 1 and mu is None and sigma is None:
            mu_vec = np.fromiter(
                map(attrgetter("mean_return"), self.assets),
                dtype=float,
                count=len(self.assets),
            )
            cov_mat = self.covariance_matrix.to_numpy(dtype=float)
            return MonteCarloEngine.simulate_multivariate_gbm(
                initial_capital=cap,
                weights=self.weights_vector,
                mu_vector=mu_vec,
                cov_matrix=cov_mat,
                horizon=horizon,
                n_simulations=n_simulations,
                seed=seed,
                name=self.name,
            )

        drift = mu if mu is not None else self.mean_return
        vol = sigma if sigma is not None else self.std_return
        return MonteCarloEngine.simulate_gbm(
            initial_value=cap,
            mu=drift,
            sigma=vol,
            horizon=horizon,
            n_simulations=n_simulations,
            seed=seed,
            name=self.name,
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
        return sim.plot(
            title=f"Monte Carlo Simulation: {self.name} (Capital: {sim.initial_value:,.0f}€)",
            save_path=save_path,
            show=show,
        )

    # -------------------------------------------------------------------------
    # Analytical Reporting & Visualization Dashboard (Requirement 4.5)
    # -------------------------------------------------------------------------

    def report(
        self,
        risk_free_rate: float = 0.0,
        confidence_level: float = 0.95,
        output_path: str | Path | None = None,
    ) -> str:
        """Generate a structured, publication-ready analytical report in Markdown."""
        from ..reports import build_portfolio_report

        return build_portfolio_report(
            self,
            risk_free_rate=risk_free_rate,
            confidence_level=confidence_level,
            output_path=output_path,
        )

    def plots_report(
        self,
        figsize: tuple[int, int] = (16, 11),
        save_path: str | Path | None = None,
        show: bool = True,
    ) -> Any:
        """Generate a 2x2 visual analytics dashboard for the portfolio."""
        from ..reports import plot_portfolio_dashboard

        return plot_portfolio_dashboard(self, figsize=figsize, save_path=save_path, show=show)
