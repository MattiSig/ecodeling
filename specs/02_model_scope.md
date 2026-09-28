# Model Scope and Version Boundaries

## Objective of version 0.1

Version 0.1 exists to isolate one mechanism:

> **How does mortgage indexation alter the transmission of an externally generated inflation shock?**

Everything that does not materially contribute to that question should be simplified.

## Recommended scale

- 1,000 households
- 20 consumer-goods firms
- 2 banks
- 1 government
- 1 central bank
- 1 stylized foreign sector
- monthly time step
- 600 months for long-run experiments after stabilization/burn-in

These counts are engineering choices, not claims about the correct number of representative agents.

## Version 0.1 endogenous variables

At minimum:

- household employment and labor income;
- household consumption;
- mortgage balances;
- mortgage payments;
- firm production and employment;
- consumer-good prices;
- CPI;
- bank assets/equity;
- defaults;
- policy rate;
- exchange-rate/import-price shock process.

## Version 0.1 exogenous or simplified variables

Initially simplify:

- demographics;
- immigration/emigration;
- multiple consumption baskets;
- detailed pension system;
- equity markets;
- commercial real estate;
- international capital flows;
- endogenous bank runs;
- multiple currencies on private balance sheets;
- detailed tax code;
- household bargaining over wages;
- sophisticated expectations.

## Version roadmap

### V0.1 — Mortgage indexation laboratory

Only mortgages can be indexed. Housing stock is fixed or highly simplified. Imported inflation enters through firm input costs. Compare indexed and non-indexed debt.

### V0.2 — Wage and rent indexation

Add contract-specific indexation for wages and rents. This enables analysis of asymmetric versus symmetric household exposure.

### V0.3 — Banking mismatch and funding

Add indexed and nominal bank liabilities, richer funding costs, capital constraints, and explicit net indexed positions.

### V0.4 — Housing market

Add house transactions, construction, endogenous housing prices, LTV constraints, and mortgage origination.

### V0.5 — Government and pension indexation

Add indexed transfers, tax thresholds, pension claims, government debt, and fiscal feedback.

### V1.0 — Calibrated Iceland-style economy

Only after the mechanism-level versions are stable should the project attempt a more empirical Iceland calibration.

## Time resolution

Use **monthly periods** because:

- household debt service is naturally monthly;
- CPI is observed monthly;
- indexation commonly operates with a lag;
- monetary-policy changes can be mapped into monthly rules;
- monthly simulation exposes the distinction between immediate cash-flow effects and slow principal accumulation.

## Model philosophy

Prefer a transparent behavioral rule over a complicated optimized decision rule unless the added complexity changes the research question.

For example, a household consumption heuristic such as

\[
C_{i,t}=\min(\text{liquid resources},\ c_0 + c_y Y^{disp}_{i,t} + c_w NW_{i,t})
\]

is acceptable for V0.1 if it produces understandable behavior and respects cash constraints.

## Explicit simplification policy

Every simplification should be documented under one of three labels:

- **structural assumption** — an intended part of the economic model;
- **temporary simplification** — expected to be relaxed in a later version;
- **numerical convenience** — chosen to keep computation stable or efficient.

This distinction matters when interpreting results.
