"""Market data access package."""

from .market_data_service import (
    MarketDataService,
    get_historical_data,
    get_security_master,
    normalize_market_data_frame,
    normalize_security_master_frame,
)

__all__ = [
    "MarketDataService",
    "get_historical_data",
    "get_security_master",
    "normalize_market_data_frame",
    "normalize_security_master_frame",
]
