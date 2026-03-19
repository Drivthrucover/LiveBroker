from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint

from pydantic import ValidationError

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.app.compiler.compiler import CompilationContext, DataRegistry, compile_strategy
from backend.app.models.strategy_spec import StrategySpec
from backend.app.validator.validator import CapabilityRegistry, validate_strategy


def build_valid_spec_payload() -> dict:
    return {
        "schema_version": "1.0.0",
        "metadata": {
            "name": "Weekly Momentum Demo",
            "description": "Minimal valid spec for backend core smoke testing.",
            "author": "scratch_test_core",
            "tags": ["smoke-test"],
        },
        "universe": {
            "asset_class": "us_equities",
            "market_cap_min": 1_000_000_000,
            "avg_dollar_volume_min": 5_000_000,
        },
        "direction": "long_only",
        "signals": {
            "momentum_1m": {
                "kind": "momentum_return",
                "source": "adjusted_close",
                "lookback_days": 21,
            }
        },
        "selection": {
            "source_signal": "momentum_1m",
            "top_n": 5,
            "max_positions": 5,
            "order": "desc",
        },
        "portfolio_construction": {
            "method": "equal_weight",
            "max_positions": 5,
            "target_gross_exposure": 1.0,
        },
        "risk": {
            "max_position_weight": 0.25,
            "max_turnover": 0.5,
        },
        "rebalance": {
            "frequency": "weekly",
            "day_of_week": "monday",
        },
        "execution": {
            "order_type": "market",
            "time_in_force": "day",
        },
        "benchmark": {
            "symbol": "SPY",
        },
        "backtest": {
            "initial_capital": 100_000,
            "start_date": "2020-01-01",
            "end_date": "2024-12-31",
        },
        "deployment": {
            "mode": "paper",
        },
        "assumptions": [],
        "warnings": [],
    }


def run_case(name: str, payload: dict) -> None:
    print(f"\n=== {name} ===")
    try:
        spec = StrategySpec.model_validate(payload)
        print("Schema validation: PASS")
    except ValidationError as exc:
        print("Schema validation: FAIL")
        print(exc)
        return

    validation = validate_strategy(spec, CapabilityRegistry())
    print(f"Semantic/platform validation: {'PASS' if validation.valid else 'FAIL'}")
    print("Validator errors:")
    pprint(validation.errors)
    print("Validator warnings:")
    pprint(validation.warnings)

    if not validation.valid:
        print("Compilation skipped because validator failed.")
        return

    try:
        compiled = compile_strategy(
            spec=spec,
            capability_registry=CapabilityRegistry(),
            data_registry=DataRegistry(),
            context=CompilationContext(),
        )
        print("Compilation: PASS")
        print("Compiled strategy summary:")
        pprint(
            {
                "universe_plan": compiled.universe_plan.model_dump(),
                "signal_plan_keys": sorted(compiled.signal_plan.keys()),
                "selection_plan": compiled.selection_plan.model_dump(),
                "portfolio_plan": compiled.portfolio_plan.model_dump(),
                "risk_plan": compiled.risk_plan.model_dump(),
                "execution_plan": compiled.execution_plan.model_dump(),
                "schedule": compiled.schedule.model_dump(),
                "data_requirements": [req.model_dump() for req in compiled.data_requirements],
            }
        )
    except Exception as exc:  # pragma: no cover - scratch script
        print("Compilation: FAIL")
        print(repr(exc))


def main() -> None:
    valid_payload = build_valid_spec_payload()

    unsupported_signal_payload = build_valid_spec_payload()
    unsupported_signal_payload["signals"] = {
        "alpha_magic": {
            "kind": "totally_new_signal",
            "source": "adjusted_close",
            "lookback_days": 10,
        }
    }
    unsupported_signal_payload["selection"]["source_signal"] = "alpha_magic"

    bad_selection_payload = build_valid_spec_payload()
    bad_selection_payload["selection"] = {
        "source_signal": "missing_signal",
        "top_n": 5,
        "max_positions": 5,
        "order": "desc",
    }

    schema_invalid_payload = build_valid_spec_payload()
    schema_invalid_payload["signals"]["momentum_1m"]["lookback_days"] = 0

    live_deployment_payload = build_valid_spec_payload()
    live_deployment_payload["deployment"] = {"mode": "live"}

    cases = [
        ("Valid spec", valid_payload),
        ("Unsupported signal", unsupported_signal_payload),
        ("Bad selection references", bad_selection_payload),
        ("Schema-invalid lookback", schema_invalid_payload),
        ("Unsupported live deployment", live_deployment_payload),
    ]

    for case_name, case_payload in cases:
        run_case(case_name, case_payload)


if __name__ == "__main__":
    main()
