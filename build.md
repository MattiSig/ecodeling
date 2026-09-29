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

## [x] Phase 00 — Repository and toolchain foundation

References: `specs/17_implementation_architecture.md`, `specs/18_v0_1_build_plan.md`

- [x] Create `pyproject.toml`, `uv.lock`, the `src/ecodeling/` package, and `tests/` layout.
- [x] Configure pytest, Hypothesis, Ruff, and mypy with strict settings appropriate for a new codebase.
- [x] Add a minimal Typer CLI exposing `ecodeling --version` and `ecodeling validate`.
- [x] Add `.gitignore` entries for Python, Node, simulation outputs, caches, databases, and local environment files.
- [x] Add CI that installs locked dependencies and runs tests, lint, formatting checks, and type checks.
- [x] Document local setup and quality commands in the root README.

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

## [x] Phase 01 — Core identifiers, configuration, clock, and randomness

References: `specs/02_model_scope.md`, `specs/04_agents.md`, `specs/12_simulation_loop.md`, `specs/17_implementation_architecture.md`

- [x] Add typed IDs for agents, accounts, contracts, runs, and scenarios.
- [x] Implement an immutable monthly simulation clock with explicit start, stop, and current month.
- [x] Define the validated configuration schema, including simulation length, seed, indexation, policy, and shock sections.
- [x] Implement named random streams derived deterministically from one master seed.
- [x] Add canonical configuration serialization and hashing for reproducibility and future caching.
- [x] Add unit and property tests for validation, clock boundaries, stream independence, and repeatability.

Verification gate: standard quality suite plus repeated-run tests proving identical configurations and seeds yield identical primitive random sequences and hashes.

Acceptance: later phases can depend on stable identifiers, validated parameters, a monthly clock, and reproducible named randomness.

## [x] Phase 02 — Ledger and stock-flow accounting kernel

References: `specs/05_balance_sheets_and_sfc.md`, `specs/16_validation_and_testing.md`

- [x] Implement accounts, balance-sheet positions, transaction entries, and revaluation entries using integer ISK minor units or another explicitly documented exact representation.
- [x] Require every transaction and revaluation to identify balanced asset/liability or debit/credit effects.
- [x] Implement agent and system balance-sheet reports without hidden balance mutation.
- [x] Add accounting assertions for transaction balance, mirrored claims, and aggregate sector identities.
- [x] Add fixtures for households, banks, deposits, loans, and transfers.
- [x] Add property tests showing arbitrary valid transfers conserve the required totals and invalid entries fail atomically.

Verification gate: standard quality suite plus accounting invariant tests over generated transaction sequences.

Acceptance: creating, transferring, or revaluing 1 ISK never breaks the declared balance-sheet identities.

## [x] Phase 03 — Contract registry and mortgage engine

References: `specs/03_indexation_contract_spec.md`, `specs/05_balance_sheets_and_sfc.md`, `specs/09_banks_and_credit.md`

- [x] Implement the contract registry and the opening state → revaluation → cash-flow calculation → settlement → closing state lifecycle.
- [x] Implement nominal and partially/fully indexed amortizing mortgages with lag, rate, maturity, and payment rules.
- [x] Mirror borrower liabilities and bank assets through ledger events.
- [x] Encode rounding, final-payment, zero/negative-inflation, and payoff behavior explicitly.
- [x] Add hand-calculated 12-month golden fixtures for nominal, partially indexed, and fully indexed loans.
- [x] Add property tests for principal continuity, mirrored revaluation, payment decomposition, and payoff bounds.

Verification gate: standard quality suite; all golden fixtures match exactly and all contract/accounting invariants pass.

Acceptance: isolated mortgages reproduce hand calculations and every principal change is traceable to a typed ledger event.

## [x] Phase 04 — Household-and-bank micro simulation

References: `specs/07_households.md`, `specs/09_banks_and_credit.md`, `specs/14_metrics_and_outputs.md`

- [x] Implement household and bank registries with heterogeneous but reproducible initial states.
- [x] Generate roughly 1,000 households and two banks from configuration.
- [x] Drive incomes and CPI from external paths while settling deposits, mortgages, arrears, and defaults.
- [x] Record household, cohort, bank, and aggregate monthly outputs.
- [x] Implement a scenario comparing nominal and indexed mortgages against an identical CPI path.
- [x] Add integration tests for long-run accounting, deterministic replay, distributional groups, and expected nominal/indexed divergence.

Verification gate: standard quality suite plus a 600-month seeded integration run with no accounting or numerical failures.

Acceptance: the micro model produces auditable principal, payment, net-worth, default, and bank-asset series under a shared CPI path.

## [x] Phase 05 — Replay v0 and visual accounting audit

References: `specs/14_metrics_and_outputs.md`, `specs/17_implementation_architecture.md`, `specs/22_interactive_web_experience.md`

- [x] Define replay schema version `0` for the micro simulation: manifest, timeline, snapshots, flows, events, representative agents, and series.
- [x] Implement deterministic representative-household selection and stable identifiers.
- [x] Export a compact canonical replay fixture from the micro simulation.
- [x] Build a minimal internal browser page that steps and scrubs through principal, payments, revaluations, net worth, and bank assets.
- [x] Link visible changes to source ledger event IDs and show both sides of each revaluation.
- [x] Add schema, reconciliation, rendering, and basic browser interaction tests.

Verification gate: Python quality suite, replay reconciliation tests, frontend unit tests, and one Playwright smoke test of timeline inspection.

Acceptance: selecting a visible mortgage change reveals the matching ledger event and reconciled borrower/lender entries. This is the first end-to-end vertical slice.

## [x] Phase 06 — Firms, labor, goods, and endogenous CPI

References: `specs/06_markets_and_matching.md`, `specs/08_firms.md`, `specs/11_prices_cpi_and_fx.md`

- [x] Implement firms, employment, wages, production, inventories where specified, and capacity constraints.
- [x] Implement staged labor and goods-market matching without order-dependent hidden mutations.
- [x] Implement household consumption budgets and firm revenue/cost settlement through the ledger.
- [x] Calculate an endogenous consumer price level and monthly/annual inflation.
- [x] Add a stable no-shock baseline calibration fixture.
- [x] Test market conservation, reproducibility, CPI construction, and bounded baseline behavior.

Verification gate: standard quality suite plus a seeded no-shock run meeting declared stability tolerances.

Acceptance: the economy generates production, employment, consumption, prices, and CPI endogenously while preserving accounting identities.

## [x] Phase 07 — Foreign sector and import-cost shock

References: `specs/11_prices_cpi_and_fx.md`, `specs/13_shocks_and_scenarios.md`

- [x] Implement the stylized foreign sector, exchange-rate/import-price path, and imported firm inputs.
- [x] Implement configured one-off and persistent foreign-price or exchange-rate shocks.
- [x] Propagate import costs into firm costs and pricing without activating mortgage indexation feedback yet.
- [x] Record shock events and affected sector flows for analysis and replay.
- [x] Add no-shock equivalence, shock-timing, sign, magnitude, and reproducibility tests.

Verification gate: standard quality suite plus an impulse-response fixture showing the configured depreciation raises import costs and produces an interpretable CPI response.

Acceptance: the path `FX → import costs → firm prices → CPI` is reproducible and traceable.

## [x] Phase 08 — Close the endogenous indexation feedback loop

References: `specs/01_research_question.md`, `specs/03_indexation_contract_spec.md`, `specs/12_simulation_loop.md`, `specs/13_shocks_and_scenarios.md`

- [x] Feed correctly lagged endogenous CPI into mortgage revaluation.
- [x] Feed balance-sheet and payment effects back into household consumption, arrears/defaults, and bank state.
- [x] Implement `alpha_indexation` values from 0 through 1 without special-case scenario code.
- [x] Ensure the monthly stage order prevents same-period look-ahead.
- [x] Produce paired nominal/indexed runs using common initialization and shock streams.
- [x] Add causal trace fixtures linking shock, CPI, revaluation, household response, and bank response.

Verification gate: standard quality suite plus paired 600-month runs with accounting, timing, and common-random-number assertions.

Acceptance: the complete v0.1 feedback mechanism exists and every divergence can be traced to a rule, event, or ledger entry.

## [x] Phase 09 — Central bank and interest-rate transmission

References: `specs/10_government_and_central_bank.md`, `specs/11_prices_cpi_and_fx.md`

- [x] Implement the configured inflation-response rule, smoothing, and rate bounds.
- [x] Implement explicit reset timing and pass-through for applicable loan rates.
- [x] Record policy decisions and debt-service effects as typed outputs/events.
- [x] Test policy timing, no-look-ahead behavior, bounds, and deterministic transmission.
- [x] Add paired fixtures showing how tightening differs from CPI principal revaluation.

Verification gate: standard quality suite plus policy impulse tests and long-run numerical stability checks.

Acceptance: policy tightening changes debt-service dynamics through documented channels without corrupting comparative experiments.

## [x] Phase 10 — Scenario runner, comparisons, and analytical reporting

References: `specs/13_shocks_and_scenarios.md`, `specs/14_metrics_and_outputs.md`

- [x] Implement CLI commands for one run, baseline/shock pairs, and nominal/indexed comparisons.
- [x] Persist metadata, configuration, aggregate series, cohort series, bank series, event summaries, and parameter snapshots.
- [x] Calculate impulse-response-style differences from each regime's no-shock counterfactual.
- [x] Produce the six core paired charts and required distributional comparison.
- [x] Include commit, model version, scenario, seed, shock, and topology metadata in every output set.
- [x] Add golden reporting tests and end-to-end CLI tests.

Verification gate: standard quality suite plus regeneration of a small version-controlled golden report fixture.

Acceptance: one documented command produces a complete, reproducible paired experiment and its publication-ready analytical figures.

## [x] Phase 11 — Monte Carlo and sensitivity experiments

References: `specs/15_calibration_iceland.md`, `specs/16_validation_and_testing.md`, `specs/18_v0_1_build_plan.md`

- [x] Implement independent-seed and paired-seed batch execution with bounded parallelism.
- [x] Implement alpha sweeps and the specified sensitivity parameters.
- [x] Persist run-level results separately from derived summaries.
- [x] Report distributions, uncertainty, failure counts, and numerical-invalidity reasons.
- [x] Make interrupted batches safely resumable without duplicating completed runs.
- [x] Test serial/parallel equivalence, pairing, resume behavior, and aggregation correctness.

Verification gate: standard quality suite plus a reduced CI batch exercising pairing, parallel execution, resume, and summary generation.

Acceptance: experiments report distributions across reproducible runs rather than relying on a single illustrative path.

## [x] Phase 12 — Production replay exporter

References: `specs/14_metrics_and_outputs.md`, `specs/17_implementation_architecture.md`, `specs/22_interactive_web_experience.md`

- [x] Promote the replay schema to version `1` and document every field, unit, optional value, and compatibility rule.
- [x] Export aligned nominal/indexed canonical runs, aggregates, distributions, sector flows, typed events, and representative tracks.
- [x] Enforce reconciliation with authoritative analytical outputs and declared rounding tolerances.
- [x] Add payload-size controls, compression, schema migration/error behavior, and deterministic serialization.
- [x] Generate a canonical precomputed replay fixture used by the public experience.
- [x] Add contract tests shared between Python and TypeScript.

Verification gate: standard quality suites on both stacks, cross-language contract tests, deterministic export hashes, and reconciliation tests.

Acceptance: the browser can consume an immutable, compact replay without importing Python internals or recalculating economics.

## [x] Phase 13 — Public web component foundation

References: `specs/22_interactive_web_experience.md`

- [x] Create the Vite/Lit/TypeScript package with D3, Vitest, Playwright, formatting, linting, and type checks.
- [x] Implement replay loading, validation, timeline state, selection state, and error boundaries.
- [x] Define the host-inheritable Industrial visual system: JetBrains Mono, profile-site tokens, flat ruled panels, one signal color, flow/stock encodings, spacing, motion, and chart conventions.
- [x] Implement responsive shell, loading/error/static states, keyboard operation, and reduced-motion primitives.
- [x] Package the experience as an embeddable custom element with documented attributes and events.
- [x] Add component, accessibility, responsive, and embedding tests.

Verification gate: frontend quality suite and Playwright checks at representative desktop/mobile widths with normal and reduced motion.

Acceptance: the host site can embed a robust empty experience and load the canonical replay through a stable component API.

## [x] Phase 14 — Animated economy, Story mode, and Explore mode

References: `specs/20_blog_post_plan.md`, `specs/22_interactive_web_experience.md`

- [x] Render households, firms, banks, government, central bank, foreign sector/harbor, CPI, and clock.
- [x] Animate recorded aggregate flows while keeping stock and flow encodings distinct.
- [x] Implement play, pause, restart, speed, scrubber, markers, exact-value tooltips, and sector/agent inspection.
- [x] Implement guided scenes for shock → imports → prices → CPI → debt → household/bank feedback.
- [x] Preserve the current month when moving between Story and Explore modes.
- [x] Add deterministic animation, interaction, screenshot, mobile, and reduced-motion tests.

Verification gate: frontend suite, visual regression baselines, and manual trace of every guided scene to replay data.

Acceptance: a reader can watch and freely inspect the canonical mechanism, and no visible economic event is invented by the frontend.

## [x] Phase 15 — Compare mode and synchronized analytical charts

References: `specs/14_metrics_and_outputs.md`, `specs/20_blog_post_plan.md`, `specs/22_interactive_web_experience.md`

- [x] Implement nominal, indexed, and synchronized split-screen views.
- [x] Keep month, playback, selection, camera, and selected metric aligned across paired runs.
- [x] Add synchronized charts for CPI, policy rate, principal, debt service, consumption, defaults, and bank equity.
- [x] Add cohort comparisons and clearly labeled differences with units and baselines.
- [x] Fall back from individual matching to declared cohort comparison when identities do not correspond.
- [x] Add pairing validation, synchronization, chart, responsive, and accessibility tests.

Verification gate: frontend suite plus end-to-end playback over the full canonical paired timeline with no alignment drift.

Acceptance: readers can see where and why the nominal and indexed economies diverge without implying false agent correspondence.

## [x] Phase 16 — Simulation API, cache, and Laboratory mode

References: `specs/17_implementation_architecture.md`, `specs/22_interactive_web_experience.md`

- [x] Implement allowlisted public parameters with bounds on population, months, concurrency, and output size.
- [x] Implement create/status/result endpoints and structured validation/failure responses.
- [x] Run jobs in bounded worker processes using the same installed model package as the CLI.
- [x] Cache immutable results by model version plus canonical configuration hash using SQLite metadata and filesystem artifacts.
- [x] Implement Laboratory controls, progress, cancellation where safe, retry, and fallback to the canonical replay.
- [x] Add API contract, security-limit, cache, failure, concurrency, and browser end-to-end tests.

Verification gate: all quality suites plus repeated/colliding request tests, resource-limit tests, and a full browser → API → simulation → replay workflow.

Acceptance: a reader can request a safe bounded experiment, receive reproducibility metadata, and replay the result without affecting other users or the canonical story.

## [x] Phase 17 — Publication hardening and v0.1 release

References: all specifications, especially `specs/16_validation_and_testing.md`, `specs/19_research_sources.md`, and `specs/20_blog_post_plan.md`

- [x] Run the full validation, calibration, paired-experiment, Monte Carlo, replay, API, and browser suites.
- [x] Audit empirical statements and calibration inputs against primary sources.
- [x] Complete static figure, reduced-motion, textual, and recorded-video fallbacks.
- [x] Performance-test canonical loading, playback, and bounded custom jobs; document operating limits.
- [x] Complete deployment, backup/cache cleanup, observability, security, and rollback documentation for the CV-owned `/work/ecodeling` route and its vendored assets.
- [x] Verify the production CV page, health endpoint, hashed component assets, canonical replay, dark/light host themes, and absence of Laboratory requests when `api-base` is omitted.
- [x] Publish versioned canonical configurations, outputs, replay bundle, methodology, limitations, and reproducibility box.
- [x] Tag the release only after every v0.1 definition-of-done item in `specs/README.md` is verified.

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
2026-09-28 — Phase 00 — COMPLETE
Baseline: n/a (the workspace contained an empty `.git` directory and no valid repository)
Verification: `uv sync --all-groups`; `uv run pytest` (3 passed); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version` (all passed)
Notes: Initialized the repository on `main`; pinned Python 3.12 and uv 0.12.19 for CI; established `src/ecodeling`, strict quality tooling, the Typer foundation CLI, and root-only build-output ignores so the repository-owned build skill remains tracked.

2026-09-28 — Phase 01 — COMPLETE
Baseline: 77df04ae55af1b8a0c592c2764efc0f2e4ad7dd4
Verification: `uv sync --all-groups`; `uv run pytest` (20 passed); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `uv run pytest tests/unit/test_config.py tests/unit/test_randomness.py` (13 passed); `git diff --check` (all passed)
Notes: Added static domain ID types, an immutable inclusive monthly clock, frozen Pydantic configuration with bounded simulation/indexation/policy/shock sections, SHA-256 canonical JSON identity, and order-independent named NumPy PCG64 streams. Golden configuration-hash and primitive-random-sequence fixtures make reproducibility changes explicit; NumPy and Pydantic were added as already-locked architecture dependencies.

2026-09-28 — Phase 02 — COMPLETE
Baseline: 32ef3acdd018d2d3d2bb13718d3f2635c52681ca
Verification: `uv sync --all-groups`; `uv run pytest` (31 passed); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `uv run pytest tests/unit/test_accounting.py tests/property/test_accounting_properties.py` (11 passed); `git diff --check` (all passed)
Notes: Added an append-only ledger whose typed transaction and revaluation entries use exact whole-ISK integers and reconstruct all positions from journal history. Posting is atomic and enforces per-agent balance, equal changes to both sides of every financial claim, unique entry IDs, and explicit negative-balance permission; reports expose agent, sector, and system identities. Household/bank deposit, mortgage, revaluation, and transfer fixtures cover explicit equity effects, including 1 ISK creation/revaluation and a generated 1 ISK transfer example.

2026-09-28 — Phase 03 — COMPLETE
Baseline: 0b7944cc0289d5014af2d7c2dba71eb9be2026b6
Verification: `uv sync --all-groups`; `uv run pytest` (44 passed); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `uv run pytest tests/unit/test_mortgage.py tests/integration/test_mortgage_golden.py tests/property/test_mortgage_properties.py tests/unit/test_accounting.py` (22 passed); `git diff --check` (all passed)
Notes: Added a reference-index-aware contract registry and fixed-coupon annuity mortgage lifecycle with integer-basis-point terms, lagged CPI revaluation, whole-ISK half-away-from-zero rounding, symmetric deflation, exact final payoff, and explicit nominal/indexed pricing decomposition. Origination, revaluation, and settlement mirror mortgage and deposit claims through typed events; ordered event batches commit atomically before contract state advances. Static 12-month nominal, half-indexed, and fully indexed fixtures plus generated lifecycle tests verify continuity, decomposition, payoff bounds, timing, and accounting.

2026-09-29 — Phase 04 — COMPLETE
Baseline: 3d6efe8cf13101dc9f1b7c6c362b22703c677263
Verification: `uv sync --all-groups`; `uv run pytest` (51 passed, including the 1,000-household/two-bank 600-month seeded run); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `git diff --check` (all passed)
Notes: Added deterministic heterogeneous household/bank registries, externally supplied exact CPI and income paths, ledger-backed income/consumption settlement, mortgage payment and CPI revaluation, persistent arrears with interest capitalization, zero-recovery default write-downs, and household/cohort/bank/aggregate outputs. External settlement claims are mirrored by foreign-sector liabilities; paired nominal/indexed runs regenerate identical populations and share paths while applying the documented coupon/indexation distinction. A derived ledger balance cache and cached annuity factors make the long-run audit tractable without changing journal authority or monetary rounding.

2026-09-29 — Phase 05 — COMPLETE
Baseline: 4e423f9a753d05da917e09414df2fab8a5824a91
Verification: `uv sync --all-groups`; `uv run pytest` (56 passed, including the 1,000-household 600-month accounting run and replay reconciliation/regression tests); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `npm ci`; `npm test`; `npm run test:browser` (1 Playwright smoke test passed); `git diff --check` (all passed)
Notes: Added strict replay schema v0 and canonical JSON export as a presentation derivative of authoritative micro outputs and ledger entries. Deterministic policy-cohort selection retains real stable household IDs; visible stocks and payment flows reconcile exactly, and each representative CPI change exposes its source entry plus mirrored borrower-liability/lender-asset postings. The compact six-month fixture and dependency-light internal audit page establish the first vertical slice without introducing the later public Lit component or a browser economic engine.

2026-09-29 — Phase 06 — COMPLETE
Baseline: 715d07f351e6e359a594f137fb11a779bae3e58e
Verification: `uv sync --all-groups`; `uv run pytest` (62 passed, including generated conservation paths, the 120-month no-shock calibration, and the existing 600-month accounting run); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; default 1,000-household/600-month endogenous no-shock stress run; `npm ci`; `npm test`; `npm run test:browser` (1 Playwright smoke test passed); `git diff --check` (all passed)
Notes: Added a separate staged real-economy engine so Phase 04's external-path comparison and replay remain stable. Firms form adaptive sales expectations, match labor from a named stream, settle wages and household purchases through mirrored bank-deposit claims, produce within labor/capacity bounds, carry physical inventories, and partially adjust cost-plus prices without reading CPI. Goods search uses its own named stream and plans against an inventory snapshot before committing state. CPI is an exact sales-weighted firm-price index normalized to 100,000, with monthly and twelve-month rates; the declared baseline fixes wages and uses zero markup to isolate matching/accounting stability before foreign inputs and feedback channels. Adding result-affecting real-economy configuration intentionally changed canonical configuration hashes, so the replay-v0 fixture was regenerated; its analytical values still reconcile unchanged.

2026-09-29 — Phase 07 — COMPLETE
Baseline: 035730525537377a8e994cf44b0cfd19df49d08a
Verification: `uv sync --all-groups`; `uv run pytest` (72 passed); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `uv run pytest tests/integration/test_foreign_impulse.py tests/unit/test_foreign_sector.py` (7 passed); `npm test`; `npm run test:browser` (1 Playwright smoke test passed); `git diff --check` (all passed)
Notes: Added integer-indexed exogenous FX and foreign-price paths, configurable one-month or permanent shocks, and imported firm inputs whose baseline share is derived relative to labor unit cost. Import bills settle to a foreign-sector deposit through mirrored bank claims; monthly aggregate flows retain their ledger entry IDs, and typed onset events record the before/after causal step. Current-month foreign prices are observed before production/import settlement/pricing, while CPI remains derived from actual goods transactions and is not yet fed into mortgages. Decimal shock magnitudes are converted once to basis points with half-up rounding; all downstream indices and ISK flows use integer arithmetic. The default zero import share preserves Phase 06 behavior, while a fixed 10% depreciation fixture verifies the traceable import-cost and CPI impulse. Result-affecting configuration changed the canonical hash, so replay v0 was regenerated and reconciled without changing its analytical series.

2026-09-29 — Phase 08 — COMPLETE
Baseline: ee02cee245dc403e61b59ce1248d545737bc7efe
Verification: `uv sync --all-groups`; `uv run pytest` (75 passed, including paired 600-month nominal/indexed runs); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `npm test`; `npm run test:browser` (1 Playwright smoke test passed); `git diff --check` (all passed)
Notes: Joined the endogenous real economy to ledger-backed household mortgages and the bank balance sheet. CPI produced at period end becomes eligible only after one information month plus the configured contract lag; typed feedback events retain the source shock, CPI observations, revaluation ledger entry, debt service, household consumption, arrears/defaults, and bank equity. Mortgage alpha is converted once to integer basis points and uses one continuous coupon/indexation rule across the full 0.0–1.0 range. The paired runner changes only alpha/scenario identity while preserving initialized households/firms, named random streams, and the exogenous shock path. Current mortgage interest is returned deterministically as household bank dividends, a documented stylized closure assumption preventing the omitted bank-spending sector from becoming a permanent demand sink. The Phase 06 no-shock tolerance now permits a one-household employment fluctuation, and its aggregate goods assertion correctly includes opening inventory.

2026-09-29 — Phase 09 — COMPLETE
Baseline: 1e7a1816dad7a6a39eda2b78728779268531ce6e
Verification: `uv sync --all-groups`; `uv run pytest` (80 passed, including policy impulse, paired-regime, and existing paired 600-month tests); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; dedicated 600-month policy stress run with accounting/rate/debt bounds; `npm test`; `npm run test:browser` (1 Playwright smoke test passed); `git diff --check` (all passed)
Notes: Added an exact annual-basis-point Taylor-like rule with smoothing, configurable bounds, and a held initial rate until trailing twelve-month CPI exists. Month-end decisions become eligible only in the following month; nominal and indexed mortgages reset on independent schedules with distinct pass-through, while deposit and bank-funding channel rates are recorded separately. Typed decision/reset events link every applicable rate to its inflation observation and source decision, and monthly/household outputs separate coupon-driven interest from CPI principal revaluation. The checked paired impulse fixture shows nominal tightening through debt service versus indexed CPI revaluation plus weaker coupon pass-through. Existing isolated mortgage and micro-model contracts remain fixed-rate; the Phase 06 calibration explicitly pins policy to preserve its historical boundary. Result-affecting policy parameters changed the canonical configuration hash, so replay v0 was regenerated and reconciled.

2026-09-29 — Phase 10 — COMPLETE
Baseline: 6064e6d613dccfa718b859021b0558e0c2041e9a
Verification: `uv sync --all-groups`; `uv run pytest` (82 passed); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `uv run python scripts/generate_phase10_golden.py`; `npm test`; `npm run test:browser` (1 Playwright smoke test passed); `git diff --check` (all passed)
Notes: Added `run`, `shock-pair`, and `compare` workflows. A complete comparison executes nominal/indexed regimes against their own no-shock counterfactuals with common initialization and shocks, persists Zstandard-compressed Parquet aggregates/cohorts/bank series plus metadata, parameter snapshots, and typed event summaries, and calculates aligned long-form impulse responses. Bank credit losses are read from authoritative default ledger postings. The deterministic SVG report contains the six core paired mechanisms and an initial-income-quintile consumption comparison; charts remain Python reporting derivatives rather than a second economic engine. The checked 20-household fixture and end-to-end CLI tests regenerate all four paths. Pandas and PyArrow activate the already-locked analytical-output architecture.

2026-09-29 — Phase 11 — COMPLETE
Baseline: f3b2158095f6195092c432197ee24ed52fd5e083
Verification: `uv sync --all-groups`; `uv run pytest` (86 passed, including reduced serial/parallel, paired/independent seed, resume, all-sensitivity-axis, aggregation, and CLI batch cases); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `npm test`; `npm run test:browser` (1 Playwright smoke test passed); `git diff --check` (all passed)
Notes: Added a validated `batch` workflow with a 10,000-run safety bound, spawn-based process parallelism, common-random-number paired seeds, and deterministic independent seed derivation. Alpha and the specified shock, lag, import-share, maturity, price-adjustment, policy-response, expected-inflation, consumption-propensity, and default-threshold axes form an explicit Cartesian grid. Stable task identities and atomic terminal records make interrupted batches resumable without rerunning completed work; raw complete, failed, and numerically invalid run records remain separate from regenerated JSON/Parquet summaries. Summaries report distributions, standard errors, 95% normal-approximation intervals, quantiles, failure reasons, and paired variant-minus-reference differences matched by seed group. The manifest distinguishes stylized mechanism experiments from empirical calibration and records omitted channels and sensitivity coverage; execution worker count does not affect scientific identity.

2026-09-29 — Phase 12 — COMPLETE
Baseline: e9da824ebad39679ceabe0ad3825f3a247618acb
Verification: `uv sync --all-groups`; `uv run pytest` (90 passed, including replay-v1 pairing, reconciliation, size, compatibility, deterministic compression/hash, and canonical-fixture cases); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `uv run python scripts/generate_replay_v1.py`; `npm test` (2 Python/TypeScript-facing contract suites passed); `npm run test:browser` (1 Playwright smoke test passed); `git diff --check` (all passed)
Notes: Promoted the browser boundary to a strict paired schema v1 while retaining v0 as the internal micro-accounting audit contract. The exporter aligns nominal/indexed timelines and common-random-number provenance, reconstructs month-end sector stocks from ledger postings, and carries recorded sector flows, typed economic events, stable matched representative households, chart aggregates, and all five required distributional dimensions. Exact whole-ISK aggregates, debt-service flows, and cohort totals reconcile at zero tolerance before serialization. Government and central-bank stock fields are explicitly null because those balance sheets are not modeled. Canonical key-sorted JSON, deterministic timestamp-free gzip, an uncompressed-size cap, explicit v0/future-version errors, a generated JSON Schema, and shared Python/browser validation protect the presentation contract. The checked 18-month canonical pair is 293,688 bytes uncompressed and 24,709 bytes compressed; its sidecar records the canonical SHA-256.

2026-09-29 — Phase 13 — COMPLETE
Baseline: 008dd3ca5e69924bfa54bc1813bfe0cd3f38c9b6
Verification: `uv sync --all-groups`; `uv run pytest` (90 passed); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `npm ci`; `npm run typecheck:web`; `npm run lint:web`; `npm run format:check`; `npm test` (2 legacy/contract and 8 Vitest tests passed); `npm run build:web`; `npm run test:browser` (11 passed across desktop, mobile, and reduced-motion projects; 4 project-specific skips); `npm audit` (0 vulnerabilities); `git diff --check` (all passed)
Notes: Added an embeddable Lit custom element whose stable attributes, methods, composed events, and fallback slot expose validated replay-v1 loading plus independent timeline and selection state without implementing economic transitions. JSON and gzip inputs fail into typed network, decoding, or compatibility states; published provenance remains visible after successful validation. The Organic visual system packages Fraunces and defines sand/sage/clay sector geometry, distinct future stock/flow and chart conventions, a responsive month ribbon, keyboard navigation, static mode, and reduced-motion behavior. Vitest and Playwright cover component state, loading failures, accessibility, responsive containment, keyboard operation, reduced motion, and compatibility with the existing internal audit page. CI now runs the complete frontend quality and production-build gate, and the pinned dependency tree has no known advisories.

2026-09-29 — Phase 14 — COMPLETE
Baseline: d7df2dba1e09dbd6bcfaf63f4b4126b469defa04
Verification: `uv sync --all-groups`; `uv run pytest` (90 passed); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `npm run typecheck:web`; `npm run lint:web`; `npm run format:check`; `npm test` (5 legacy/contract and 10 Vitest tests passed); `npm run build:web`; `npm run test:browser` (16 passed across desktop, mobile, and reduced-motion projects; 8 project-specific skips); `git diff --check` (all passed)
Notes: Replaced the empty public stage with a replay-driven Organic economic circuit containing all six sectors, CPI, simulation month, distinct stock silhouettes, scaled aggregate-flow paths, exact values, ledger identifiers, typed events, and deterministic representative-household inspection. Story scenes derive their source months from the first replay month, FX shock, post-shock import flow, CPI movement, CPI revaluation, and feedback event; manual and automated traces confirmed the canonical chain without presentation-invented transactions. Story and Explore share timeline state; playback provides play, pause, restart, speed, scrub, event markers, keyboard controls, off-screen pausing, discrete reduced-motion behavior, and static fallbacks. Deterministic desktop, mobile, and reduced-motion screenshots plus accessibility and interaction tests lock the rendered circuit to the canonical replay.

2026-09-29 — Phase 15 — COMPLETE
Baseline: 3ef28fb27b99be649da263b55d8ab0fb1eaa52cf
Verification: `uv sync --all-groups`; `uv run pytest` (90 passed); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `npm run typecheck:web`; `npm run lint:web`; `npm run format:check`; `npm test` (5 legacy/contract and 13 Vitest tests passed); `npm run build:web`; `npm run test:browser` (18 passed across desktop, mobile, and reduced-motion projects; 12 project-specific skips, including full 18-month paired playback with no drift); `git diff --check` (all passed)
Notes: Added replay-validated nominal, indexed, and split-screen Compare views on one timeline, playback state, selection, shared sector camera, and selected metric. Seven authoritative paired series render as synchronized solid/dashed charts with one visible time rail and exact indexed-minus-nominal readouts labeled by unit and nominal baseline. Declared distribution cohorts expose like-for-like totals and differences; representative agents are treated as matched individuals only for reciprocal counterpart IDs, otherwise the UI explicitly falls back to the declared cohort. Pairing validation now checks run IDs, seed, shared initialization and shock path, named streams, series timelines, and units. The existing Organic visual system was preserved; desktop/mobile inspection, accessibility checks, responsive containment, and the exact visual baseline all pass.

2026-09-29 — Phase 16 — COMPLETE
Baseline: aeb7d7e584925b74a67cc674f0e03a3427bcee34
Verification: `uv sync --all-groups`; `uv run pytest` (94 passed, including API validation/resource limits, collisions, bounded capacity, cancellation, failure/retry, immutable cache, and full simulation/replay cases); `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src tests`; `uv run ecodeling --version`; `npm run typecheck:web`; `npm run lint:web`; `npm run format:check`; `npm test` (2 legacy/contract and 17 Vitest tests passed); `npm run build:web`; `npm run test:browser` (19 passed across desktop, mobile, and reduced-motion projects; 14 project-specific skips, including a real browser → API → worker-process simulation → replay workflow); `git diff --check` (all passed)
Notes: Added a strict allowlisted experiment API with bounded request size, months, population, firms, pending work, worker processes, and replay bytes. FastAPI create/status/result/cancel endpoints expose structured validation and failure states; safe cancellation never kills a running artifact writer. Jobs use the installed Python model in a ProcessPoolExecutor, publish replay-v1 gzip artifacts atomically, and store restart-aware SQLite metadata keyed by model version plus the complete canonical configuration hash, so colliding requests share work and completed results are immutable. Laboratory mode provides bounded controls, polling progress, safe cancellation, retry, provenance, and canonical restoration; a failed or invalid custom result never replaces the published replay. The production-like browser gate starts both Vite and the Python service, and the inspected one-pixel mobile reflow from the fourth mode tab is recorded in the refreshed deterministic baseline.

2026-09-29 — Phase 16 — COMPLETE (publication integration follow-up)
Baseline: fe0dcd4785018f1ee90ad942bb6b80aa7cb67b21
Verification: `npm run format:check`; `npm run typecheck:web`; `npm run lint:web`; `npm test` (5 legacy/contract and 18 Vitest tests passed); `npm run build:web`; `ECODELING_API_PORT=8865 ECODELING_WEB_PORT=4273 npm run test:browser` (19 passed, 14 project-specific skips); CV `make validate`; exported `sha256sum -c SHA256SUMS`; local production-style desktop/mobile and dark/light browser inspection with no console errors; Railway health and `/work/ecodeling` returned 200 for the first publication.
Notes: Changed the publication boundary after the phase implementation. `MattiSig/cv` now owns the native `/work/ecodeling` route and Railway service, while this repository exports checksummed JavaScript, CSS, and the immutable canonical replay through `scripts/export-cv-assets.sh`. The CV page omits `api-base`, so Laboratory is hidden and canonical Story/Explore/Compare playback has no Python-service dependency. The original Organic/Fraunces presentation recorded in the Phase 13–15 history was superseded by a host-inheritable Industrial system using JetBrains Mono, the profile's dark/light tokens, flat one-pixel rules, and gold only for active/model signals. Commits `a9c11ef` and `ebad869` implement the source-side handoff and theme; CV commits `6ff7053` and `52a7391` contain the host route and vendored assets.

2026-09-29 — Phase 17 — COMPLETE
Baseline: e20ea49919863af2dd6d8e6dc7fee0a10b59c95a
Verification: clean-copy `npm run release:verify` (`uv sync --locked --all-groups`; 94 pytest cases including 1,000-household/600-month accounting, paired experiments, reduced Monte Carlo, replay, and API; Ruff; mypy; deterministic replay regeneration; 5 legacy/contract and 18 Vitest tests; production build; 19 Playwright passes with 14 project-specific skips); release artifact verifier (15 SHA-pinned files); fallback export (six PNG scenes and 5.2-second WebM); exported `sha256sum -c SHA256SUMS`; CV `make validate`; Railway `/healthz`, `/work/ecodeling`, and versioned assets returned 200; dark/light Chromium inspection had no console errors or Laboratory/API requests; `git diff --check` (all passed)
Notes: Released package version 0.1.0 with a versioned canonical configuration, replay-derived summary, immutable replay/schema metadata, source-audited methodology and limitations, reproducibility box, operating runbook, static/text/reduced-motion/recorded fallbacks, and an offline CI artifact gate. The live Railway route still carries the pre-release replay's `0.0.0` metadata; its economic run and source commit match the canonical fixture, and the v0.1 CV handoff was checksummed and tested locally. Publishing that new handoff remains a separate explicitly authorized push/deploy. The required local tag is `v0.1.0`.
