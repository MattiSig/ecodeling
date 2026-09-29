export class ReplayCompatibilityError extends Error {}

export function validateReplayV1(bundle, byteLength) {
  if (!bundle || typeof bundle !== "object" || !bundle.manifest) {
    throw new ReplayCompatibilityError("Replay manifest is missing.");
  }
  const version = bundle.manifest.schema_version;
  if (version === 0) {
    throw new ReplayCompatibilityError(
      "Schema v0 is audit-only and cannot be losslessly migrated to v1.",
    );
  }
  if (version !== 1) {
    throw new ReplayCompatibilityError(`Unsupported replay schema version: ${String(version)}.`);
  }
  const requiredTables = [
    "timeline",
    "runs",
    "sector_snapshots",
    "sector_flows",
    "events",
    "representative_agents",
    "aggregate_series",
    "distribution_series",
    "scenario_pairing",
  ];
  for (const table of requiredTables) {
    if (!(table in bundle)) throw new ReplayCompatibilityError(`Replay table is missing: ${table}.`);
  }
  const months = bundle.manifest.months;
  if (
    !Array.isArray(months) ||
    bundle.timeline.length !== months.length ||
    bundle.timeline.some((point, index) => point.index !== index || point.month !== months[index])
  ) {
    throw new ReplayCompatibilityError("Replay timeline is not aligned.");
  }
  if (bundle.runs.map((run) => run.regime).join(",") !== "nominal,indexed") {
    throw new ReplayCompatibilityError("Replay must contain aligned nominal and indexed runs.");
  }
  if (
    typeof byteLength === "number" &&
    byteLength > bundle.manifest.maximum_uncompressed_bytes
  ) {
    throw new ReplayCompatibilityError("Replay exceeds its declared payload-size limit.");
  }
  for (const agent of bundle.representative_agents) {
    if (
      agent.household_id !== agent.matched_household_id ||
      agent.track.length !== months.length ||
      agent.track.some((point, index) => point.month !== months[index])
    ) {
      throw new ReplayCompatibilityError("Representative track is not aligned or matched.");
    }
  }
  return bundle;
}
