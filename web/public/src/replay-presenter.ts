import type {
  ReplayBundleV1,
  ReplayRegime,
  ReplaySector,
} from "../../replay/replay-v1-contract.d.ts";

export type StorySceneId =
  | "orientation"
  | "shock"
  | "imports"
  | "prices"
  | "debt"
  | "feedback";

export interface StoryScene {
  id: StorySceneId;
  title: string;
  month: string;
  summary: string;
  trace: string;
  focus: ReplaySector[];
}

export const SECTOR_LABELS: Record<ReplaySector, string> = {
  households: "Households",
  firms: "Firms and shops",
  banks: "Banks",
  government: "Government",
  central_bank: "Central bank",
  foreign: "Foreign sector and harbor",
};

export const FLOW_LABELS: Record<string, string> = {
  wages: "Wages",
  consumption: "Consumption",
  imports: "Imports",
  interest: "Interest",
  principal_payment: "Principal payment",
  bank_dividend: "Bank dividend",
};

export function formatValue(value: number | null, unit: string | null): string {
  if (value === null) return "Not available";
  if (unit === "ISK")
    return `${new Intl.NumberFormat("en-IS").format(value)} ISK`;
  if (unit === "basis_points") return `${(value / 100).toFixed(2)}%`;
  if (unit === "index") return (value / 1000).toFixed(3);
  if (unit === "households")
    return `${new Intl.NumberFormat("en-IS").format(value)} households`;
  if (unit === "physical_units")
    return `${new Intl.NumberFormat("en-IS").format(value)} units`;
  return new Intl.NumberFormat("en-IS").format(value);
}

function firstMonth<T>(
  values: T[],
  predicate: (value: T) => boolean,
  fallback: string,
): string {
  return (
    (values.find(predicate) as (T & { month?: string }) | undefined)?.month ??
    fallback
  );
}

export function storyScenes(
  replay: ReplayBundleV1,
  regime: ReplayRegime,
): StoryScene[] {
  const first = replay.manifest.months[0]!;
  const shockMonth = firstMonth(
    replay.events,
    (event) => event.regime === regime && event.event_type === "FX_SHOCK",
    first,
  );
  const importMonth = firstMonth(
    replay.sector_flows,
    (flow) =>
      flow.regime === regime &&
      flow.flow_type === "imports" &&
      flow.month >= shockMonth,
    shockMonth,
  );
  const cpi = replay.aggregate_series.find(
    (series) => series.regime === regime && series.name === "cpi_level",
  );
  const initialCpi = cpi?.points[0]?.value;
  const priceMonth =
    cpi?.points.find(
      (point) =>
        point.month >= shockMonth &&
        point.value !== null &&
        initialCpi !== null &&
        point.value !== initialCpi,
    )?.month ?? shockMonth;
  const debtMonth = firstMonth(
    replay.events,
    (event) =>
      event.regime === regime && event.event_type === "CPI_REVALUATION",
    priceMonth,
  );
  const feedbackMonth = firstMonth(
    replay.events,
    (event) =>
      event.regime === regime &&
      ["ARREARS", "DEFAULT", "POLICY_RATE_CHANGE"].includes(event.event_type),
    debtMonth,
  );

  return [
    {
      id: "orientation",
      title: "The economic circuit",
      month: first,
      summary:
        "Households, firms, banks, policy institutions, and the foreign sector exchange recorded flows each month.",
      trace:
        "Sector snapshots and ledger-linked flows in the published replay.",
      focus: [],
    },
    {
      id: "shock",
      title: "The exchange-rate shock",
      month: shockMonth,
      summary:
        "The configured depreciation changes the recorded exchange-rate and import-price paths.",
      trace: "FX_SHOCK event and exchange-rate series.",
      focus: ["foreign"],
    },
    {
      id: "imports",
      title: "Imported inputs cost more",
      month: importMonth,
      summary:
        "Firms pay the foreign sector for imported inputs at the shocked price path.",
      trace: "Imports flow with its source ledger entry.",
      focus: ["foreign", "firms"],
    },
    {
      id: "prices",
      title: "Firm prices move the CPI",
      month: priceMonth,
      summary:
        "Recorded transactions at firms' adjusted prices raise the consumer price index.",
      trace: "CPI level and monthly inflation series.",
      focus: ["firms", "households"],
    },
    {
      id: "debt",
      title: "The price index rewrites debt",
      month: debtMonth,
      summary:
        regime === "indexed"
          ? "Lagged CPI growth is posted to indexed mortgage principal on both household and bank balance sheets."
          : "This nominal run records no CPI principal revaluation; debt changes through payments and rate resets.",
      trace:
        regime === "indexed"
          ? "CPI_REVALUATION event and mirrored mortgage positions."
          : "Mortgage principal series and settlement flows.",
      focus: ["households", "banks"],
    },
    {
      id: "feedback",
      title: "Households and banks respond",
      month: feedbackMonth,
      summary:
        "Debt service, arrears, defaults, consumption, bank equity, and later policy decisions record the feedback.",
      trace: "Typed events, household tracks, and aggregate series.",
      focus: ["households", "banks", "central_bank"],
    },
  ];
}

export function seriesValue(
  replay: ReplayBundleV1,
  regime: ReplayRegime,
  name: string,
  month: string,
): { value: number | null; unit: string } | null {
  const series = replay.aggregate_series.find(
    (candidate) => candidate.regime === regime && candidate.name === name,
  );
  if (!series) return null;
  return {
    value: series.points.find((point) => point.month === month)?.value ?? null,
    unit: series.unit,
  };
}
