import type { ReplayBundleV1 } from "../../replay/replay-v1-contract.d.ts";
import { loadReplay } from "./replay-loader.js";

export interface LaboratoryParameters {
  months: number;
  seed: number;
  households: number;
  firms: number;
  indexation_lag_months: number;
  shock_kind: "fx_depreciation" | "foreign_price_increase";
  shock_month: number;
  shock_magnitude_bps: number;
  shock_persistence: "one_off" | "permanent";
  import_share_bps: number;
  price_adjustment_bps: number;
}

export interface LaboratoryJob {
  job_id: string;
  status: string;
  cached: boolean;
  configuration_hash: string;
  model_version: string;
  links: { status: string; result: string };
}

export interface LaboratoryProgress {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress_percent: number;
  result_url?: string;
  failure?: { code: string; message: string };
}

export class LaboratoryError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = "LaboratoryError";
    this.code = code;
  }
}

async function apiJson<T>(
  url: string,
  init: RequestInit,
  fetcher: typeof fetch,
): Promise<T> {
  const response = await fetcher(url, init);
  const body = (await response.json().catch(() => null)) as {
    error?: { code?: string; message?: string };
  } | null;
  if (!response.ok) {
    throw new LaboratoryError(
      body?.error?.code ?? `http_${response.status}`,
      body?.error?.message ??
        `The experiment service returned ${response.status}.`,
    );
  }
  return body as T;
}

export async function createLaboratoryExperiment(
  apiBase: string,
  parameters: LaboratoryParameters,
  options: { signal?: AbortSignal; fetcher?: typeof fetch } = {},
): Promise<LaboratoryJob> {
  const init: RequestInit = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(parameters),
  };
  if (options.signal !== undefined) init.signal = options.signal;
  return apiJson<LaboratoryJob>(
    `${apiBase.replace(/\/$/, "")}/experiments`,
    init,
    options.fetcher ?? fetch,
  );
}

export async function waitForLaboratoryExperiment(
  statusUrl: string,
  options: {
    signal?: AbortSignal;
    fetcher?: typeof fetch;
    intervalMs?: number;
    onProgress?: (progress: LaboratoryProgress) => void;
  } = {},
): Promise<LaboratoryProgress> {
  const fetcher = options.fetcher ?? fetch;
  for (;;) {
    const init: RequestInit = {};
    if (options.signal !== undefined) init.signal = options.signal;
    const progress = await apiJson<LaboratoryProgress>(
      statusUrl,
      init,
      fetcher,
    );
    options.onProgress?.(progress);
    if (progress.status === "completed") return progress;
    if (progress.status === "failed" || progress.status === "cancelled") {
      throw new LaboratoryError(
        progress.failure?.code ?? progress.status,
        progress.failure?.message ??
          `The custom experiment was ${progress.status}.`,
      );
    }
    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(resolve, options.intervalMs ?? 750);
      options.signal?.addEventListener(
        "abort",
        () => {
          window.clearTimeout(timer);
          reject(new DOMException("Aborted", "AbortError"));
        },
        { once: true },
      );
    });
  }
}

export async function runLaboratoryExperiment(
  apiBase: string,
  parameters: LaboratoryParameters,
  options: {
    signal?: AbortSignal;
    fetcher?: typeof fetch;
    onProgress?: (progress: LaboratoryProgress) => void;
  } = {},
): Promise<{ job: LaboratoryJob; replay: ReplayBundleV1 }> {
  const job = await createLaboratoryExperiment(apiBase, parameters, options);
  const progress = await waitForLaboratoryExperiment(job.links.status, options);
  const replayOptions: { signal?: AbortSignal; fetcher?: typeof fetch } = {};
  if (options.signal !== undefined) replayOptions.signal = options.signal;
  if (options.fetcher !== undefined) replayOptions.fetcher = options.fetcher;
  const replay = await loadReplay(
    progress.result_url ?? job.links.result,
    replayOptions,
  );
  return { job, replay };
}

export async function cancelLaboratoryExperiment(
  statusUrl: string,
  options: { fetcher?: typeof fetch } = {},
): Promise<void> {
  await apiJson(statusUrl, { method: "DELETE" }, options.fetcher ?? fetch);
}
