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

Economic configuration and simulation commands will be added in later build phases.
