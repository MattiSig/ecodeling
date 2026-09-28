# Research Question and Hypotheses

## Primary question

> **How does the breadth and asymmetry of CPI indexation affect the propagation, persistence, and distribution of inflation shocks in a small open economy?**

The model is not designed to prove that indexation is intrinsically good or bad. Instead, it should reveal **where inflation risk goes**, **when the burden is realized**, and **how the resulting behavioral responses feed back into the rest of the economy**.

## Three dimensions of the experiment

### 1. Breadth

How many kinds of contracts are indexed?

Examples:

- mortgages;
- rents;
- wages;
- pensions;
- government transfers;
- tax brackets;
- corporate loans;
- bank deposits;
- government bonds.

### 2. Symmetry

Are both sides of an agent's economic position indexed?

Examples:

- indexed mortgage + nominal wage = household mismatch;
- indexed mortgage + indexed wage = partial household hedge;
- indexed bank loans + nominal bank funding = bank inflation exposure;
- indexed assets + indexed liabilities = lower balance-sheet mismatch.

A useful diagnostic is:

\[
\text{IndexationMismatch}_i = \text{IndexedAssets}_i - \text{IndexedLiabilities}_i
\]

For households, a broader economic exposure measure may also include indexed income and indexed recurring expenses.

### 3. Shock type

Indexation may behave differently depending on the origin of inflation. The model should therefore distinguish at least:

- exchange-rate depreciation;
- imported commodity/energy inflation;
- domestic demand boom;
- wage shock;
- housing-price shock;
- foreign interest-rate shock;
- productivity shock.

## Mechanisms to investigate

### Cash-flow channel

A nominal/floating debt contract can transmit tighter monetary policy quickly through monthly payments:

\[
i_t \uparrow \Rightarrow \text{DebtService}_t \uparrow \Rightarrow C_t \downarrow
\]

### Balance-sheet channel

An indexed loan can place part of the inflation burden onto principal:

\[
\pi_t \uparrow \Rightarrow B_t \uparrow \Rightarrow \text{NetWorth}_t \downarrow
\]

The cash-flow consequences can then be spread into the future.

### Wage-price/indexation feedback

If wages or recurring business costs are indexed:

\[
CPI \uparrow \Rightarrow Wages/Costs \uparrow \Rightarrow Prices \uparrow \Rightarrow CPI \uparrow
\]

The model should measure whether this creates additional inflation persistence under particular parameterizations rather than assume that it does.

### Bank balance-sheet channel

When indexed bank assets exceed indexed bank liabilities:

\[
CPI \uparrow \Rightarrow \text{AssetValue} \uparrow \text{ faster than LiabilityValue}
\]

This may strengthen bank equity mechanically while potentially weakening highly leveraged borrowers.

## Initial hypotheses

These are **questions to test**, not conclusions.

1. Broader indexation may reduce immediate real cash-flow volatility for some agents while increasing balance-sheet persistence.
2. Mismatched indexation may create stronger distributional effects than symmetric indexation.
3. Debt-only indexation may affect indebted households very differently from a system in which wages and transfers are also indexed.
4. Indexation may weaken some interest-rate cash-flow channels without eliminating monetary transmission through expectations, credit, exchange rates, asset prices, and new lending.
5. The sign of welfare or stability effects may depend strongly on the shock source and household heterogeneity.
6. Aggregate GDP effects may be small while wealth and default effects across groups are large.

## Non-goals

The model should not initially attempt to:

- produce a single policy verdict;
- forecast Icelandic GDP or CPI;
- estimate optimal monetary policy;
- reproduce every legal detail of Icelandic mortgage contracts;
- represent every Icelandic industry;
- infer causal effects from simulation alone.

## Research standard

Every result should be phrased as:

> "Under this model structure, calibration, and shock, regime A produced X relative to regime B."

Avoid language implying that a simulated outcome is automatically an empirical fact about Iceland.
