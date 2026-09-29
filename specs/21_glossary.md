# Glossary

## Agent-based model (ABM)

A simulation in which heterogeneous agents follow behavioral rules and interact. Aggregate economic outcomes emerge from those interactions rather than being solved only at representative-agent level.

## Verðtrygging / price indexation

A contractual rule that adjusts a nominal amount according to a price index, commonly CPI. In this project it is represented by an indexation coefficient, reference index, and lag.

## CPI

Consumer Price Index. A measure of the price level of a specified consumption basket. The model computes its own synthetic CPI from simulated prices.

## Inflation

Rate of change of the price level. Monthly and annual inflation must be kept in consistent units.

## Principal

Outstanding amount of a loan before future interest. Under an indexed mortgage, CPI adjustments may change principal.

## Negative amortization

A situation where outstanding loan principal increases despite scheduled payments, for example because indexation/revaluation exceeds principal repayment.

## Nominal interest rate

Interest rate measured in currency units without adjusting for inflation.

## Real interest rate

Interest rate adjusted conceptually for inflation. Indexed loans often quote a real coupon while CPI changes affect principal.

## Inflation risk premium

Additional return a nominal lender may require to compensate for uncertainty about future inflation.

## LTV — loan-to-value

\[
LTV=LoanBalance/PropertyValue
\]

Measures leverage against collateral.

## DSTI — debt-service-to-income

\[
DSTI=DebtService/Income
\]

Measures current cash-flow burden of debt.

## Stock-flow consistency (SFC)

Accounting discipline in which stocks and flows reconcile across agents and sectors. Every financial asset is matched by a liability somewhere else in the modeled system.

## Revaluation

Change in the nominal value of an asset or liability that is not itself a cash transaction. CPI indexation of mortgage principal is modeled as a revaluation.

## Cash-flow channel

Mechanism through which a shock changes current payments/income and therefore near-term spending capacity.

## Balance-sheet channel

Mechanism through which a shock changes assets, liabilities, leverage, or net worth, possibly affecting behavior over a longer horizon.

## Indexation topology

The pattern of which contracts in the economy are indexed and by how much.

## Indexation mismatch

Difference between indexed exposures on different sides of an agent's balance sheet or income/expenditure structure.

## Small open economy

An economy whose domestic conditions are materially affected by foreign prices, trade, capital conditions, and exchange rates, while being too small to determine global prices on its own.

## Exchange-rate depreciation

In this project, \(E\) is ISK per foreign-currency unit. An increase in \(E\) means the króna has depreciated and imported goods become more expensive, all else equal.

## Markup

Amount a firm adds over unit cost when setting its target sale price.

## Price stickiness

Prices do not instantly adjust to their desired/target levels.

## Common random numbers

Experimental technique where different model regimes use the same random seed/shock draws, improving the comparability of paired simulation outcomes.

## Burn-in period

Initial simulation period allowed to pass before evaluating an experiment so initialization artifacts can diminish.

## Monte Carlo experiment

Running the stochastic model many times with different seeds and analyzing the distribution of outcomes.

## Impulse response

The path of a variable after a shock relative to a no-shock counterfactual or baseline.

## Calibration

Choosing model parameters so the model corresponds to selected empirical facts or moments.

## Validation

Checking code correctness, accounting consistency, behavioral plausibility, and empirical properties appropriate to the model's intended use.

## FX — foreign exchange

Exchange rates between currencies. This model quotes the rate as ISK per foreign-currency unit.

## ISK — Icelandic króna

Currency used for monetary accounting. Model outputs use nominal whole krónur.

## IRF — impulse response function

The path following a shock relative to a no-shock counterfactual. An indexed-minus-nominal regime
difference alone is not an IRF.
