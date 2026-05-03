from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend.app.models.backtest_result import (
    BacktestCurvePoint,
    BacktestMetrics,
    BacktestResult,
    DrawdownPoint,
    TradeRecord,
)
from backend.app.models.compiled_strategy import CompiledSignal, CompiledStrategy

TRADING_DAYS_PER_YEAR = 252
REQUIRED_MARKET_DATA_COLUMNS = [
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "adjusted_close",
]


def run_backtest(
    compiled_strategy: CompiledStrategy,
    market_data: pd.DataFrame,
) -> BacktestResult:
    normalized_data = _normalize_market_data(market_data)
    price_matrix = _build_price_matrix(normalized_data)
    signal_frames = _compute_signal_frames(compiled_strategy, normalized_data, price_matrix)
    target_weights = _build_target_weights(compiled_strategy, signal_frames, price_matrix)
    returns = price_matrix.pct_change().fillna(0.0)
    strategy_returns = (target_weights.shift(1).fillna(0.0) * returns).sum(axis=1)
    equity_curve = compiled_strategy.initial_capital * (1.0 + strategy_returns).cumprod()
    benchmark_curve = _build_benchmark_curve(compiled_strategy, price_matrix)
    trades = _build_trade_records(target_weights, price_matrix)
    drawdowns = _build_drawdown_points(equity_curve)
    metrics = _build_metrics(strategy_returns, equity_curve, target_weights)

    return BacktestResult(
        equity_curve=_series_to_curve(equity_curve),
        benchmark_curve=_series_to_curve(benchmark_curve),
        trades=trades,
        drawdowns=drawdowns,
        metrics=metrics,
    )


def _normalize_market_data(market_data: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_MARKET_DATA_COLUMNS if column not in market_data.columns]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"market_data is missing required columns: {missing_list}")

    normalized = market_data.loc[:, REQUIRED_MARKET_DATA_COLUMNS].copy()
    normalized["symbol"] = normalized["symbol"].astype(str).str.upper()
    normalized["date"] = pd.to_datetime(normalized["date"], utc=False).dt.tz_localize(None)
    for column in ["open", "high", "low", "close", "volume", "adjusted_close"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="raise").astype(float)
    normalized = normalized.sort_values(["date", "symbol"]).drop_duplicates(["date", "symbol"])
    if normalized.empty:
        raise ValueError("market_data must contain at least one row")
    return normalized.reset_index(drop=True)


def _build_price_matrix(market_data: pd.DataFrame) -> pd.DataFrame:
    price_matrix = market_data.pivot(index="date", columns="symbol", values="adjusted_close").sort_index()
    price_matrix = price_matrix.ffill().dropna(how="all")
    if price_matrix.empty:
        raise ValueError("market_data did not produce a usable price matrix")
    return price_matrix


def _compute_signal_frames(
    compiled_strategy: CompiledStrategy,
    market_data: pd.DataFrame,
    price_matrix: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    returns = price_matrix.pct_change()
    for signal_name, signal in compiled_strategy.signal_plan.items():
        frames[signal_name] = _compute_signal_frame(signal, market_data, price_matrix, returns)
    return frames


def _compute_signal_frame(
    signal: CompiledSignal,
    market_data: pd.DataFrame,
    price_matrix: pd.DataFrame,
    returns: pd.DataFrame,
) -> pd.DataFrame:
    source_matrix = market_data.pivot(index="date", columns="symbol", values=signal.source).sort_index()
    source_matrix = source_matrix.reindex(price_matrix.index).ffill()
    params = signal.parameters

    if signal.kind == "momentum_return":
        lookback = int(params.get("lookback_days", 21))
        return source_matrix.pct_change(lookback)

    if signal.kind == "sma_crossover":
        fast = int(params["fast_lookback_days"])
        slow = int(params["slow_lookback_days"])
        fast_sma = source_matrix.rolling(fast).mean()
        slow_sma = source_matrix.rolling(slow).mean()
        return (fast_sma / slow_sma) - 1.0

    if signal.kind == "realized_volatility":
        window = int(params.get("lookback_days", params.get("window_days", 21)))
        return returns.rolling(window).std() * math.sqrt(TRADING_DAYS_PER_YEAR)

    if signal.kind == "rsi":
        window = int(params.get("lookback_days", params.get("window_days", 14)))
        delta = source_matrix.diff()
        up = delta.clip(lower=0.0)
        down = -delta.clip(upper=0.0)
        average_gain = up.rolling(window).mean()
        average_loss = down.rolling(window).mean()
        rs = average_gain / average_loss.replace(0.0, np.nan)
        return 100.0 - (100.0 / (1.0 + rs))

    if signal.kind == "exclude_earnings_window":
        if "earnings_excluded" in market_data.columns:
            earnings_mask = market_data.pivot(
                index="date",
                columns="symbol",
                values="earnings_excluded",
            ).sort_index()
            earnings_mask = earnings_mask.reindex(price_matrix.index).ffill().fillna(0.0)
            return 1.0 - earnings_mask.astype(float)
        return pd.DataFrame(1.0, index=price_matrix.index, columns=price_matrix.columns)

    raise ValueError(f"Unsupported compiled signal kind: {signal.kind}")


def _build_target_weights(
    compiled_strategy: CompiledStrategy,
    signal_frames: dict[str, pd.DataFrame],
    price_matrix: pd.DataFrame,
) -> pd.DataFrame:
    signal_frame = signal_frames[compiled_strategy.selection_plan.source_signal].copy()
    signal_frame = signal_frame.reindex(price_matrix.index).replace([np.inf, -np.inf], np.nan)
    target_weights = pd.DataFrame(0.0, index=price_matrix.index, columns=price_matrix.columns)
    current_weights = pd.Series(0.0, index=price_matrix.columns)
    rebalance_mask = _rebalance_mask(price_matrix.index, compiled_strategy)

    max_weight = compiled_strategy.risk_plan.constraints.get(
        "max_position_weight",
        compiled_strategy.portfolio_plan.weight_per_position,
    )
    base_weight = min(compiled_strategy.portfolio_plan.weight_per_position, max_weight)

    for date in price_matrix.index:
        if rebalance_mask.loc[date]:
            scores = signal_frame.loc[date].dropna()
            if compiled_strategy.selection_plan.min_score is not None:
                scores = scores[scores >= compiled_strategy.selection_plan.min_score]
            if compiled_strategy.selection_plan.order == "asc":
                selected_symbols = scores.nsmallest(compiled_strategy.selection_plan.top_n).index
            else:
                selected_symbols = scores.nlargest(compiled_strategy.selection_plan.top_n).index
            current_weights = pd.Series(0.0, index=price_matrix.columns)
            if len(selected_symbols) > 0:
                selected_weight = min(
                    base_weight,
                    compiled_strategy.portfolio_plan.target_gross_exposure / len(selected_symbols),
                )
                current_weights.loc[list(selected_symbols)] = float(selected_weight)
        target_weights.loc[date] = current_weights

    return target_weights


def _rebalance_mask(index: pd.DatetimeIndex, compiled_strategy: CompiledStrategy) -> pd.Series:
    frequency = compiled_strategy.schedule.frequency
    if frequency == "daily":
        return pd.Series(True, index=index)

    if frequency == "weekly":
        day_lookup = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
        }
        rebalance_weekday = day_lookup.get(compiled_strategy.schedule.day_of_week or "monday", 0)
        return pd.Series(index.weekday == rebalance_weekday, index=index)

    if frequency == "monthly":
        rebalance_day = compiled_strategy.schedule.day_of_month or 1
        month_groups = pd.Series(index.day, index=index).groupby(index.to_period("M"))
        selected_dates = {
            group[group >= rebalance_day].index.min()
            if (group >= rebalance_day).any()
            else group.index.max()
            for _, group in month_groups
        }
        return pd.Series(index.isin(selected_dates), index=index)

    raise ValueError(f"Unsupported rebalance frequency: {frequency}")


def _build_benchmark_curve(
    compiled_strategy: CompiledStrategy,
    price_matrix: pd.DataFrame,
) -> pd.Series:
    if compiled_strategy.benchmark_symbol in price_matrix.columns:
        benchmark_returns = price_matrix[compiled_strategy.benchmark_symbol].pct_change().fillna(0.0)
    else:
        benchmark_returns = price_matrix.pct_change().mean(axis=1).fillna(0.0)
    return compiled_strategy.initial_capital * (1.0 + benchmark_returns).cumprod()


def _build_trade_records(
    target_weights: pd.DataFrame,
    price_matrix: pd.DataFrame,
) -> list[TradeRecord]:
    trades: list[TradeRecord] = []
    weight_deltas = target_weights.diff().fillna(target_weights)

    for date, changes in weight_deltas.iterrows():
        non_zero_changes = changes[changes.abs() > 1e-12]
        for symbol, change in non_zero_changes.items():
            trades.append(
                TradeRecord(
                    date=date.date().isoformat(),
                    symbol=symbol,
                    side="buy" if change > 0 else "sell",
                    weight_change=float(change),
                    target_weight=float(target_weights.at[date, symbol]),
                    price=float(price_matrix.at[date, symbol]),
                )
            )
    return trades


def _build_drawdown_points(equity_curve: pd.Series) -> list[DrawdownPoint]:
    running_peak = equity_curve.cummax()
    drawdown_series = (equity_curve / running_peak) - 1.0
    return [
        DrawdownPoint(date=index.date().isoformat(), drawdown=float(value))
        for index, value in drawdown_series.items()
    ]


def _build_metrics(
    strategy_returns: pd.Series,
    equity_curve: pd.Series,
    target_weights: pd.DataFrame,
) -> BacktestMetrics:
    cagr = _safe_float(_annualized_return(strategy_returns))
    sharpe = _safe_float(_sharpe_ratio(strategy_returns))
    sortino = _safe_float(_sortino_ratio(strategy_returns))
    max_drawdown = _safe_float(_max_drawdown(equity_curve))
    turnover = float(target_weights.diff().abs().sum(axis=1).mean())

    return BacktestMetrics(
        cagr=cagr,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=max_drawdown,
        turnover=turnover,
    )


def _series_to_curve(series: pd.Series) -> list[BacktestCurvePoint]:
    return [
        BacktestCurvePoint(date=index.date().isoformat(), value=float(value))
        for index, value in series.items()
    ]


def _safe_float(value: object) -> float:
    scalar = float(np.asarray(value).item())
    if np.isnan(scalar) or np.isinf(scalar):
        return 0.0
    return scalar


def _annualized_return(strategy_returns: pd.Series) -> float:
    cleaned_returns = strategy_returns.fillna(0.0)
    periods = len(cleaned_returns)
    if periods == 0:
        return 0.0
    total_return = float((1.0 + cleaned_returns).prod())
    if total_return <= 0.0:
        return 0.0
    return total_return ** (TRADING_DAYS_PER_YEAR / periods) - 1.0


def _sharpe_ratio(strategy_returns: pd.Series) -> float:
    cleaned_returns = strategy_returns.fillna(0.0)
    volatility = float(cleaned_returns.std(ddof=0))
    if math.isclose(volatility, 0.0, abs_tol=1e-12):
        return 0.0
    return math.sqrt(TRADING_DAYS_PER_YEAR) * float(cleaned_returns.mean()) / volatility


def _sortino_ratio(strategy_returns: pd.Series) -> float:
    cleaned_returns = strategy_returns.fillna(0.0)
    downside_returns = cleaned_returns[cleaned_returns < 0.0]
    if downside_returns.empty:
        return 0.0
    downside_deviation = float(np.sqrt((downside_returns.pow(2).mean())))
    if math.isclose(downside_deviation, 0.0, abs_tol=1e-12):
        return 0.0
    return math.sqrt(TRADING_DAYS_PER_YEAR) * float(cleaned_returns.mean()) / downside_deviation


def _max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    running_peak = equity_curve.cummax()
    drawdowns = (equity_curve / running_peak) - 1.0
    return float(drawdowns.min())
