# Research Sources and Notes

## Purpose

These sources ground the design in Icelandic institutions and in agent-based/stock-flow-consistent modeling. They are not a claim that the model reproduces each source exactly.

_Last checked: September 2026._

## Statistics Iceland — CPI and financial indexation

**Consumer price index in May 2026**
Statistics Iceland, 28 May 2026. The release states that the CPI compiled in May 2026 was applicable for indexation purposes in July 2026, providing a concrete example of the lag between CPI measurement and financial indexation.

https://www.statice.is/publications/news-archive/prices/consumer-price-index-in-may-2026/

Use in model:

- motivates a parameterized indexation lag;
- provides CPI methodology/data source for later calibration.

## IMF — Iceland 2026 Article IV

**Iceland: 2026 Article IV Consultation — Staff Report**
IMF Country Report No. 2026/208, July 2026.

https://www.imf.org/en/publications/cr/issues/2026/07/29/iceland-2026-article-iv-consultation-press-release-and-staff-report-578170

Relevant observation:

- CPI-indexed loans were reported as 54% of outstanding household debt;
- the report notes that the prevalence of CPI-indexed loans cushioned the impact of high nominal rates on borrowers.

Use in model:

- motivates explicit separation of immediate debt-service effects from principal/balance-sheet effects;
- provides a current empirical anchor for indexation prevalence.

## IMF — Iceland 2023 financial-sector stress testing

**Financial Sector Assessment Program — Technical Note on Stress Testing and Systemic Risk Analysis**
IMF Country Report No. 23/276, July 2023.

https://www.elibrary.imf.org/view/journals/002/2023/276/article-A001-en.xml

Relevant observations:

- indexed loans charge real rates and can have a lower short-run interest burden than non-indexed loans;
- inflation is added to indexed loan principal and can lead to negative amortization;
- the analysis reported that Icelandic banks had more indexed assets than indexed liabilities in the examined data, leaving a positive net inflation-indexed position;
- borrowers were observed moving between indexed and non-indexed mortgage products as relative conditions changed.

Use in model:

- motivates bank `NetIndexedPosition`;
- motivates later endogenous household product choice;
- motivates separate cash-flow and borrower-equity channels.

## Central Bank of Iceland — indexation and monetary policy

**Verðtrygging og peningastefna**
Ásgeir Daníelsson, Central Bank of Iceland, February 2009.

https://sedlabanki.is/frettir-og-utgefid-efni/grein/2009-02-02-1--rit-Verdtrygging-og-peningastefna

The paper discusses how price indexation, fixed interest rates, and annuity-style long-term loans interact with monetary-policy transmission, including the role of refinancing and new lending.

Use in model:

- reinforces the need to distinguish indexation from fixed/floating interest-rate structure;
- motivates tracking monetary transmission through new credit as well as existing debt service.

## Agent-based stock-flow-consistent benchmark

**Caiani, A., Godin, A., Caverzasi, E., Gallegati, M., Kinsella, S., & Stiglitz, J. E. (2016). "Agent based-stock flow consistent macroeconomics: Towards a benchmark model." Journal of Economic Dynamics and Control, 69, 375–408.**

DOI: https://doi.org/10.1016/j.jedc.2016.06.001

Accessible metadata/abstract:

https://ideas.repec.org/a/eee/dyncon/v69y2016icp375-408.html

Use in model:

- methodological inspiration for combining heterogeneous agents with coherent balance sheets and transaction flows;
- useful reference for calibration, validation, and macro ABM architecture.

## Source hierarchy for future research

Prefer, roughly in this order:

1. Statistics Iceland;
2. Central Bank of Iceland;
3. Icelandic government/legal sources;
4. IMF/OECD institutional reports;
5. peer-reviewed academic papers;
6. bank product documentation for contract implementation details;
7. journalism/blogs only for leads, not primary calibration.

## Research notes to resolve before empirical V1.0

- Exact legal and operational indexation formula used by major mortgage products.
- Timing conventions for indexation, interest accrual, and scheduled payment calculation.
- Current distribution of indexed vs non-indexed loans by lender type and borrower characteristics.
- Fixed/floating reset distribution for both indexed and non-indexed loans.
- Mortgage refinancing/prepayment behavior.
- Indexed versus nominal deposit and bond funding shares.
- Household income/debt/LTV joint distributions.
- Treatment of owner-occupied housing in CPI through time.
- Wage-contract indexation practices and lags by sector.
- Pension and benefit indexation rules.
