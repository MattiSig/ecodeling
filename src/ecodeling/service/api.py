"""FastAPI contract for bounded public simulation experiments."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ecodeling import __version__
from ecodeling.config.schema import ShockKind, ShockPersistence
from ecodeling.reporting import current_git_commit
from ecodeling.service.jobs import Executor, JobManager, public_model_config

MAX_REQUEST_BYTES = 8_192


class APIModel(BaseModel):
    """Strict public API base."""

    model_config = ConfigDict(extra="forbid")


class ExperimentRequest(APIModel):
    """Intentionally small allowlist of safe result-affecting controls."""

    months: Annotated[int, Field(ge=6, le=60)] = 18
    seed: Annotated[int, Field(ge=0, le=2**64 - 1)] = 1010
    households: Annotated[int, Field(ge=10, le=250)] = 20
    firms: Annotated[int, Field(ge=2, le=50)] = 4
    indexation_lag_months: Annotated[int, Field(ge=0, le=24)] = 1
    shock_kind: Literal[ShockKind.FX_DEPRECIATION, ShockKind.FOREIGN_PRICE_INCREASE] = (
        ShockKind.FX_DEPRECIATION
    )
    shock_month: Annotated[int, Field(ge=1)] | None = 3
    shock_magnitude_bps: Annotated[int, Field(ge=-5_000, le=5_000)] = 1_000
    shock_persistence: ShockPersistence = ShockPersistence.PERMANENT
    import_share_bps: Annotated[int, Field(ge=0, le=7_500)] = 2_500
    price_adjustment_bps: Annotated[int, Field(ge=100, le=10_000)] = 2_500

    @model_validator(mode="after")
    def validate_timeline(self) -> ExperimentRequest:
        """Keep active shocks inside the bounded public timeline."""
        if self.shock_month is None or self.shock_month >= self.months:
            raise ValueError("shock_month must fall within the experiment timeline")
        return self


class JobLinks(APIModel):
    """Stable URLs for polling and replay loading."""

    status: str
    result: str


class ExperimentCreated(APIModel):
    """Submission identity and reproducibility metadata."""

    job_id: str
    status: str
    cached: bool
    model_version: str
    configuration_hash: str
    links: JobLinks


def _error(code: str, message: str, *, details: object | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"] = {"code": code, "message": message, "details": details}
    return payload


def create_app(
    storage: Path | None = None,
    *,
    max_workers: int = 2,
    max_pending: int = 8,
    executor: Executor | None = None,
    git_commit: str | None = None,
) -> FastAPI:
    """Create an isolated service instance with explicit resource limits."""
    root = storage or Path(os.environ.get("ECODELING_SERVICE_DATA", "runs/service"))
    manager = JobManager(
        root,
        git_commit=git_commit or current_git_commit(),
        max_workers=max_workers,
        max_pending=max_pending,
        executor=executor,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        manager.close()

    app = FastAPI(
        title="Ecodeling Simulation API",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.jobs = manager

    @app.middleware("http")
    async def enforce_request_size(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Reject declared request bodies before parsing or allocation."""
        length = request.headers.get("content-length")
        try:
            declared_length = int(length) if length is not None else 0
        except ValueError:
            return JSONResponse(
                _error("invalid_content_length", "Content-Length must be an integer"),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if declared_length > MAX_REQUEST_BYTES:
            return JSONResponse(
                _error("request_too_large", f"request body limit is {MAX_REQUEST_BYTES} bytes"),
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            )
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            _error(
                "validation_error",
                "experiment parameters are invalid",
                details=jsonable_encoder(error.errors()),
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, error: HTTPException) -> JSONResponse:
        detail = error.detail
        body = {"error": detail} if isinstance(detail, dict) else _error("http_error", str(detail))
        return JSONResponse(body, status_code=error.status_code, headers=error.headers)

    @app.post("/api/v1/experiments", response_model=ExperimentCreated)
    async def create_experiment(
        payload: ExperimentRequest, response: Response
    ) -> ExperimentCreated:
        config = public_model_config(payload)
        try:
            submission = manager.submit(config)
        except OverflowError as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=_error("queue_full", str(error))["error"],
                headers={"Retry-After": "5"},
            ) from error
        response.status_code = status.HTTP_200_OK if submission.cached else status.HTTP_202_ACCEPTED
        base = f"/api/v1/experiments/{submission.job_id}"
        return ExperimentCreated(
            job_id=submission.job_id,
            status=submission.status,
            cached=submission.cached,
            model_version=__version__,
            configuration_hash=submission.configuration_hash,
            links=JobLinks(status=base, result=f"{base}/result"),
        )

    @app.get("/api/v1/experiments/{job_id}")
    async def experiment_status(job_id: str) -> dict[str, object]:
        record = manager.store.get(job_id)
        if record is None:
            raise HTTPException(
                status_code=404, detail=_error("not_found", "job not found")["error"]
            )
        state = str(record["status"])
        progress = {"queued": 0, "running": 50, "completed": 100, "failed": 100, "cancelled": 100}[
            state
        ]
        output: dict[str, object] = {
            "job_id": job_id,
            "status": state,
            "progress_percent": progress,
            "model_version": __version__,
            "configuration_hash": record["configuration_hash"],
        }
        if state == "completed":
            output["result_url"] = f"/api/v1/experiments/{job_id}/result"
            output["sha256"] = record["sha256"]
        elif state == "failed":
            output["failure"] = {
                "code": record["error_code"],
                "message": record["error_message"],
            }
        return output

    @app.get("/api/v1/experiments/{job_id}/result")
    async def experiment_result(job_id: str) -> Response:
        record = manager.store.get(job_id)
        if record is None:
            raise HTTPException(
                status_code=404, detail=_error("not_found", "job not found")["error"]
            )
        if record["status"] != "completed":
            raise HTTPException(
                status_code=409,
                detail=_error("result_not_ready", f"job is {record['status']}")["error"],
            )
        artifact = Path(str(record["artifact_path"]))
        if not artifact.is_file():
            raise HTTPException(
                status_code=500,
                detail=_error("artifact_missing", "completed result artifact is unavailable")[
                    "error"
                ],
            )
        return Response(
            content=artifact.read_bytes(),
            media_type="application/gzip",
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "Content-Disposition": f'attachment; filename="ecodeling-{job_id}.json.gz"',
                "ETag": f'"{record["sha256"]}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.delete("/api/v1/experiments/{job_id}")
    async def cancel_experiment(job_id: str) -> Response:
        record = manager.store.get(job_id)
        if record is None:
            raise HTTPException(
                status_code=404, detail=_error("not_found", "job not found")["error"]
            )
        if manager.cancel(job_id):
            return JSONResponse({"job_id": job_id, "status": "cancelled"})
        raise HTTPException(
            status_code=409,
            detail=_error("not_cancellable", "only queued work can be cancelled safely")["error"],
        )

    return app


app = create_app()
