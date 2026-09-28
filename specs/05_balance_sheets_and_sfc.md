# Balance Sheets and Stock-Flow Consistency

## Why stock-flow consistency is required

Indexation directly changes nominal values on balance sheets. Without explicit double-entry logic, the model can accidentally create or destroy financial wealth.

Every financial asset must be another agent's liability.

## Core balance-sheet relationships

### Household mortgage

Household:

- liability: mortgage principal \(B\)

Bank:

- asset: mortgage principal \(B\)

If indexation increases principal by 100,000 ISK:

```text
Household mortgage liability  +100,000
Bank mortgage asset           +100,000
```

No cash transaction is required for the revaluation itself.

### Deposit

Household:

- asset: deposit balance

Bank:

- liability: deposit balance

A wage payment from firm to household should transfer deposits, not create a one-sided household asset.

### Wage

```text
Firm cash/deposit     - wage payment
Household deposit     + wage payment
Firm wage expense      recorded in flow accounts
Household labor income recorded in flow accounts
```

### Consumption

```text
Household deposit - purchase
Firm deposit      + purchase
Household consumption expenditure = Firm sales revenue
```

## Suggested sector balance sheets

| Sector | Assets | Liabilities / Equity |
|---|---|---|
| Households | deposits, housing | mortgages, other debt, net worth |
| Firms | deposits, inventories/capital | bank loans, equity |
| Banks | reserves/cash, mortgages, firm loans | deposits, bonds, equity |
| Government | optional financial assets | government debt, net worth |
| Foreign | claims on domestic economy | domestic claims on foreign sector |

## Financial net wealth invariant

For a closed set of domestic financial claims:

\[
\sum_i FinancialAssets_i - \sum_i FinancialLiabilities_i = 0
\]

Real assets such as houses and productive capital can create positive sector net worth, but internal financial claims must cancel.

With a foreign sector, domestic net financial wealth can differ from zero only because of net foreign assets/liabilities.

## Flow consistency

Every payment should be recorded from both perspectives.

Examples:

\[
HouseholdConsumption = FirmSales
\]

\[
HouseholdWageIncome = FirmWageExpense
\]

\[
BankInterestIncome = BorrowerInterestExpense
\]

\[
GovernmentTransfers = HouseholdTransferIncome
\]

## Revaluation account

It is useful to separate **transactions** from **revaluations**.

Indexation is primarily a revaluation of a financial contract, not a current-period cash payment.

Track:

```text
opening_balance
+ transaction_flows
+ indexation_revaluation
+ other_revaluation
= closing_balance
```

This distinction will be important in the blog write-up because it makes the cash-flow vs balance-sheet channel visible.

## Default accounting

When a borrower defaults, do not simply delete the liability.

A stylized sequence:

1. bank recognizes expected loss/write-down;
2. borrower liability is reduced or restructured according to default rule;
3. bank equity absorbs the loss;
4. collateral recovery, if modeled, transfers housing value or sale proceeds.

## Required automated checks

Run after every month in debug mode:

- total household deposits = corresponding bank deposit liabilities;
- total mortgage liabilities = total mortgage assets;
- total wage income = wage expense;
- total consumption expenditure = sales revenue, allowing for taxes if modeled;
- transaction ledgers sum to zero across counterparties;
- balance-sheet equation holds for every agent;
- no NaN or impossible negative quantity unless explicitly permitted.

## Tolerance

Floating-point reconciliation should use a documented tolerance, e.g.:

```text
abs(accounting_gap) < 1e-8 * max(1, economy_scale)
```

Never fix persistent accounting gaps by widening the tolerance.
