from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError
from pydantic import Field

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[4]))

from backend.app.compiler.compiler import CapabilityRegistry, CompilationContext, DataRegistry, compile_strategy
from backend.app.models.compiled_strategy import CompiledStrategy
from backend.app.models.strategy_spec import StrategySpec, StrictModel
from backend.app.parser.prompt_parser import (
    StrategyDraft,
    StrategyDraftSession,
    answer_strategy_draft,
    finalize_strategy_draft,
    parse_strategy_prompt,
    start_strategy_draft,
)
from backend.app.validator.validator import ValidationResult, validate_strategy

router = APIRouter(prefix="/api/strategy", tags=["strategy"])


class ParsePromptRequest(StrictModel):
    prompt: str


class ParsePromptResponse(StrictModel):
    strategy_spec: dict[str, Any]
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ValidateStrategyRequest(StrictModel):
    strategy_spec: StrategySpec


class CompileStrategyRequest(StrictModel):
    strategy_spec: StrategySpec


class SaveStrategyRequest(StrictModel):
    strategy_spec: StrategySpec
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DraftStartRequest(StrictModel):
    prompt: str


class DraftAnswerRequest(StrictModel):
    draft: StrategyDraft
    question_key: str
    answer: str


class DraftFinalizeRequest(StrictModel):
    draft: StrategyDraft


@router.post("/parse", response_model=ParsePromptResponse)
def parse_prompt(request: ParsePromptRequest) -> ParsePromptResponse:
    try:
        parsed = parse_strategy_prompt(request.prompt)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OpenAI authentication failed. Check OPENAI_API_KEY.",
        ) from exc
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OpenAI quota or rate limit exceeded for prompt parsing.",
        ) from exc
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API connection failed during prompt parsing.",
        ) from exc
    except APIStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI API returned an error during prompt parsing: {exc.status_code}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return ParsePromptResponse(
        strategy_spec=parsed.strategy_spec.model_dump(mode="json"),
        assumptions=parsed.assumptions,
        warnings=parsed.warnings,
    )


@router.post("/draft/start", response_model=StrategyDraftSession)
def start_strategy_draft_route(request: DraftStartRequest) -> StrategyDraftSession:
    try:
        return start_strategy_draft(request.prompt)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OpenAI authentication failed. Check OPENAI_API_KEY.",
        ) from exc
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OpenAI quota or rate limit exceeded for prompt parsing.",
        ) from exc
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API connection failed during prompt parsing.",
        ) from exc
    except APIStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI API returned an error during prompt parsing: {exc.status_code}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/draft/answer", response_model=StrategyDraftSession)
def answer_strategy_draft_route(request: DraftAnswerRequest) -> StrategyDraftSession:
    try:
        return answer_strategy_draft(
            draft=request.draft,
            question_key=request.question_key,  # validated at parser layer
            answer=request.answer,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OpenAI authentication failed. Check OPENAI_API_KEY.",
        ) from exc
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OpenAI quota or rate limit exceeded for prompt parsing.",
        ) from exc
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API connection failed during prompt parsing.",
        ) from exc
    except APIStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI API returned an error during prompt parsing: {exc.status_code}",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/draft/finalize", response_model=ParsePromptResponse)
def finalize_strategy_draft_route(request: DraftFinalizeRequest) -> ParsePromptResponse:
    try:
        parsed = finalize_strategy_draft(request.draft)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ParsePromptResponse(
        strategy_spec=parsed.strategy_spec.model_dump(mode="json"),
        assumptions=parsed.assumptions,
        warnings=parsed.warnings,
    )


@router.post("/validate", response_model=ValidationResult)
def validate_strategy_route(request: ValidateStrategyRequest) -> ValidationResult:
    return validate_strategy(spec=request.strategy_spec, capability_registry=CapabilityRegistry())


@router.post("/compile", response_model=CompiledStrategy)
def compile_strategy_route(request: CompileStrategyRequest) -> CompiledStrategy:
    return compile_strategy(
        spec=request.strategy_spec,
        capability_registry=CapabilityRegistry(),
        data_registry=DataRegistry(),
        context=CompilationContext(),
    )


@router.post("/save")
def save_strategy(_: SaveStrategyRequest) -> dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Strategy persistence is not implemented yet because the database layer is not available.",
    )
