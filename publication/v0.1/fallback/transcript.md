# Ecodeling v0.1 static transcript

Run `canonical-replay-v1`, seed 1010, follows the same synthetic economy from January 2025 through
June 2026 under nominal and fully CPI-indexed mortgage structures. It is a stylized mechanism
experiment, not a forecast or an estimate of Iceland.

1. A permanent 10% exchange-rate depreciation begins in April 2025.
2. Recorded import costs rise and firms partially adjust their prices.
3. The simulated CPI rises from 100,000 to 100,667 in April and reaches 102,467 by June 2026 in
   both canonical regimes.
4. After the declared information and contract lag, indexed mortgage principal is revalued on both
   the household liability and bank asset. The nominal contract has no CPI principal revaluation.
5. Contract pricing differs by construction: the nominal coupon includes expected-inflation and
   risk-premium terms, while the indexed contract carries CPI changes in principal. Opening total
   debt service is therefore 2,560,911 ISK nominal and 1,604,555 ISK indexed.
6. By the last canonical month, recorded mortgage principal is 452,338,298 ISK nominal and
   460,211,944 ISK indexed. Consumption and bank equity also diverge through the recorded payment,
   balance-sheet and demand feedback rules. Both regimes retain 20 jobs and record zero defaults.
7. Total spending is 165,297,096 ISK nominal and 161,994,709 ISK indexed; real household purchases
   are 108,377 and 106,212 units. The corrected model includes fixed nominal export demand and
   consumption from disposable income and savings. See `docs/demand-correction.md`.

These values describe one checked seed. Distributional claims require the paired Monte Carlo and
sensitivity workflows; no single welfare score or causal empirical claim is attached to them.
