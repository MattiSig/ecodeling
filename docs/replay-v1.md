# Replay schema v1

Replay v1 is the immutable browser contract for a completed, paired nominal/indexed experiment.
The Python simulation, ledger, and analytical outputs remain authoritative; a browser may filter,
compare, and animate this data but must not calculate an economic transition.

## Encoding, compatibility, and limits

Canonical JSON is UTF-8, compact, key-sorted, and contains no non-finite numbers. Published files
use deterministic gzip (`Content-Encoding: gzip`). `manifest.schema_version` is `1`; readers must
also honor the inclusive `compatibility.minimum_reader_schema` and `maximum_reader_schema` range.
Unknown top-level or record fields are invalid. Replay v0 is the earlier household-bank audit
contract and cannot be losslessly migrated because it lacks the endogenous economy and paired-run
tables; loaders return a structured compatibility error. Future unknown versions are rejected.

`manifest.maximum_uncompressed_bytes` is checked during export, serialization, and browser
validation. The default is 2,000,000 bytes. The checked canonical artifact records compressed and
uncompressed sizes plus the SHA-256 of canonical uncompressed bytes in its sidecar metadata.
The generated `web/replay/replay-v1.schema.json` is the machine-readable definition of every
required field, nullable field, enum, constraint, and record shape; the TypeScript declaration is
the browser-facing static view of that same contract.

## Units and missing values

- All `*_isk` values are exact nominal whole Icelandic krónur. The reconciliation tolerance is
  therefore zero ISK.
- Rates are integer basis points. Price and exchange-rate indices use 100,000 at base.
- Production, inventories, and real consumption are physical units; household/default fields are
  counts.
- `null` means unavailable. In particular, the current model has no government or central-bank
  balance sheet; their required sector rows contain null stocks rather than invented zeroes.

## Tables and fields

`manifest` contains the schema/reader versions, bundle/model/commit/scenario identity, shared seed,
the nominal and indexed configuration hashes (`parameter_sets`), aligned months, global units,
zero-ISK rounding tolerance, byte limit, and representative-selection rule.

`timeline` contains contiguous `index`, ISO `month`, and Boolean `shock` and `policy_decision`
markers. `runs` contains `regime`, `run_id`, `scenario_id`, `seed`, and `configuration_hash` for the
nominal run followed by the indexed run.

`sector_snapshots` contains `regime`, `month`, `sector`, financial and real assets, liabilities,
equity, and physical inventory. It includes households, firms, banks, government, central bank,
and foreign sector every month. `sector_flows` contains regime/month, typed flow, source and target
sectors, exact `amount_isk`, and its `ledger_entry_id`. Supported recorded flows are wages,
consumption, imports, mortgage interest, principal payment, and bank dividends. Taxes, transfers,
and new credit are omitted because v0.1 does not model those flows; omission is not a zero value.

`events` contains a globally unique `id`, regime/month, an explicit economic `event_type`, optional
amount and unit, and authoritative `source_id`. Types are `FX_SHOCK`, `FOREIGN_PRICE_SHOCK`,
`CPI_REVALUATION`, `POLICY_RATE_CHANGE`, `RATE_RESET`, `ARREARS`, and `DEFAULT`.

`representative_agents` contains regime, stable household ID, declared cohort, matched household
ID, and the full monthly `track`. Each track point records wage income, consumption, deposits,
mortgage principal/payment/revaluation, arrears, and default status. IDs are selected once from
the shared initialized population and are identical across regimes.

`aggregate_series` contains regime, stable metric name, unit, nominal/real/status classification,
and aligned month/value points. Nullable values represent genuinely unavailable observations such
as annual inflation before twelve months. `distribution_series` contains regime/month, one of the
five required cohort dimensions, cohort label, household count, income, consumption, mortgage
principal, debt service, revaluation, deposits, net worth, and defaults.

`scenario_pairing` names both run IDs, the shared seed, common initialization and shock-path
assertions, stable-ID matching, named shared random streams, and the sole declared structural
difference: mortgage indexation topology.

## Reconciliation and provenance

Export fails unless both timelines, seeds, initialized households/firms, and shock paths match.
Aggregate chart values are checked against simulation monthly outputs; interest plus principal
flows must equal authoritative debt service; and income-quintile rows must sum to aggregate
consumption and mortgage principal. Sector stocks are reconstructed month by month from ledger
postings. Every nonzero visible flow names an existing ledger entry. Python and the TypeScript-
facing runtime validator both consume the same checked compressed fixture as their contract test.
