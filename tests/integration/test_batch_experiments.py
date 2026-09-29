"""Reduced Monte Carlo batch gate: pairing, parallelism, resume, and summaries."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from ecodeling.config.schema import (
    ForeignSectorConfig,
    MicroSimulationConfig,
    ModelConfig,
    RealEconomyConfig,
    ShockConfig,
    ShockKind,
    SimulationConfig,
)
from ecodeling.identifiers import ScenarioId
from ecodeling.reporting.batch import (
    BatchConfig,
    SeedDesign,
    SensitivityParameter,
    SensitivitySweep,
    generate_batch,
)


def _model() -> ModelConfig:
    return ModelConfig(
        scenario_id=ScenarioId("phase-11-ci"),
        simulation=SimulationConfig(months=6, seed=1),
        micro=MicroSimulationConfig(households=10, banks=1),
        real_economy=RealEconomyConfig(firms=2, firm_cash_buffer_months=12),
        foreign_sector=ForeignSectorConfig(import_share_bps=2_000),
        shock=ShockConfig(kind=ShockKind.FX_DEPRECIATION, month=2, magnitude=0.05),
    )


def _batch(workers: int) -> BatchConfig:
    return BatchConfig(
        model=_model(),
        seeds=(41, 42),
        seed_design=SeedDesign.PAIRED,
        max_workers=workers,
        alpha_values=(0.0, 1.0),
        sensitivities=(
            SensitivitySweep(
                parameter=SensitivityParameter.CONSUMPTION_PROPENSITY,
                values=(9_000, 10_000),
            ),
        ),
    )


def _terminal_records(root: Path) -> list[dict[str, object]]:
    return [json.loads(path.read_text()) for path in sorted((root / "runs").glob("*/result.json"))]


def test_serial_parallel_pairing_resume_and_aggregation(tmp_path: Path) -> None:
    serial = generate_batch(_batch(1), tmp_path / "serial", git_commit="abc1234")
    parallel = generate_batch(_batch(2), tmp_path / "parallel", git_commit="abc1234")

    assert serial.run_count == parallel.run_count == 8
    serial_records = _terminal_records(serial.path)
    parallel_records = _terminal_records(parallel.path)
    assert serial_records == parallel_records
    assert {record["status"] for record in serial_records} == {"complete"}

    seed_groups: dict[int, set[int]] = {}
    for record in serial_records:
        seed_group = record["seed_group"]
        seed = record["seed"]
        assert isinstance(seed_group, int)
        assert isinstance(seed, int)
        seed_groups.setdefault(seed_group, set()).add(seed)
    assert seed_groups == {41: {41}, 42: {42}}

    before = {
        path: path.stat().st_mtime_ns for path in (serial.path / "runs").glob("*/result.json")
    }
    resumed = generate_batch(_batch(2), serial.path, git_commit="abc1234")
    after = {path: path.stat().st_mtime_ns for path in before}
    assert resumed.resumed_runs == 8
    assert before == after

    summary = json.loads((serial.path / "summary.json").read_text())
    assert summary["counts"] == {"complete": 8, "failed": 0, "numerically_invalid": 0}
    rows = pq.read_table(serial.path / "summary.parquet").to_pylist()
    assert rows
    assert {row["sample_size"] for row in rows} == {2}
    assert all(row["minimum"] <= row["median"] <= row["maximum"] for row in rows)
    checked = rows[0]
    raw_values = [
        float(record["metrics"][checked["metric"]])
        for record in serial_records
        if record["variant_id"] == checked["variant_id"] and isinstance(record["metrics"], dict)
    ]
    assert checked["mean"] == statistics.fmean(raw_values)
    assert checked["minimum"] == min(raw_values)
    assert checked["maximum"] == max(raw_values)
    paired_rows = pq.read_table(serial.path / "paired_differences.parquet").to_pylist()
    assert paired_rows
    assert {row["sample_size"] for row in paired_rows} == {2}


def test_independent_design_derives_unique_reproducible_seeds(tmp_path: Path) -> None:
    config = _batch(1).model_copy(update={"seed_design": SeedDesign.INDEPENDENT})
    first = generate_batch(config, tmp_path / "first", git_commit="abc1234")
    second = generate_batch(config, tmp_path / "second", git_commit="abc1234")
    first_records = _terminal_records(first.path)
    second_records = _terminal_records(second.path)

    assert first_records == second_records
    assert len({record["seed"] for record in first_records}) == len(first_records)
    assert {record["seed_group"] for record in first_records} == {None}


def test_all_required_sensitivity_axes_are_applied(tmp_path: Path) -> None:
    levels: tuple[tuple[SensitivityParameter, int | float], ...] = (
        (SensitivityParameter.SHOCK_MAGNITUDE, 0.08),
        (SensitivityParameter.INDEXATION_LAG, 0),
        (SensitivityParameter.IMPORT_SHARE, 1_500),
        (SensitivityParameter.LOAN_MATURITY, 24),
        (SensitivityParameter.PRICE_STICKINESS, 5_000),
        (SensitivityParameter.POLICY_RESPONSE, 2.0),
        (SensitivityParameter.EXPECTED_INFLATION, 300),
        (SensitivityParameter.CONSUMPTION_PROPENSITY, 9_000),
        (SensitivityParameter.DEFAULT_THRESHOLD, 4),
    )
    config = BatchConfig(
        model=_model(),
        seeds=(7,),
        alpha_values=(0.5,),
        sensitivities=tuple(
            SensitivitySweep(parameter=parameter, values=(value,)) for parameter, value in levels
        ),
    )

    generated = generate_batch(config, tmp_path / "all-axes", git_commit="abc1234")
    record = _terminal_records(generated.path)[0]
    assert record["status"] == "complete"
    assert record["parameters"] == {
        "mortgage_alpha": 0.5,
        **{parameter.value: value for parameter, value in levels},
    }
