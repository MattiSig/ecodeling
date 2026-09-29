# Ecodeling

Ecodeling is a specification-first project for an educational agent-based model of CPI indexation in a small open economy inspired by Iceland.

The model is designed to explore how the breadth, symmetry, and location of indexation affect the propagation of inflation shocks through households, firms, banks, government, housing, and monetary policy.

Read the [full specification and recommended reading order](specs/README.md).

Development proceeds one verified phase at a time using the checklist in the [build plan](build.md).
The repository-owned [`$build` skill](skills/build/SKILL.md) executes exactly one unchecked phase per invocation.
## Local development

Ecodeling requires Python 3.12 or newer and [uv](https://docs.astral.sh/uv/). Install the
locked project environment from a clean checkout:

```bash
uv sync --all-groups
```

Run the complete foundation quality suite:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

The initial command-line interface exposes the installed version and a foundation validation
check:

```bash
uv run ecodeling --version
uv run ecodeling validate
```

Simulation commands will be added in later build phases.

## Core reproducibility primitives

Phase 01 provides typed IDs, an immutable inclusive monthly clock, frozen Pydantic configuration,
canonical configuration hashing, and independent named NumPy random streams. A minimal run identity
can be constructed as follows:

```python
from ecodeling.config.schema import ModelConfig
from ecodeling.identifiers import ScenarioId
from ecodeling.model.clock import SimulationClock
from ecodeling.randomness import NamedRandomStreams, RandomStream

config = ModelConfig(scenario_id=ScenarioId("baseline"))
clock = SimulationClock.create(config.simulation.start_month, config.simulation.months)
shocks = NamedRandomStreams(config.simulation.seed).generator(RandomStream.SHOCKS)

print(clock.start, clock.stop)
print(config.configuration_hash())
print(shocks.bit_generator.random_raw())
```

Clock bounds are inclusive. Calling `advance()` returns a new clock, and advancing the final month
raises `ClockExhaustedError`. Each call to `generator()` returns a fresh generator at the stable
start of that named stream, so requesting other streams cannot perturb its sequence.

## Accounting kernel

All monetary positions and journal changes use exact integer Icelandic krónur (ISK). Iceland's
currency has no circulating fractional unit, so floats and booleans are rejected rather than
rounded. Positive posting amounts increase an account's natural asset, liability, or equity
balance; negative amounts decrease it.

The append-only `Ledger` reconstructs positions from typed `TransactionEntry` and
`RevaluationEntry` records. Before an entry is appended, it must balance for every affected agent,
change both sides of each financial claim equally, reference known accounts, preserve non-negative
positions unless an account explicitly permits otherwise, and use a unique entry ID. Failed entries
leave the ledger unchanged. `balance_sheet()`, `sector_balance_sheet()`,
`system_balance_sheet()`, and `assert_accounting_invariants()` expose the resulting agent, sector,
and closed-system identities without mutable balance fields.

## Mortgage contracts

`ContractRegistry` runs each mortgage through an explicit monthly opening state → lagged CPI
revaluation → cash-flow calculation → settlement → closing state lifecycle. Origination,
principal revaluation, and payment settlement are typed ledger entries. Mortgage assets and
liabilities, as well as the deposit movements used for cash settlement, are always posted to both
counterparties. Multi-entry periods are validated and appended atomically.

Contract rates and indexation shares use integer basis points; reference-index levels are positive
integers. The Phase 03 coupon is fixed for the contract, and interest uses that annual coupon
divided by 12; policy-rate reset rules arrive in a later phase. Annuity payments are recalculated
from the post-indexation principal and remaining term, and all monetary results round to whole ISK
with ties away from zero. The first payment is one month after origination, and the last payment
clears the remaining principal exactly. Early payoff is permitted when rounded amortization or
deflation reduces the balance sooner.

An indexation share of zero is nominal and needs no CPI observations. Positive shares use
`P[t-lag] / P[t-lag-1] - 1`; inflation and deflation are symmetric, with no implicit zero floor.
`MortgagePricing` documents the comparison rule: the indexed coupon includes the real rate,
credit/term spreads, and bank margin, while the nominal coupon additionally includes expected
inflation and its risk premium. These are mechanism-oriented assumptions, not empirical Icelandic
calibration claims.

## Household-bank micro simulation

Phase 04 adds a deterministic population of 1,000 heterogeneous households and two banks by
default. Initialization assigns housing tenure, mortgage LTV, liquidity, income quintile, and bank
from the named initialization stream. Every monthly deposit, mortgage, CPI revaluation, payment,
capitalized arrear, consumption flow, and default write-down is recorded in the ledger. Household,
required distributional-cohort, bank, and aggregate records retain whole-ISK stocks and flows.

Until firms and endogenous prices arrive in later phases, income and CPI are explicit external
paths. Income and consumption cross a declared external settlement boundary; CPI mortgage
revaluation never changes deposits. Arrears apply payments to interest first, capitalize unpaid
interest, and default after the configured persistent-arrears threshold. The initial default rule
uses zero collateral recovery, so the complete remaining loan is removed from both parties and the
loss reduces bank equity. This is a stylized mechanism assumption, not an empirical calibration.

```python
from ecodeling.config.schema import ModelConfig
from ecodeling.identifiers import ScenarioId
from ecodeling.micro import constant_external_paths, run_nominal_indexed_comparison

config = ModelConfig(scenario_id=ScenarioId("shared-cpi-comparison"))
paths = constant_external_paths(config, annual_inflation_bps=250)
pair = run_nominal_indexed_comparison(config, paths)

print(pair.nominal.aggregate_months[-1].total_mortgage_principal)
print(pair.indexed.aggregate_months[-1].total_mortgage_principal)
```

The comparison regenerates the same opening population from the common seed and feeds both runs
the same income and CPI observations. Only the documented nominal coupon versus indexed-principal
contract structure differs. Output metadata includes scenario, seed, canonical configuration hash,
run identity, regime, and exact timeline.

## Replay v0 accounting audit

Phase 05 provides a strict Pydantic replay-v0 contract in `ecodeling.reporting.replay`. The exporter
selects actual simulated representatives by a declared deterministic cohort rule, copies monthly
stocks and flows from authoritative outputs, and links representative CPI revaluations to the
source ledger entry and its mirrored borrower-liability/lender-asset postings. Export fails when
visible stocks, payment flows, tracks, timelines, or ledger references do not reconcile exactly.
Money is nominal whole ISK; CPI is an integer price index; unavailable fields remain absent or null
rather than being silently replaced with zero.

The checked `web/internal-audit/replay-v0.json` is a six-month, 20-household canonical fixture. To
regenerate it and run the small internal scrubber's tests:

```bash
uv run python scripts/generate_replay_v0.py
npm ci
npm test
npm run test:browser
```

The page is an internal vertical-slice audit tool, not the later public web component. It steps or
scrubs the completed replay without recalculating any economic transition in JavaScript.
