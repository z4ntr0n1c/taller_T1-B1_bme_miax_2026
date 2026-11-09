from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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
print(
    "\n".join(
        map(
            lambda s: f"Batch item: {s.ticker} ({len(s.data)} trading days)",
            portfolio_series,
        )
    )
)
