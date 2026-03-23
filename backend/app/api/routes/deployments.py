from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[4]))

from backend.app.models.compiled_strategy import CompiledStrategy
from backend.app.models.strategy_spec import StrictModel

router = APIRouter(prefix="/api/deployments", tags=["deployments"])


class StartDeploymentRequest(StrictModel):
    compiled_strategy: CompiledStrategy


@router.post("/start")
def start_deployment(_: StartDeploymentRequest) -> dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Deployment activation is not implemented yet because the live paper engine is not available.",
    )
