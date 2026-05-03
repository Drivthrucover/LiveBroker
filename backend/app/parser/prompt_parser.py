from __future__ import annotations

import os
import re
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


class PromptIntentUpdate(StrictModel):
    strategy_name: str | None = None
    strategy_description: str | None = None
    universe_scope: Literal["explicit_symbols", "us_large_cap", "us_mega_cap", "us_broad_market"] | None = None
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


class ClarificationQuestion(StrictModel):
    key: Literal["universe", "signal", "selection", "rebalance", "backtest_window", "benchmark"]
    prompt: str
    rationale: str


class StrategyDraft(StrictModel):
    prompt: str
    strategy_name: str | None = None
    strategy_description: str | None = None
    universe_scope: Literal["explicit_symbols", "us_large_cap", "us_mega_cap", "us_broad_market"] | None = None
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


class StrategyDraftSession(StrictModel):
    draft: StrategyDraft
    next_question: ClarificationQuestion | None = None
    completion_percent: int
    completed_sections: list[str]
    missing_sections: list[str]
    can_finalize: bool


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


def start_strategy_draft(prompt: str) -> StrategyDraftSession:
    client = OpenAI(api_key=_get_openai_api_key())
    intent = _extract_intent(client=client, prompt=prompt)
    draft = StrategyDraft(prompt=prompt, **intent.model_dump())
    return _build_draft_session(draft)


def answer_strategy_draft(
    draft: StrategyDraft,
    question_key: Literal["universe", "signal", "selection", "rebalance", "backtest_window", "benchmark"],
    answer: str,
) -> StrategyDraftSession:
    update = _deterministic_draft_update(question_key=question_key, answer=answer)
    if update is None:
        client = OpenAI(api_key=_get_openai_api_key())
        update = _extract_draft_update(client=client, draft=draft, question_key=question_key, answer=answer)
    merged = _merge_draft_update(draft, update)
    return _build_draft_session(merged)


def finalize_strategy_draft(draft: StrategyDraft) -> PromptParseResult:
    session = _build_draft_session(draft)
    if not session.can_finalize:
        missing = ", ".join(session.missing_sections)
        raise ValueError(f"Strategy draft is incomplete. Missing sections: {missing}")
    intent = PromptIntent.model_validate(
        {
            key: value
            for key, value in draft.model_dump().items()
            if key in PromptIntent.model_fields
        }
    )
    result = _build_strategy_spec_from_intent(prompt=draft.prompt, intent=intent)
    validation = validate_strategy(result.strategy_spec, CapabilityRegistry())
    if not validation.valid:
        errors = "; ".join(validation.errors)
        raise ValueError(f"Draft finalization produced an invalid StrategySpec: {errors}")
    return _merge_validation_warnings(result, validation)


def _extract_draft_update(
    client: OpenAI,
    draft: StrategyDraft,
    question_key: str,
    answer: str,
) -> PromptIntentUpdate:
    response = client.responses.parse(
        model=MODEL_NAME,
        reasoning={"effort": "low"},
        instructions=_draft_update_instructions(question_key),
        input=(
            "Current draft state:\n"
            f"{draft.model_dump_json(indent=2)}\n\n"
            f"User answer to the {question_key} question:\n{answer}"
        ),
        text_format=PromptIntentUpdate,
    )
    return response.output_parsed


def _draft_update_instructions(question_key: str) -> str:
    return (
        "You update a partially completed trading strategy draft using one user answer.\n"
        "Return only fields that are clarified by the answer. Leave unrelated fields null or empty.\n"
        "Prefer qualitative interpretation over asking for raw schema field names.\n"
        "Never introduce unsupported signals, short selling, live deployment, or non-US-equity assets.\n"
        f"The current question category is: {question_key}.\n"
        "Use assumptions and warnings when the answer is still ambiguous."
    )


def _merge_draft_update(draft: StrategyDraft, update: PromptIntentUpdate) -> StrategyDraft:
    merged = draft.model_copy(deep=True)
    update_data = update.model_dump(exclude_none=True)
    for key, value in update_data.items():
        if key == "symbols" and value:
            merged.symbols = [symbol.upper() for symbol in value]
        elif key == "assumptions":
            merged.assumptions = list(dict.fromkeys([*merged.assumptions, *value]))
        elif key == "warnings":
            merged.warnings = list(dict.fromkeys([*merged.warnings, *value]))
        else:
            setattr(merged, key, value)
    return merged


def _build_draft_session(draft: StrategyDraft) -> StrategyDraftSession:
    completed_sections = _completed_sections(draft)
    missing_sections = [section for section in _required_sections() if section not in completed_sections]
    completion_percent = int(round((len(completed_sections) / len(_required_sections())) * 100))
    next_question = _next_question(draft, missing_sections)
    return StrategyDraftSession(
        draft=draft,
        next_question=next_question,
        completion_percent=completion_percent,
        completed_sections=completed_sections,
        missing_sections=missing_sections,
        can_finalize=not missing_sections,
    )


def _required_sections() -> list[str]:
    return ["universe", "signal", "selection", "rebalance", "backtest_window", "benchmark"]


def _completed_sections(draft: StrategyDraft) -> list[str]:
    completed: list[str] = []
    if draft.universe_scope is not None or draft.symbols:
        completed.append("universe")
    if draft.signal_kind is not None:
        completed.append("signal")
    if draft.selection_top_n is not None:
        completed.append("selection")
    if draft.rebalance_frequency is not None:
        completed.append("rebalance")
    if draft.start_date is not None and draft.end_date is not None:
        completed.append("backtest_window")
    if draft.benchmark_symbol is not None:
        completed.append("benchmark")
    return completed


def _signal_params_complete(draft: StrategyDraft) -> bool:
    if draft.signal_kind == "sma_crossover":
        return draft.fast_lookback_days is not None and draft.slow_lookback_days is not None
    if draft.signal_kind in {"momentum_return", "realized_volatility", "rsi"}:
        return draft.lookback_days is not None or draft.window_days is not None
    if draft.signal_kind == "exclude_earnings_window":
        return True
    return False


def _rebalance_complete(draft: StrategyDraft) -> bool:
    if draft.rebalance_frequency == "weekly":
        return draft.rebalance_day_of_week is not None
    if draft.rebalance_frequency == "monthly":
        return draft.rebalance_day_of_month is not None
    return draft.rebalance_frequency == "daily"


def _next_question(
    draft: StrategyDraft,
    missing_sections: list[str],
) -> ClarificationQuestion | None:
    if not missing_sections:
        return None
    section = missing_sections[0]
    if section == "universe":
        return ClarificationQuestion(
            key="universe",
            prompt=(
                "What part of the market should this strategy focus on? "
                "For example, a named list of tickers, a broad US large-cap universe, or a narrower theme."
            ),
            rationale="The strategy needs a clearer investable universe before it can be finalized.",
        )
    if section == "signal":
        return ClarificationQuestion(
            key="signal",
            prompt=(
                "What kind of edge should drive selection here: medium-term momentum, fast trend following, "
                "moving-average crossover, lower volatility, RSI-style mean reversion, or avoiding earnings events?"
            ),
            rationale="The strategy still needs a complete signal definition.",
        )
    if section == "selection":
        return ClarificationQuestion(
            key="selection",
            prompt=(
                "Should the portfolio be fairly concentrated in a handful of names, or spread across a broader basket?"
            ),
            rationale="The system still needs to know how many names to hold.",
        )
    if section == "rebalance":
        return ClarificationQuestion(
            key="rebalance",
            prompt="How often should the strategy refresh holdings: daily, weekly, or monthly?",
            rationale="The rebalance schedule is still incomplete.",
        )
    if section == "backtest_window":
        return ClarificationQuestion(
            key="backtest_window",
            prompt=(
                "What period do you want to test over? You can answer naturally, like 'the last 2 years' or "
                "'from January 2023 through December 2024'."
            ),
            rationale="A backtest window is required before the strategy can be finalized.",
        )
    return ClarificationQuestion(
        key="benchmark",
        prompt="What benchmark should this strategy be compared against: SPY, QQQ, or something else?",
        rationale="A benchmark is required for the reporting output.",
    )


def _deterministic_draft_update(
    question_key: Literal["universe", "signal", "selection", "rebalance", "backtest_window", "benchmark"],
    answer: str,
) -> PromptIntentUpdate | None:
    normalized = answer.strip().lower()
    if not normalized:
        return None

    if question_key == "rebalance":
        return _deterministic_rebalance_update(normalized)
    if question_key == "selection":
        return _deterministic_selection_update(normalized)
    if question_key == "benchmark":
        return _deterministic_benchmark_update(answer)
    if question_key == "signal":
        return _deterministic_signal_update(normalized)
    if question_key == "universe":
        return _deterministic_universe_update(answer, normalized)
    if question_key == "backtest_window":
        return _deterministic_backtest_window_update(normalized)
    return None


def _deterministic_rebalance_update(normalized: str) -> PromptIntentUpdate | None:
    if "daily" in normalized:
        return PromptIntentUpdate(rebalance_frequency="daily")

    if "weekly" in normalized:
        weekday = next((day for day in _WEEKDAYS if day in normalized), None)
        assumptions = []
        if weekday is None:
            weekday = "monday"
            assumptions.append(
                "A weekly rebalance cadence was specified without a day, so Monday was assumed."
            )
        return PromptIntentUpdate(
            rebalance_frequency="weekly",
            rebalance_day_of_week=weekday,
            assumptions=assumptions,
        )

    if "monthly" in normalized:
        day_match = re.search(r"\b([1-9]|[12][0-9]|3[01])\b", normalized)
        assumptions = []
        day_of_month = int(day_match.group(1)) if day_match else 1
        if day_match is None:
            assumptions.append(
                "A monthly rebalance cadence was specified without a day, so the 1st of the month was assumed."
            )
        return PromptIntentUpdate(
            rebalance_frequency="monthly",
            rebalance_day_of_month=day_of_month,
            assumptions=assumptions,
        )

    return None


def _deterministic_selection_update(normalized: str) -> PromptIntentUpdate | None:
    top_n_match = re.search(r"\btop\s+(\d+)\b|\b(\d+)\s+(?:stocks|names|positions|holdings)\b", normalized)
    if top_n_match:
        parsed = next(group for group in top_n_match.groups() if group is not None)
        return PromptIntentUpdate(selection_top_n=int(parsed))

    if any(keyword in normalized for keyword in ["concentrated", "handful", "focused"]):
        return PromptIntentUpdate(
            selection_top_n=5,
            assumptions=["The portfolio was described as concentrated, so top_n was inferred as 5."],
        )

    if any(keyword in normalized for keyword in ["broad", "diversified", "spread"]):
        return PromptIntentUpdate(
            selection_top_n=20,
            assumptions=["The portfolio was described as broad, so top_n was inferred as 20."],
        )

    return None


def _deterministic_benchmark_update(answer: str) -> PromptIntentUpdate | None:
    symbols = re.findall(r"\b[A-Za-z]{2,5}\b", answer.upper())
    if not symbols:
        return None
    return PromptIntentUpdate(benchmark_symbol=symbols[0])


def _deterministic_signal_update(normalized: str) -> PromptIntentUpdate | None:
    lookback_match = re.search(r"\b(\d+)\s*(?:day|days|week|weeks|month|months)\b", normalized)
    lookback_days: int | None = None
    if lookback_match:
        value = int(lookback_match.group(1))
        if "week" in normalized:
            lookback_days = value * 5
        elif "month" in normalized:
            lookback_days = value * 21
        else:
            lookback_days = value

    if "momentum" in normalized or "trend" in normalized:
        return PromptIntentUpdate(signal_kind="momentum_return", lookback_days=lookback_days)
    if "moving average" in normalized or "crossover" in normalized or "sma" in normalized:
        return PromptIntentUpdate(
            signal_kind="sma_crossover",
            fast_lookback_days=20,
            slow_lookback_days=50,
            assumptions=["A crossover signal was requested, so SMA windows defaulted to 20 and 50 days."],
        )
    if "volatility" in normalized or "low vol" in normalized:
        return PromptIntentUpdate(signal_kind="realized_volatility", lookback_days=lookback_days or 20)
    if "rsi" in normalized or "mean reversion" in normalized:
        return PromptIntentUpdate(signal_kind="rsi", lookback_days=lookback_days or 14)
    if "earnings" in normalized:
        return PromptIntentUpdate(signal_kind="exclude_earnings_window", window_days=3)
    return None


def _deterministic_universe_update(answer: str, normalized: str) -> PromptIntentUpdate | None:
    symbols = re.findall(r"\b[A-Z]{1,5}\b", answer.upper())
    if symbols:
        deduped = list(dict.fromkeys(symbols))
        return PromptIntentUpdate(universe_scope="explicit_symbols", symbols=deduped)

    if "mega" in normalized:
        return PromptIntentUpdate(universe_scope="us_mega_cap")
    if "large cap" in normalized or "large-cap" in normalized:
        return PromptIntentUpdate(universe_scope="us_large_cap")
    if "broad market" in normalized or "all us equities" in normalized or "entire market" in normalized:
        return PromptIntentUpdate(universe_scope="us_broad_market")
    return None


def _deterministic_backtest_window_update(normalized: str) -> PromptIntentUpdate | None:
    range_match = re.search(
        r"\bfrom\s+(\d{4}-\d{2}-\d{2})\s+(?:to|through)\s+(\d{4}-\d{2}-\d{2})\b",
        normalized,
    )
    if range_match:
        return PromptIntentUpdate(start_date=range_match.group(1), end_date=range_match.group(2))

    last_years_match = re.search(r"\blast\s+(\d+)\s+years?\b", normalized)
    if last_years_match:
        years = int(last_years_match.group(1))
        end_date = date.today()
        start_date = end_date - timedelta(days=365 * years)
        return PromptIntentUpdate(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

    explicit_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", normalized)
    if len(explicit_dates) >= 2:
        return PromptIntentUpdate(start_date=explicit_dates[0], end_date=explicit_dates[1])

    return None


_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]


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
