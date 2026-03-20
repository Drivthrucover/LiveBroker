from __future__ import annotations

import sys
from pathlib import Path

from pydantic import Field

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend.app.models.strategy_spec import StrictModel


class BacktestCurvePoint(StrictModel):
    date: str
    value: float


class TradeRecord(StrictModel):
    date: str
    symbol: str
    side: str
    weight_change: float
    target_weight: float
    price: float


class DrawdownPoint(StrictModel):
    date: str
    drawdown: float


class BacktestMetrics(StrictModel):
    cagr: float
    sharpe: float
    sortino: float
    max_drawdown: float
    turnover: float


class BacktestResult(StrictModel):
    equity_curve: list[BacktestCurvePoint] = Field(default_factory=list)
    benchmark_curve: list[BacktestCurvePoint] = Field(default_factory=list)
    trades: list[TradeRecord] = Field(default_factory=list)
    drawdowns: list[DrawdownPoint] = Field(default_factory=list)
    metrics: BacktestMetrics
