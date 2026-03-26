from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

from openai import OpenAI
from pydantic import Field

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend.app.models.strategy_spec import (
    BacktestSpec,
    BenchmarkSpec,
    DeploymentSpec,
    ExecutionSpec,
    MetadataSpec,
    PortfolioConstructionSpec,
    RebalanceSpec,
    RiskSpec,
    SelectionSpec,
    SignalSpec,
    StrategySpec,
    StrictModel,
    UniverseSpec,
)
from backend.app.validator.validator import CapabilityRegistry, ValidationResult, validate_strategy

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5")
DEFAULT_MEGA_CAP_SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "META"]

INTENT_INSTRUCTIONS = """
You extract structured trading intent from natural-language prompts for a US-equities-only, long-only strategy system.

Rules:
- Supported signal kinds only:
  - momentum_return
  - sma_crossover
  - realized_volatility
  - rsi
  - exclude_earnings_window
- Never return unsupported asset classes, short selling, options, crypto, leverage, or live deployment.
- If the user asks for unsupported behavior, narrow it to the closest supported V1 behavior and add a warning.
- If the prompt omits details, leave the field null when possible and add an assumption note.
- Extract explicit ticker symbols when mentioned.
- If the prompt refers to broad US large-cap or mega-cap stocks without explicit tickers, set universe_scope accordingly and leave symbols empty.
- Return only the PromptIntent structure.
""".strip()


class PromptIntent(StrictModel):
    strategy_name: str | None = None
    strategy_description: str | None = None
    universe_scope: Literal["explicit_symbols", "us_large_cap", "us_mega_cap", "us_broad_market"] = (
        "us_large_cap"
    )
    symbols: list[str] = Field(default_factory=list)
    signal_kind: Literal[
        "momentum_return",
        "sma_crossover",
        "realized_volatility",
        "rsi",
        "exclude_earnings_window",
    ] | None = None
    lookback_days: int | None = None
    fast_lookback_days: int | None = None
    slow_lookback_days: int | None = None
    window_days: int | None = None
    selection_top_n: int | None = None
    rebalance_frequency: Literal["daily", "weekly", "monthly"] | None = None
    rebalance_day_of_week: Literal["monday", "tuesday", "wednesday", "thursday", "friday"] | None = None
    rebalance_day_of_month: int | None = None
    benchmark_symbol: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: float | None = None
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PromptParseResult(StrictModel):
    strategy_spec: StrategySpec
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def parse_strategy_prompt(prompt: str) -> PromptParseResult:
    client = OpenAI(api_key=_get_openai_api_key())
    intent = _extract_intent(client=client, prompt=prompt)
    result = _build_strategy_spec_from_intent(prompt=prompt, intent=intent)
    validation = validate_strategy(result.strategy_spec, CapabilityRegistry())
    if not validation.valid:
        errors = "; ".join(validation.errors)
        raise ValueError(f"Prompt parser produced an invalid StrategySpec: {errors}")
    return _merge_validation_warnings(result, validation)


def _extract_intent(client: OpenAI, prompt: str) -> PromptIntent:
    response = client.responses.parse(
        model=MODEL_NAME,
        reasoning={"effort": "medium"},
        instructions=INTENT_INSTRUCTIONS,
        input=f"User prompt:\n{prompt}",
        text_format=PromptIntent,
    )
    return response.output_parsed


def _build_strategy_spec_from_intent(prompt: str, intent: PromptIntent) -> PromptParseResult:
    assumptions = list(intent.assumptions)
    warnings = list(intent.warnings)

    symbols = _resolve_symbols(intent)
    if not intent.symbols:
        assumptions.append("No explicit ticker list was provided, so a default mega-cap basket was used.")
        warnings.append(
            "Prompt parsing currently resolves broad large-cap prompts to a curated mega-cap basket for deterministic V1 backtests."
        )

    signal_spec, signal_name, signal_assumptions = _build_signal_spec(intent)
    assumptions.extend(signal_assumptions)

    requested_top_n = intent.selection_top_n or min(5, len(symbols))
    top_n = min(requested_top_n, len(symbols))
    if intent.selection_top_n is None:
        assumptions.append(f"Selection size was not specified, so top_n defaulted to {top_n}.")
    if requested_top_n > len(symbols):
        warnings.append(
            f"Requested top_n of {requested_top_n} exceeded the deterministic universe size of {len(symbols)}, so top_n was capped."
        )

    rebalance_frequency = intent.rebalance_frequency or "weekly"
    rebalance_day_of_week = intent.rebalance_day_of_week or "monday"
    if intent.rebalance_frequency is None:
        assumptions.append("Rebalance frequency was not specified, so it defaulted to weekly.")

    start_date, end_date, date_assumptions = _resolve_backtest_dates(intent)
    assumptions.extend(date_assumptions)

    benchmark_symbol = (intent.benchmark_symbol or "SPY").upper()
    if intent.benchmark_symbol is None:
        assumptions.append("Benchmark was not specified, so it defaulted to SPY.")

    initial_capital = float(intent.initial_capital or 100000.0)
    if intent.initial_capital is None:
        assumptions.append("Initial capital was not specified, so it defaulted to 100000.")

    name = intent.strategy_name or _derive_strategy_name(prompt, intent)
    description = intent.strategy_description or prompt

    strategy_spec = StrategySpec(
        metadata=MetadataSpec(
            name=name,
            description=description,
            author="openai-parser",
            tags=["prompt-generated"],
        ),
        universe=UniverseSpec(
            asset_class="us_equities",
            symbols=symbols,
            market_cap_min=_default_market_cap_min(intent.universe_scope),
            avg_dollar_volume_min=5_000_000.0,
        ),
        direction="long_only",
        signals={signal_name: signal_spec},
        selection=SelectionSpec(
            source_signal=signal_name,
            top_n=top_n,
            max_positions=top_n,
            order="desc",
        ),
        portfolio_construction=PortfolioConstructionSpec(
            method="equal_weight",
            max_positions=top_n,
            target_gross_exposure=1.0,
        ),
        risk=RiskSpec(
            max_position_weight=min(1.0, round(1 / top_n + 0.01, 2)),
            max_turnover=1.0,
        ),
        rebalance=RebalanceSpec(
            frequency=rebalance_frequency,
            day_of_week=rebalance_day_of_week if rebalance_frequency == "weekly" else None,
            day_of_month=intent.rebalance_day_of_month if rebalance_frequency == "monthly" else None,
        ),
        execution=ExecutionSpec(
            order_type="market",
            time_in_force="day",
            slippage_bps=0.0,
            commission_bps=0.0,
            allow_fractional_shares=False,
        ),
        benchmark=BenchmarkSpec(symbol=benchmark_symbol),
        backtest=BacktestSpec(
            initial_capital=initial_capital,
            start_date=start_date,
            end_date=end_date,
        ),
        deployment=DeploymentSpec(mode="paper"),
        assumptions=list(dict.fromkeys(assumptions)),
        warnings=list(dict.fromkeys(warnings)),
    )

    return PromptParseResult(
        strategy_spec=strategy_spec,
        assumptions=strategy_spec.assumptions,
        warnings=strategy_spec.warnings,
    )


def _build_signal_spec(intent: PromptIntent) -> tuple[SignalSpec, str, list[str]]:
    assumptions: list[str] = []
    signal_kind = intent.signal_kind or "momentum_return"
    signal_name = {
        "momentum_return": "momentum_signal",
        "sma_crossover": "sma_signal",
        "realized_volatility": "volatility_signal",
        "rsi": "rsi_signal",
        "exclude_earnings_window": "earnings_filter",
    }[signal_kind]

    if signal_kind == "momentum_return":
        lookback_days = intent.lookback_days or 63
        if intent.lookback_days is None:
            assumptions.append("Momentum lookback was not specified, so it defaulted to 63 trading days.")
        return (
            SignalSpec(kind=signal_kind, source="adjusted_close", lookback_days=lookback_days),
            signal_name,
            assumptions,
        )

    if signal_kind == "sma_crossover":
        fast = intent.fast_lookback_days or 20
        slow = intent.slow_lookback_days or 50
        if intent.fast_lookback_days is None or intent.slow_lookback_days is None:
            assumptions.append("SMA crossover windows were not fully specified, so they defaulted to 20 and 50 days.")
        return (
            SignalSpec(
                kind=signal_kind,
                source="adjusted_close",
                fast_lookback_days=fast,
                slow_lookback_days=slow,
            ),
            signal_name,
            assumptions,
        )

    if signal_kind == "realized_volatility":
        window_days = intent.lookback_days or intent.window_days or 20
        if intent.lookback_days is None and intent.window_days is None:
            assumptions.append("Volatility window was not specified, so it defaulted to 20 trading days.")
        return (
            SignalSpec(kind=signal_kind, source="adjusted_close", lookback_days=window_days),
            signal_name,
            assumptions,
        )

    if signal_kind == "rsi":
        window_days = intent.lookback_days or intent.window_days or 14
        if intent.lookback_days is None and intent.window_days is None:
            assumptions.append("RSI window was not specified, so it defaulted to 14 trading days.")
        return (
            SignalSpec(kind=signal_kind, source="adjusted_close", lookback_days=window_days),
            signal_name,
            assumptions,
        )

    assumptions.append("Earnings exclusion window was not specified, so it defaulted to 3 trading days.")
    return (
        SignalSpec(kind="exclude_earnings_window", source="adjusted_close", window_days=intent.window_days or 3),
        signal_name,
        assumptions,
    )


def _resolve_symbols(intent: PromptIntent) -> list[str]:
    explicit_symbols = [symbol.upper() for symbol in intent.symbols]
    if explicit_symbols:
        return explicit_symbols
    return list(DEFAULT_MEGA_CAP_SYMBOLS)


def _resolve_backtest_dates(intent: PromptIntent) -> tuple[str, str, list[str]]:
    assumptions: list[str] = []
    end_date = intent.end_date or date.today().isoformat()
    start_date = intent.start_date
    if start_date is None:
        start_date = (date.fromisoformat(end_date) - timedelta(days=365)).isoformat()
        assumptions.append("Backtest start date was not specified, so it defaulted to one year before the end date.")
    if intent.end_date is None:
        assumptions.append("Backtest end date was not specified, so it defaulted to today.")
    return start_date, end_date, assumptions


def _default_market_cap_min(universe_scope: PromptIntent.__annotations__["universe_scope"]) -> float:
    if universe_scope == "us_mega_cap":
        return 100_000_000_000.0
    if universe_scope == "us_large_cap":
        return 10_000_000_000.0
    return 1_000_000_000.0


def _derive_strategy_name(prompt: str, intent: PromptIntent) -> str:
    signal_label = (intent.signal_kind or "momentum_return").replace("_", " ").title()
    rebalance_label = (intent.rebalance_frequency or "weekly").title()
    return f"{rebalance_label} {signal_label} Strategy"


def _merge_validation_warnings(
    result: PromptParseResult,
    validation: ValidationResult,
) -> PromptParseResult:
    merged_warnings = list(dict.fromkeys([*result.warnings, *validation.warnings]))
    return result.model_copy(update={"warnings": merged_warnings})


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


def _get_openai_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY") or _dotenv_fallback_values().get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY is required for prompt parsing")
    return key
