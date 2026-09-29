# Demand correction, model 0.1.1

The earlier published experiment was not a stable shock experiment. Removing the shock left
only 4 nominal-regime jobs and 7 indexed-regime jobs after 18 months, from 20 initially.
Its import payments accumulated abroad with no export demand. Consumption was capped at current
wages, excluding dividends from desired spending and forcing jobless households' budgets to zero
regardless of savings. Falling sales, inventory adjustment, layoffs, and defaults amplified this
structural demand shortfall. The earlier claim that indexation cushioned a shock-driven collapse
must not be retained as evidence about the economy.

## Corrected rules

Both regimes use the same rules, initialization, and named random streams:

- Monthly desired household consumption is `c_y * max(0, wages + cash dividends - actual
  mortgage payment) + c_w * opening deposits`, capped by cash remaining after settlement.
  The defaults are `c_y = 1` and `c_w = 0.05` per month. Unemployed households may draw remaining
  savings; neither principal revaluation nor capitalized interest supplies spendable cash.
- Banks distribute only collected mortgage interest, equally across households. Unpaid interest
  remains an accrued claim. This deliberately simple ownership and payout rule is an assumption,
  not a calibrated description of banks or household portfolios.
- Foreign buyers have a fixed nominal monthly budget. When `monthly_export_demand_isk` is null,
  initialize it to full-employment production times the opening imported-input unit cost:
  3,000,000 ISK for the published population. An explicit integer overrides the budget; zero
  disables exports. It never follows current imports, employment, mortgage payments, FX, or CPI.
- Domestic buyers have priority; exports buy remaining physical inventory at posted firm prices.
  Sales expectations include both customers. CPI uses household purchases only. Household real
  consumption excludes exported units; total firm revenue equals consumption plus export receipts.
- Foreign buyers use their accumulated domestic deposits first. A shortfall creates a bank
  settlement asset and mirrored foreign liability, plus matching foreign deposit asset and bank
  deposit liability. Export payments then transfer those deposits to firms. No unrecorded money
  or goods are created. The rest-of-world settlement facility is unbounded in this model; this is
  an explicit external-financing assumption, not evidence that every trade path is sustainable.

This is a transparent open-economy closure and a behavioral correction, not a rule that forces
employment or defaults to a target. Firm hiring, firing, pricing, mortgage terms, and shocks are
unchanged. The budget is nominal: higher import prices can still reduce real demand and output.
Alternative export demand, ownership, savings propensities, and credit creation remain material
sensitivity questions. Fresh mortgages, housing transactions, fiscal stabilization, and firm entry
are still omitted.

## Validation and interpretation

The no-shock regression now uses the actual published import exposure and mortgage configuration,
extended to 120 months at seeds 1010, 42, and 808. A separate 200-household/10-firm case checks scale.
Both regimes retain full employment and zero defaults in these cases, with no more than a 10%
decline in last-year versus first-year production. Disabling export demand permits contraction;
stability is not hard-coded. The prior closed-economy stability gate remains unchanged.

Tests also verify household liquidity constraints, disposable-income effects, physical goods,
export payments, collected-interest dividends, exact mirrored claims, deterministic pairing,
lagged CPI, and policy transmission. Economic golden values are regenerated only after these
independent checks; matching a snapshot is not itself evidence of stability.

In the corrected 18-month shock experiment both regimes retain 20 jobs and record zero defaults.
Total household spending is 165,297,096 ISK nominal versus 161,994,709 ISK indexed; household goods
consumed are 108,377 versus 106,212 units. Opening debt service remains 2,560,911 versus 1,604,555
ISK. Closing debt is 452,338,298 versus 460,211,944 ISK. CPI ends at 102,467 in both regimes.

Indexation still lowers initial borrower payments, but it does not increase aggregate consumption
in this corrected experiment. Interest is recycled as dividends; principal repayment reduces
credit and deposits. These contract and closure assumptions matter to the result. Neither the
earlier collapse nor this single stable comparison establishes a general welfare ranking.

The publication uses model version 0.1.1 and replay/export revision `demand-2`; old service-cache
identities must not serve the corrected experiment. The checked release manifest pins all new
artifacts, while Git history retains the superseded results.
