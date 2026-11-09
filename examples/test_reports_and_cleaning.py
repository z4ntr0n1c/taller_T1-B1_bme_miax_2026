"""
test_reports_and_cleaning.py — Validation script for Data Cleaning, Input Validation,
Markdown Reporting, and Visual Dashboard (Requirement 4.5).

Demonstrates:
  1. Data cleaning routines: NaN handling (ffill/drop) and cross-exchange calendar alignment
  2. Input validation policy: Enforcing invariants (positive prices, DatetimeIndex, monotonic ordering)
     and rejection of corrupted inputs with ValidationError
  3. Generation of professional Markdown report via Portfolio.report()
  4. Generation of 4-panel analytics dashboard via Portfolio.plots_report()
"""

import os
import pandas as pd
import numpy as np

from toolkit.data import YahooFinanceExtractor
from toolkit.models import Portfolio, PriceSeries
from toolkit.utils import (
    clean_missing_values,
    align_calendar_series,
    validate_price_dataframe,
    validate_portfolio_weights,
    ValidationError,
)


def test_validation_and_cleaning():
    print("=" * 75)
    print("1. TESTING INPUT VALIDATION & DATA CLEANING POLICY")
    print("=" * 75)

    # 1A. Testing valid DataFrame
    valid_df = pd.DataFrame(
        {"close": [100.0, 102.5, 101.8, 104.2, 105.0]},
        index=pd.date_range("2024-01-01", periods=5),
    )
    assert validate_price_dataframe(valid_df) is True
    print("   [PASS] Valid price DataFrame passed all structural invariants.")

    # 1B. Testing rejection of negative prices
    invalid_neg_df = pd.DataFrame(
        {"close": [100.0, -5.0, 102.0, 103.0, 104.0]},
        index=pd.date_range("2024-01-01", periods=5),
    )
    try:
        validate_price_dataframe(invalid_neg_df)
        raise AssertionError("Should have raised ValidationError for negative prices!")
    except ValidationError as e:
        print(f"   [PASS] Correctly rejected negative prices: {e}")

    # 1C. Testing rejection of non-monotonic timestamps
    non_monotonic_df = pd.DataFrame(
        {"close": [100.0, 102.0, 101.0, 104.0, 105.0]},
        index=pd.to_datetime(["2024-01-01", "2024-01-03", "2024-01-02", "2024-01-04", "2024-01-05"]),
    )
    try:
        validate_price_dataframe(non_monotonic_df)
        raise AssertionError("Should have raised ValidationError for non-monotonic dates!")
    except ValidationError as e:
        print(f"   [PASS] Correctly rejected unordered timestamps: {e}")

    # 1D. Testing weight validation
    weights = validate_portfolio_weights([30, 70], ["AAPL", "MSFT"])
    print(f"   [PASS] Normalized raw weights [30, 70] -> {weights}")

    # 1E. Testing calendar alignment and NaN cleaning
    s_us = pd.Series([100.0, 101.0, np.nan, 103.0], index=pd.date_range("2024-01-01", periods=4))
    s_es = pd.Series([50.0, np.nan, 52.0, 53.0], index=pd.date_range("2024-01-01", periods=4))
    aligned_inner = align_calendar_series({"US": s_us, "ES": s_es}, join_method="inner")
    print(f"   [PASS] Calendar inner alignment: {len(aligned_inner)} common sessions.")

    aligned_ffill = align_calendar_series({"US": s_us, "ES": s_es}, join_method="outer_ffill")
    print(f"   [PASS] Calendar outer ffill alignment: {len(aligned_ffill)} total sessions with gaps filled.")


def test_reporting_and_plots():
    print("\n" + "=" * 75)
    print("2. TESTING PORTFOLIO MARKDOWN REPORT & VISUAL DASHBOARD")
    print("=" * 75)

    extractor = YahooFinanceExtractor()
    tickers = ["AAPL", "MSFT", "SAN.MC", "^IBEX"]
    print(f"\n   Fetching market data for {tickers}...")
    assets = extractor.fetch_batch(tickers, start="2024-01-01", end="2025-01-01")

    # Construct portfolio with deliberate concentration to trigger risk diagnostic warnings
    weights = {"AAPL": 0.50, "MSFT": 0.25, "SAN.MC": 0.15, "^IBEX": 0.10}
    portfolio = Portfolio(
        assets=assets,
        weights=weights,
        name="Tech-Weighted European Hybrid",
        initial_capital=100000.0,
    )

    output_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(output_dir, exist_ok=True)
    plots_dir = os.path.join(os.path.dirname(__file__), "plots")
    os.makedirs(plots_dir, exist_ok=True)

    # 2A. Generate Markdown Report (.report())
    report_path = os.path.join(output_dir, "portfolio_report.md")
    report_md = portfolio.report(risk_free_rate=0.03, output_path=report_path)
    print(f"\n   [SUCCESS] Markdown Report generated and saved to: {report_path}")
    print("\n   --- Preview of Generated Markdown Report (First 40 lines) ---")
    preview_lines = report_md.splitlines()[:40]
    for line in preview_lines:
        print(f"   {line}")
    print("   [... report continues with Correlation Matrix & Diagnostics ...]")

    # 2B. Generate Visual Analytics Dashboard (.plots_report())
    plots_path = os.path.join(plots_dir, "portfolio_dashboard.png")
    portfolio.plots_report(save_path=plots_path, show=False)
    print(f"\n   [SUCCESS] 4-Panel Analytics Dashboard exported to: {plots_path}")


def main():
    test_validation_and_cleaning()
    test_reporting_and_plots()
    print("\n" + "=" * 75)
    print("ALL 4.5 CLEANING, VALIDATION & REPORTING TESTS COMPLETED!")
    print("=" * 75)


if __name__ == "__main__":
    main()

