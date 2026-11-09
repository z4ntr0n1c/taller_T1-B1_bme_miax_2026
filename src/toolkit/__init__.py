"""toolkit: Financial data extraction, portfolio modeling, Monte Carlo simulation, and reporting."""

from __future__ import annotations

from . import data, models, reports, utils
from .data import BaseDataExtractor, FREDExtractor, YahooFinanceExtractor
from .logging_utils import setup_logging
from .models import MonteCarloEngine, MonteCarloResult, Portfolio, PriceSeries
from .utils import (
    ValidationError,
    align_calendar_series,
    clean_missing_values,
    filter_anomalous_returns,
    validate_portfolio_weights,
    validate_price_dataframe,
)

__version__ = "0.1.0"

__all__ = [
    "BaseDataExtractor",
    "FREDExtractor",
    "MonteCarloEngine",
    "MonteCarloResult",
    "Portfolio",
    "PriceSeries",
    "ValidationError",
    "YahooFinanceExtractor",
    "__version__",
    "align_calendar_series",
    "clean_missing_values",
    "data",
    "filter_anomalous_returns",
    "models",
    "reports",
    "setup_logging",
    "utils",
    "validate_portfolio_weights",
    "validate_price_dataframe",
]



