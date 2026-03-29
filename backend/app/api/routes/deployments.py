from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[4]))

from backend.app.deployments.paper_service import get_paper_trading_service
from backend.app.models.compiled_strategy import CompiledStrategy
from backend.app.models.strategy_spec import StrictModel
from backend.app.models.trading import PaperDeployment

router = APIRouter(prefix="/api/deployments", tags=["deployments"])


class StartDeploymentRequest(StrictModel):
    compiled_strategy: CompiledStrategy


@router.post("/start", response_model=PaperDeployment)
def start_deployment(request: StartDeploymentRequest) -> PaperDeployment:
    try:
        return get_paper_trading_service().start_deployment(request.compiled_strategy)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
