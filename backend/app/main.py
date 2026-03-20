from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import request_id_ctx, setup_logging
from app.core.models import ErrorResponse


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    setup_logging(settings.app_log_level, output=settings.app_log_output, file_path=settings.app_log_file)
    yield


app = FastAPI(title="Homework Backend", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    token = request_id_ctx.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    payload = ErrorResponse(
        error_code=exc.code,
        message=exc.detail,
        request_id=getattr(request.state, "request_id", "-"),
    )
    return JSONResponse(status_code=exc.spec.http_status, content=payload.model_dump())


@app.exception_handler(Exception)
async def internal_error_handler(request: Request, _: Exception):
    payload = ErrorResponse(
        error_code="INTERNAL_ERROR",
        message="Internal server error.",
        request_id=getattr(request.state, "request_id", "-"),
    )
    return JSONResponse(status_code=500, content=payload.model_dump())
