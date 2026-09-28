# Banks and Credit

## Purpose

Banks are essential because mortgage indexation is simultaneously a household liability mechanism and a bank asset mechanism.

## Bank balance sheet

A minimal bank has:

### Assets

- reserves/cash;
- indexed mortgages;
- nominal mortgages;
- optional firm loans.

### Liabilities

- household/firm deposits;
- optional wholesale bonds;
- equity as residual.

## Indexed position

Track:

\[
NetIndexedPosition_b = IndexedAssets_b - IndexedLiabilities_b
\]

This metric should be available even before indexed deposits are implemented; in V0.1 indexed liabilities may be zero.

## Mortgage pricing

### Indexed product

Stylized rate:

\[
r^{idx}=r^*+creditSpread+termSpread+bankMargin
\]

CPI indexation changes principal separately.

### Nominal product

Stylized rate:

\[
i^{nom}=r^*+E[\pi]+inflationRiskPremium+creditSpread+termSpread+bankMargin
\]

The objective is not to reproduce exact market pricing, but to prevent the baseline comparison from pretending expected inflation is free on nominal loans.

## Fixed versus floating rates

V0.1 should choose one clean comparison and document it.

Recommended first comparison:

- indexed loan: fixed real coupon for a specified reset period;
- nominal loan: nominal rate reset from policy rate + spreads at a chosen frequency.

Later experiments can separately vary interest-rate fixation from indexation. Do not conflate the two concepts in interpretation.

## Credit constraints

If V0.1 includes origination, bank approval can use:

### Loan-to-value

\[
LTV=\frac{Loan}{HouseValue}
\]

### Debt service to income

\[
DSTI=\frac{MonthlyDebtService}{MonthlyGrossIncome}
\]

Use stylized thresholds initially; empirical Icelandic rules belong in calibration versions.

## Defaults

When a household defaults:

1. bank marks down the mortgage asset;
2. loss reduces bank equity;
3. collateral recovery is applied if modeled;
4. household debt is resolved under the default rule.

## Capital constraint

A simple bank capital ratio:

\[
CapitalRatio_b=\frac{Equity_b}{RiskWeightedAssets_b}
\]

V0.1 can use mortgage risk weight = 1 for simplicity and block new lending below a minimum capital ratio.

## Funding costs

Initially, deposit interest may follow policy rate with a pass-through coefficient:

\[
i^{deposit}_t=\beta_d i^{policy}_t
\]

Later versions should distinguish nominal and indexed funding.

## Why bank mismatch matters

If inflation raises indexed mortgage assets while deposits remain nominal, bank nominal equity can mechanically increase before credit losses. At the same time, borrower leverage worsens. The model must record both effects rather than treating indexation as a pure transfer-free accounting trick.

## Acceptance criteria

- total mortgage assets equal borrower mortgage liabilities;
- CPI indexation increases bank indexed assets exactly as it increases household liabilities;
- bank equity falls when loan losses are recognized;
- bank cannot lend unlimited amounts if a capital rule is active;
- nominal and indexed loan pricing use distinct, documented formulas.
