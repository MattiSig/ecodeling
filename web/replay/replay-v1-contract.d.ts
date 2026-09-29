export type ReplayRegime = "nominal" | "indexed";
export type ReplaySector =
  | "households"
  | "firms"
  | "banks"
  | "government"
  | "central_bank"
  | "foreign";

export interface ReplayManifestV1 {
  schema_version: 1;
  bundle_id: string;
  model_version: string;
  git_commit: string;
  scenario_id: string;
  seed: number;
  months: string[];
  maximum_uncompressed_bytes: number;
}

export interface ReplayBundleV1 {
  manifest: ReplayManifestV1;
  timeline: Array<{ index: number; month: string; shock: boolean; policy_decision: boolean }>;
  runs: Array<{ regime: ReplayRegime; run_id: string; configuration_hash: string }>;
  sector_snapshots: Array<{
    regime: ReplayRegime;
    month: string;
    sector: ReplaySector;
    financial_assets_isk: number | null;
    real_assets_isk: number | null;
    liabilities_isk: number | null;
    equity_isk: number | null;
    inventory_units: number | null;
  }>;
  sector_flows: Array<{
    regime: ReplayRegime;
    month: string;
    flow_type:
      | "wages"
      | "consumption"
      | "imports"
      | "interest"
      | "principal_payment"
      | "bank_dividend";
    source_sector: ReplaySector;
    target_sector: ReplaySector;
    amount_isk: number;
    ledger_entry_id: string;
  }>;
  events: Array<{
    id: string;
    regime: ReplayRegime;
    month: string;
    event_type:
      | "FX_SHOCK"
      | "FOREIGN_PRICE_SHOCK"
      | "CPI_REVALUATION"
      | "POLICY_RATE_CHANGE"
      | "RATE_RESET"
      | "ARREARS"
      | "DEFAULT";
    amount: number | null;
    unit: "ISK" | "basis_points" | "households" | null;
    source_id: string;
  }>;
  representative_agents: Array<{
    regime: ReplayRegime;
    cohort: string;
    household_id: string;
    matched_household_id: string;
    track: Array<{
      month: string;
      wage_income_isk: number;
      consumption_isk: number;
      deposits_isk: number;
      mortgage_principal_isk: number;
      mortgage_payment_isk: number;
      mortgage_revaluation_isk: number;
      arrears_isk: number;
      defaulted: boolean;
    }>;
  }>;
  aggregate_series: Array<{
    regime: ReplayRegime;
    name: string;
    unit: string;
    nominal_status: string;
    points: Array<{ month: string; value: number | null }>;
  }>;
  distribution_series: Array<{
    regime: ReplayRegime;
    month: string;
    dimension: string;
    cohort: string;
    households: number;
    income_isk: number;
    consumption_isk: number;
    deposits_isk: number;
    mortgage_principal_isk: number;
    mortgage_revaluation_isk: number;
    debt_service_isk: number;
    net_worth_isk: number;
    defaults: number;
  }>;
  scenario_pairing: object;
}

export class ReplayCompatibilityError extends Error {}
export function validateReplayV1(bundle: unknown, byteLength?: number): ReplayBundleV1;
