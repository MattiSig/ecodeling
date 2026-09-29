import { describe, expect, it } from "vitest";

import type { ReplayBundleV1 } from "../../replay/replay-v1-contract.d.ts";
import { formatValue, storyScenes } from "../src/replay-presenter.js";

const replay = {
  manifest: { months: ["2025-01", "2025-02", "2025-03"] },
  events: [
    { regime: "indexed", month: "2025-02", event_type: "FX_SHOCK" },
    { regime: "indexed", month: "2025-03", event_type: "CPI_REVALUATION" },
  ],
  sector_flows: [{ regime: "indexed", month: "2025-02", flow_type: "imports" }],
  aggregate_series: [
    {
      regime: "indexed",
      name: "cpi_level",
      points: [
        { month: "2025-01", value: 100000 },
        { month: "2025-02", value: 101000 },
      ],
    },
  ],
} as ReplayBundleV1;

describe("replay presentation derivation", () => {
  it("anchors every guided scene to a replay month", () => {
    expect(storyScenes(replay, "indexed").map((scene) => scene.month)).toEqual([
      "2025-01",
      "2025-02",
      "2025-02",
      "2025-02",
      "2025-03",
      "2025-03",
    ]);
  });

  it("formats exact replay units without inventing precision", () => {
    expect(formatValue(3020740, "ISK")).toContain("3,020,740");
    expect(formatValue(445, "basis_points")).toBe("4.45%");
    expect(formatValue(null, "ISK")).toBe("Not available");
  });
});
