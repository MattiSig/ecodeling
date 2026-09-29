"""Contract and full model workflow tests for the bounded simulation service."""

from __future__ import annotations

import asyncio
import gzip
from collections.abc import Callable
from concurrent.futures import Future
from pathlib import Path

import httpx
import pytest

from ecodeling.reporting import load_replay_v1
from ecodeling.service.api import create_app


class InlineExecutor:
    """Run the production worker synchronously while preserving Future semantics."""

    def submit(
        self,
        fn: Callable[[dict[str, object], str, str], dict[str, object]],
        config_payload: dict[str, object],
        artifact_path: str,
        git_commit: str,
    ) -> Future[dict[str, object]]:
        future: Future[dict[str, object]] = Future()
        future.set_result(fn(config_payload, artifact_path, git_commit))
        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        pass


class HoldingExecutor:
    """Leave submitted jobs pending so queue limits and cancellation are deterministic."""

    def __init__(self) -> None:
        self.futures: list[Future[dict[str, object]]] = []

    def submit(
        self,
        fn: Callable[[dict[str, object], str, str], dict[str, object]],
        config_payload: dict[str, object],
        artifact_path: str,
        git_commit: str,
    ) -> Future[dict[str, object]]:
        del fn, config_payload, artifact_path, git_commit
        future: Future[dict[str, object]] = Future()
        self.futures.append(future)
        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        del wait
        if cancel_futures:
            for future in self.futures:
                future.cancel()


class FailingExecutor(InlineExecutor):
    """Complete a worker future with a controlled numerical failure."""

    def submit(
        self,
        fn: Callable[[dict[str, object], str, str], dict[str, object]],
        config_payload: dict[str, object],
        artifact_path: str,
        git_commit: str,
    ) -> Future[dict[str, object]]:
        del fn, config_payload, artifact_path, git_commit
        future: Future[dict[str, object]] = Future()
        future.set_exception(RuntimeError("controlled numerical invalidity"))
        return future


def payload(**updates: object) -> dict[str, object]:
    """Return a small valid public experiment."""
    base: dict[str, object] = {
        "months": 6,
        "seed": 42,
        "households": 10,
        "firms": 2,
        "indexation_lag_months": 1,
        "shock_kind": "fx_depreciation",
        "shock_month": 2,
        "shock_magnitude_bps": 750,
        "shock_persistence": "permanent",
        "import_share_bps": 2_000,
        "price_adjustment_bps": 2_500,
    }
    return base | updates


def test_browser_to_api_to_simulation_to_replay_and_cache(tmp_path: Path) -> None:
    """A completed custom run is immutable, reproducible, and reused on collision."""
    app = create_app(tmp_path, executor=InlineExecutor(), git_commit="abcdef1234567890")

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post("/api/v1/experiments", json=payload())
            assert created.status_code == 202
            identity = created.json()
            status = await client.get(identity["links"]["status"])
            assert status.json()["status"] == "completed"
            assert status.json()["configuration_hash"] == identity["configuration_hash"]

            result = await client.get(identity["links"]["result"])
            assert result.status_code == 200
            assert result.headers["cache-control"].endswith("immutable")
            replay = load_replay_v1(gzip.decompress(result.content))
            assert replay.manifest.seed == 42
            assert len(replay.timeline) == 6
            assert replay.manifest.git_commit == "abcdef1234567890"

            repeated = await client.post("/api/v1/experiments", json=payload())
            assert repeated.status_code == 200
            assert repeated.json()["cached"] is True
            assert repeated.json()["job_id"] == identity["job_id"]

    asyncio.run(exercise())
    assert len(tuple((tmp_path / "artifacts").glob("*.json.gz"))) == 1


def test_validation_limits_unknown_fields_and_request_size(tmp_path: Path) -> None:
    """Malformed, out-of-bounds, and oversized requests fail as structured errors."""
    app = create_app(tmp_path, executor=HoldingExecutor(), git_commit="abcdef1")

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            invalid = await client.post(
                "/api/v1/experiments",
                json=payload(months=61, arbitrary_internal_parameter=True),
            )
            assert invalid.status_code == 422
            assert invalid.json()["error"]["code"] == "validation_error"

            bad_timing = await client.post("/api/v1/experiments", json=payload(shock_month=6))
            assert bad_timing.status_code == 422

            oversized = await client.post(
                "/api/v1/experiments",
                content=b"x" * 8_193,
                headers={"content-type": "application/json"},
            )
            assert oversized.status_code == 413
            assert oversized.json()["error"]["code"] == "request_too_large"

    asyncio.run(exercise())


def test_queue_collision_capacity_failure_and_safe_cancellation(tmp_path: Path) -> None:
    """Collisions deduplicate, capacity is bounded, and only pending futures cancel."""
    executor = HoldingExecutor()
    app = create_app(
        tmp_path,
        max_workers=1,
        max_pending=1,
        executor=executor,
        git_commit="abcdef1",
    )

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await client.post("/api/v1/experiments", json=payload(seed=1))
            assert first.status_code == 202
            collision = await client.post("/api/v1/experiments", json=payload(seed=1))
            assert collision.status_code == 202
            assert collision.json()["job_id"] == first.json()["job_id"]
            assert len(executor.futures) == 1

            full = await client.post("/api/v1/experiments", json=payload(seed=2))
            assert full.status_code == 429
            assert full.headers["retry-after"] == "5"
            assert full.json()["error"]["code"] == "queue_full"

            cancelled = await client.delete(first.json()["links"]["status"])
            assert cancelled.status_code == 200
            job_status = await client.get(first.json()["links"]["status"])
            assert job_status.json()["status"] == "cancelled"
            unavailable = await client.get(first.json()["links"]["result"])
            assert unavailable.status_code == 409
            assert unavailable.json()["error"]["code"] == "result_not_ready"

    asyncio.run(exercise())


def test_worker_failure_is_structured_and_same_request_can_retry(tmp_path: Path) -> None:
    """A failed job retains canonical identity and can be safely resubmitted."""
    app = create_app(tmp_path, executor=FailingExecutor(), git_commit="abcdef1")

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            failed = await client.post("/api/v1/experiments", json=payload())
            job_id = failed.json()["job_id"]
            state = await client.get(f"/api/v1/experiments/{job_id}")
            assert state.json()["status"] == "failed"
            assert state.json()["failure"] == {
                "code": "simulation_failed",
                "message": "controlled numerical invalidity",
            }

            app.state.jobs.executor = InlineExecutor()
            retried = await client.post("/api/v1/experiments", json=payload())
            assert retried.status_code == 202
            assert retried.json()["job_id"] == job_id
            completed = await client.get(f"/api/v1/experiments/{job_id}")
            assert completed.json()["status"] == "completed"

    asyncio.run(exercise())


def test_cache_identity_changes_with_replay_export_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A corrected presentation must not reuse immutable defective replay files."""
    from ecodeling.config.schema import ModelConfig
    from ecodeling.identifiers import ScenarioId
    from ecodeling.service import jobs

    config = ModelConfig(scenario_id=ScenarioId("export-cache"))
    current = jobs.cache_key(config)
    monkeypatch.setattr(jobs, "REPLAY_EXPORT_REVISION", "earlier-export")
    assert jobs.cache_key(config) != current
