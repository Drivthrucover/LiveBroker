from __future__ import annotations

import sys
from pathlib import Path

from pydantic import Field

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend.app.models.compiled_strategy import (
    CompiledSignal,
    CompiledStrategy,
    DataRequirement,
    ExecutionPlan,
    PortfolioPlan,
    RiskPlan,
    SchedulePlan,
    SelectionPlan,
    UniversePlan,
)
from backend.app.models.strategy_spec import SignalSpec, StrategySpec, StrictModel
from backend.app.validator.validator import CapabilityRegistry, ValidationResult, validate_strategy


class DataRegistry(StrictModel):
    available_datasets: set[str] = Field(
        default_factory=lambda: {
            "ohlcv",
            "security_master",
            "earnings_calendar",
        }
    )
    available_fields: set[str] = Field(
        default_factory=lambda: {
            "open",
            "high",
            "low",
            "close",
            "adjusted_close",
            "volume",
            "market_cap",
            "avg_dollar_volume",
        }
    )

    def ensure_available(self, requirements: list[DataRequirement]) -> None:
        missing_datasets = [
            requirement.dataset
            for requirement in requirements
            if requirement.dataset not in self.available_datasets
        ]
        if missing_datasets:
            datasets = ", ".join(sorted(set(missing_datasets)))
            raise ValueError(f"Missing required datasets in data registry: {datasets}")


class CompilationContext(StrictModel):
    timezone: str = "America/New_York"
    default_benchmark: str = "SPY"
    commission_bps: float = 0.0
    slippage_bps: float = 0.0


def compile_strategy(
    spec: StrategySpec,
    capability_registry: CapabilityRegistry,
    data_registry: DataRegistry,
    context: CompilationContext,
) -> CompiledStrategy:
    validation = validate_strategy(spec=spec, capability_registry=capability_registry)
    _raise_for_validation_errors(validation)

    normalized_spec = _normalize_strategy_spec(spec)
    universe_plan = compile_universe(normalized_spec)
    signal_plan = compile_signals(normalized_spec)
    selection_plan = compile_selection(normalized_spec)
    portfolio_plan = compile_portfolio(normalized_spec)
    risk_plan = compile_risk(normalized_spec)
    execution_plan = compile_execution(normalized_spec, context)
    schedule = compile_schedule(normalized_spec, context)
    data_requirements = compile_data_requirements(normalized_spec, signal_plan)
    data_registry.ensure_available(data_requirements)

    return CompiledStrategy(
        universe_plan=universe_plan,
        signal_plan=signal_plan,
        selection_plan=selection_plan,
        portfolio_plan=portfolio_plan,
        risk_plan=risk_plan,
        execution_plan=execution_plan,
        schedule=schedule,
        data_requirements=data_requirements,
    )


def compile_universe(spec: StrategySpec) -> UniversePlan:
    filters: dict[str, object] = {}
    if spec.universe.exchanges:
        filters["exchanges"] = spec.universe.exchanges
    if spec.universe.sectors:
        filters["sectors"] = spec.universe.sectors
    if spec.universe.symbols:
        filters["symbols"] = spec.universe.symbols
    if spec.universe.exclude_symbols:
        filters["exclude_symbols"] = spec.universe.exclude_symbols
    if spec.universe.market_cap_min is not None:
        filters["market_cap_min"] = spec.universe.market_cap_min
    if spec.universe.market_cap_max is not None:
        filters["market_cap_max"] = spec.universe.market_cap_max
    if spec.universe.avg_dollar_volume_min is not None:
        filters["avg_dollar_volume_min"] = spec.universe.avg_dollar_volume_min

    return UniversePlan(asset_class=spec.universe.asset_class, filters=filters)


def compile_signals(spec: StrategySpec) -> dict[str, CompiledSignal]:
    compiled: dict[str, CompiledSignal] = {}
    for signal_name, signal in spec.signals.items():
        parameters = {
            key: value
            for key, value in {
                "lookback_days": signal.lookback_days,
                "fast_lookback_days": signal.fast_lookback_days,
                "slow_lookback_days": signal.slow_lookback_days,
                "window_days": signal.window_days,
                "threshold": signal.threshold,
                "operator": signal.operator,
                **signal.params,
            }.items()
            if value is not None
        }
        compiled[signal_name] = CompiledSignal(
            name=signal_name,
            kind=signal.kind,
            source=signal.source,
            parameters=parameters,
        )
    return compiled


def compile_selection(spec: StrategySpec) -> SelectionPlan:
    return SelectionPlan(
        source_signal=spec.selection.source_signal,
        top_n=spec.selection.top_n,
        max_positions=spec.selection.max_positions,
        order=spec.selection.order,
        min_score=spec.selection.min_score,
    )


def compile_portfolio(spec: StrategySpec) -> PortfolioPlan:
    positions = spec.portfolio_construction.max_positions
    return PortfolioPlan(
        method=spec.portfolio_construction.method,
        max_positions=positions,
        target_gross_exposure=spec.portfolio_construction.target_gross_exposure,
        weight_per_position=spec.portfolio_construction.target_gross_exposure / positions,
    )


def compile_risk(spec: StrategySpec) -> RiskPlan:
    constraints = {
        key: value
        for key, value in {
            "max_position_weight": spec.risk.max_position_weight,
            "max_sector_weight": spec.risk.max_sector_weight,
            "max_turnover": spec.risk.max_turnover,
            "max_drawdown": spec.risk.max_drawdown,
        }.items()
        if value is not None
    }
    return RiskPlan(constraints=constraints)


def compile_execution(spec: StrategySpec, context: CompilationContext) -> ExecutionPlan:
    return ExecutionPlan(
        order_type=spec.execution.order_type,
        time_in_force=spec.execution.time_in_force,
        slippage_bps=spec.execution.slippage_bps or context.slippage_bps,
        commission_bps=spec.execution.commission_bps or context.commission_bps,
        allow_fractional_shares=spec.execution.allow_fractional_shares,
        deployment_mode=spec.deployment.mode,
    )


def compile_schedule(spec: StrategySpec, context: CompilationContext) -> SchedulePlan:
    return SchedulePlan(
        frequency=spec.rebalance.frequency,
        day_of_week=spec.rebalance.day_of_week,
        day_of_month=spec.rebalance.day_of_month,
        timezone=context.timezone,
    )


def compile_data_requirements(
    spec: StrategySpec,
    signal_plan: dict[str, CompiledSignal],
) -> list[DataRequirement]:
    requirements_by_dataset: dict[str, DataRequirement] = {}

    def upsert_requirement(dataset: str, fields: set[str], lookback_days: int = 0) -> None:
        existing = requirements_by_dataset.get(dataset)
        if existing is None:
            requirements_by_dataset[dataset] = DataRequirement(
                dataset=dataset,
                fields=sorted(fields),
                lookback_days=lookback_days,
            )
            return

        existing.fields = sorted(set(existing.fields).union(fields))
        existing.lookback_days = max(existing.lookback_days, lookback_days)

    upsert_requirement(dataset="security_master", fields={"symbol"})
    upsert_requirement(dataset="ohlcv", fields={signal.source for signal in spec.signals.values()})

    for signal in signal_plan.values():
        if signal.kind == "exclude_earnings_window":
            upsert_requirement(dataset="earnings_calendar", fields={"earnings_date"})

        lookback_days = max(
            (
                int(value)
                for key, value in signal.parameters.items()
                if key.endswith("lookback_days") or key == "window_days"
            ),
            default=0,
        )
        upsert_requirement(dataset="ohlcv", fields={signal.source}, lookback_days=lookback_days)

    if spec.benchmark.symbol:
        upsert_requirement(dataset="ohlcv", fields={"adjusted_close"})

    return list(requirements_by_dataset.values())


def _normalize_strategy_spec(spec: StrategySpec) -> StrategySpec:
    normalized_signals: dict[str, SignalSpec] = {}
    for signal_name, signal in spec.signals.items():
        if signal.kind == "quarterly_momentum":
            params = dict(signal.params)
            normalized_signals[signal_name] = signal.model_copy(
                update={
                    "kind": "momentum_return",
                    "lookback_days": signal.lookback_days or 63,
                    "params": params,
                }
            )
            continue
        normalized_signals[signal_name] = signal

    benchmark_symbol = spec.benchmark.symbol or "SPY"

    return spec.model_copy(
        update={
            "signals": normalized_signals,
            "benchmark": spec.benchmark.model_copy(update={"symbol": benchmark_symbol}),
        }
    )


def _raise_for_validation_errors(validation: ValidationResult) -> None:
    if validation.valid:
        return
    joined_errors = "; ".join(validation.errors)
    raise ValueError(f"StrategySpec failed validation: {joined_errors}")
