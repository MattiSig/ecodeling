# Monthly Simulation Loop

## Goal

The monthly execution order must be explicit because changing event order can change ABM results.

## Recommended V0.1 sequence

### 0. Start-of-period checks

- load opening balances;
- verify no broken references;
- advance simulation clock.

### 1. Foreign processes and shocks

Update:

- exchange rate;
- foreign price level;
- foreign interest rate if used.

### 2. Import costs

Calculate:

\[
P^{imp}_t=E_tP^*_t
\]

and update firm input costs.

### 3. Contract indexation reference becomes available

Resolve the lagged CPI observation used for this month's indexation.

### 4. Apply contract revaluations

For indexed contracts:

- mortgage principal;
- later: rents, deposits, wages, pensions, etc.

Record revaluation separately from cash flows.

### 5. Firms form expectations and production plans

- expected demand;
- desired inventory;
- desired employment;
- target price.

### 6. Labor market

- vacancies/firing;
- matching;
- wages for current period determined.

### 7. Production

Firms produce goods based on workers/productivity and update inventory.

### 8. Firms set prices

Apply pricing rule using current costs and desired markup.

### 9. Household income flows

- wages paid;
- taxes paid;
- transfers received;
- deposit interest if included.

### 10. Mortgage payments

- calculate interest;
- calculate scheduled amortization;
- collect payments;
- update arrears/default status.

### 11. Household consumption decisions

Households form desired spending based on disposable income, liquidity, and wealth.

### 12. Consumer-goods market

Households choose firms, transactions occur, inventories fall, and sales revenue is recorded.

### 13. Firm and bank financial closure

- pay remaining costs;
- calculate profit;
- recognize loan losses;
- calculate bank profits/equity;
- apply capital constraints for next period.

### 14. Government closure

Update fiscal cash/debt position.

### 15. Calculate CPI and inflation

Use realized current-period market prices/weights to calculate CPI.

### 16. Central bank policy decision

Update policy rate according to configured rule for use in current/next reset period as specified.

### 17. Update balance sheets and diagnostics

Record:

- closing stocks;
- sector flow totals;
- revaluation totals;
- accounting gaps;
- distribution metrics.

### 18. Assert invariants

In debug/testing runs, fail immediately if a core accounting identity is violated.

## Timing convention

The implementation must clearly define whether policy rates and CPI values set at month `t` affect contracts in `t` or `t+1`.

Recommended convention:

- current month's CPI is calculated at period end;
- it can only affect future indexation after the contract's lag;
- current policy decision affects resettable rates beginning next month.

This avoids agents responding to information that has not yet been generated.

## Determinism

All random draws must come from seeded pseudo-random generators. Ideally use independent random streams for:

- household initialization;
- labor matching;
- consumption matching;
- shocks;
- defaults/behavioral noise.

This allows experiment regimes to share identical shock streams.
