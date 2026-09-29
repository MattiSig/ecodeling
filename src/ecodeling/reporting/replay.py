"""Replay schema version 0 and exporter for the household-bank micro model.

The ledger and analytical records remain authoritative.  This module creates a
small immutable browser derivative and refuses to return it unless visible stocks,
flows, representative tracks, and source journal references reconcile exactly.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ecodeling import __version__
from ecodeling.accounting import Account, AccountKind, RevaluationEntry
from ecodeling.micro.entities import HomeownerStatus, Household
from ecodeling.micro.outputs import HouseholdMonthlyOutput, MicroSimulationResult

Month = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
ISKValue = Annotated[int, Field(description="Exact nominal whole Icelandic kronur")]
SeriesName = Literal[
    "cpi_level",
    "mortgage_principal",
    "debt_service",
    "indexation_revaluation",
    "household_net_worth",
    "bank_assets",
]


class ReplayModel(BaseModel):
    """Strict immutable base for the external replay contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ReplayManifest(ReplayModel):
    """Run identity, units, timeline, and selection provenance."""

    schema_version: Literal[0] = 0
    run_id: str
    model_version: str
    git_commit: Annotated[str, Field(min_length=7)]
    scenario_id: str
    seed: int
    parameter_set: str
    regime: Literal["nominal", "indexed"]
    units: dict[str, str]
    price_base: str
    months: tuple[Month, ...]
    representative_selection: str


class TimelinePoint(ReplayModel):
    """One stable index into the completed monthly replay."""

    index: int
    month: Month


class SectorSnapshot(ReplayModel):
    """A visible sector stock sourced from authoritative monthly outputs."""

    month: Month
    sector: Literal["households", "banks"]
    mortgage_principal: ISKValue
    deposits: ISKValue
    net_worth: ISKValue | None = None
    equity: ISKValue | None = None


class SectorFlow(ReplayModel):
    """An aggregate recorded flow with its journal provenance."""

    month: Month
    flow_type: Literal["income", "consumption", "principal_and_interest"]
    source_sector: str
    target_sector: str
    amount: ISKValue
    ledger_entry_id: str


class LedgerSide(ReplayModel):
    """One claimant side of a representative mortgage revaluation."""

    role: Literal["borrower_liability", "lender_asset"]
    account_id: str
    owner_id: str
    amount: ISKValue


class ReplayEvent(ReplayModel):
    """A typed narrative marker tied to a source ledger entry."""

    id: str
    month: Month
    event_type: Literal["CPI_REVALUATION", "ARREARS", "DEFAULT"]
    household_id: str
    amount: ISKValue
    ledger_entry_id: str
    ledger_sides: tuple[LedgerSide, ...] = ()


class RepresentativePoint(ReplayModel):
    """One actual simulated household's recorded state in one month."""

    month: Month
    mortgage_principal: ISKValue
    payment: ISKValue
    revaluation: ISKValue
    deposits: ISKValue
    net_worth: ISKValue
    revaluation_event_id: str | None = None
    payment_ledger_entry_id: str | None = None


class RepresentativeAgent(ReplayModel):
    """A deterministic real household and its unmodified simulated track."""

    household_id: str
    bank_id: str
    cohort: str
    stable_label: str
    track: tuple[RepresentativePoint, ...]


class SeriesPoint(ReplayModel):
    """One exact aggregate series observation."""

    month: Month
    value: int


class AggregateSeries(ReplayModel):
    """A chart-ready series copied from authoritative aggregate output."""

    name: SeriesName
    unit: Literal["index", "ISK"]
    nominal_status: Literal["price_index", "nominal"]
    points: tuple[SeriesPoint, ...]


class DistributionPoint(ReplayModel):
    """A cohort total copied from the distributional analytical table."""

    month: Month
    dimension: str
    value: str
    mortgage_principal: ISKValue
    debt_service: ISKValue
    net_worth: ISKValue


class ReplayBundle(ReplayModel):
    """Complete replay-v0 contract consumed by the internal audit viewer."""

    manifest: ReplayManifest
    timeline: tuple[TimelinePoint, ...]
    snapshots: tuple[SectorSnapshot, ...]
    flows: tuple[SectorFlow, ...]
    events: tuple[ReplayEvent, ...]
    representative_agents: tuple[RepresentativeAgent, ...]
    aggregate_series: tuple[AggregateSeries, ...]
    distribution_series: tuple[DistributionPoint, ...]
    scenario_pairing: None = None

    @model_validator(mode="after")
    def validate_references_and_timeline(self) -> Self:
        """Reject incompatible timelines, duplicate IDs, and dangling event links."""
        months = self.manifest.months
        if tuple(item.month for item in self.timeline) != months:
            raise ValueError("timeline must match manifest months")
        if tuple(item.index for item in self.timeline) != tuple(range(len(months))):
            raise ValueError("timeline indices must be contiguous from zero")
        event_ids = tuple(item.id for item in self.events)
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("replay event IDs must be unique")
        known_events = set(event_ids)
        for agent in self.representative_agents:
            if tuple(item.month for item in agent.track) != months:
                raise ValueError("representative tracks must span the full timeline")
            for point in agent.track:
                if point.revaluation_event_id not in known_events | {None}:
                    raise ValueError("representative track references an unknown event")
        return self

    def canonical_json(self) -> str:
        """Return deterministic compact UTF-8 JSON suitable for hashing and fixtures."""
        return json.dumps(
            self.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


def _representatives(households: tuple[Household, ...]) -> tuple[tuple[Household, str], ...]:
    borrowers = sorted(
        (item for item in households if item.homeowner_status is HomeownerStatus.MORTGAGED),
        key=lambda item: str(item.id),
    )
    low_income = [item for item in borrowers if item.income_quintile <= 2]
    selected: list[tuple[Household, str]] = []
    if low_income:
        high_ltv = max(
            low_income,
            key=lambda item: (item.initial_ltv_quintile or 0, -int(str(item.id).split("-")[-1])),
        )
        selected.append((high_ltv, "low_income_high_ltv_borrower"))
    other = next((item for item in borrowers if item not in {row[0] for row in selected}), None)
    if other is not None:
        selected.append((other, "other_borrower"))
    for status, label in (
        (HomeownerStatus.RENTER, "renter"),
        (HomeownerStatus.DEBT_FREE, "debt_free_homeowner"),
    ):
        match = next(
            (
                item
                for item in sorted(households, key=lambda row: str(row.id))
                if item.homeowner_status is status
            ),
            None,
        )
        if match is not None:
            selected.append((match, label))
    return tuple(selected)


def _revaluation_sides(
    result: MicroSimulationResult,
    household: Household,
    month: str,
) -> tuple[LedgerSide, ...]:
    entry_id = f"micro:{month}:cpi-revaluation"
    entry = next(
        (
            item
            for item in result.ledger.entries
            if str(item.id) == entry_id and isinstance(item, RevaluationEntry)
        ),
        None,
    )
    if entry is None or household.mortgage_id is None:
        return ()
    accounts: dict[str, Account] = {str(item.id): item for item in result.ledger.accounts}
    output: list[LedgerSide] = []
    for posting in entry.postings:
        account = accounts[str(posting.account_id)]
        if account.claim_id != household.mortgage_id:
            continue
        if account.kind is AccountKind.LIABILITY:
            role: Literal["borrower_liability", "lender_asset"] = "borrower_liability"
        elif account.kind is AccountKind.FINANCIAL_ASSET:
            role = "lender_asset"
        else:
            continue
        output.append(
            LedgerSide(
                role=role,
                account_id=str(account.id),
                owner_id=str(account.owner_id),
                amount=posting.amount,
            )
        )
    return tuple(output)


def _aggregate_series(result: MicroSimulationResult) -> tuple[AggregateSeries, ...]:
    bank_assets: dict[str, int] = defaultdict(int)
    for row in result.bank_months:
        bank_assets[str(row.month)] += row.total_loans
    values: tuple[tuple[SeriesName, Literal["index", "ISK"], tuple[int, ...]], ...] = (
        ("cpi_level", "index", tuple(row.cpi_level for row in result.aggregate_months)),
        (
            "mortgage_principal",
            "ISK",
            tuple(row.total_mortgage_principal for row in result.aggregate_months),
        ),
        ("debt_service", "ISK", tuple(row.debt_service for row in result.aggregate_months)),
        (
            "indexation_revaluation",
            "ISK",
            tuple(row.indexed_revaluation for row in result.aggregate_months),
        ),
        (
            "household_net_worth",
            "ISK",
            tuple(row.household_net_worth for row in result.aggregate_months),
        ),
        (
            "bank_assets",
            "ISK",
            tuple(bank_assets[str(row.month)] for row in result.aggregate_months),
        ),
    )
    return tuple(
        AggregateSeries(
            name=name,
            unit=unit,
            nominal_status="price_index" if unit == "index" else "nominal",
            points=tuple(
                SeriesPoint(month=str(row.month), value=value)
                for row, value in zip(result.aggregate_months, series_values, strict=True)
            ),
        )
        for name, unit, series_values in values
    )


def export_replay_v0(result: MicroSimulationResult, *, git_commit: str) -> ReplayBundle:
    """Export and reconcile one completed micro run as replay schema version 0."""
    months = tuple(str(row.month) for row in result.aggregate_months)
    ledger_ids = {str(item.id) for item in result.ledger.entries}
    snapshots: list[SectorSnapshot] = []
    for aggregate in result.aggregate_months:
        bank_rows = [item for item in result.bank_months if item.month == aggregate.month]
        snapshots.extend(
            (
                SectorSnapshot(
                    month=str(aggregate.month),
                    sector="households",
                    mortgage_principal=aggregate.total_mortgage_principal,
                    deposits=aggregate.household_deposits,
                    net_worth=aggregate.household_net_worth,
                ),
                SectorSnapshot(
                    month=str(aggregate.month),
                    sector="banks",
                    mortgage_principal=sum(item.total_loans for item in bank_rows),
                    deposits=sum(item.deposits for item in bank_rows),
                    equity=sum(item.equity for item in bank_rows),
                ),
            )
        )

    flows: list[SectorFlow] = []
    for aggregate_row in result.aggregate_months:
        month = str(aggregate_row.month)
        candidates = (
            (
                "income",
                "foreign",
                "households",
                aggregate_row.total_income,
                f"micro:{month}:income",
            ),
            (
                "consumption",
                "households",
                "foreign",
                aggregate_row.total_consumption,
                f"micro:{month}:consumption",
            ),
            (
                "principal_and_interest",
                "households",
                "banks",
                aggregate_row.debt_service,
                f"micro:{month}:mortgage-settlement",
            ),
        )
        for flow_type, source, target, amount, entry_id in candidates:
            if amount:
                if entry_id not in ledger_ids:
                    raise ValueError(f"visible flow has no source ledger entry: {entry_id}")
                flows.append(
                    SectorFlow(
                        month=month,
                        flow_type=flow_type,  # type: ignore[arg-type]
                        source_sector=source,
                        target_sector=target,
                        amount=amount,
                        ledger_entry_id=entry_id,
                    )
                )

    rows_by_household: dict[str, list[HouseholdMonthlyOutput]] = defaultdict(list)
    for household_row in result.household_months:
        rows_by_household[str(household_row.household_id)].append(household_row)
    events: list[ReplayEvent] = []
    representatives: list[RepresentativeAgent] = []
    for household, cohort in _representatives(result.households):
        household_id = str(household.id)
        track: list[RepresentativePoint] = []
        for household_row in rows_by_household[household_id]:
            month = str(household_row.month)
            revaluation_event_id: str | None = None
            if household_row.indexation_revaluation:
                source_id = f"micro:{month}:cpi-revaluation"
                revaluation_event_id = f"{source_id}:{household_id}"
                sides = _revaluation_sides(result, household, month)
                if len(sides) != 2 or {item.amount for item in sides} != {
                    household_row.indexation_revaluation
                }:
                    raise ValueError("representative revaluation does not reconcile to both claims")
                events.append(
                    ReplayEvent(
                        id=revaluation_event_id,
                        month=month,
                        event_type="CPI_REVALUATION",
                        household_id=household_id,
                        amount=household_row.indexation_revaluation,
                        ledger_entry_id=source_id,
                        ledger_sides=sides,
                    )
                )
            if household_row.arrears:
                events.append(
                    ReplayEvent(
                        id=f"micro:{month}:arrears:{household_id}",
                        month=month,
                        event_type="ARREARS",
                        household_id=household_id,
                        amount=household_row.arrears,
                        ledger_entry_id=f"micro:{month}:mortgage-settlement",
                    )
                )
            if household_row.defaulted:
                events.append(
                    ReplayEvent(
                        id=f"micro:{month}:default:{household_id}",
                        month=month,
                        event_type="DEFAULT",
                        household_id=household_id,
                        amount=0,
                        ledger_entry_id=f"micro:{month}:defaults",
                    )
                )
            payment_source = (
                f"micro:{month}:mortgage-settlement" if household_row.actual_payment else None
            )
            track.append(
                RepresentativePoint(
                    month=month,
                    mortgage_principal=household_row.closing_principal,
                    payment=household_row.actual_payment,
                    revaluation=household_row.indexation_revaluation,
                    deposits=household_row.deposits,
                    net_worth=household_row.net_worth,
                    revaluation_event_id=revaluation_event_id,
                    payment_ledger_entry_id=payment_source,
                )
            )
        representatives.append(
            RepresentativeAgent(
                household_id=household_id,
                bank_id=str(household.bank_id),
                cohort=cohort,
                stable_label=household_id,
                track=tuple(track),
            )
        )

    bundle = ReplayBundle(
        manifest=ReplayManifest(
            run_id=str(result.run_id),
            model_version=__version__,
            git_commit=git_commit,
            scenario_id=str(result.scenario_id),
            seed=result.seed,
            parameter_set=result.configuration_hash,
            regime=result.regime.value,  # type: ignore[arg-type]
            units={"money": "ISK", "money_precision": "whole", "cpi": "index"},
            price_base="CPI is an integer index; the first simulated month is the real-consumption base",
            months=months,
            representative_selection=(
                "deterministic v0: highest initial-LTV quintile among income quintiles 1-2, "
                "then lowest stable IDs for other available policy cohorts"
            ),
        ),
        timeline=tuple(
            TimelinePoint(index=index, month=month) for index, month in enumerate(months)
        ),
        snapshots=tuple(snapshots),
        flows=tuple(flows),
        events=tuple(events),
        representative_agents=tuple(representatives),
        aggregate_series=_aggregate_series(result),
        distribution_series=tuple(
            DistributionPoint(
                month=str(row.month),
                dimension=row.dimension,
                value=row.value,
                mortgage_principal=row.mortgage_principal,
                debt_service=row.debt_service,
                net_worth=row.net_worth,
            )
            for row in result.cohort_months
        ),
    )
    _assert_reconciliation(bundle, result)
    return bundle


def _assert_reconciliation(bundle: ReplayBundle, result: MicroSimulationResult) -> None:
    """Enforce exact replay-to-authority reconciliation before publication."""
    for aggregate in result.aggregate_months:
        month = str(aggregate.month)
        household = next(
            item for item in bundle.snapshots if item.month == month and item.sector == "households"
        )
        bank = next(
            item for item in bundle.snapshots if item.month == month and item.sector == "banks"
        )
        if (
            household.mortgage_principal != aggregate.total_mortgage_principal
            or household.deposits != aggregate.household_deposits
            or household.net_worth != aggregate.household_net_worth
            or bank.mortgage_principal != aggregate.total_mortgage_principal
        ):
            raise ValueError(f"replay stock reconciliation failed for {month}")
        payment_flow = sum(
            item.amount
            for item in bundle.flows
            if item.month == month and item.flow_type == "principal_and_interest"
        )
        if payment_flow != aggregate.debt_service:
            raise ValueError(f"replay payment-flow reconciliation failed for {month}")
