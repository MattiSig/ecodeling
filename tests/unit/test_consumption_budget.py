"""Economic behavior of disposable-income and liquid-wealth consumption."""

from ecodeling.economy.simulation import consumption_budget


def test_unemployed_household_can_draw_savings_without_spending_unavailable_cash() -> None:
    assert (
        consumption_budget(
            opening_deposits=450_000,
            available_cash=450_000,
            disposable_income=0,
            income_propensity_bps=10_000,
            wealth_propensity_bps=500,
        )
        == 22_500
    )
    assert (
        consumption_budget(
            opening_deposits=450_000,
            available_cash=1_000,
            disposable_income=0,
            income_propensity_bps=10_000,
            wealth_propensity_bps=500,
        )
        == 1_000
    )


def test_debt_service_reduces_budget_and_dividends_can_support_consumption() -> None:
    def budget(income: int) -> int:
        return consumption_budget(
            opening_deposits=450_000,
            available_cash=600_000,
            disposable_income=income,
            income_propensity_bps=10_000,
            wealth_propensity_bps=500,
        )

    assert budget(450_000 - 100_000) == 372_500
    assert budget(450_000 - 100_000 + 20_000) == 392_500
    assert budget(-50_000) == 22_500
