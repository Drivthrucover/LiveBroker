from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import backtest_router, deployments_router, strategy_router

app = FastAPI(title="LiveBroker API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(strategy_router)
app.include_router(backtest_router)
app.include_router(deployments_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
