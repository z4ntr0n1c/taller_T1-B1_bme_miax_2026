"""Offline unit test suite for ``toolkit`` (no network access required).

Compatible with both ``pytest`` and standard ``python -m unittest``.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import matplotlib
import numpy as np
import pandas as pd

from toolkit import (
    FREDExtractor,
    MonteCarloEngine,
    Portfolio,
    PriceSeries,
    ValidationError,
    YahooFinanceExtractor,
    align_calendar_series,
    clean_missing_values,
    filter_anomalous_returns,
    setup_logging,
    validate_portfolio_weights,
    validate_price_dataframe,
)
from toolkit.models.metrics import compute_drawdown_series

matplotlib.use("Agg")


def _make_synthetic_assets() -> list[PriceSeries]:
    """Build two deterministic synthetic PriceSeries without network calls."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="B")
    close_a = 100.0 * np.cumprod(1.0 + rng.normal(0.0008, 0.012, size=len(dates)))
    close_b = 50.0 * np.cumprod(1.0 + rng.normal(0.0005, 0.010, size=len(dates)))

    df_a = pd.DataFrame({"close": close_a}, index=dates)
    df_b = pd.DataFrame({"close": close_b}, index=dates)
    return [
        PriceSeries(ticker="aapl", asset_type="equity", data=df_a),
        PriceSeries(ticker="msft", asset_type="equity", data=df_b),
    ]


class TestToolkitOffline(unittest.TestCase):
    """Offline test suite for the T1 financial toolkit."""

    def test_setup_logging_is_idempotent(self) -> None:
        logger = setup_logging()
        setup_logging()
        self.assertEqual(len(logger.handlers), 1)

    def test_price_series_does_not_mutate_input_dataframe(self) -> None:
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        raw_df = pd.DataFrame({"close": np.linspace(100.0, 110.0, 10)}, index=dates)
        series = PriceSeries(ticker="aapl", asset_type="equity", data=raw_df)

        self.assertNotIn("returns", raw_df.columns)
        self.assertIn("returns", series.data.columns)
        self.assertEqual(series.ticker, "AAPL")
        self.assertEqual(len(series), 9)
        self.assertGreater(series.annualized_return(), 0.0)
        self.assertGreater(series.annualized_volatility(), 0.0)
        self.assertNotEqual(series.value_at_risk(0.95, method="parametric"), 0.0)
        self.assertLessEqual(series.conditional_value_at_risk(0.95), series.value_at_risk(0.95))

    def test_var_rejects_invalid_confidence_levels(self) -> None:
        invalid_levels = (-0.1, 0.0, 1.0, 1.1, np.nan, np.inf, -np.inf, True)
        series = _make_synthetic_assets()[0]
        portfolio = Portfolio(_make_synthetic_assets())
        simulation = MonteCarloEngine.simulate_gbm(
            initial_value=100.0,
            mu=0.001,
            sigma=0.01,
            horizon=5,
            n_simulations=20,
            seed=1,
        )

        for level in invalid_levels:
            with self.subTest(level=level):
                with self.assertRaises(ValueError):
                    series.value_at_risk(level)
                with self.assertRaises(ValueError):
                    series.conditional_value_at_risk(level)
                with self.assertRaises(ValueError):
                    portfolio.value_at_risk(level)
                with self.assertRaises(ValueError):
                    portfolio.conditional_value_at_risk(level)
                with self.assertRaises(ValueError):
                    portfolio.report(confidence_level=level)
                with self.assertRaises(ValueError):
                    simulation.terminal_var(level)
                with self.assertRaises(ValueError):
                    simulation.terminal_cvar(level)
                with self.assertRaises(ValueError):
                    simulation.summary(level)

        for level in (0.01, 0.99):
            with self.subTest(level=level):
                self.assertTrue(np.isfinite(series.value_at_risk(level)))
                self.assertTrue(np.isfinite(series.value_at_risk(level, method="parametric")))
                self.assertTrue(np.isfinite(simulation.terminal_var(level)))

        with self.assertRaises(ValueError):
            simulation.plot(confidence_level=0.0, show=False)

    def test_drawdown_includes_initial_wealth_peak(self) -> None:
        returns = pd.Series([-0.10, 0.05])

        drawdowns = compute_drawdown_series(returns)

        self.assertAlmostEqual(drawdowns.iloc[0], -0.10)
        self.assertAlmostEqual(drawdowns.iloc[1], -0.055)
        self.assertAlmostEqual(float(drawdowns.min()), -0.10)

        dates = pd.date_range("2024-01-01", periods=6, freq="B")
        asset = PriceSeries(
            ticker="A",
            asset_type="equity",
            data=pd.DataFrame(
                {"close": [100.0, 90.0, 94.5, 100.0, 95.0, 105.0]},
                index=dates,
            ),
        )
        portfolio = Portfolio([asset])

        self.assertAlmostEqual(asset.max_drawdown(), -0.10)
        self.assertAlmostEqual(portfolio.max_drawdown(), -0.10)

    def test_price_series_rejects_invalid_price_data(self) -> None:
        dates = pd.date_range("2024-01-01", periods=6, freq="B")
        valid_df = pd.DataFrame({"close": np.linspace(100.0, 105.0, 6)}, index=dates)

        invalid_prices = valid_df.copy()
        invalid_prices.iloc[2, 0] = 0.0
        with self.assertRaises(ValidationError):
            PriceSeries(ticker="bad", asset_type="equity", data=invalid_prices)

        extreme_prices = valid_df.copy()
        extreme_prices["close"] = [1e-308, 1e308, 1e308, 1e308, 1e308, 1e308]
        with self.assertRaisesRegex(ValidationError, "Calculated column 'returns'"):
            PriceSeries(
                ticker="extreme",
                asset_type="equity",
                data=extreme_prices,
            )

        finite_returns_overflow_std = valid_df.copy()
        finite_returns_overflow_std["close"] = [
            1e-300,
            1e7,
            1e7,
            1e7,
            1e7,
            1e7,
        ]
        with self.assertRaisesRegex(ValidationError, "return statistics"):
            PriceSeries(
                ticker="overflow_std",
                asset_type="equity",
                data=finite_returns_overflow_std,
            )

        for invalid_value in (np.nan, np.inf, -np.inf):
            with self.subTest(invalid_value=invalid_value):
                non_finite_prices = valid_df.copy()
                non_finite_prices.iloc[2, 0] = invalid_value
                with self.assertRaises(ValidationError):
                    PriceSeries(
                        ticker="bad",
                        asset_type="equity",
                        data=non_finite_prices,
                    )

        for invalid_return in (np.inf, -np.inf):
            with self.subTest(invalid_return=invalid_return):
                invalid_returns = valid_df.assign(
                    returns=[np.nan, 0.01, invalid_return, 0.01, 0.01, 0.01]
                )
                with self.assertRaises(ValidationError):
                    PriceSeries(
                        ticker="bad",
                        asset_type="equity",
                        data=invalid_returns,
                    )

        missing_returns = valid_df.assign(
            returns=valid_df["close"].pct_change(fill_method=None)
        )
        series_with_missing_returns = PriceSeries(
            ticker="missing",
            asset_type="equity",
            data=missing_returns,
        )
        self.assertEqual(len(series_with_missing_returns), 5)

        inconsistent_returns = valid_df.assign(
            returns=[np.nan, 0.01, 0.01, 0.01, 0.01, 0.01]
        )
        with self.assertRaisesRegex(ValidationError, "inconsistent with 'close'"):
            PriceSeries(
                ticker="inconsistent",
                asset_type="equity",
                data=inconsistent_returns,
            )

        empty_returns = valid_df.assign(returns=np.nan)
        with self.assertRaisesRegex(ValidationError, "at least one valid observation"):
            PriceSeries(
                ticker="empty",
                asset_type="equity",
                data=empty_returns,
            )

        duplicate_dates = valid_df.copy()
        duplicate_dates.index = dates.where(np.arange(6) != 2, dates[1])
        with self.assertRaises(ValidationError):
            PriceSeries(ticker="bad", asset_type="equity", data=duplicate_dates)

        with self.assertRaises(ValidationError):
            PriceSeries(
                ticker="short",
                asset_type="equity",
                data=valid_df.iloc[:4],
            )

    def test_standardize_dataframes(self) -> None:
        dates = pd.date_range("2024-01-01", periods=6, freq="B")
        yahoo_raw = pd.DataFrame({"Close": [100, 101, 102, 103, 104, 105]}, index=dates)
        std_yahoo = YahooFinanceExtractor._standardize_dataframe(yahoo_raw)
        self.assertEqual(list(std_yahoo.columns), ["close", "returns"])
        self.assertEqual(std_yahoo.index.name, "date")

        for columns in (
            pd.MultiIndex.from_product([["Close", "High"], ["AAPL"]]),
            pd.MultiIndex.from_product([["AAPL"], ["Close", "High"]]),
        ):
            with self.subTest(columns=columns):
                yahoo_multiindex = pd.DataFrame(
                    [[100, 101], [101, 102], [102, 103], [103, 104], [104, 105], [105, 106]],
                    index=dates,
                    columns=columns,
                )
                standardized_multiindex = YahooFinanceExtractor._standardize_dataframe(
                    yahoo_multiindex
                )
                self.assertEqual(
                    standardized_multiindex["close"].tolist(),
                    [100, 101, 102, 103, 104, 105],
                )

        fred_raw = pd.DataFrame({"DFF": [5.0, 5.1, 5.2, 5.1, 5.3, 5.4]}, index=dates)
        std_fred = FREDExtractor._standardize_dataframe(fred_raw, "DFF")
        self.assertEqual(list(std_fred.columns), ["close", "returns"])

    def test_fred_standardization_drops_missing_observations(self) -> None:
        dates = pd.date_range("2024-01-01", periods=7, freq="B")
        fred_raw = pd.DataFrame(
            {"DFF": [5.0, np.nan, 5.2, np.inf, 5.3, 5.4, 5.5]},
            index=dates,
        )

        standardized = FREDExtractor._standardize_dataframe(fred_raw, "DFF")
        series = PriceSeries(ticker="DFF", asset_type="macro", data=standardized)

        self.assertEqual(standardized["close"].tolist(), [5.0, 5.2, 5.3, 5.4, 5.5])
        self.assertFalse(series.data["close"].isna().any())

    def test_fred_csv_fallback_parses_observation_dates(self) -> None:
        response = Mock()
        response.text = (
            "observation_date,DFF\n"
            "2024-01-01,5.10\n"
            "2024-01-02,5.11\n"
            "2024-01-03,5.12\n"
            "2024-01-04,5.13\n"
            "2024-01-05,5.14\n"
            "2024-01-08,5.15\n"
        )

        with patch("requests.get", return_value=response) as get:
            raw = FREDExtractor()._fetch_via_fred_csv("DFF", "2024-01-01", "2024-01-08")

        get.assert_called_once()
        self.assertIsInstance(raw.index, pd.DatetimeIndex)
        self.assertEqual(str(raw.index[0].date()), "2024-01-01")

        standardized = FREDExtractor._standardize_dataframe(raw, series_name="DFF")
        series = PriceSeries(ticker="DFF", asset_type="macro", data=standardized)
        self.assertEqual(series.data.index[0], pd.Timestamp("2024-01-01"))

    def test_validation_invariants(self) -> None:
        dates = pd.date_range("2024-01-01", periods=6, freq="B")
        valid_df = pd.DataFrame({"close": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]}, index=dates)
        self.assertTrue(validate_price_dataframe(valid_df))

        neg_df = valid_df.copy()
        neg_df.iloc[1, 0] = -1.0
        with self.assertRaises(ValidationError):
            validate_price_dataframe(neg_df)

        weights = validate_portfolio_weights([30, 70], ["AAPL", "MSFT"])
        self.assertEqual(weights, {"AAPL": 0.3, "MSFT": 0.7})
    def test_cleaning_and_alignment(self) -> None:
        dates = pd.date_range("2024-01-01", periods=4, freq="D")
        s1 = pd.Series([100.0, np.nan, 102.0, 103.0], index=dates)
        s2 = pd.Series([50.0, 51.0, np.nan, 53.0], index=dates)

        inner = align_calendar_series({"A": s1, "B": s2}, join_method="inner")
        self.assertEqual(len(inner), 2)

        outer = align_calendar_series({"A": s1, "B": s2}, join_method="outer_ffill")
        self.assertEqual(len(outer), 4)

        df_cleaned = clean_missing_values(pd.DataFrame({"close": s1}), method="ffill")
        self.assertFalse(df_cleaned["close"].isna().any())

        clean_ret, anomalies = filter_anomalous_returns(
            pd.Series([0.01, -0.02, 2.5]), max_abs_return=1.0
        )
        self.assertEqual(len(clean_ret), 2)
        self.assertEqual(len(anomalies), 1)

    def test_cleaning_does_not_fill_long_interior_gaps(self) -> None:
        dates = pd.date_range("2024-01-01", periods=8, freq="D")
        prices = pd.DataFrame(
            {"close": [np.nan, np.nan, 100.0, np.nan, np.nan, np.nan, np.nan, 105.0]},
            index=dates,
        )

        cleaned = clean_missing_values(prices, method="ffill", max_consecutive_nans=2)

        self.assertEqual(
            cleaned["close"].tolist(),
            [100.0, 100.0, 100.0, 105.0],
        )
        self.assertEqual(
            cleaned.index.tolist(),
            [dates[2], dates[3], dates[4], dates[7]],
        )

        with self.assertRaises(ValueError):
            clean_missing_values(prices, method="ffill", max_consecutive_nans=0)

    def test_calendar_alignment_does_not_backfill_from_future(self) -> None:
        dates = pd.date_range("2024-01-01", periods=4, freq="D")
        leading_gap = pd.Series([np.nan, 10.0, 11.0, 12.0], index=dates)
        complete = pd.Series([20.0, 21.0, 22.0, 23.0], index=dates)

        aligned = align_calendar_series(
            {"leading_gap": leading_gap, "complete": complete},
            join_method="outer_ffill",
        )
        cleaned = clean_missing_values(
            pd.DataFrame({"close": leading_gap}),
            method="interpolate",
        )

        self.assertEqual(aligned.index[0], dates[1])
        self.assertEqual(aligned.iloc[0]["leading_gap"], 10.0)
        self.assertEqual(cleaned.index[0], dates[1])

    def test_portfolio_returns_use_matching_price_intervals(self) -> None:
        dates = pd.date_range("2024-01-01", periods=6, freq="D")
        asset_a = PriceSeries(
            ticker="A",
            asset_type="equity",
            data=pd.DataFrame(
                {"close": [100.0, 110.0, 121.0, 133.1, 146.41, 161.051]},
                index=dates,
            ),
        )
        asset_b = PriceSeries(
            ticker="B",
            asset_type="equity",
            data=pd.DataFrame(
                {"close": [100.0, 100.0, 121.0, 133.1, 146.41]},
                index=dates.delete(2),
            ),
        )

        portfolio = Portfolio([asset_a, asset_b])

        self.assertAlmostEqual(portfolio.returns_df.loc[dates[3], "A"], 0.21)
        self.assertAlmostEqual(portfolio.returns_df.loc[dates[3], "B"], 0.21)

    def test_portfolio_metrics_and_reports(self) -> None:
        assets = _make_synthetic_assets()
        portfolio = Portfolio(
            assets=assets,
            weights={"AAPL": 0.6, "MSFT": 0.4},
            name="Synthetic Test Portfolio",
            initial_capital=10_000.0,
        )

        self.assertEqual(len(portfolio), 2)
        self.assertEqual(portfolio["aapl"].ticker, "AAPL")
        self.assertEqual(portfolio.weights_dict, {"AAPL": 0.6, "MSFT": 0.4})
        self.assertLess(portfolio.value_at_risk(0.95, method="parametric"), 0.0)
        self.assertLessEqual(
            portfolio.conditional_value_at_risk(0.95), portfolio.value_at_risk(0.95)
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            md_path = tmp_path / "reports" / "report.md"
            md_text = portfolio.report(risk_free_rate=0.02, output_path=md_path)
            self.assertTrue(md_path.is_file())
            self.assertIn("Synthetic Test Portfolio", md_text)

            plot_path = tmp_path / "plots" / "dashboard.png"
            portfolio.plots_report(save_path=plot_path, show=False)
            self.assertTrue(plot_path.is_file())

    def test_portfolio_rejects_negative_or_nonfinite_initial_capital(self) -> None:
        asset = _make_synthetic_assets()[0]
        for capital in (-1.0, np.nan, np.inf, -np.inf):
            with self.subTest(capital=capital), self.assertRaises(ValueError):
                Portfolio(assets=[asset], initial_capital=capital)

    def test_monte_carlo_reproducibility(self) -> None:
        assets = _make_synthetic_assets()
        portfolio = Portfolio(assets=assets, initial_capital=10_000.0)

        mc1 = portfolio.simulate_montecarlo(
            n_simulations=200, horizon=30, seed=123, multivariate=True
        )
        mc2 = portfolio.simulate_montecarlo(
            n_simulations=200, horizon=30, seed=123, multivariate=True
        )
        self.assertTrue(np.allclose(mc1.trajectories, mc2.trajectories))
        self.assertEqual(mc1.trajectories.shape, (31, 200))

        mc_agg = MonteCarloEngine.simulate_gbm(
            initial_value=100.0, mu=0.0005, sigma=0.01, horizon=20, n_simulations=100, seed=7
        )
        with tempfile.TemporaryDirectory() as tmp:
            mc_plot = Path(tmp) / "mc.png"
            mc_agg.plot(save_path=mc_plot, show=False)
            self.assertTrue(mc_plot.is_file())

    def test_monte_carlo_rejects_invalid_parameters(self) -> None:
        invalid_params = [
            {"initial_value": 0.0, "mu": 0.01, "sigma": 0.1},
            {"initial_value": 100.0, "mu": 0.01, "sigma": -0.1},
            {"initial_value": 100.0, "mu": 0.01, "sigma": 0.1, "horizon": 0},
            {
                "initial_value": 100.0,
                "mu": 0.01,
                "sigma": 0.1,
                "n_simulations": 0,
            },
        ]
        for params in invalid_params:
            with self.subTest(params=params), self.assertRaises(ValueError):
                MonteCarloEngine.simulate_gbm(**params)

        invalid_gbm_params = [
            {"mu": np.nan},
            {"mu": np.inf},
            {"dt": -1.0},
            {"dt": np.nan},
        ]
        for params in invalid_gbm_params:
            with self.subTest(params=params), self.assertRaises(ValueError):
                simulation_params = {
                    "initial_value": 100.0,
                    "mu": 0.01,
                    "sigma": 0.1,
                    "horizon": 2,
                    "n_simulations": 2,
                }
                simulation_params.update(params)
                MonteCarloEngine.simulate_gbm(**simulation_params)

        with self.assertRaises(ValueError):
            MonteCarloEngine.simulate_multivariate_gbm(
                initial_capital=100.0,
                weights=np.array([0.5, 0.5]),
                mu_vector=np.array([0.01, np.nan]),
                cov_matrix=np.eye(2),
                horizon=2,
                n_simulations=2,
            )

        for cov_matrix, message in (
            (np.array([[-1e-4, 0.0], [0.0, 1e-4]]), "positive semidefinite"),
            (np.array([[1e-4, 2e-4], [0.0, 1e-4]]), "symmetric"),
        ):
            with self.subTest(cov_matrix=cov_matrix), self.assertRaisesRegex(
                ValueError, message
            ):
                MonteCarloEngine.simulate_multivariate_gbm(
                    initial_capital=100.0,
                    weights=np.array([0.5, 0.5]),
                    mu_vector=np.array([0.01, 0.02]),
                    cov_matrix=cov_matrix,
                    horizon=2,
                    n_simulations=2,
                )

    def test_multivariate_gbm_preserves_singular_covariance(self) -> None:
        covariance = np.array([[1e-12, 1e-12], [1e-12, 1e-12]])

        result = MonteCarloEngine.simulate_multivariate_gbm(
            initial_capital=100.0,
            weights=np.array([0.8, 0.2]),
            mu_vector=np.array([0.0, 0.0]),
            cov_matrix=covariance,
            horizon=1,
            n_simulations=10_000,
            seed=7,
        )

        daily_returns = result.terminal_values / result.initial_value - 1.0
        self.assertTrue(np.isfinite(result.trajectories).all())
        self.assertLess(float(np.std(daily_returns)), 1e-5)

    def test_multivariate_gbm_rejects_negative_weights_only(self) -> None:
        params = {
            "initial_capital": 100.0,
            "mu_vector": np.array([0.0, 0.0]),
            "cov_matrix": np.zeros((2, 2)),
            "horizon": 1,
            "n_simulations": 2,
            "seed": 1,
        }

        with self.assertRaisesRegex(ValueError, "weights must be non-negative"):
            MonteCarloEngine.simulate_multivariate_gbm(
                weights=np.array([1.5, -0.5]),
                **params,
            )

        result = MonteCarloEngine.simulate_multivariate_gbm(
            weights=np.array([0.2, 0.2]),
            **params,
        )
        self.assertTrue(np.isfinite(result.trajectories).all())


if __name__ == "__main__":
    unittest.main()
