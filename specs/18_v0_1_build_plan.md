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

## Milestone 4 — Visual audit prototype

Build a deliberately plain internal replay view for the household-and-bank experiment. It should step through months and show mortgage principal, payments, revaluations, household net worth, and mirrored bank assets.

This is a correctness tool, not the final public artwork.

**Done when:** selecting a visible change reveals the source ledger event and both sides of the accounting entry.

## Milestone 5 — Firms and goods market

Add:

- 20 firms;
- employment;
- production;
- pricing;
- household consumption;
- endogenous consumer price level.

**Done when:** the model produces a stable CPI under no shock and responds to a cost shock.

## Milestone 6 — Foreign/import shock

Add exchange rate and import cost process.

Run:

\[
FX \rightarrow ImportCost \rightarrow Price \rightarrow CPI
\]

without mortgage indexation first.

**Done when:** a depreciation produces an interpretable inflation response.

## Milestone 7 — Close the indexation feedback

Feed lagged endogenous CPI into indexed mortgage principals.

Now the complete V0.1 mechanism exists:

\[
FX \rightarrow ImportPrices \rightarrow CPI \rightarrow IndexedDebt \rightarrow Household/BankBalanceSheets \rightarrow Consumption/Credit \rightarrow Economy
\]

**Done when:** nominal and indexed scenarios run from common seeds and produce paired outputs.

## Milestone 8 — Central bank

Add a simple inflation-response rule and interest-rate pass-through.

Be explicit about which mortgage rates reset and when.

**Done when:** monetary tightening changes nominal debt-service dynamics and comparative results remain numerically stable.

## Milestone 9 — Public animated explainer

Export a canonical paired run through the versioned replay contract and build the browser experience defined in `22_interactive_web_experience.md`.

The first public version should include guided story playback, free timeline scrubbing, nominal/indexed comparison, synchronized charts, and inspectable representative households.

**Done when:** every visible stock, flow, and event can be traced to the replay bundle and the experience works on desktop and mobile with a reduced-motion fallback.

## Milestone 10 — Monte Carlo experiments

Run many paired seeds for:

- `alpha=0`;
- `alpha=1`;
- alpha sweep 0–1.

Produce distributions, not just one illustrative path.

## Milestone 11 — Sensitivity

Vary:

- shock size;
- indexation lag;
- import share;
- loan maturity;
- price stickiness;
- monetary-policy response;
- expected inflation assumption;
- household consumption propensity.

## Milestone 12 — Reader laboratory

Allow readers to submit a bounded set of parameters to the server-side Python runner. Cache completed results by model version and configuration hash, then load them into the same replay and chart components used by the canonical article.

**Done when:** invalid or excessive runs are rejected, identical requests reuse cached results, and every returned run carries complete reproducibility metadata.

## What not to build yet

Do not add these before Milestone 7 works:

- endogenous housing transactions;
- wage indexation;
- rent indexation;
- pension funds;
- detailed Iceland tax law;
- endogenous exchange-rate market;
- sophisticated household optimization;
- firm entry/exit network effects.

## First publishable experience

The first mechanism post should lead with the animated economy and use six synchronized paired charts around the shock date:

1. CPI inflation;
2. policy rate;
3. household mortgage principal;
4. household debt service;
5. real consumption;
6. bank equity/default losses.

Then include one distributional figure comparing low-income/high-LTV borrowers with wealthy/debt-free households.

The canonical animation should show the foreign-price or exchange-rate shock moving through import costs, firm prices, CPI, indexed principal, household balance sheets, consumption, and banks. It must replay the same underlying paired runs used by the charts.

## First research checkpoint

Before adding wage indexation, be able to explain in plain language every divergence between the indexed and nominal runs. If a divergence cannot be traced to a ledger event, behavioral rule, or feedback channel, the model is not yet understood well enough to expand.
