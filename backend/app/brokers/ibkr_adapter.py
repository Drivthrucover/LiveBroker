from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend.app.models.trading import AccountSummary, BrokerOrderResult, OrderIntent, PositionSnapshot


@dataclass(slots=True)
class IBKRConnectionConfig:
    host: str
    port: int
    client_id: int
    account_id: str | None = None
    connect_timeout_seconds: float = 8.0
    request_timeout_seconds: float = 10.0


@dataclass(slots=True)
class _IBKRRuntimeState:
    connected_event: threading.Event = field(default_factory=threading.Event)
    next_order_id_event: threading.Event = field(default_factory=threading.Event)
    positions_complete_event: threading.Event = field(default_factory=threading.Event)
    account_summary_complete_event: threading.Event = field(default_factory=threading.Event)
    next_order_id: int | None = None
    account_summary: dict[str, str] = field(default_factory=dict)
    account_id: str | None = None
    positions: list[PositionSnapshot] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class IBKRBrokerAdapter:
    def __init__(self, config: IBKRConnectionConfig | None = None) -> None:
        self.config = config or self._load_config()
        self._client: Any | None = None
        self._thread: threading.Thread | None = None
        self._state = _IBKRRuntimeState()

    def connect(self) -> None:
        if self._client is not None and self._state.connected_event.is_set():
            return

        EClient, EWrapper, Contract, Order = self._load_ibapi()
        self._contract_cls = Contract
        self._order_cls = Order

        adapter = self

        class _IBClient(EWrapper, EClient):
            def __init__(self) -> None:
                EClient.__init__(self, self)

            def nextValidId(self, orderId: int) -> None:  # noqa: N802
                adapter._state.next_order_id = orderId
                adapter._state.connected_event.set()
                adapter._state.next_order_id_event.set()

            def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N803
                message = f"IBKR error {errorCode}: {errorString}"
                adapter._state.errors.append(message)

            def position(self, account: str, contract: Any, position: float, avgCost: float) -> None:
                adapter._state.positions.append(
                    PositionSnapshot(
                        symbol=str(contract.symbol).upper(),
                        quantity=float(position),
                        avg_price=float(avgCost),
                    )
                )

            def positionEnd(self) -> None:  # noqa: N802
                adapter._state.positions_complete_event.set()

            def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str) -> None:  # noqa: N802
                adapter._state.account_id = account
                adapter._state.account_summary[tag] = value

            def accountSummaryEnd(self, reqId: int) -> None:  # noqa: N802
                adapter._state.account_summary_complete_event.set()

        self._client = _IBClient()
        self._client.connect(self.config.host, self.config.port, clientId=self.config.client_id)
        self._thread = threading.Thread(target=self._client.run, daemon=True, name="ibkr-api-thread")
        self._thread.start()

        if not self._state.connected_event.wait(self.config.connect_timeout_seconds):
            self.disconnect()
            errors = "; ".join(self._state.errors) or "Timed out waiting for IBKR nextValidId."
            raise RuntimeError(f"Failed to connect to IBKR paper session: {errors}")

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            finally:
                self._client = None
                self._thread = None
                self._state = _IBKRRuntimeState()

    def get_positions(self) -> list[PositionSnapshot]:
        self._require_connected()
        self._state.positions = []
        self._state.positions_complete_event.clear()
        self._client.reqPositions()
        self._wait_for(self._state.positions_complete_event, "positions")
        return list(self._state.positions)

    def get_account_summary(self) -> AccountSummary:
        self._require_connected()
        self._state.account_summary = {}
        self._state.account_summary_complete_event.clear()
        self._client.reqAccountSummary(1, "All", "NetLiquidation,BuyingPower,TotalCashValue")
        self._wait_for(self._state.account_summary_complete_event, "account summary")
        return AccountSummary(
            account_id=self.config.account_id or self._state.account_id,
            cash=float(self._state.account_summary.get("TotalCashValue", 0.0) or 0.0),
            buying_power=float(self._state.account_summary.get("BuyingPower", 0.0) or 0.0),
            net_liquidation=float(self._state.account_summary.get("NetLiquidation", 0.0) or 0.0),
        )

    def place_order(self, order_intent: OrderIntent) -> BrokerOrderResult:
        self._require_connected()
        if self._state.next_order_id is None:
            raise RuntimeError("IBKR did not provide a valid order id.")

        order_id = self._state.next_order_id
        self._state.next_order_id += 1

        contract = self._contract_cls()
        contract.symbol = order_intent.symbol.upper()
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"

        order = self._order_cls()
        order.action = "BUY" if order_intent.side == "buy" else "SELL"
        order.orderType = "MKT"
        order.totalQuantity = float(order_intent.quantity)
        order.tif = "DAY"

        self._client.placeOrder(order_id, contract, order)

        return BrokerOrderResult(
            order_id=str(order_id),
            status="submitted",
            symbol=order_intent.symbol.upper(),
            side=order_intent.side,
            quantity=float(order_intent.quantity),
            order_type=order_intent.order_type,
            broker_message="Order submitted to IBKR paper session.",
        )

    @staticmethod
    def _load_ibapi() -> tuple[Any, Any, Any, Any]:
        try:
            from ibapi.client import EClient
            from ibapi.contract import Contract
            from ibapi.order import Order
            from ibapi.wrapper import EWrapper
        except ImportError as exc:
            raise RuntimeError(
                "ibapi is not installed. Add it to the environment before testing the IBKR workflow."
            ) from exc
        return EClient, EWrapper, Contract, Order

    @staticmethod
    def _load_config() -> IBKRConnectionConfig:
        host = _get_env_value("IBKR_HOST") or "127.0.0.1"
        port = int(_get_env_value("IBKR_PORT") or "7497")
        client_id = int(_get_env_value("IBKR_CLIENT_ID") or "1")
        account_id = _get_env_value("IBKR_ACCOUNT_ID")
        connect_timeout_seconds = float(_get_env_value("IBKR_CONNECT_TIMEOUT_SECONDS") or "8")
        request_timeout_seconds = float(_get_env_value("IBKR_REQUEST_TIMEOUT_SECONDS") or "10")
        return IBKRConnectionConfig(
            host=host,
            port=port,
            client_id=client_id,
            account_id=account_id,
            connect_timeout_seconds=connect_timeout_seconds,
            request_timeout_seconds=request_timeout_seconds,
        )

    def _require_connected(self) -> None:
        if self._client is None or not self._state.connected_event.is_set():
            raise RuntimeError("IBKR adapter is not connected.")

    def _wait_for(self, event: threading.Event, label: str) -> None:
        if event.wait(self.config.request_timeout_seconds):
            return
        errors = "; ".join(self._state.errors) or f"Timed out waiting for {label}."
        raise RuntimeError(errors)


def _dotenv_fallback_values() -> dict[str, str]:
    values: dict[str, str] = {}
    candidate_paths = [
        Path.cwd() / ".env",
        Path.cwd() / ".env.txt",
        Path.cwd() / "backend" / ".env",
        Path.cwd() / "backend" / ".env.txt",
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


def _get_env_value(key: str) -> str | None:
    return os.getenv(key) or _dotenv_fallback_values().get(key)
