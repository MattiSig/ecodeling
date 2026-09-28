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
