"""FREDExtractor — Data extractor for macroeconomic series from FRED.

Typical macro series IDs:
    'DFF'              – Fed Funds Effective Rate (daily)
    'GS10'             – 10-Year Treasury Constant Maturity Rate (monthly)
    'CPIAUCSL'         – Consumer Price Index (monthly)
    'UNRATE'           – Civilian Unemployment Rate (monthly)
    'VIXCLS'           – CBOE Volatility Index (VIX, daily)
    'DCOILWTICO'       – Crude Oil WTI spot price (daily)
    'GOLDAMGBD228NLBM' – Gold fixing price (daily)

All outputs are normalized to the same :class:`PriceSeries` format as
:class:`YahooFinanceExtractor` so both sources are fully interoperable downstream.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Sequence
from datetime import date

import pandas as pd
import pandas_datareader.data as web
import requests

from ..models.series import PriceSeries
from .base import BaseDataExtractor

logger = logging.getLogger(__name__)

FRED_GRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def _fetch_fred_csv(series_id: str, start: date | str, end: date | str | None = None) -> pd.DataFrame:
    """Fallback downloader using FRED's public ``fredgraph.csv`` endpoint."""
    params: dict[str, str] = {"id": series_id, "cosd": str(start)}
    if end is not None:
        params["coed"] = str(end)
    response = requests.get(FRED_GRAPH_CSV_URL, params=params, timeout=30)
    response.raise_for_status()
    frame = pd.read_csv(io.StringIO(response.text), na_values=["."])
    if series_id not in frame.columns or frame.shape[1] < 2:
        raise ValueError(f"FRED CSV response does not contain column '{series_id}'.")
    date_col = frame.columns[0]
    frame[date_col] = pd.to_datetime(frame[date_col])
    return frame.set_index(date_col)[[series_id]]


class FREDExtractor(BaseDataExtractor):
    """Data extractor implementation using the FRED API (Federal Reserve Economic Data).

    Fetches macroeconomic and financial series and normalizes them into the shared
    :class:`PriceSeries` format, keeping the data layer fully interoperable with other
    extractor implementations.
    """

    def _fetch_via_fred_csv(
        self,
        ticker: str,
        start: date | str,
        end: date | str | None = None,
    ) -> pd.DataFrame:
        """Fallback CSV fetch for public FRED series using the official FRED endpoint."""
        return _fetch_fred_csv(ticker, start, end)

    def fetch_series(
        self,
        ticker: str,
        start: date | str,
        end: date | str | None = None,
        asset_type: str = "macro",
    ) -> PriceSeries:
        """Fetch a single FRED series and return a standardized :class:`PriceSeries`.

        Args:
            ticker: FRED series ID (e.g. ``'DFF'``, ``'CPIAUCSL'``, ``'VIXCLS'``).
            start: Start date in ``'YYYY-MM-DD'`` format or ``date``.
            end: End date in ``'YYYY-MM-DD'`` format or ``date``.
            asset_type: Semantic label for the series (default: ``'macro'``).

        Returns:
            :class:`PriceSeries` with Date-indexed DataFrame containing ``'close'`` and ``'returns'``.

        Raises:
            ValueError: If FRED returns no data for the given series ID and date range.
        """
        try:
            raw: pd.DataFrame = web.DataReader(ticker, "fred", start=start, end=end)
        except Exception as exc:
            logger.debug("pandas_datareader failed for %s (%s), falling back to fredgraph.csv", ticker, exc)
            raw = self._fetch_via_fred_csv(ticker, start, end)

        if raw is None or raw.empty:
            raise ValueError(
                f"FRED returned no data for series '{ticker}' in range [{start}, {end}]."
            )

        standardized_df = self._standardize_dataframe(raw, ticker)
        logger.info("FRED %s: %d observations", ticker.upper(), len(standardized_df))
        return PriceSeries(
            ticker=ticker.upper(),
            asset_type=asset_type,
            data=standardized_df,
        )

    def fetch_batch(
        self,
        tickers: Sequence[str],
        start: date | str,
        end: date | str | None = None,
        asset_type: str = "macro",
    ) -> list[PriceSeries]:
        """Fetch multiple FRED series in a single request and return a list of :class:`PriceSeries`.

        Args:
            tickers: Sequence of FRED series IDs.
            start: Start date in ``'YYYY-MM-DD'`` format or ``date``.
            end: End date in ``'YYYY-MM-DD'`` format or ``date``.
            asset_type: Semantic label applied to all series (default: ``'macro'``).

        Returns:
            List of :class:`PriceSeries`, one per successfully downloaded series.
        """
        ticker_list = list(tickers)
        if not ticker_list:
            return []

        try:
            batch_df: pd.DataFrame = web.DataReader(ticker_list, "fred", start=start, end=end)
        except Exception as exc:
            logger.debug("pandas_datareader batch failed (%s), fetching series via fredgraph.csv", exc)
            frames = list(map(lambda t: _fetch_fred_csv(t, start, end), ticker_list))
            batch_df = pd.concat(frames, axis=1, join="outer").sort_index()

        def _extract_fred_series(ticker: str) -> PriceSeries | None:
            if ticker not in batch_df.columns:
                logger.warning("FRED: series '%s' not found in batch response.", ticker)
                return None

            series_df = batch_df[[ticker]].dropna()
            if series_df.empty:
                logger.warning("FRED: series '%s' has no valid observations.", ticker)
                return None

            std_df = self._standardize_dataframe(series_df, ticker)
            return PriceSeries(
                ticker=ticker.upper(),
                asset_type=asset_type,
                data=std_df,
            )

        results: list[PriceSeries] = list(filter(None, map(_extract_fred_series, ticker_list)))
        logger.info("FRED batch: %d/%d series loaded", len(results), len(ticker_list))
        return results

    @staticmethod
    def _standardize_dataframe(
        df: pd.DataFrame,
        series_name: str | None = None,
    ) -> pd.DataFrame:
        """Normalize a raw FRED DataFrame to the canonical ``'close'`` / ``'returns'`` schema.

        Args:
            df: Raw DataFrame from ``pandas_datareader`` or ``fredgraph.csv``.
            series_name: FRED series ID used to locate the column when ``df`` is multi-column.

        Returns:
            DataFrame with ``DatetimeIndex`` named ``'date'``, columns ``['close', 'returns']``.

        Raises:
            KeyError: If the target series column cannot be found.
        """
        if series_name is not None and series_name in df.columns:
            close_col = series_name
        elif len(df.columns) == 1:
            close_col = str(df.columns[0])
        else:
            raise KeyError(
                f"Could not locate column for series '{series_name}' in FRED response."
            )

        return BaseDataExtractor._normalize_close_dataframe(df, close_col=close_col)


