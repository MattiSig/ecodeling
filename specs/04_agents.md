# Agent Types

## Household agents

Households supply labor, receive income, consume, save, rent or own housing, service debt, and may default.

Suggested state:

```text
id
age_group_optional
employment_status
employer_id
monthly_wage
liquid_deposits
home_value
mortgage_contract_id_optional
rent_contract_id_optional
other_debt
net_worth
consumption_propensity
wealth_propensity
risk_aversion_optional
expected_inflation
```

V0.1 heterogeneity should include at least:

- renters;
- mortgaged homeowners;
- debt-free homeowners;
- low/medium/high income groups;
- differing marginal propensities to consume;
- differing LTV or debt-to-income positions.

## Firm agents

V0.1 can use one consumer-goods sector with heterogeneous firms.

Suggested state:

```text
id
cash
bank_deposits
bank_loans_optional
workers
wage_offer
inventory
productive_capacity
productivity
price
markup_target
import_input_share
expected_demand
```

Later versions should split firms into domestic/non-tradable and trade-exposed sectors.

## Bank agents

Banks originate mortgages, hold loan assets, fund themselves through deposits and optionally bonds, receive payments, absorb defaults, and are constrained by liquidity/capital rules.

Suggested state:

```text
id
cash_or_reserves
household_loans
firm_loans
indexed_assets
nominal_assets
deposits
indexed_liabilities
nominal_liabilities
equity
capital_ratio
credit_policy
mortgage_rates
```

## Government

The government collects taxes, pays transfers, purchases goods if included, and may issue debt.

V0.1 can keep fiscal policy simple and broadly stabilizing.

Suggested state:

```text
tax_revenue
transfer_spending
government_consumption
debt
cash_account
```

## Central bank

The central bank sets the policy rate and optionally provides reserves/liquidity to banks.

Suggested state:

```text
policy_rate
inflation_target
neutral_real_rate
policy_rule_parameters
```

V0.1 does not need a full central-bank balance sheet unless required for stock-flow closure.

## Foreign sector

The foreign sector should initially be a compact shock generator and trading counterparty.

Suggested state/processes:

```text
foreign_price_level
foreign_interest_rate
exchange_rate_or_fx_shock
export_demand
```

V0.1 may treat the exchange rate as exogenous or semi-exogenous. Later versions can endogenize it through interest differentials, trade flows, expectations, or portfolio choice.

## Agent population initialization

Initialization should create economically plausible distributions rather than identical clones.

Recommended approach:

1. choose population shares by household type;
2. draw incomes from a positive skewed distribution;
3. assign employment and firms;
4. assign tenure status;
5. assign house values and LTVs to mortgaged owners;
6. create corresponding bank loan assets;
7. assign deposits and ensure bank liabilities match household deposit assets;
8. verify aggregate balance-sheet identities before period 0.

## Design rule

State belongs to agents. Terms governing relationships belong to contracts.

Example: a household has a `mortgage_contract_id`; the interest rate, principal, indexation coefficient, and maturity belong to the mortgage contract rather than being copied into household state.
