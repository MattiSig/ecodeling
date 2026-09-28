# Indexation Contract Specification

## Core idea

Verðtrygging is modeled as a **contract transformation rule**.

Every contract that can be indexed has at least:

```text
contract_id
contract_type
payer_agent_id
receiver_agent_id
nominal_or_real_base
reference_index
alpha_indexation
indexation_lag_months
indexation_floor_optional
indexation_cap_optional
interest_rule_optional
amortization_rule_optional
start_month
maturity_month
```

The model should not contain a global boolean called `icelandic_indexation = true`. Indexation must be attached to individual contracts.

## Basic indexation coefficient

For contract `c`:

\[
\alpha_c \in [0,1]
\]

Interpretation:

- `0.0` = no CPI adjustment;
- `1.0` = full CPI adjustment;
- `0.5` = half of the referenced CPI movement passes through.

The first version should restrict alpha to `[0,1]`.

## Lagged indexation

Let the reference CPI level be \(P_t\). With a lag \(L_c\):

\[
g_{c,t}=\frac{P_{t-L_c}}{P_{t-L_c-1}}-1
\]

Then the indexed amount changes by:

\[
X_{c,t}^{preflow}=X_{c,t-1}\left(1+\alpha_c g_{c,t}\right)
\]

After indexation, normal contractual flows such as amortization, interest, or payment occur.

## Indexed mortgage principal

For a mortgage balance \(B\):

\[
B_{t}^{indexed}=B_{t-1}\left(1+\alpha_m \pi_{t-L}\right)
\]

Then apply amortization and interest/payment rules.

The exact order of operations must be fixed in the implementation and covered by tests. Recommended monthly order:

1. observe reference CPI movement;
2. apply principal indexation;
3. calculate interest on the post-indexation principal;
4. determine scheduled payment;
5. split payment into interest and principal reduction;
6. record arrears/default if cash is insufficient.

## Nominal mortgage comparison rule

A nominal loan must not be compared with an indexed loan using the same nominal coupon if the purpose is to isolate indexation.

A stylized pricing decomposition is:

\[
i^{nominal} \approx r^{real} + E[\pi] + \rho^{inflation} + \rho^{credit} + \rho^{term}
\]

while an indexed loan may use:

\[
r^{indexed} \approx r^{real} + \rho^{credit} + \rho^{term/indexation}
\]

The exact pricing rule may be simplified, but expected inflation cannot simply disappear from the nominal contract.

## Contract categories for later versions

### Wages

\[
W_{t}=W_{t-1}\left(1+\alpha_w \pi_{t-L_w}\right)\times(1+\text{other wage adjustment})
\]

### Rent

\[
R_{t}=R_{t-1}\left(1+\alpha_r \pi_{t-L_r}\right)
\]

### Transfers/pensions

\[
T_t=T_{t-1}\left(1+\alpha_T \pi_{t-L_T}\right)
\]

### Bank deposits or bonds

Principal can be updated with the same generic indexation operator before interest is applied.

## Deflation behavior

Do not silently assume indexation only moves upward. The base rule should allow a negative CPI movement to reduce the indexed amount unless the contract explicitly contains a floor.

Therefore the contract needs an optional floor rule:

```text
indexation_floor = None      # fully symmetric
indexation_floor = 0.0       # no negative indexation
```

Do not add floors to V0.1 unless needed for a specific empirical contract.

## Accounting invariant

For every financial indexation event:

\[
\Delta Liability_{borrower} = \Delta Asset_{lender}
\]

There must be no unmatched increase in aggregate financial wealth.

## Indexation topology

At the experiment level, define a vector:

\[
A=[\alpha_{mortgage},\alpha_{rent},\alpha_{wage},\alpha_{corpDebt},\alpha_{pension},\alpha_{benefit},\alpha_{tax},\alpha_{govDebt},\alpha_{deposit}]
\]

This is the model's **indexation topology**. Different regimes are alternative topologies rather than a binary indexed/unindexed economy.

## Acceptance tests

- With `alpha=0`, CPI changes do not alter principal through the indexation operator.
- With `alpha=1` and CPI rising 1%, a 10,000,000 balance becomes 10,100,000 before contractual flows.
- With `alpha=0.5` and CPI rising 1%, the same balance becomes 10,050,000.
- A borrower liability increase exactly matches the lender asset increase.
- A lag of two months references the CPI observation specified by the model calendar.
- Re-running the same contract state and CPI path is deterministic.
