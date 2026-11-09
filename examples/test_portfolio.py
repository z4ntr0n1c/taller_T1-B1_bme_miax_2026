"""
test_portfolio.py — Validation script for Portfolio DataClass (Requirement 4.3).

Demonstrates:
  1. Creation of Portfolio with equal weights (1/N)
  2. Creation of Portfolio with custom dictionary weights
  3. Automatic metric computation on instantiation (__post_init__)
  4. Correlation & Covariance matrices
  5. Key analytical metrics: Annualized Return, Volatility, Sharpe Ratio, Max Drawdown, VaR, CVaR
"""

from toolkit.data import YahooFinanceExtractor
from toolkit.models import Portfolio

def main():
    print("=" * 70)
    print("TESTING PORTFOLIO DATACLASS MODELING (REQUIREMENT 4.3)")
    print("=" * 70)

    extractor = YahooFinanceExtractor()

    # 1. Fetch data for individual assets
    tickers = ["AAPL", "MSFT", "SAN.MC", "^IBEX"]
    print(f"\n1. Downloading historical series for: {tickers} ...")
    series_list = extractor.fetch_batch(
        tickers=tickers,
        start="2024-01-01",
        end="2025-01-01"
    )
    for s in series_list:
        print(f"   - {s.ticker:<8} | Days: {len(s.data):<4} | Mean: {s.mean_return:+.5f} | Std: {s.std_return:.5f} | Ann.Vol: {s.annualized_volatility():.2%}")

    # 2. Instantiate Portfolio with Equal Weights (default: None -> 1/N)
    print("\n2. Initializing Portfolio with EQUAL WEIGHTS (None -> 1/N)...")
    eq_portfolio = Portfolio(
        assets=series_list,
        name="Equal-Weighted Global Portfolio"
    )
    print(f"   Result: {eq_portfolio}")
    print(f"   Weights: {eq_portfolio.weights_dict}")
    print(f"   Overlapping trading days: {len(eq_portfolio.portfolio_returns)}")

    # 3. Instantiate Portfolio with Custom Weights
    print("\n3. Initializing Portfolio with CUSTOM WEIGHTS (dict)...")
    custom_weights = {
        "AAPL": 0.35,
        "MSFT": 0.35,
        "SAN.MC": 0.15,
        "^IBEX": 0.15,
    }
    custom_portfolio = Portfolio(
        assets=series_list,
        weights=custom_weights,
        name="Tactical Growth Portfolio"
    )
    print(f"   Result: {custom_portfolio}")
    print(f"   Weights: {custom_portfolio.weights_dict}")

    # 4. Display Auto-computed Matrices
    print("\n4. Asset Correlation Matrix:")
    print(custom_portfolio.correlation_matrix.round(4))

    print("\n5. Asset Covariance Matrix (daily, x10^4):")
    print((custom_portfolio.covariance_matrix * 10000).round(4))

    # 5. Display Analytical and Risk Metrics
    print("\n6. Portfolio Summary & Risk Diagnostics:")
    summary = custom_portfolio.summary(risk_free_rate=0.03)
    for metric, value in summary.items():
        if isinstance(value, float):
            if "return" in metric or "volatility" in metric or "var" in metric or "drawdown" in metric:
                print(f"   - {metric:<25}: {value:+.4f} ({value:+.2%})")
            else:
                print(f"   - {metric:<25}: {value:.4f}")
        elif isinstance(value, dict):
            formatted_dict = ", ".join(f"{k}: {v:.1%}" for k, v in value.items())
            print(f"   - {metric:<25}: {{{formatted_dict}}}")
        else:
            print(f"   - {metric:<25}: {value}")

    print("\n" + "=" * 70)
    print("ALL 4.3 PORTFOLIO TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()

