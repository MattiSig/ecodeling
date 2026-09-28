# Prices, CPI, and the Exchange Rate

## CPI construction

V0.1 can calculate CPI from firm prices using expenditure weights:

\[
CPI_t=\sum_j \omega_{j,t} P_{j,t}
\]

For a single generic good, CPI may simply be the sales-weighted average price normalized to 100 at initialization.

A multi-category CPI can be introduced later.

## Inflation

Monthly inflation:

\[
\pi^{m}_t=\frac{CPI_t}{CPI_{t-1}}-1
\]

Annual inflation:

\[
\pi^{12m}_t=\frac{CPI_t}{CPI_{t-12}}-1
\]

Do not mix monthly and annual units in contract updates or policy rules.

## Financial indexation CPI

The model should explicitly support a lag between measured CPI and the value used for financial indexation.

Example abstraction:

```text
published_cpi[t] = CPI measured for month t
indexation_reference[t] = published_cpi[t - L]
```

A two-month lag is a reasonable Iceland-inspired starting point for experiments, but it should be a parameter, not hard-coded universal truth.

## Exchange rate

Define:

\[
E_t = \text{ISK per unit of foreign currency}
\]

Therefore:

\[
E_t \uparrow \Rightarrow \text{domestic currency depreciation}
\]

Import price:

\[
P^{imp}_t=E_tP^*_t
\]

## V0.1 exchange-rate process

For the first controlled experiment, make the exchange-rate shock exogenous:

```text
E[t] = baseline process
at shock_month: E[t] *= 1.10
then persistence/mean reversion follows configured path
```

This makes causal interpretation easier.

## Later semi-endogenous process

Possible extension:

\[
\Delta \log E_t=f(i^*_t-i_t,\ tradeBalance_t,\ riskPremium_t,\ expectations_t)+\epsilon_t
\]

Do not add this until the primary indexation mechanism is stable.

## Housing in CPI

If owner-occupied housing is later included in CPI, document exactly how. Housing can create additional feedback between asset prices and indexation, but it should not be introduced casually because it can dominate model dynamics.

## Important circularity check

CPI can index **contracts**, whose effects may feed into firm costs and therefore future prices. That feedback is legitimate.

CPI should not directly update the same consumer prices used to calculate CPI unless that price is explicitly governed by an indexed contract.

## Acceptance criteria

- a 10% exchange-rate depreciation raises import prices by 10% when foreign prices are unchanged;
- firms with zero import share are not directly affected by import prices;
- CPI inflation is derived from actual market prices;
- indexation uses the configured lagged CPI series;
- annual inflation calculations are correct after 12 months of data.
