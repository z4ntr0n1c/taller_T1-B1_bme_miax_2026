"""Abstract data extraction contract used by all market-data connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from ..models.series import PriceSeries


class BaseDataExtractor(ABC):
    """Contract for all market-data connectors in the toolkit.

    Every subclass is expected to fetch a raw DataFrame from a source API,
    standardize it to the canonical ``['close', 'returns']`` schema, and return a
    :class:`~toolkit.models.series.PriceSeries`.
    """

    @staticmethod
    def _normalize_close_dataframe(
        df: pd.DataFrame,
        close_col: str = "close",
    ) -> pd.DataFrame:
        """Normalize a raw market dataframe to the canonical close/returns schema."""
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Expected pandas DataFrame, got {type(df).__name__}.")

        normalized = df.copy()
        normalized = normalized.sort_index()
        normalized.index = pd.to_datetime(normalized.index)
        normalized.index.name = "date"

        if close_col not in normalized.columns:
            lower_map = {column.lower(): column for column in normalized.columns}
            key = close_col.lower()
            if key in lower_map:
                close_col = lower_map[key]
            else:
                preferred = ["close", "Close", "Adj Close", "adj close"]
                found = next((col for col in normalized.columns if str(col).lower() in preferred), None)
                if found is None:
                    raise ValueError(
                        f"Could not find a usable close-price column in DataFrame columns: {list(normalized.columns)}"
                    )
                close_col = found

        normalized[close_col] = pd.to_numeric(normalized[close_col], errors="coerce")
        normalized = normalized[[close_col]].dropna(subset=[close_col])
        normalized = normalized.rename(columns={close_col: "close"})
        normalized["returns"] = normalized["close"].pct_change()
        return normalized

    @staticmethod
    def _standardize_dataframe(df: pd.DataFrame, *args, **kwargs) -> pd.DataFrame:
        """Standardize market data into the toolkit's canonical schema."""
        return BaseDataExtractor._normalize_close_dataframe(df, *args, **kwargs)

    @abstractmethod
    def fetch_series(
        self,
        ticker: str,
        start: str,
        end: str,
        asset_type: str = "equity",
    ) -> PriceSeries:
        """Fetch a single time series and return a :class:`PriceSeries`."""

    def fetch_batch(
        self,
        tickers: list[str] | tuple[str, ...],
        start: str,
        end: str,
        asset_type: str = "equity",
    ) -> list[PriceSeries]:
        """Fetch a batch of market series for the requested tickers."""
        return [
            self.fetch_series(ticker=ticker, start=start, end=end, asset_type=asset_type)
            for ticker in tickers
        ]
