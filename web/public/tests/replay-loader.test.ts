import { describe, expect, it, vi } from "vitest";

import { loadReplay, ReplayLoadError } from "../src/replay-loader.js";

const validReplay = {
  manifest: {
    schema_version: 1,
    bundle_id: "test",
    model_version: "0.0.0",
    git_commit: "abc",
    scenario_id: "test",
    seed: 1,
    months: ["2025-01"],
    maximum_uncompressed_bytes: 20_000,
  },
  timeline: [
    { index: 0, month: "2025-01", shock: false, policy_decision: false },
  ],
  runs: [
    { regime: "nominal", run_id: "n", configuration_hash: "n" },
    { regime: "indexed", run_id: "i", configuration_hash: "i" },
  ],
  sector_snapshots: [],
  sector_flows: [],
  events: [],
  representative_agents: [],
  aggregate_series: [],
  distribution_series: [],
  scenario_pairing: {
    nominal_run_id: "n",
    indexed_run_id: "i",
    shared_seed: 1,
    shared_initialization: true,
    shared_shock_path: true,
    shared_random_streams: ["shocks"],
    structural_difference: "mortgage_indexation_topology",
    matching: "stable_household_id",
  },
};

describe("loadReplay", () => {
  it("loads and validates an uncompressed replay", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(validReplay), {
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(
      loadReplay("/replay.json", { fetcher }),
    ).resolves.toMatchObject({
      manifest: { bundle_id: "test" },
    });
  });

  it("classifies incompatible schemas", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        new Response(JSON.stringify({ manifest: { schema_version: 2 } })),
      );
    const result = loadReplay("/replay.json", { fetcher });
    await expect(result).rejects.toBeInstanceOf(ReplayLoadError);
    await expect(result).rejects.toMatchObject({ kind: "compatibility" });
  });

  it("classifies failed requests", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response("missing", { status: 404 }));
    await expect(
      loadReplay("/missing.json", { fetcher }),
    ).rejects.toMatchObject({
      kind: "network",
    });
  });
});
