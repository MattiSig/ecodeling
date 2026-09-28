# Ecodeling Build Plan

This file is the executable build queue for Ecodeling. A build pass implements exactly one phase, verifies it, checks it off, and stops. The economic and product requirements remain authoritative in [`specs/`](specs/README.md).

## Build-pass protocol

Every `$build` pass must follow this sequence:

1. Read this file, `README.md`, and the specification files referenced by the first unchecked phase.
2. Inspect the current code, tests, Git status, and prior phase evidence before editing.
3. Select the first phase whose heading starts with `## [ ]`. Never skip ahead.
4. Implement only that phase. Check subtask boxes as they are completed.
5. Run every command in the phase's verification gate.
6. If the gate passes, change the phase heading to `## [x]`, add a dated entry with the pre-phase baseline commit and verification evidence to the build log, commit the complete phase, and stop.
7. If blocked or interrupted, leave the phase heading unchecked, preserve truthful subtask state, add a build-log entry describing the blocker, and stop.

Additional rules:

- Do not begin the next phase in the same pass.
- Do not check a phase merely because code was written; all acceptance criteria and verification must pass.
- Fix regressions caused by the active phase within that phase. Record unrelated defects for a later phase.
- Keep economic calculations in Python. The browser may replay and aggregate results but must not implement economic state transitions.
- Preserve deterministic behavior: identical code, configuration, and seed must produce identical authoritative outputs.
- New dependencies or architectural changes outside the locked decisions below require an ADR in `docs/decisions/` and explicit approval.
- Use one commit per completed phase with the subject `phase NN: <outcome>`. Push only when the invoking request authorizes it.

## Locked implementation decisions

- **Model:** Python 3.12+, packaged from `src/ecodeling/` with `pyproject.toml` and `uv`.
- **Domain objects:** typed dataclasses; Pydantic v2 for external configuration and replay/API validation.
- **Numerics and outputs:** NumPy, pandas, PyArrow/Parquet, and schema-versioned JSON replay bundles.
- **CLI:** Typer commands for validation, running scenarios, comparisons, exports, and batch experiments.
- **Quality:** pytest, Hypothesis for invariant/property tests, Ruff, and mypy.
- **Web:** an embeddable TypeScript web component built with Lit, Vite, and D3; Vitest and Playwright for tests.
- **Service:** FastAPI running the same Python model package; SQLite job metadata plus filesystem artifacts for the first deployment.
- **Time:** monthly, discrete, and explicitly staged according to `specs/12_simulation_loop.md`.
- **Authority:** ledgers and analytical outputs are authoritative; replay bundles are validated presentation derivatives.

## Completion standard for every phase

- [ ] The phase's implementation and tests are present.
- [ ] Existing tests, static checks, and formatting checks pass.
- [ ] New public behavior is documented where users or later phases need it.
- [ ] No secrets, generated bulk outputs, local databases, or caches are tracked.
- [ ] `git diff --check` passes and the worktree contains only intended changes.
- [ ] The build log records the pre-phase baseline and verification commands; the resulting commit uses the required `phase NN:` subject.

---

## [ ] Phase 00 — Repository and toolchain foundation

References: `specs/17_implementation_architecture.md`, `specs/18_v0_1_build_plan.md`

- [ ] Create `pyproject.toml`, `uv.lock`, the `src/ecodeling/` package, and `tests/` layout.
- [ ] Configure pytest, Hypothesis, Ruff, and mypy with strict settings appropriate for a new codebase.
- [ ] Add a minimal Typer CLI exposing `ecodeling --version` and `ecodeling validate`.
- [ ] Add `.gitignore` entries for Python, Node, simulation outputs, caches, databases, and local environment files.
- [ ] Add CI that installs locked dependencies and runs tests, lint, formatting checks, and type checks.
- [ ] Document local setup and quality commands in the root README.

Verification gate:

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run ecodeling --version
```

Acceptance: a clean checkout can install, validate, test, and invoke the empty application through documented commands.

## [ ] Phase 01 — Core identifiers, configuration, clock, and randomness

References: `specs/02_model_scope.md`, `specs/04_agents.md`, `specs/12_simulation_loop.md`, `specs/17_implementation_architecture.md`

- [ ] Add typed IDs for agents, accounts, contracts, runs, and scenarios.
- [ ] Implement an immutable monthly simulation clock with explicit start, stop, and current month.
- [ ] Define the validated configuration schema, including simulation length, seed, indexation, policy, and shock sections.
- [ ] Implement named random streams derived deterministically from one master seed.
- [ ] Add canonical configuration serialization and hashing for reproducibility and future caching.
- [ ] Add unit and property tests for validation, clock boundaries, stream independence, and repeatability.

Verification gate: standard quality suite plus repeated-run tests proving identical configurations and seeds yield identical primitive random sequences and hashes.

Acceptance: later phases can depend on stable identifiers, validated parameters, a monthly clock, and reproducible named randomness.

## [ ] Phase 02 — Ledger and stock-flow accounting kernel

References: `specs/05_balance_sheets_and_sfc.md`, `specs/16_validation_and_testing.md`

- [ ] Implement accounts, balance-sheet positions, transaction entries, and revaluation entries using integer ISK minor units or another explicitly documented exact representation.
- [ ] Require every transaction and revaluation to identify balanced asset/liability or debit/credit effects.
- [ ] Implement agent and system balance-sheet reports without hidden balance mutation.
- [ ] Add accounting assertions for transaction balance, mirrored claims, and aggregate sector identities.
- [ ] Add fixtures for households, banks, deposits, loans, and transfers.
- [ ] Add property tests showing arbitrary valid transfers conserve the required totals and invalid entries fail atomically.

Verification gate: standard quality suite plus accounting invariant tests over generated transaction sequences.

Acceptance: creating, transferring, or revaluing 1 ISK never breaks the declared balance-sheet identities.

## [ ] Phase 03 — Contract registry and mortgage engine

References: `specs/03_indexation_contract_spec.md`, `specs/05_balance_sheets_and_sfc.md`, `specs/09_banks_and_credit.md`

- [ ] Implement the contract registry and the opening state → revaluation → cash-flow calculation → settlement → closing state lifecycle.
- [ ] Implement nominal and partially/fully indexed amortizing mortgages with lag, rate, maturity, and payment rules.
- [ ] Mirror borrower liabilities and bank assets through ledger events.
- [ ] Encode rounding, final-payment, zero/negative-inflation, and payoff behavior explicitly.
- [ ] Add hand-calculated 12-month golden fixtures for nominal, partially indexed, and fully indexed loans.
- [ ] Add property tests for principal continuity, mirrored revaluation, payment decomposition, and payoff bounds.

Verification gate: standard quality suite; all golden fixtures match exactly and all contract/accounting invariants pass.

Acceptance: isolated mortgages reproduce hand calculations and every principal change is traceable to a typed ledger event.

## [ ] Phase 04 — Household-and-bank micro simulation

References: `specs/07_households.md`, `specs/09_banks_and_credit.md`, `specs/14_metrics_and_outputs.md`

- [ ] Implement household and bank registries with heterogeneous but reproducible initial states.
- [ ] Generate roughly 1,000 households and two banks from configuration.
- [ ] Drive incomes and CPI from external paths while settling deposits, mortgages, arrears, and defaults.
- [ ] Record household, cohort, bank, and aggregate monthly outputs.
- [ ] Implement a scenario comparing nominal and indexed mortgages against an identical CPI path.
- [ ] Add integration tests for long-run accounting, deterministic replay, distributional groups, and expected nominal/indexed divergence.

Verification gate: standard quality suite plus a 600-month seeded integration run with no accounting or numerical failures.

Acceptance: the micro model produces auditable principal, payment, net-worth, default, and bank-asset series under a shared CPI path.

## [ ] Phase 05 — Replay v0 and visual accounting audit

References: `specs/14_metrics_and_outputs.md`, `specs/17_implementation_architecture.md`, `specs/22_interactive_web_experience.md`

- [ ] Define replay schema version `0` for the micro simulation: manifest, timeline, snapshots, flows, events, representative agents, and series.
- [ ] Implement deterministic representative-household selection and stable identifiers.
- [ ] Export a compact canonical replay fixture from the micro simulation.
- [ ] Build a minimal internal browser page that steps and scrubs through principal, payments, revaluations, net worth, and bank assets.
- [ ] Link visible changes to source ledger event IDs and show both sides of each revaluation.
- [ ] Add schema, reconciliation, rendering, and basic browser interaction tests.

Verification gate: Python quality suite, replay reconciliation tests, frontend unit tests, and one Playwright smoke test of timeline inspection.

Acceptance: selecting a visible mortgage change reveals the matching ledger event and reconciled borrower/lender entries. This is the first end-to-end vertical slice.

## [ ] Phase 06 — Firms, labor, goods, and endogenous CPI

References: `specs/06_markets_and_matching.md`, `specs/08_firms.md`, `specs/11_prices_cpi_and_fx.md`

- [ ] Implement firms, employment, wages, production, inventories where specified, and capacity constraints.
- [ ] Implement staged labor and goods-market matching without order-dependent hidden mutations.
- [ ] Implement household consumption budgets and firm revenue/cost settlement through the ledger.
- [ ] Calculate an endogenous consumer price level and monthly/annual inflation.
- [ ] Add a stable no-shock baseline calibration fixture.
- [ ] Test market conservation, reproducibility, CPI construction, and bounded baseline behavior.

Verification gate: standard quality suite plus a seeded no-shock run meeting declared stability tolerances.

Acceptance: the economy generates production, employment, consumption, prices, and CPI endogenously while preserving accounting identities.

## [ ] Phase 07 — Foreign sector and import-cost shock

References: `specs/11_prices_cpi_and_fx.md`, `specs/13_shocks_and_scenarios.md`

- [ ] Implement the stylized foreign sector, exchange-rate/import-price path, and imported firm inputs.
- [ ] Implement configured one-off and persistent foreign-price or exchange-rate shocks.
- [ ] Propagate import costs into firm costs and pricing without activating mortgage indexation feedback yet.
- [ ] Record shock events and affected sector flows for analysis and replay.
- [ ] Add no-shock equivalence, shock-timing, sign, magnitude, and reproducibility tests.

Verification gate: standard quality suite plus an impulse-response fixture showing the configured depreciation raises import costs and produces an interpretable CPI response.

Acceptance: the path `FX → import costs → firm prices → CPI` is reproducible and traceable.

## [ ] Phase 08 — Close the endogenous indexation feedback loop

References: `specs/01_research_question.md`, `specs/03_indexation_contract_spec.md`, `specs/12_simulation_loop.md`, `specs/13_shocks_and_scenarios.md`

- [ ] Feed correctly lagged endogenous CPI into mortgage revaluation.
- [ ] Feed balance-sheet and payment effects back into household consumption, arrears/defaults, and bank state.
- [ ] Implement `alpha_indexation` values from 0 through 1 without special-case scenario code.
- [ ] Ensure the monthly stage order prevents same-period look-ahead.
- [ ] Produce paired nominal/indexed runs using common initialization and shock streams.
- [ ] Add causal trace fixtures linking shock, CPI, revaluation, household response, and bank response.

Verification gate: standard quality suite plus paired 600-month runs with accounting, timing, and common-random-number assertions.

Acceptance: the complete v0.1 feedback mechanism exists and every divergence can be traced to a rule, event, or ledger entry.

## [ ] Phase 09 — Central bank and interest-rate transmission

References: `specs/10_government_and_central_bank.md`, `specs/11_prices_cpi_and_fx.md`

- [ ] Implement the configured inflation-response rule, smoothing, and rate bounds.
- [ ] Implement explicit reset timing and pass-through for applicable loan rates.
- [ ] Record policy decisions and debt-service effects as typed outputs/events.
- [ ] Test policy timing, no-look-ahead behavior, bounds, and deterministic transmission.
- [ ] Add paired fixtures showing how tightening differs from CPI principal revaluation.

Verification gate: standard quality suite plus policy impulse tests and long-run numerical stability checks.

Acceptance: policy tightening changes debt-service dynamics through documented channels without corrupting comparative experiments.

## [ ] Phase 10 — Scenario runner, comparisons, and analytical reporting

References: `specs/13_shocks_and_scenarios.md`, `specs/14_metrics_and_outputs.md`

- [ ] Implement CLI commands for one run, baseline/shock pairs, and nominal/indexed comparisons.
- [ ] Persist metadata, configuration, aggregate series, cohort series, bank series, event summaries, and parameter snapshots.
- [ ] Calculate impulse-response-style differences from each regime's no-shock counterfactual.
- [ ] Produce the six core paired charts and required distributional comparison.
- [ ] Include commit, model version, scenario, seed, shock, and topology metadata in every output set.
- [ ] Add golden reporting tests and end-to-end CLI tests.

Verification gate: standard quality suite plus regeneration of a small version-controlled golden report fixture.

Acceptance: one documented command produces a complete, reproducible paired experiment and its publication-ready analytical figures.

## [ ] Phase 11 — Monte Carlo and sensitivity experiments

References: `specs/15_calibration_iceland.md`, `specs/16_validation_and_testing.md`, `specs/18_v0_1_build_plan.md`

- [ ] Implement independent-seed and paired-seed batch execution with bounded parallelism.
- [ ] Implement alpha sweeps and the specified sensitivity parameters.
- [ ] Persist run-level results separately from derived summaries.
- [ ] Report distributions, uncertainty, failure counts, and numerical-invalidity reasons.
- [ ] Make interrupted batches safely resumable without duplicating completed runs.
- [ ] Test serial/parallel equivalence, pairing, resume behavior, and aggregation correctness.

Verification gate: standard quality suite plus a reduced CI batch exercising pairing, parallel execution, resume, and summary generation.

Acceptance: experiments report distributions across reproducible runs rather than relying on a single illustrative path.

## [ ] Phase 12 — Production replay exporter

References: `specs/14_metrics_and_outputs.md`, `specs/17_implementation_architecture.md`, `specs/22_interactive_web_experience.md`

- [ ] Promote the replay schema to version `1` and document every field, unit, optional value, and compatibility rule.
- [ ] Export aligned nominal/indexed canonical runs, aggregates, distributions, sector flows, typed events, and representative tracks.
- [ ] Enforce reconciliation with authoritative analytical outputs and declared rounding tolerances.
- [ ] Add payload-size controls, compression, schema migration/error behavior, and deterministic serialization.
- [ ] Generate a canonical precomputed replay fixture used by the public experience.
- [ ] Add contract tests shared between Python and TypeScript.

Verification gate: standard quality suites on both stacks, cross-language contract tests, deterministic export hashes, and reconciliation tests.

Acceptance: the browser can consume an immutable, compact replay without importing Python internals or recalculating economics.

## [ ] Phase 13 — Public web component foundation

References: `specs/22_interactive_web_experience.md`

- [ ] Create the Vite/Lit/TypeScript package with D3, Vitest, Playwright, formatting, linting, and type checks.
- [ ] Implement replay loading, validation, timeline state, selection state, and error boundaries.
- [ ] Define the visual system: typography, colors, sector shapes, flow/stock encodings, spacing, motion, and chart conventions.
- [ ] Implement responsive shell, loading/error/static states, keyboard operation, and reduced-motion primitives.
- [ ] Package the experience as an embeddable custom element with documented attributes and events.
- [ ] Add component, accessibility, responsive, and embedding tests.

Verification gate: frontend quality suite and Playwright checks at representative desktop/mobile widths with normal and reduced motion.

Acceptance: the host site can embed a robust empty experience and load the canonical replay through a stable component API.

## [ ] Phase 14 — Animated economy, Story mode, and Explore mode

References: `specs/20_blog_post_plan.md`, `specs/22_interactive_web_experience.md`

- [ ] Render households, firms, banks, government, central bank, foreign sector/harbor, CPI, and clock.
- [ ] Animate recorded aggregate flows while keeping stock and flow encodings distinct.
- [ ] Implement play, pause, restart, speed, scrubber, markers, exact-value tooltips, and sector/agent inspection.
- [ ] Implement guided scenes for shock → imports → prices → CPI → debt → household/bank feedback.
- [ ] Preserve the current month when moving between Story and Explore modes.
- [ ] Add deterministic animation, interaction, screenshot, mobile, and reduced-motion tests.

Verification gate: frontend suite, visual regression baselines, and manual trace of every guided scene to replay data.

Acceptance: a reader can watch and freely inspect the canonical mechanism, and no visible economic event is invented by the frontend.

## [ ] Phase 15 — Compare mode and synchronized analytical charts

References: `specs/14_metrics_and_outputs.md`, `specs/20_blog_post_plan.md`, `specs/22_interactive_web_experience.md`

- [ ] Implement nominal, indexed, and synchronized split-screen views.
- [ ] Keep month, playback, selection, camera, and selected metric aligned across paired runs.
- [ ] Add synchronized charts for CPI, policy rate, principal, debt service, consumption, defaults, and bank equity.
- [ ] Add cohort comparisons and clearly labeled differences with units and baselines.
- [ ] Fall back from individual matching to declared cohort comparison when identities do not correspond.
- [ ] Add pairing validation, synchronization, chart, responsive, and accessibility tests.

Verification gate: frontend suite plus end-to-end playback over the full canonical paired timeline with no alignment drift.

Acceptance: readers can see where and why the nominal and indexed economies diverge without implying false agent correspondence.

## [ ] Phase 16 — Simulation API, cache, and Laboratory mode

References: `specs/17_implementation_architecture.md`, `specs/22_interactive_web_experience.md`

- [ ] Implement allowlisted public parameters with bounds on population, months, concurrency, and output size.
- [ ] Implement create/status/result endpoints and structured validation/failure responses.
- [ ] Run jobs in bounded worker processes using the same installed model package as the CLI.
- [ ] Cache immutable results by model version plus canonical configuration hash using SQLite metadata and filesystem artifacts.
- [ ] Implement Laboratory controls, progress, cancellation where safe, retry, and fallback to the canonical replay.
- [ ] Add API contract, security-limit, cache, failure, concurrency, and browser end-to-end tests.

Verification gate: all quality suites plus repeated/colliding request tests, resource-limit tests, and a full browser → API → simulation → replay workflow.

Acceptance: a reader can request a safe bounded experiment, receive reproducibility metadata, and replay the result without affecting other users or the canonical story.

## [ ] Phase 17 — Publication hardening and v0.1 release

References: all specifications, especially `specs/16_validation_and_testing.md`, `specs/19_research_sources.md`, and `specs/20_blog_post_plan.md`

- [ ] Run the full validation, calibration, paired-experiment, Monte Carlo, replay, API, and browser suites.
- [ ] Audit empirical statements and calibration inputs against primary sources.
- [ ] Complete static figure, reduced-motion, textual, and recorded-video fallbacks.
- [ ] Performance-test canonical loading, playback, and bounded custom jobs; document operating limits.
- [ ] Complete deployment, backup/cache cleanup, observability, security, and rollback documentation.
- [ ] Publish versioned canonical configurations, outputs, replay bundle, methodology, limitations, and reproducibility box.
- [ ] Tag the release only after every v0.1 definition-of-done item in `specs/README.md` is verified.

Verification gate: all repository checks, full end-to-end tests in a production-like environment, accessibility audit, and reproducibility rerun from a clean checkout.

Acceptance: the model, research outputs, animated article, and optional public laboratory are reproducible, explainable, accessible, and deployable as one versioned release.

---

## Build log

Append one entry per pass. Never rewrite earlier entries.

```text
YYYY-MM-DD — Phase NN — COMPLETE|BLOCKED
Baseline: <commit hash before the pass or n/a>
Verification: <commands and concise result>
Notes: <decisions, deviations, or blocker>
```
