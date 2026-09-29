"""Regenerate the compact Phase 10 golden analytical summary."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from ecodeling.reporting import generate_regime_comparison, load_config

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
ROLES = (
    "nominal-baseline",
    "nominal-shock",
    "indexed-baseline",
    "indexed-shock",
)


def main() -> None:
    """Run the checked experiment and replace its deterministic summary fixture."""
    config = load_config(FIXTURES / "phase10_report_config.json")
    with TemporaryDirectory() as temporary_directory:
        output = Path(temporary_directory) / "report"
        generate_regime_comparison(config, output, git_commit="golden-fixture")
        summary: dict[str, dict[str, int]] = {}
        for role in ROLES:
            row = pq.read_table(output / "runs" / role / "aggregates.parquet").to_pylist()[-1]
            summary[role] = {
                "cpi_level": row["cpi_level"],
                "mortgage_principal": row["total_mortgage_principal"],
                "debt_service": row["debt_service"],
                "bank_equity": row["bank_equity"],
                "defaults": row["defaults"],
            }
    fixture = FIXTURES / "phase10_report_golden.json"
    fixture.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {fixture.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
