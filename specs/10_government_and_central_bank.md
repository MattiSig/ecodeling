# Government and Central Bank

## Government — V0.1

Government should initially provide only enough fiscal structure to make household incomes and unemployment shocks less pathological.

### Taxes

Simple proportional labor-income tax:

\[
Tax_{i,t}=\tau_y WageIncome_{i,t}
\]

Optional later additions:

- consumption tax;
- progressive brackets;
- property taxes;
- corporate taxes.

### Transfers

Unemployment transfer:

\[
Transfer_{i,t}=replacementRate \times previousOrReferenceIncome
\]

V0.1 transfers are nominal unless explicitly testing benefit indexation.

### Government budget

\[
Deficit_t=Transfers+GovConsumption+InterestExpense-TaxRevenue
\]

If public debt is modeled, deficit changes debt consistently.

## Central bank

### Inflation target

Define \(\pi^*\) as an annualized target but calculate policy monthly using consistent units.

### Policy rule

A simple Taylor-like rule:

\[
i_t=\rho i_{t-1}+(1-\rho)[r^*+\pi_t+\phi_{\pi}(\pi_t-\pi^*)+\phi_y ygap_t]
\]

For V0.1, the output-gap term can be omitted if output potential is difficult to define:

\[
i_t=\rho i_{t-1}+(1-\rho)[r^*+\pi_t+\phi_{\pi}(\pi_t-\pi^*)]
\]

## Transmission channels to preserve conceptually

Even if simplified, interpretation should recognize that monetary policy can act through:

- borrowing rates;
- debt service;
- new credit supply;
- expectations;
- exchange rate;
- asset prices;
- aggregate demand.

Mortgage indexation may change the relative strength/timing of these channels rather than making monetary policy binary-effective or ineffective.

## Interest-rate pass-through

Define separate pass-through rules for:

- nominal mortgage rates;
- indexed real mortgage rates;
- deposit rates;
- bank funding costs.

This is important because indexation and interest-rate fixation are distinct contract dimensions.

## Later indexation experiments

Government can eventually carry its own indexation topology:

- indexed transfers;
- indexed tax thresholds;
- indexed pension benefits;
- indexed public debt.

These should be added one at a time so fiscal automatic-stabilizer effects remain interpretable.

## Acceptance criteria

- policy rate reacts in the documented direction to inflation deviations;
- tax payments reduce household deposits and increase government funds;
- transfers do the reverse;
- fiscal deficits map to debt/cash changes consistently;
- policy-rate changes affect only contracts whose interest rule references the policy rate.
