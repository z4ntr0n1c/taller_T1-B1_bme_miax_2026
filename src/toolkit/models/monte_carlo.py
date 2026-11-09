"""Monte Carlo Simulation Engine for financial assets and investment portfolios.

Provides stochastic trajectory simulation based on Geometric Brownian Motion (GBM)
and multivariate correlated asset diffusion, with analytical summaries and visual reporting.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .metrics import TRADING_DAYS_PER_YEAR, validate_confidence_level


@dataclass
class MonteCarloResult:
    """Encapsulates the output and diagnostics of a Monte Carlo simulation run.

    Attributes:
        name: Name of the asset or portfolio simulated.
        trajectories: 2D NumPy array of shape ``(horizon + 1, n_simulations)``
                      containing the simulated value paths over time.
        horizon: Number of forward time steps (e.g. trading days).
        n_simulations: Total number of generated Monte Carlo trajectories.
        initial_value: Starting price or capital at ``t = 0``.
        mu: Drift parameter (daily expected return) used in the simulation.
        sigma: Diffusion parameter (daily volatility) used in the simulation.
        method: Stochastic model employed (``'gbm'`` or ``'multivariate_gbm'``).
    """

    name: str
    trajectories: np.ndarray
    horizon: int
    n_simulations: int
    initial_value: float
    mu: float
    sigma: float
    method: str = "gbm"
    time_steps: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        self.time_steps = np.arange(self.horizon + 1)

    @property
    def terminal_values(self) -> np.ndarray:
        """Simulated asset or portfolio values at the final horizon step T."""
        return self.trajectories[-1, :]

    @property
    def terminal_returns(self) -> np.ndarray:
        """Percentage return from t=0 to t=T for each simulated path."""
        return (self.terminal_values - self.initial_value) / self.initial_value

    @property
    def terminal_mean(self) -> float:
        """Expected (mean) value at horizon T."""
        return float(np.mean(self.terminal_values))

    @property
    def terminal_median(self) -> float:
        """Median value at horizon T."""
        return float(np.median(self.terminal_values))

    @property
    def terminal_std(self) -> float:
        """Standard deviation of simulated terminal values."""
        return float(np.std(self.terminal_values))

    @property
    def terminal_min(self) -> float:
        """Minimum observed terminal value across simulations."""
        return float(np.min(self.terminal_values))

    @property
    def terminal_max(self) -> float:
        """Maximum observed terminal value across simulations."""
        return float(np.max(self.terminal_values))

    @property
    def probability_of_loss(self) -> float:
        """Estimated probability that terminal value is below the initial investment."""
        return float(np.mean(self.terminal_values < self.initial_value))

    def percentiles(
        self, q: Sequence[float] = (0.05, 0.25, 0.50, 0.75, 0.95)
    ) -> dict[float, float]:
        """Calculate specific percentiles of the terminal value distribution.

        Args:
            q: Sequence of percentiles in ``[0, 1]`` range.
        """
        q_arr = np.asarray(q, dtype=float)
        pct_vals = np.percentile(self.terminal_values, q_arr * 100.0)
        return dict(zip(q, np.asarray(pct_vals, dtype=float).tolist(), strict=False))

    def terminal_var(self, confidence_level: float = 0.95) -> float:
        """Compute Value at Risk (VaR) in monetary units at the terminal horizon."""
        validate_confidence_level(confidence_level)
        cutoff = float(np.percentile(self.terminal_values, (1.0 - confidence_level) * 100.0))
        return float(max(0.0, self.initial_value - cutoff))

    def terminal_cvar(self, confidence_level: float = 0.95) -> float:
        """Compute Conditional Value at Risk (CVaR / Expected Shortfall) in monetary units."""
        validate_confidence_level(confidence_level)
        cutoff = float(np.percentile(self.terminal_values, (1.0 - confidence_level) * 100.0))
        tail = self.terminal_values[self.terminal_values <= cutoff]
        if len(tail) == 0:
            return self.terminal_var(confidence_level)
        return float(max(0.0, self.initial_value - float(np.mean(tail))))

    def summary(self, confidence_level: float = 0.95) -> dict[str, Any]:
        """Generate a comprehensive diagnostic summary of the Monte Carlo simulation."""
        validate_confidence_level(confidence_level)
        pcts = self.percentiles((0.05, 0.25, 0.50, 0.75, 0.95))
        conf_pct = int(confidence_level * 100)
        return {
            "name": self.name,
            "method": self.method,
            "n_simulations": self.n_simulations,
            "horizon_days": self.horizon,
            "initial_value": self.initial_value,
            "daily_mu": self.mu,
            "daily_sigma": self.sigma,
            "annualized_drift": self.mu * TRADING_DAYS_PER_YEAR,
            "annualized_vol": self.sigma * np.sqrt(TRADING_DAYS_PER_YEAR),
            "terminal_mean": self.terminal_mean,
            "terminal_median": self.terminal_median,
            "terminal_std": self.terminal_std,
            "terminal_min": self.terminal_min,
            "terminal_max": self.terminal_max,
            "expected_return": (self.terminal_mean - self.initial_value) / self.initial_value,
            "probability_of_loss": self.probability_of_loss,
            f"terminal_var_{conf_pct}": self.terminal_var(confidence_level),
            f"terminal_cvar_{conf_pct}": self.terminal_cvar(confidence_level),
            "p05": pcts[0.05],
            "p25": pcts[0.25],
            "p50": pcts[0.50],
            "p75": pcts[0.75],
            "p95": pcts[0.95],
        }

    def plot(
        self,
        title: str | None = None,
        max_paths_to_display: int = 150,
        confidence_level: float = 0.95,
        figsize: tuple[int, int] = (14, 6),
        save_path: str | Path | None = None,
        show: bool = True,
    ) -> Any:
        """Visualize simulation trajectories and terminal value distribution."""
        from ..reports import plot_monte_carlo

        return plot_monte_carlo(
            self,
            title=title,
            max_paths_to_display=max_paths_to_display,
            confidence_level=confidence_level,
            figsize=figsize,
            save_path=save_path,
            show=show,
        )


def _validate_simulation_params(
    initial_value: float,
    horizon: int,
    n_simulations: int,
    sigma: float = 0.0,
) -> None:
    """Validate common Monte Carlo input parameters."""
    if not np.isfinite(initial_value) or initial_value <= 0:
        raise ValueError(f"initial_value must be positive, got {initial_value}")
    if isinstance(horizon, bool) or not isinstance(horizon, (int, np.integer)) or horizon <= 0:
        raise ValueError(f"horizon must be positive integer, got {horizon}")
    if (
        isinstance(n_simulations, bool)
        or not isinstance(n_simulations, (int, np.integer))
        or n_simulations <= 0
    ):
        raise ValueError(f"n_simulations must be positive integer, got {n_simulations}")
    if not np.isfinite(sigma) or sigma < 0:
        raise ValueError(f"sigma must be non-negative, got {sigma}")


def _validate_time_step(dt: float) -> None:
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError(f"dt must be a positive finite number, got {dt}")


class MonteCarloEngine:
    """Stochastic engine executing vectorized Monte Carlo simulations for financial series."""

    @staticmethod
    def simulate_gbm(
        initial_value: float,
        mu: float,
        sigma: float,
        horizon: int = TRADING_DAYS_PER_YEAR,
        n_simulations: int = 1000,
        dt: float = 1.0,
        seed: int | None = None,
        name: str = "Asset",
    ) -> MonteCarloResult:
        """Simulate single-asset or aggregate portfolio paths using Geometric Brownian Motion (GBM).

        $$S_{t+1} = S_t \\exp\\left((\\mu - \\tfrac{1}{2}\\sigma^2)\\Delta t + \\sigma\\sqrt{\\Delta t}\\,Z_t\\right)$$
        """
        _validate_simulation_params(initial_value, horizon, n_simulations, sigma)
        if not np.isfinite(mu):
            raise ValueError(f"mu must be finite, got {mu}")
        _validate_time_step(dt)
        rng = np.random.default_rng(seed)

        drift = (mu - 0.5 * (sigma**2)) * dt
        diffusion = sigma * np.sqrt(dt)

        shocks = rng.standard_normal(size=(horizon, n_simulations))
        daily_log_returns = drift + diffusion * shocks

        cum_log_returns = np.vstack([
            np.zeros((1, n_simulations)),
            np.cumsum(daily_log_returns, axis=0),
        ])
        trajectories = initial_value * np.exp(cum_log_returns)

        return MonteCarloResult(
            name=name,
            trajectories=trajectories,
            horizon=horizon,
            n_simulations=n_simulations,
            initial_value=initial_value,
            mu=mu,
            sigma=sigma,
            method="gbm",
        )

    @staticmethod
    def simulate_multivariate_gbm(
        initial_capital: float,
        weights: np.ndarray,
        mu_vector: np.ndarray,
        cov_matrix: np.ndarray,
        horizon: int = TRADING_DAYS_PER_YEAR,
        n_simulations: int = 1000,
        dt: float = 1.0,
        seed: int | None = None,
        name: str = "Portfolio",
    ) -> MonteCarloResult:
        """Simulate portfolio paths using correlated multivariate Geometric Brownian Motion.

        Generates correlated Gaussian shocks using Cholesky for positive-definite
        covariances and an eigenvalue factorization for singular positive-semidefinite ones.
        """
        _validate_simulation_params(initial_capital, horizon, n_simulations)
        _validate_time_step(dt)
        n_assets = len(weights)
        if n_assets == 0:
            raise ValueError("weights must contain at least one asset.")
        if weights.shape != (n_assets,) or mu_vector.shape != (n_assets,):
            raise ValueError("weights and mu_vector must be one-dimensional arrays of equal length.")
        if cov_matrix.shape != (n_assets, n_assets):
            raise ValueError(
                f"Covariance matrix shape {cov_matrix.shape} does not match "
                f"number of assets ({n_assets})."
            )
        if not np.isfinite(weights).all():
            raise ValueError("weights must contain only finite values.")
        if np.any(weights < 0):
            raise ValueError("weights must be non-negative.")
        if not np.isfinite(mu_vector).all():
            raise ValueError("mu_vector must contain only finite values.")
        if not np.isfinite(cov_matrix).all():
            raise ValueError("cov_matrix must contain only finite values.")

        covariance_scale = float(np.max(np.abs(cov_matrix)))
        symmetry_tolerance = (
            100.0 * np.finfo(float).eps * max(n_assets, 1) * covariance_scale
        )
        if np.max(np.abs(cov_matrix - cov_matrix.T)) > symmetry_tolerance:
            raise ValueError("cov_matrix must be symmetric.")

        symmetric_cov = (cov_matrix + cov_matrix.T) / 2.0
        eigvals, eigvecs = np.linalg.eigh(symmetric_cov)
        eigenvalue_tolerance = (
            100.0
            * np.finfo(float).eps
            * max(n_assets, 1)
            * max(float(np.max(np.abs(eigvals))), np.finfo(float).tiny)
        )
        if eigvals[0] < -eigenvalue_tolerance:
            raise ValueError("cov_matrix must be positive semidefinite.")

        rng = np.random.default_rng(seed)
        if eigvals[0] > eigenvalue_tolerance:
            covariance_factor = np.linalg.cholesky(symmetric_cov)
        else:
            covariance_factor = eigvecs * np.sqrt(np.maximum(eigvals, 0.0))[np.newaxis, :]
        vol_vector = np.sqrt(np.maximum(np.diag(symmetric_cov), 0.0))
        drift_vector = (mu_vector - 0.5 * (vol_vector**2)) * dt

        # Vectorized correlated shocks across (horizon, n_assets, n_simulations)
        uncorrelated = rng.standard_normal(size=(horizon, n_assets, n_simulations))
        correlated_shocks = covariance_factor @ uncorrelated * np.sqrt(dt)
        step_log_returns = drift_vector[np.newaxis, :, np.newaxis] + correlated_shocks
        cum_log_returns = np.cumsum(step_log_returns, axis=0)

        initial_asset_wealth = initial_capital * weights[np.newaxis, :, np.newaxis]
        asset_wealth_paths = initial_asset_wealth * np.exp(cum_log_returns)

        portfolio_wealth = np.vstack([
            np.full((1, n_simulations), initial_capital, dtype=float),
            asset_wealth_paths.sum(axis=1),
        ])

        portfolio_mu = float(np.sum(weights * mu_vector))
        portfolio_variance = float(weights.T @ symmetric_cov @ weights)
        portfolio_sigma = float(np.sqrt(max(portfolio_variance, 0.0)))

        return MonteCarloResult(
            name=name,
            trajectories=portfolio_wealth,
            horizon=horizon,
            n_simulations=n_simulations,
            initial_value=initial_capital,
            mu=portfolio_mu,
            sigma=portfolio_sigma,
            method="multivariate_gbm",
        )
