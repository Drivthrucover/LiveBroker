from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from openai import OpenAI
from pydantic import Field

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[3]))

from backend.app.models.strategy_spec import StrategySpec, StrictModel
from backend.app.validator.validator import CapabilityRegistry, ValidationResult, validate_strategy

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-5")

SYSTEM_INSTRUCTIONS = """
You convert natural-language trading strategy prompts into a strict StrategySpec JSON object.

Follow these product constraints exactly:
- US equities only
- direction must be long_only
- supported signal kinds only:
  - momentum_return
  - sma_crossover
  - realized_volatility
  - rsi
  - exclude_earnings_window
- portfolio construction method must be equal_weight
- deployment mode must be disabled or paper, never live
- execution must not include unsupported modes
- never emit executable code
- never invent unsupported asset classes, broker behavior, or strategy fields

Output must contain:
- strategy_spec_json
- assumptions
- warnings

strategy_spec_json must be a valid JSON string that parses into the StrategySpec schema.

Use assumptions when the user prompt leaves something underspecified.
Use warnings for ambiguity, unsupported requests, or narrowed scope.
Prefer valid, compilable StrategySpec output over literal interpretation of unsupported user requests.
""".strip()


class PromptParseRawResult(StrictModel):
    strategy_spec_json: str
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PromptParseResult(StrictModel):
    strategy_spec: StrategySpec
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def parse_strategy_prompt(prompt: str) -> PromptParseResult:
    client = OpenAI(api_key=_get_openai_api_key())
    raw_result = _parse_once(
        client=client,
        prompt=prompt,
        repair_context=None,
    )
    result = _materialize_result(raw_result)
    validation = validate_strategy(result.strategy_spec, CapabilityRegistry())
    if validation.valid:
        return _merge_validation_warnings(result, validation)

    repaired_raw = _parse_once(
        client=client,
        prompt=prompt,
        repair_context=validation,
        prior_result=result,
    )
    repaired = _materialize_result(repaired_raw)
    repaired_validation = validate_strategy(repaired.strategy_spec, CapabilityRegistry())
    if not repaired_validation.valid:
        errors = "; ".join(repaired_validation.errors)
        raise ValueError(f"Prompt parser produced an invalid StrategySpec: {errors}")

    return _merge_validation_warnings(repaired, repaired_validation)


def _parse_once(
    client: OpenAI,
    prompt: str,
    repair_context: ValidationResult | None,
    prior_result: PromptParseResult | None = None,
) -> PromptParseRawResult:
    repair_suffix = ""
    if repair_context is not None and prior_result is not None:
        repair_suffix = (
            "\n\nThe previous structured attempt failed semantic validation.\n"
            f"Validation errors: {repair_context.errors}\n"
            f"Validation warnings: {repair_context.warnings}\n"
            f"Previous result: {prior_result.model_dump_json()}\n"
            "Return a corrected PromptParseResult that satisfies the StrategySpec constraints."
        )

    response = client.responses.parse(
        model=MODEL_NAME,
        reasoning={"effort": "medium"},
        instructions=SYSTEM_INSTRUCTIONS,
        input=f"User prompt:\n{prompt}{repair_suffix}",
        text_format=PromptParseRawResult,
    )
    return response.output_parsed


def _merge_validation_warnings(
    result: PromptParseResult,
    validation: ValidationResult,
) -> PromptParseResult:
    merged_warnings = list(dict.fromkeys([*result.warnings, *validation.warnings]))
    return result.model_copy(update={"warnings": merged_warnings})


def _materialize_result(raw_result: PromptParseRawResult) -> PromptParseResult:
    strategy_spec = StrategySpec.model_validate_json(raw_result.strategy_spec_json)
    return PromptParseResult(
        strategy_spec=strategy_spec,
        assumptions=raw_result.assumptions,
        warnings=raw_result.warnings,
    )


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
