# Household Behavior

## Household budget

For household \(i\):

\[
Y^{disp}_{i,t}=WageIncome+Transfers+InterestIncome-Taxes-DebtService-Rent
\]

Liquid resources equal opening deposits plus net cash inflows.

## Consumption rule

A simple V0.1 rule:

\[
C^{desired}_{i,t}=c_{0,i}+c_{y,i}Y^{disp,expected}_{i,t}+c_{w,i}NW^{liquid}_{i,t}
\]

Then impose a liquidity constraint:

\[
C^{planned}_{i,t}=\max(0,\min(C^{desired}_{i,t},\ available\ cash_i))
\]

Actual consumption may be lower if goods are rationed.

## Heterogeneous marginal propensity to consume

Lower-liquidity households should generally have higher income sensitivity than wealthy households. V0.1 can assign household groups rather than estimate a continuous behavioral equation.

Example groups:

- liquidity constrained: high \(c_y\), near-zero wealth effect;
- middle wealth: medium \(c_y\), small \(c_w\);
- wealthy: lower \(c_y\), larger but still modest \(c_w\).

## Mortgage cash flow

For each household with a mortgage:

1. contract principal is indexed if applicable;
2. interest due is calculated;
3. scheduled principal/amortization is calculated;
4. scheduled payment is deducted from deposits;
5. insufficient cash triggers arrears/default logic.

Track separately:

```text
scheduled_payment
interest_component
principal_amortization
indexation_revaluation
arrears
closing_principal
```

This decomposition is a core research output.

## Net worth

\[
NW_i = Deposits_i + HouseValue_i + OtherAssets_i - Mortgage_i - OtherDebt_i
\]

An indexed principal increase can lower net worth without immediately lowering current-period cash.

## Default rule

A stylized V0.1 default condition can combine cash-flow stress and persistent arrears:

```text
if arrears_months >= N:
    default = True
```

or:

\[
Default\ if\ DebtService/Income > threshold
\]

for a sustained period.

Avoid making default instantaneous after one bad month unless the experiment explicitly studies that behavior.

## Employment behavior

Households either work for a firm or are unemployed. V0.1 can avoid job-search sophistication.

Unemployment affects:

- wage income;
- desired consumption;
- ability to service debt;
- default probability.

## Inflation expectations

Start simple.

Adaptive expectation:

\[
E_i[\pi_{t+1}] = \lambda \pi_t + (1-\lambda)E_i[\pi_t]
\]

In V0.1, expectations mainly matter for nominal loan pricing or household decisions if included. Later versions may give agents heterogeneous expectations.

## Household groups for reporting

Always retain grouping dimensions so aggregate outcomes can be decomposed by:

- renter / homeowner / mortgaged homeowner;
- indexed mortgage / nominal mortgage;
- income quintile;
- initial LTV quintile;
- liquidity level;
- age group if later added.

## Acceptance criteria

- household cash cannot be spent twice;
- mortgage revaluation does not itself consume deposits;
- debt service does consume deposits;
- net worth falls when indexed debt rises holding assets constant;
- unemployed households respond through income and consumption without requiring special-case code in the market layer.
