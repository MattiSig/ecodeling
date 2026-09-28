"""Typed household and bank registries for the micro simulation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ecodeling.accounting import ISK
from ecodeling.identifiers import AgentId, ContractId


class HomeownerStatus(StrEnum):
    """Mutually exclusive housing-tenure groups."""

    RENTER = "renter"
    DEBT_FREE = "debt_free_homeowner"
    MORTGAGED = "mortgaged_homeowner"


class LiquidityGroup(StrEnum):
    """Opening liquid-resource group used for behavior and reporting."""

    LOW = "low"
    MIDDLE = "middle"
    HIGH = "high"


class MortgageRegime(StrEnum):
    """Loan indexation regime for a household or complete run."""

    NONE = "none"
    NOMINAL = "nominal"
    INDEXED = "indexed"


@dataclass(frozen=True, slots=True)
class Household:
    """Reproducible opening attributes for one household."""

    id: AgentId
    bank_id: AgentId
    gross_monthly_income: ISK
    opening_deposits: ISK
    house_value: ISK
    opening_mortgage: ISK
    mortgage_id: ContractId | None
    homeowner_status: HomeownerStatus
    mortgage_regime: MortgageRegime
    income_quintile: int
    initial_ltv_quintile: int | None
    liquidity_group: LiquidityGroup
    consumption_propensity_bps: int


@dataclass(frozen=True, slots=True)
class Bank:
    """One mortgage lender and deposit-taking bank."""

    id: AgentId


class HouseholdRegistry:
    """Stable ordered registry of unique households."""

    def __init__(self, households: tuple[Household, ...]) -> None:
        """Validate and retain households in their declared order."""
        if not households:
            raise ValueError("household registry cannot be empty")
        ids = tuple(household.id for household in households)
        if len(ids) != len(set(ids)):
            raise ValueError("household IDs must be unique")
        self._households = households

    @property
    def households(self) -> tuple[Household, ...]:
        """Return households in stable initialization order."""
        return self._households


class BankRegistry:
    """Stable ordered registry of unique banks."""

    def __init__(self, banks: tuple[Bank, ...]) -> None:
        """Validate and retain banks in their declared order."""
        if not banks:
            raise ValueError("bank registry cannot be empty")
        ids = tuple(bank.id for bank in banks)
        if len(ids) != len(set(ids)):
            raise ValueError("bank IDs must be unique")
        self._banks = banks

    @property
    def banks(self) -> tuple[Bank, ...]:
        """Return banks in stable initialization order."""
        return self._banks
