"""FastAPI app. Start it with `python -m med_api serve`."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from med_api.context import ApiPaths
from med_api.service import AssessmentService
from med_api.version import API_CONTRACT_VERSION


def create_app(paths: ApiPaths | None = None) -> FastAPI:
    service = AssessmentService(paths or ApiPaths.from_env())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await run_in_threadpool(service.load)
        yield
        service.close()

    app = FastAPI(title="Misdirected email risk scoring (simulation)", version=API_CONTRACT_VERSION, lifespan=lifespan)
    app.state.service = service

    @app.get("/health")
    async def health():
        return {"status": "ok", "contract_version": API_CONTRACT_VERSION}

    @app.get("/ready")
    async def ready():
        ok, body = service.ready()
        return JSONResponse(body, status_code=200 if ok else 503)

    @app.post("/assess")
    async def assess(request: Request):
        payload = await _json(request)
        status, body = await run_in_threadpool(service.assess, payload)
        return JSONResponse(body, status_code=status)

    @app.post("/feedback")
    async def feedback(request: Request):
        payload = await _json(request)
        status, body = await run_in_threadpool(service.feedback, payload)
        return JSONResponse(body, status_code=status)

    return app


async def _json(request: Request):
    """Parse the body ourselves so malformed JSON maps to invalid_input, not a framework error."""
    raw = await request.body()
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _MALFORMED


class _Malformed:
    """Sentinel the normalizer rejects as not a JSON object."""


_MALFORMED = _Malformed()
