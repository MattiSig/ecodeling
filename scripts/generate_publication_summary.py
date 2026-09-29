"""Regenerate the publication's config and descriptive values from its replay."""

import gzip
import json
from pathlib import Path

from ecodeling.reporting import ReplayBundleV1, load_config


def main() -> None:
    """Copy authoritative recorded values without recomputing model transitions."""
    release = Path("publication/v0.1")
    config = load_config(Path("tests/fixtures/phase10_report_config.json"))
    (release / "canonical-config.json").write_text(
        json.dumps(
            config.model_dump(mode="json") | {"scenario_id": "canonical-replay-v1"}, indent=2
        )
        + "\n"
    )
    replay = ReplayBundleV1.model_validate_json(
        gzip.decompress(Path("web/replay/canonical-v1.json.gz").read_bytes())
    )
    series: dict[str, dict[str, int | None]] = {}
    for output, metric, operation in (
        ("bank_equity_closing_isk", "bank_equity", "last"),
        ("consumption_closing_isk", "consumption", "last"),
        ("consumption_total_isk", "consumption", "sum"),
        ("real_consumption_total_units", "real_consumption", "sum"),
        ("employment_closing_households", "employment", "last"),
        ("cpi_closing_index", "cpi_level", "last"),
        ("defaults_peak_households", "defaults", "max"),
        ("defaults_total_households", "defaults", "sum"),
        ("debt_service_opening_isk", "debt_service", "first"),
        ("mortgage_principal_closing_isk", "mortgage_principal", "last"),
        ("policy_rate_closing_basis_points", "policy_rate", "last"),
    ):
        series[output] = {}
        for regime in ("nominal", "indexed"):
            points = next(
                s.points for s in replay.aggregate_series if s.name == metric and s.regime == regime
            )
            values = [p.value for p in points]
            if any(value is None for value in values):
                raise ValueError(f"missing {metric} observation")
            numbers = [int(value) for value in values if value is not None]
            series[output][regime] = {
                "first": numbers[0],
                "last": numbers[-1],
                "sum": sum(numbers),
                "max": max(numbers),
            }[operation]
    summary = {
        "calibration_status": "stylized mechanism calibration",
        "model_version": replay.manifest.model_version,
        "model_source_commit": replay.manifest.git_commit,
        "scenario_id": replay.manifest.scenario_id,
        "seed": replay.manifest.seed,
        "series": series,
        "statement": "Replay-derived descriptive values, not empirical estimates or forecasts.",
    }
    (release / "canonical-summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
