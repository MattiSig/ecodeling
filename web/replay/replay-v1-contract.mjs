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
    throw new ReplayCompatibilityError(
      `Unsupported replay schema version: ${String(version)}.`,
    );
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
    if (!(table in bundle))
      throw new ReplayCompatibilityError(`Replay table is missing: ${table}.`);
  }
  const months = bundle.manifest.months;
  if (
    !Array.isArray(months) ||
    bundle.timeline.length !== months.length ||
    bundle.timeline.some(
      (point, index) => point.index !== index || point.month !== months[index],
    )
  ) {
    throw new ReplayCompatibilityError("Replay timeline is not aligned.");
  }
  if (bundle.runs.map((run) => run.regime).join(",") !== "nominal,indexed") {
    throw new ReplayCompatibilityError(
      "Replay must contain aligned nominal and indexed runs.",
    );
  }
  const nominalRun = bundle.runs[0];
  const indexedRun = bundle.runs[1];
  const pairing = bundle.scenario_pairing;
  if (
    !pairing ||
    pairing.nominal_run_id !== nominalRun.run_id ||
    pairing.indexed_run_id !== indexedRun.run_id ||
    pairing.shared_seed !== bundle.manifest.seed ||
    pairing.shared_initialization !== true ||
    pairing.shared_shock_path !== true ||
    !Array.isArray(pairing.shared_random_streams) ||
    pairing.shared_random_streams.length === 0 ||
    typeof pairing.structural_difference !== "string" ||
    pairing.structural_difference.length === 0
  ) {
    throw new ReplayCompatibilityError("Replay pairing metadata is invalid.");
  }
  if (
    typeof byteLength === "number" &&
    byteLength > bundle.manifest.maximum_uncompressed_bytes
  ) {
    throw new ReplayCompatibilityError(
      "Replay exceeds its declared payload-size limit.",
    );
  }
  for (const agent of bundle.representative_agents) {
    if (
      typeof agent.matched_household_id !== "string" ||
      agent.track.length !== months.length ||
      agent.track.some((point, index) => point.month !== months[index])
    ) {
      throw new ReplayCompatibilityError(
        "Representative track alignment or counterpart ID is invalid.",
      );
    }
  }
  const seriesKeys = new Map();
  for (const series of bundle.aggregate_series) {
    const key = series.name;
    const peer = seriesKeys.get(key);
    if (
      peer &&
      (peer.unit !== series.unit ||
        peer.nominal_status !== series.nominal_status)
    ) {
      throw new ReplayCompatibilityError(
        "Paired aggregate series units are not aligned.",
      );
    }
    if (
      series.points.length !== months.length ||
      series.points.some((point, index) => point.month !== months[index])
    ) {
      throw new ReplayCompatibilityError(
        "Paired aggregate series timeline is not aligned.",
      );
    }
    seriesKeys.set(key, series);
  }
  return bundle;
}
