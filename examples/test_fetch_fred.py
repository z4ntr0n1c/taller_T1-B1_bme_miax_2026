"""
test_fetch_fred.py — Verify FREDExtractor (second data source: macroeconomic data).

Demonstrates that the FREDExtractor produces PriceSeries objects with the same
interface as YahooFinanceExtractor, keeping the data layer fully interoperable.

Common FRED series IDs used here:
    DFF         – Fed Funds Effective Rate (daily)
    VIXCLS      – CBOE Volatility Index / VIX (daily)
    DCOILWTICO  – WTI Crude Oil spot price (daily)
"""

from toolkit.data import FREDExtractor, YahooFinanceExtractor

fred = FREDExtractor()
yahoo = YahooFinanceExtractor()

print("=" * 60)
print("FRED — Single macro series")
print("=" * 60)

fed_funds = fred.fetch_series("DFF", start="2024-01-01", end="2025-01-01")
print(
    f"[{fed_funds.asset_type.upper()}] {fed_funds.ticker} | "
    f"Mean: {fed_funds.mean_return:.6f} | Std: {fed_funds.std_return:.6f} | "
    f"Observations: {len(fed_funds.data)}"
)

print()
print("=" * 60)
print("FRED — Batch macro series")
print("=" * 60)

macro_series = fred.fetch_batch(
    tickers=["VIXCLS", "DCOILWTICO"],
    start="2024-01-01",
    end="2025-01-01",
    asset_type="macro",
)
for s in macro_series:
    print(
        f"[{s.asset_type.upper()}] {s.ticker} | "
        f"Mean: {s.mean_return:.6f} | Std: {s.std_return:.6f} | "
        f"Observations: {len(s.data)}"
    )

print()
print("=" * 60)
print("Mixed portfolio — Yahoo equities + FRED macro (same PriceSeries interface)")
print("=" * 60)

# Yahoo data
equities = yahoo.fetch_batch(
    tickers=["AAPL", "SAN.MC"],
    start="2024-01-01",
    end="2025-01-01",
    asset_type="equity",
)

# Merge into one unified list — all share the same PriceSeries contract
all_series = equities + macro_series

for s in all_series:
    print(
        f"[{s.asset_type.upper():6s}] {s.ticker:<20} | "
        f"Mean return: {s.mean_return:+.6f} | Std: {s.std_return:.6f}"
    )

