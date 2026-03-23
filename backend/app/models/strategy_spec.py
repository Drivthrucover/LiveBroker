from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Base model with strict field handling for externally supplied specs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MetadataSpec(StrictModel):
    name: str | None = None
    description: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)


class UniverseSpec(StrictModel):
    asset_class: Literal["us_equities"] = "us_equities"
    exchanges: list[str] = Field(default_factory=list)
    sectors: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    exclude_symbols: list[str] = Field(default_factory=list)
    market_cap_min: float | None = None
    market_cap_max: float | None = None
    avg_dollar_volume_min: float | None = None

    @field_validator("market_cap_min", "market_cap_max", "avg_dollar_volume_min")
    @classmethod
    def non_negative_numbers(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("must be non-negative")
        return value

    @model_validator(mode="after")
    def validate_bounds(self) -> "UniverseSpec":
        if (
            self.market_cap_min is not None
            and self.market_cap_max is not None
            and self.market_cap_min > self.market_cap_max
        ):
            raise ValueError("market_cap_min cannot exceed market_cap_max")
        return self


class SignalSpec(StrictModel):
    kind: str
    source: Literal["open", "high", "low", "close", "adjusted_close", "volume"] = (
        "adjusted_close"
    )
    lookback_days: int | None = None
    fast_lookback_days: int | None = None
    slow_lookback_days: int | None = None
    window_days: int | None = None
    threshold: float | None = None
    operator: Literal["gt", "gte", "lt", "lte"] | None = None
    invert: bool = False
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def kind_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("kind must not be empty")
        return value

    @field_validator("lookback_days", "fast_lookback_days", "slow_lookback_days", "window_days")
    @classmethod
    def positive_windows(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("window values must be greater than zero")
        return value

    @model_validator(mode="after")
    def validate_signal_shape(self) -> "SignalSpec":
        if self.kind == "sma_crossover":
            if self.fast_lookback_days is None or self.slow_lookback_days is None:
                raise ValueError(
                    "sma_crossover requires fast_lookback_days and slow_lookback_days"
                )
            if self.fast_lookback_days >= self.slow_lookback_days:
                raise ValueError("fast_lookback_days must be less than slow_lookback_days")
        return self


class SelectionSpec(StrictModel):
    source_signal: str
    top_n: int
    max_positions: int
    order: Literal["asc", "desc"] = "desc"
    min_score: float | None = None

    @field_validator("source_signal")
    @classmethod
    def source_signal_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("source_signal must not be empty")
        return value

    @field_validator("top_n", "max_positions")
    @classmethod
    def positive_counts(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value

    @model_validator(mode="after")
    def validate_position_limits(self) -> "SelectionSpec":
        if self.top_n > self.max_positions:
            raise ValueError("top_n cannot exceed max_positions")
        return self


class PortfolioConstructionSpec(StrictModel):
    method: Literal["equal_weight"] = "equal_weight"
    max_positions: int
    target_gross_exposure: float = 1.0

    @field_validator("max_positions")
    @classmethod
    def max_positions_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("max_positions must be greater than zero")
        return value

    @field_validator("target_gross_exposure")
    @classmethod
    def exposure_must_be_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("target_gross_exposure must be greater than zero")
        return value


class RiskSpec(StrictModel):
    max_position_weight: float | None = 1.0
    max_sector_weight: float | None = None
    max_turnover: float | None = None
    max_drawdown: float | None = None

    @field_validator(
        "max_position_weight",
        "max_sector_weight",
        "max_turnover",
        "max_drawdown",
    )
    @classmethod
    def risk_values_in_unit_interval(cls, value: float | None) -> float | None:
        if value is not None and not 0 < value <= 1:
            raise ValueError("risk values must be within (0, 1]")
        return value


class RebalanceSpec(StrictModel):
    frequency: Literal["daily", "weekly", "monthly"]
    day_of_week: Literal["monday", "tuesday", "wednesday", "thursday", "friday"] | None = None
    day_of_month: int | None = None

    @field_validator("day_of_month")
    @classmethod
    def valid_month_day(cls, value: int | None) -> int | None:
        if value is not None and not 1 <= value <= 31:
            raise ValueError("day_of_month must be between 1 and 31")
        return value

    @model_validator(mode="after")
    def validate_schedule(self) -> "RebalanceSpec":
        if self.frequency == "weekly" and self.day_of_week is None:
            raise ValueError("weekly rebalance requires day_of_week")
        if self.frequency == "monthly" and self.day_of_month is None:
            raise ValueError("monthly rebalance requires day_of_month")
        return self


class ExecutionSpec(StrictModel):
    order_type: Literal["market", "market_on_close"] = "market"
    time_in_force: Literal["day", "gtc"] = "day"
    slippage_bps: float | None = None
    commission_bps: float | None = None
    allow_fractional_shares: bool = False

    @field_validator("slippage_bps", "commission_bps")
    @classmethod
    def bps_must_be_non_negative(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("basis points values must be non-negative")
        return value


class BenchmarkSpec(StrictModel):
    symbol: str = "SPY"

    @field_validator("symbol")
    @classmethod
    def symbol_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("symbol must not be empty")
        return value.upper()


class BacktestSpec(StrictModel):
    initial_capital: float = 100000.0
    start_date: str | None = None
    end_date: str | None = None

    @field_validator("initial_capital")
    @classmethod
    def capital_must_be_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("initial_capital must be greater than zero")
        return value


class DeploymentSpec(StrictModel):
    mode: Literal["disabled", "paper", "live"] = "disabled"


class StrategySpec(StrictModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    metadata: MetadataSpec = Field(default_factory=MetadataSpec)
    universe: UniverseSpec
    direction: Literal["long_only"]
    signals: dict[str, SignalSpec]
    selection: SelectionSpec
    portfolio_construction: PortfolioConstructionSpec
    risk: RiskSpec = Field(default_factory=RiskSpec)
    rebalance: RebalanceSpec
    execution: ExecutionSpec = Field(default_factory=ExecutionSpec)
    benchmark: BenchmarkSpec = Field(default_factory=BenchmarkSpec)
    backtest: BacktestSpec = Field(default_factory=BacktestSpec)
    deployment: DeploymentSpec = Field(default_factory=DeploymentSpec)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("signals")
    @classmethod
    def signals_must_not_be_empty(cls, value: dict[str, SignalSpec]) -> dict[str, SignalSpec]:
        if not value:
            raise ValueError("signals must contain at least one signal")
        return value
