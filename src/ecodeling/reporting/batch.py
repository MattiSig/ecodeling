"""Resumable Monte Carlo and parameter-sensitivity experiments."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from enum import StrEnum
from multiprocessing import get_context
from pathlib import Path
from typing import Annotated, Self, cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from pydantic import Field, model_validator

from ecodeling import __version__
from ecodeling.config.schema import FrozenConfigModel, ModelConfig
from ecodeling.economy import EconomySimulationResult, run_economy_simulation

BATCH_SCHEMA_VERSION = 1
_MAX_RUNS = 10_000
_TERMINAL_STATUSES = frozenset({"complete", "numerically_invalid", "failed"})


class SeedDesign(StrEnum):
    """Whether variants share random seeds or receive independent derived seeds."""

    PAIRED = "paired"
    INDEPENDENT = "independent"


class SensitivityParameter(StrEnum):
    """Allowlisted scientific assumptions supported by the v0.1 sensitivity runner."""

    SHOCK_MAGNITUDE = "shock_magnitude"
    INDEXATION_LAG = "indexation_lag_months"
    IMPORT_SHARE = "import_share_bps"
    LOAN_MATURITY = "loan_maturity_months"
    PRICE_STICKINESS = "price_adjustment_bps"
    POLICY_RESPONSE = "policy_phi_pi"
    EXPECTED_INFLATION = "expected_inflation_bps"
    CONSUMPTION_PROPENSITY = "consumption_propensity_bps"
    DEFAULT_THRESHOLD = "default_after_arrears_months"


class SensitivitySweep(FrozenConfigModel):
    """One allowlisted parameter and its explicit experiment levels."""

    parameter: SensitivityParameter
    values: Annotated[tuple[int | float, ...], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def reject_boolean_and_duplicate_values(self) -> Self:
        """Keep the experiment grid unambiguous and JSON-numeric."""
        if any(isinstance(value, bool) or not math.isfinite(float(value)) for value in self.values):
            raise ValueError("sensitivity values must be finite numbers, not booleans")
        if len({json.dumps(value) for value in self.values}) != len(self.values):
            raise ValueError("sensitivity values must be unique within an axis")
        return self


class BatchConfig(FrozenConfigModel):
    """Validated external contract for a bounded, reproducible experiment batch."""

    model: ModelConfig
    seeds: Annotated[tuple[int, ...], Field(min_length=1, max_length=1_000)]
    seed_design: SeedDesign = SeedDesign.PAIRED
    max_workers: Annotated[int, Field(ge=1, le=32)] = 1
    alpha_values: Annotated[tuple[float, ...], Field(min_length=1, max_length=101)] = (0.0, 1.0)
    sensitivities: Annotated[tuple[SensitivitySweep, ...], Field(max_length=10)] = ()

    @model_validator(mode="after")
    def validate_grid(self) -> Self:
        """Reject duplicate axes/seeds and batches beyond the declared safety bound."""
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("batch seeds must be unique")
        if any(seed < 0 or seed > 2**64 - 1 for seed in self.seeds):
            raise ValueError("batch seeds must be unsigned 64-bit integers")
        if len(set(self.alpha_values)) != len(self.alpha_values):
            raise ValueError("alpha values must be unique")
        if any(
            not math.isfinite(alpha) or alpha < 0.0 or alpha > 1.0 for alpha in self.alpha_values
        ):
            raise ValueError("alpha values must lie between zero and one")
        parameters = [sweep.parameter for sweep in self.sensitivities]
        if len(set(parameters)) != len(parameters):
            raise ValueError("each sensitivity parameter may appear only once")
        variant_count = len(self.alpha_values) * math.prod(
            len(sweep.values) for sweep in self.sensitivities
        )
        if variant_count * len(self.seeds) > _MAX_RUNS:
            raise ValueError(f"batch may contain at most {_MAX_RUNS} runs")
        return self

    def scientific_payload(self) -> dict[str, object]:
        """Return result-affecting batch inputs, excluding execution parallelism."""
        payload = self.model_dump(mode="json", exclude={"max_workers"})
        return dict(payload)

    def scientific_hash(self) -> str:
        """Identify a batch independently of serial versus parallel execution."""
        encoded = json.dumps(
            self.scientific_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class BatchOutput:
    """Location and completion counts for one generated or resumed batch."""

    path: Path
    batch_id: str
    run_count: int
    resumed_runs: int


@dataclass(frozen=True, slots=True)
class _RunTask:
    task_id: str
    variant_id: str
    seed_group: int | None
    seed: int
    parameters: dict[str, int | float]
    config_payload: dict[str, object]


def load_batch_config(path: Path) -> BatchConfig:
    """Load and validate a JSON batch experiment configuration."""
    return BatchConfig.model_validate_json(path.read_text(encoding="utf-8"))


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _variants(config: BatchConfig) -> list[tuple[str, dict[str, int | float]]]:
    axes: list[tuple[str, tuple[int | float, ...]]] = [
        ("mortgage_alpha", tuple(config.alpha_values))
    ]
    axes.extend((sweep.parameter.value, sweep.values) for sweep in config.sensitivities)
    variants: list[tuple[str, dict[str, int | float]]] = []
    for values in itertools.product(*(values for _, values in axes)):
        parameters = dict(zip((name for name, _ in axes), values, strict=True))
        variant_id = _canonical_hash(parameters)[:16]
        variants.append((variant_id, parameters))
    return variants


def _derived_seed(base_seed: int, variant_id: str) -> int:
    payload = f"ecodeling-independent-seed-v1:{base_seed}:{variant_id}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _nested_set(payload: dict[str, object], section: str, field: str, value: object) -> None:
    nested = payload[section]
    if not isinstance(nested, dict):
        raise TypeError(f"expected configuration section {section!r} to be an object")
    nested[field] = value


def _configured_model(
    base: ModelConfig,
    *,
    variant_id: str,
    seed: int,
    parameters: dict[str, int | float],
) -> ModelConfig:
    payload = base.model_dump(mode="json")
    payload["scenario_id"] = f"{base.scenario_id}-batch-{variant_id}"
    _nested_set(payload, "simulation", "seed", seed)
    paths = {
        "mortgage_alpha": ("indexation", "mortgage_alpha"),
        SensitivityParameter.SHOCK_MAGNITUDE.value: ("shock", "magnitude"),
        SensitivityParameter.INDEXATION_LAG.value: ("indexation", "lag_months"),
        SensitivityParameter.IMPORT_SHARE.value: ("foreign_sector", "import_share_bps"),
        SensitivityParameter.LOAN_MATURITY.value: ("micro", "mortgage_term_months"),
        SensitivityParameter.PRICE_STICKINESS.value: ("real_economy", "price_adjustment_bps"),
        SensitivityParameter.POLICY_RESPONSE.value: ("monetary_policy", "phi_pi"),
        SensitivityParameter.EXPECTED_INFLATION.value: ("micro", "expected_inflation_bps"),
        SensitivityParameter.CONSUMPTION_PROPENSITY.value: (
            "real_economy",
            "consumption_propensity_bps",
        ),
        SensitivityParameter.DEFAULT_THRESHOLD.value: (
            "micro",
            "default_after_arrears_months",
        ),
    }
    integer_parameters = {
        SensitivityParameter.INDEXATION_LAG.value,
        SensitivityParameter.IMPORT_SHARE.value,
        SensitivityParameter.LOAN_MATURITY.value,
        SensitivityParameter.PRICE_STICKINESS.value,
        SensitivityParameter.EXPECTED_INFLATION.value,
        SensitivityParameter.CONSUMPTION_PROPENSITY.value,
        SensitivityParameter.DEFAULT_THRESHOLD.value,
    }
    for name, value in parameters.items():
        if name in integer_parameters and (isinstance(value, float) and not value.is_integer()):
            raise ValueError(f"{name} requires an integer sensitivity value")
        section, field = paths[name]
        _nested_set(payload, section, field, int(value) if name in integer_parameters else value)
    return ModelConfig.model_validate(payload)


def _tasks(config: BatchConfig) -> list[_RunTask]:
    tasks: list[_RunTask] = []
    seen_seeds: set[int] = set()
    for variant_id, parameters in _variants(config):
        for base_seed in config.seeds:
            seed = (
                base_seed
                if config.seed_design is SeedDesign.PAIRED
                else _derived_seed(base_seed, variant_id)
            )
            if config.seed_design is SeedDesign.INDEPENDENT and seed in seen_seeds:
                raise AssertionError("independent seed derivation collision")
            seen_seeds.add(seed)
            model = _configured_model(
                config.model,
                variant_id=variant_id,
                seed=seed,
                parameters=parameters,
            )
            identity = {
                "variant_id": variant_id,
                "seed_group": base_seed if config.seed_design is SeedDesign.PAIRED else None,
                "seed": seed,
                "configuration_hash": model.configuration_hash(),
            }
            tasks.append(
                _RunTask(
                    task_id=_canonical_hash(identity)[:24],
                    variant_id=variant_id,
                    seed_group=base_seed if config.seed_design is SeedDesign.PAIRED else None,
                    seed=seed,
                    parameters=parameters,
                    config_payload=model.model_dump(mode="json"),
                )
            )
    return sorted(tasks, key=lambda task: task.task_id)


def _invalidity_reasons(result: EconomySimulationResult) -> list[str]:
    aggregate_months = result.aggregate_months
    reasons: list[str] = []
    for row in aggregate_months:
        for field in ("cpi_level", "bank_mortgage_assets", "bank_equity"):
            value = getattr(row, field)
            if isinstance(value, float) and not math.isfinite(value):
                reasons.append(f"non_finite:{field}:{row.month}")
        if row.cpi_level <= 0:
            reasons.append(f"non_positive:cpi_level:{row.month}")
        if row.bank_mortgage_assets < 0:
            reasons.append(f"negative:bank_mortgage_assets:{row.month}")
    return reasons


def _run_task(task: _RunTask) -> dict[str, object]:
    base: dict[str, object] = {
        "batch_schema_version": BATCH_SCHEMA_VERSION,
        "task_id": task.task_id,
        "variant_id": task.variant_id,
        "seed_group": task.seed_group,
        "seed": task.seed,
        "parameters": task.parameters,
    }
    try:
        config = ModelConfig.model_validate(task.config_payload)
        result = run_economy_simulation(config)
        reasons = _invalidity_reasons(result)
        if reasons:
            return {**base, "status": "numerically_invalid", "invalidity_reasons": reasons}
        final = result.aggregate_months[-1]
        metrics: dict[str, int | float] = {
            "final_cpi_level": final.cpi_level,
            "final_mortgage_principal_isk": final.total_mortgage_principal,
            "final_debt_service_isk": final.debt_service,
            "final_bank_equity_isk": final.bank_equity,
            "cumulative_consumption_isk": sum(
                row.household_consumption for row in result.aggregate_months
            ),
            "cumulative_defaults": sum(row.defaults for row in result.aggregate_months),
            "cumulative_mortgage_revaluation_isk": sum(
                row.indexation_revaluation for row in result.aggregate_months
            ),
            "peak_monthly_inflation_bps": max(
                row.monthly_inflation_bps for row in result.aggregate_months
            ),
            "peak_policy_rate_bps": max(row.policy_rate_bps for row in result.aggregate_months),
        }
        return {
            **base,
            "status": "complete",
            "configuration_hash": config.configuration_hash(),
            "run_id": str(result.run_id),
            "metrics": metrics,
        }
    except ArithmeticError as exc:
        return {
            **base,
            "status": "numerically_invalid",
            "invalidity_reasons": [f"{type(exc).__name__}:{exc}"],
        }
    except Exception as exc:  # a failed run is data; the batch must finish and report it
        return {
            **base,
            "status": "failed",
            "failure_type": type(exc).__name__,
            "failure_reason": str(exc),
        }


def _atomic_json_write(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _summary_rows(records: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[float]] = {}
    parameters: dict[str, dict[str, int | float]] = {}
    for record in records:
        if record["status"] != "complete":
            continue
        variant_id = str(record["variant_id"])
        parameters[variant_id] = dict(cast(dict[str, int | float], record["parameters"]))
        metrics = record["metrics"]
        if not isinstance(metrics, dict):
            raise TypeError("complete run record has invalid metrics")
        for metric, value in metrics.items():
            groups.setdefault((variant_id, metric), []).append(float(value))
    rows: list[dict[str, object]] = []
    for (variant_id, metric), values in sorted(groups.items()):
        rows.append(
            {
                "variant_id": variant_id,
                "parameters_json": json.dumps(parameters[variant_id], sort_keys=True),
                "metric": metric,
                **_distribution(values),
            }
        )
    return rows


def _distribution(values: list[float]) -> dict[str, int | float]:
    count = len(values)
    mean = statistics.fmean(values)
    standard_deviation = statistics.stdev(values) if count > 1 else 0.0
    standard_error = standard_deviation / math.sqrt(count)
    return {
        "sample_size": count,
        "mean": mean,
        "standard_deviation": standard_deviation,
        "standard_error": standard_error,
        "confidence_95_low": mean - 1.96 * standard_error,
        "confidence_95_high": mean + 1.96 * standard_error,
        "minimum": min(values),
        "p05": _quantile(values, 0.05),
        "median": statistics.median(values),
        "p95": _quantile(values, 0.95),
        "maximum": max(values),
    }


def _paired_summary_rows(
    records: list[dict[str, object]], reference_variant_id: str | None
) -> list[dict[str, object]]:
    if reference_variant_id is None:
        return []
    complete: dict[tuple[str, int], dict[str, int | float]] = {}
    variants: set[str] = set()
    for record in records:
        if record["status"] != "complete" or not isinstance(record["seed_group"], int):
            continue
        variant_id = str(record["variant_id"])
        metrics = record["metrics"]
        if not isinstance(metrics, dict):
            raise TypeError("complete run record has invalid metrics")
        complete[(variant_id, record["seed_group"])] = cast(dict[str, int | float], metrics)
        variants.add(variant_id)
    reference_seeds = {
        seed_group for variant_id, seed_group in complete if variant_id == reference_variant_id
    }
    rows: list[dict[str, object]] = []
    for variant_id in sorted(variants - {reference_variant_id}):
        paired_seeds = sorted(
            reference_seeds
            & {seed_group for candidate, seed_group in complete if candidate == variant_id}
        )
        if not paired_seeds:
            continue
        metric_names = sorted(complete[(reference_variant_id, paired_seeds[0])])
        for metric in metric_names:
            differences = [
                float(complete[(variant_id, seed_group)][metric])
                - float(complete[(reference_variant_id, seed_group)][metric])
                for seed_group in paired_seeds
            ]
            rows.append(
                {
                    "reference_variant_id": reference_variant_id,
                    "variant_id": variant_id,
                    "metric": metric,
                    **_distribution(differences),
                }
            )
    return rows


def _parquet_summary_write(path: Path, rows: list[dict[str, object]], manifest: object) -> None:
    table = pa.Table.from_pylist(rows)
    metadata = dict(table.schema.metadata or {})
    metadata[b"ecodeling"] = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    pq.write_table(table.replace_schema_metadata(metadata), path, compression="zstd")


def _write_summaries(
    root: Path,
    records: list[dict[str, object]],
    manifest: object,
    reference_variant_id: str | None,
) -> None:
    counts = {
        status: sum(record["status"] == status for record in records)
        for status in ("complete", "failed", "numerically_invalid")
    }
    invalidity_reasons: dict[str, int] = {}
    failure_reasons: dict[str, int] = {}
    for record in records:
        for reason in cast(list[object], record.get("invalidity_reasons", [])):
            text = str(reason)
            invalidity_reasons[text] = invalidity_reasons.get(text, 0) + 1
        if record["status"] == "failed":
            text = f"{record.get('failure_type')}:{record.get('failure_reason')}"
            failure_reasons[text] = failure_reasons.get(text, 0) + 1
    rows = _summary_rows(records)
    paired_rows = _paired_summary_rows(records, reference_variant_id)
    _atomic_json_write(
        root / "summary.json",
        {
            "counts": counts,
            "failure_reasons": failure_reasons,
            "invalidity_reasons": invalidity_reasons,
            "distributions": rows,
            "paired_differences": paired_rows,
        },
    )
    if rows:
        _parquet_summary_write(root / "summary.parquet", rows, manifest)
    if paired_rows:
        _parquet_summary_write(root / "paired_differences.parquet", paired_rows, manifest)


def generate_batch(config: BatchConfig, output: Path, *, git_commit: str) -> BatchOutput:
    """Execute or resume a bounded batch and regenerate derived distributions."""
    batch_hash = config.scientific_hash()
    batch_id = f"batch-{batch_hash[:16]}"
    reference_variant_id = (
        _variants(config)[0][0] if config.seed_design is SeedDesign.PAIRED else None
    )
    manifest = {
        "batch_schema_version": BATCH_SCHEMA_VERSION,
        "batch_id": batch_id,
        "scientific_hash": batch_hash,
        "model_version": __version__,
        "git_commit": git_commit,
        "seed_design": config.seed_design.value,
        "paired_reference_variant_id": reference_variant_id,
        "scientific_configuration": config.scientific_payload(),
        "validation_statement": {
            "calibration_status": "stylized",
            "exercise": "mechanism-based, not empirically calibrated",
            "major_omitted_channels": [
                "endogenous exchange-rate market",
                "housing transactions",
                "rent and wage indexation",
            ],
            "sensitivity_checks": [
                "mortgage_alpha",
                *[sweep.parameter.value for sweep in config.sensitivities],
            ],
        },
    }
    manifest_path = output / "manifest.json"
    if output.exists() and any(output.iterdir()):
        entries = {path.name for path in output.iterdir()}
        if not manifest_path.is_file() and entries == {".manifest.json.tmp"}:
            _atomic_json_write(manifest_path, manifest)
        elif not manifest_path.is_file():
            raise FileExistsError(f"non-empty batch output has no manifest: {output}")
        else:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if existing != manifest:
                raise ValueError(
                    "existing batch manifest does not match configuration and source commit"
                )
    else:
        output.mkdir(parents=True, exist_ok=True)
        _atomic_json_write(manifest_path, manifest)
    runs_path = output / "runs"
    runs_path.mkdir(exist_ok=True)

    tasks = _tasks(config)
    records: dict[str, dict[str, object]] = {}
    pending: list[_RunTask] = []
    resumed = 0
    for task in tasks:
        result_path = runs_path / task.task_id / "result.json"
        if result_path.is_file():
            record = json.loads(result_path.read_text(encoding="utf-8"))
            if record.get("task_id") == task.task_id and record.get("status") in _TERMINAL_STATUSES:
                records[task.task_id] = record
                resumed += 1
                continue
        pending.append(task)

    def store(task: _RunTask, record: dict[str, object]) -> None:
        run_path = runs_path / task.task_id
        run_path.mkdir(exist_ok=True)
        _atomic_json_write(run_path / "result.json", record)
        records[task.task_id] = record

    if config.max_workers == 1:
        for task in pending:
            store(task, _run_task(task))
    elif pending:
        with ProcessPoolExecutor(
            max_workers=config.max_workers, mp_context=get_context("spawn")
        ) as executor:
            futures = {executor.submit(_run_task, task): task for task in pending}
            for future in as_completed(futures):
                task = futures[future]
                try:
                    record = future.result()
                except Exception as exc:
                    record = {
                        "batch_schema_version": BATCH_SCHEMA_VERSION,
                        "task_id": task.task_id,
                        "variant_id": task.variant_id,
                        "seed_group": task.seed_group,
                        "seed": task.seed,
                        "parameters": task.parameters,
                        "status": "failed",
                        "failure_type": type(exc).__name__,
                        "failure_reason": str(exc),
                    }
                store(task, record)

    ordered_records = [records[task.task_id] for task in tasks]
    _write_summaries(output, ordered_records, manifest, reference_variant_id)
    return BatchOutput(output, batch_id, len(tasks), resumed)
