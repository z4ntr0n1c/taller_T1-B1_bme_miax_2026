"""Yahoo Finance data extractor via ``yfinance``."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date

import pandas as pd
import yfinance as yf

from ..models.series import PriceSeries
from .base import BaseDataExtractor

logger = logging.getLogger(__name__)


class YahooFinanceExtractor(BaseDataExtractor):
    """Data extractor implementation using Yahoo Finance (``yfinance``)."""

    def fetch_series(
        self,
        ticker: str,
        start: date | str,
        end: date | str | None = None,
        asset_type: str = "equity",
    ) -> PriceSeries:
        """Fetch and standardize historical price data for a single ticker.

        Args:
            ticker: Yahoo Finance symbol (e.g. ``"AAPL"``, ``"SAN.MC"``, ``"^IBEX"``).
            start: Start date (``YYYY-MM-DD`` or ``date``).
            end: End date (exclusive; ``None`` defaults to today).
            asset_type: Semantic label for the asset (default: ``"equity"``).

        Returns:
            A standardized :class:`PriceSeries`.

        Raises:
            ValueError: If Yahoo Finance returns no data for the ticker.
        """
        raw_df = yf.download(
            tickers=ticker,
            start=str(start),
            end=str(end) if end is not None else None,
            progress=False,
            auto_adjust=True,
        )

        if raw_df is None or raw_df.empty:
            raise ValueError(f"No price data found for ticker '{ticker}'.")

        standardized_df = self._standardize_dataframe(raw_df)
        logger.info("Yahoo %s: %d observations", ticker.upper(), len(standardized_df))
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
        asset_type: str = "equity",
    ) -> list[PriceSeries]:
        """Fetch multiple tickers simultaneously and standardize each into a :class:`PriceSeries`.

        Args:
            tickers: Sequence of Yahoo Finance symbols.
            start: Start date (``YYYY-MM-DD`` or ``date``).
            end: End date (exclusive; ``None`` defaults to today).
            asset_type: Semantic label applied to all tickers (default: ``"equity"``).

        Returns:
            List of :class:`PriceSeries` for all successfully downloaded tickers.
        """
        ticker_list = list(tickers)
        if not ticker_list:
            return []

        if len(ticker_list) == 1:
            return [self.fetch_series(ticker_list[0], start=start, end=end, asset_type=asset_type)]

        batch_df = yf.download(
            tickers=ticker_list,
            start=str(start),
            end=str(end) if end is not None else None,
            group_by="ticker",
            progress=False,
            auto_adjust=True,
        )

        if batch_df is None or batch_df.empty:
            return []

        def _extract_ticker_series(ticker: str) -> PriceSeries | None:
            try:
                ticker_df = batch_df[ticker].dropna(how="all")
            except KeyError:
                logger.warning("Yahoo Finance: ticker '%s' not found in batch response.", ticker)
                return None

            if ticker_df.empty:
                logger.warning("Yahoo Finance: no price rows returned for '%s'.", ticker)
                return None

            std_df = self._standardize_dataframe(ticker_df)
            return PriceSeries(
                ticker=ticker.upper(),
                asset_type=asset_type,
                data=std_df,
            )

        results: list[PriceSeries] = list(filter(None, map(_extract_ticker_series, ticker_list)))
        logger.info("Yahoo batch: %d/%d tickers loaded", len(results), len(ticker_list))
        return results

    @staticmethod
    def _standardize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to lowercase and calculate daily returns."""
        out = df.copy()
        if isinstance(out.columns, pd.MultiIndex):
            lvl0 = out.columns.get_level_values(0).astype(str).str.strip().str.lower()
            lvl1 = out.columns.get_level_values(-1).astype(str).str.strip().str.lower()
            if (lvl0 == "close").any() or (lvl0 == "adj close").any():
                out.columns = lvl0
            else:
                out.columns = lvl1
        else:
            out.columns = out.columns.astype(str).str.strip().str.lower()

        out = out.loc[:, ~out.columns.duplicated()]
        close_col = "close" if "close" in out.columns else "adj close"
        return BaseDataExtractor._normalize_close_dataframe(out, close_col=close_col)
