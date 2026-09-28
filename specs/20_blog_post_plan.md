# Blog Post Plan

## Working thesis

Do not begin the eventual article with a verdict about verðtrygging. Begin with the mechanism:

> Inflation is not only a change in prices. In an indexed economy, inflation can mechanically rewrite contracts and balance sheets.

The blog post should show how an ABM lets us follow those rewrites through the economy.

The primary explanatory device should be a browser-based animated economy driven by real simulation output. Static figures remain necessary for precise comparison and accessibility, but the animation should carry the causal narrative.

## Experience modes

The article should expose four progressively deeper modes:

- **Story:** guided scenes synchronized with the written argument;
- **Explore:** play, pause, scrub, and inspect sectors or representative households;
- **Compare:** nominal and indexed runs aligned side by side on the same clock;
- **Laboratory:** submit bounded parameters to create a server-side simulation and replay the result.

Story, Explore, and Compare should use a precomputed canonical run and load immediately. The Laboratory is an optional deeper interaction and must not block the article.

## Suggested structure

### 1. The question

Explain why comparing one mortgage payment calculator is not enough. Verðtrygging changes who carries inflation risk and when.

### 2. The key modeling decision

"Index contracts, not people."

Show a small network:

```text
Household --mortgage--> Bank
Household --labor-----> Firm
Firm      --wage------> Household
Household --rent------> Landlord
Government--benefit---> Household
```

Each edge can have its own indexation coefficient.

Use the first interactive scene to introduce these sectors and contract edges. Selecting an edge should explain its indexation coefficient, lag, asset holder, and liability holder.

### 3. A two-household example

Compare:

- household A: indexed debt, nominal wage;
- household B: indexed debt, indexed wage.

Use a single inflation shock to demonstrate asymmetry before introducing 1,000 agents.

Represent both households as actual tracked agents from a small reproducible run. Let the reader scrub across the revaluation month and inspect the corresponding ledger event.

### 4. Why nominal versus indexed is not "same interest rate"

Explain expected inflation compensation and why naive comparisons bias the experiment.

### 5. The synthetic Iceland-style economy

Describe agents, markets, monthly sequence, and the external shock.

Expand the scene into the full animated economy: household district, firms, banks, government and central bank, and a harbor/foreign-sector boundary. Visual tokens and line weight may communicate aggregate flows, but labels and tooltips should provide exact values.

### 6. The first experiment

Use identical seeds and shock paths across regimes.

Show six core graphs:

- inflation;
- mortgage principal;
- debt service;
- consumption;
- defaults;
- bank equity.

Synchronize all charts with the animation clock and mark the shock, CPI response, mortgage revaluation, and later feedback. The nominal and indexed views must use paired runs with common initialization and shock streams.

### 7. Cash-flow versus balance-sheet effects

This should be a central explanatory section.

A strong graphic would show two columns:

```text
Nominal/floating shock
rate ↑ -> payment ↑ -> cash today ↓

Indexed shock
CPI ↑ -> principal ↑ -> net worth today ↓ -> future burden ↑
```

Let readers switch between these channels while the relevant payment flows or balance-sheet stocks are emphasized in the economy view.

### 8. Distribution

Show that aggregate effects can conceal redistribution among:

- borrowers;
- savers;
- banks;
- renters;
- homeowners;
- low/high income households.

### 9. What surprised us

Only write this after results exist. Avoid precommitting to a narrative.

### 10. Model limitations

Be explicit about:

- stylized firms;
- simplified housing;
- simplified expectations;
- parameter uncertainty;
- the distinction between mechanism exploration and causal empirical evidence.

### 11. Next experiment

Wage indexation is a natural second article because it changes the topology from debt-only indexation to partial household hedging and potential wage-price feedback.

## Writing discipline

Every empirical Icelandic statement should have a primary/institutional source.

Every simulation statement should clearly distinguish:

- assumption;
- mechanism;
- simulated result;
- interpretation.

Avoid phrases such as "the model proves." Prefer "in this specification," "the simulation suggests," or "the mechanism produces."

## Reproducibility box

The post should include:

```text
Model version:
Commit:
Parameters:
Seeds:
Shock:
Indexation regime:
Data sources:
```

Ideally publish the configuration and code used for every figure.

## Visual truthfulness

Every animated state, flow, and event must come from the published replay bundle. The interface may aggregate many agents into a district, slow down events that occur within one monthly step, and scale marks for legibility. It must not create transactions or causal sequences absent from the model.

Representative households must be selected deterministically from declared cohorts and retain stable IDs. The article should make clear when a view shows one agent, a cohort statistic, or an economy-wide aggregate.

Every guided scene needs a static textual or graphical fallback. Respect reduced-motion preferences and never make animation the only way to access a result.
