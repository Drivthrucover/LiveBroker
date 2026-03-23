from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, status
from pydantic import Field
from requests import HTTPError

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[4]))

from backend.app.backtest.run_backtest import run_backtest
from backend.app.compiler.compiler import CapabilityRegistry, CompilationContext, DataRegistry, compile_strategy
from backend.app.data.market_data_service import MarketDataService
from backend.app.models.backtest_result import BacktestResult
from backend.app.models.compiled_strategy import CompiledStrategy
from backend.app.models.strategy_spec import StrategySpec, StrictModel

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class RunBacktestRequest(StrictModel):
    compiled_strategy: CompiledStrategy
    strategy_spec: StrategySpec | None = None
    market_data: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/run", response_model=BacktestResult)
def run_backtest_route(request: RunBacktestRequest) -> BacktestResult:
    compiled_strategy = _hydrate_compiled_strategy(
        compiled_strategy=request.compiled_strategy,
        strategy_spec=request.strategy_spec,
    )

    try:
        market_data_frame = (
            pd.DataFrame(request.market_data)
            if request.market_data
            else _fetch_market_data_for_compiled_strategy(compiled_strategy)
        )
    except HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Market data provider request failed with status {status_code}.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return run_backtest(
        compiled_strategy=compiled_strategy,
        market_data=market_data_frame,
    )


def _hydrate_compiled_strategy(
    compiled_strategy: CompiledStrategy,
    strategy_spec: StrategySpec | None,
) -> CompiledStrategy:
    filters = compiled_strategy.universe_plan.filters
    has_symbols = isinstance(filters.get("symbols"), list) and bool(filters.get("symbols"))
    has_dates = bool(compiled_strategy.backtest_start_date and compiled_strategy.backtest_end_date)
    if has_symbols and has_dates:
        return compiled_strategy

    if strategy_spec is None:
        return compiled_strategy

    return compile_strategy(
        spec=strategy_spec,
        capability_registry=CapabilityRegistry(),
        data_registry=DataRegistry(),
        context=CompilationContext(),
    )


def _fetch_market_data_for_compiled_strategy(compiled_strategy: CompiledStrategy) -> pd.DataFrame:
    symbols = _resolve_symbols(compiled_strategy)
    start_date = compiled_strategy.backtest_start_date
    end_date = compiled_strategy.backtest_end_date
    if not start_date or not end_date:
        raise ValueError(
            "CompiledStrategy must include backtest_start_date and backtest_end_date when market_data is omitted."
        )

    service = MarketDataService(provider="polygon")
    return service.get_historical_data(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
    )


def _resolve_symbols(compiled_strategy: CompiledStrategy) -> list[str]:
    filters = compiled_strategy.universe_plan.filters
    raw_symbols = filters.get("symbols")
    if not isinstance(raw_symbols, list) or not raw_symbols:
        raise ValueError(
            "Automatic market data fetch currently requires universe.symbols to be explicitly set."
        )

    normalized = [str(symbol).upper() for symbol in raw_symbols]
    benchmark_symbol = compiled_strategy.benchmark_symbol.upper()
    if benchmark_symbol not in normalized:
        normalized.append(benchmark_symbol)
    return normalized
