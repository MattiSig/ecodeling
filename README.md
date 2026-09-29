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

## Endogenous firms, markets, and CPI

Phase 06 adds a staged real-economy simulation in `ecodeling.economy`. Firms form adaptive demand
expectations, hire from a seeded labor-matching stream, pay wages through mirrored deposit claims,
produce subject to labor technology and capacity, and set cost-plus prices with partial adjustment.
Households search suppliers using a separate seeded stream; purchases are planned against an
inventory snapshot before settlement, so no registry-order mutation can claim goods early.

Firm revenue equals household expenditure in the ledger, wage income equals firm payroll, and the
physical identity `opening inventory + production = sales + closing inventory` is recorded for
each firm and month. CPI is the sales-weighted price of actual consumer-good transactions,
normalized to 100,000 at initialization; monthly and twelve-month inflation are derived from that
series. Prices never read CPI directly. The Phase 06 baseline deliberately uses a zero markup and
fixed wage, isolating matching and accounting stability before foreign costs and feedback channels
are introduced in later phases.

```python
from ecodeling.config.schema import ModelConfig
from ecodeling.economy import run_economy_simulation
from ecodeling.identifiers import ScenarioId

result = run_economy_simulation(ModelConfig(scenario_id=ScenarioId("no-shock")))
print(result.aggregate_months[-1].cpi_level)
```

## Foreign sector and import-cost shocks

Phase 07 adds exogenous exchange-rate and foreign-price indices plus imported production inputs.
The exchange rate is defined as ISK per unit of foreign currency, so a higher value is a domestic
currency depreciation. The import-price index is their product, normalized to 100,000. A firm's
configured import share determines its baseline imported cost per produced unit; a zero share has
no direct cost or price response.

Each month observes the configured foreign path before production and pricing. Firms then buy the
inputs used in current production and settle the bill to the foreign sector through mirrored bank
deposit claims. Firm price targets include the observed import cost and adjust only by the declared
partial-adjustment rule. CPI remains the sales-weighted index of actual consumer transactions, and
this phase does not feed CPI into mortgages.

Shocks may target FX or foreign prices and may be a one-month impulse or a permanent level shift.
Their decimal configuration magnitude is converted once to integer basis points using half-up
rounding; thereafter the authoritative indices and ISK flows use integer arithmetic. Results expose
the FX, foreign-price, and import-price paths, firm and aggregate import expenditures, the matching
ledger entries, and a typed shock-onset event.

```python
from ecodeling.config.schema import (
    ForeignSectorConfig,
    ModelConfig,
    ShockConfig,
    ShockKind,
)
from ecodeling.economy import run_economy_simulation
from ecodeling.identifiers import ScenarioId

config = ModelConfig(
    scenario_id=ScenarioId("fx-depreciation"),
    foreign_sector=ForeignSectorConfig(import_share_bps=2_500),
    shock=ShockConfig(kind=ShockKind.FX_DEPRECIATION, month=12, magnitude=0.10),
)
result = run_economy_simulation(config)
print(result.shock_events[0])
```

## Endogenous mortgage-indexation feedback

Phase 08 joins the real-economy and mortgage mechanisms in `run_economy_simulation`. A seeded
opening population now includes ledger-backed houses and mortgages. Mortgage alpha is converted
to integer basis points and may take any configured value from zero through one; the coupon
interpolates between the documented nominal and indexed pricing decompositions instead of using
scenario-specific branches.

The monthly information convention is explicit: CPI is calculated after the goods market closes,
so it cannot affect a mortgage in that same month. A payment in month `t` uses CPI from
`t - lag_months - 1` and its preceding observation. Revaluation is posted symmetrically to the
borrower liability and bank asset before payment, arrears/default processing, and the household's
next goods budget. Current mortgage interest is distributed deterministically as household bank
dividends during financial closure; this is a stylized closure assumption that prevents an omitted
bank-spending sector from becoming a permanent demand sink, not an empirical claim.

Results expose household mortgage flows, aggregate principal, debt service, arrears/defaults, bank
assets/equity, source ledger IDs, and typed feedback events connecting a foreign shock to its CPI
observation and later mortgage and consumption response. Common-random-number comparisons use the
same initialization, labor/goods streams, and exogenous shock path:

```python
from ecodeling.economy import run_endogenous_indexation_comparison

pair = run_endogenous_indexation_comparison(config)
print(pair.nominal.aggregate_months[-1].total_mortgage_principal)
print(pair.indexed.aggregate_months[-1].total_mortgage_principal)
```
