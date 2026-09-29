"""Golden analytical reporting and persisted counterfactual tests."""

import json
from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from ecodeling.reporting import generate_regime_comparison, load_config

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_complete_comparison_reconciles_irfs_metadata_and_golden_summary(
    tmp_path: Path,
) -> None:
    config = load_config(FIXTURES / "phase10_report_config.json")
    output = tmp_path / "report"
    generated = generate_regime_comparison(config, output, git_commit="abcdef0123456789")

    assert generated.run_count == 4
    assert sorted(path.name for path in (output / "figures").glob("*.svg")) == [
        "01-inflation.svg",
        "02-mortgage-principal.svg",
        "03-debt-service.svg",
        "04-consumption.svg",
        "05-defaults.svg",
        "06-bank-equity.svg",
        "07-distributional-consumption.svg",
    ]
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["git_commit"] == "abcdef0123456789"
    assert manifest["seed"] == 1010
    assert manifest["shock_definition"]["kind"] == "fx_depreciation"

    roles = manifest["roles"]
    assert roles == [
        "nominal-baseline",
        "nominal-shock",
        "indexed-baseline",
        "indexed-shock",
    ]
    for role in roles:
        run_path = output / "runs" / role
        assert {path.name for path in run_path.iterdir()} == {
            "aggregates.parquet",
            "banks.parquet",
            "cohorts.parquet",
            "events.json",
            "metadata.json",
            "parameters.json",
        }
        table = pq.read_table(run_path / "aggregates.parquet")
        embedded = json.loads(table.schema.metadata[b"ecodeling"])
        assert embedded["git_commit"] == "abcdef0123456789"
        assert embedded["parameter_set"] == "embedded:parameters.json"
        cohort_rows = pq.read_table(run_path / "cohorts.parquet").to_pylist()
        assert {row["cohort_dimension"] for row in cohort_rows} == {
            "homeowner_status",
            "income_quintile",
            "initial_ltv_group",
            "mortgage_regime",
            "opening_liquidity_group",
        }
        bank_rows = pq.read_table(run_path / "banks.parquet").to_pylist()
        events = json.loads((run_path / "events.json").read_text())
        assert (
            sum(row["credit_losses_isk"] for row in bank_rows)
            == events["summary"]["defaults"]["credit_losses_isk"]
        )

    irfs = pq.read_table(output / "impulse_responses.parquet").to_pylist()
    target = next(
        row
        for row in irfs
        if row["regime"] == "indexed"
        and row["metric"] == "total_mortgage_principal"
        and row["month"] == "2025-06"
    )
    assert target["response"] == target["shock"] - target["baseline"]

    final_rows = {
        role: pq.read_table(output / "runs" / role / "aggregates.parquet").to_pylist()[-1]
        for role in roles
    }
    summary = {
        role: {
            "cpi_level": row["cpi_level"],
            "mortgage_principal": row["total_mortgage_principal"],
            "debt_service": row["debt_service"],
            "bank_equity": row["bank_equity"],
            "defaults": row["defaults"],
        }
        for role, row in final_rows.items()
    }
    assert summary == json.loads((FIXTURES / "phase10_report_golden.json").read_text())
