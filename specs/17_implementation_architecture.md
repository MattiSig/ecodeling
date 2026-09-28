# Implementation Architecture

## Language

Python is a natural first choice because the project needs fast iteration, testing, data analysis, and plotting more than maximum simulation throughput.

The spec does not require a particular ABM framework. A plain Python implementation may be easier to understand than introducing framework-specific abstractions too early.

## Suggested package structure

```text
src/
  model/
    economy.py
    clock.py
    accounting.py
    contracts.py
    indexation.py
  agents/
    household.py
    firm.py
    bank.py
    government.py
    central_bank.py
    foreign_sector.py
  markets/
    labor.py
    goods.py
    credit.py
    housing.py          # later
  policy/
    monetary.py
    fiscal.py
  experiments/
    scenarios.py
    runner.py
  reporting/
    metrics.py
    recorder.py
    plots.py
    replay.py
  config/
    schema.py

tests/
  unit/
  integration/
  regression/
```

## Data model

Prefer IDs and central contract registries over deeply nested mutable object references.

Example:

```text
Household.mortgage_id -> ContractRegistry[mortgage_id]
```

This makes counterparties and accounting audits easier.

## Contract abstraction

Base contract interface:

```text
Contract
  opening_state(t)
  apply_revaluation(context)
  calculate_cashflows(context)
  settle(context)
  closing_state(t)
```

Mortgage, wage, rent, deposit, and government-bond contracts can later share the same indexation operator.

## Ledger-first accounting

Use a transaction/revaluation ledger rather than modifying balances invisibly whenever practical.

Example revaluation event:

```text
RevaluationEvent(
  contract_id=123,
  asset_agent=bank_1,
  liability_agent=household_77,
  amount=240_000,
  reason="CPI_INDEXATION"
)
```

This makes auditing and blog visualizations much easier.

## Configuration

All economic parameters should live outside core logic.

Example conceptual configuration:

```yaml
simulation:
  months: 600
  seed: 123

indexation:
  mortgage_alpha: 1.0
  lag_months: 2

monetary_policy:
  inflation_target_annual: 0.025
  phi_pi: 1.5
  smoothing: 0.8

shock:
  type: fx_depreciation
  month: 120
  magnitude: 0.10
```

The user requested Markdown-only spec files, so this is illustrative rather than an included config file.

## Randomness

Use a master seed to generate named streams:

```text
rng_initialization
rng_labor
rng_goods
rng_shocks
rng_defaults
```

Regime comparisons should reuse shock streams and, where possible, matching streams.

## Performance strategy

Do not optimize prematurely.

Start with readable loops and objects. Profile only once the model works. If needed later:

- vectorize household calculations;
- use NumPy arrays for state;
- use Numba for hot loops;
- parallelize independent Monte Carlo seeds.

## Persistence

Each run should write:

```text
run_metadata.json or equivalent
aggregate_timeseries
household_panel_or_sample
bank_timeseries
event_summary
parameter_snapshot
```

Even if the final storage format changes, the logical data products should remain stable.

## Reproducibility

A result is reproducible when a reader can identify:

- code commit;
- model version;
- parameter configuration;
- seed;
- experiment/scenario ID.

## Logging

Provide two logging modes:

- normal: high-level progress and summary;
- audit/debug: individual contract/ledger events for a small model.

The audit mode is invaluable for diagnosing stock-flow inconsistencies.

## Presentation boundary

The Python model is the sole authority for economic state transitions. The web experience may filter, aggregate, annotate, and animate recorded results, but it must not independently calculate prices, balances, payments, defaults, or policy responses.

The boundary is:

```text
scenario configuration
        -> Python simulation
        -> versioned run outputs and replay bundle
        -> browser visualization
```

This avoids maintaining separate Python and TypeScript versions of the economic model.

## Replay exporter

`reporting/replay.py` should transform a completed run into the web replay contract defined in `22_interactive_web_experience.md`. The exporter should:

- preserve the run ID, model version, commit, seed, scenario, units, and timeline;
- aggregate transaction-ledger entries into sector-to-sector flows without changing their totals;
- expose notable shocks, revaluations, defaults, and policy changes as typed events;
- select representative agents deterministically from declared cohorts;
- align paired nominal and indexed runs on the same monthly clock;
- validate the replay bundle against aggregates before publishing it.

The replay export is a derived presentation artifact. The analytical tables and ledger remain the authoritative research outputs.

## Web delivery

The default article should load a precomputed canonical replay so that playback begins without waiting for a simulation. Reader-created experiments should be submitted to a server-side Python runner with an allowlisted parameter schema and bounded run size. Results should be cached by model version plus configuration hash.

The browser should receive immutable completed-run data and replay it locally. Scrubbing and playback must not rerun the model. Progress reporting for a custom run may use polling or server-sent events; live tick-by-tick streaming is not required for version 0.1.
