# Agent-Based Model of Verðtrygging in a Small Open Economy

## Purpose

This repository is a **specification pack** for building an educational agent-based macroeconomic model (ABM) of a small open economy inspired by Iceland. The main research question is:

> **How do the breadth, symmetry, and location of CPI indexation change the way inflation shocks propagate through households, firms, banks, government, housing, and monetary policy?**

The project treats **verðtrygging (price indexation)** as a property of contracts and balance-sheet relationships rather than as a property of an individual agent. A mortgage can be indexed while the borrower's wage is not; a bank can hold indexed assets while issuing nominal liabilities; a government can index benefits but not tax thresholds. These mismatches are expected to be central to the model's dynamics.

The first implementation should be deliberately small. The goal is **not** to reproduce Iceland perfectly in version 0.1. The goal is to build a stock-flow-consistent environment in which the indexation mechanism is explicit, testable, and understandable.

## Recommended reading order

| File | Topic | Why it matters |
|---|---|---|
| [01_research_question.md](01_research_question.md) | Research question and hypotheses | Defines what the model is trying to learn rather than assuming an answer. |
| [02_model_scope.md](02_model_scope.md) | Scope and version boundaries | Prevents the first implementation from becoming a national-accounting monster. |
| [03_indexation_contract_spec.md](03_indexation_contract_spec.md) | Core verðtrygging mechanism | Defines indexation as a reusable contract rule with intensity, lag, and reference index. |
| [04_agents.md](04_agents.md) | Agent types | Specifies households, firms, banks, government, central bank, and foreign sector. |
| [05_balance_sheets_and_sfc.md](05_balance_sheets_and_sfc.md) | Stock-flow consistency | Ensures every financial asset is someone else's liability and flows reconcile. |
| [06_markets_and_matching.md](06_markets_and_matching.md) | Markets | Defines labor, goods, credit, housing, and foreign-sector interactions. |
| [07_households.md](07_households.md) | Household behavior | Consumption, employment, debt service, default, housing, and heterogeneity. |
| [08_firms.md](08_firms.md) | Firm behavior | Pricing, production, hiring, markups, imported inputs, and investment. |
| [09_banks_and_credit.md](09_banks_and_credit.md) | Banks and lending | Loan pricing, credit constraints, indexed asset/liability mismatch, and losses. |
| [10_government_and_central_bank.md](10_government_and_central_bank.md) | Policy sector | Taxes, transfers, public debt, policy rates, and monetary transmission. |
| [11_prices_cpi_and_fx.md](11_prices_cpi_and_fx.md) | CPI and exchange rate | Defines how prices arise and how foreign shocks enter a small open economy. |
| [12_simulation_loop.md](12_simulation_loop.md) | Monthly execution order | Gives a deterministic sequence for each simulation step. |
| [13_shocks_and_scenarios.md](13_shocks_and_scenarios.md) | Experiments | Defines controlled shocks and indexation regimes using common random seeds. |
| [14_metrics_and_outputs.md](14_metrics_and_outputs.md) | Measurements | Specifies macro, distributional, bank, debt, and persistence metrics. |
| [15_calibration_iceland.md](15_calibration_iceland.md) | Iceland calibration strategy | Separates empirical calibration from stylized assumptions. |
| [16_validation_and_testing.md](16_validation_and_testing.md) | Tests and invariants | Defines accounting tests, unit tests, sanity checks, and validation criteria. |
| [17_implementation_architecture.md](17_implementation_architecture.md) | Software design | Suggests data structures, modules, reproducibility rules, and experiment tooling. |
| [18_v0_1_build_plan.md](18_v0_1_build_plan.md) | Minimal build plan | The recommended order for getting the first working model running. |
| [19_research_sources.md](19_research_sources.md) | Research notes and sources | Pointers to Icelandic institutions and AB-SFC literature used to ground the spec. |
| [20_blog_post_plan.md](20_blog_post_plan.md) | Future write-up | A structure for turning the model and results into an explanatory blog post. |
| [21_glossary.md](21_glossary.md) | Glossary | Defines economic and modeling terms used throughout the specification. |

## Core design principles

1. **Index contracts, not agents.** Every indexable relationship gets an indexation coefficient and lag.
2. **Do not compare indexed and nominal loans at identical nominal interest rates.** Inflation compensation must appear somewhere in the nominal contract.
3. **Keep the accounting stock-flow consistent.** An indexed increase in a borrower's principal is simultaneously an increase in the lender's asset.
4. **Prices should emerge from costs, demand, capacity, and pricing rules.** Do not mechanically index every consumer price to CPI.
5. **Use identical shocks when comparing regimes.** Structural changes should be isolated using common random numbers/seeds.
6. **Measure distribution as well as aggregates.** Indexation can redistribute risk and wealth even if GDP barely changes.
7. **Treat conclusions as model-dependent.** The simulation is a laboratory for mechanisms, not an oracle about policy.

## Version 0.1 in one paragraph

The smallest useful model contains roughly 1,000 households, 20 domestic firms, 2 banks, a government, a central bank, and a stylized foreign sector. It runs monthly. Households earn wages, consume, and some own homes financed by mortgages. Firms hire labor, use imported and domestic inputs, and set consumer prices. Banks issue indexed or nominal mortgages. A foreign-price/exchange-rate shock raises import costs and CPI. The central bank follows a simple policy rule. The experiment compares otherwise identical simulations in which mortgage indexation varies from 0 to 1, while loan pricing remains economically consistent. The first outputs are CPI, consumption, mortgage balances, debt service, defaults, bank equity, and the policy rate.

## Definition of done for the first milestone

The first milestone is complete when:

- the economy can initialize with balance sheets that reconcile;
- households, firms, and banks transact for at least 600 monthly steps without numerical failure;
- CPI is calculated endogenously from market prices;
- at least one inflation shock can be injected;
- mortgages can be run with `alpha_indexation = 0` and `alpha_indexation = 1`;
- indexed principal changes appear on both borrower and lender balance sheets;
- the same random seed produces the same run;
- regime comparisons use the same shock sequence;
- output tables contain the required core metrics;
- unit tests verify accounting identities and contract update rules.

## Naming convention

Use `alpha` for indexation intensity, `pi` for inflation, `P` for price level/CPI, `B` for loan principal, `i` for nominal interest rates, `r` for real interest rates, and `t` for monthly time steps.

The project is intentionally written as a **spec first**. Code should be allowed to change; the economic contracts, invariants, and experiment definitions should change only deliberately and transparently.
