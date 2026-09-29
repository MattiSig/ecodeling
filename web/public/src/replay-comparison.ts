import type {
  ReplayBundleV1,
  ReplayRegime,
} from "../../replay/replay-v1-contract.d.ts";

export interface ComparisonMetric {
  name: string;
  label: string;
}

export const COMPARISON_METRICS: readonly ComparisonMetric[] = [
  { name: "cpi_level", label: "CPI" },
  { name: "policy_rate", label: "Policy rate" },
  { name: "mortgage_principal", label: "Mortgage principal" },
  { name: "debt_service", label: "Debt service" },
  { name: "consumption", label: "Consumption" },
  { name: "real_consumption", label: "Goods consumed" },
  { name: "employment", label: "Employment" },
  { name: "defaults", label: "Defaults" },
  { name: "bank_equity", label: "Bank equity" },
] as const;

export interface PairedPoint {
  month: string;
  nominal: number | null;
  indexed: number | null;
  difference: number | null;
}

export interface PairedSeries {
  name: string;
  unit: string;
  points: PairedPoint[];
}

export function pairedSeries(
  replay: ReplayBundleV1,
  name: string,
): PairedSeries | null {
  const nominal = replay.aggregate_series.find(
    (series) => series.regime === "nominal" && series.name === name,
  );
  const indexed = replay.aggregate_series.find(
    (series) => series.regime === "indexed" && series.name === name,
  );
  if (!nominal || !indexed || nominal.unit !== indexed.unit) return null;
  const indexedByMonth = new Map(
    indexed.points.map((point) => [point.month, point.value]),
  );
  return {
    name,
    unit: nominal.unit,
    points: nominal.points.map((point) => {
      const indexedValue = indexedByMonth.get(point.month) ?? null;
      return {
        month: point.month,
        nominal: point.value,
        indexed: indexedValue,
        difference:
          point.value === null || indexedValue === null
            ? null
            : indexedValue - point.value,
      };
    }),
  };
}

export type CohortMeasure =
  | "consumption_isk"
  | "mortgage_principal_isk"
  | "debt_service_isk"
  | "net_worth_isk"
  | "defaults";

export interface CohortDifference {
  cohort: string;
  nominal: number;
  indexed: number;
  difference: number;
}

export function cohortDifferences(
  replay: ReplayBundleV1,
  month: string,
  dimension: string,
  measure: CohortMeasure,
): CohortDifference[] {
  const points = replay.distribution_series.filter(
    (point) => point.month === month && point.dimension === dimension,
  );
  const nominal = new Map(
    points
      .filter((point) => point.regime === "nominal")
      .map((point) => [point.cohort, point[measure]]),
  );
  return points
    .filter((point) => point.regime === "indexed")
    .filter((point) => nominal.has(point.cohort))
    .map((point) => ({
      cohort: point.cohort,
      nominal: nominal.get(point.cohort)!,
      indexed: point[measure],
      difference: point[measure] - nominal.get(point.cohort)!,
    }))
    .sort((left, right) => left.cohort.localeCompare(right.cohort));
}

export interface RepresentativeComparison {
  kind: "individual" | "cohort";
  cohort: string;
  nominalId: string | null;
  indexedId: string | null;
}

export function representativeComparison(
  replay: ReplayBundleV1,
  regime: ReplayRegime,
  householdId: string,
): RepresentativeComparison | null {
  const source = replay.representative_agents.find(
    (agent) => agent.regime === regime && agent.household_id === householdId,
  );
  if (!source) return null;
  const otherRegime = regime === "nominal" ? "indexed" : "nominal";
  const individual = replay.representative_agents.find(
    (agent) =>
      agent.regime === otherRegime &&
      agent.household_id === source.matched_household_id &&
      agent.matched_household_id === source.household_id,
  );
  if (individual) {
    return {
      kind: "individual",
      cohort: source.cohort,
      nominalId:
        regime === "nominal" ? source.household_id : individual.household_id,
      indexedId:
        regime === "indexed" ? source.household_id : individual.household_id,
    };
  }
  const cohortPeer = replay.representative_agents.find(
    (agent) => agent.regime === otherRegime && agent.cohort === source.cohort,
  );
  return {
    kind: "cohort",
    cohort: source.cohort,
    nominalId:
      regime === "nominal"
        ? source.household_id
        : (cohortPeer?.household_id ?? null),
    indexedId:
      regime === "indexed"
        ? source.household_id
        : (cohortPeer?.household_id ?? null),
  };
}
