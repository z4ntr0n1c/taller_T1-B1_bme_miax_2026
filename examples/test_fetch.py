from toolkit.data import YahooFinanceExtractor

extractor = YahooFinanceExtractor()

# 1. Fetch single equity
apple = extractor.fetch_series(ticker="AAPL", start="2025-01-01", end="2026-01-01")
print(f"Loaded: {apple.ticker} | Mean Return: {apple.mean_return:.5f} | Std: {apple.std_return:.5f}")

# 2. Fetch batch equities & indices
portfolio_series = extractor.fetch_batch(
    tickers=["MSFT", "SAN.MC", "^IBEX"],
    start="2025-01-01",
    end="2026-01-01",
)
for s in portfolio_series:
    print(f"Batch item: {s.ticker} ({len(s.data)} trading days)")
