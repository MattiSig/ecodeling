# Firm Behavior

## V0.1 role

Firms convert labor and imported inputs into a generic consumer good. Their pricing decisions create the domestic price level from which CPI is calculated.

## Production

Simplest technology:

\[
Q_{j,t}=A_j L_{j,t}
\]

where \(A_j\) is labor productivity.

Imported inputs can be represented as a cost share rather than a physical Leontief input in V0.1.

## Unit cost

\[
UC_{j,t}=(1-m_j)\frac{WageBill_{j,t}}{Q_{j,t}} + m_j P^{imp}_t + OtherCost_{j,t}
\]

This is stylized. The important feature is that exchange-rate and foreign-price shocks affect firms in proportion to their import exposure.

## Price setting

Target price:

\[
P^{target}_{j,t}=(1+\mu_j)UC_{j,t}
\]

Firms need not jump instantly to target. A partial adjustment rule can create realistic price stickiness:

\[
P_{j,t}=P_{j,t-1}+\lambda_p(P^{target}_{j,t}-P_{j,t-1})
\]

with optional menu-cost or threshold rules later.

## Important anti-shortcut rule

Do **not** define:

\[
P_{j,t}=P_{j,t-1}(1+\pi_t)
\]

for ordinary consumer goods.

That would hard-code CPI persistence and create a circular system in which the prices used to calculate CPI are automatically moved by CPI itself.

Instead, prices respond to costs, demand, capacity, inventories, and markups. Indexation operates on contracts feeding into those costs.

## Demand expectations

Simple adaptive expectation:

\[
Q^{expected}_{j,t}=\lambda_q Sales_{j,t-1}+(1-\lambda_q)Q^{expected}_{j,t-1}
\]

Desired production adds an inventory buffer.

## Employment

Desired workers:

\[
L^d_{j,t}=\left\lceil\frac{Q^{desired}_{j,t}}{A_j}\right\rceil
\]

Firms hire when below target and fire gradually when above target.

## Wages

Baseline wage changes can depend on labor tightness and recent inflation without formal CPI indexation.

Later wage-indexation experiment:

- keep normal wage-setting rule;
- add contract indexation operator with \(\alpha_w\);
- compare the incremental effect.

## Profits and cash

\[
Profit=Revenue-Wages-ImportedInputs-Interest-Taxes-OtherCosts
\]

Firm deposits rise/fall with cash profit and financing flows.

## Insolvency

V0.1 may allow loss-making firms to continue if cash remains positive. If firm entry/exit is introduced, replacements should enter with documented initial balance sheets so the population does not collapse mechanically.

## Acceptance criteria

- an import price increase raises unit costs for firms with positive import share;
- price response depends on the firm's pricing adjustment rule;
- household purchases plus export purchases equal firm revenue;
- wages paid equal household wage income;
- firm output cannot exceed defined technology/capacity without an explicit rule.
