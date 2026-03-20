from __future__ import annotations

import sys
from pathlib import Path

from pydantic import Field

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend.app.models.strategy_spec import StrictModel


class UniversePlan(StrictModel):
    asset_class: str
    filters: dict[str, object] = Field(default_factory=dict)


class CompiledSignal(StrictModel):
    name: str
    kind: str
    source: str
    parameters: dict[str, object] = Field(default_factory=dict)


class SelectionPlan(StrictModel):
    source_signal: str
    top_n: int
    max_positions: int
    order: str
    min_score: float | None = None


class PortfolioPlan(StrictModel):
    method: str
    max_positions: int
    target_gross_exposure: float
    weight_per_position: float


class RiskPlan(StrictModel):
    constraints: dict[str, float] = Field(default_factory=dict)


class ExecutionPlan(StrictModel):
    order_type: str
    time_in_force: str
    slippage_bps: float
    commission_bps: float
    allow_fractional_shares: bool
    deployment_mode: str


class SchedulePlan(StrictModel):
    frequency: str
    day_of_week: str | None = None
    day_of_month: int | None = None
    timezone: str


class DataRequirement(StrictModel):
    dataset: str
    fields: list[str] = Field(default_factory=list)
    lookback_days: int = 0


class CompiledStrategy(StrictModel):
    universe_plan: UniversePlan
    signal_plan: dict[str, CompiledSignal]
    selection_plan: SelectionPlan
    portfolio_plan: PortfolioPlan
    risk_plan: RiskPlan
    execution_plan: ExecutionPlan
    schedule: SchedulePlan
    benchmark_symbol: str = "SPY"
    initial_capital: float = 100000.0
    data_requirements: list[DataRequirement] = Field(default_factory=list)
