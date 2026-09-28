"""Twelve-month hand-calculated mortgage golden fixtures."""

import json
from pathlib import Path
from typing import TypedDict, cast

from tests.mortgage_support import build_mortgage_environment, reference_index

from ecodeling.identifiers import AccountId, ContractId
from ecodeling.model.clock import YearMonth


class GoldenCase(TypedDict):
    """One nominal or indexed hand-calculated fixture case."""

    name: str
    annual_rate_bps: int
    alpha_bps: int
    expected: list[list[int]]


class GoldenFixture(TypedDict):
    """Shared CPI path and the three contract cases."""

    principal: int
    reference_levels: list[int]
    cases: list[GoldenCase]


def test_twelve_month_nominal_partial_and_full_indexation_golden() -> None:
    fixture_path = Path(__file__).parents[1] / "fixtures" / "mortgage_12_month_golden.json"
    fixture = cast(GoldenFixture, json.loads(fixture_path.read_text()))
    index = reference_index(
        YearMonth(2024, 11),
        tuple(fixture["reference_levels"]),
    )

    for case in fixture["cases"]:
        environment = build_mortgage_environment(
            contract_id=case["name"],
            principal=fixture["principal"],
            annual_rate_bps=case["annual_rate_bps"],
            alpha_bps=case["alpha_bps"],
            lag_months=2,
            term_months=12,
            index=index,
            extra_cash=fixture["principal"],
        )
        actual: list[list[int]] = []
        for offset in range(1, 13):
            period = environment.registry.advance(
                ContractId(case["name"]),
                YearMonth(2025, 1).add_months(offset),
            )
            actual.append(
                [
                    period.opening_principal,
                    period.indexation_revaluation,
                    period.preflow_principal,
                    period.interest,
                    period.scheduled_payment,
                    period.principal_payment,
                    period.closing_principal,
                ]
            )
            assert period.settlement_entry_id is not None
            if period.indexation_revaluation != 0:
                assert period.revaluation_entry_id is not None
            environment.ledger.assert_accounting_invariants()

        assert actual == case["expected"]
        assert environment.ledger.balance(AccountId("household-1-mortgage")) == 0
        assert environment.ledger.balance(AccountId("bank-1-mortgage")) == 0
