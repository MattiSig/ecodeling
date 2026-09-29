"""Production replay schema version 1 for paired endogenous-economy runs.

The simulation ledger and analytical outputs remain authoritative.  This module
creates a compact, deterministic presentation derivative and rejects bundles
whose stocks, flows, timelines, pairing, or representative tracks do not
reconcile with those sources.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ecodeling import __version__
from ecodeling.accounting import AccountKind, JournalEntry, Sector
from ecodeling.economy.outputs import (
    EconomySimulationResult,
    HouseholdEconomyMonthlyOutput,
    PairedEconomyResult,
)

Month = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
ISKValue = Annotated[int, Field(description="Exact nominal whole Icelandic kronur")]
REPLAY_EXPORT_REVISION = "demand-2"
DEFAULT_MAX_UNCOMPRESSED_BYTES = 2_000_000


class ReplayCompatibilityError(ValueError):
    """Raised when a replay uses an unsupported or non-migratable schema."""


class ReplaySizeError(ValueError):
    """Raised when a replay exceeds its declared publication size limit."""


class ReplayModel(BaseModel):
    """Strict immutable base for every externally visible replay record."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Compatibility(ReplayModel):
    """Reader-version range accepted for this bundle."""

    minimum_reader_schema: Literal[1] = 1
    maximum_reader_schema: Literal[1] = 1


class ReplayUnits(ReplayModel):
    """Unit conventions applying to all tables unless a series overrides them."""

    money: Literal["nominal_whole_ISK"] = "nominal_whole_ISK"
    rates: Literal["basis_points"] = "basis_points"
    price_indices: Literal["index_100000_at_base"] = "index_100000_at_base"
    real_activity: Literal["physical_units"] = "physical_units"
    ratios: Literal["basis_points"] = "basis_points"
    missing: Literal["null_means_unavailable"] = "null_means_unavailable"


class ReplayManifestV1(ReplayModel):
    """Bundle identity, provenance, compatibility, units, and publication limits."""

    schema_version: Literal[1] = 1
    compatibility: Compatibility = Compatibility()
    bundle_id: str
    model_version: str
    git_commit: Annotated[str, Field(min_length=7)]
    scenario_id: str
    seed: int
    parameter_sets: dict[Literal["nominal", "indexed"], str]
    months: tuple[Month, ...]
    units: ReplayUnits = ReplayUnits()
    rounding_tolerance_isk: Literal[0] = 0
    maximum_uncompressed_bytes: Annotated[int, Field(gt=0)]
    representative_selection: str


class TimelinePointV1(ReplayModel):
    """One aligned monthly index and its optional narrative markers."""

    index: Annotated[int, Field(ge=0)]
    month: Month
    shock: bool
    policy_decision: bool


class RunIdentityV1(ReplayModel):
    """Identity of one regime run included in the paired bundle."""

    regime: Literal["nominal", "indexed"]
    run_id: str
    scenario_id: str
    seed: int
    configuration_hash: str


class SectorSnapshotV1(ReplayModel):
    """Recorded month-end sector stocks; null means the sector/stock is unavailable."""

    regime: Literal["nominal", "indexed"]
    month: Month
    sector: Literal["households", "firms", "banks", "government", "central_bank", "foreign"]
    financial_assets_isk: ISKValue | None
    real_assets_isk: ISKValue | None
    liabilities_isk: ISKValue | None
    equity_isk: ISKValue | None
    inventory_units: int | None


class SectorFlowV1(ReplayModel):
    """A recorded monthly sector-to-sector flow with ledger provenance."""

    regime: Literal["nominal", "indexed"]
    month: Month
    flow_type: Literal[
        "wages",
        "consumption",
        "imports",
        "exports",
        "external_financing",
        "interest",
        "principal_payment",
        "bank_dividend",
    ]
    source_sector: str
    target_sector: str
    amount_isk: ISKValue
    ledger_entry_id: str


class ReplayEventV1(ReplayModel):
    """Typed event copied from an authoritative simulation event or output."""

    id: str
    regime: Literal["nominal", "indexed"]
    month: Month
    event_type: Literal[
        "FX_SHOCK",
        "FOREIGN_PRICE_SHOCK",
        "CPI_REVALUATION",
        "POLICY_RATE_CHANGE",
        "RATE_RESET",
        "ARREARS",
        "DEFAULT",
    ]
    amount: int | None
    unit: Literal["ISK", "basis_points", "households"] | None
    source_id: str


class RepresentativePointV1(ReplayModel):
    """One actual household's recorded state for one month."""

    month: Month
    wage_income_isk: ISKValue
    consumption_isk: ISKValue
    deposits_isk: ISKValue
    mortgage_principal_isk: ISKValue
    mortgage_payment_isk: ISKValue
    mortgage_revaluation_isk: ISKValue
    arrears_isk: ISKValue
    defaulted: bool


class RepresentativeAgentV1(ReplayModel):
    """Stable simulated household followed without rewriting its history."""

    regime: Literal["nominal", "indexed"]
    household_id: str
    cohort: str
    matched_household_id: str
    track: tuple[RepresentativePointV1, ...]


class SeriesPointV1(ReplayModel):
    """One aligned chart observation; null is an explicit unavailable value."""

    month: Month
    value: int | None


class AggregateSeriesV1(ReplayModel):
    """A chart-ready aggregate series copied from authoritative monthly output."""

    regime: Literal["nominal", "indexed"]
    name: str
    unit: Literal["ISK", "index", "basis_points", "households", "physical_units"]
    nominal_status: Literal["nominal", "price_index", "rate", "count", "real"]
    points: tuple[SeriesPointV1, ...]


class DistributionPointV1(ReplayModel):
    """A policy-relevant cohort aggregate for one month."""

    regime: Literal["nominal", "indexed"]
    month: Month
    dimension: Literal[
        "income_quintile",
        "homeowner_status",
        "mortgage_regime",
        "initial_ltv_group",
        "opening_liquidity_group",
    ]
    cohort: str
    households: int
    income_isk: ISKValue
    consumption_isk: ISKValue
    mortgage_principal_isk: ISKValue
    debt_service_isk: ISKValue
    mortgage_revaluation_isk: ISKValue
    deposits_isk: ISKValue
    net_worth_isk: ISKValue
    defaults: int


class ScenarioPairingV1(ReplayModel):
    """Declared common-random-number relationship between the two runs."""

    nominal_run_id: str
    indexed_run_id: str
    shared_seed: int
    shared_initialization: Literal[True] = True
    shared_shock_path: Literal[True] = True
    matching: Literal["stable_household_id"] = "stable_household_id"
    shared_random_streams: tuple[str, ...]
    structural_difference: Literal["mortgage_indexation_topology"] = "mortgage_indexation_topology"


class ReplayBundleV1(ReplayModel):
    """Complete immutable production replay contract."""

    manifest: ReplayManifestV1
    timeline: tuple[TimelinePointV1, ...]
    runs: tuple[RunIdentityV1, RunIdentityV1]
    sector_snapshots: tuple[SectorSnapshotV1, ...]
    sector_flows: tuple[SectorFlowV1, ...]
    events: tuple[ReplayEventV1, ...]
    representative_agents: tuple[RepresentativeAgentV1, ...]
    aggregate_series: tuple[AggregateSeriesV1, ...]
    distribution_series: tuple[DistributionPointV1, ...]
    scenario_pairing: ScenarioPairingV1

    @model_validator(mode="after")
    def validate_alignment_and_references(self) -> Self:
        """Reject drift, duplicate events, incomplete tracks, and broken pairing."""
        months = self.manifest.months
        if tuple(point.month for point in self.timeline) != months:
            raise ValueError("timeline must match manifest months")
        if tuple(point.index for point in self.timeline) != tuple(range(len(months))):
            raise ValueError("timeline indices must be contiguous from zero")
        if tuple(run.regime for run in self.runs) != ("nominal", "indexed"):
            raise ValueError("runs must contain nominal then indexed identities")
        event_ids = tuple(event.id for event in self.events)
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("event IDs must be unique")
        for agent in self.representative_agents:
            if tuple(point.month for point in agent.track) != months:
                raise ValueError("representative tracks must span the aligned timeline")
        for series in self.aggregate_series:
            if tuple(point.month for point in series.points) != months:
                raise ValueError("aggregate series must span the aligned timeline")
        return self

    def canonical_json(self) -> str:
        """Return deterministic compact UTF-8 JSON suitable for publication and hashing."""
        return json.dumps(
            self.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def canonical_bytes(self) -> bytes:
        """Return canonical UTF-8 bytes."""
        return self.canonical_json().encode("utf-8")

    def deterministic_gzip(self) -> bytes:
        """Return a reproducible gzip representation with no wall-clock timestamp."""
        return gzip.compress(self.canonical_bytes(), compresslevel=9, mtime=0)

    def sha256(self) -> str:
        """Return the hash of the uncompressed canonical payload."""
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class ReplayArtifact:
    """Serialized publication artifact metadata."""

    canonical_bytes: bytes
    gzip_bytes: bytes
    sha256: str


class _CohortDimension(StrEnum):
    INCOME = "income_quintile"
    HOMEOWNER = "homeowner_status"
    REGIME = "mortgage_regime"
    LTV = "initial_ltv_group"
    LIQUIDITY = "opening_liquidity_group"


def _rows_by_household(
    result: EconomySimulationResult,
) -> dict[str, tuple[HouseholdEconomyMonthlyOutput, ...]]:
    rows: dict[str, list[HouseholdEconomyMonthlyOutput]] = defaultdict(list)
    for row in result.household_months:
        rows[str(row.household_id)].append(row)
    return {key: tuple(value) for key, value in rows.items()}


def _classifications(
    result: EconomySimulationResult, regime: Literal["nominal", "indexed"]
) -> dict[str, dict[_CohortDimension, str]]:
    rows = _rows_by_household(result)
    households = sorted(result.households, key=lambda item: str(item.id))
    income_order = sorted(
        households,
        key=lambda item: (rows[str(item.id)][0].wage_income, str(item.id)),
    )
    quintiles = {
        str(item.id): f"q{min(5, rank * 5 // len(income_order) + 1)}"
        for rank, item in enumerate(income_order)
    }
    monthly_wage = result.firms[0].opening_wage
    output: dict[str, dict[_CohortDimension, str]] = {}
    for item in households:
        if item.mortgage_id is not None:
            ltv_bps = item.opening_mortgage * 10_000 // item.house_value
            homeowner = "mortgaged_homeowner"
            ltv = "low" if ltv_bps < 6_500 else "middle" if ltv_bps < 8_000 else "high"
            mortgage_regime: str = regime
        elif item.house_value:
            homeowner, ltv, mortgage_regime = "debt_free_homeowner", "debt_free", "no_mortgage"
        else:
            homeowner, ltv, mortgage_regime = "renter", "not_applicable", "no_mortgage"
        liquidity_months = item.opening_deposits / monthly_wage
        liquidity = "low" if liquidity_months < 1 else "middle" if liquidity_months < 3 else "high"
        output[str(item.id)] = {
            _CohortDimension.INCOME: quintiles[str(item.id)],
            _CohortDimension.HOMEOWNER: homeowner,
            _CohortDimension.REGIME: mortgage_regime,
            _CohortDimension.LTV: ltv,
            _CohortDimension.LIQUIDITY: liquidity,
        }
    return output


def _representative_ids(result: EconomySimulationResult) -> tuple[tuple[str, str], ...]:
    classes = _classifications(result, "nominal")
    households = {str(item.id): item for item in result.households}
    borrowers = [key for key in sorted(households) if households[key].mortgage_id is not None]
    selected: list[tuple[str, str]] = []
    low_income = [key for key in borrowers if classes[key][_CohortDimension.INCOME] in {"q1", "q2"}]
    if low_income:
        selected.append(
            (
                min(
                    low_income,
                    key=lambda key: (
                        -(households[key].opening_mortgage * 10_000 // households[key].house_value),
                        key,
                    ),
                ),
                "low_income_high_ltv_borrower",
            )
        )
    other = next((key for key in borrowers if key not in {item[0] for item in selected}), None)
    if other is not None:
        selected.append((other, "other_borrower"))
    for status, label in (("renter", "renter"), ("debt_free_homeowner", "debt_free_homeowner")):
        match = next(
            (
                key
                for key in sorted(households)
                if classes[key][_CohortDimension.HOMEOWNER] == status
            ),
            None,
        )
        if match is not None:
            selected.append((match, label))
    return tuple(selected)


def _sector_balances(
    result: EconomySimulationResult,
) -> dict[tuple[str, Sector], tuple[int, int, int, int]]:
    """Reconstruct month-end sector positions from the append-only journal."""
    accounts = {account.id: account for account in result.ledger.accounts}
    balances = {account.id: 0 for account in result.ledger.accounts}
    output: dict[tuple[str, Sector], tuple[int, int, int, int]] = {}
    entries_by_month: dict[str, list[JournalEntry]] = defaultdict(list)
    for entry in result.ledger.entries:
        entries_by_month[str(entry.month)].append(entry)
    # Origination and opening capital are journaled before the reporting window.
    # Include them once; otherwise the alleged stocks are only cumulative changes.
    first_month = str(result.aggregate_months[0].month)
    for entry in result.ledger.entries:
        if str(entry.month) < first_month:
            for posting in entry.postings:
                balances[posting.account_id] += posting.amount
    for aggregate in result.aggregate_months:
        month = str(aggregate.month)
        for entry in entries_by_month[month]:
            for posting in entry.postings:
                balances[posting.account_id] += posting.amount
        for sector in (Sector.HOUSEHOLDS, Sector.FIRMS, Sector.BANKS, Sector.FOREIGN):
            financial = real = liabilities = equity = 0
            for account_id, account in accounts.items():
                if account.sector is not sector:
                    continue
                balance = balances[account_id]
                if account.kind is AccountKind.FINANCIAL_ASSET:
                    financial += balance
                elif account.kind is AccountKind.REAL_ASSET:
                    real += balance
                elif account.kind is AccountKind.LIABILITY:
                    liabilities += balance
                else:
                    equity += balance
            output[(month, sector)] = (financial, real, liabilities, equity)
    return output


def _snapshots(
    result: EconomySimulationResult, regime: Literal["nominal", "indexed"]
) -> tuple[SectorSnapshotV1, ...]:
    balances = _sector_balances(result)
    inventories = {
        str(row.month): sum(
            item.closing_inventory for item in result.firm_months if item.month == row.month
        )
        for row in result.aggregate_months
    }
    output: list[SectorSnapshotV1] = []
    for aggregate in result.aggregate_months:
        month = str(aggregate.month)
        for sector_name, sector in (
            ("households", Sector.HOUSEHOLDS),
            ("firms", Sector.FIRMS),
            ("banks", Sector.BANKS),
            ("government", None),
            ("central_bank", None),
            ("foreign", Sector.FOREIGN),
        ):
            values = balances.get((month, sector)) if sector is not None else None
            output.append(
                SectorSnapshotV1(
                    regime=regime,
                    month=month,
                    sector=sector_name,  # type: ignore[arg-type]
                    financial_assets_isk=values[0] if values else None,
                    real_assets_isk=values[1] if values else None,
                    liabilities_isk=values[2] if values else None,
                    equity_isk=values[3] if values else None,
                    inventory_units=inventories[month] if sector is Sector.FIRMS else None,
                )
            )
    return tuple(output)


def _flows(
    result: EconomySimulationResult, regime: Literal["nominal", "indexed"]
) -> tuple[SectorFlowV1, ...]:
    households: dict[str, list[HouseholdEconomyMonthlyOutput]] = defaultdict(list)
    for row in result.household_months:
        households[str(row.month)].append(row)
    output: list[SectorFlowV1] = []
    for aggregate in result.aggregate_months:
        month = str(aggregate.month)
        rows = households[month]
        interest = sum(min(row.actual_mortgage_payment, row.mortgage_interest) for row in rows)
        principal = sum(max(0, row.actual_mortgage_payment - row.mortgage_interest) for row in rows)
        candidates = (
            ("wages", "firms", "households", aggregate.wage_income, f"economy:{month}:wages"),
            (
                "consumption",
                "households",
                "firms",
                aggregate.household_consumption,
                f"economy:{month}:goods",
            ),
            (
                "imports",
                "firms",
                "foreign",
                aggregate.imported_input_expenditure,
                f"economy:{month}:imports",
            ),
            (
                "exports",
                "foreign",
                "firms",
                aggregate.export_revenue,
                f"economy:{month}:exports",
            ),
            (
                "external_financing",
                "banks",
                "foreign",
                aggregate.external_financing,
                f"economy:{month}:export-funding",
            ),
            (
                "interest",
                "households",
                "banks",
                interest,
                f"economy:{month}:mortgage-settlement",
            ),
            (
                "principal_payment",
                "households",
                "banks",
                principal,
                f"economy:{month}:mortgage-settlement",
            ),
            (
                "bank_dividend",
                "banks",
                "households",
                aggregate.bank_dividends,
                f"economy:{month}:bank-dividends",
            ),
        )
        ledger_ids = {str(entry.id) for entry in result.ledger.entries}
        for flow_type, source, target, amount, entry_id in candidates:
            if amount:
                if entry_id not in ledger_ids:
                    raise ValueError(f"replay flow has no source ledger entry: {entry_id}")
                output.append(
                    SectorFlowV1(
                        regime=regime,
                        month=month,
                        flow_type=flow_type,  # type: ignore[arg-type]
                        source_sector=source,
                        target_sector=target,
                        amount_isk=amount,
                        ledger_entry_id=entry_id,
                    )
                )
    return tuple(output)


def _events(
    result: EconomySimulationResult, regime: Literal["nominal", "indexed"]
) -> tuple[ReplayEventV1, ...]:
    output: list[ReplayEventV1] = []
    for event in result.shock_events:
        output.append(
            ReplayEventV1(
                id=f"{regime}:{event.event_id}",
                regime=regime,
                month=str(event.month),
                event_type=(
                    "FX_SHOCK" if event.kind.value == "fx_depreciation" else "FOREIGN_PRICE_SHOCK"
                ),
                amount=event.magnitude_bps,
                unit="basis_points",
                source_id=event.event_id,
            )
        )
    for row in result.aggregate_months:
        month = str(row.month)
        if row.indexation_revaluation:
            output.append(
                ReplayEventV1(
                    id=f"{regime}:cpi-revaluation:{month}",
                    regime=regime,
                    month=month,
                    event_type="CPI_REVALUATION",
                    amount=row.indexation_revaluation,
                    unit="ISK",
                    source_id=str(row.revaluation_ledger_entry_id),
                )
            )
        if row.arrears_households:
            output.append(
                ReplayEventV1(
                    id=f"{regime}:arrears:{month}",
                    regime=regime,
                    month=month,
                    event_type="ARREARS",
                    amount=row.arrears_households,
                    unit="households",
                    source_id=f"economy:{month}:mortgage-settlement",
                )
            )
        if row.defaults:
            output.append(
                ReplayEventV1(
                    id=f"{regime}:defaults:{month}",
                    regime=regime,
                    month=month,
                    event_type="DEFAULT",
                    amount=row.defaults,
                    unit="households",
                    source_id=f"economy:{month}:defaults",
                )
            )
    for policy_event in result.policy_events:
        output.append(
            ReplayEventV1(
                id=f"{regime}:{policy_event.event_id}",
                regime=regime,
                month=str(policy_event.month),
                event_type="POLICY_RATE_CHANGE",
                amount=policy_event.policy_rate_bps,
                unit="basis_points",
                source_id=policy_event.event_id,
            )
        )
    for reset_event in result.rate_reset_events:
        output.append(
            ReplayEventV1(
                id=f"{regime}:{reset_event.event_id}",
                regime=regime,
                month=str(reset_event.month),
                event_type="RATE_RESET",
                amount=reset_event.new_rate_bps,
                unit="basis_points",
                source_id=reset_event.source_policy_event_id,
            )
        )
    return tuple(output)


def _representatives(
    result: EconomySimulationResult,
    regime: Literal["nominal", "indexed"],
    selected: tuple[tuple[str, str], ...],
) -> tuple[RepresentativeAgentV1, ...]:
    rows = _rows_by_household(result)
    return tuple(
        RepresentativeAgentV1(
            regime=regime,
            household_id=household_id,
            cohort=cohort,
            matched_household_id=household_id,
            track=tuple(
                RepresentativePointV1(
                    month=str(row.month),
                    wage_income_isk=row.wage_income,
                    consumption_isk=row.consumption_expenditure,
                    deposits_isk=row.closing_deposits,
                    mortgage_principal_isk=row.closing_mortgage_principal,
                    mortgage_payment_isk=row.actual_mortgage_payment,
                    mortgage_revaluation_isk=row.mortgage_revaluation,
                    arrears_isk=row.arrears,
                    defaulted=row.defaulted,
                )
                for row in rows[household_id]
            ),
        )
        for household_id, cohort in selected
    )


def _aggregate_series(
    result: EconomySimulationResult, regime: Literal["nominal", "indexed"]
) -> tuple[AggregateSeriesV1, ...]:
    definitions: tuple[tuple[str, str, str, tuple[int | None, ...]], ...] = (
        (
            "cpi_level",
            "index",
            "price_index",
            tuple(row.cpi_level for row in result.aggregate_months),
        ),
        (
            "monthly_inflation",
            "basis_points",
            "rate",
            tuple(row.monthly_inflation_bps for row in result.aggregate_months),
        ),
        (
            "annual_inflation",
            "basis_points",
            "rate",
            tuple(row.annual_inflation_bps for row in result.aggregate_months),
        ),
        (
            "production",
            "physical_units",
            "real",
            tuple(row.production_units for row in result.aggregate_months),
        ),
        (
            "employment",
            "households",
            "count",
            tuple(row.employed_households for row in result.aggregate_months),
        ),
        (
            "consumption",
            "ISK",
            "nominal",
            tuple(row.household_consumption for row in result.aggregate_months),
        ),
        (
            "real_consumption",
            "physical_units",
            "real",
            tuple(row.sales_units - row.export_units for row in result.aggregate_months),
        ),
        (
            "exports",
            "ISK",
            "nominal",
            tuple(row.export_revenue for row in result.aggregate_months),
        ),
        (
            "policy_rate",
            "basis_points",
            "rate",
            tuple(row.policy_rate_bps for row in result.aggregate_months),
        ),
        (
            "exchange_rate",
            "index",
            "price_index",
            tuple(row.exchange_rate_index for row in result.aggregate_months),
        ),
        (
            "import_price",
            "index",
            "price_index",
            tuple(row.import_price_index for row in result.aggregate_months),
        ),
        (
            "mortgage_principal",
            "ISK",
            "nominal",
            tuple(row.total_mortgage_principal for row in result.aggregate_months),
        ),
        (
            "mortgage_revaluation",
            "ISK",
            "nominal",
            tuple(row.indexation_revaluation for row in result.aggregate_months),
        ),
        (
            "debt_service",
            "ISK",
            "nominal",
            tuple(row.debt_service for row in result.aggregate_months),
        ),
        (
            "arrears",
            "households",
            "count",
            tuple(row.arrears_households for row in result.aggregate_months),
        ),
        ("defaults", "households", "count", tuple(row.defaults for row in result.aggregate_months)),
        (
            "bank_equity",
            "ISK",
            "nominal",
            tuple(row.bank_equity for row in result.aggregate_months),
        ),
    )
    return tuple(
        AggregateSeriesV1(
            regime=regime,
            name=name,
            unit=unit,  # type: ignore[arg-type]
            nominal_status=status,  # type: ignore[arg-type]
            points=tuple(
                SeriesPointV1(month=str(row.month), value=value)
                for row, value in zip(result.aggregate_months, values, strict=True)
            ),
        )
        for name, unit, status, values in definitions
    )


def _distribution_series(
    result: EconomySimulationResult, regime: Literal["nominal", "indexed"]
) -> tuple[DistributionPointV1, ...]:
    classes = _classifications(result, regime)
    households = {str(item.id): item for item in result.households}
    by_month: dict[str, list[HouseholdEconomyMonthlyOutput]] = defaultdict(list)
    for row in result.household_months:
        by_month[str(row.month)].append(row)
    output: list[DistributionPointV1] = []
    for aggregate in result.aggregate_months:
        month = str(aggregate.month)
        for dimension in _CohortDimension:
            cohorts = sorted({labels[dimension] for labels in classes.values()})
            for cohort in cohorts:
                members = [
                    row
                    for row in by_month[month]
                    if classes[str(row.household_id)][dimension] == cohort
                ]
                house_value = sum(households[str(row.household_id)].house_value for row in members)
                principal = sum(row.closing_mortgage_principal for row in members)
                deposits = sum(row.closing_deposits for row in members)
                output.append(
                    DistributionPointV1(
                        regime=regime,
                        month=month,
                        dimension=dimension.value,
                        cohort=cohort,
                        households=len(members),
                        income_isk=sum(row.wage_income for row in members),
                        consumption_isk=sum(row.consumption_expenditure for row in members),
                        mortgage_principal_isk=principal,
                        debt_service_isk=sum(row.actual_mortgage_payment for row in members),
                        mortgage_revaluation_isk=sum(row.mortgage_revaluation for row in members),
                        deposits_isk=deposits,
                        net_worth_isk=deposits + house_value - principal,
                        defaults=sum(row.defaulted for row in members),
                    )
                )
    return tuple(output)


def _assert_reconciliation(bundle: ReplayBundleV1, pair: PairedEconomyResult) -> None:
    for regime, result in (("nominal", pair.nominal), ("indexed", pair.indexed)):
        series = {
            (item.name, point.month): point.value
            for item in bundle.aggregate_series
            if item.regime == regime
            for point in item.points
        }
        flows = [item for item in bundle.sector_flows if item.regime == regime]
        distributions = [item for item in bundle.distribution_series if item.regime == regime]
        snapshots = {
            (item.sector, item.month): item
            for item in bundle.sector_snapshots
            if item.regime == regime
        }
        for aggregate in result.aggregate_months:
            month = str(aggregate.month)
            if (
                snapshots[("banks", month)].equity_isk != aggregate.bank_equity
                or snapshots[("households", month)].liabilities_isk
                != aggregate.total_mortgage_principal
            ):
                raise ValueError(f"sector-stock reconciliation failed for {regime} {month}")
            expected = {
                "cpi_level": aggregate.cpi_level,
                "mortgage_principal": aggregate.total_mortgage_principal,
                "debt_service": aggregate.debt_service,
                "consumption": aggregate.household_consumption,
                "defaults": aggregate.defaults,
                "bank_equity": aggregate.bank_equity,
            }
            if any(series[(name, month)] != value for name, value in expected.items()):
                raise ValueError(f"aggregate replay reconciliation failed for {regime} {month}")
            debt_flows = sum(
                item.amount_isk
                for item in flows
                if item.month == month and item.flow_type in {"interest", "principal_payment"}
            )
            if debt_flows != aggregate.debt_service:
                raise ValueError(f"debt-service flow reconciliation failed for {regime} {month}")
            income_rows = [
                item
                for item in distributions
                if item.month == month and item.dimension == "income_quintile"
            ]
            if (
                sum(item.consumption_isk for item in income_rows) != aggregate.household_consumption
                or sum(item.mortgage_principal_isk for item in income_rows)
                != aggregate.total_mortgage_principal
            ):
                raise ValueError(f"distribution reconciliation failed for {regime} {month}")


def export_replay_v1(
    pair: PairedEconomyResult,
    *,
    git_commit: str,
    maximum_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
) -> ReplayBundleV1:
    """Export, align, reconcile, and size-check a paired production replay."""
    nominal_months = tuple(str(row.month) for row in pair.nominal.aggregate_months)
    indexed_months = tuple(str(row.month) for row in pair.indexed.aggregate_months)
    if nominal_months != indexed_months:
        raise ValueError("paired runs must use the same monthly timeline")
    if pair.nominal.seed != pair.indexed.seed:
        raise ValueError("paired runs must use the same master seed")
    if (
        pair.nominal.households != pair.indexed.households
        or pair.nominal.firms != pair.indexed.firms
    ):
        raise ValueError("paired runs must share initialized agents")
    if pair.nominal.shock_events != pair.indexed.shock_events:
        raise ValueError("paired runs must share the exogenous shock path")
    selected = _representative_ids(pair.nominal)
    shock_months = {str(event.month) for event in pair.nominal.shock_events}
    policy_months = {str(event.month) for event in pair.nominal.policy_events}
    bundle = ReplayBundleV1(
        manifest=ReplayManifestV1(
            bundle_id=f"paired-{pair.nominal.seed}-{pair.nominal.configuration_hash[:8]}-{pair.indexed.configuration_hash[:8]}-{REPLAY_EXPORT_REVISION}",
            model_version=__version__,
            git_commit=git_commit,
            scenario_id=str(pair.nominal.scenario_id).removesuffix("-nominal"),
            seed=pair.nominal.seed,
            parameter_sets={
                "nominal": pair.nominal.configuration_hash,
                "indexed": pair.indexed.configuration_hash,
            },
            months=nominal_months,
            maximum_uncompressed_bytes=maximum_uncompressed_bytes,
            representative_selection=(
                "deterministic v1: highest-LTV q1/q2 borrower, next stable borrower, "
                "then lowest stable renter and debt-free homeowner; IDs match across regimes"
            ),
        ),
        timeline=tuple(
            TimelinePointV1(
                index=index,
                month=month,
                shock=month in shock_months,
                policy_decision=month in policy_months,
            )
            for index, month in enumerate(nominal_months)
        ),
        runs=(
            RunIdentityV1(
                regime="nominal",
                run_id=str(pair.nominal.run_id),
                scenario_id=str(pair.nominal.scenario_id),
                seed=pair.nominal.seed,
                configuration_hash=pair.nominal.configuration_hash,
            ),
            RunIdentityV1(
                regime="indexed",
                run_id=str(pair.indexed.run_id),
                scenario_id=str(pair.indexed.scenario_id),
                seed=pair.indexed.seed,
                configuration_hash=pair.indexed.configuration_hash,
            ),
        ),
        sector_snapshots=_snapshots(pair.nominal, "nominal") + _snapshots(pair.indexed, "indexed"),
        sector_flows=_flows(pair.nominal, "nominal") + _flows(pair.indexed, "indexed"),
        events=_events(pair.nominal, "nominal") + _events(pair.indexed, "indexed"),
        representative_agents=_representatives(pair.nominal, "nominal", selected)
        + _representatives(pair.indexed, "indexed", selected),
        aggregate_series=_aggregate_series(pair.nominal, "nominal")
        + _aggregate_series(pair.indexed, "indexed"),
        distribution_series=_distribution_series(pair.nominal, "nominal")
        + _distribution_series(pair.indexed, "indexed"),
        scenario_pairing=ScenarioPairingV1(
            nominal_run_id=str(pair.nominal.run_id),
            indexed_run_id=str(pair.indexed.run_id),
            shared_seed=pair.nominal.seed,
            shared_random_streams=(
                "initialization",
                "labor_matching",
                "goods_matching",
                "shocks",
                "defaults",
            ),
        ),
    )
    _assert_reconciliation(bundle, pair)
    if len(bundle.canonical_bytes()) > maximum_uncompressed_bytes:
        raise ReplaySizeError(
            f"replay payload exceeds {maximum_uncompressed_bytes} uncompressed bytes"
        )
    return bundle


def serialize_replay_v1(bundle: ReplayBundleV1) -> ReplayArtifact:
    """Serialize a validated bundle as canonical JSON plus deterministic gzip."""
    canonical = bundle.canonical_bytes()
    if len(canonical) > bundle.manifest.maximum_uncompressed_bytes:
        raise ReplaySizeError("replay payload exceeds its manifest size limit")
    return ReplayArtifact(canonical, bundle.deterministic_gzip(), bundle.sha256())


def load_replay_v1(payload: str | bytes) -> ReplayBundleV1:
    """Load schema v1 and fail explicitly for legacy or future versions."""
    raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReplayCompatibilityError("replay is not valid JSON") from error
    if not isinstance(decoded, dict) or not isinstance(decoded.get("manifest"), dict):
        raise ReplayCompatibilityError("replay manifest is missing")
    version = decoded["manifest"].get("schema_version")
    if version == 0:
        raise ReplayCompatibilityError(
            "schema v0 is an audit-only micro replay and cannot be losslessly migrated to v1"
        )
    if version != 1:
        raise ReplayCompatibilityError(f"unsupported replay schema version: {version!r}")
    return ReplayBundleV1.model_validate(decoded)
