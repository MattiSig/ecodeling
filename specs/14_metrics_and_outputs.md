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

## Interactive replay outputs

Each publishable run should be convertible into a versioned, browser-oriented replay bundle containing:

- a manifest with schema version, run ID, model version, commit, scenario, seed, units, and available months;
- monthly sector snapshots for households, firms, banks, government, central bank, and foreign sector;
- monthly sector-to-sector flows for wages, consumption, taxes, transfers, imports, credit, interest, and principal payments;
- typed events for shocks, indexation revaluations, policy-rate changes, arrears, defaults, and other narrative markers;
- representative-agent tracks with stable IDs and declared cohort labels;
- the aggregate and distributional series needed by synchronized charts;
- pairing metadata connecting nominal and indexed runs that share initialization and shock streams.

Representative agents should be selected deterministically from policy-relevant cohorts such as low-income/high-LTV borrowers, other mortgagors, renters, and debt-free households. They illustrate actual simulated paths; they are not synthetic personas assembled after the run.

## Replay integrity

The replay exporter must assert that:

- displayed sector stocks match the authoritative monthly outputs;
- aggregated visual flows match the underlying ledger within declared rounding tolerance;
- paired runs use the same timeline and intended common random streams;
- every visual event references its source month and event type;
- units, nominal/real status, and price base are explicit;
- missing data is represented as unavailable rather than silently replaced with zero.

Animations may simplify scale, timing within a month, and the number of visible agents. They must not invent transactions, causal links, or outcomes. A visual replay is an explanatory view of a run, not an additional empirical result.

## Storage formats

Use columnar analytical outputs such as Parquet for research and batch analysis. Produce a compact, schema-versioned JSON or equivalent web payload for published replays. Large household panels should remain outside the browser bundle; include only declared representative tracks and aggregates required by the experience.
