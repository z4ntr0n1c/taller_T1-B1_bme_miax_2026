"""Yahoo Finance connector implementing the toolkit data abstraction."""

from __future__ import annotations

import pandas as pd
import yfinance as yf

from ..models.series import PriceSeries
from .base import BaseDataExtractor


class YahooFinanceExtractor(BaseDataExtractor):
    """Fetch equity and index data using Yahoo Finance."""

    @staticmethod
    def _standardize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Standardize a raw Yahoo Finance dataframe to the canonical close/returns schema."""
        if isinstance(df.columns, pd.MultiIndex):
            close_columns = [
                (position, str(column_part).strip().lower())
                for position, column in enumerate(df.columns)
                for column_part in column
                if str(column_part).strip().lower() in {"close", "adj close"}
            ]
            exact_close = [position for position, name in close_columns if name == "close"]
            adjusted_close = [
                position for position, name in close_columns if name == "adj close"
            ]
            candidate_positions = exact_close or adjusted_close
            if not candidate_positions:
                raise ValueError(
                    "Could not find a Close or Adj Close column in Yahoo Finance data."
                )
            close_prices = df.iloc[:, candidate_positions[0]].rename("Close").to_frame()
            df = close_prices

        return BaseDataExtractor._normalize_close_dataframe(df, close_col="Close")

    def fetch_series(
        self,
        ticker: str,
        start: str,
        end: str,
        asset_type: str = "equity",
    ) -> PriceSeries:
        """Download a single ticker's market data from Yahoo Finance."""
        raw = yf.download(
            tickers=ticker,
            start=start,
            end=end,
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
        )

        if raw.empty:
            raise ValueError(f"No Yahoo Finance data returned for ticker '{ticker}'.")

        standardized = self._standardize_dataframe(raw)
        return PriceSeries(ticker=ticker, asset_type=asset_type, data=standardized)

    def fetch_batch(
        self,
        tickers: list[str] | tuple[str, ...],
        start: str,
        end: str,
        asset_type: str = "equity",
    ) -> list[PriceSeries]:
        """Fetch several tickers as a list of :class:`PriceSeries` objects."""
        return [
            self.fetch_series(ticker=ticker, start=start, end=end, asset_type=asset_type)
            for ticker in tickers
        ]
