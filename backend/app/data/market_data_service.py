from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import requests

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))


ProviderName = Literal["polygon", "alpha_vantage"]

MARKET_DATA_COLUMNS = [
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "adjusted_close",
]

SECURITY_MASTER_COLUMNS = [
    "symbol",
    "exchange",
    "sector",
    "market_cap",
    "avg_dollar_volume",
]


class MarketDataService:
    def __init__(
        self,
        provider: ProviderName = "polygon",
        polygon_api_key: str | None = None,
        alpha_vantage_api_key: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.provider = provider
        self.polygon_api_key = polygon_api_key or _get_env_value("POLYGON_API_KEY")
        self.alpha_vantage_api_key = alpha_vantage_api_key or _get_env_value("ALPHAVANTAGE_API_KEY")
        self.session = session or requests.Session()

    def get_historical_data(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame(columns=MARKET_DATA_COLUMNS)

        frames = [
            self._fetch_symbol_history(symbol=symbol, start_date=start_date, end_date=end_date)
            for symbol in symbols
        ]
        if not frames:
            return pd.DataFrame(columns=MARKET_DATA_COLUMNS)
        return normalize_market_data_frame(pd.concat(frames, ignore_index=True))

    def get_security_master(self) -> pd.DataFrame:
        if self.provider != "polygon":
            raise NotImplementedError(
                "Security master fetching is implemented only for the polygon provider in v1"
            )
        if not self.polygon_api_key:
            raise ValueError("POLYGON_API_KEY is required to fetch security master data")

        response = self.session.get(
            "https://api.polygon.io/v3/reference/tickers",
            params={
                "market": "stocks",
                "active": "true",
                "limit": 1000,
                "apiKey": self.polygon_api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        rows = []
        for item in payload.get("results", []):
            rows.append(
                {
                    "symbol": item.get("ticker"),
                    "exchange": item.get("primary_exchange") or "",
                    "sector": item.get("sic_description") or "",
                    "market_cap": float(item.get("market_cap") or 0.0),
                    "avg_dollar_volume": 0.0,
                }
            )
        return normalize_security_master_frame(pd.DataFrame(rows))

    def _fetch_symbol_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        if self.provider == "polygon":
            return self._fetch_polygon_history(symbol=symbol, start_date=start_date, end_date=end_date)
        if self.provider == "alpha_vantage":
            return self._fetch_alpha_vantage_history(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
            )
        raise ValueError(f"Unsupported provider: {self.provider}")

    def _fetch_polygon_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        if not self.polygon_api_key:
            raise ValueError("POLYGON_API_KEY is required to fetch Polygon market data")

        response = self.session.get(
            f"https://api.polygon.io/v2/aggs/ticker/{symbol.upper()}/range/1/day/{start_date}/{end_date}",
            params={
                "adjusted": "true",
                "sort": "asc",
                "limit": 50000,
                "apiKey": self.polygon_api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        rows = [
            {
                "symbol": symbol.upper(),
                "date": pd.to_datetime(item["t"], unit="ms", utc=True).tz_localize(None),
                "open": float(item["o"]),
                "high": float(item["h"]),
                "low": float(item["l"]),
                "close": float(item["c"]),
                "volume": float(item["v"]),
                "adjusted_close": float(item["c"]),
            }
            for item in payload.get("results", [])
        ]
        return normalize_market_data_frame(pd.DataFrame(rows))

    def _fetch_alpha_vantage_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        if not self.alpha_vantage_api_key:
            raise ValueError("ALPHAVANTAGE_API_KEY is required to fetch Alpha Vantage market data")

        response = self.session.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": symbol.upper(),
                "outputsize": "full",
                "apikey": self.alpha_vantage_api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        series = payload.get("Time Series (Daily)", {})
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        rows = []
        for date_str, values in series.items():
            timestamp = pd.Timestamp(date_str)
            if timestamp < start_ts or timestamp > end_ts:
                continue
            rows.append(
                {
                    "symbol": symbol.upper(),
                    "date": timestamp,
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["4. close"]),
                    "volume": float(values["6. volume"]),
                    "adjusted_close": float(values["5. adjusted close"]),
                }
            )
        return normalize_market_data_frame(pd.DataFrame(rows))


def normalize_market_data_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=MARKET_DATA_COLUMNS)

    required_aliases = {
        "symbol": "symbol",
        "date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "adjusted_close": "adjusted_close",
        "adj_close": "adjusted_close",
    }
    renamed = frame.rename(columns={key: value for key, value in required_aliases.items() if key in frame.columns})
    missing = [column for column in MARKET_DATA_COLUMNS if column not in renamed.columns]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"Market data frame missing required columns: {missing_list}")

    normalized = renamed.loc[:, MARKET_DATA_COLUMNS].copy()
    normalized["symbol"] = normalized["symbol"].astype(str).str.upper()
    normalized["date"] = pd.to_datetime(normalized["date"], utc=False).dt.tz_localize(None)
    for column in ["open", "high", "low", "close", "volume", "adjusted_close"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="raise").astype(float)

    normalized = normalized.sort_values(["date", "symbol"]).drop_duplicates(["date", "symbol"])
    return normalized.reset_index(drop=True)


def normalize_security_master_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=SECURITY_MASTER_COLUMNS)

    renamed = frame.rename(columns={"ticker": "symbol"})
    missing = [column for column in SECURITY_MASTER_COLUMNS if column not in renamed.columns]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"Security master frame missing required columns: {missing_list}")

    normalized = renamed.loc[:, SECURITY_MASTER_COLUMNS].copy()
    normalized["symbol"] = normalized["symbol"].astype(str).str.upper()
    normalized["exchange"] = normalized["exchange"].fillna("").astype(str)
    normalized["sector"] = normalized["sector"].fillna("").astype(str)
    for column in ["market_cap", "avg_dollar_volume"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0.0)

    normalized = normalized.sort_values("symbol").drop_duplicates("symbol")
    return normalized.reset_index(drop=True)


def get_historical_data(
    symbols: list[str],
    start_date: str,
    end_date: str,
    provider: ProviderName = "polygon",
) -> pd.DataFrame:
    service = MarketDataService(provider=provider)
    return service.get_historical_data(symbols=symbols, start_date=start_date, end_date=end_date)


def get_security_master(provider: ProviderName = "polygon") -> pd.DataFrame:
    service = MarketDataService(provider=provider)
    return service.get_security_master()


@lru_cache(maxsize=1)
def _dotenv_fallback_values() -> dict[str, str]:
    values: dict[str, str] = {}
    candidate_paths = [
        Path.cwd() / ".env",
        Path.cwd() / ".env.txt",
        Path.cwd() / "backend" / ".env",
        Path.cwd() / "backend" / ".env.txt",
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[2] / ".env.txt",
    ]
    for path in candidate_paths:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values.setdefault(key.strip(), value.strip())
    return values


def _get_env_value(key: str) -> str | None:
    return os.getenv(key) or _dotenv_fallback_values().get(key)
