"""Data ingestion layer for market and macroeconomic series."""

from __future__ import annotations

from .base import BaseDataExtractor
from .fred import FREDExtractor
from .yahoo import YahooFinanceExtractor

__all__ = ["BaseDataExtractor", "FREDExtractor", "YahooFinanceExtractor"]
