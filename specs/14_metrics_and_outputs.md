# Metrics and Outputs

## Core philosophy

A model of indexation should not be evaluated only with GDP. It changes timing, risk allocation, leverage, and distribution.

## V0.1 required time series

### Prices and macro activity

- CPI level;
- monthly inflation;
- 12-month inflation;
- output/production;
- employment/unemployment;
- aggregate real consumption;
- policy rate;
- exchange rate/import price index.

### Household finance

- average and median mortgage principal;
- total mortgage stock;
- indexed revaluation amount;
- debt service;
- debt-service-to-income ratio;
- debt-to-income ratio;
- LTV if house values exist;
- household deposits;
- household net worth;
- arrears/default rate.

### Banking

- total loans;
- indexed assets;
- nominal assets;
- net indexed position;
- bank equity;
- capital ratio;
- interest income;
- credit losses;
- loan origination if modeled.

## Distributional reporting

At minimum, calculate results by:

- income quintile;
- homeowner status;
- indexed vs nominal borrowers;
- initial LTV group;
- liquidity group.

Useful differences:

\[
\Delta C_{bottom20\%}
\]

\[
\Delta NW_{mortgaged}-\Delta NW_{debtfree}
\]

\[
DefaultRate_{indexed}-DefaultRate_{nominal}
\]

## Inflation persistence

Possible measures:

- time until inflation returns within `x` percentage points of target;
- cumulative inflation above baseline;
- AR(1)-style estimated persistence on simulated inflation;
- half-life of the shock response.

Do not rely on only one persistence statistic.

## Cash-flow vs balance-sheet decomposition

This is a key output.

For indebted households, separately report:

### Cash-flow burden

\[
DebtService_t / Income_t
\]

### Balance-sheet burden

\[
MortgagePrincipal_t / Income_t
\]

and:

\[
MortgagePrincipal_t / HouseValue_t
\]

when house values are modeled.

### Indexation revaluation

\[
Revaluation_t=B_t^{after\ indexation}-B_{t-1}^{before\ indexation}
\]

This makes it possible to show that two regimes can have similar lifetime costs but very different timing—or genuinely different outcomes due to behavior/defaults.

## Welfare caution

Do not create a single "welfare score" in early versions. It would embed strong normative assumptions.

Instead report a vector of outcomes such as:

- consumption volatility;
- cumulative consumption;
- defaults;
- net worth;
- unemployment exposure;
- bank losses;
- inflation persistence.

## Impulse-response style plots

For each regime, plot deviations from its no-shock counterfactual:

\[
IRF_M(t)=M^{shock}(t)-M^{baseline}(t)
\]

Then compare IRFs across indexation regimes. This controls for any structural steady-state differences between the regimes.

## Reproducibility metadata

Every output file should include or reference:

```text
model_version
git_commit
scenario_id
seed
parameter_set
start_date_or_simulation_month
shock_definition
indexation_topology
```
