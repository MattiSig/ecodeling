# Ecodeling v0.1 publication package

This directory is the human-readable release index for the first mortgage-indexation mechanism
laboratory. The authoritative browser artifact remains
[`web/replay/canonical-v1.json.gz`](../../web/replay/canonical-v1.json.gz); analytical Parquet
outputs can be regenerated from the checked configuration rather than duplicated in Git.

## Reproducibility box

| Field | Published value |
|---|---|
| Model version | `0.1.0` |
| Replay schema | `1` |
| Canonical source commit | `e9da824ebad39679ceabe0ad3825f3a247618acb` |
| Release baseline | `e20ea49919863af2dd6d8e6dc7fee0a10b59c95a` |
| Configuration | [`canonical-config.json`](canonical-config.json) |
| Seed | `1010` |
| Shock | permanent 10% FX depreciation beginning at zero-based model month `3` |
| Regimes | mortgage alpha `0` and `1`; all named random streams shared |
| Calibration status | stylized mechanism calibration, not an empirical Iceland forecast |
| Primary sources | [`docs/release-v0.1.md`](../../docs/release-v0.1.md#empirical-source-audit) |

The replay's source commit identifies the model implementation on which the immutable canonical
run was first established. The v0.1 release commit adds publication evidence and does not alter
economic transition rules. Regenerating the replay at v0.1 changes its declared model version but
not its economic series.

## Published artifacts

- `canonical-config.json` is the versioned publication copy of the checked analytical fixture with
  the canonical replay scenario identity.
- `manifest.json` pins SHA-256 digests for the configuration, analytical summary, compressed replay,
  replay metadata/schema, and fallback exports.
- `canonical-summary.json` records selected replay-derived opening, shock-month, closing, peak, and
  trough values. It is a convenience index, not a second authoritative output.
- `fallback/` contains a textual transcript, a static SVG figure, and a six-scene recorded image
  sequence for channels that cannot execute the custom element. Every item names the same run.
- [`docs/release-v0.1.md`](../../docs/release-v0.1.md) records methodology, empirical-source audit,
  limitations, validation evidence, and measured operating limits.
- [`docs/operations.md`](../../docs/operations.md) defines deployment, backup, cleanup,
  observability, security, and rollback for the CV-owned route and the optional API.

Regenerate the complete analytical report with:

```bash
uv run ecodeling compare tests/fixtures/phase10_report_config.json \
  --output outputs/v0.1-canonical
```

Run the release gate with `npm run release:verify`. Network-dependent Railway checks are listed in
the operations runbook and are deliberately separate from the clean-checkout offline gate.
