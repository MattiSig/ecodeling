# Iceland Calibration Strategy

## Principle

Calibration should occur in layers. Do not import a large number of Icelandic statistics before the mechanism works.

Use three labels for every parameter:

1. **empirical** — directly tied to a documented statistic;
2. **stylized** — chosen to represent a plausible mechanism;
3. **numerical** — chosen for stability/scale rather than realism.

## Early empirical anchors

Useful Iceland-inspired quantities include:

- share of household debt that is CPI indexed;
- typical indexed versus non-indexed mortgage rate structure;
- mortgage maturity and amortization conventions;
- inflation and policy-rate history;
- household debt/income distribution;
- homeownership and mortgage prevalence;
- bank funding composition;
- import share of consumption/production;
- wage growth and unemployment;
- CPI methodology and financial-indexation lag.

## Evidence snapshot relevant to this project

As of the IMF's 2026 Article IV staff report, CPI-indexed loans represented **54% of outstanding household debt**, and the report states that their prevalence had cushioned the immediate impact of high nominal rates on borrowers. This is a strong reason to model the cash-flow timing channel explicitly.

Statistics Iceland publishes a CPI that is used for financial indexation with a lag. For example, its May 2026 CPI release stated that the index measured in May was applicable for indexation purposes in July 2026. This supports a parameterized lag structure in the model.

IMF financial-sector analysis from 2023 noted that Icelandic banks held more indexed assets than indexed liabilities in the data it examined, creating a positive net inflation-indexed position. It also highlighted the contrast between short-run lower interest burden on indexed mortgages and the possibility that inflation added to principal can produce negative amortization and erode borrower equity.

These facts are **calibration clues**, not instructions to hard-code a result.

## Calibration workflow

### Phase A — mechanism calibration

Choose simple parameters that produce:

- stable production;
- nonzero unemployment;
- plausible but not explosive debt service;
- positive bank equity;
- low stable inflation absent shocks.

### Phase B — moment matching

Match a limited set of macro moments:

- average inflation;
- inflation volatility;
- unemployment;
- debt/income;
- mortgage share;
- bank capital ratio;
- consumption/income.

### Phase C — distribution matching

Match household distributions:

- income;
- liquid wealth;
- mortgage balances;
- LTV;
- debt service.

### Phase D — dynamic validation

Check that simulated responses to historical-style shocks are qualitatively plausible without tuning directly to the desired indexation conclusion.

## Scaling a small synthetic population

If 1,000 households represent the economy, attach a population weight:

```text
household_weight = real_household_population / 1000
```

Use weights for aggregate monetary quantities while behavioral decisions remain at agent level.

## Avoid overfitting

The objective is not to tune the indexed regime until it resembles one historical episode and then claim confirmation. Parameters should be chosen independently of the comparative result whenever possible.

## Sensitivity requirement

Any substantive conclusion about indexation should survive reasonable ranges for:

- expected inflation;
- consumption propensity;
- loan maturity;
- indexation lag;
- price stickiness;
- policy-rule response;
- import share;
- default threshold.
