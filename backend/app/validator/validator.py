from __future__ import annotations

import sys
from pathlib import Path

from pydantic import Field

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend.app.models.strategy_spec import StrategySpec, StrictModel


class ValidationResult(StrictModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CapabilityRegistry(StrictModel):
    supported_signals: set[str] = Field(
        default_factory=lambda: {
            "momentum_return",
            "sma_crossover",
            "realized_volatility",
            "rsi",
            "exclude_earnings_window",
        }
    )
    signal_aliases: dict[str, str] = Field(
        default_factory=lambda: {
            "quarterly_momentum": "momentum_return",
        }
    )
    supported_asset_classes: set[str] = Field(default_factory=lambda: {"us_equities"})
    supported_directions: set[str] = Field(default_factory=lambda: {"long_only"})
    supported_portfolio_methods: set[str] = Field(default_factory=lambda: {"equal_weight"})
    supported_execution_order_types: set[str] = Field(
        default_factory=lambda: {"market", "market_on_close"}
    )
    supported_deployment_modes: set[str] = Field(default_factory=lambda: {"disabled", "paper"})

    def is_supported_signal(self, signal_kind: str) -> bool:
        return signal_kind in self.supported_signals or signal_kind in self.signal_aliases


def validate_strategy(
    spec: StrategySpec,
    capability_registry: CapabilityRegistry | None = None,
) -> ValidationResult:
    registry = capability_registry or CapabilityRegistry()
    errors: list[str] = []
    warnings: list[str] = []

    _validate_universe(spec, registry, errors)
    _validate_signals(spec, registry, errors, warnings)
    _validate_selection(spec, errors)
    _validate_portfolio(spec, registry, errors)
    _validate_risk(spec, warnings)
    _validate_safety(spec, registry, errors)

    return ValidationResult(valid=not errors, errors=errors, warnings=warnings)


def _validate_universe(
    spec: StrategySpec,
    registry: CapabilityRegistry,
    errors: list[str],
) -> None:
    if spec.universe.asset_class not in registry.supported_asset_classes:
        errors.append(f"Unsupported asset class: {spec.universe.asset_class}")

    if spec.universe.market_cap_min is not None and spec.universe.market_cap_min < 0:
        errors.append("universe.market_cap_min cannot be negative")

    if spec.universe.avg_dollar_volume_min is not None and spec.universe.avg_dollar_volume_min < 0:
        errors.append("universe.avg_dollar_volume_min cannot be negative")


def _validate_signals(
    spec: StrategySpec,
    registry: CapabilityRegistry,
    errors: list[str],
    warnings: list[str],
) -> None:
    for signal_name, signal in spec.signals.items():
        if not registry.is_supported_signal(signal.kind):
            errors.append(f"Unsupported signal kind for '{signal_name}': {signal.kind}")

        if signal.lookback_days is not None and signal.lookback_days <= 0:
            errors.append(f"Signal '{signal_name}' has invalid lookback_days")

        if signal.kind in registry.signal_aliases:
            warnings.append(
                f"Signal '{signal_name}' uses alias '{signal.kind}' and will be normalized during compilation"
            )


def _validate_selection(spec: StrategySpec, errors: list[str]) -> None:
    if spec.selection.source_signal not in spec.signals:
        errors.append(
            f"selection.source_signal '{spec.selection.source_signal}' does not exist in signals"
        )

    if spec.selection.top_n > spec.selection.max_positions:
        errors.append("selection.top_n cannot exceed selection.max_positions")

    if spec.selection.top_n > spec.portfolio_construction.max_positions:
        errors.append("selection.top_n cannot exceed portfolio_construction.max_positions")


def _validate_portfolio(
    spec: StrategySpec,
    registry: CapabilityRegistry,
    errors: list[str],
) -> None:
    if spec.portfolio_construction.method not in registry.supported_portfolio_methods:
        errors.append(
            f"Unsupported portfolio construction method: {spec.portfolio_construction.method}"
        )

    if spec.selection.top_n > spec.portfolio_construction.max_positions:
        errors.append("portfolio_construction.max_positions must be >= selection.top_n")


def _validate_risk(spec: StrategySpec, warnings: list[str]) -> None:
    if spec.risk.max_position_weight is not None:
        equal_weight = 1 / spec.portfolio_construction.max_positions
        if spec.risk.max_position_weight < equal_weight:
            warnings.append(
                "risk.max_position_weight is below equal-weight target and may constrain allocations"
            )


def _validate_safety(
    spec: StrategySpec,
    registry: CapabilityRegistry,
    errors: list[str],
) -> None:
    if spec.direction not in registry.supported_directions:
        errors.append(f"Unsupported direction: {spec.direction}")

    if spec.execution.order_type not in registry.supported_execution_order_types:
        errors.append(f"Unsupported execution order type: {spec.execution.order_type}")

    if spec.deployment.mode not in registry.supported_deployment_modes:
        errors.append(f"Unsupported deployment mode: {spec.deployment.mode}")

    if spec.deployment.mode == "live":
        errors.append("Live deployment is not supported in the current platform scope")

    if spec.direction != "long_only":
        errors.append("Only long_only strategies are supported")
