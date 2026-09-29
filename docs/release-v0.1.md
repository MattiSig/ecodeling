# Ecodeling v0.1 release evidence

## Scope and research status

Version 0.1 is a stock-flow-consistent mechanism laboratory for one question: how mortgage CPI
indexation changes the timing and location of an imported-inflation shock. It is not calibrated to
forecast Iceland, estimate causal policy effects, or rank regimes with a welfare score. Parameters
are empirical anchors only where explicitly cited; the canonical run is otherwise stylized or
numerical and every public statement must retain that distinction.

The authoritative causal chain is:

```text
FX shock → imported input cost → firm price → CPI → lagged mortgage revaluation
         → household and bank balance sheets → payments/defaults/consumption
```

Python owns all transitions. Analytical Parquet outputs and ledgers are authoritative; replay v1
is a reconciled presentation derivative. The browser only selects, aligns, aggregates, and renders
recorded data.

## Empirical-source audit

Audit performed 2026-09-29 against institutional or primary sources:

| Statement used by the project | Source and finding | Classification / model use |
|---|---|---|
| Financial indexation uses a lagged CPI observation. | [Statistics Iceland, CPI May 2026](https://www.statice.is/publications/news-archive/prices/consumer-price-index-in-may-2026/) says the CPI compiled in mid-May was applicable for July indexation. | Empirical institutional example motivating a parameterized lag; not a universal hard-coded legal rule. |
| CPI-indexed loans were 54% of household debt and softened immediate exposure to high nominal rates. | [IMF 2026 Article IV, Country Report 26/208](https://www.elibrary.imf.org/abstract/journals/002/2026/208/article-A001-en.xml). | Current empirical anchor for prevalence and the cash-flow timing channel; the canonical mortgage share is not calibrated to 54%. |
| Indexed principal can negatively amortize and banks can have positive net indexed exposure. | [IMF 2023 FSAP technical note, Country Report 23/276](https://www.elibrary.imf.org/view/journals/002/2023/276/article-A001-en.xml). | Institutional motivation for separate revaluation and bank-position accounting; not a claim that the synthetic banks reproduce Icelandic exposures. |
| Indexation and rate fixation are distinct transmission dimensions. | [Central Bank of Iceland, *Verðtrygging og peningastefna* (2009)](https://sedlabanki.is/frettir-og-utgefid-efni/grein/2009-02-02-1--rit-Verdtrygging-og-peningastefna). | Primary policy-research motivation for explicit reset/pass-through rules. |
| Heterogeneous agents can be joined to coherent balance sheets and flows. | Caiani et al. (2016), [DOI 10.1016/j.jedc.2016.06.001](https://doi.org/10.1016/j.jedc.2016.06.001). | Peer-reviewed methodological precedent, not an empirical calibration source. |

The audit found no unsupported empirical number in the public repository narrative. It did find a
deliberate boundary worth repeating: the 54% statistic and two-month Statistics Iceland example
motivate configurable mechanisms; neither is copied into the canonical parameter set as an
Iceland estimate.

## Methodology and canonical result

The published pair uses one seed, one initialized population, the same named labor, goods, shock,
default, and initialization streams, and the same permanent 10% depreciation. Mortgage alpha is
the declared structural difference. Nominal pricing includes expected inflation and an inflation
risk premium; indexed pricing moves the realized CPI component into principal after the lag.

The 18-month canonical run exists to explain the mechanism quickly. Its CPI ends at 102,467 in
both regimes. Its final mortgage stocks are 452,338,298 ISK nominal and 460,211,944 ISK indexed;
opening debt service is 2,560,911 ISK nominal and 1,604,555 ISK indexed. Under this model
structure, parameterization, and seed, indexed debt carries less opening cash-flow burden and more
closing principal. These are simulated outcomes, not estimates of household outcomes in Iceland.

The actual canonical no-shock calibration now passes 120-month stability gates across three seeds
and at 200-household scale. Separate 600-month runs check accounting and pairing, not universal
economic stability. See [the model 0.1.1 correction](demand-correction.md).
Distributional uncertainty and parameter dependence are exercised through the paired batch and
sensitivity machinery; the checked canonical replay must not be interpreted as their substitute.

## Limitations

- The model has one generic consumer good and stylized firms, expectations, labor matching, and
  default. It omits endogenous housing transactions, refinancing, prepayment, demographics,
  detailed taxation, pension funds, and endogenous exchange-rate formation.
- Housing value is initialized rather than generated in a housing market. Zero-recovery default, collected bank-interest dividends, consumption from disposable income
  and savings, and fixed nominal export demand with external settlement credit are transparent
  mechanism assumptions.
- The production replay uses 20 households, four firms, and one clearing bank for compactness,
  while validation separately exercises the intended 1,000-household and two-bank scale.
- The canonical 18-month path is too short for a general persistence or welfare conclusion.
- The policy rule, pass-through, consumption propensity, import share, price adjustment, and loan
  terms are stylized. Sensitivity support does not turn them into empirical estimates.
- Government and central-bank balance sheets are not modeled; replay fields are `null`, never zero.
- Results are conditional on declared rules and common-random-number design. Simulation alone does
  not identify real-world causal effects.

## Accessibility and fallback evidence

The component supplies exact values, semantic controls, keyboard operation, non-color regime
encoding, mobile containment, and axe-tested Story/Explore/Compare views. `prefers-reduced-motion`
and the `static` attribute replace continuous flows with discrete states. The release package adds
the same run's textual transcript, static SVG, and six-scene image sequence. The sequence is the
recorded fallback for video channels: it preserves the event order without requiring motion.

## Performance and operating limits

Measurements are taken on the release workstation with Chromium and Python 3.12 and are evidence,
not cross-device guarantees. The release gate records:

- canonical replay: exact compressed and uncompressed sizes in `web/replay/canonical-v1.metadata.json`;
- public component bundle: approximately 168 KB JavaScript and 36 bytes host CSS;
- canonical Story/Explore/Compare is static-host playback and makes no simulation request;
- custom API: 8 KiB request body, 6–60 months, 10–250 households, 2–50 firms, at most four worker
  processes by configuration, eight pending jobs by default, and 2 MB uncompressed replay output;
- completed API artifacts are immutable and collision-deduplicated by model version plus complete
  configuration hash.

The browser gate plays the entire 18-month paired timeline without drift. The API gate runs a real
six-month, ten-household, two-firm browser-to-worker-to-replay job inside a 30-second test budget.
Canonical load and playback remain available if the optional API is absent.

## Validation statement

Ecodeling v0.1 is a mechanism-calibrated educational AB-SFC model. Validation covers exact whole-
ISK accounting, contract goldens, lag/no-look-ahead timing, reproducible named randomness, no-shock
stability, shock direction, common-random-number comparisons, serial/parallel batches, replay
reconciliation, API limits, browser accessibility, and production-host integration. Major omitted
channels are listed above. The release does not claim empirical validation of Icelandic aggregate
or household moments.

## Production verification

On 2026-09-29 the Railway origin
`https://web-production-68429.up.railway.app` returned `200` for `/healthz`,
`/work/ecodeling`, the versioned component JavaScript and CSS, and the canonical gzip replay.
Downloaded asset bytes matched the CV repository's checked `SHA256SUMS`. Headless Chromium loaded
the custom element with no console errors in both host themes, found no Laboratory control or
`api-base` attribute, and observed no `/api/v1/` request. Desktop screenshots were inspected for
both themes.

The live replay inspected during hardening identifies model version `0.0.0`; its economic series
and source commit are the same canonical run, while the v0.1 handoff changes the declared package
version and gzip checksum. Publishing the new handoff still requires an explicitly authorized CV
commit/deploy. The release candidate was therefore also exported to a fresh directory, passed its
own `SHA256SUMS`, and was exercised by the clean-copy production-like browser gate before tagging.

## Phase 18 reader and snapshot correction

The current component adds Article onboarding, a shared accessible glossary, replay-derived
numerical evidence, and a conditional conclusion. During its balance-sheet review, an independent
journal audit exposed an omission of opening entries in the original sector snapshot exporter.
The `stocks-1` correction reconstructs complete positions and rejects mismatches with analytical
bank equity and household mortgage liabilities. The model, aggregate trajectories, flows, events,
distributions, and representative histories remain unchanged. Current checksums and recorded
fallbacks reflect the correction; the historical release tag remains unchanged. This is a local
verified handoff, not evidence that the new assets have been deployed to the live CV site.
