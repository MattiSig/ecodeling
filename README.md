# Ecodeling

Ecodeling is a specification-first project for an educational agent-based model of CPI indexation in a small open economy inspired by Iceland.

The model is designed to explore how the breadth, symmetry, and location of indexation affect the propagation of inflation shocks through households, firms, banks, government, housing, and monetary policy.

Read the [full specification and recommended reading order](specs/README.md).

Development proceeds one verified phase at a time using the checklist in the [build plan](build.md).
The repository-owned [`$build` skill](skills/build/SKILL.md) executes exactly one unchecked phase per invocation.

The versioned v0.1 methodology, limitations, audited sources, fallback exports, and reproducibility
box are indexed in [`publication/v0.1/`](publication/v0.1/README.md). Run the complete clean-checkout
release gate with `npm run release:verify`; deployment and rollback are documented in
[`docs/operations.md`](docs/operations.md).
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

The command-line interface exposes the installed version and a foundation validation check:

```bash
uv run ecodeling --version
uv run ecodeling validate
```

## Reproducible analytical experiments

Phase 10 adds three JSON-configured workflows. `run` persists one model run, `shock-pair` compares
one regime with its own no-shock counterfactual, and `compare` executes the complete four-run
nominal/indexed experiment. Output directories must be new or empty, which prevents an experiment
from silently mixing with older artifacts.

The checked small configuration can regenerate the golden analytical report:

```bash
uv run ecodeling compare tests/fixtures/phase10_report_config.json \
  --output outputs/phase10-example
```

Each run directory contains metadata, the complete parameter snapshot, typed event summaries, and
Parquet aggregate, cohort, and clearing-bank series. Parquet schemas embed the run metadata and use
Zstandard compression. The comparison also writes long-form impulse responses calculated as each
regime's shocked path minus that same regime's no-shock path, plus six paired SVG charts and a
bottom/top initial reporting-month income-quintile comparison. The figures are reporting
derivatives of Python outputs; they do not recalculate economic transitions.

Every output identifies the model version, Git commit, scenario, seed, shock, configuration hash,
start month, units, and current indexation topology. Money remains nominal whole ISK; price indices
use a base of 100,000; unavailable ratios remain null. The endogenous v0.1 economy currently uses
one clearing bank, so bank reporting has one explicitly identified row per month. Income quintiles
are fixed from initial reporting-month labor income with stable household IDs as the deterministic
tie-breaker.

## Monte Carlo and sensitivity batches

The `batch` command executes a bounded Cartesian grid of mortgage-indexation alpha values and
allowlisted sensitivity axes across explicit seed replications. A paired design uses the same
master seed for every parameter variant in a seed group, preserving common initialization and
named shock streams. An independent design derives a stable, distinct 64-bit seed for every
variant/replication combination.

```bash
uv run ecodeling batch batch-config.json --output outputs/my-batch
```

The batch JSON contains `model` (a normal model configuration), `seeds`, `seed_design`,
`max_workers`, `alpha_values`, and optional `sensitivities`. Supported sensitivity names are
`shock_magnitude`, `indexation_lag_months`, `import_share_bps`, `loan_maturity_months`,
`price_adjustment_bps`, `policy_phi_pi`, `expected_inflation_bps`,
`consumption_propensity_bps`, and `default_after_arrears_months`. Price adjustment is the explicit
inverse operational measure of stickiness: smaller adjustment values make prices stickier.

Each run is atomically persisted under its stable task ID before derived summaries are rebuilt.
Re-running the identical batch and source commit skips terminal run records, so an interrupted
batch resumes without duplicate simulations. `summary.json` reports completion, numerical
invalidity, failure reasons, and distributions; `summary.parquet` stores per-variant moments,
standard errors, 95% normal-approximation uncertainty intervals, and quantiles. Paired batches also
write `paired_differences.parquet`, using the first declared parameter combination as the explicit
reference and matching observations by seed group. Run records remain separate and authoritative
for regeneration. Worker count is an execution setting and does not change batch identity or
results.

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

## Production replay v1

Phase 12 adds the paired production contract documented in
[`docs/replay-v1.md`](docs/replay-v1.md). It aligns nominal and indexed endogenous-economy runs,
reconstructs six-sector stocks from the ledger, exports recorded flows and typed events, retains
actual representative-household tracks, and carries aggregate and five-dimension distributional
series. Export uses zero-ISK reconciliation tolerance and fails on pairing drift, dangling flow
provenance, or the default 2 MB uncompressed payload limit.

The public experience's precomputed fixture is `web/replay/canonical-v1.json.gz`; its sidecar
records sizes and the canonical JSON hash. Regenerate and verify the shared Python/browser contract
with:

```bash
uv run python scripts/generate_replay_v1.py
uv run pytest tests/unit/test_replay_v1.py tests/regression/test_replay_v1_fixture.py
npm test
```

## Public web component

Phase 13 provides the embeddable `<ecodeling-experience>` foundation in `web/public/`. It loads
JSON or gzip-compressed replay v1 data, validates compatibility before exposing state, and keeps
timeline and selection changes behind a documented custom-element API. The shell includes explicit
empty, loading, error, fallback, static, and reduced-motion states. It remains a replay reader: no
economic transition is calculated in the browser.

```bash
npm ci
npm run typecheck:web
npm run lint:web
npm run format:check
npm test
npm run build:web
npm run test:browser
```

Phase 18 adds Article as the first-reader entry point, with a replay-backed walkthrough, exact
paired evidence, a shared accessible glossary, and a conditional conclusion. Evidence links open
Story, Explore, or Compare at the recorded month and restore reading position on return.
`initial-mode` or `?ecodeling-mode=compare` provides direct entry; returning readers retain their
mode for the session. The introduction and limitations remain readable if the replay fails.

The canonical development host is available at `/web/public/` under `npm run dev:web`. Attributes,
events, methods, fallback slots, and the visual encoding system are documented in
[`web/public/README.md`](web/public/README.md).

### CV publication

The public experience is hosted by `MattiSig/cv` at `/work/ecodeling`. It is not a separate
Ecodeling deployment. Export a verified static bundle into a CV checkout with:

```bash
scripts/export-cv-assets.sh /path/to/cv/web/static/ecodeling
```

The handoff vendors the component JavaScript, minimal host CSS, canonical gzip replay, and
`SHA256SUMS`. The CV Go application embeds those files and versions their URLs by content hash. The
component inherits the profile's background, foreground, muted, rule, and accent tokens, so its
Industrial interface follows both site themes without shipping another font.

## Bounded simulation service and Laboratory

Phase 16 exposes custom experiments through a FastAPI service while keeping Python as the only
economic engine. Start it beside the Vite development host:

```bash
uv run ecodeling serve
npm run dev:web
```

`POST /api/v1/experiments` accepts only the documented public fields: months (6–60), seed,
households (10–250), firms (2–50), indexation lag, shock kind/month/magnitude/persistence, import
share, and price adjustment. Unknown fields and values outside those bounds fail with structured
errors. The service caps request bodies, pending jobs, worker processes, and replay size. Jobs run
in bounded worker processes using the installed `ecodeling` package; the browser polls status and
loads only a completed, replay-v1-validated artifact.

SQLite stores job metadata under `runs/service/` by default and gzip replay artifacts remain on the
filesystem. Cache identity includes the model version, replay-export revision, and complete canonical
model-configuration hash. Identical concurrent requests therefore share one job, completed responses are immutable,
and a failed or safely cancelled identity can be retried. Set `ECODELING_SERVICE_DATA` to relocate
service state. `GET /docs` publishes the exact request and response schema.

Laboratory mode is disabled unless a host explicitly sets `api-base`; the development page sets it
to `/api/v1`. The CV publication intentionally omits it and therefore serves Story, Explore, and
Compare without making failed requests to an undeployed Python API. A custom failure never
replaces the canonical replay, and a successful custom replay can be replaced with the canonical
publication using “Restore canonical replay.” Running jobs are not forcibly killed; cancellation
succeeds only while an executor future is still safely queued.

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

## Monetary policy and interest-rate transmission

Phase 09 adds a smoothed, bounded Taylor-like rule using trailing twelve-month CPI inflation in
annual basis points. Because CPI is finalized after the goods market closes, the decision recorded
for month `t` is first available in `t + 1`; it can never alter debt service already settled in
`t`. Before twelve months of model CPI exist, the configured initial policy rate is held.

Nominal mortgages, indexed mortgages, deposits, and bank funding have separate pass-through
coefficients. The two mortgage channels also have independent reset intervals. Economy mortgages
are policy-linked: at a reset, their coupon is reconstructed from its opening nominal or indexed
coupon plus the configured share of the policy-rate change from the opening policy rate. Mixed
indexation contracts use the same alpha to blend those two coupon channels. Isolated contracts in
the mortgage engine remain fixed-rate unless a caller explicitly supplies a reset coupon; CPI
principal revaluation never changes the coupon itself.

`EconomySimulationResult.policy_events` records the inflation observation, unconstrained rule,
bounds, decision, and effective month. `rate_reset_events` links each channel reset to its source
decision. Monthly aggregate and household outputs record the applicable rates and mortgage
interest, keeping rate-driven debt service separate from CPI-driven principal revaluation. These
are stylized mechanism assumptions for controlled experiments, not claims about empirical Icelandic
pass-through magnitudes.
