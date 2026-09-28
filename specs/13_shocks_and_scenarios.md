# Shocks and Experiment Scenarios

## Experimental principle

When comparing indexation regimes, keep everything else identical.

Use **common random numbers**:

```text
run(regime=A, seed=123)
run(regime=B, seed=123)
```

The same households, firm productivity draws, matching randomness, and shock path should be used unless the structural regime itself changes those outcomes endogenously.

## Baseline stabilization

Before injecting shocks:

1. initialize economy;
2. run a burn-in period;
3. verify that no explosive drift exists without shocks;
4. save a checkpoint state if practical;
5. branch regime experiments from comparable conditions.

## Primary V0.1 shock

### Exchange-rate depreciation

At month \(T_s\):

\[
E_{T_s}=1.10E_{T_s-1}
\]

Then choose one documented persistence path:

- permanent level shift;
- AR(1) mean reversion;
- gradual reversal over 12–24 months.

This shock raises imported input costs and therefore tests the chain:

\[
FX \rightarrow ImportCosts \rightarrow FirmPrices \rightarrow CPI \rightarrow MortgageIndexation
\]

## Mortgage indexation regimes

### Regime N — nominal

\[
\alpha_{mortgage}=0
\]

Nominal interest pricing includes expected inflation compensation.

### Regime I — indexed

\[
\alpha_{mortgage}=1
\]

Mortgage principal receives the CPI adjustment after the configured lag.

### Intensity sweep

\[
\alpha_{mortgage}\in\{0,0.1,0.2,...,1.0\}
\]

This tests whether outcomes change smoothly or show thresholds/nonlinearities.

## Later topology regimes

| Regime | Mortgage | Wage | Rent | Benefits | Bank funding |
|---|---:|---:|---:|---:|---:|
| Nominal | 0 | 0 | 0 | 0 | 0 |
| Debt only | 1 | 0 | 0 | 0 | 0 |
| Debt + rent | 1 | 0 | 1 | 0 | 0 |
| Debt + wages | 1 | 1 | 0 | 0 | 0 |
| Household hedge | 1 | 1 | 1 | 1 | 0 |
| Broad/symmetric | 1 | 1 | 1 | 1 | 1 |

## Additional shock library

### Foreign-price shock

Increase \(P^*\) without changing \(E\).

### Domestic demand boom

Temporarily raise household propensity to consume, transfers, or export demand.

### Wage shock

Raise wage growth independently of CPI to test cost-push dynamics.

### Policy-rate shock

Exogenously raise the policy rate for a defined period.

### Productivity shock

Lower firm productivity and observe supply-side inflation.

### Housing shock — later

Change house prices or housing demand when the housing market exists.

## Monte Carlo design

Each scenario should eventually run across many seeds:

```text
for seed in 1..N:
    run nominal
    run indexed
    store paired differences
```

Use paired differences rather than comparing unrelated ensembles.

## Output definition

For metric \(M\):

\[
\Delta M^{seed}=M^{indexed,seed}-M^{nominal,seed}
\]

Report:

- mean paired difference;
- median;
- quantiles/confidence intervals;
- full distribution when nonlinear/default effects matter.
