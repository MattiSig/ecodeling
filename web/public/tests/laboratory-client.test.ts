import { describe, expect, it, vi } from "vitest";

import {
  createLaboratoryExperiment,
  waitForLaboratoryExperiment,
  type LaboratoryParameters,
} from "../src/laboratory-client.js";

const parameters: LaboratoryParameters = {
  months: 18,
  seed: 1010,
  households: 20,
  firms: 4,
  indexation_lag_months: 1,
  shock_kind: "fx_depreciation",
  shock_month: 3,
  shock_magnitude_bps: 1000,
  shock_persistence: "permanent",
  import_share_bps: 2500,
  price_adjustment_bps: 2500,
};

describe("laboratory client", () => {
  it("submits only the explicit public parameter payload", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          job_id: "job-1",
          status: "queued",
          cached: false,
          model_version: "0.0.0",
          configuration_hash: "hash",
          links: { status: "/status", result: "/result" },
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      ),
    );
    await createLaboratoryExperiment("/api/v1", parameters, { fetcher });
    const request = fetcher.mock.calls[0] as [string, RequestInit];
    expect(request[0]).toBe("/api/v1/experiments");
    expect(JSON.parse(request[1].body as string)).toEqual(parameters);
  });

  it("polls through progress and returns the completed result URL", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            job_id: "job-1",
            status: "running",
            progress_percent: 50,
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            job_id: "job-1",
            status: "completed",
            progress_percent: 100,
            result_url: "/result",
          }),
          { status: 200 },
        ),
      );
    const updates = vi.fn();
    const progress = await waitForLaboratoryExperiment("/status", {
      fetcher,
      intervalMs: 0,
      onProgress: updates,
    });
    expect(progress.result_url).toBe("/result");
    expect(updates).toHaveBeenCalledTimes(2);
  });

  it("surfaces structured failures for retry without touching replay state", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "queue_full", message: "Try again shortly." },
        }),
        { status: 429 },
      ),
    );
    await expect(
      createLaboratoryExperiment("/api/v1", parameters, { fetcher }),
    ).rejects.toMatchObject(
      expect.objectContaining({
        name: "LaboratoryError",
        code: "queue_full",
        message: "Try again shortly.",
      }),
    );
  });
});
