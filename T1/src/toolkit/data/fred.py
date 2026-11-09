"""Federal Reserve (FRED) connector for macroeconomic and market indicator series."""

from __future__ import annotations

import io

import numpy as np
import pandas as pd

try:
    from pandas_datareader import data as pdr
except ImportError:  # pragma: no cover - compatibility fallback
    pdr = None

from ..models.series import PriceSeries
from .base import BaseDataExtractor


class FREDExtractor(BaseDataExtractor):
    """Fetch macroeconomic time series from the FRED API and standardize them."""

    @staticmethod
    def _standardize_dataframe(df: pd.DataFrame, series_name: str | None = None) -> pd.DataFrame:
        """Standardize a raw FRED dataframe to the canonical close/returns schema."""
        standardized = df.copy()
        if standardized.empty:
            return standardized

        if isinstance(standardized.columns, pd.MultiIndex):
            standardized.columns = [str(col[-1]) for col in standardized.columns]

        if series_name is not None and series_name in standardized.columns:
            standardized = standardized[[series_name]]
        elif len(standardized.columns) > 1:
            standardized = standardized.iloc[:, :1]

        standardized.index = pd.to_datetime(standardized.index)
        standardized.index.name = "date"
        standardized = standardized.rename(columns={standardized.columns[0]: "close"})
        standardized["close"] = pd.to_numeric(standardized["close"], errors="coerce")
        standardized["close"] = standardized["close"].replace([np.inf, -np.inf], np.nan)
        standardized = standardized.dropna(subset=["close"])
        standardized["returns"] = standardized["close"].pct_change(fill_method=None)
        return standardized[["close", "returns"]]

    def _fetch_via_pandas_datareader(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Download a FRED series using pandas_datareader when available."""
        if pdr is None:
            raise RuntimeError("pandas_datareader is not installed.")
        return pdr.DataReader(ticker, data_source="fred", start=start, end=end)

    def _fetch_via_fred_csv(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Fallback CSV fetch for public FRED series, using the official FRED endpoint."""
        import requests

        url = (
            "https://fred.stlouisfed.org/graph/fredgraph.csv"
            f"?id={ticker}&cosd={start}&coed={end}&fq=Daily&fam=avg"
        )
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return pd.read_csv(
            io.StringIO(response.text),
            index_col="observation_date",
            parse_dates=["observation_date"],
        )

    def fetch_series(
        self,
        ticker: str,
        start: str,
        end: str,
        asset_type: str = "macro",
    ) -> PriceSeries:
        """Fetch a single macroeconomic series from FRED and wrap it as a PriceSeries."""
        try:
            raw = self._fetch_via_pandas_datareader(ticker, start, end)
        except Exception:
            raw = self._fetch_via_fred_csv(ticker, start, end)

        if raw.empty:
            raise ValueError(f"No macroeconomic data available for FRED series '{ticker}'.")

        standardized = self._standardize_dataframe(raw, series_name=ticker)
        return PriceSeries(ticker=ticker, asset_type=asset_type, data=standardized)

    def fetch_batch(
        self,
        tickers: list[str] | tuple[str, ...],
        start: str,
        end: str,
        asset_type: str = "macro",
    ) -> list[PriceSeries]:
        """Fetch several FRED series as a list of :class:`PriceSeries` objects."""
        return [
            self.fetch_series(ticker=ticker, start=start, end=end, asset_type=asset_type)
            for ticker in tickers
        ]
