# Version 0.1 Build Plan

## Goal

Get the smallest scientifically useful model running before adding realism.

## Milestone 1 — Accounting skeleton

Implement:

- agent IDs and registries;
- deposits;
- bank deposit liabilities;
- mortgage asset/liability pair;
- transaction ledger;
- revaluation ledger;
- accounting assertions.

**Done when:** creating and transferring 1 ISK never breaks balance-sheet identities.

## Milestone 2 — Mortgage contract engine

Implement:

- opening principal;
- indexation coefficient;
- lag;
- interest calculation;
- amortization/payment;
- closing principal;
- borrower/lender mirrored updates.

Test the contract in isolation before any macro economy exists.

**Done when:** hand-calculated 12-month examples match the code.

## Milestone 3 — Household + bank micro simulation

Create 1,000 households and 2 banks with heterogeneous mortgages and incomes.

Initially keep incomes exogenous.

Inject an exogenous CPI path and compare nominal/indexed contracts.

This is an important intermediate experiment because it isolates contract mechanics from macro feedback.

**Done when:** you can graph cash payments, principal, net worth, and bank assets under the same CPI path.

## Milestone 4 — Firms and goods market

Add:

- 20 firms;
- employment;
- production;
- pricing;
- household consumption;
- endogenous consumer price level.

**Done when:** the model produces a stable CPI under no shock and responds to a cost shock.

## Milestone 5 — Foreign/import shock

Add exchange rate and import cost process.

Run:

\[
FX \rightarrow ImportCost \rightarrow Price \rightarrow CPI
\]

without mortgage indexation first.

**Done when:** a depreciation produces an interpretable inflation response.

## Milestone 6 — Close the indexation feedback

Feed lagged endogenous CPI into indexed mortgage principals.

Now the complete V0.1 mechanism exists:

\[
FX \rightarrow ImportPrices \rightarrow CPI \rightarrow IndexedDebt \rightarrow Household/BankBalanceSheets \rightarrow Consumption/Credit \rightarrow Economy
\]

**Done when:** nominal and indexed scenarios run from common seeds and produce paired outputs.

## Milestone 7 — Central bank

Add a simple inflation-response rule and interest-rate pass-through.

Be explicit about which mortgage rates reset and when.

**Done when:** monetary tightening changes nominal debt-service dynamics and comparative results remain numerically stable.

## Milestone 8 — Monte Carlo experiments

Run many paired seeds for:

- `alpha=0`;
- `alpha=1`;
- alpha sweep 0–1.

Produce distributions, not just one illustrative path.

## Milestone 9 — Sensitivity

Vary:

- shock size;
- indexation lag;
- import share;
- loan maturity;
- price stickiness;
- monetary-policy response;
- expected inflation assumption;
- household consumption propensity.

## What not to build yet

Do not add these before Milestone 6 works:

- endogenous housing transactions;
- wage indexation;
- rent indexation;
- pension funds;
- detailed Iceland tax law;
- endogenous exchange-rate market;
- sophisticated household optimization;
- firm entry/exit network effects.

## First publishable figure set

A very strong first mechanism post could use six paired charts around the shock date:

1. CPI inflation;
2. policy rate;
3. household mortgage principal;
4. household debt service;
5. real consumption;
6. bank equity/default losses.

Then include one distributional figure comparing low-income/high-LTV borrowers with wealthy/debt-free households.

## First research checkpoint

Before adding wage indexation, be able to explain in plain language every divergence between the indexed and nominal runs. If a divergence cannot be traced to a ledger event, behavioral rule, or feedback channel, the model is not yet understood well enough to expand.
