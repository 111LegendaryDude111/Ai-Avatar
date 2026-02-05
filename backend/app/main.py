from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router as api_router
from .config import settings
from .worker import worker_loop


def create_app() -> FastAPI:
    app = FastAPI(title="AI Video Avatar Studio", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    stop_event = asyncio.Event()
    worker_task: asyncio.Task[None] | None = None

    @app.on_event("startup")
    async def _startup() -> None:
        nonlocal worker_task
        worker_task = asyncio.create_task(worker_loop(stop_event))

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        stop_event.set()
        if worker_task:
            worker_task.cancel()

    @app.get("/health")
    async def health():
        return {"status": "ok", "generator_backend": settings.generator_backend}

    return app


app = create_app()
