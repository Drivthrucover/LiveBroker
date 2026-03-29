from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from pydantic import Field

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend.app.models.compiled_strategy import CompiledStrategy
from backend.app.models.strategy_spec import StrictModel


class PositionSnapshot(StrictModel):
    symbol: str
    quantity: float
    avg_price: float = 0.0
    market_price: float | None = None
    market_value: float | None = None


class OrderIntent(StrictModel):
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    order_type: Literal["market"] = "market"


class BrokerOrderResult(StrictModel):
    order_id: str
    status: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    order_type: str
    broker_message: str | None = None


class AccountSummary(StrictModel):
    account_id: str | None = None
    currency: str = "USD"
    cash: float = 0.0
    buying_power: float = 0.0
    net_liquidation: float = 0.0


class DeploymentStatus(StrictModel):
    state: Literal["created", "paper_ready", "paper_running", "paper_error", "stopped"]
    detail: str | None = None


class PaperDeployment(StrictModel):
    deployment_id: str
    mode: Literal["paper"] = "paper"
    compiled_strategy: CompiledStrategy
    status: DeploymentStatus
    created_at: str
    account_summary: AccountSummary | None = None
    positions: list[PositionSnapshot] = Field(default_factory=list)
    pending_orders: list[BrokerOrderResult] = Field(default_factory=list)
    last_error: str | None = None
