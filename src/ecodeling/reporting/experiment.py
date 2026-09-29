"""Reproducible analytical outputs for controlled Ecodeling experiments."""

from __future__ import annotations

import json
import math
import statistics
import subprocess
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from ecodeling import __version__
from ecodeling.config.schema import IndexationConfig, ModelConfig, ShockConfig, ShockKind
from ecodeling.economy import EconomySimulationResult, run_economy_simulation
from ecodeling.economy.outputs import HouseholdEconomyMonthlyOutput
from ecodeling.identifiers import AgentId, ScenarioId

REPORT_SCHEMA_VERSION = 1
_BPS = 10_000


@dataclass(frozen=True, slots=True)
class OutputSet:
    """Location and identity of one completed analytical output set."""

    path: Path
    experiment_id: str
    run_count: int


def current_git_commit() -> str:
    """Resolve the source revision attached to a generated output set."""
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def load_config(path: Path) -> ModelConfig:
    """Load and validate a JSON model configuration."""
    return ModelConfig.model_validate_json(path.read_text(encoding="utf-8"))


def _json_write(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, default=str, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"expected a numeric reporting value, got {value!r}")
    return float(value)


def _prepare_output(path: Path) -> None:
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise FileExistsError(f"output path must not already contain files: {path}")
    else:
        path.mkdir(parents=True)


def _parquet_write(path: Path, rows: Sequence[Mapping[str, object]], metadata: object) -> None:
    if not rows:
        raise ValueError(f"cannot write empty analytical table: {path.name}")
    table = pa.Table.from_pylist(list(rows))
    schema_metadata = dict(table.schema.metadata or {})
    schema_metadata[b"ecodeling"] = json.dumps(
        metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    pq.write_table(table.replace_schema_metadata(schema_metadata), path, compression="zstd")


def _shock_payload(config: ModelConfig) -> dict[str, object]:
    return config.shock.model_dump(mode="json")


def _topology_payload(config: ModelConfig) -> dict[str, object]:
    return {
        "mortgage_alpha": config.indexation.mortgage_alpha,
        "wage_alpha": 0.0,
        "rent_alpha": 0.0,
        "benefit_alpha": 0.0,
        "bank_funding_alpha": 0.0,
    }


def _run_metadata(
    result: EconomySimulationResult,
    config: ModelConfig,
    *,
    git_commit: str,
    role: str,
    experiment_id: str,
) -> dict[str, object]:
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "role": role,
        "run_id": str(result.run_id),
        "model_version": __version__,
        "git_commit": git_commit,
        "scenario_id": str(result.scenario_id),
        "seed": result.seed,
        "configuration_hash": result.configuration_hash,
        "parameter_set": "embedded:parameters.json",
        "start_month": str(config.simulation.start_month),
        "months": config.simulation.months,
        "shock_definition": _shock_payload(config),
        "indexation_topology": _topology_payload(config),
        "units": {
            "money": "nominal whole ISK",
            "rates": "annual basis points unless named monthly",
            "price_indices": "100000 at base",
            "real_activity": "physical consumption/production units",
            "ratios": "unitless; debt-to-income uses annualized current monthly income",
        },
    }


def _household_lookup(
    result: EconomySimulationResult,
) -> dict[tuple[str, str], HouseholdEconomyMonthlyOutput]:
    return {(str(row.month), str(row.household_id)): row for row in result.household_months}


def _household_classifications(
    result: EconomySimulationResult, config: ModelConfig
) -> dict[AgentId, dict[str, str]]:
    first_month = str(result.aggregate_months[0].month)
    lookup = _household_lookup(result)
    income_order = sorted(
        result.households,
        key=lambda household: (
            lookup[(first_month, str(household.id))].wage_income,
            str(household.id),
        ),
    )
    quintile_by_id = {
        household.id: min(5, (rank * 5 // len(income_order)) + 1)
        for rank, household in enumerate(income_order)
    }
    classifications: dict[AgentId, dict[str, str]] = {}
    for household in result.households:
        if household.mortgage_id is not None:
            ltv_bps = household.opening_mortgage * _BPS // household.house_value
            ltv = "low" if ltv_bps < 6_500 else "middle" if ltv_bps < 8_000 else "high"
            status = "mortgaged_homeowner"
        elif household.house_value:
            ltv = "debt_free"
            status = "debt_free_homeowner"
        else:
            ltv = "not_applicable"
            status = "renter"
        liquidity_months = household.opening_deposits / config.real_economy.monthly_wage_isk
        liquidity = "low" if liquidity_months < 1 else "middle" if liquidity_months < 3 else "high"
        classifications[household.id] = {
            "income_quintile": f"q{quintile_by_id[household.id]}",
            "homeowner_status": status,
            "mortgage_regime": (
                "no_mortgage"
                if household.mortgage_id is None
                else "indexed"
                if config.indexation.mortgage_alpha == 1.0
                else "nominal"
                if config.indexation.mortgage_alpha == 0.0
                else "partially_indexed"
            ),
            "initial_ltv_group": ltv,
            "opening_liquidity_group": liquidity,
        }
    return classifications


def _credit_losses_by_month(result: EconomySimulationResult) -> dict[str, int]:
    """Read exact clearing-bank default losses from authoritative ledger postings."""
    return {
        str(entry.month): -next(
            posting.amount
            for posting in entry.postings
            if str(posting.account_id) == "economy-clearing-bank:equity"
        )
        for entry in result.ledger.entries
        if str(entry.id).endswith(":defaults")
    }


def _derived_month_rows(
    result: EconomySimulationResult,
    config: ModelConfig,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    households_by_month: dict[str, list[HouseholdEconomyMonthlyOutput]] = defaultdict(list)
    for row in result.household_months:
        households_by_month[str(row.month)].append(row)
    opening = {household.id: household for household in result.households}
    classifications = _household_classifications(result, config)
    credit_losses = _credit_losses_by_month(result)
    aggregate_rows: list[dict[str, object]] = []
    cohort_rows: list[dict[str, object]] = []
    bank_rows: list[dict[str, object]] = []
    for aggregate in result.aggregate_months:
        month_rows = households_by_month[str(aggregate.month)]
        principals = [
            row.closing_mortgage_principal
            for row in month_rows
            if opening[row.household_id].mortgage_id is not None
        ]
        total_income = sum(row.wage_income for row in month_rows)
        total_deposits = sum(row.closing_deposits for row in month_rows)
        total_house_value = sum(opening[row.household_id].house_value for row in month_rows)
        total_net_worth = total_deposits + total_house_value - aggregate.total_mortgage_principal
        losses = credit_losses.get(str(aggregate.month), 0)
        aggregate_row: dict[str, object] = asdict(aggregate)
        aggregate_row["month"] = str(aggregate.month)
        aggregate_row.update(
            {
                "average_mortgage_principal_isk": round(statistics.fmean(principals))
                if principals
                else 0,
                "median_mortgage_principal_isk": round(statistics.median(principals))
                if principals
                else 0,
                "aggregate_real_consumption_units": aggregate.sales_units,
                "household_deposits_isk": total_deposits,
                "household_net_worth_isk": total_net_worth,
                "debt_service_to_income": aggregate.debt_service / total_income
                if total_income
                else None,
                "debt_to_income": aggregate.total_mortgage_principal / (total_income * 12)
                if total_income
                else None,
                "loan_to_value": aggregate.total_mortgage_principal / total_house_value
                if total_house_value
                else None,
                "default_rate": aggregate.defaults / len(month_rows),
            }
        )
        aggregate_rows.append(aggregate_row)
        alpha_bps = round(config.indexation.mortgage_alpha * _BPS)
        indexed_assets = aggregate.bank_mortgage_assets * alpha_bps // _BPS
        bank_rows.append(
            {
                "month": str(aggregate.month),
                "bank_id": "economy-clearing-bank",
                "total_loans_isk": aggregate.bank_mortgage_assets,
                "indexed_assets_isk": indexed_assets,
                "nominal_assets_isk": aggregate.bank_mortgage_assets - indexed_assets,
                "net_indexed_position_isk": indexed_assets,
                "equity_isk": aggregate.bank_equity,
                "capital_ratio": (
                    aggregate.bank_equity / aggregate.bank_mortgage_assets
                    if aggregate.bank_mortgage_assets
                    else None
                ),
                "interest_income_isk": aggregate.mortgage_interest,
                "credit_losses_isk": losses,
                "loan_origination_isk": 0,
            }
        )
        for dimension in classifications[next(iter(classifications))]:
            values = sorted({labels[dimension] for labels in classifications.values()})
            for value in values:
                members = [
                    output
                    for output in month_rows
                    if classifications[output.household_id][dimension] == value
                ]
                cohort_income = sum(member.wage_income for member in members)
                cohort_principal = sum(member.closing_mortgage_principal for member in members)
                cohort_deposits = sum(member.closing_deposits for member in members)
                cohort_house_value = sum(
                    opening[member.household_id].house_value for member in members
                )
                cohort_rows.append(
                    {
                        "month": str(aggregate.month),
                        "cohort_dimension": dimension,
                        "cohort": value,
                        "households": len(members),
                        "income_isk": cohort_income,
                        "consumption_isk": sum(
                            member.consumption_expenditure for member in members
                        ),
                        "mortgage_principal_isk": cohort_principal,
                        "debt_service_isk": sum(
                            member.actual_mortgage_payment for member in members
                        ),
                        "mortgage_revaluation_isk": sum(
                            member.mortgage_revaluation for member in members
                        ),
                        "deposits_isk": cohort_deposits,
                        "net_worth_isk": cohort_deposits + cohort_house_value - cohort_principal,
                        "defaults": sum(member.defaulted for member in members),
                        "debt_service_to_income": (
                            sum(member.actual_mortgage_payment for member in members)
                            / cohort_income
                            if cohort_income
                            else None
                        ),
                    }
                )
    return aggregate_rows, cohort_rows, bank_rows


def _event_summary(result: EconomySimulationResult) -> dict[str, object]:
    credit_losses = _credit_losses_by_month(result)
    return {
        "shock_events": [asdict(event) for event in result.shock_events],
        "policy_decisions": [asdict(event) for event in result.policy_events],
        "rate_resets": [asdict(event) for event in result.rate_reset_events],
        "feedback": {
            "event_count": len(result.feedback_events),
            "total_mortgage_revaluation_isk": sum(
                event.mortgage_revaluation for event in result.feedback_events
            ),
            "total_actual_debt_service_isk": sum(
                event.actual_debt_service for event in result.feedback_events
            ),
            "total_defaults": sum(event.defaults for event in result.feedback_events),
        },
        "defaults": {
            "households": sum(month.defaults for month in result.aggregate_months),
            "credit_losses_isk": sum(credit_losses.values()),
        },
    }


def _write_run(
    root: Path,
    role: str,
    result: EconomySimulationResult,
    config: ModelConfig,
    *,
    git_commit: str,
    experiment_id: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    run_path = root / "runs" / role
    run_path.mkdir(parents=True)
    metadata = _run_metadata(
        result, config, git_commit=git_commit, role=role, experiment_id=experiment_id
    )
    aggregates, cohorts, banks = _derived_month_rows(result, config)
    _json_write(run_path / "metadata.json", metadata)
    _json_write(
        run_path / "parameters.json",
        {"metadata": "metadata.json", "parameters": config.model_dump(mode="json")},
    )
    _json_write(
        run_path / "events.json",
        {"metadata": "metadata.json", "summary": _event_summary(result)},
    )
    _parquet_write(run_path / "aggregates.parquet", aggregates, metadata)
    _parquet_write(run_path / "cohorts.parquet", cohorts, metadata)
    _parquet_write(run_path / "banks.parquet", banks, metadata)
    return aggregates, cohorts


def _config_for(
    config: ModelConfig,
    *,
    role: str,
    alpha: float | None = None,
    baseline: bool = False,
) -> ModelConfig:
    updates: dict[str, object] = {"scenario_id": ScenarioId(f"{config.scenario_id}-{role}")}
    if alpha is not None:
        updates["indexation"] = IndexationConfig(
            mortgage_alpha=alpha,
            lag_months=config.indexation.lag_months,
        )
    if baseline:
        updates["shock"] = ShockConfig()
    return config.model_copy(update=updates)


def _experiment_manifest(
    config: ModelConfig,
    *,
    git_commit: str,
    experiment_id: str,
    kind: str,
    roles: Iterable[str],
) -> dict[str, object]:
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "kind": kind,
        "model_version": __version__,
        "git_commit": git_commit,
        "scenario_id": str(config.scenario_id),
        "seed": config.simulation.seed,
        "shock_definition": _shock_payload(config),
        "indexation_topology": _topology_payload(config),
        "roles": list(roles),
    }


def generate_single_run(config: ModelConfig, output: Path, *, git_commit: str) -> OutputSet:
    """Run one validated configuration and persist its analytical outputs."""
    _prepare_output(output)
    experiment_id = f"single-{config.configuration_hash()[:16]}"
    result = run_economy_simulation(config)
    _write_run(output, "run", result, config, git_commit=git_commit, experiment_id=experiment_id)
    manifest = _experiment_manifest(
        config,
        git_commit=git_commit,
        experiment_id=experiment_id,
        kind="single_run",
        roles=("run",),
    )
    _json_write(output / "manifest.json", manifest)
    return OutputSet(output, experiment_id, 1)


def generate_shock_pair(config: ModelConfig, output: Path, *, git_commit: str) -> OutputSet:
    """Run one regime against its own no-shock counterfactual."""
    if config.shock.kind is ShockKind.NONE:
        raise ValueError("shock-pair requires an active shock in the configuration")
    _prepare_output(output)
    experiment_id = f"shock-pair-{config.configuration_hash()[:16]}"
    configs = {
        "baseline": _config_for(config, role="baseline", baseline=True),
        "shock": _config_for(config, role="shock"),
    }
    rows: dict[str, list[dict[str, object]]] = {}
    results: dict[str, EconomySimulationResult] = {}
    for role, run_config in configs.items():
        result = run_economy_simulation(run_config)
        results[role] = result
        rows[role], _ = _write_run(
            output,
            role,
            result,
            run_config,
            git_commit=git_commit,
            experiment_id=experiment_id,
        )
    if results["baseline"].households != results["shock"].households:
        raise AssertionError("shock run does not share baseline household initialization")
    if results["baseline"].firms != results["shock"].firms:
        raise AssertionError("shock run does not share baseline firm initialization")
    irfs = _irf_rows({"regime": (rows["baseline"], rows["shock"])})
    metadata = _experiment_manifest(
        config,
        git_commit=git_commit,
        experiment_id=experiment_id,
        kind="baseline_shock_pair",
        roles=configs,
    )
    _parquet_write(output / "impulse_responses.parquet", irfs, metadata)
    _json_write(output / "manifest.json", metadata)
    return OutputSet(output, experiment_id, 2)


def _irf_rows(
    pairs: Mapping[str, tuple[Sequence[Mapping[str, object]], Sequence[Mapping[str, object]]]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for regime, (baseline, shock) in pairs.items():
        for baseline_row, shock_row in zip(baseline, shock, strict=True):
            if baseline_row["month"] != shock_row["month"]:
                raise AssertionError(f"{regime} baseline and shock timelines are not aligned")
            for metric, shock_value in shock_row.items():
                baseline_value = baseline_row.get(metric)
                if (
                    metric != "month"
                    and isinstance(shock_value, (int, float))
                    and not isinstance(shock_value, bool)
                    and isinstance(baseline_value, (int, float))
                    and not isinstance(baseline_value, bool)
                ):
                    output.append(
                        {
                            "month": shock_row["month"],
                            "regime": regime,
                            "metric": metric,
                            "baseline": baseline_value,
                            "shock": shock_value,
                            "response": shock_value - baseline_value,
                        }
                    )
    return output


def _svg_chart(
    path: Path,
    *,
    title: str,
    subtitle: str,
    y_label: str,
    series: Mapping[str, Sequence[float]],
    months: Sequence[str],
) -> None:
    width, height = 960, 540
    left, right, top, bottom = 92, 28, 78, 68
    plot_width, plot_height = width - left - right, height - top - bottom
    values = [value for values in series.values() for value in values if math.isfinite(value)]
    minimum, maximum = (min(values), max(values)) if values else (0.0, 1.0)
    if minimum == maximum:
        padding = max(1.0, abs(minimum) * 0.1)
        minimum -= padding
        maximum += padding
    padding = (maximum - minimum) * 0.08
    minimum -= padding
    maximum += padding
    colors = ("#006d77", "#d1495b", "#edae49", "#4c78a8")

    def x(index: int) -> float:
        return left + (plot_width * index / max(1, len(months) - 1))

    def y(value: float) -> float:
        return top + plot_height * (maximum - value) / (maximum - minimum)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fffdf7"/>',
        f'<text x="{left}" y="34" font-family="system-ui,sans-serif" font-size="24" font-weight="700" fill="#172121">{escape(title)}</text>',
        f'<text x="{left}" y="58" font-family="system-ui,sans-serif" font-size="13" fill="#52616b">{escape(subtitle)}</text>',
    ]
    for tick in range(5):
        value = minimum + (maximum - minimum) * tick / 4
        tick_y = y(value)
        lines.extend(
            [
                f'<line x1="{left}" y1="{tick_y:.2f}" x2="{width - right}" y2="{tick_y:.2f}" stroke="#d7ddd9"/>',
                f'<text x="{left - 10}" y="{tick_y + 4:.2f}" text-anchor="end" font-family="system-ui,sans-serif" font-size="11" fill="#52616b">{value:,.2f}</text>',
            ]
        )
    for index, (name, points) in enumerate(series.items()):
        path_points = " ".join(
            f"{'M' if point_index == 0 else 'L'} {x(point_index):.2f} {y(value):.2f}"
            for point_index, value in enumerate(points)
        )
        color = colors[index % len(colors)]
        lines.append(f'<path d="{path_points}" fill="none" stroke="{color}" stroke-width="3"/>')
        legend_x = left + index * 190
        lines.extend(
            [
                f'<line x1="{legend_x}" y1="{height - 25}" x2="{legend_x + 24}" y2="{height - 25}" stroke="{color}" stroke-width="3"/>',
                f'<text x="{legend_x + 31}" y="{height - 20}" font-family="system-ui,sans-serif" font-size="12" fill="#172121">{escape(name)}</text>',
            ]
        )
    lines.extend(
        [
            f'<text x="{left}" y="{height - bottom + 28}" font-family="system-ui,sans-serif" font-size="11" fill="#52616b">{escape(months[0])}</text>',
            f'<text x="{width - right}" y="{height - bottom + 28}" text-anchor="end" font-family="system-ui,sans-serif" font-size="11" fill="#52616b">{escape(months[-1])}</text>',
            f'<text transform="translate(22 {top + plot_height / 2}) rotate(-90)" text-anchor="middle" font-family="system-ui,sans-serif" font-size="12" fill="#52616b">{escape(y_label)}</text>',
            "</svg>",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_figures(
    root: Path,
    irfs: Sequence[Mapping[str, object]],
    cohorts: Mapping[str, Sequence[Mapping[str, object]]],
) -> None:
    figure_path = root / "figures"
    figure_path.mkdir()
    metrics = (
        ("monthly_inflation_bps", "01-inflation.svg", "Inflation response", "monthly basis points"),
        (
            "total_mortgage_principal",
            "02-mortgage-principal.svg",
            "Mortgage principal response",
            "ISK",
        ),
        ("debt_service", "03-debt-service.svg", "Debt-service response", "ISK / month"),
        ("household_consumption", "04-consumption.svg", "Consumption response", "ISK / month"),
        ("defaults", "05-defaults.svg", "Default response", "households / month"),
        ("bank_equity", "06-bank-equity.svg", "Bank-equity response", "ISK"),
    )
    for metric, filename, title, unit in metrics:
        selected = [row for row in irfs if row["metric"] == metric]
        regimes = sorted({str(row["regime"]) for row in selected})
        chart_months = [str(row["month"]) for row in selected if row["regime"] == regimes[0]]
        series = {
            regime: [_number(row["response"]) for row in selected if row["regime"] == regime]
            for regime in regimes
        }
        _svg_chart(
            figure_path / filename,
            title=title,
            subtitle="Shock minus the same regime's no-shock counterfactual",
            y_label=unit,
            series=series,
            months=chart_months,
        )
    distribution_series: dict[str, list[float]] = {}
    months: list[str] = []
    for regime in ("nominal", "indexed"):
        baseline_rows = cohorts[f"{regime}-baseline"]
        shock_rows = cohorts[f"{regime}-shock"]
        for cohort in ("q1", "q5"):
            baseline = [
                row
                for row in baseline_rows
                if row["cohort_dimension"] == "income_quintile" and row["cohort"] == cohort
            ]
            shock = [
                row
                for row in shock_rows
                if row["cohort_dimension"] == "income_quintile" and row["cohort"] == cohort
            ]
            if not months:
                months = [str(row["month"]) for row in shock]
            distribution_series[f"{regime} · {cohort}"] = [
                _number(shock_row["consumption_isk"]) - _number(baseline_row["consumption_isk"])
                for baseline_row, shock_row in zip(baseline, shock, strict=True)
            ]
    _svg_chart(
        figure_path / "07-distributional-consumption.svg",
        title="Distributional consumption response",
        subtitle="Bottom and top initial reporting-month income quintiles; shock minus baseline",
        y_label="ISK / month",
        series=distribution_series,
        months=months,
    )


def generate_regime_comparison(
    config: ModelConfig,
    output: Path,
    *,
    git_commit: str,
) -> OutputSet:
    """Generate a complete nominal/indexed experiment with regime-specific baselines."""
    if config.shock.kind is ShockKind.NONE:
        raise ValueError("compare requires an active shock in the configuration")
    _prepare_output(output)
    experiment_id = f"comparison-{config.configuration_hash()[:16]}"
    configs = {
        "nominal-baseline": _config_for(config, role="nominal-baseline", alpha=0.0, baseline=True),
        "nominal-shock": _config_for(config, role="nominal-shock", alpha=0.0),
        "indexed-baseline": _config_for(config, role="indexed-baseline", alpha=1.0, baseline=True),
        "indexed-shock": _config_for(config, role="indexed-shock", alpha=1.0),
    }
    aggregates: dict[str, list[dict[str, object]]] = {}
    cohorts: dict[str, list[dict[str, object]]] = {}
    results: dict[str, EconomySimulationResult] = {}
    for role, run_config in configs.items():
        result = run_economy_simulation(run_config)
        results[role] = result
        aggregates[role], cohorts[role] = _write_run(
            output,
            role,
            result,
            run_config,
            git_commit=git_commit,
            experiment_id=experiment_id,
        )
    for baseline_role, shock_role in (
        ("nominal-baseline", "nominal-shock"),
        ("indexed-baseline", "indexed-shock"),
    ):
        if results[baseline_role].households != results[shock_role].households:
            raise AssertionError(f"{shock_role} does not share baseline initialization")
    if results["nominal-shock"].households != results["indexed-shock"].households:
        raise AssertionError("nominal and indexed regimes do not share initialization")
    if results["nominal-shock"].shock_events != results["indexed-shock"].shock_events:
        raise AssertionError("nominal and indexed regimes do not share shock events")
    irfs = _irf_rows(
        {
            "nominal": (aggregates["nominal-baseline"], aggregates["nominal-shock"]),
            "indexed": (aggregates["indexed-baseline"], aggregates["indexed-shock"]),
        }
    )
    metadata = _experiment_manifest(
        config,
        git_commit=git_commit,
        experiment_id=experiment_id,
        kind="nominal_indexed_counterfactual_comparison",
        roles=configs,
    )
    _parquet_write(output / "impulse_responses.parquet", irfs, metadata)
    _write_figures(output, irfs, cohorts)
    _json_write(output / "manifest.json", metadata)
    return OutputSet(output, experiment_id, 4)
