from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend.app.brokers.ibkr_adapter import IBKRBrokerAdapter
from backend.app.live.live_engine import evaluate_strategy_tick
from backend.app.models.compiled_strategy import CompiledStrategy
from backend.app.models.trading import (
    AccountSummary,
    BrokerOrderResult,
    DeploymentStatus,
    PaperDeployment,
    PositionSnapshot,
)


class PaperTradingService:
    def __init__(self) -> None:
        self._deployments: dict[str, PaperDeployment] = {}

    def start_deployment(self, compiled_strategy: CompiledStrategy) -> PaperDeployment:
        if compiled_strategy.execution_plan.deployment_mode != "paper":
            raise ValueError("Only paper deployment mode is supported.")

        deployment_id = uuid.uuid4().hex
        deployment = PaperDeployment(
            deployment_id=deployment_id,
            compiled_strategy=compiled_strategy,
            created_at=datetime.now(timezone.utc).isoformat(),
            status=DeploymentStatus(state="created", detail="Paper deployment created."),
        )

        adapter = IBKRBrokerAdapter()
        try:
            adapter.connect()
            account_summary = adapter.get_account_summary()
            positions = adapter.get_positions()
            deployment = deployment.model_copy(
                update={
                    "status": DeploymentStatus(
                        state="paper_ready",
                        detail="Connected to IBKR paper session and ready to evaluate ticks.",
                    ),
                    "account_summary": account_summary,
                    "positions": positions,
                }
            )
        except Exception as exc:
            deployment = deployment.model_copy(
                update={
                    "status": DeploymentStatus(
                        state="paper_error",
                        detail="Failed to initialize IBKR paper deployment.",
                    ),
                    "last_error": str(exc),
                }
            )
        finally:
            try:
                adapter.disconnect()
            except Exception:
                pass

        self._deployments[deployment_id] = deployment
        return deployment

    def get_deployment(self, deployment_id: str) -> PaperDeployment:
        deployment = self._deployments.get(deployment_id)
        if deployment is None:
            raise KeyError(f"Unknown deployment id: {deployment_id}")
        return deployment

    def evaluate_snapshot(
        self,
        deployment_id: str,
        latest_market_data: pd.DataFrame,
        submit_orders: bool = False,
    ) -> PaperDeployment:
        deployment = self.get_deployment(deployment_id)
        current_positions = deployment.positions
        order_intents = evaluate_strategy_tick(
            compiled_strategy=deployment.compiled_strategy,
            latest_market_data=latest_market_data,
            current_positions=current_positions,
        )

        pending_orders: list[BrokerOrderResult] = []
        if submit_orders and order_intents:
            adapter = IBKRBrokerAdapter()
            try:
                adapter.connect()
                pending_orders = [adapter.place_order(order_intent) for order_intent in order_intents]
            finally:
                try:
                    adapter.disconnect()
                except Exception:
                    pass

        updated = deployment.model_copy(
            update={
                "status": DeploymentStatus(
                    state="paper_running",
                    detail=f"Evaluated latest snapshot and generated {len(order_intents)} order intents.",
                ),
                "pending_orders": pending_orders,
            }
        )
        self._deployments[deployment_id] = updated
        return updated


_PAPER_TRADING_SERVICE = PaperTradingService()


def get_paper_trading_service() -> PaperTradingService:
    return _PAPER_TRADING_SERVICE
