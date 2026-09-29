# Publication and operations runbook

## Ownership and deployment

`MattiSig/ecodeling` owns the Python model, component source, canonical replay, and checksummed
handoff. `MattiSig/cv` owns `/work/ecodeling`, page copy, theme tokens, vendored assets, and the
existing Railway `web` service. Canonical playback does not deploy the FastAPI service.

1. Run `npm run release:verify` from a clean Ecodeling checkout.
2. Run `scripts/export-cv-assets.sh /path/to/cv/web/static/ecodeling`.
3. In the CV checkout, run `sha256sum -c web/static/ecodeling/SHA256SUMS` and `make validate`.
4. Inspect the vendored diff, commit it in the CV repository, and deploy its `main` branch.
5. Verify `GET /healthz`, `/work/ecodeling`, the versioned JavaScript, CSS, and gzip replay.
6. In a real browser, verify custom-element upgrade, an empty console, full paired playback,
   narrow/mobile containment, dark and light host tokens, and no request whose path contains
   `/api/v1/` when the page omits `api-base`.

The currently verified Railway origin is
`https://web-production-68429.up.railway.app`. A custom domain is not yet a release dependency.

## Backup, cache, and cleanup

The canonical deployment is recoverable from Git: both repositories pin the source and vendored
assets, while `SHA256SUMS` detects corruption. Keep the preceding CV commit until the new page and
assets pass production verification. Railway need not persist model state for canonical playback.

For an optional API deployment, back up `jobs.sqlite3` and `artifacts/` together from the directory
named by `ECODELING_SERVICE_DATA`. Stop submissions or snapshot both paths atomically. Completed
artifacts are immutable; queued/running rows are safely marked failed after restart. Cleanup may
remove failed/cancelled metadata and unreferenced artifacts only after retaining logs needed for
diagnosis. Never remove the checked canonical replay as API cache cleanup.

## Observability

The CV service exposes `/healthz` and Railway restart/health status. Monitor page and asset status,
latency, content lengths, five-minute error rate, and browser console failures after deployment.
Log the CV commit, Ecodeling release/tag, replay SHA-256, and asset checksum manifest for every
publication.

For the optional API, log job ID, configuration hash, model version, status transition, duration,
compressed/uncompressed size, and bounded failure code. Do not log full request bodies or agent
records. Alert on queue saturation, repeated `simulation_failed`, missing completed artifacts,
health failure, or replay-size rejection.

## Security boundary

The static CV page supplies no `api-base`, so it cannot submit experiments. Vendored URLs are
content-versioned and the export manifest is verified before commit. The host sends `nosniff`,
clickjacking, and referrer-policy headers. Treat replay JSON as untrusted input: the component
validates schema compatibility before rendering and does not insert replay strings as HTML.

If the API is deployed later, place it behind same-origin TLS and rate limiting. Retain the strict
parameter allowlist, 8 KiB request cap, bounded queue/process counts, replay-size cap, structured
errors, and immutable artifact responses. Do not expose the service-data directory directly.

## Rollback

1. Redeploy or revert the previous known-good CV commit. Because assets are embedded and URLs are
   content-versioned, page and assets roll back together.
2. Verify `/healthz`, the route, and the prior `SHA256SUMS`.
3. If only the component fails, remove the new embed from the CV route or restore its prior vendored
   directory; the textual page remains available.
4. If an optional API fails, remove `api-base` first. Story, Explore, and Compare continue from the
   static canonical replay while the service is repaired.

No database migration or destructive cache action is required to roll back the canonical release.
