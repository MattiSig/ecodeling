"""Process-isolated simulation jobs with SQLite cache metadata."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

from ecodeling import __version__
from ecodeling.config.schema import (
    ForeignSectorConfig,
    IndexationConfig,
    MicroSimulationConfig,
    ModelConfig,
    RealEconomyConfig,
    ShockConfig,
    ShockKind,
    ShockPersistence,
    SimulationConfig,
)
from ecodeling.economy import run_endogenous_indexation_comparison
from ecodeling.identifiers import ScenarioId
from ecodeling.reporting import export_replay_v1, serialize_replay_v1

MAX_REPLAY_BYTES = 2_000_000


class PublicExperiment(Protocol):
    """Fields accepted by the public parameter allowlist."""

    months: int
    seed: int
    households: int
    firms: int
    indexation_lag_months: int
    shock_kind: Literal[ShockKind.FX_DEPRECIATION, ShockKind.FOREIGN_PRICE_INCREASE]
    shock_month: int | None
    shock_magnitude_bps: int
    shock_persistence: ShockPersistence
    import_share_bps: int
    price_adjustment_bps: int


class Executor(Protocol):
    """Subset of an executor used by the job manager."""

    def submit(
        self,
        fn: Callable[[dict[str, object], str, str], dict[str, object]],
        config_payload: dict[str, object],
        artifact_path: str,
        git_commit: str,
    ) -> Future[dict[str, object]]:
        """Schedule work and return a future."""

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """Release executor resources."""


@dataclass(frozen=True, slots=True)
class JobSubmission:
    """Stable identity and current state returned for a submission."""

    job_id: str
    status: str
    cached: bool
    configuration_hash: str


def public_model_config(request: PublicExperiment) -> ModelConfig:
    """Map the allowlisted public surface onto a complete validated model config."""
    shock = ShockConfig(
        kind=request.shock_kind,
        month=request.shock_month,
        magnitude=request.shock_magnitude_bps / 10_000,
        persistence=request.shock_persistence,
    )
    return ModelConfig(
        scenario_id=ScenarioId("public-laboratory"),
        simulation=SimulationConfig(months=request.months, seed=request.seed),
        indexation=IndexationConfig(lag_months=request.indexation_lag_months),
        micro=MicroSimulationConfig(households=request.households, banks=1),
        real_economy=RealEconomyConfig(
            firms=request.firms,
            price_adjustment_bps=request.price_adjustment_bps,
            firm_cash_buffer_months=max(120, request.months),
        ),
        foreign_sector=ForeignSectorConfig(import_share_bps=request.import_share_bps),
        shock=shock,
    )


def cache_key(config: ModelConfig) -> str:
    """Key results by model version and every result-affecting parameter."""
    material = f"{__version__}\0{config.configuration_hash()}".encode()
    return hashlib.sha256(material).hexdigest()


def _execute_job(
    config_payload: dict[str, object], artifact_path: str, git_commit: str
) -> dict[str, object]:
    """Run a complete pair and atomically publish its validated replay artifact."""
    config = ModelConfig.model_validate(config_payload)
    pair = run_endogenous_indexation_comparison(config)
    bundle = export_replay_v1(
        pair,
        git_commit=git_commit,
        maximum_uncompressed_bytes=MAX_REPLAY_BYTES,
    )
    artifact = serialize_replay_v1(bundle)
    destination = Path(artifact_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f".tmp-{os.getpid()}")
    temporary.write_bytes(artifact.gzip_bytes)
    if destination.exists():
        temporary.unlink()
    else:
        temporary.replace(destination)
    return {
        "sha256": artifact.sha256,
        "compressed_bytes": len(artifact.gzip_bytes),
        "uncompressed_bytes": len(artifact.canonical_bytes),
    }


class JobStore:
    """Small transactional SQLite metadata store; artifacts stay on the filesystem."""

    def __init__(self, database: Path) -> None:
        """Initialize schema and mark abandoned work as failed."""
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    configuration_hash TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    artifact_path TEXT,
                    sha256 TEXT,
                    compressed_bytes INTEGER,
                    uncompressed_bytes INTEGER,
                    error_code TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "UPDATE jobs SET status='failed', error_code='worker_interrupted', "
                "error_message='Service restarted before the worker completed', "
                "updated_at=CURRENT_TIMESTAMP WHERE status IN ('queued', 'running')"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def get(self, job_id: str) -> dict[str, object] | None:
        """Return one detached job record."""
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row is not None else None

    def create(self, job_id: str, config: ModelConfig, artifact_path: Path) -> bool:
        """Insert a queued job atomically; return false for a colliding cache key."""
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO jobs "
                    "(job_id, configuration_hash, config_json, status, artifact_path) "
                    "VALUES (?, ?, ?, 'queued', ?)",
                    (
                        job_id,
                        config.configuration_hash(),
                        config.canonical_json(),
                        str(artifact_path),
                    ),
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def update(self, job_id: str, status: str, **fields: object) -> None:
        """Update only internal fixed columns."""
        allowed = {
            "sha256",
            "compressed_bytes",
            "uncompressed_bytes",
            "error_code",
            "error_message",
        }
        if not fields.keys() <= allowed:
            raise ValueError("unknown job metadata column")
        assignments = ["status=?", "updated_at=CURRENT_TIMESTAMP"]
        values: list[object] = [status]
        for key, value in fields.items():
            assignments.append(f"{key}=?")
            values.append(value)
        values.append(job_id)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE jobs SET {', '.join(assignments)} WHERE job_id=?",
                values,
            )

    def active_count(self) -> int:
        """Count bounded queued and running work."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM jobs WHERE status IN ('queued', 'running')"
            ).fetchone()
        return int(row["count"])


class JobManager:
    """Deduplicating facade over a bounded worker-process pool."""

    def __init__(
        self,
        root: Path,
        *,
        git_commit: str,
        max_workers: int = 2,
        max_pending: int = 8,
        executor: Executor | None = None,
    ) -> None:
        """Create a cache rooted at an explicit service-data directory."""
        if not 1 <= max_workers <= 4:
            raise ValueError("max_workers must be between 1 and 4")
        if max_pending < max_workers:
            raise ValueError("max_pending must be at least max_workers")
        self.root = root
        self.artifacts = root / "artifacts"
        self.store = JobStore(root / "jobs.sqlite3")
        self.git_commit = git_commit
        self.max_pending = max_pending
        self.executor = executor or cast(Executor, ProcessPoolExecutor(max_workers=max_workers))
        self._futures: dict[str, Future[dict[str, object]]] = {}
        self._lock = threading.RLock()

    def submit(self, config: ModelConfig) -> JobSubmission:
        """Return a cache hit/collision or enqueue one unique bounded job."""
        job_id = cache_key(config)
        existing = self.store.get(job_id)
        if existing is not None and existing["status"] in {"queued", "running", "completed"}:
            return JobSubmission(
                job_id,
                str(existing["status"]),
                existing["status"] == "completed",
                config.configuration_hash(),
            )
        with self._lock:
            existing = self.store.get(job_id)
            if existing is not None and existing["status"] in {
                "queued",
                "running",
                "completed",
            }:
                return JobSubmission(
                    job_id,
                    str(existing["status"]),
                    existing["status"] == "completed",
                    config.configuration_hash(),
                )
            if self.store.active_count() >= self.max_pending:
                raise OverflowError("the public experiment queue is full")
            artifact_path = self.artifacts / f"{job_id}.json.gz"
            if existing is None:
                if not self.store.create(job_id, config, artifact_path):
                    return JobSubmission(job_id, "queued", False, config.configuration_hash())
            else:
                self.store.update(
                    job_id,
                    "queued",
                    error_code=None,
                    error_message=None,
                    sha256=None,
                    compressed_bytes=None,
                    uncompressed_bytes=None,
                )
            future = self.executor.submit(
                _execute_job,
                config.model_dump(mode="json"),
                str(artifact_path),
                self.git_commit,
            )
            self._futures[job_id] = future
            self.store.update(job_id, "running")
            future.add_done_callback(lambda completed: self._complete(job_id, completed))
            final = self.store.get(job_id)
        return JobSubmission(
            job_id,
            str(final["status"]) if final is not None else "running",
            False,
            config.configuration_hash(),
        )

    def _complete(self, job_id: str, future: Future[dict[str, object]]) -> None:
        try:
            metadata = future.result()
        except Exception as error:  # worker failures are an external API state
            self.store.update(
                job_id,
                "failed",
                error_code="simulation_failed",
                error_message=str(error)[:500],
            )
        else:
            self.store.update(job_id, "completed", **metadata)
        finally:
            with self._lock:
                self._futures.pop(job_id, None)

    def cancel(self, job_id: str) -> bool:
        """Cancel only work that has not started; never kill a writing worker."""
        with self._lock:
            future = self._futures.get(job_id)
            if future is None or not future.cancel():
                return False
            self._futures.pop(job_id, None)
            self.store.update(job_id, "cancelled")
            return True

    def close(self) -> None:
        """Stop accepting work and release worker processes."""
        self.executor.shutdown(wait=False, cancel_futures=True)
