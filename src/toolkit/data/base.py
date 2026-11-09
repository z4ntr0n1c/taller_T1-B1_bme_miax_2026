"""Abstract base class and shared normalization logic for market data extractors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date

import pandas as pd

from ..models.series import PriceSeries


class BaseDataExtractor(ABC):
    """Abstract interface defining the standardized data ingestion contract."""

    @abstractmethod
    def fetch_series(
        self,
        ticker: str,
        start: date | str,
        end: date | str | None = None,
        asset_type: str = "equity",
    ) -> PriceSeries:
        """Fetch a single asset series and return a standardized :class:`PriceSeries`."""

    @abstractmethod
    def fetch_batch(
        self,
        tickers: Sequence[str],
        start: date | str,
        end: date | str | None = None,
        asset_type: str = "equity",
    ) -> list[PriceSeries]:
        """Fetch multiple assets simultaneously in batch."""

    @staticmethod
    def _normalize_close_dataframe(df: pd.DataFrame, close_col: str = "close") -> pd.DataFrame:
        """Convert a DataFrame with a close price column into the canonical schema.

        Canonical schema:
          - ``DatetimeIndex`` named ``"date"``, sorted chronologically.
          - Numeric ``"close"`` column (rows with missing close dropped).
          - ``"returns"`` column with simple daily percentage changes.

        Args:
            df: Source DataFrame.
            close_col: Column name to treat as ``"close"``.

        Returns:
            Standardized DataFrame with columns ``["close", "returns"]``.

        Raises:
            KeyError: If ``close_col`` is not present in ``df``.
        """
        out = df.copy()
        out.index = pd.DatetimeIndex(pd.to_datetime(out.index), name="date")
        out = out.sort_index()

        if close_col != "close" and close_col in out.columns:
            out = out.rename(columns={close_col: "close"})

        if "close" not in out.columns:
            raise KeyError(f"Downloaded data is missing a '{close_col}' column.")

        out["close"] = pd.to_numeric(out["close"], errors="coerce")
        out = out.dropna(subset=["close"])
        out["returns"] = out["close"].pct_change()
        return out[["close", "returns"]]
