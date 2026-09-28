# Validation and Testing

## Four types of validation

### 1. Code correctness

Does the implementation match the specification?

### 2. Accounting correctness

Do balance sheets and flows reconcile?

### 3. Behavioral sanity

Do agents respond in the expected direction to controlled changes?

### 4. Empirical plausibility

Does the model reproduce selected real-world moments/stylized facts well enough for the intended experiment?

## Unit tests

### Indexation

- zero alpha produces zero revaluation;
- full alpha reproduces CPI change exactly;
- partial alpha scales correctly;
- lag references correct month;
- negative CPI works under no-floor rule.

### Loans

- payment decomposition: payment = interest + principal reduction + fees if any;
- closing principal reconciles with opening principal + revaluation - amortization + arrears capitalization if configured;
- maturity schedule is deterministic.

### CPI

- weighted price index calculation is correct;
- monthly and 12-month inflation calculations are correct.

### Balance sheets

- deposits match bank liabilities;
- mortgage assets match liabilities;
- transaction ledger nets to zero.

## Integration tests

### No-shock steady run

Run at least 600 months with shock process disabled. The model should not explode solely because of numerical drift.

### Zero-indexation equivalence

A contract with the indexation feature enabled but `alpha=0` should match the equivalent non-indexed implementation, holding interest rules equal.

### No-import-exposure test

If all firms have import share zero, an exchange-rate shock should not directly raise firm costs.

### No-debt test

If households have no mortgages, changing mortgage indexation parameters should not change the economy except through code bugs or downstream initialization differences.

### Counterparty test

Every mortgage revaluation must be equal and opposite across borrower and lender accounting positions.

## Directional sanity tests

These are not hard empirical truths but useful checks:

- raising import prices should raise costs for import-dependent firms;
- raising prices should raise CPI;
- raising the policy rate should raise resettable nominal borrowing costs;
- increasing mortgage principal should lower borrower net worth holding house value fixed;
- loan losses should lower bank equity.

## Statistical validation

For stochastic models, never validate a behavior from one seed.

Track distributions across seeds and compare moments with uncertainty.

## Regression tests

Store a small deterministic scenario with fixed seed and expected summary outputs. After refactoring, check whether outputs changed. If they did, require an explicit explanation.

## Failure modes worth catching

- CPI indexing consumer prices directly by accident;
- double-counting mortgage indexation as both cash payment and revaluation;
- updating household debt without updating bank assets;
- using annual inflation as if it were monthly;
- using future CPI because of event-order leakage;
- changing RNG draw order between regimes and thereby destroying paired comparison;
- allowing nominal mortgage pricing to omit expected inflation while indexed pricing includes CPI principal adjustment;
- conflating fixed-rate versus floating-rate effects with indexation effects.

## Model validation statement

Every published result should carry a short statement describing:

- version;
- calibration status;
- whether the exercise is mechanism-based or empirically calibrated;
- major omitted channels;
- sensitivity checks performed.
