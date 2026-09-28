# Blog Post Plan

## Working thesis

Do not begin the eventual article with a verdict about verðtrygging. Begin with the mechanism:

> Inflation is not only a change in prices. In an indexed economy, inflation can mechanically rewrite contracts and balance sheets.

The blog post should show how an ABM lets us follow those rewrites through the economy.

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

### 3. A two-household example

Compare:

- household A: indexed debt, nominal wage;
- household B: indexed debt, indexed wage.

Use a single inflation shock to demonstrate asymmetry before introducing 1,000 agents.

### 4. Why nominal versus indexed is not "same interest rate"

Explain expected inflation compensation and why naive comparisons bias the experiment.

### 5. The synthetic Iceland-style economy

Describe agents, markets, monthly sequence, and the external shock.

### 6. The first experiment

Use identical seeds and shock paths across regimes.

Show six core graphs:

- inflation;
- mortgage principal;
- debt service;
- consumption;
- defaults;
- bank equity.

### 7. Cash-flow versus balance-sheet effects

This should be a central explanatory section.

A strong graphic would show two columns:

```text
Nominal/floating shock
rate ↑ -> payment ↑ -> cash today ↓

Indexed shock
CPI ↑ -> principal ↑ -> net worth today ↓ -> future burden ↑
```

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
