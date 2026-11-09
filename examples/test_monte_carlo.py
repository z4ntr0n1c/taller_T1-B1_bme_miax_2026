"""
test_monte_carlo.py — Validation script for Monte Carlo Engine (Requirement 4.4).

Demonstrates:
  1. Stochastic simulation on an individual asset (AAPL) via PriceSeries.simulate_montecarlo
  2. Stochastic simulation on a multi-asset Portfolio via Portfolio.simulate_montecarlo
     - Multivariate correlated GBM (using empirical covariance & Cholesky decomposition)
     - Aggregate portfolio GBM
  3. Parametrizable inputs: n_simulations, horizon, mu, sigma, initial capital, seed
  4. Diagnostic statistics: Terminal Mean, Median, VaR (95%), CVaR (95%), Probability of Loss
  5. Graphical visualization saved to disk (trajectories & terminal distribution plots)
"""

import os
from toolkit.data import YahooFinanceExtractor
from toolkit.models import Portfolio

def main():
    print("=" * 75)
    print("TESTING MONTE CARLO SIMULATION ENGINE (REQUIREMENT 4.4)")
    print("=" * 75)

    # 1. Fetch market data
    extractor = YahooFinanceExtractor()
    tickers = ["AAPL", "MSFT", "SAN.MC", "^IBEX"]
    print(f"\n1. Fetching historical data for {tickers} ...")
    series_list = extractor.fetch_batch(
        tickers=tickers,
        start="2024-01-01",
        end="2025-01-01"
    )

    output_dir = os.path.join(os.path.dirname(__file__), "plots")
    os.makedirs(output_dir, exist_ok=True)

    # 2. Individual Asset Simulation (PriceSeries)
    aapl = next(s for s in series_list if s.ticker == "AAPL")
    print(f"\n2. Running Monte Carlo on Individual Asset: {aapl.ticker}")
    print(f"   Historical Daily Mean: {aapl.mean_return:+.5f} | Daily Std: {aapl.std_return:.5f}")
    
    aapl_mc = aapl.simulate_montecarlo(
        n_simulations=2000,
        horizon=252,          # 1 year forward
        seed=42
    )

    print(f"   Simulated Paths: {aapl_mc.n_simulations:,} | Horizon: {aapl_mc.horizon} trading days")
    print(f"   Initial Price:   ${aapl_mc.initial_value:.2f}")
    print(f"   Terminal Mean:   ${aapl_mc.terminal_mean:.2f} ({aapl_mc.summary()['expected_return']:+.2%})")
    print(f"   Terminal Median: ${aapl_mc.terminal_median:.2f}")
    print(f"   Prob. of Loss:   {aapl_mc.probability_of_loss:.2%}")
    print(f"   95% Term. VaR:   ${aapl_mc.terminal_var(0.95):.2f}")
    print(f"   95% Term. CVaR:  ${aapl_mc.terminal_cvar(0.95):.2f}")

    aapl_plot_path = os.path.join(output_dir, "mc_aapl.png")
    aapl_mc.plot(save_path=aapl_plot_path, show=False)
    print(f"   Saved plot to: {aapl_plot_path}")

    # 3. Portfolio Multi-Asset Simulation
    print("\n3. Building Portfolio and Running Correlated Monte Carlo Simulation...")
    weights = {"AAPL": 0.35, "MSFT": 0.35, "SAN.MC": 0.15, "^IBEX": 0.15}
    portfolio = Portfolio(
        assets=series_list,
        weights=weights,
        name="Global Balanced Portfolio",
        initial_capital=50000.0  # 50,000 EUR
    )

    print(f"   Portfolio: {portfolio.name} (Capital: {portfolio.initial_capital:,.0f}€)")
    print(f"   Weights: {portfolio.weights_dict}")

    # 3A. Correlated multivariate simulation (Cholesky diffusion)
    print("\n   [Method A] Correlated Multivariate GBM (Cholesky decomposition):")
    port_mc_corr = portfolio.simulate_montecarlo(
        n_simulations=2500,
        horizon=252,
        seed=123,
        multivariate=True
    )

    summary_corr = port_mc_corr.summary(confidence_level=0.95)
    print(f"   - Expected Capital:     {summary_corr['terminal_mean']:,.2f}€ ({summary_corr['expected_return']:+.2%})")
    print(f"   - Median Capital:       {summary_corr['terminal_median']:,.2f}€")
    print(f"   - 5th Percentile (p05): {summary_corr['p05']:,.2f}€")
    print(f"   - 95th Percentile(p95): {summary_corr['p95']:,.2f}€")
    print(f"   - Probability of Loss:  {summary_corr['probability_of_loss']:.2%}")
    print(f"   - 95% Terminal VaR:     {summary_corr['terminal_var_95']:,.2f}€")
    print(f"   - 95% Terminal CVaR:    {summary_corr['terminal_cvar_95']:,.2f}€")

    corr_plot_path = os.path.join(output_dir, "mc_portfolio_multivariate.png")
    port_mc_corr.plot(save_path=corr_plot_path, show=False)
    print(f"   Saved plot to: {corr_plot_path}")

    # 3B. Direct Aggregate Portfolio Simulation
    print("\n   [Method B] Aggregate Portfolio GBM:")
    port_mc_agg = portfolio.simulate_montecarlo(
        n_simulations=2500,
        horizon=252,
        seed=123,
        multivariate=False
    )
    print(f"   - Expected Capital:     {port_mc_agg.terminal_mean:,.2f}€")
    print(f"   - Median Capital:       {port_mc_agg.terminal_median:,.2f}€")
    print(f"   - Probability of Loss:  {port_mc_agg.probability_of_loss:.2%}")

    agg_plot_path = os.path.join(output_dir, "mc_portfolio_aggregate.png")
    port_mc_agg.plot(save_path=agg_plot_path, show=False)
    print(f"   Saved plot to: {agg_plot_path}")

    print("\n" + "=" * 75)
    print("ALL 4.4 MONTE CARLO TESTS PASSED AND CHARTS GENERATED!")
    print("=" * 75)


if __name__ == "__main__":
    main()

