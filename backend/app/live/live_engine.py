from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend.app.backtest.run_backtest import (
    _build_price_matrix,
    _build_target_weights,
    _compute_signal_frames,
    _normalize_market_data,
)
from backend.app.models.compiled_strategy import CompiledStrategy
from backend.app.models.trading import OrderIntent, PositionSnapshot


def evaluate_strategy_tick(
    compiled_strategy: CompiledStrategy,
    latest_market_data: pd.DataFrame,
    current_positions: list[PositionSnapshot],
) -> list[OrderIntent]:
    normalized_market_data = _normalize_market_data(latest_market_data)
    if normalized_market_data.empty:
        return []

    price_matrix = _build_price_matrix(normalized_market_data)
    if price_matrix.empty:
        return []

    signal_frames = _compute_signal_frames(compiled_strategy, price_matrix)
    target_weights = _build_target_weights(compiled_strategy, price_matrix, signal_frames)
    if target_weights.empty:
        return []

    latest_date = target_weights.index[-1]
    latest_weights = target_weights.loc[latest_date]
    latest_prices = price_matrix.loc[latest_date].dropna()
    if latest_prices.empty:
        return []

    current_quantities = {position.symbol.upper(): float(position.quantity) for position in current_positions}
    target_quantities = _target_quantities(
        compiled_strategy=compiled_strategy,
        latest_weights=latest_weights,
        latest_prices=latest_prices,
    )

    order_intents: list[OrderIntent] = []
    symbols = sorted(set(current_quantities) | set(target_quantities))
    for symbol in symbols:
        target_quantity = target_quantities.get(symbol, 0.0)
        current_quantity = current_quantities.get(symbol, 0.0)
        delta = target_quantity - current_quantity
        if math.isclose(delta, 0.0, abs_tol=1e-9):
            continue
        order_intents.append(
            OrderIntent(
                symbol=symbol,
                side="buy" if delta > 0 else "sell",
                quantity=abs(delta),
                order_type="market",
            )
        )

    return order_intents


def _target_quantities(
    compiled_strategy: CompiledStrategy,
    latest_weights: pd.Series,
    latest_prices: pd.Series,
) -> dict[str, float]:
    target_quantities: dict[str, float] = {}
    use_fractional = compiled_strategy.execution_plan.allow_fractional_shares
    total_capital = float(compiled_strategy.initial_capital)

    for symbol, weight in latest_weights.items():
        if pd.isna(weight) or float(weight) <= 0.0:
            continue
        price = float(latest_prices.get(symbol, 0.0))
        if price <= 0.0:
            continue
        target_notional = total_capital * float(weight)
        raw_quantity = target_notional / price
        quantity = raw_quantity if use_fractional else math.floor(raw_quantity)
        if quantity <= 0.0:
            continue
        target_quantities[str(symbol).upper()] = float(quantity)

    return target_quantities
