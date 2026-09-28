"""Reusable account and registry builders for isolated mortgage tests."""

from dataclasses import dataclass

from ecodeling.accounting import (
    Account,
    AccountKind,
    Ledger,
    Posting,
    Sector,
    TransactionEntry,
)
from ecodeling.contracts import (
    ContractRegistry,
    IndexObservation,
    MortgageContract,
    ReferenceIndex,
)
from ecodeling.identifiers import (
    AccountId,
    AgentId,
    ContractId,
    LedgerEntryId,
    ReferenceIndexId,
)
from ecodeling.model.clock import YearMonth


@dataclass(frozen=True, slots=True)
class MortgageEnvironment:
    """An isolated borrower, bank, ledger, contract, and registry."""

    ledger: Ledger
    contract: MortgageContract
    registry: ContractRegistry


def reference_index(
    first_month: YearMonth,
    levels: tuple[int, ...],
) -> ReferenceIndex:
    """Build consecutive monthly integer reference-index observations."""
    return ReferenceIndex(
        ReferenceIndexId("cpi"),
        tuple(
            IndexObservation(first_month.add_months(offset), level)
            for offset, level in enumerate(levels)
        ),
    )


def build_mortgage_environment(
    *,
    contract_id: str = "mortgage-1",
    principal: int = 120_000,
    annual_rate_bps: int = 600,
    alpha_bps: int = 10_000,
    lag_months: int = 2,
    term_months: int = 12,
    index: ReferenceIndex | None = None,
    extra_cash: int = 120_000,
) -> MortgageEnvironment:
    """Build and originate one mortgage with enough optional payment liquidity."""
    ledger = Ledger()
    borrower_id = AgentId("household-1")
    lender_id = AgentId("bank-1")
    mortgage_id = ContractId(contract_id)
    deposit_claim = ContractId("household-1-deposit")
    accounts = (
        Account(
            AccountId("household-1-deposit"),
            borrower_id,
            Sector.HOUSEHOLDS,
            "Household deposit",
            AccountKind.FINANCIAL_ASSET,
            deposit_claim,
        ),
        Account(
            AccountId("bank-1-household-1-deposit"),
            lender_id,
            Sector.BANKS,
            "Household deposit liability",
            AccountKind.LIABILITY,
            deposit_claim,
        ),
        Account(
            AccountId("household-1-mortgage"),
            borrower_id,
            Sector.HOUSEHOLDS,
            "Mortgage liability",
            AccountKind.LIABILITY,
            mortgage_id,
        ),
        Account(
            AccountId("bank-1-mortgage"),
            lender_id,
            Sector.BANKS,
            "Mortgage asset",
            AccountKind.FINANCIAL_ASSET,
            mortgage_id,
        ),
        Account(
            AccountId("household-1-equity"),
            borrower_id,
            Sector.HOUSEHOLDS,
            "Household equity",
            AccountKind.EQUITY,
            allow_negative=True,
        ),
        Account(
            AccountId("bank-1-equity"),
            lender_id,
            Sector.BANKS,
            "Bank equity",
            AccountKind.EQUITY,
            allow_negative=True,
        ),
        Account(
            AccountId("bank-1-operating-asset"),
            lender_id,
            Sector.BANKS,
            "Bank operating asset",
            AccountKind.REAL_ASSET,
            allow_negative=True,
        ),
    )
    for account in accounts:
        ledger.register_account(account)

    if extra_cash > 0:
        ledger.post(
            TransactionEntry(
                LedgerEntryId("opening-payment-liquidity"),
                YearMonth(2025, 1),
                "Fund borrower payment liquidity",
                (
                    Posting(AccountId("household-1-deposit"), extra_cash),
                    Posting(AccountId("household-1-equity"), extra_cash),
                    Posting(AccountId("bank-1-operating-asset"), extra_cash),
                    Posting(AccountId("bank-1-household-1-deposit"), extra_cash),
                ),
            )
        )

    contract = MortgageContract(
        id=mortgage_id,
        borrower_id=borrower_id,
        lender_id=lender_id,
        principal=principal,
        annual_rate_bps=annual_rate_bps,
        alpha_bps=alpha_bps,
        indexation_lag_months=lag_months,
        reference_index_id=ReferenceIndexId("cpi"),
        start_month=YearMonth(2025, 1),
        term_months=term_months,
        borrower_deposit_account_id=AccountId("household-1-deposit"),
        lender_deposit_account_id=AccountId("bank-1-household-1-deposit"),
        borrower_mortgage_account_id=AccountId("household-1-mortgage"),
        lender_mortgage_account_id=AccountId("bank-1-mortgage"),
        borrower_equity_account_id=AccountId("household-1-equity"),
        lender_equity_account_id=AccountId("bank-1-equity"),
    )
    registry = ContractRegistry(
        ledger,
        (index or ReferenceIndex(ReferenceIndexId("cpi"), ()),),
    )
    registry.register_mortgage(contract)
    ledger.assert_accounting_invariants()
    return MortgageEnvironment(ledger, contract, registry)
